"""Build the tutorial notebooks from their percent-format sources (WP-1545).

Each tutorial is a script, ``NN_slug.py``, and its notebook ``NN_slug.ipynb``
is generated from it, executed, and committed beside it.  The script is the
authority (root CLAUDE.md: a walkthrough has one, and it is ``examples/``), so
an edit goes to the ``.py`` and this file regenerates the notebook.

The source format is the subset of jupytext's percent format that a
notebook needs: ``# %%`` opens a code cell, ``# %% [markdown]`` a markdown
cell whose lines each start ``# ``.  A file opens with a marker.

    python examples/tutorials/build.py              # rebuild every notebook
    python examples/tutorials/build.py 01_quickstart  # rebuild one
    python examples/tutorials/build.py --check      # exit 1 if a notebook's cells or stamp are stale

A rebuild of unchanged code on one machine changes nothing.  Timing is not
recorded, cell ids are positional, and the notebook metadata holds only what
a reader needs.  The figures' bytes still depend on the matplotlib that drew
them, so a rebuild on another machine moves them; ``--check`` therefore
compares cells and the version stamp, never outputs.

A build **fails on any stderr output**.  A warning prints the absolute path of
the file that raised it, and a notebook committed with one carries the
builder's home directory.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = "[0-9][0-9]_*.py"
_MARKER = re.compile(r"^# %%(?P<markdown> \[markdown\])?\s*$")


def sources(directory: Path = HERE) -> list[Path]:
    return sorted(directory.glob(SOURCES))


def parse(path: Path) -> list[tuple[str, str]]:
    """``(cell_type, source)`` per cell, in order."""
    cells: list[tuple[str, list[str]]] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = _MARKER.match(line)
        if m:
            cells.append(("markdown" if m["markdown"] else "code", []))
            continue
        if line.lstrip().startswith(("# %%", "#%%")):
            raise ValueError(f"{path.name}:{n}: a cell marker this builder does not read")
        if not cells:
            raise ValueError(f"{path.name}:{n}: text before the first '# %%' marker")
        kind, body = cells[-1]
        if kind == "markdown" and line.strip():
            if not line.startswith("# ") and line != "#":
                raise ValueError(f"{path.name}:{n}: a markdown line must start '# '")
            line = line[2:]
        elif kind == "markdown":
            line = ""
        body.append(line.rstrip() if kind == "markdown" else line)
    out = []
    for kind, body in cells:
        text = "\n".join(body).strip("\n")
        if not text:
            raise ValueError(f"{path.name}: an empty {kind} cell")
        out.append((kind, text))
    return out


def notebook_cells(nb) -> list[tuple[str, str]]:
    return [(c.cell_type, c.source) for c in nb.cells]


def _version() -> str:
    import rietx

    return rietx.__version__


def _notebook(path: Path):
    import nbformat

    nb = nbformat.v4.new_notebook()
    for i, (kind, text) in enumerate(parse(path)):
        make = nbformat.v4.new_markdown_cell if kind == "markdown" else nbformat.v4.new_code_cell
        nb.cells.append(make(text, id=f"{path.stem[:2]}-{i:02d}"))
    nb.metadata = {
        "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
        "language_info": {"name": "python"},
        "rietx": {"version": _version()},
    }
    return nb


def problems(nb) -> list[str]:
    """What makes an executed notebook unfit to commit."""
    home = str(Path.home())
    found = []
    for i, cell in enumerate(nb.cells):
        for out in cell.get("outputs", []):
            if out.get("output_type") == "stream" and out.get("name") == "stderr":
                found.append(f"cell {i} wrote to stderr: {out['text'][:300]!r}")
            if out.get("output_type") == "error":
                found.append(f"cell {i} raised {out.get('ename')}: {out.get('evalue')}")
            text = out.get("text", "") + "".join(
                v for k, v in out.get("data", {}).items() if k.startswith("text/"))
            if home in text:
                found.append(f"cell {i} prints the home directory {home!r}")
    return found


def execute(path: Path):
    """The executed notebook, never written: a test calls this too."""
    from jupyter_client.kernelspec import KernelSpecManager
    from jupyter_client.manager import AsyncKernelManager
    from nbclient import NotebookClient

    from rietx._about import TELEMETRY_ENV

    nb = _notebook(path)
    env = {k: v for k, v in os.environ.items() if k != "MPLBACKEND"}  # the kernel's own, as a reader's
    env[TELEMETRY_ENV] = "0"
    env["PYTHONUTF8"] = "1"
    # The kernel is this interpreter's ipykernel.  A looked-up "python3" spec
    # can be a user-level one naming another environment's python, which then
    # executes the notebook against whatever rietx that environment holds.
    # A client handed its manager shuts the kernel down only when told to.
    km = AsyncKernelManager(kernel_name="python3",
                            kernel_spec_manager=KernelSpecManager(kernel_dirs=[]))
    NotebookClient(nb, km=km, timeout=900, record_timing=False,
                   resources={"metadata": {"path": str(HERE)}}).execute(env=env, cleanup_kc=True)
    nb.metadata.get("language_info", {}).pop("version", None)  # the builder's Python patch release
    return nb


def build(path: Path) -> Path:
    import nbformat

    nb = execute(path)
    found = problems(nb)
    if found:
        raise SystemExit(f"{path.name}: not written\n  " + "\n  ".join(found))
    out = path.with_suffix(".ipynb")
    out.write_text(nbformat.writes(nb) + "\n", encoding="utf-8", newline="\n")
    return out


def check(directory: Path = HERE) -> list[str]:
    import nbformat

    stale = []
    major_minor = ".".join(_version().split(".")[:2])
    for path in sources(directory):
        nb_path = path.with_suffix(".ipynb")
        if not nb_path.exists():
            stale.append(f"{nb_path.name}: missing")
            continue
        nb = nbformat.reads(nb_path.read_text(encoding="utf-8"), as_version=4)
        if notebook_cells(nb) != parse(path):
            stale.append(f"{nb_path.name}: cells differ from {path.name}")
        stamped = nb.metadata.get("rietx", {}).get("version", "")
        if ".".join(stamped.split(".")[:2]) != major_minor:
            stale.append(f"{nb_path.name}: built by rietx {stamped or '?'}, package is {major_minor}")
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help="stems to rebuild (default: all)")
    parser.add_argument("--check", action="store_true", help="report stale notebooks, build nothing")
    args = parser.parse_args(argv)
    if args.check:
        stale = check()
        for line in stale:
            print(line)
        return 1 if stale else 0
    chosen = [p for p in sources() if not args.names or p.stem in args.names]
    unknown = set(args.names) - {p.stem for p in chosen}
    if unknown:
        parser.error(f"no tutorial named {sorted(unknown)}")
    for path in chosen:
        print(f"wrote {build(path).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
