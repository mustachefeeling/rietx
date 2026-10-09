"""The tutorial notebooks execute, and each committed one is its source (WP-1545).

A tutorial's authority is its percent-format script in `examples/tutorials/`,
and `build.py` there generates, executes and commits the `.ipynb` beside it.
These tests find the tutorials by glob, so adding one needs no edit here.

**Each notebook executes in a real kernel on every push.**  A plain script run
would exercise none of the display (WP-1544), and per-push execution is the
whole value of an example guard (`test_examples.py`'s docstring).  So each
notebook is sized to fit the fast tier.  The executed notebook is never written:
outputs move with the machine that drew them, and the committed ones are the
builder's to refresh.

**CI executes them on its newest Python leg alone** (WP-1547).  The other legs
set `RIETX_TUTORIALS=skip` and skip rather than deselect, so passed+skipped
agrees across the matrix.  What only the newest Python can break is a
notebook's own: a cell printing a new DeprecationWarning to stderr, or a kernel
release lagging the interpreter.  The rietx calls behind each cell run on every
leg through the rest of the suite.  Syntax newer than the 3.11 floor fails ruff,
whose target is py311.  A stdlib name newer than 3.11 in a tutorial's own cells
passes every check, and that is the trade.  The nightly executes them on 3.13,
on Linux, Windows and macOS.
"""

from __future__ import annotations

import html
import importlib.util
import os
import re
import shutil
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")
pytest.importorskip("nbclient")
pytest.importorskip("ipykernel")

REPO_ROOT = Path(__file__).resolve().parent.parent
TUTORIALS = REPO_ROOT / "examples" / "tutorials"

_spec = importlib.util.spec_from_file_location("tutorials_build", TUTORIALS / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

SOURCES = build.sources()

#: The tutorial whose first fit `docs/landing/src/index.html` shows, code and output.
LANDING_TUTORIAL = "02_simple_rietveld"
LANDING_PAGE = REPO_ROOT / "docs" / "landing" / "src" / "index.html"


def _landing_box() -> tuple[str, str]:
    """The landing page's code box and output panel, as plain text."""
    section = re.search(r'<section[^>]*id="example".*?</section>',
                        LANDING_PAGE.read_text(encoding="utf-8"), re.S)
    assert section, f"{LANDING_PAGE.name} has no example section"
    pres = re.findall(r"<pre[^>]*>(.*?)</pre>", section.group(0), re.S)
    assert len(pres) == 2, f"the example section holds {len(pres)} <pre> blocks, not code and output"
    code, out = (html.unescape(re.sub(r"<[^>]+>", "", pre)) for pre in pres)
    return code, out


def _flat(text: str) -> str:
    return " ".join(text.split())


def _printed(cells) -> str:
    """Everything the code cells printed, in order."""
    return "".join(o.get("text", "") for c in cells if c.cell_type == "code" for o in c.outputs)


def _committed(path: Path):
    return nbformat.reads(path.with_suffix(".ipynb").read_text(encoding="utf-8"), as_version=4)


def test_there_are_tutorials():
    """The glob below finds something, or every parametrised test is vacuous."""
    assert SOURCES, f"no {build.SOURCES} under {TUTORIALS}"


@pytest.mark.skipif(os.environ.get("RIETX_TUTORIALS") == "skip",
                    reason="CI executes the notebooks on its newest Python leg (WP-1547)")
@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.stem)
def test_tutorial_executes_clean(path):
    """No error, no stderr, no home path, and a figure where a cell plots.

    A rietx figure shows through its own display hook whatever the backend,
    so the suite's `MPLBACKEND=Agg` (conftest) does not hide one.  What hides
    one is a cell that discards it, such as a trailing `;` (WP-1544)."""
    nb = build.execute(path)
    assert build.problems(nb) == []
    plots = [c for c in nb.cells
             if c.cell_type == "code" and ".plot(" in c.source.splitlines()[-1]]
    assert plots, f"{path.stem} ends no cell on a plot, so this test checks no figure"
    for cell in plots:
        kinds = {k for out in cell.outputs for k in out.get("data", {})}
        assert "image/png" in kinds, f"{path.stem}: {cell.source.splitlines()[-1]!r} showed no image"
    if path.stem == LANDING_TUTORIAL:
        printed = _printed(nb.cells)
        out = _landing_box()[1]
        codes = re.findall(r"\] ([A-Z_]+):", out)
        assert codes, "found no diagnostic code in the landing page's output panel"
        quoted = [out.split()[0], *codes]  # the status word, then each code
        missing = [code for code in quoted if code not in printed]
        assert missing == [], f"{path.stem} no longer prints {missing}, which the landing page quotes"


