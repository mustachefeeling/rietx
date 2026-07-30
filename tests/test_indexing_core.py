"""WP-1020 — the Q-space core: the quadratic form, the subspaces, the FoM panel.

Three of these tests are the WP's own acceptance criteria and are written to fail
loudly rather than drift:

* the **derived** metric-subspace dimensions must equal the cell degrees of
  freedom ``params.vector`` has tabulated since v0.1 — the derivation has to
  reproduce the tabulation, or one of the two is wrong;
* recovery of (A..F) from true assignments must be **exact** (1e-10), which is
  the linearity claim the whole design rests on, checked rather than asserted;
* a **paired** figure-of-merit test: M₂₀ is invariant under a unimodular setting
  change, and F_N is explicitly *not* invariant under a zero shift.  The second
  half turns a documented blind spot into a tested one, which is the only way a
  blind spot stays true.
"""

from __future__ import annotations

import numpy as np
import pytest

from pxrdref.crystallography.lattice import cell_volume
from pxrdref.crystallography.symmetry import generate_reflections
from pxrdref.indexing.fom import (
    FOM_N,
    borda_scores,
    f_n,
    fom_panel,
    fom_panel_disagrees,
    indexed_fraction,
    lattice_group,
    m20,
    match_lines,
    predicted_lines,
    predicted_seen_fraction,
)
from pxrdref.indexing.qspace import (
    af_from_cell,
    cell_esds,
    cell_from_af,
    cell_jacobian,
    design_matrix,
    metric_basis,
    refine_candidate,
    sigma_effective,
)
from pxrdref.params.vector import _CELL_TIES, _FIXED_ANGLES
from pxrdref.schemas.indexing import (
    METRIC_DOF,
    FigureOfMerit,
    q_esd_of_two_theta,
    q_of_two_theta,
)

LAM = 1.5405929
CELLS = {
    "cubic": ("P m -3 m", (4.1566, 4.1566, 4.1566, 90.0, 90.0, 90.0)),
    "tetragonal": ("P 4/m m m", (3.7842, 3.7842, 9.5146, 90.0, 90.0, 90.0)),
    "hexagonal": ("P 6/m m m", (9.4166, 9.4166, 6.8745, 90.0, 90.0, 120.0)),
    "trigonal": ("P -3 m 1", (4.7591, 4.7591, 12.9894, 90.0, 90.0, 120.0)),
    "orthorhombic": ("P m m m", (7.0, 8.0, 9.0, 90.0, 90.0, 90.0)),
    "monoclinic": ("P 1 2/m 1", (8.875, 16.408, 7.137, 90.0, 93.84, 90.0)),
    "triclinic": ("P -1", (7.0, 8.0, 9.0, 85.0, 95.0, 100.0)),
}


def _lines(system: str, two_theta_max: float = 90.0):
    """(hkl, Q, 2θ) of a known cell — the assignment an engine would produce."""
    sg, cell = CELLS[system]
    refl = generate_reflections(sg, cell, LAM, two_theta_max)
    q = 1.0 / np.asarray(refl.d) ** 2
    order = np.argsort(q)
    q = q[order]
    tt = np.degrees(2.0 * np.arcsin(LAM * np.sqrt(q) / 2.0))
    return np.asarray(refl.hkl)[order], q, tt, cell


# ----------------------------------------------------------------------
# The quadratic form and its subspaces
# ----------------------------------------------------------------------
def test_metric_subspace_dimensions_match_the_tabulated_cell_dof():
    """The derived subspace must reproduce ``params.vector``'s cell ties.

    Two independent statements of the same crystallography: the refinement side
    ties b←a and fixes angles from a table, while indexing derives the invariant
    metric directions from the operators by exact rational algebra.  If they ever
    disagree, one of them is wrong — and the derivation is the one that stays
    right in a non-standard setting.
    """
    for system, dof in METRIC_DOF.items():
        tabulated = 6 - len(_CELL_TIES[system]) - len(_FIXED_ANGLES[system])
        derived = metric_basis(system).shape[0]
        assert derived == tabulated == dof, (
            f"{system}: derived {derived}, tabulated {tabulated}, "
            f"METRIC_DOF {dof}")


def test_metric_basis_is_integer_and_spans_the_true_cell():
    """The basis is an exact integer nullspace, and the true metric lies in it."""
    for system, (_sg, cell) in CELLS.items():
        basis = metric_basis(system)
        assert np.allclose(basis, np.round(basis))
        af = af_from_cell(cell)
        # projection onto the subspace must return the vector itself
        coef, *_ = np.linalg.lstsq(basis.T, af, rcond=None)
        assert np.allclose(basis.T @ coef, af, atol=1e-12), system


