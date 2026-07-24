"""WP-0404 — cross-backend Jacobian agreement.

DESIGN.md's mitigation for *backend drift* (small op vocabulary + mandatory
cross-backend tests), made executable: every way pxrdref can produce a Jacobian
is compared against the analytic one on the same compiled state, so a backend
that starts computing a different derivative is caught here rather than in an
esd three milestones later.

The matrix
----------
**Methods** (all compared against the analytic assembly, ``backend="numpy"``
under the default fp64 policy):

* ``fd`` — central differences of the numpy residual, the reference that is
  independent of *both* the analytic chain and autodiff;
* ``jax`` — chunked jacfwd (WP-0402), ``importorskip``-gated;
* ``torch`` — fp64 CPU jacfwd; the row is wired and skips itself until
  WP-0408 teaches ``_jacobian_for`` the backend;
* ``numpy+fp32`` / ``jax+fp32`` — the WP-0403 mixed-precision *policy*, which
  is not a backend but a layer over whichever one built the columns, so it
  composes with both and needs no optional dependency.

**Configs**: the 18 ``ANALYTIC_FAMILIES`` on the v0.2 lab state, plus the five
WP-0401 golden states — ``toy_lebail`` (Le Bail snapshot + P-spline penalty
rows), ``toy_pawley`` (aux intensity block + overlap-restraint rows),
``toy_rich`` (aniso ADPs + March-Dollase + *nonzero* extinction + displacement/
transparency), and the real-data ``srm660c`` / ``nac`` (marked ``slow``).
Multi-histogram (stacked ``run_multi_least_squares`` layout) and the
stage-boundary recompiles get their own tests below.  Le Bail and Pawley are
single-histogram only — WP-0308 shipped multi-histogram as Rietveld-only,
because per-pattern intensity extractions are not a shared quantity.

Tolerances
----------
The fp32 bars are **imported** from ``backend.linalg64`` (WP-0403 owns them);
restating the numbers here would be the exact drift this file exists to catch.
The fp64 bars are declared here, in the v0.2 style: per-column relative L2
< 5e-3 and cosine > 0.99999.

Two documented exceptions, neither of them drift:

* **The FCJ S/L == H/L kink.**  The quadrature split point ξ_kink = |S/L − H/L|
  sits at its own non-differentiable zero when the two axial ratios are equal
  (``srm660c`` starts exactly there), so the analytic node-FD (right-sided),
  jacfwd (sign(0) = 0 subgradient) and central FD legitimately disagree at the
  few-1e-3 level — measured jax-vs-analytic 6.1e-3 on ``axial_hl``.  Those two
  columns get WP-0402's loose bar, and only when the state actually sits on the
  kink.  ``_lab_state``/``toy_rich`` use unequal ratios on purpose.
* **Axial columns routed to FD** (``DerivativeBases.axial_ok`` False, i.e. an
  axial ratio ≤ 0 with FCJ nodes allocated): autodiff correctness *at* that
  discontinuity was declared out of scope in WP-0401, so those columns are
  excluded explicitly rather than quietly tolerated.  No config here triggers
  it; the check asserts that, so the exclusion cannot go silent.

Why central differences
-----------------------
Forward differences carry O(h) truncation error, and on real data with sharp
peaks that is not small: measured against the analytic column on ``srm660c``,
forward FD sits 6.2e-3 away on ``phases.0.cell.a`` and ``nac`` 4.7e-3 — at or
past the 5e-3 bar, for reasons that have nothing to do with any backend.  The
same columns with central differences (O(h²)) land at 1.2e-3 and 2.2e-5.  A bar
loose enough to accommodate forward FD would be too loose to catch drift, so
the FD *reference* here is central; the forward-difference variant remains
under test where it belongs, as the v0.2 harness
(``test_v02_core.test_analytic_jacobian_matches_fd``).
"""

from __future__ import annotations

import numpy as np
import pytest

from pxrdref.backend.linalg64 import (
    COLUMN_COSINE_MIN,
    COLUMN_REL_L2_MAX,
    FP32_JACOBIAN,
    precision_policy,
)
from pxrdref.model.forward import compile_model
from pxrdref.optimize.least_squares import _jacobian_for, _make_residual
from pxrdref.params.vector import ParameterTable
from tests.test_backend_shim import STATES
from tests.test_v02_core import ANALYTIC_FAMILIES, _lab_state

#: fp64 agreement bars — declared here (the v0.2 harness's numbers).  The fp32
#: pair is imported above: WP-0403 owns COLUMN_REL_L2_MAX / COLUMN_COSINE_MIN.
REL_L2_MAX = 5e-3
COSINE_MIN = 0.99999

