"""The WP-1115 compiled tier against the numpy path it accelerates.

Two things are checked here and they are different in kind.

**The arithmetic**, at the bar each kernel claims in ``model/compiled.py``:

* the **scatter** is bit-identical, and that is not a tolerance dressed up as
  one — no library function enters the sum, so the two implementations perform
  the same IEEE operations in the same order and the assertion is on the raw
  bit pattern;
* the **profile kernels** agree to rounding — 1e-13 relative, WP-1112's bar —
  and on symmetric rows they are bit-identical *where that was measured*.
  Which is a property of the platform rather than of the code: numba calls the
  C library's ``exp``, numpy its own vectorised routine, and the two agree bit
  for bit on darwin/arm64 against numpy 2.5.2 and miss by ~3e-17 on Linux.  The
  bit is therefore asserted only there, for the same reason
  ``test_backend_shim`` pins its goldens to one platform.  The pad tail is
  excluded from the bit assertion either way: numpy reaches it by multiplying
  the computed value by ``mask``, so a negative value lands on ``-0.0`` there
  while the kernel never writes it at all, and nothing downstream can see the
  difference because the scatter drops the pad.

**The contract**, which is the half a green arithmetic test would not notice: a
build with no numba, or one with the tier switched off, must produce a working
fit rather than an ``ImportError``.  The fallback is only real if something
runs it, so the switch is exercised here and, one rank up, by every golden in
``tests/test_backend_shim.py``.

What is deliberately *not* asserted: that the compiled path is faster.  Wall
clock belongs in ``examples/bench_refinement.py``, where it is quoted as a
range with its venv and platform (CLAUDE.md § Commands); a timing assertion in
a suite that runs under ``-n auto`` measures the machine, not the change.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from rietx import Instrument, PatternData
from rietx._about import COMPILED_ENV, STATE_DIR_ENV
from rietx.model import compiled
from rietx.model.forward import BatchLayout, accumulate_planes, compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure

pytestmark = pytest.mark.skipif(
    not compiled.available(), reason="no numba in this venv")


@pytest.fixture(autouse=True)
def _restore_switch():
    """Every test here moves the switch; none may leak it to the next module."""
    was = compiled.set_enabled(None)
    yield
    compiled.set_enabled(was)


def _bits_equal(a, b) -> bool:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    return a.shape == b.shape and np.array_equal(a.view(np.int64),
                                                 b.view(np.int64))


def _rel(a, b) -> float:
    scale = float(np.abs(b).max()) or 1.0
    return float(np.abs(np.asarray(a) - np.asarray(b)).max()) / scale


def _both(fn):
    """``fn()`` on the numpy path and on the compiled one, in that order."""
    compiled.set_enabled(False)
    want = fn()
    compiled.set_enabled(True)
    compiled.warm(block=True)
    return fn(), want


# -- the scatter --------------------------------------------------------------
def _layout(rng, rows: int, w: int, n_points: int) -> BatchLayout:
    i0 = np.sort(rng.integers(0, n_points - w - 1, rows)).astype(np.int64)
    i1 = i0 + rng.integers(max(w // 2, 1), w, rows)
    width = i1 - i0
    w_max = int(width.max())
    ar = np.arange(w_max, dtype=np.int64)[None, :]
    idx = np.minimum(i0[:, None] + ar, np.maximum(i1 - 1, 0)[:, None])
    return BatchLayout(
        il=np.zeros(rows, dtype=np.int64), k=np.arange(rows), i0=i0, i1=i1,
        width=width, w_max=w_max, idx=idx, x=np.zeros((rows, w_max)),
        mask=(ar < width[:, None]).astype(np.float64),
        fcj=np.zeros(rows, dtype=np.int64), buckets={0: np.arange(rows)},
        line_ptr=np.array([0, rows]))


@pytest.mark.parametrize("n_terms", [1, 2, 3, 4])
def test_the_scatter_is_bit_identical_at_every_arity(n_terms):
    """All four arities, because each is a separate branch of the kernel.

    One term is what every intensity-only column and the forward build; four is
    ``_peak_chain_column``'s full set.  A branch written with the two adds
    folded into one expression would pass a tolerance test and fail this.
    """
    rng = np.random.default_rng(11)
    n_points = 4000
    parts = []
    for _ in range(3):
        lay = _layout(rng, 400, 51, n_points)
        terms = [(rng.standard_normal(len(lay.i0)),
                  rng.standard_normal((len(lay.i0), lay.w_max)) * lay.mask)
                 for _ in range(n_terms)]
        parts.append((lay, terms))
    got, want = _both(lambda: accumulate_planes(n_points, parts))
    assert _bits_equal(got, want)


def test_the_scatter_declines_an_arity_it_was_not_written_for():
    """Five terms is not a shape the kernel has a branch for, and the honest
    answer is the numpy expression rather than a wrong sum or a raise."""
    rng = np.random.default_rng(12)
    lay = _layout(rng, 50, 21, 500)
    terms = [(rng.standard_normal(len(lay.i0)),
              rng.standard_normal((len(lay.i0), lay.w_max)) * lay.mask)
             for _ in range(compiled.MAX_TERMS + 1)]
    compiled.set_enabled(True)
    compiled.warm(block=True)
    assert compiled.accumulate(500, [(lay, terms)]) is None
    got, want = _both(lambda: accumulate_planes(500, [(lay, terms)]))
    assert _bits_equal(got, want)


# -- the profile kernels ------------------------------------------------------
def _model(*, axial: bool):
    phases = [
        Phase(name="a", space_group="P21/c",
              cell=Cell(a=Parameter(value=5.2), b=Parameter(value=6.4),
                        c=Parameter(value=7.8), alpha=Parameter(value=90.0),
                        beta=Parameter(value=105.0),
                        gamma=Parameter(value=90.0)),
              atoms=[Atom(label="Fe", species="Fe", x=Parameter(value=0.0),
                          y=Parameter(value=0.0), z=Parameter(value=0.0)),
                     Atom(label="C", species="C", x=Parameter(value=0.23),
                          y=Parameter(value=0.31), z=Parameter(value=0.42))],
              scale=Parameter(value=1e-3)),
    ]
    if axial:
        ins = Instrument.bragg_brentano(radiation="CuKa",
                                        goniometer_radius_mm=173.0)
        ins.geometry.axial_sl.value = 0.025
        ins.geometry.axial_hl.value = 0.030
    else:
        ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    structure = Structure(phases=phases)
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    model = compile_model(structure, ins, pattern)
    table = ParameterTable(structure, ins)
    return model, table.decode(table.x0())


def test_symmetric_rows_land_on_the_numpy_doubles():
    """A symmetric row is a straight transcription, so the only thing that can
    move it is ``exp``, and whether that moves it is a **property of the
    platform, not of the code**.

    numba calls the C library's ``exp``; numpy calls its own vectorised
    routine.  Measured: they agree bit for bit on darwin/arm64 against numpy
    2.5.2, and miss by ~3e-17 relative on Linux — which cost a CI round, and is
    why the bar this test enforces everywhere is the rounding one.  The bit is
    asserted only where it was measured, on the same platform and for the same
    reason ``test_backend_shim``'s goldens are pinned to one: it is a real
    property worth not losing silently, and it is not portable.

    In window only, either way: see the module docstring on the pad tail.
    """
    model, values = _model(axial=False)
    assert not any(np.any(cp.batch.fcj > 0) for cp in model.phases)
    got, want = _both(lambda: model.derivative_bases(values))
    on_the_measured_platform = (sys.platform, platform.machine()) == ("darwin",
                                                                     "arm64")
    for gp, wp in zip(got.planes, want.planes):
        inwin = gp.layout.mask > 0
        for name in ("omega", "d_pos", "d_gamma", "d_eta"):
            a, b = getattr(gp, name)[inwin], getattr(wp, name)[inwin]
            assert _rel(a, b) < 1e-15, f"{name} past the rounding bar"
            if on_the_measured_platform:
                assert _bits_equal(a, b), (
                    f"{name} moved off the numpy bits on darwin/arm64, where "
                    "they were measured identical — a transcription changed")


def test_the_forward_and_the_bases_keep_their_separate_spellings():
    """Ω from the forward and Ω from the bases must stay 1-2 ulp apart.

    They are built by the same kernel under different ``spell`` flags, which is
    exactly the way to lose the distinction by accident — one shared code path
    and one forgotten argument.  Two guards, and the second is deliberately
    platform-gated rather than dressed up as portable.

    **That the two spells produce different output** is checkable anywhere and
    catches the likeliest mistake, a forgotten argument leaving both callers on
    one spelling.  **Which of them is which** cannot be established by
    magnitude off the measured platform, and pretending otherwise would be the
    weakest kind of green: the gap between the spellings is 1-2 ulp, and so is
    the gap between numba's ``exp`` and numpy's, so on Linux "used the other
    spelling" and "used the right one" are literally the same size — measured
    at 2.87e-17 against a 5.74e-17 spelling gap, a factor of two.  On
    darwin/arm64, where ``exp`` agrees, each compiled Ω is bit-equal to its own
    numpy function and a swap is unmissable.  So that is where the identity is
    asserted, on the same argument that pins ``test_backend_shim``'s goldens to
    one platform.
    """
    model, values = _model(axial=False)

    def pair():
        fwd = model._phase_component_batched(0, values)
        omega = model.derivative_bases(values, profile_derivs=False).planes[0]
        inten = omega.inten
        bas = accumulate_planes(len(model.tt),
                                [(omega.layout, [(inten, omega.omega)])])
        return fwd, bas

    (g_fwd, g_bas), (w_fwd, w_bas) = _both(pair)
    assert not _bits_equal(w_fwd, w_bas), \
        "the numpy spellings stopped differing — this guard proves nothing"
    assert not _bits_equal(g_fwd, g_bas), \
        "the compiled kernel lost the spelling distinction"
    if (sys.platform, platform.machine()) == ("darwin", "arm64"):
        assert _bits_equal(g_fwd, w_fwd), \
            "the compiled forward stopped reproducing pseudo_voigt"
        assert _bits_equal(g_bas, w_bas), \
            "the compiled bases Ω stopped reproducing _components"


def test_fcj_rows_agree_to_rounding_on_every_plane():
    """Including the two axial planes, which are node-FD differences divided by
    1e-7 and so the place a last-digit disagreement is most amplified."""
    model, values = _model(axial=True)
    assert any(np.any(cp.batch.fcj > 0) for cp in model.phases)
    got, want = _both(lambda: model.derivative_bases(values))
    for gp, wp in zip(got.planes, want.planes):
        for name in ("omega", "d_pos", "d_gamma", "d_eta", "d_sl", "d_hl"):
            a, b = getattr(gp, name), getattr(wp, name)
            assert (a is None) == (b is None), f"{name} present on one path only"
            if a is None:
                continue
            assert _rel(a, b) < 1e-13, f"{name} past the rounding bar"


def test_the_forward_agrees_with_the_scalar_loop_on_fcj_data():
    """The oracle chain, end to end: the compiled path against the
    per-reflection loop that neither batching nor compiling may drift from."""
    model, values = _model(axial=True)
    compiled.set_enabled(True)
    compiled.warm(block=True)
    for ip in range(len(model.phases)):
        got = model._phase_component_batched(ip, values)
        want = model._phase_component_scalar(ip, values)
        assert _rel(got, want) < 1e-13


# -- the contract -------------------------------------------------------------
def test_the_switch_turns_the_tier_off_without_a_reinstall():
    """``RIETX_COMPILED=0``'s python-level twin: the knob a user who cannot run
    the compiled tier reaches for, since an extra could not have removed it."""
    compiled.set_enabled(False)
    assert not compiled.enabled()
    model, values = _model(axial=True)
    assert np.isfinite(model.evaluate(values)).all()
    compiled.set_enabled(True)
    assert compiled.enabled()


def test_a_build_with_no_numba_still_fits(monkeypatch):
    """The soft import is the whole reason numba can be a *required* dependency
    without making it a hard one, so it is worth a test that actually removes
    the kernels rather than one that reads the code and believes it."""
    model, values = _model(axial=True)
    compiled.set_enabled(True)
    compiled.warm(block=True)
    want = model.evaluate(values)
    monkeypatch.setattr(compiled, "_KERNELS", None)
    monkeypatch.setattr(compiled, "_UNAVAILABLE", True)
    assert compiled.accumulate(len(model.tt), []) is None
    got = model.evaluate(values)
    assert _rel(got, want) < 1e-13


def test_the_disk_cache_lands_in_the_state_dir_and_not_beside_the_source(
        tmp_path):
    """numba reads ``NUMBA_CACHE_DIR`` **when it is imported**, once.

    Setting it later does nothing, and the cache then falls back to
    ``__pycache__`` beside the source — inside ``site-packages`` for an ordinary
    install, which is read-only often enough to matter, and where an unwritable
    cache means recompiling in every process with nothing said.  This was live
    here for one commit and worked perfectly on a dev checkout, which is exactly
    where nobody notices; only counting the files caught it.

    A subprocess, because the ordering being asserted is an import ordering and
    this one has numba loaded already.
    """
    env = dict(os.environ)
    env[STATE_DIR_ENV] = str(tmp_path)
    env.pop("NUMBA_CACHE_DIR", None)
    env.pop(COMPILED_ENV, None)
    script = (
        "from rietx.model import compiled\n"
        "compiled.warm(block=True)\n"
        "assert compiled._kernels() is not None, 'kernels did not build'\n"
    )
    out = subprocess.run([sys.executable, "-c", script], env=env,
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    written = sorted(p.name for p in (tmp_path / "numba-cache").rglob("*.nb[ic]"))
    assert written, f"nothing cached under {tmp_path}: {out.stderr}"
    beside = Path(compiled.__file__).parent / "__pycache__"
    assert not list(beside.glob("*.nb[ic]")), \
        f"cache leaked beside the source: {sorted(p.name for p in beside.glob('*.nb[ic]'))}"


def test_the_thread_count_is_settable_and_never_zero(monkeypatch):
    """A pool of zero workers raises, and the environment is a stranger's."""
    from rietx._about import COMPILED_THREADS_ENV

    for raw, want in (("1", 1), ("4", 4), ("0", 1), ("-3", 1), ("", None),
                      ("many", None)):
        monkeypatch.setenv(COMPILED_THREADS_ENV, raw)
        got = compiled.n_threads()
        assert got >= 1
        if want is not None:
            assert got == want, f"{raw!r} gave {got}"


