"""Build the tutorial notebooks into a JupyterLite site that runs them in the browser (WP-1966).

    python docs/lite/build.py --wheels DIR                 # the notebooks at the newest release tag
    python docs/lite/build.py --wheels DIR --ref HEAD --rietx-wheel dist/rietx-….whl

`--wheels` is the directory `build_wheels.py` wrote: gemmi, spglib and
rietx-kernels built for the Pyodide this JupyterLite loads, none of which
Pyodide's own distribution has.  The site goes to `docs/lite/site` unless
`--out` says otherwise, and needs `requirements.txt` installed in the Python
that runs this.

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
import shutil
import subprocess
import sys
import tempfile
import tomllib
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


def requirements_of(ref: str, rietx_wheel: Path | None) -> list[str]:
    """The requirements of the rietx the site installs: the served wheel's own
    `METADATA`, else `pyproject.toml` at `ref`, the release PyPI serves for it."""
    if rietx_wheel is not None:
        with zipfile.ZipFile(rietx_wheel) as whl:
            meta = next(n for n in whl.namelist() if n.endswith(".dist-info/METADATA"))
            text = whl.read(meta).decode("utf-8")
        return [ln.split(":", 1)[1].strip() for ln in text.splitlines()
                if ln.startswith("Requires-Dist:")]
    text = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:pyproject.toml"],
                          capture_output=True, text=True, check=True).stdout
    return tomllib.loads(text)["project"]["dependencies"]


def check_kernels(kernels_wheel: Path, requirements: list[str]) -> None:
    """Refuse a site whose kernels the rietx it installs would not accept.

    micropip would refuse rietx in every notebook at once, so the build says so
    first.  The kernels come from this checkout and rietx may come from a tag,
    which is how the two can disagree."""
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name, parse_wheel_filename

    version = parse_wheel_filename(kernels_wheel.name)[1]
    for line in requirements:
        req = Requirement(line)
        if canonicalize_name(req.name) == canonicalize_name(KERNELS_DIST):
            if version not in req.specifier:
                raise SystemExit(f"{kernels_wheel.name} does not satisfy {req}: rebuild the"
                                 f" kernels at the ref the site installs")
            return
    raise SystemExit(f"the {ABOUT.DIST_NAME} the site installs names no {KERNELS_DIST}")


#: The browser's install cell.  gemmi, spglib and the kernels resolve from the
#: site's own index, which micropip reads before PyPI.  RIETX_TELEMETRY=0
#: because no `rietx watch` can read a browser tab's run records.
INSTALL = """\
# This notebook runs in your browser, on Pyodide (Python compiled to WebAssembly).
# gemmi, spglib and {dist}'s compiled kernels, built for WebAssembly, come from this site.
import os

os.environ["{telemetry_env}"] = "0"
%pip install {dist}"""


def install_source() -> str:
    """`INSTALL` with the package's own names filled in."""
    return INSTALL.format(dist=ABOUT.DIST_NAME, telemetry_env=ABOUT.TELEMETRY_ENV)


KERNELSPEC = {"display_name": "Python (Pyodide)", "language": "python", "name": "python"}

#: The site's theme, by what its figures can show (`settings`).  `adaptive-theme`
#: follows the reader's own light or dark setting (WP-1970).  The light pin is
#: WP-1966's, for figures drawn on white alone, which on a dark page would be
#: white rectangles.
FOLLOW = {"@jupyterlab/apputils-extension:themes": {"adaptive-theme": True}}
LIGHT = {"@jupyterlab/apputils-extension:themes": {
    "theme": "JupyterLab Light", "adaptive-theme": False}}


def settings(notebooks: list[dict]) -> dict:
    """`FOLLOW` when every stored figure carries a dark image, else `LIGHT`.

    The notebooks come from the newest tag, so this is a fact about that tag
    and not about this checkout.  A tag cut before WP-1970 has figures drawn on
    white alone, and its site stays light."""
    figures = [o["data"] for nb in notebooks for c in nb["cells"] if c["cell_type"] == "code"
               for o in c.get("outputs", []) if "image/png" in o.get("data", {})]
    paired = all("rx-fig-dark" in "".join(f.get("text/html", "")) for f in figures)
    return FOLLOW if paired else LIGHT


def _is_install(cell: dict) -> bool:
    lines = [ln for ln in "".join(cell["source"]).splitlines() if ln.strip()]
    return cell["cell_type"] == "code" and bool(lines) and all(ln.startswith("%pip ") for ln in lines)


def project(data: bytes) -> dict:
    """The notebook for the browser: its one install cell replaced, its kernel
    Pyodide's, and its code cells marked trusted.

    JupyterLite strips `<style>` from an output it does not trust, and a stored
    output is untrusted unless its cell says otherwise, so each figure would
    stay light on a dark page until its cell ran again (measured, WP-1970).
    The outputs are this repository's own, built from its tag, so the mark is
    what `jupyter trust` would sign."""
    nb = json.loads(data)
    installs = [c for c in nb["cells"] if _is_install(c)]
    if len(installs) != 1:
        raise SystemExit(f"expected one %pip install cell, found {len(installs)}")
    cell = installs[0]
    cell["source"] = install_source().splitlines(keepends=True)
    cell["outputs"] = []
    cell["execution_count"] = None
    for code in nb["cells"]:
        if code["cell_type"] == "code":
            code.setdefault("metadata", {})["trusted"] = True
    nb["metadata"]["kernelspec"] = dict(KERNELSPEC)
    return nb


def build(wheels: Path, out: Path, ref: str, rietx_wheel: Path | None) -> None:
    found = []
    for name in SERVED:
        stem = name.replace("-", "_")  # a wheel's file name normalises the dash
        matches = sorted(wheels.glob(f"{stem}-*-pyemscripten_*_wasm32.whl"))
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
    kernels = next(w for w in found if w.name.startswith(KERNELS_DIST.replace("-", "_") + "-"))
    check_kernels(kernels, requirements_of(ref, rietx_wheel))
    with tempfile.TemporaryDirectory() as tmp:
        contents = Path(tmp) / "contents"
        contents.mkdir()
        projected = []
        for book in LANDING.notebooks(ref):
            projected.append(project(book.data))
            (contents / book.name).write_text(
                json.dumps(projected[-1], indent=1, ensure_ascii=False) + "\n",
                encoding="utf-8", newline="\n")
        lite_dir = Path(tmp) / "lite"
        lite_dir.mkdir()
        # exposeAppInBrowser sets window.jupyterapp, which smoke.mjs drives.
        (lite_dir / "jupyter-lite.json").write_text(json.dumps({
            "jupyter-lite-schema-version": 0,
            "jupyter-config-data": {"appName": f"{ABOUT.DIST_NAME} tutorials",
                                    "exposeAppInBrowser": True},
        }, indent=2) + "\n", encoding="utf-8", newline="\n")
        overrides = lite_dir / "overrides.json"
        overrides.write_text(json.dumps(settings(projected), indent=2) + "\n",
                             encoding="utf-8", newline="\n")
        # Built beside the old site and swapped in, so a failed build leaves it standing.
        built = Path(tmp) / "site"
        cmd = [sys.executable, "-m", "jupyterlite_core", "build",
               "--lite-dir", str(lite_dir), "--output-dir", str(built),
               "--contents", str(contents), "--settings-overrides", str(overrides),
               "--no-sourcemaps"]
        for w in found:
            cmd += ["--piplite-wheels", str(w)]
        subprocess.run(cmd, check=True, cwd=tmp)
        if out.exists():
            shutil.rmtree(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(built, out)
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