#: the loose bar for a column sitting on a documented kink of the
#: parameterisation (WP-0402's convention, reused verbatim)
KINK_REL_L2_MAX = 2e-2
KINK_COSINE_MIN = 0.9995
KINK_PATHS = frozenset({"instrument.geometry.axial_sl",
                        "instrument.geometry.axial_hl"})

#: a column is "live" when its norm clears this fraction of the largest
#: column's — below it the value is transform-floor noise, not a derivative
DEAD_COL_FRAC = 1e-6

#: FD step, the same rule as the v0.2 harness (applied ±h, centrally)
FD_STEP = 1e-6


# ----------------------------------------------------------------------
# configs: (model, table) at a compiled expansion point
# ----------------------------------------------------------------------
def _state_families():
    """The 18 analytic column families on the v0.2 lab Bragg-Brentano state."""
    structure, ins, pattern = _lab_state()
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path in ANALYTIC_FAMILIES:
        assert table.set_vary([path], True), path
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    return model, table, {}


CONFIGS = {"families": _state_families, **STATES}

#: the fast configs run everywhere; the two real-data ones are `slow`
CONFIG_PARAMS = [
    "families",
    "toy_lebail",
    "toy_pawley",
    "toy_rich",
    pytest.param("srm660c", marks=pytest.mark.slow),
    pytest.param("nac", marks=pytest.mark.slow),
]

_STATE_CACHE: dict[str, tuple | None] = {}


def _state(name: str):
    """The config's (model, table), built once per session (states are pure)."""
    if name not in _STATE_CACHE:
        _STATE_CACHE[name] = CONFIGS[name]()
    built = _STATE_CACHE[name]
    if built is None:
        pytest.skip(f"dataset for config {name!r} not present")
    model, table, _extras = built
    return model, table


def _theta(model, table) -> np.ndarray:
    """The full free vector: table θ, plus the Pawley intensity block."""
    theta = table.x0()
    if model.pawley is not None:
        theta = np.concatenate([theta, model.pawley_x0()])
    return theta


def _labels(model, table) -> list[str]:
    labels = list(table.free_paths)
    if model.pawley is not None:
        labels += [f"pawley.I{k}" for k in range(model.pawley.n)]
    return labels


def _kink_paths(model, table) -> frozenset[str]:
    """The axial columns, when this state sits exactly on the FCJ S/L == H/L
    kink; empty otherwise (see the module docstring)."""
    values = table.decode(table.x0())
    on_kink = (values["instrument.geometry.axial_sl"]
               == values["instrument.geometry.axial_hl"])
    return KINK_PATHS if on_kink else frozenset()


# ----------------------------------------------------------------------
# methods
# ----------------------------------------------------------------------
def _analytic_jacobian(model, table):
    """The reference: the mixed analytic/FD assembly on the numpy backend."""
    return _jacobian_for(model, table, "numpy")


def _central_fd_jacobian(model, table):
    """Central differences of the (augmented) numpy residual — the reference
    independent of both the analytic chain and autodiff."""
    residual = _make_residual(model, table)

    def jacobian(theta: np.ndarray) -> np.ndarray:
        cols = []
        for c in range(len(theta)):
            h = FD_STEP * max(1.0, abs(theta[c]))
            tp, tm = theta.copy(), theta.copy()
            tp[c] += h
            tm[c] -= h
            cols.append((residual(tp) - residual(tm)) / (2.0 * h))
        return np.column_stack(cols)

    return jacobian


def _backend_jacobian(name: str):
    """A row for an optional backend: skipped when it is not installed, and
    (for torch) while ``_jacobian_for`` does not know it yet — WP-0408."""

    def build(model, table):
        pytest.importorskip(name)
        try:
            return _jacobian_for(model, table, name)
        except ValueError as exc:  # "unknown backend" — not wired yet
            pytest.skip(f"{exc} (torch lands with WP-0408)")

    return build


def _fp32_over(name: str):
    """The WP-0403 policy layered over backend ``name`` — not a backend of its
    own, so it composes with every row above and needs no optional install."""
    inner = _backend_jacobian(name) if name != "numpy" else _analytic_jacobian

    def build(model, table):
        jac = inner(model, table)

        def jacobian(theta: np.ndarray) -> np.ndarray:
            with precision_policy(FP32_JACOBIAN):
                return jac(theta)

        return jacobian

    return build