def test_the_landing_box_is_the_tutorial():
    """The landing page's code box is the tutorial's first fit, line for line and
    in order, less only import lines.  Every stretch of its output panel between
    cuts (`…`) is in that cell's committed output, in order, and a panel ending
    without a cut ends where the output does.  So the published numbers are the
    ones the builder drew.

    The box names bare files where the tutorial reads the copies in the wheel."""
    code, out = _landing_box()
    nb = _committed(TUTORIALS / f"{LANDING_TUTORIAL}.py")
    cell = next(c for c in nb.cells if c.cell_type == "code" and "ref.fit(" in c.source)
    box = [_flat(ln) for ln in code.splitlines() if ln.strip()]
    source = [_flat(ln.replace("examples_dir() / ", "")) for ln in cell.source.splitlines()
              if ln.strip()]
    kept = [ln for ln in source if ln in box or not ln.startswith(("import ", "from "))]
    assert kept == box, "the landing page's code box is not the tutorial's fit cell"
    printed = _flat(_printed([cell]))
    pieces = [p for p in map(_flat, out.split("…")) if p]
    stale, at = [], 0
    for piece in pieces:
        found = printed.find(piece, at)
        if found < 0:
            stale.append(piece)
        else:
            at = found + len(piece)
    assert stale == [], "the landing page's output panel no longer matches the tutorial"
    if not out.rstrip().endswith("…"):
        assert printed.endswith(pieces[-1]), "the tutorial prints more than the panel shows, uncut"


def test_committed_notebooks_are_their_sources():
    """Cells equal the script's, and the stamp is this package's major.minor."""
    assert build.check() == []


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.stem)
def test_committed_outputs_are_fit_to_publish(path):
    assert build.problems(_committed(path)) == []


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.stem)
def test_a_notebook_opens_by_installing_and_never_ran_it(path):
    """A reader's first cell installs rietx; a build must not install anything."""
    code = [c for c in _committed(path).cells if c.cell_type == "code"]
    assert code[0].source.startswith("%pip install "), code[0].source
    assert code[0].execution_count is None and code[0].outputs == []


def test_parse_uncomments_a_pip_magic(tmp_path):
    src = tmp_path / "00_pip.py"
    src.write_text("# %%\n# %pip install rietx\n", encoding="utf-8", newline="\n")
    assert build.parse(src) == [("code", "%pip install rietx")]


def test_the_readme_lists_every_tutorial():
    readme = (TUTORIALS / "README.md").read_text(encoding="utf-8")
    missing = [p.with_suffix(".ipynb").name for p in SOURCES
               if p.with_suffix(".ipynb").name not in readme]
    assert missing == [], f"examples/tutorials/README.md does not list {missing}"


def test_check_sees_a_stale_notebook(tmp_path):
    """The guard can fail: a source edited without a rebuild is reported."""
    source = SOURCES[0]
    shutil.copy(source, tmp_path / source.name)
    shutil.copy(source.with_suffix(".ipynb"), tmp_path / source.with_suffix(".ipynb").name)
    assert build.check(tmp_path) == []
    copy = tmp_path / source.name
    copy.write_text(copy.read_text(encoding="utf-8") + "\n# %%\nprint('new')\n",
                    encoding="utf-8", newline="\n")
    assert build.check(tmp_path) == [f"{source.stem}.ipynb: cells differ from {source.name}"]


def test_problems_sees_stderr_and_a_home_path():
    v4 = nbformat.v4
    cell = v4.new_code_cell("x", outputs=[
        v4.new_output("stream", name="stderr", text="UserWarning: careful\n"),
        v4.new_output("stream", name="stdout", text=f"read {Path.home() / 'data.xy'}\n"),
    ])
    found = build.problems(v4.new_notebook(cells=[cell]))
    assert len(found) == 2 and "stderr" in found[0] and "home directory" in found[1]


def test_parse_refuses_what_it_cannot_round_trip(tmp_path):
    bad = tmp_path / "00_bad.py"
    bad.write_text("import rietx\n# %%\nx = 1\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="before the first"):
        build.parse(bad)
    bad.write_text("# %% [markdown]\nno hash\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="must start"):
        build.parse(bad)
    bad.write_text("# %% [markdown]\n# text\n# %% A titled cell\nx = 1\n",
                   encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="does not read"):
        build.parse(bad)