def test_design_matrix_reproduces_inv_d_squared():
    """``M @ (A..F)`` is the same number ``inv_d_squared`` computes."""
    for system in CELLS:
        hkl, q, _tt, cell = _lines(system)
        got = design_matrix(hkl) @ af_from_cell(cell)
        assert np.allclose(got, q, rtol=1e-12)


def test_exact_linear_recovery_of_the_metric():
    """**The linearity claim, checked.**  With true assignments and no noise the
    solve is exact — 1e-10 on the cell — in every system."""
    for system in CELLS:
        hkl, q, tt, cell = _lines(system)
        fit = refine_candidate(q, np.full_like(q, 1e-6), hkl, system=system)
        assert np.allclose(fit.cell, cell, atol=1e-10), (
            f"{system}: {fit.cell} against {cell}")
        assert fit.chi2_red < 1e-12
        assert fit.volume == pytest.approx(float(cell_volume(*cell)), rel=1e-12)


def test_cell_jacobian_is_analytic_and_agrees_with_finite_differences():
    """∂cell/∂(A..F) by hand against central differences — the delta-method
    covariance is used to *decide* cell equality, so its accuracy is part of a
    decision rather than of a report."""
    for system, (_sg, cell) in CELLS.items():
        af = af_from_cell(cell)
        ana = cell_jacobian(af)
        fd = np.zeros((6, 6))
        for p in range(6):
            h = 1e-8 * max(abs(af[p]), 1e-3)
            lo, hi = af.copy(), af.copy()
            lo[p] -= h
            hi[p] += h
            fd[:, p] = (np.array(cell_from_af(hi))
                        - np.array(cell_from_af(lo))) / (2.0 * h)
        scale = np.maximum(np.abs(fd), 1e-6)
        assert np.max(np.abs(ana - fd) / scale) < 1e-4, system


def test_non_positive_definite_metric_raises():
    """A metric with a non-positive eigenvalue is not a lattice, and an engine
    that has wandered there is told rather than handed a NaN cell."""
    with pytest.raises(ValueError, match="not a lattice"):
        cell_from_af(np.array([1.0, -1.0, 1.0, 0.0, 0.0, 0.0]))


def test_cell_esds_scale_with_the_input_covariance():
    hkl, q, _tt, cell = _lines("orthorhombic")
    af = af_from_cell(cell)
    cov = np.diag(np.full(6, 1e-10))
    esd_a = cell_esds(af, cov)
    esd_b = cell_esds(af, 4.0 * cov)
    assert np.allclose(esd_b, 2.0 * esd_a, rtol=1e-12)
    assert np.all(esd_a[:3] > 0)


def test_sigma_effective_adds_the_systematic_in_quadrature():
    hkl, q, tt, cell = _lines("cubic")
    esd = q_esd_of_two_theta(tt, np.full_like(tt, 0.002), LAM)
    plain = sigma_effective(esd, tt, LAM, 0.0)
    floored = sigma_effective(esd, tt, LAM, 0.002)
    assert np.allclose(plain, esd)
    assert np.allclose(floored, np.sqrt(2.0) * esd, rtol=1e-12)


# ----------------------------------------------------------------------
# The shift column
# ----------------------------------------------------------------------
@pytest.mark.parametrize("template,amplitude", [
    ("constant", 0.05),
    ("cos_theta", 0.08),
    ("sin_2theta", 0.04),
])
def test_shift_column_recovers_an_injected_aberration(template, amplitude):
    """A candidate refined with the wrong positions gets the *wrong cell*; with
    the shift column it gets both back.

    The size of the effect is the point: 0.05-0.08° is small next to a FWHM and
    large next to σ(2θ), so the cell moves by far more than its esd if the shift
    is ignored.  That is why WP-1019's template choice is carried into the
    candidate refinement rather than left as a report field.
    """
    from pxrdref.indexing.quality import shift_template_basis

    hkl, q, tt, cell = _lines("monoclinic", two_theta_max=110.0)
    shifted = tt + amplitude * shift_template_basis(tt)[template]
    q_shift = q_of_two_theta(shifted, LAM)
    esd = q_esd_of_two_theta(shifted, np.full_like(shifted, 0.002), LAM)

    naive = refine_candidate(q_shift, esd, hkl, system="monoclinic")
    assert np.max(np.abs(np.array(naive.cell[:3]) - np.array(cell[:3]))) > 1e-3

    fixed = refine_candidate(q_shift, esd, hkl, system="monoclinic",
                             two_theta=shifted, wavelength=LAM,
                             shift_template=template)
    assert fixed.shift_coefficient == pytest.approx(amplitude, rel=2e-3)
    assert np.allclose(fixed.cell, cell, atol=2e-5)
    assert fixed.chi2_red < naive.chi2_red
    assert fixed.shift_esd > 0.0