def test_the_cache_redirect_survives_a_numba_another_thread_is_importing(
        monkeypatch):
    """``warm`` imports numba on a *thread*, so the module can be half-built.

    :func:`compiled.warm` deliberately keeps the numba import off the calling
    thread, which means a first :func:`compiled.enabled` on that thread can run
    while the background one is inside ``import numba`` — ``sys.modules`` has
    the module, with no ``config`` attribute on it yet.  Reading ``mod.config``
    there raised ``AttributeError`` out of an ordinary fit; it surfaced as a
    crashed benchmark that ran clean on the next attempt, which is how a race
    announces itself.

    The stand-in *is* the racing state rather than a mock of it, and that is
    what makes the assertion deterministic: a test that started a thread and
    hoped to land inside its import would fail to reproduce far more often
    than it reproduced.

    Skipping the correction is also correct and not merely safe — the thread
    doing the importing came through ``_redirect_cache`` first, so the
    environment variable the fresh import reads was already set.
    """
    monkeypatch.setenv("NUMBA_CACHE_DIR", "/tmp/set-by-the-other-thread")
    half_built = types.ModuleType("numba")     # exactly: no ``config`` yet
    assert not hasattr(half_built, "config")
    monkeypatch.setitem(sys.modules, "numba", half_built)

    compiled._redirect_cache()                 # must not raise

    assert os.environ["NUMBA_CACHE_DIR"] == "/tmp/set-by-the-other-thread", \
        "a caller's (or the other thread's) setting must survive"
