"""Cross-compile gemmi and spglib for the Pyodide the JupyterLite site loads (WP-1963).

    python docs/lite/build_wheels.py OUT_DIR [--work DIR]

rietx needs both and Pyodide's distribution has neither, nor does PyPI carry a
WebAssembly wheel of either (checked 2026-10-14).  This builds them from their
PyPI sdists with `pyodide-build`, in a work directory it creates (a uv venv on
CPython 3.14, Pyodide's cross-build environment, an Emscripten SDK), and writes
the two `pyemscripten` wheels to OUT_DIR.  About five minutes on four cores,
most of it gemmi; it needs `uv`, `git`, `cmake` and `ninja`.

The pins move together.  `jupyterlite-pyodide-kernel` (requirements.txt) loads
one Pyodide, a wheel must match that Pyodide's ABI, and `pyodide-build` builds
against that Pyodide's cross-build environment, which names its Emscripten.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

#: `jupyterlite_pyodide_kernel.constants.PYODIDE_VERSION` for the kernel in requirements.txt.
PYODIDE = "314.0.6"
#: The host Python must match the Pyodide's CPython to the minor version.
HOST_PYTHON = "3.14"
PYODIDE_BUILD = "pyodide-build==0.39.1"
XBUILDENV = f"https://github.com/pyodide/pyodide/releases/download/{PYODIDE}/xbuildenv-{PYODIDE}.tar.bz2"

#: Per package: its version, and what its build needs that a native build does not.
PACKAGES = {
    "spglib": {
        "version": "2.8.0",
        # Shared, `_spglib.so` links a `libsymspg.so` Pyodide's loader cannot find.
        "cmake_args": "-DSPGLIB_SHARED_LIBS=OFF;-DSPGLIB_WITH_TESTS=OFF",
    },
    "gemmi": {
        "version": "0.7.5",
        # The command-line program links as an executable, which a side module is not.
        "cmake_args": ("-DBUILD_GEMMI_PROGRAM=OFF;-DINSTALL_DEV_FILES=OFF;"
                       "-DBUILD_SHARED_LIBS=OFF;-DGENERATE_STUBS=OFF"),
        # The vendored half.hpp names floating-point exception flags wasm's libc
        # does not define.  Only CCP4 map reading includes it, and with its error
        # handling off (the default) the flags are never raised, so any distinct
        # values compile to the same code.
        "cxxflags": "-DFE_INVALID=1 -DFE_DIVBYZERO=4 -DFE_OVERFLOW=8 -DFE_UNDERFLOW=16 -DFE_INEXACT=32",
        # Its CMake asks for nanobind 2.4 under SameMajorVersion, so 3.x is refused.
        "pyproject": [('"nanobind >=2.4",', '"nanobind >=2.4,<3",')],
    },
}


def run(*cmd: str, **kw) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def sdist(name: str, version: str, into: Path) -> Path:
    """The package's sdist from PyPI, unpacked; its source directory."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json") as r:
        url = next(u["url"] for u in json.load(r)["urls"] if u["filename"].endswith(".tar.gz"))
    archive = into / url.rsplit("/", 1)[1]
    with urllib.request.urlopen(url) as r, archive.open("wb") as f:
        shutil.copyfileobj(r, f)
    with tarfile.open(archive) as t:
        t.extractall(into, filter="data")
    return into / f"{name}-{version}"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--work", type=Path, help="where the toolchain goes (default: OUT/../.lite-work)")
    args = ap.parse_args(argv)
    out = args.out.resolve()
    work = (args.work or out.parent / ".lite-work").resolve()
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    venv = work / "venv"
    if not (venv / "bin" / "pyodide").exists():
        run("uv", "venv", "-q", "--python", HOST_PYTHON, str(venv))
        run("uv", "pip", "install", "-q", "--python", str(venv / "bin" / "python"), PYODIDE_BUILD)
    pyodide = str(venv / "bin" / "pyodide")
    env = dict(os.environ, PYODIDE_XBUILDENV_PATH=str(work / "xbuildenv"))
    if not (work / "xbuildenv" / "xbuildenv").exists():
        # --url: the version search reads a metadata host, the release asset is enough.
        run(pyodide, "xbuildenv", "install", "--url", XBUILDENV, env=env)
        run(pyodide, "xbuildenv", "install-emscripten", env=env)
    emsdk = subprocess.run([pyodide, "config", "get", "emsdk_dir"], env=env, check=True,
                           capture_output=True, text=True).stdout.strip()
    # emsdk_env.sh puts emcc on PATH; read its environment rather than re-deriving it.
    shown = subprocess.run(["bash", "-c", f'source "{emsdk}/emsdk_env.sh" >/dev/null 2>&1 && env -0'],
                           env=env, check=True, capture_output=True, text=True).stdout
    env = dict(line.split("=", 1) for line in shown.split("\0") if "=" in line)
    env["CMAKE_BUILD_PARALLEL_LEVEL"] = str(os.cpu_count() or 2)

    for name, spec in PACKAGES.items():
        for old in out.glob(f"{name}-*.whl"):
            old.unlink()
        src_root = work / "src"
        shutil.rmtree(src_root / f"{name}-{spec['version']}", ignore_errors=True)
        src_root.mkdir(exist_ok=True)
        src = sdist(name, spec["version"], src_root)
        pyproject = src / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        for old, new in spec.get("pyproject", []):
            if old not in text:
                raise SystemExit(f"{name}: pyproject.toml no longer reads {old!r}")
            text = text.replace(old, new)
        pyproject.write_text(text, encoding="utf-8")
        pkg_env = dict(env, SKBUILD_CMAKE_ARGS=spec["cmake_args"])
        if "cxxflags" in spec:
            pkg_env["CXXFLAGS"] = spec["cxxflags"]
        run(pyodide, "build", "-o", str(out), ".", cwd=src, env=pkg_env)
        # pyodide build leaves the pre-repack wheel beside the one Pyodide loads.
        for stale in out.glob(f"{name}-*-emscripten_*_wasm32.whl"):
            stale.unlink()
    print("\n".join(sorted(p.name for p in out.glob("*.whl"))))


if __name__ == "__main__":
    main()
