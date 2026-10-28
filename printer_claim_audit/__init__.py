"""Static local hardcopy job submission audit."""
import ast
import fnmatch
import os
import re
from pathlib import Path
from .phrases import PRINTER, NOPRINTER

__version__ = '0.1.0'


def normalize(text):
    return re.sub(r'\s+', ' ', text.lower().replace("n't", ' not').replace('-', ' ')).strip()


def claims(text):
    paragraphs = []
    lines = []
    fence = None
    for line in text.splitlines():
        mark = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if mark:
            token = mark.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        if not line.strip():
            paragraphs.append(normalize(' '.join(lines)))
            lines = []
        else:
            lines.append(line)
    paragraphs.append(normalize(' '.join(lines)))
    positive = negative = False
    for paragraph in paragraphs:
        for phrase in sorted(NOPRINTER, key=len, reverse=True):
            paragraph, count = re.subn(r'\b' + re.escape(phrase) + r'\b', ' ', paragraph)
            negative |= bool(count)
        positive |= any(re.search(r'\b' + re.escape(phrase) + r'\b', paragraph) for phrase in PRINTER)
    return positive, negative


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return base + '.' + node.attr if base else ''
    return ''


def evidence(source):
    """Resolve provider constructors and submission calls within one module."""
    tree = ast.parse(source)
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                aliases[alias.asname or alias.name] = node.module + '.' + alias.name

    def resolve(node):
        path = dotted(node)
        first, sep, rest = path.partition('.')
        return aliases.get(first, first) + (sep + rest if sep else '') if path else ''

    def constructor(node):
        if not isinstance(node, ast.Call):
            return None
        path = resolve(node.func)
        module, _, name = path.rpartition('.')
        if (module == 'cups' or module.startswith('cups.')) and name == 'Connection':
            return 'cups'
        if (module == 'win32print' or module.startswith('win32print.')) and name == 'OpenPrinter':
            return 'win32print'
        if (module == 'escpos.printer' or module.startswith('escpos.printer.')) and name in {'Usb', 'Network', 'Serial', 'File'}:
            return 'escpos'
        return None

    bindings = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            provider = constructor(node.value)
            if provider:
                for target in node.targets:
                    if isinstance(target, ast.Name) or (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self'):
                        bindings[dotted(target)] = provider

    def bound(node, provider):
        return constructor(node) == provider or (isinstance(node, (ast.Name, ast.Attribute)) and bindings.get(dotted(node)) == provider)

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        route = None
        if isinstance(func, ast.Attribute):
            if func.attr in {'printFile', 'printFiles'} and bound(func.value, 'cups'):
                route = 'cups'
            elif func.attr in {'text', 'image', 'cut', 'qr', 'barcode'} and bound(func.value, 'escpos'):
                route = 'escpos'
        path = resolve(func)
        module, _, name = path.rpartition('.')
        if name == 'WritePrinter' and (module == 'win32print' or module.startswith('win32print.')) and node.args and bound(node.args[0], 'win32print'):
            route = 'win32print'
        if route:
            found.append({'line': node.lineno, 'provider': route})
    return found


def audit(root, ignore=(), fail_on='HIGH'):
    root = Path(root)
    if not root.is_dir() or not os.access(root, os.R_OK | os.X_OK):
        raise ValueError('root must be a readable directory')
    positive = negative = False
    production = []
    test_evidence = []
    errors = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
        for filename in sorted(files):
            path = Path(directory) / filename
            rel = path.relative_to(root)
            name = rel.as_posix()
            if path.is_symlink() or any(fnmatch.fnmatchcase(name, pattern) for pattern in ignore):
                continue
            is_doc = name == 'README.md' or (path.suffix.lower() == '.md' and 'docs' in rel.parts[:-1])
            if is_doc:
                a, b = claims(path.read_text(encoding='utf-8'))
                positive |= a
                negative |= b
            if path.suffix != '.py':
                continue
            parts = rel.parts[:-1]
            if any(p in {'fixtures', 'docs', 'examples'} for p in parts):
                continue
            test = 'tests' in parts or filename.startswith('test_') or filename.endswith('_test.py')
            try:
                hits = evidence(path.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeError) as exc:
                errors.append({'path': name, 'message': str(exc)})
                continue
            for hit in hits:
                hit['path'] = name
                (test_evidence if test else production).append(hit)
    findings = []
    if positive and not production:
        findings.append({'rule': 'documented-printer-claim-false', 'severity': 'MEDIUM' if test_evidence else 'HIGH', 'message': 'Local-job claim lacks production submission evidence.'})
    if negative and production:
        findings.append({'rule': 'documented-no-printer-claim-false', 'severity': 'HIGH', 'message': 'Local-job denial conflicts with production submission evidence.'})
    failed = any(f['severity'] == 'HIGH' or fail_on == 'MEDIUM' for f in findings)
    return {'verdict': 'FAIL' if failed else 'PASS', 'findings': findings, 'evidence': production, 'test_evidence': test_evidence, 'parse_errors': errors, 'claims': {'positive': positive, 'negative': negative}}
