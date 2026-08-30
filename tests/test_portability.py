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
import os
import subprocess
import sys
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
        # os.open returns a file descriptor, never a text stream, and rejects
        # `encoding=` outright -- so flagging it asks for an argument that
        # cannot be given.  _NOT_FILE_IO cannot express this: it substring-
        # matches the receiver, and "os" matches any receiver spelling those
        # letters, so the exemption is an exact-receiver test instead.
        if name == "open" and receiver == "os":
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


# ----------------------------------------------------------------------
# the CLI's own output
# ----------------------------------------------------------------------
#: Commands whose output carries characters cp1252 has no code point for.
#: ``skill --print`` reaches ``α`` at character 4795 of the body; ``index
#: --help`` reaches ``Å`` in argparse's own help text.  Both exited 1 on the
#: nightly's Windows runner (run 33251188429) before ``cli._utf8_output``.
_NON_ASCII_COMMANDS = (("skill", "--print"), ("index", "--help"))


def _cli_through_an_ansi_pipe(*command: str) -> subprocess.CompletedProcess[bytes]:
    """The CLI with stdout claiming cp1252 — a Windows capture, on any platform.

    ``PYTHONIOENCODING`` is the same fallback the runner takes when stdout is
    not a console, which is what kept this invisible here for a whole
    milestone.  Bytes, never ``text=True``: the decode *is* the assertion.
    """
    return subprocess.run(
        [sys.executable, "-m", "rietx.cli", *command],
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        timeout=120,  # a runaway guard, not a timer (tests/CLAUDE.md)
    )


@pytest.mark.parametrize("command", _NON_ASCII_COMMANDS, ids=lambda c: " ".join(c))
def test_the_cli_writes_utf8_into_an_ansi_code_page_pipe(command):
    """A pipe that claims cp1252 gets UTF-8, not a ``UnicodeEncodeError``."""
    out = _cli_through_an_ansi_pipe(*command)
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")
    text = out.stdout.decode("utf-8")  # raises if the stream is not UTF-8
    assert any(ord(c) > 127 for c in text), "nothing non-ASCII survived to assert on"


def test_the_skill_body_arrives_whole_through_the_pipe():
    """``skill --print`` is documented as the way into a harness that reads no
    skills, so the pipe must carry the file rather than a rendering of it.

    This is the assertion ``errors="replace"`` would fail where an exit status
    would not: that also exits 0, and hands an agent ``K?`` for ``Kα``.
    """
    from rietx import skill as skill_module

    out = _cli_through_an_ansi_pipe("skill", "--print")
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")
    body = out.stdout.decode("utf-8").replace("\r\n", "\n")
    assert body.rstrip("\n") == skill_module.read(None).rstrip("\n")


def _cli_subprocess_calls(tree: ast.AST) -> list[ast.Call]:
    """``subprocess.run``/``Popen`` calls whose argv mentions ``rietx.cli``."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in {"run", "Popen"}):
            continue
        argv = node.args[0] if node.args else None
        if not isinstance(argv, (ast.List, ast.Tuple)):
            continue
        literals = [e.value for e in argv.elts if isinstance(e, ast.Constant)]
        if any(isinstance(v, str) and "rietx.cli" in v for v in literals):
            out.append(node)
    return out


def test_a_pipe_from_the_cli_names_utf8_rather_than_the_locale():
    """The other half of ``cli._utf8_output``, and it fails on the same platform.

    The CLI writes UTF-8 on every platform; a reader that takes ``text=True``
    decodes with ``locale.getpreferredencoding(False)``, cp1252 on Windows. The
    two disagree and the **reader** raises — measured on the nightly's Windows
    runner (run 33297474071) on the ``₁`` of ``occ₁``, whose UTF-8 lead byte
    0x81 cp1252 has no code point for.

    The producer's fix cannot close this; only the consumer's can, and there is
    no platform here on which forgetting it goes red, which is what makes it a
    source guard rather than a behaviour test.

    **Bytes are not an offender.**  A call that asks for neither ``text`` nor
    ``encoding`` gets bytes and decodes them itself, which is what
    ``_cli_through_an_ansi_pipe`` above does deliberately — there the decode is
    the assertion.  What cannot be right is asking the *pipe* to decode without
    saying with what.
    """
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _cli_subprocess_calls(tree):
            kw = {k.arg: k.value for k in call.keywords}
            decodes = any(isinstance(kw.get(name), ast.Constant) and kw[name].value
                          for name in ("text", "universal_newlines"))
            if decodes and "encoding" not in kw:
                offenders.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert not offenders, (
        "these ask the pipe to decode the rietx CLI's output without saying "
        f"with what, so they use the locale codec: {offenders}"
    )


def test_the_cli_pipe_guard_can_actually_fail():
    """The guard above is an absence assertion (`tests/CLAUDE.md`), so prove it
    still fails on the construct it is written for."""
    snippet = ('import subprocess\n'
               'subprocess.run(["python", "-m", "rietx.cli", "skill"], text=True)\n')
    calls = _cli_subprocess_calls(ast.parse(snippet))
    assert len(calls) == 1
    names = {kw.arg for kw in calls[0].keywords}
    assert "text" in names and "encoding" not in names
