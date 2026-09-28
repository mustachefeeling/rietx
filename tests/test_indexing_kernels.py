"""WP-1508's compiled dichotomy traversal against the numpy loop it replaces.

**The bar is the bit, at both ranks.**  The kernel's box test calls no library
function but ``sqrt`` and sums its ≤ 6 terms left to right, as numpy's
``.sum(axis=1)`` does at that width, so one box's verdict, survivors, width and
uniqueness are asserted equal to ``_test_box``'s on the raw bit pattern.  One
rank up, the traversal visits the same boxes in the same order, so a whole
search reports the same box and row counts and the same candidates — cell,
A..F, hkl and line assignment, bit for bit — with the tier on and off.

Both paths are **declared** in every test here (the autouse fixture restores
the switch), never inherited: the compiled tier is the default, and a test that
leaves it implicit measures whichever path the environment chose
(``tests/CLAUDE.md`` § Quoting numbers).

What is deliberately not asserted: that the compiled path is faster.  That is a
measurement, quoted with its venv and platform in WP-1508's handover.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.indexing import dichotomy
from rietx.indexing.dichotomy import (
    MAX_ANGLE_COSINE,
    _centre_volume,
    _centre_volumes,
    _initial_box,
    _max_index,
    _pivot_of,
    _pivots,
    _q_bounds,
    _test_box,
    axis_swaps,
    search_dichotomy,
)
from rietx.indexing.engines import (
    effective_shift_allowance,
    search_line_order,
    trial_hkl,
)
from rietx.indexing.qspace import af_from_cell, design_matrix, metric_basis, sigma_effective
from rietx.model import compiled
from tests.test_indexing_engines import CASES, spec_for, synthetic_peaks

#: every test that builds a kernel; the ordering-key test below needs none,
#: because the numpy loop reads that key too
needs_numba = pytest.mark.skipif(
    not compiled.available(), reason="no numba in this venv")

#: the fast synthetic cases, one per metric dimension up to three
FAST_SYSTEMS = ("cubic", "tetragonal", "hexagonal", "trigonal", "orthorhombic")


@pytest.fixture(autouse=True)
def _restore_switch():
    """Every test here moves the switch; none may leak it to the next module."""
    was = compiled.set_enabled(None)
    yield
    compiled.set_enabled(was)


def _kernels() -> dict:
    compiled.set_enabled(True)
    kernels = dichotomy._traversal_kernels()
    assert kernels is not None, "numba imports here, so the kernels must build"
    return kernels


def _bits(x) -> bytes:
    return np.asarray(x, dtype=np.float64).tobytes()


def test_numpy_still_sums_a_short_row_left_to_right():
    """The one numpy behaviour the kernel copies rather than computes.

    ``_q_bounds`` and ``_af_interval`` reduce ≤ 6 terms with ``.sum(axis=1)``,
    and the kernel reproduces that as a left-to-right loop.  ``1e16 + 1`` rounds
    back to ``1e16``, so left to right gives ``1e16`` where any pairing of the
    two ones first gives ``1e16 + 2``.  If a numpy release changes its
    reduction, this names the cause before the equivalence tests below fail.
    """
    row = np.array([[1e16, 1.0, 1.0], [1e16, 1.0, 1.0]])
    assert np.all(row.sum(axis=1) == 1e16)


# ----------------------------------------------------------------------
# One box
# ----------------------------------------------------------------------
def _box_setup(peaks_system: str, basis_system: str):
    """The inputs ``_search_one`` hands ``_test_box``, built the same way."""
    peaks, cell = synthetic_peaks(peaks_system)
    spec = spec_for(peaks_system)
    q_all = peaks.q()
    allowance, _ = effective_shift_allowance(spec, None)
    sigma = sigma_effective(peaks.q_esd(), peaks.two_theta(), peaks.wavelength,
                            allowance)
    search = search_line_order(peaks, spec)
    q_search, tol = q_all[search], spec.k_sigma * sigma[search]
    basis = metric_basis(basis_system)
    lo0, hi0 = _initial_box(basis, spec)
    q_hi = float(q_search.max() + tol.max())
    m = design_matrix(trial_hkl(_max_index(spec, q_hi), "P")) @ basis.T
    root_min, _ = _q_bounds(m, lo0, hi0)
    m = np.ascontiguousarray(m[root_min <= q_hi])
    vol_max = CASES[peaks_system][4]
    det_band = (1.0 / vol_max ** 2, 1.0 / 1.0 ** 2)
    swaps = [(_pivot_of(basis, i), _pivot_of(basis, j))
             for i, j in axis_swaps(basis)]
    swaps = [(a, b) for a, b in swaps if a is not None and b is not None]
    # the true cell's θ, where boxes must survive for the test to mean anything
    af = af_from_cell(cell)
    theta = np.array([af[p] / v for p, v in _pivots(basis)])
    return dict(m=m, basis=basis, lo0=lo0, hi0=hi0, q_hi=q_hi, det_band=det_band,
                swaps=swaps, lo_s=q_search - tol, hi_s=q_search + tol,
                n_unindexed=spec.n_unindexed, theta=theta)


@pytest.mark.parametrize("peaks_system,basis_system", [
    ("cubic", "cubic"), ("tetragonal", "tetragonal"), ("hexagonal", "hexagonal"),
    ("trigonal", "trigonal"), ("orthorhombic", "orthorhombic"),
    ("monoclinic", "monoclinic"),
    # a 6-D box over an orthorhombic list: the box test does not care where the
    # truth is, and this is the only way to reach every off-diagonal and every
    # swap without a triclinic search
    ("orthorhombic", "triclinic"),
])
@needs_numba
def test_one_box_is_the_numpy_box_bit_for_bit(peaks_system, basis_system):
    """Verdict, survivors, width and uniqueness of ``_test_box``, on the bit.

    Boxes are drawn at every scale from 1e-4 to half the domain, half of them
    around the true cell so that survivors — the case with something to get
    wrong — are common, and over row subsets as well as the whole search set,
    because the traversal hands the test a filtered list.  The last assertion
    is the vacuity guard: a draw where nothing survives would pass whatever the
    kernel did.
    """
    s = _box_setup(peaks_system, basis_system)
    k = _kernels()["test_rows"]
    m, basis = s["m"], s["basis"]
    rng = np.random.default_rng(1508)
    n_dim = len(s["lo0"])
    span = s["hi0"] - s["lo0"]
    out = np.empty(len(m), dtype=np.int64)
    scratch = (np.empty(len(m)), np.empty(len(m)),
               np.empty(len(s["lo_s"]), dtype=np.int64),
               np.empty(len(s["lo_s"]), dtype=np.int64), np.empty(6), np.empty(6))
    basis_t = np.ascontiguousarray(basis.T)
    swaps = np.asarray(s["swaps"], dtype=np.int64).reshape(-1, 2)
    outcomes = {True: 0, False: 0}
    for trial in range(400):
        centre = (s["theta"] if trial % 2 else
                  s["lo0"] + rng.random(n_dim) * span)
        half = span * 10.0 ** rng.uniform(-4.0, -0.3, n_dim)
        lo = np.maximum(centre - half, s["lo0"])
        hi = np.minimum(centre + half, s["hi0"])
        keep = rng.random(len(m)) < (1.0, 0.5, 0.05)[trial % 3]
        rows = np.flatnonzero(keep).astype(np.int64)
        want = _test_box(m[rows], lo, hi, basis, s["q_hi"], s["det_band"],
                         s["swaps"], s["lo_s"], s["hi_s"], s["n_unindexed"])
        ok, n_out, width, unique = k(
            m, rows, lo, hi, basis_t, s["q_hi"], s["det_band"][0],
            s["det_band"][1], swaps, s["lo_s"], s["hi_s"], s["n_unindexed"],
            float(MAX_ANGLE_COSINE), out, *scratch)
        assert ok == (want is not None), f"trial {trial}: verdicts differ"
        outcomes[ok] += 1
        if want is None:
            continue
        m_kept, w_want, u_want = want
        assert np.array_equal(m[out[:n_out]], m_kept), f"trial {trial}: survivors"
        assert np.all(np.isin(out[:n_out], rows))
        assert np.all(np.diff(out[:n_out]) > 0), "survivors keep their order"
        assert _bits(width) == _bits(w_want), f"trial {trial}: width bits"
        assert unique == u_want, f"trial {trial}: uniqueness"
    assert outcomes[True] >= 20 and outcomes[False] >= 20, outcomes


# ----------------------------------------------------------------------
# A whole search
# ----------------------------------------------------------------------
def _signature(result) -> tuple:
    """Everything a search reports that the traversal could move, as bytes."""
    cands = [(c.system, c.centring, _bits(c.cell), c.n_indexed, _bits(c.fit.af),
              np.asarray(c.hkl).tobytes(), np.asarray(c.line_index).tobytes())
             for c in result.candidates]
    stats = {k: v for k, v in result.stats.items() if not k.endswith(".seconds")}
    return cands, stats, dict(result.search_complete)


def _both(system: str, monkeypatch, **spec_kw) -> tuple:
    """Each path's result, and the **sequence** of leaves it reached.

    The leaf sequence is the stronger half.  A finished search tests the same
    set of boxes in any order, so box and row counts cannot see the order, and
    the candidate list sees it only where two leaves share a ``_box_key`` —
    the first one refined wins.  Recording every key request, in order and on
    the bit, is what would catch a traversal that pushed its children the
    other way round (measured: flipping the tie rule passes every other
    assertion in this file).
    """
    peaks, _cell = synthetic_peaks(system)
    key = dichotomy._box_key
    out = []
    for flag in (False, True):
        leaves: list[bytes] = []

        def recording_key(af, _leaves=leaves):
            _leaves.append(_bits(af))
            return key(af)

        monkeypatch.setattr(dichotomy, "_box_key", recording_key)
        compiled.set_enabled(flag)
        out.append((search_dichotomy(peaks, spec=spec_for(system, **spec_kw)),
                    leaves))
    monkeypatch.setattr(dichotomy, "_box_key", key)
    return tuple(out)


@needs_numba
@pytest.mark.parametrize("system", FAST_SYSTEMS)
def test_a_whole_search_reports_the_same_boxes_and_candidates(system, monkeypatch):
    (numpy_result, numpy_leaves), (compiled_result, compiled_leaves) = _both(
        system, monkeypatch)
    assert numpy_result.candidates, "a search that finds nothing checks little"
    assert _signature(compiled_result) == _signature(numpy_result)
    assert compiled_leaves == numpy_leaves, "the leaves arrived in another order"


@needs_numba
@pytest.mark.parametrize("system", ("tetragonal", "orthorhombic"))
def test_every_handback_resumes_where_the_traversal_stopped(system, monkeypatch):
    """Hand back after every box, every leaf, and on every pool write.

    The kernel returns to python to run a leaf's ``_accept``, to let the budget
    be asked, and to have its pool grown, and each resume must carry on from
    exactly the stack it left.  Forcing all three on every box is the cheap way
    to make a resume bug show as a different search rather than hide in the
    one run a day that happens to cross a boundary.
    """
    monkeypatch.setattr(dichotomy, "TRAVERSAL_ROW_CHUNK", 1)
    monkeypatch.setattr(dichotomy, "TRAVERSAL_LEAF_BUFFER", 1)
    monkeypatch.setattr(dichotomy, "_POOL_HEADROOM", 0)
    (numpy_result, numpy_leaves), (compiled_result, compiled_leaves) = _both(
        system, monkeypatch)
    assert _signature(compiled_result) == _signature(numpy_result)
    assert compiled_leaves == numpy_leaves


@needs_numba
def test_an_expired_budget_stops_the_compiled_search_and_says_so(monkeypatch):
    """A cut search is incomplete on both paths — never silently finished."""
    (numpy_result, _), (compiled_result, _) = _both(
        "orthorhombic", monkeypatch, budget_seconds=1e-9)
    assert numpy_result.search_complete == {"orthorhombic": False}
    assert compiled_result.search_complete == {"orthorhombic": False}


@needs_numba
def test_the_switch_turns_the_compiled_traversal_off():
    """``RIETX_COMPILED``'s switch is the one knob: off means the numpy loop."""
    compiled.set_enabled(False)
    assert dichotomy._traversal_kernels() is None
    compiled.set_enabled(True)
    assert dichotomy._traversal_kernels() is not None


