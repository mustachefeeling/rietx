"""Build the tutorial notebooks into a JupyterLite site that runs them in the browser (WP-1963).

    python docs/lite/build.py --wheels DIR                 # the notebooks at the newest release tag
    python docs/lite/build.py --wheels DIR --ref HEAD --rietx-wheel dist/rietx-….whl

`--wheels` is the directory `build_wheels.py` wrote: gemmi and spglib built for
the Pyodide this JupyterLite loads, which Pyodide's own distribution lacks.  The
site goes to `docs/lite/site` unless `--out` says otherwise, and needs
`requirements.txt` installed in the Python that runs this.

The notebooks are the landing page's: the same reader (`docs/landing/build.py`'s
`notebooks`) at the same ref, the newest `vX.Y.Z` tag by default, so the browser
copy and the Colab link open the same notebook and install the same release
from PyPI.  `--rietx-wheel` serves a wheel from the site instead, which is how a
change reaches the browser before it is released.

Each notebook is a *projection*: its install cell, the one cell of nothing but
`%pip` lines, is replaced by `INSTALL`, and its kernelspec names the Pyodide
kernel.  Every other cell and output is the committed notebook's, byte for byte
once parsed.  The script stays the authority (examples/tutorials/README.md).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def _by_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LANDING = _by_path("_lite_landing", REPO / "docs" / "landing" / "build.py")
#: The name-bearing literals (`src/rietx/_about.py`), never spelled here.
ABOUT = LANDING.ABOUT
KERNELS_DIST = f"{ABOUT.DIST_NAME}-kernels"
#: The packages the site serves itself, and nothing else from `--wheels`.
SERVED = tuple(_by_path("_lite_wheels", HERE / "build_wheels.py").PACKAGES)


def kernels_floor(requirements: str | None = None) -> str:
    """The lowest `rietx-kernels` rietx accepts, which is the version the mock claims.

    `requirements` is the text naming that requirement: a `pyproject.toml`, or a
    wheel's `METADATA`.  The working tree's `pyproject.toml` when omitted."""
    if requirements is None:
        requirements = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(rf'{re.escape(KERNELS_DIST)}[^"\n]*?>=\s*(\d+(?:\.\d+)*)', requirements)
    if not m:
        raise SystemExit(f"no {KERNELS_DIST} floor in the requirements read")
    return m[1]


def requirements_of(ref: str, rietx_wheel: Path | None) -> str:
    """The requirements of the rietx the site installs: the served wheel's own
    `METADATA`, else `pyproject.toml` at `ref`, the release PyPI serves for it."""
    if rietx_wheel is not None:
        with zipfile.ZipFile(rietx_wheel) as whl:
            meta = next(n for n in whl.namelist() if n.endswith(".dist-info/METADATA"))
            return whl.read(meta).decode("utf-8")
    return subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:pyproject.toml"],
                          capture_output=True, text=True, check=True).stdout


#: The browser's install cell.  `rietx-kernels` has no WebAssembly build, so the
#: resolver would refuse rietx; a mock with no modules satisfies it, and rietx's
#: soft import then finds nothing and runs the numpy path.  RIETX_COMPILED=0 is
#: the switch the decline warning itself names, and RIETX_TELEMETRY=0 because
#: no `rietx watch` can read a browser tab's run records.
INSTALL = """\
# This notebook runs in your browser, on Pyodide (Python compiled to WebAssembly).
# {dist}'s compiled kernels have no WebAssembly build, so micropip is told to skip
# them and {dist} runs its numpy path. gemmi and spglib come from this site.
import os

import micropip