def test_underdetermined_system_raises_rather_than_returning_a_cell():
    hkl, q, _tt, _cell = _lines("triclinic")
    with pytest.raises(ValueError, match="cannot determine"):
        refine_candidate(q[:4], np.full(4, 1e-4), hkl[:4], system="triclinic")


# ----------------------------------------------------------------------
# Figures of merit
# ----------------------------------------------------------------------
def _panel_inputs(system: str = "cubic", two_theta_max: float = 90.0,
                  esd_deg: float = 0.005):
    hkl, q, tt, cell = _lines(system, two_theta_max)
    esd_tt = np.full_like(tt, esd_deg)
    return q, q_esd_of_two_theta(tt, esd_tt, LAM), tt, esd_tt, cell


def test_m20_is_finite_and_large_for_a_perfect_cell():
    """The precision floor, and why it is not an epsilon.

    ⟨ΔQ⟩ → 0 on a cell that fits within fp noise, so an unfloored M₂₀ is
    infinite and a zero-guarded one is **zero** — which ranks a perfect cell
    last.  Flooring at the median σ(Q) gives a large finite value whose size is
    set by the data's own precision.
    """
    q, q_esd, tt, esd_tt, cell = _panel_inputs()
    _hkl, q_pred = predicted_lines(cell, "cubic", "P", LAM, 90.0)
    got = m20(q, q_esd, q_pred)
    assert np.isfinite(got.value) and got.value > 100.0
    assert got.mean_discrepancy < float(np.median(q_esd))
    # ten times worse data, ten times smaller M20 — the floor is the precision
    coarse = m20(q, 10.0 * q_esd, q_pred)
    assert coarse.value == pytest.approx(got.value / 10.0, rel=1e-9)


def test_m20_is_invariant_under_a_unimodular_setting_change():
    """A setting change is not a different lattice, so no figure of merit may
    move.  M₂₀ lives in Q and the Q set is identical, so this is exact."""
    from pxrdref.indexing.ambiguity import transform_cell

    q, q_esd, tt, esd_tt, cell = _panel_inputs("triclinic")
    t = np.array([[1, 1, 0], [0, 1, 0], [0, 0, 1]], dtype=np.int64)
    assert round(float(np.linalg.det(t))) == 1
    other = transform_cell(cell, t)

    _h1, q_a = predicted_lines(cell, "triclinic", "P", LAM, 90.0)
    _h2, q_b = predicted_lines(other, "triclinic", "P", LAM, 90.0)
    a, b = m20(q, q_esd, q_a), m20(q, q_esd, q_b)
    assert a.value == pytest.approx(b.value, rel=1e-9)
    assert a.n_possible == b.n_possible


def test_f_n_is_not_invariant_under_a_zero_shift():
    """The documented blind spot, made a test.

    F_N lives in 2θ, so shifting every observed position by a constant — exactly
    what an unmodelled zero-point error does — changes it, while a Q-space figure
    computed on the same lattice would report the mismatch.  A blind spot that is
    only documented is one refactor from being false.
    """
    q, q_esd, tt, esd_tt, cell = _panel_inputs()
    _hkl, q_pred = predicted_lines(cell, "cubic", "P", LAM, 90.0)
    tt_pred = np.degrees(2.0 * np.arcsin(LAM * np.sqrt(q_pred) / 2.0))

    honest = f_n(tt, esd_tt, tt_pred)
    shifted = f_n(tt + 0.05, esd_tt, tt_pred)
    assert shifted.value < 0.5 * honest.value
    assert shifted.mean_discrepancy > 10.0 * max(honest.mean_discrepancy, 1e-12)