def test_the_ordering_key_is_the_scalar_one_on_the_bit():
    """``_centre_volumes`` orders the grid's survivors for both paths.

    It replaced a per-cell loop that became a quarter of a compiled 4-D unit, and
    it may not move a single bit of the key: two cells whose keys differ in the
    last place would swap, and the search would visit them in another order.
    Boxes are drawn over the whole triclinic domain, where most centres are not
    lattices at all, so the ``inf`` branch is exercised beside the finite one.
    """
    rng = np.random.default_rng(15081)
    for system in ("cubic", "hexagonal", "orthorhombic", "monoclinic", "triclinic"):
        basis = metric_basis(system)
        spec = spec_for("monoclinic")
        lo0, hi0 = _initial_box(basis, spec)
        boxes = []
        for _ in range(300):
            a = lo0 + rng.random(len(lo0)) * (hi0 - lo0)
            b = lo0 + rng.random(len(lo0)) * (hi0 - lo0)
            boxes.append((np.minimum(a, b), np.maximum(a, b), None))
        want = [_centre_volume(basis, lo, hi) for lo, hi, _ in boxes]
        got = _centre_volumes(basis, boxes)
        assert _bits(got) == _bits(want), system
        if system == "triclinic":
            assert np.isinf(want).any() and np.isfinite(want).any()
    assert _centre_volumes(metric_basis("cubic"), []) == []
