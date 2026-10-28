"""Numbered spec tests plus one independently named test per template phrase."""
import builtins
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from printer_claim_audit import audit, claims, evidence, normalize
from printer_claim_audit.__main__ import main
from printer_claim_audit.phrases import PRINTER, NOPRINTER

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures'
GOOD = (FIXTURES / 'good' / 'app.py').read_text()


class AuditTests(unittest.TestCase):
    def check_project(self, doc, source=None, location='app.py', fail_on='HIGH'):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text(doc)
            if source is not None:
                target = root / location
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
            return audit(root, fail_on=fail_on)

    def assert_high(self, result, rule='documented-printer-claim-false'):
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertEqual(result['findings'][0]['rule'], rule)

    def test_27_denial(self):
        self.assert_high(audit(FIXTURES / 'no_printer'), 'documented-no-printer-claim-false')

    def test_28_no_claim(self):
        self.assertEqual(self.check_project('Local utility.', GOOD)['findings'], [])

    def test_29_bare_noun(self):
        self.assertEqual(self.check_project('the printer chapter explains delivery', 'import cups')['findings'], [])

    def test_30_user_instruction(self):
        for doc in ('connect your printer before starting', 'load paper into your printer first'):
            self.assertEqual(self.check_project(doc, 'import cups')['findings'], [])

    def test_31_console(self):
        self.assertEqual(self.check_project('prints results to the console', 'print("hi")')['findings'], [])

    def test_32_pdf(self):
        self.assertEqual(self.check_project('exports a PDF for later printing', 'import reportlab')['findings'], [])

    def test_33_no_source(self):
        self.assert_high(self.check_project(PRINTER[0]))
        self.assertEqual(self.check_project(NOPRINTER[0])['findings'], [])

    def test_34_test_only(self):
        for location in ('tests/jobs.py', 'test_jobs.py', 'jobs_test.py'):
            for threshold, verdict in [('HIGH', 'PASS'), ('MEDIUM', 'FAIL')]:
                result = self.check_project(PRINTER[0], GOOD, location, threshold)
                self.assertEqual(result['verdict'], verdict)
                self.assertEqual(result['findings'][0]['severity'], 'MEDIUM')

    def test_35_fences_inline(self):
        for fence in ('```', '~~~~'):
            self.assertEqual(self.check_project(fence + '\n' + PRINTER[0] + '\n' + fence)['findings'], [])
        self.assert_high(self.check_project('`' + PRINTER[0] + '`'))

    def test_36_negation(self):
        self.assertEqual(claims('does not print documents to your printer'), (False, True))

    def test_37_self_audit(self):
        self.assertEqual(audit(ROOT)['findings'], [])
        for path in [ROOT / 'README.md'] + list(ROOT.glob('**/docs/**/*.md')):
            text = normalize(path.read_text())
            for phrase in PRINTER + NOPRINTER:
                self.assertIsNone(re.search(r'\b' + re.escape(phrase) + r'\b', text), (path, phrase))
            self.assertIsNone(re.search(r'\b(using|uses|with|via|over|supports|sends|send)\s+printer claim audit\b', text))

    def invoke(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = main(args)
            except SystemExit as exc:
                code = exc.code
        return code, output.getvalue()

    def test_38_cli(self):
        self.assertEqual(self.invoke(['--version']), (0, '0.1.0\n'))
        code, output = self.invoke([str(FIXTURES / 'good'), '--json'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)['verdict'], 'PASS')
        self.assertIn('cups', self.invoke([str(FIXTURES / 'good'), '--verbose'])[1])
        self.assertEqual(self.invoke([str(FIXTURES / 'bad'), '--ignore', 'README.md'])[0], 0)
        self.assertEqual(self.invoke(['/nonexistent/path'])[0], 1)
        self.assertEqual(self.invoke(['--fail-on', 'LOW'])[0], 1)
        self.assertEqual(self.invoke([str(FIXTURES / 'bad')])[0], 2)

    def test_39_env_guard(self):
        original = io.open
        def guarded(path, *args, **kwargs):
            if str(path).endswith('.env'):
                raise AssertionError('environment file opened')
            return original(path, *args, **kwargs)
        with patch('io.open', guarded), patch('builtins.open', guarded):
            self.assertEqual(audit(ROOT)['verdict'], 'PASS')
        self.assertTrue((FIXTURES / '.env').is_file())

    def test_40_packaging(self):
        for path in ROOT.rglob('*'):
            if path.is_file() and (path.suffix == '.py' or path.name == 'README.md'):
                self.assertIsNone(re.search(r'\b' + 'py' + r'thon\b', path.read_text()), str(path))
        config = (ROOT / 'pyproject.toml').read_text()
        self.assertIn('setuptools>=77', config)
        self.assertIn('license = "MIT"', config)
        self.assertIn('>=3.9', config)
        self.assertIn('recursive-include tests', (ROOT / 'MANIFEST.in').read_text())

    def test_41_phrase_inventory(self):
        self.assertEqual(len(PRINTER), 31)
        self.assertEqual(len(NOPRINTER), 18)

    def test_normalization_boundaries(self):
        self.assertEqual(claims("DOESN'T PRINT\nDOCUMENTS TO YOUR PRINTER"), (False, True))
        self.assertEqual(claims('supports-direct-printing'), (True, False))
        self.assertEqual(claims('reprints documentsXYZ'), (False, False))
        self.assertEqual(claims('prints\n\ndocuments'), (False, False))

    def test_extra_routes(self):
        for source in [
            'from cups.sub import Connection as C\nC().printFiles([])',
            'from win32print import OpenPrinter as O, WritePrinter as W\nW(O("p"), b"x")',
            'import win32print as w\nh=w.OpenPrinter("p")\nw.WritePrinter(h,b"x")',
            'import escpos.printer\nescpos.printer.File("f").barcode("x")',
            'from escpos.printer.sub import File as F\nF("f").image("x")']:
            with self.subTest(source=source):
                self.assertTrue(evidence(source))

    def test_extra_non_evidence(self):
        for source in [
            'conn.printFile("x")', 'import escpos\nescpos.Usb(1,2).text("x")',
            'from other import Connection\nConnection().printFile("x")',
            'def print_job():\n    print("x")',
            '@app.post("/print")\ndef job():\n    return "printer"',
            'preview("receipt")', '# cups.Connection().printFile("x")',
            '"""cups.Connection().printFile("x")"""',
            'import subprocess\nsubprocess.run(["lpr", "f"])',
            'import subprocess\nsubprocess.run(["lpstat"])']:
            with self.subTest(source=source):
                self.assertFalse(evidence(source))

    def test_scopes_symlinks_ignore_errors(self):
        for location in ('fixtures/job.py', 'docs/job.py', 'examples/job.py'):
            self.assert_high(self.check_project(PRINTER[0], GOOD, location))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text(PRINTER[0])
            (root / 'linked.py').symlink_to(FIXTURES / 'good' / 'app.py')
            self.assert_high(audit(root))
            (root / 'broken.py').write_text('def (')
            self.assertTrue(audit(root)['parse_errors'])
            docs = root / 'tests' / 'docs'
            docs.mkdir(parents=True)
            (docs / 'guide.md').write_text(NOPRINTER[0])
            (root / 'job.py').write_text(GOOD)
            self.assert_high(audit(root), 'documented-no-printer-claim-false')
            self.assertEqual(audit(root, ['tests/docs/*'])['findings'], [])

    def test_two_families_max(self):
        result = self.check_project('\n\n'.join(PRINTER + NOPRINTER))
        self.assertEqual(len(result['findings']), 1)


def numbered(index):
    def test(self):
        result = audit(FIXTURES / ('case_%02d' % index))
        if index <= 14:
            self.assertEqual(result['findings'], [])
            self.assertTrue(result['evidence'])
        else:
            self.assert_high(result)
    return test


for index in range(1, 27):
    setattr(AuditTests, 'test_%02d_fixture' % index, numbered(index))


def phrase_test(phrase, negative):
    def test(self):
        self.assertEqual(claims(phrase), (not negative, negative))
        if negative:
            self.assert_high(self.check_project(phrase, GOOD), 'documented-no-printer-claim-false')
            self.assertEqual(self.check_project(phrase)['findings'], [])
        else:
            self.assert_high(self.check_project(phrase))
            self.assertEqual(self.check_project(phrase, GOOD)['findings'], [])
    return test


# Every generated method covers exactly the phrase encoded in its method name.
for negative, phrases in [(False, PRINTER), (True, NOPRINTER)]:
    for phrase in phrases:
        setattr(AuditTests, 'test_phrase_' + phrase.replace(' ', '_'), phrase_test(phrase, negative))