def test_a_big_cell_indexes_everything_and_the_panel_says_so():
    """The measured §D failure, reproduced: ``indexed_fraction`` alone ranks a
    wrong cell **first**, and the panel with the reverse direction in it does not.

    The impostor here is a large triclinic cell plus three impurity lines the
    truth cannot index — which is the shape of the real case (a 390-line phase
    indexing 83.7 % of the observed intensity against the truth's 79.2 %).
    """
    # σ(2θ) = 0.02° — PeakList.from_positions' *assumed* value, i.e. exactly the
    # published-peak-list case §D was measured on.  The window a coarse σ opens is
    # what lets a large cell have a line near everything.
    q, q_esd, tt, esd_tt, cell = _panel_inputs(esd_deg=0.02)
    impurity_q = np.array([0.11, 0.27, 0.53])
    q_all = np.sort(np.concatenate([q, impurity_q]))
    esd_all = np.interp(q_all, q, q_esd)
    tt_all = np.degrees(2.0 * np.arcsin(LAM * np.sqrt(q_all) / 2.0))
    esd_tt_all = np.full_like(tt_all, 0.02)
    inten = np.linspace(100.0, 10.0, len(q_all))

    impostor = (12.4, 12.6, 13.1, 88.0, 92.0, 97.0)
    panels, indexed = [], []
    for candidate, system in ((cell, "cubic"), (impostor, "triclinic")):
        panels.append(fom_panel(q_all, esd_all, inten, tt_all, esd_tt_all,
                                candidate, system, "P", LAM))
        _h, q_pred = predicted_lines(candidate, system, "P", LAM,
                                     float(tt_all.max()))
        indexed.append(indexed_fraction(q_all, esd_all, q_pred).value)
        seen = predicted_seen_fraction(q_all, esd_all, q_pred).value
        print(f"{system}: indexed {indexed[-1]:.3f} seen {seen:.4f}")

    # the forward direction alone prefers the impostor …
    assert indexed[1] >= indexed[0]
    # … and the panel does not
    scores = borda_scores(panels)
    assert scores[0] > scores[1]
    assert fom_panel_disagrees(panels)


def test_every_figure_of_merit_carries_its_blind_spot():
    q, q_esd, tt, esd_tt, cell = _panel_inputs()
    panel = fom_panel(q, q_esd, np.ones_like(q), tt, esd_tt, cell, "cubic", "P",
                      LAM)
    assert len(panel) == 5
    for f in panel:
        assert isinstance(f, FigureOfMerit)
        assert f.blind_spot, f.name
        assert f.k_sigma > 0
    round_tripped = [FigureOfMerit.model_validate_json(f.model_dump_json())
                     for f in panel]
    assert [f.blind_spot for f in round_tripped] == [f.blind_spot for f in panel]


def test_lattice_group_is_absence_free_and_carries_the_centring():
    assert lattice_group("cubic") == "P m -3 m"
    assert lattice_group("cubic", "F") == "F m -3 m"
    assert lattice_group("trigonal", "R") == "R -3 m"
    with pytest.raises(ValueError):
        lattice_group("rhombic")
    # a centred lattice allows fewer lines than its primitive namesake
    _h1, q_p = predicted_lines((5.4309,) * 3 + (90.0,) * 3, "cubic", "P", LAM, 90.0)
    _h2, q_f = predicted_lines((5.4309,) * 3 + (90.0,) * 3, "cubic", "F", LAM, 90.0)
    assert len(q_f) < len(q_p)


def test_match_lines_uses_each_lines_own_sigma():
    """Per-line σ, not one global window — the contract the whole peak list
    exists to establish."""
    q_obs = np.array([0.10, 0.20])
    q_pred = np.array([0.1005, 0.2005])
    tight = np.array([1e-5, 1e-5])
    loose = np.array([1e-5, 1e-3])
    idx_tight, _ = match_lines(q_obs, tight, q_pred)
    idx_loose, _ = match_lines(q_obs, loose, q_pred)
    assert idx_tight.tolist() == [-1, -1]
    assert idx_loose.tolist() == [-1, 1]


def test_fom_n_is_twenty_lines():
    """M₂₀ and F₂₀ are defined on twenty lines; a longer list must not silently
    change the figure's meaning."""
    q, q_esd, tt, esd_tt, cell = _panel_inputs("triclinic")
    assert len(q) > FOM_N
    _hkl, q_pred = predicted_lines(cell, "triclinic", "P", LAM, 90.0)
    assert m20(q, q_esd, q_pred).n_lines == FOM_N
    assert f_n(tt, esd_tt, tt).n_lines == FOM_N
