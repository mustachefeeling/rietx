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
"""

from __future__ import annotations

import importlib.util
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


def _committed(path: Path):
    return nbformat.reads(path.with_suffix(".ipynb").read_text(encoding="utf-8"), as_version=4)


def test_there_are_tutorials():
    """The glob below finds something, or every parametrised test is vacuous."""
    assert SOURCES, f"no {build.SOURCES} under {TUTORIALS}"


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


def test_committed_notebooks_are_their_sources():
    """Cells equal the script's, and the stamp is this package's major.minor."""
    assert build.check() == []


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.stem)
def test_committed_outputs_are_fit_to_publish(path):
    assert build.problems(_committed(path)) == []


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
