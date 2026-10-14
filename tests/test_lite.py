"""The browser copy of the tutorials (`docs/lite/`, WP-1966): the projection, not the build.

Building the site needs JupyterLite and three cross-compiled wheels, and running
it needs a browser, so neither is here (`docs/lite/README.md` has both commands).
What is here is the part a tutorial edit can break with nothing else going red:
each notebook must carry exactly one install cell for `build.project` to replace,
and everything else must reach the browser unchanged.  The kernels the site
builds from `kernels/` must also satisfy rietx's own `rietx-kernels`
requirement, or micropip refuses rietx in every notebook at once.

And one fact about the browser's Python that a native run never meets: the
kernel replaces `fcntl` with an empty module, so every lock site must read a
missing `flock` the way it reads Windows.  Tutorial 02 raised on it at
`Project.create` until WP-1966.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TUTORIALS = ROOT / "examples" / "tutorials"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LITE = _load("_test_lite_build", ROOT / "docs" / "lite" / "build.py")
WHEELS = _load("_test_lite_wheels", ROOT / "docs" / "lite" / "build_wheels.py")
NOTEBOOKS = sorted(TUTORIALS.glob("[0-9][0-9]_*.ipynb"))


def test_there_are_notebooks_to_project():
    assert NOTEBOOKS, f"no tutorial notebook in {TUTORIALS}"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_projection_replaces_the_install_cell_and_nothing_else(path):
    original = json.loads(path.read_bytes())
    projected = LITE.project(path.read_bytes())

    assert len(projected["cells"]) == len(original["cells"])
    changed = [i for i, (a, b) in enumerate(zip(original["cells"], projected["cells"])) if a != b]
    assert len(changed) == 1, f"{path.name}: cells {changed} changed, expected only the install cell"
    cell = projected["cells"][changed[0]]
    assert "".join(cell["source"]) == LITE.install_source()
    assert cell["outputs"] == [] and cell["execution_count"] is None
    assert projected["metadata"]["kernelspec"]["name"] == "python"  # the Pyodide kernel's
    assert {k: v for k, v in projected["metadata"].items() if k != "kernelspec"} == \
        {k: v for k, v in original["metadata"].items() if k != "kernelspec"}


def test_the_kernels_built_here_satisfy_rietx_s_own_requirement():
    """The site builds rietx-kernels from `kernels/`, so the crate's version is
    the one micropip weighs against rietx's requirement in the browser."""
    crate = tomllib.loads((ROOT / "kernels" / "Cargo.toml").read_text(encoding="utf-8"))
    version = crate["package"]["version"]
    wheel = Path(f"rietx_kernels-{version}-cp311-abi3-pyemscripten_2026_0_wasm32.whl")
    dependencies = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    LITE.check_kernels(wheel, dependencies["project"]["dependencies"])


def test_kernels_the_rietx_refuses_stop_the_build():
    wheel = Path("rietx_kernels-2.0.0-cp311-abi3-pyemscripten_2026_0_wasm32.whl")
    with pytest.raises(SystemExit, match="does not satisfy"):
        LITE.check_kernels(wheel, ["numpy>=1.26", "rietx-kernels<2,>=1.3"])


@pytest.fixture
def jupyterlite_fcntl(monkeypatch):
    """What JupyterLite's Pyodide kernel does at start (`pyodide_kernel/mocks.py`):
    an empty module named `fcntl`, which `import fcntl` accepts with no `flock`."""
    monkeypatch.setitem(sys.modules, "fcntl", types.ModuleType("fcntl"))


def test_the_history_store_reads_an_empty_fcntl_as_no_lock(jupyterlite_fcntl, tmp_path):
    # A fresh copy, since the store binds flock at import.
    spec = importlib.util.spec_from_file_location(
        "rietx.history._store_under_jupyterlite", ROOT / "src" / "rietx" / "history" / "store.py")
    store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(store)
    assert store.flock is None
    with (open(tmp_path / "history.jsonl", "w", encoding="utf-8", newline="\n") as handle,
          store._locked(handle)):
        handle.write("{}\n")


def test_the_run_lock_reads_an_empty_fcntl_as_windows(jupyterlite_fcntl, tmp_path):
    from rietx import runs

    lock = tmp_path / runs.LOCK_FILE
    lock.write_text("", encoding="utf-8")
    assert runs._probe_lock(lock) == "unavailable"
    recorder = types.SimpleNamespace(dir=tmp_path)
    runs.RunRecorder._take_lock(recorder)
    assert not hasattr(recorder, "_lock_fh")


def test_the_wheel_pins_name_the_kernel_s_pyodide():
    """build_wheels.PYODIDE must be the Pyodide the pinned kernel loads.

    Asked of the installed kernel when there is one.  Without it, the pin
    requirements.txt installs must be the one build_wheels names beside
    PYODIDE, so a kernel bump that leaves PYODIDE behind fails here too."""
    pins = (ROOT / "docs" / "lite" / "requirements.txt").read_text(encoding="utf-8")
    assert WHEELS.KERNEL_PIN in pins.splitlines()
    kernel = pytest.importorskip("jupyterlite_pyodide_kernel.constants")
    assert kernel.PYODIDE_VERSION == WHEELS.PYODIDE