#: method → (Jacobian builder, rel-L2 bar, cosine bar)
METHODS = {
    "fd": (_central_fd_jacobian, REL_L2_MAX, COSINE_MIN),
    "jax": (_backend_jacobian("jax"), REL_L2_MAX, COSINE_MIN),
    "torch": (_backend_jacobian("torch"), REL_L2_MAX, COSINE_MIN),
    "numpy+fp32": (_fp32_over("numpy"), COLUMN_REL_L2_MAX, COLUMN_COSINE_MIN),
    "jax+fp32": (_fp32_over("jax"), COLUMN_REL_L2_MAX, COLUMN_COSINE_MIN),
}


def _assert_columns(J_ref, J_test, labels, *, rel_max, cos_min,
                    kink=frozenset(), what=""):
    """Per-column rel-L2 + cosine agreement, skipping transform-floor columns."""
    assert J_ref.shape == J_test.shape, f"{what}: {J_ref.shape} vs {J_test.shape}"
    scale = np.linalg.norm(J_ref, axis=0).max()
    n_live = 0
    for c in range(J_ref.shape[1]):
        a, b = J_ref[:, c], J_test[:, c]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if max(na, nb) < DEAD_COL_FRAC * scale:
            continue
        n_live += 1
        bar, cbar = ((KINK_REL_L2_MAX, KINK_COSINE_MIN) if labels[c] in kink
                     else (rel_max, cos_min))
        err = np.linalg.norm(a - b) / max(na, nb)
        assert err < bar, f"{what}{labels[c]}: rel-L2 {err:.3e} (bar {bar:g})"
        cos = float(a @ b) / (na * nb)
        assert cos > cbar, f"{what}{labels[c]}: cosine {cos:.8f} (bar {cbar:g})"
    assert n_live > 0, f"{what}every column was dead — the comparison proved nothing"


# ----------------------------------------------------------------------
# the matrix
# ----------------------------------------------------------------------
@pytest.mark.parametrize("config", CONFIG_PARAMS)
@pytest.mark.parametrize("method", list(METHODS))
def test_jacobian_matches_analytic(method, config):
    model, table = _state(config)
    build, rel_max, cos_min = METHODS[method]
    theta = _theta(model, table)

    J_ref = _analytic_jacobian(model, table)(theta)
    J_test = build(model, table)(theta)   # may skip (optional backend)
    _assert_columns(J_ref, J_test, _labels(model, table),
                    rel_max=rel_max, cos_min=cos_min,
                    kink=_kink_paths(model, table),
                    what=f"{config}/{method} ")


@pytest.mark.parametrize("config", CONFIG_PARAMS)
def test_axial_columns_are_not_silently_fd_routed(config):
    """``axial_ok`` False sends the axial columns to plain FD, and autodiff *at*
    that discontinuity is out of scope (WP-0401).  No config here triggers it —
    asserted, so the exclusion can never become a silent pass."""
    model, table = _state(config)
    values = table.decode(table.x0())
    if not any(p in table.free_paths for p in KINK_PATHS):
        pytest.skip("no axial columns in this config")
    bases = model.derivative_bases(
        values, None if model.mode == "rietveld" else
        [cp.hkl_intensity for cp in model.phases])
    assert bases.axial_ok, (
        f"{config}: axial columns fell back to FD — exclude them explicitly "
        "rather than comparing autodiff at the FCJ discontinuity")


def test_pawley_intensity_columns_are_exact_across_backends():
    """The Pawley aux block is exactly linear in the intensities (−√w·Σ_l w_l·Ω)
    and never finite-differenced, so every fp64 method must agree to round-off
    there — a loose bar on those columns would be hiding something."""
    model, table = _state("toy_pawley")
    assert model.pawley is not None
    theta = _theta(model, table)
    n_table = len(table.free_paths)
    aux_ref = _analytic_jacobian(model, table)(theta)[:, n_table:]
    assert np.linalg.norm(aux_ref) > 0

    for method in ("fd", "jax"):
        build, _rel, _cos = METHODS[method]
        aux = build(model, table)(theta)[:, n_table:]
        err = np.linalg.norm(aux - aux_ref) / np.linalg.norm(aux_ref)
        # central FD of a linear function is exact to round-off scaled by 1/h
        assert err < (1e-6 if method == "fd" else 1e-9), f"{method}: {err:.3e}"

    # the overlap-restraint rows are the constant matrix R itself, in every row
    n_res = model.pawley.restraint.shape[0]
    np.testing.assert_allclose(aux_ref[-n_res:], model.pawley.restraint,
                               rtol=0, atol=1e-12)
