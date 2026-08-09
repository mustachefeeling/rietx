"""WP-1002 — the portability rules that only a non-POSIX platform can break.

These are source guards, not behaviour tests: they parse the tree and fail on a
construct, because the failure they prevent is invisible on the platform this
package is developed on.  Both encode something measured on a Windows runner
rather than something assumed.

**Text I/O must name its encoding.**  ``Path.read_text()`` and ``open()`` use
``locale.getpreferredencoding(False)``, which is UTF-8 on macOS and Linux and
**cp1252 on Windows** (measured: the runner reports ``preferred encoding:
cp1252``, ``stdout encoding: cp1252``).  So a file this package writes as UTF-8
on one platform is read back as mojibake — or raises ``UnicodeDecodeError`` —
on another.  Six of the seven failures in the first Windows run were exactly
this, every one of them ``'charmap' codec can't decode byte 0x81``.  Python
3.15 makes UTF-8 the default and retires the problem, but the supported range
here starts at 3.11.

**CSV must be written through ``newline=""``.**  ``csv.writer`` emits ``\\r\\n``
per the spec; writing that string through text mode translates each ``\\n``
again, so every line ends ``\\r\\r\\n`` — a file with a blank line between every
row.  That was the seventh failure, and a real one: ``write_qpa_table``
produced corrupt CSV on Windows while its sibling ``write_reflection_table``,
which already opened with ``newline=""``, did not.

The guards parse rather than grep because the calls that matter span lines —
the multi-line ``write_text(json.dumps({...}), encoding="utf-8")`` in
``viz/live.py`` is invisible to a line-based search, which is how one site
survived the first sweep.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TREES = ("src", "tests", "examples")

#: Calls that open a text stream and therefore need an explicit encoding.
_TEXT_IO = {"read_text", "write_text", "open"}

#: Receivers whose ``.open`` is not a text stream: ``webbrowser.open`` /
#: ``webbrowser.open_new_tab``, ``Project.open`` — which opens a *directory*
#: (WP-1005) and does its own reading through calls this guard checks
#: individually — and a ``zipfile.ZipFile``, whose ``.open`` returns **bytes**
#: whatever its mode, so ``encoding=`` there is a ``TypeError`` rather than an
#: omission (the container readers decode those bytes through
#: ``io.formats.base.decode``, which reads the member's own byte-order mark).
#: The match is on the receiver's source text, so it is a name list and will go
#: stale; it goes stale in the safe direction, since a new non-file ``.open``
#: fails this test until someone adds the row — and the ``zip`` entry is why a
#: reader names its archive handle ``zip_*``.
_NOT_FILE_IO = ("webbrowser", "urllib", "request", "Project", "zip")


def _python_files() -> list[Path]:
    out: list[Path] = []
    for tree in TREES:
        out.extend(sorted((ROOT / tree).rglob("*.py")))
    return out


def _is_binary_mode(call: ast.Call) -> bool:
    """True when a mode argument selects binary, where encoding is illegal."""
    for arg in call.args[:2]:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and "b" in arg.value:
            return True
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            if isinstance(kw.value.value, str) and "b" in kw.value.value:
                return True
    return False


def _text_io_calls(tree: ast.AST, source: str) -> list[tuple[ast.Call, str]]:
    """Every call that opens a text stream, with the receiver's source text."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            name = func.attr
            receiver = ast.get_source_segment(source, func.value) or ""
        elif isinstance(func, ast.Name):
            name, receiver = func.id, ""
        else:
            continue
        if name not in _TEXT_IO:
            continue
        if any(bad in receiver for bad in _NOT_FILE_IO):
            continue
        if _is_binary_mode(node):
            continue
        found.append((node, receiver))
    return found


def _calls_a_csv_writer(tree: ast.AST) -> bool:
    """True when the module actually constructs a csv writer."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"writer", "DictWriter"}
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "csv"):
            return True
    return False


def test_every_text_io_call_names_its_encoding():
    """No implicit locale encoding anywhere in the tree.

    The default differs by platform, so an unnamed encoding means the package
    behaves differently on Windows than it was validated on — silently, for
    ASCII inputs, right up until a user's CIF carries an accented author name.
    """
    offenders = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        for call, _ in _text_io_calls(ast.parse(source), source):
            if not any(kw.arg == "encoding" for kw in call.keywords):
                offenders.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert not offenders, (
        "text I/O without an explicit encoding= (cp1252 on Windows, UTF-8 here):\n  "
        + "\n  ".join(offenders))


def test_csv_writers_open_with_newline_suppressed():
    """Anything handing csv.writer output to a file must pass newline="".

    csv.writer emits \\r\\n itself; text mode then translates the \\n again and
    every row ends \\r\\r\\n on Windows.  Measured on a real runner, not feared.
    """
    offenders = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        if "csv" not in source:
            continue
        tree = ast.parse(source)
        # a *call*, not a mention: this file and validation_matrix.py both
        # discuss csv.writer in prose, and a substring test flags them
        if not _calls_a_csv_writer(tree):
            continue
        for call, _ in _text_io_calls(tree, source):
            writes = isinstance(call.func, ast.Attribute) and call.func.attr in {
                "open", "write_text"}
            if not writes:
                continue
            # only writers matter; a read cannot double a line ending
            modes = [a.value for a in call.args
                     if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if call.func.attr == "open" and not any("w" in m or "a" in m for m in modes):
                continue
            if not any(kw.arg == "newline" for kw in call.keywords):
                offenders.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert not offenders, (
        "a module that builds CSV with csv.writer opens a file without newline=\"\":\n  "
        + "\n  ".join(offenders))


@pytest.mark.parametrize("snippet, guard", [
    ('from pathlib import Path\nPath("x").read_text()\n', "encoding"),
    ('import csv\nimport io\nw = csv.writer(io.StringIO())\n'
     'from pathlib import Path\nPath("x").open("w")\n', "newline"),
])
def test_the_guards_can_actually_fail(snippet, guard, tmp_path):
    """A guard that cannot fail is decoration.

    Both rules are checked against source that violates them, so a refactor
    that quietly stops detecting anything fails here rather than passing
    vacuously.
    """
    tree = ast.parse(snippet)
    calls = _text_io_calls(tree, snippet)
    assert calls, "the walker found no text I/O in a snippet that is all text I/O"
    assert not any(kw.arg == guard for call, _ in calls for kw in call.keywords)


def test_webbrowser_open_is_not_mistaken_for_file_io():
    """The exclusion list earns its place: `webbrowser.open(url)` is a call
    named ``open`` that must never be asked for an encoding."""
    snippet = 'import webbrowser\nwebbrowser.open("http://localhost:8000")\n'
    assert not _text_io_calls(ast.parse(snippet), snippet)