os.environ["{compiled_env}"] = "0"
os.environ["{telemetry_env}"] = "0"
micropip.add_mock_package("{kernels}", "{floor}", modules={{}})
%pip install {dist}"""


def install_source(floor: str) -> str:
    """`INSTALL` for a mock claiming `floor`."""
    return INSTALL.format(floor=floor, dist=ABOUT.DIST_NAME, kernels=KERNELS_DIST,
                          compiled_env=ABOUT.COMPILED_ENV, telemetry_env=ABOUT.TELEMETRY_ENV)

KERNELSPEC = {"display_name": "Python (Pyodide)", "language": "python", "name": "python"}


def _is_install(cell: dict) -> bool:
    lines = [ln for ln in "".join(cell["source"]).splitlines() if ln.strip()]
    return cell["cell_type"] == "code" and bool(lines) and all(ln.startswith("%pip ") for ln in lines)


def project(data: bytes, floor: str) -> dict:
    """The notebook for the browser: its one install cell replaced, its kernel Pyodide's."""
    nb = json.loads(data)
    installs = [c for c in nb["cells"] if _is_install(c)]
    if len(installs) != 1:
        raise SystemExit(f"expected one %pip install cell, found {len(installs)}")
    cell = installs[0]
    cell["source"] = install_source(floor).splitlines(keepends=True)
    cell["outputs"] = []
    cell["execution_count"] = None
    nb["metadata"]["kernelspec"] = dict(KERNELSPEC)
    return nb


def build(wheels: Path, out: Path, ref: str, rietx_wheel: Path | None) -> None:
    found = []
    for name in SERVED:
        matches = sorted(wheels.glob(f"{name}-*-pyemscripten_*_wasm32.whl"))
        if len(matches) != 1:
            raise SystemExit(f"expected one {name} wheel in {wheels}, found {len(matches)}:"
                             f" run build_wheels.py into an empty directory")
        found += matches
    if rietx_wheel is not None:
        if not rietx_wheel.is_file():
            raise SystemExit(f"--rietx-wheel {rietx_wheel}: no such file")
        found.append(rietx_wheel)
    if out.exists() and not (out / "jupyter-lite.json").is_file():
        raise SystemExit(f"--out {out} exists and is not a JupyterLite site; refusing to delete it")
    floor = kernels_floor(requirements_of(ref, rietx_wheel))
    with tempfile.TemporaryDirectory() as tmp:
        contents = Path(tmp) / "contents"
        contents.mkdir()
        for book in LANDING.notebooks(ref):
            (contents / book.name).write_text(
                json.dumps(project(book.data, floor), indent=1, ensure_ascii=False) + "\n",
                encoding="utf-8")
        lite_dir = Path(tmp) / "lite"
        lite_dir.mkdir()
        # exposeAppInBrowser sets window.jupyterapp, which smoke.mjs drives.
        (lite_dir / "jupyter-lite.json").write_text(json.dumps({
            "jupyter-lite-schema-version": 0,
            "jupyter-config-data": {"appName": "rietx tutorials", "exposeAppInBrowser": True},
        }, indent=2) + "\n", encoding="utf-8")
        if out.exists():
            shutil.rmtree(out)
        cmd = [sys.executable, "-m", "jupyterlite_core", "build",
               "--lite-dir", str(lite_dir), "--output-dir", str(out),
               "--contents", str(contents), "--no-sourcemaps"]
        for w in found:
            cmd += ["--piplite-wheels", str(w)]
        subprocess.run(cmd, check=True, cwd=tmp)
    print(f"{out}: {len(LANDING.notebooks(ref))} notebooks at {ref}, "
          f"wheels {', '.join(w.name for w in found)}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--wheels", type=Path, required=True,
                    help="the directory build_wheels.py wrote")
    ap.add_argument("--ref", help="where the notebooks are read (default: the newest vX.Y.Z tag)")
    ap.add_argument("--rietx-wheel", type=Path,
                    help="serve this rietx wheel from the site instead of installing from PyPI")
    ap.add_argument("--out", type=Path, default=HERE / "site")
    args = ap.parse_args(argv)
    build(args.wheels.resolve(), args.out.resolve(), args.ref or LANDING.release_tag(),
          args.rietx_wheel.resolve() if args.rietx_wheel else None)


if __name__ == "__main__":
    main()
