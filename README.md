# printer-claim-audit

An offline static audit for local hardcopy job submission claims. It compares
root README.md and Markdown files beneath a docs path component against Python
AST evidence of attached printing device intake. Source is never executed.
No runtime dependencies are required. Python 3.9 or newer is required.

Install and run:

```sh
python3 -m pip install .
printer-claim-audit /path/to/project --json
python3 -m printer_claim_audit /path/to/project --verbose
```

Options: `--ignore <glob>` is repeatable and matches root-relative paths;
`--fail-on HIGH` is the default; `--fail-on MEDIUM` also fails on evidence
found only in test source. `--version` reports 0.1.0. JSON includes verdict,
findings, production and test evidence locations, claim flags, and parse errors.
Human output lists findings; verbose output also lists evidence and parse errors.
Exit 0 means PASS, exit 2 means findings meet the severity threshold, and exit 1
means invalid usage or an inaccessible root. Findings below the threshold remain
visible even when the verdict is PASS. At most one finding per claim family is emitted.

## Limitations

Only the exact phrase templates in the package's `phrases.py` are recognized.
A bare device noun, tool name, dependency list, user instruction, console message,
PDF export, file save, screen grab, audio capture, or network send is outside
that vocabulary. Fenced blocks are excluded; inline code counts. Paragraphs are
normalized for case, contractions, hyphens, and whitespace. Denial spans are
removed before affirmative matching.

Evidence recognizes bound cups Connection job methods, win32print handle writes,
and escpos.printer object job methods. Imports, constructors alone, previews,
strings, comments, and docstrings do not establish capability. Shell spool helpers
such as lp, lpr, and lpstat are outside the recognized routes.

Bindings and aliases are module-local syntactic approximations; this tool does
not prove execution, device availability, delivery, control flow, or runtime name
identity. Syntax errors are reported and contribute no evidence. Test source can
reduce an unsupported affirmative assertion to MEDIUM; a denial contradicted by
production evidence is HIGH. An affirmative assertion without source is HIGH;
a denial without source passes. No recognized assertion means PASS.

Production excludes tests, test-named modules, fixtures, docs, examples, and
symlinked files or directories. Environment files are never opened. Ignore globs
apply to documentation and source. Markdown under any docs path component counts,
including documentation beneath test directories.

Run checks and build distributions:

```sh
python3 -m unittest discover
python3 -m build
```

The tests and fixtures are included in the source distribution. License: MIT.
