"""How badly-scaled and gradient-free columns reach a reported esd (WP-1110 §14).

The defect these guard against does not show up as a failure, a warning or a
missing number.  It shows up as an esd that is *small*: ``np.linalg.pinv``
discards every eigenvalue below ``rcond × |λ|max``, so one column with a large
gradient sets the cutoff for all of them, and a direction the data does not
constrain is returned with **zero** variance rather than infinite.  On the fit
this WP measured, ``phases.0.gauss_size`` came back 6.1e-14 ± 9.9e-11 — a
figure a reader would quote — where the equilibrated inverse says ± 4.3e+08.

The load-bearing test here is
``test_an_esd_does_not_depend_on_another_parameters_units``.  It needs no
dataset and no tolerance argument: if rescaling one column moves a *different*
column's esd, the inversion is wrong, and it moved by a factor of two.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.optimize.least_squares import covariance_estimates
from rietx.optimize.statistics import normal_covariance


def _problem(seed: int = 0, n: int = 400, p: int = 4):
    rng = np.random.default_rng(seed)
    jac = rng.normal(size=(n, p))
    jac[:, -1] *= 1e-7  # a column carrying almost no gradient
    return jac, rng.normal(size=n) * 0.01


def _esds(jac, resid):
    cov, _ = normal_covariance(jac, resid, jac.shape[1])
    return np.sqrt(np.maximum(np.diag(cov), 0.0))


def test_an_esd_does_not_depend_on_another_parameters_units():
    """Rescale one column; every *other* column's esd must not move.

    A parameter's units are the caller's choice — Biso in Å² or in 1e-4 Å²
    describes the same fit — so an esd that moves when a different parameter is
    respelled is reporting an artefact of the arithmetic.  Before WP-1110 the
    pseudo-inverse took its rcond cutoff from the largest eigenvalue of the
    whole normal matrix, which is exactly the coupling; measured here, the
    other three esds changed by a factor of 2.
    """
    jac, resid = _problem()
    base = _esds(jac, resid)

    rescaled = jac.copy()
    rescaled[:, 0] *= 1e6
    moved = _esds(rescaled, resid)
    moved[0] *= 1e6  # undo the reparameterisation on the column that had it

    assert np.allclose(moved, base, rtol=1e-9), moved / base


def test_a_gradient_free_column_is_undetermined_and_not_precise():
    """No gradient means infinite variance, never zero.

    Zero is the answer that reads as "measured perfectly" — the confident wrong
    singleton the package's own invariant forbids.  Its covariance *with*
    everything else is zero, which is the true statement: a direction the
    residual does not move cannot co-vary with one it does.
    """
    jac, resid = _problem()
    jac[:, -1] = 0.0
    cov, _ = normal_covariance(jac, resid, jac.shape[1])

    assert np.isinf(cov[-1, -1])
    assert np.all(cov[-1, :-1] == 0.0) and np.all(cov[:-1, -1] == 0.0)
    assert np.all(np.isfinite(np.diag(cov)[:-1]))


def test_the_correlation_matrix_survives_an_undetermined_column():
    """``corr`` stays a valid Pearson matrix with an infinity in the diagonal.

    The guard that reads it (``HIGH_CORRELATION``) must not see a NaN, and the
    undetermined column must not read as correlated with anything.
    """
    jac, resid = _problem()
    jac[:, -1] = 0.0
    stderr, corr = covariance_estimates(jac, resid, jac.shape[1])

    assert np.isinf(stderr[-1]) and np.all(np.isfinite(stderr[:-1]))
    assert np.all(np.isfinite(corr))
    assert np.allclose(np.diag(corr), 1.0)
    assert np.all(np.abs(corr) <= 1.0)
    assert np.all(corr[-1, :-1] == 0.0)


def test_a_well_determined_column_keeps_the_esd_it_had():
    """Equilibration is not allowed to move a number anyone was relying on.

    Against the closed form for an orthogonal design, where the covariance is
    ``chi2_red / n`` per column and the scaling has nothing to fix.
    """
    n, p = 512, 4
    jac = np.zeros((n, p))
    for k in range(p):  # orthogonal columns of differing, honest magnitudes
        jac[:, k] = np.cos((k + 1) * np.pi * np.arange(n) / n) * 10.0 ** k
    rng = np.random.default_rng(3)
    resid = rng.normal(size=n) * 0.01

    chi2_red = float(resid @ resid) / (n - p)
    expected = np.sqrt(chi2_red / np.sum(jac * jac, axis=0))
    assert np.allclose(_esds(jac, resid), expected, rtol=1e-10)


@pytest.mark.parametrize("scale", [1.0, 1e-8, 1e8])
def test_the_answer_is_the_same_however_the_whole_problem_is_scaled(scale):
    """Scaling *every* column together must scale every esd together.

    The companion to the units test: the first says the columns must not talk
    to each other, this one says the inversion still tracks an overall change.
    """
    jac, resid = _problem(seed=5)
    base = _esds(jac, resid)
    assert np.allclose(_esds(jac * scale, resid) * scale, base, rtol=1e-9)


# --- propagation: which rows an undetermined column is allowed to cost -------

def _table():
    """A cubic phase: ``cell.a`` free with ``cell.b``/``cell.c`` tied to it."""
    import rietx as rx
    from rietx.params.vector import ParameterTable

    structure = rx.Structure.from_cif("tests/data/cod_1000236.cif")
    instrument = rx.Instrument.debye_scherrer(wavelength=0.4139090)
    structure.phases[0].cell.a.vary = True
    structure.phases[0].scale.vary = True
    instrument.profile.w.vary = True
    return ParameterTable(structure, instrument)


def test_an_undetermined_column_costs_its_own_rows_and_no_others():
    """The rutile failure, at the size where it can be read.

    ``instrument.profile.w`` measured nothing; ``cell.a`` and the two lengths
    tied to it did.  The tied rows must still report — a symmetry tie carries
    its source's esd — and only the profile row goes absent.  Before the mask,
    the infinity in ``Cov_free`` met a zero coefficient in ``C @ cov`` and put
    a NaN on every row sharing a source with it; the rutile geometry table lost
    all six Ti-O bond esds to a parameter no bond depends on.
    """
    table = _table()
    theta = table.x0()
    stderr = np.array([1e-5, 1e-7, np.inf])  # profile.w undetermined
    corr = np.eye(3)

    esd = table.stderr_physical(theta, stderr, corr)
    assert "instrument.profile.w" not in esd
    for path in ("phases.0.cell.a", "phases.0.cell.b", "phases.0.cell.c",
                 "phases.0.scale"):
        assert path in esd and np.isfinite(esd[path]) and esd[path] > 0

    assert esd["phases.0.cell.b"] == pytest.approx(esd["phases.0.cell.a"])


def test_the_mask_names_the_columns_and_the_rows_they_reach():
    """``unmeasured_free`` is over columns, ``unmeasured_rows`` over entries.

    The second is the first pushed through ``C``, which is what makes a *tied*
    row inherit its source's blindness — a tie whose source measured nothing
    measured nothing — without a second rule saying so.
    """
    table = _table()
    theta = table.x0()
    stderr = np.array([np.inf, 1e-7, 1e-6])  # cell.a undetermined

    assert list(table.unmeasured_free(theta, stderr)) == [True, False, False]
    blind = table.unmeasured_rows(theta, stderr)
    named = {e.path for e, b in zip(table.entries, blind, strict=True) if b}
    assert named == {"phases.0.cell.a", "phases.0.cell.b", "phases.0.cell.c"}

    esd = table.stderr_physical(theta, stderr, np.eye(3))
    assert not (named & set(esd))
    assert "phases.0.scale" in esd


def test_nothing_changes_when_every_column_measured_something():
    """The mask is inert on an ordinary fit, and inert exactly.

    Both branches of ``stderr_physical`` — with and without a correlation
    matrix — go through the same construction now, so this also pins that the
    refactor did not move the uncorrelated answer.
    """
    table = _table()
    theta = table.x0()
    stderr = np.array([1e-5, 1e-7, 1e-6])

    assert not table.unmeasured_free(theta, stderr).any()
    assert not table.unmeasured_rows(theta, stderr).any()

    diag_only = table.stderr_physical(theta, stderr, None)
    correlated = table.stderr_physical(theta, stderr, np.eye(3))
    assert diag_only.keys() == correlated.keys()
    for path, value in diag_only.items():
        assert correlated[path] == pytest.approx(value, rel=1e-12)
