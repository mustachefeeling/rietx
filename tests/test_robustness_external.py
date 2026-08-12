"""WP-1028 regressions: robustness on data and CIFs we did not author.

One section per WP item, and every test here failed before its fix.  The
defects were measured on external files (COD entries, ICSD exports, the
PyWPEM CASES data) and are reproduced as synthetic minimal cases so the
suite carries no third-party data; the measured stories live in the WP file.
"""

from __future__ import annotations

from typing import get_args

import numpy as np
import pytest

from anatase import Instrument, PatternData
from anatase.schemas.structure import Structure

# ----------------------------------------------------------------------
# (a) species syntaxes that reject valid CIFs — at two lookups, not one
# ----------------------------------------------------------------------

NACL_CIF = """\
data_nacl
_symmetry_space_group_name_H-M 'F m -3 m'
_cell_length_a 5.6402
_cell_length_b 5.6402
_cell_length_c 5.6402
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Na1 {na} 0 0 0 1
Cl1 {cl} 0.5 0.5 0.5 1
"""


def _nacl_cif(tmp_path, na="Na", cl="Cl"):
    path = tmp_path / "nacl.cif"
    path.write_text(NACL_CIF.format(na=na, cl=cl), encoding="utf-8")
    return str(path)


def test_normalize_cif_species_covers_both_wild_forms_and_only_them():
    from anatase.crystallography.cif import normalize_cif_species

    label = "site label in the type-symbol column"
    sign = "sign-first charge"
    assert normalize_cif_species("O1") == ("O", label)
    assert normalize_cif_species("Cl1") == ("Cl", label)
    assert normalize_cif_species("CL1") == ("Cl", label)
    assert normalize_cif_species("O-2") == ("O2-", sign)
    assert normalize_cif_species("Ni+3") == ("Ni3+", sign)
    assert normalize_cif_species("Li+1") == ("Li1+", sign)
    # canonical forms are untouched — including the trailing-sign ion that
    # always read fine, and a bare element in any case the lookups handle
    assert normalize_cif_species("Cl1-") == ("Cl1-", None)
    assert normalize_cif_species("O2-") == ("O2-", None)
    assert normalize_cif_species("Na") == ("Na", None)
    # a symbol the table cannot help is never half-rewritten: it passes
    # through verbatim to fail with the lookup's own message
    assert normalize_cif_species("Wat") == ("Wat", None)
    assert normalize_cif_species("D1") == ("D1", None)
    assert normalize_cif_species("Xx1") == ("Xx1", None)


def test_site_label_type_symbols_normalise_at_read(tmp_path):
    diags = []
    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na1", cl="Cl1"),
                                   diagnostics=diags)
    assert [a.species for a in structure.phases[0].atoms] == ["Na", "Cl"]
    assert {d.code for d in diags} == {"CIF_SPECIES_NORMALISED"}
    assert all(d.level == "info" for d in diags)
    where = sorted(w for d in diags for w in d.where)
    assert where == ["phases.0.atoms.0.species", "phases.0.atoms.1.species"]


def test_sign_first_charges_normalise_keeping_the_ion(tmp_path):
    diags = []
    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na+1", cl="Cl-1"),
                                   diagnostics=diags)
    assert [a.species for a in structure.phases[0].atoms] == ["Na1+", "Cl1-"]
    assert len(diags) == 2
    assert all("sign-first charge" in d.message for d in diags)


def test_untouched_species_record_no_diagnostic(tmp_path):
    diags = []
    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na", cl="Cl1-"),
                                   diagnostics=diags)
    assert [a.species for a in structure.phases[0].atoms] == ["Na", "Cl1-"]
    assert diags == []


@pytest.mark.parametrize("dispersion_on", [True, False],
                         ids=["dispersion-on", "dispersion-none"])
def test_normalised_species_compile_under_both_dispersion_settings(
        tmp_path, dispersion_on):
    # the defect fired at the first stage compile, from *two* lookups —
    # resolve_dispersion with the block on, normalize_species either way —
    # so the fix is asserted at compile, under both settings
    from anatase.model.forward import compile_model

    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na+1", cl="Cl1"))
    structure.phases[0].scale.value = 5e-3
    ins = Instrument.bragg_brentano(radiation="CuKa")
    if not dispersion_on:
        ins.source.dispersion = None
    tt = np.arange(20.0, 60.0, 0.05)
    pattern = PatternData(two_theta=tt.tolist(),
                          intensity=np.zeros_like(tt).tolist())
    compile_model(structure, ins, pattern, mode="rietveld")


# ----------------------------------------------------------------------
# (j) a symmetry-fixed angle an external CIF reports is corrected and named,
#     where a reader has a diagnostics channel and ParameterTable does not
# ----------------------------------------------------------------------

ORTHO_CIF = """\
data_ortho
_symmetry_space_group_name_H-M 'P m m m'
_cell_length_a 5.0
_cell_length_b 6.0
_cell_length_c 7.0
_cell_angle_alpha 90
_cell_angle_beta {beta}
_cell_angle_gamma 90
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Na1 Na 0 0 0 1
"""


def _ortho_cif(tmp_path, beta):
    path = tmp_path / "ortho.cif"
    path.write_text(ORTHO_CIF.format(beta=beta), encoding="utf-8")
    return str(path)


def test_a_reported_refined_angle_is_corrected_and_named(tmp_path):
    # the realistic external case: an experimenter quoting a refined
    # beta = 90.002(3) under an orthorhombic symbol is reporting a
    # measurement, not making a mistake — and before this it raised at the
    # first parameters()/set_vary/stage compile rather than refining
    from anatase.params.vector import ParameterTable

    diags = []
    structure = Structure.from_cif(_ortho_cif(tmp_path, 90.002),
                                   diagnostics=diags)
    assert structure.phases[0].cell.beta.value == 90.0
    assert [d.code for d in diags] == ["CIF_CELL_ANGLE_CORRECTED"]
    assert diags[0].where == ["phases.0.cell.beta"]
    assert "90.002" in diags[0].message and "+0.002" in diags[0].message
    # and the correction is what lets the model reach a table at all
    ParameterTable(structure, Instrument.bragg_brentano(radiation="CuKa"))


def test_a_structural_disagreement_is_left_alone_and_still_raises(tmp_path):
    # a monoclinic beta under an orthorhombic symbol: the symbol and the angle
    # contradict each other, and which is wrong is not a reader's call
    from anatase.params.vector import ParameterTable

    diags = []
    structure = Structure.from_cif(_ortho_cif(tmp_path, 93.2), diagnostics=diags)
    assert structure.phases[0].cell.beta.value == pytest.approx(93.2)
    assert diags == []
    with pytest.raises(ValueError, match="fixes beta"):
        ParameterTable(structure, Instrument.bragg_brentano(radiation="CuKa"))


def test_an_exact_angle_is_neither_touched_nor_reported(tmp_path):
    diags = []
    structure = Structure.from_cif(_ortho_cif(tmp_path, 90.0), diagnostics=diags)
    assert structure.phases[0].cell.beta.value == 90.0
    assert diags == []


def test_the_correction_band_separates_a_report_from_a_mis_declaration():
    from anatase.crystallography.cif import CIF_ANGLE_CORRECT_MAX_DEG
    from anatase.crystallography.symmetry import SYMMETRY_ANGLE_TOL_DEG

    # wide enough to cover a refined-and-reported angle, and strictly above
    # the tolerance that decides whether there is anything to correct at all
    assert SYMMETRY_ANGLE_TOL_DEG < CIF_ANGLE_CORRECT_MAX_DEG
    # narrow enough that the 3.2° case WP-1036 found in the wild is excluded
    assert CIF_ANGLE_CORRECT_MAX_DEG < 3.2


# ----------------------------------------------------------------------
# (b) generate_reflections refuses a petabyte grid before allocating it
# ----------------------------------------------------------------------


def test_a_collapsed_cell_is_refused_before_the_grid_is_allocated():
    # the real case allocated 2.35 PiB and killed the process; the guard has
    # to fire before np.meshgrid, so the test's only budget is the raise
    from anatase.crystallography.symmetry import generate_reflections

    with pytest.raises(ValueError, match="grid points") as err:
        generate_reflections("P 1", (56800.0, 56800.0, 72600.0,
                                     90.0, 90.0, 90.0),
                             wavelength=1.5406, two_theta_max=120.0)
    # the message names the cell and the likely cause, not just the size
    assert "56800" in str(err.value)
    assert "collapsed or mis-scaled" in str(err.value)


def test_the_grid_limit_clears_every_physical_cell():
    from anatase.crystallography.symmetry import MAX_HKL_GRID_POINTS, generate_reflections

    # a 100 Å protein-scale cell at d_min ≈ 1 Å implies a 201³ grid — the
    # refusal must sit far above any physical powder problem, so pin the
    # limit against that arithmetic, and enumerate a small P1 cell for real
    assert 201 ** 3 < MAX_HKL_GRID_POINTS
    refl = generate_reflections("P 1", (25.0, 25.0, 25.0, 90.0, 90.0, 90.0),
                                wavelength=1.5406, two_theta_max=40.0)
    assert len(refl.hkl) > 0


# ----------------------------------------------------------------------
# (c) a fit that is nowhere near the data says so, instead of "converged"
# (d) a stage that stopped on its budget says so, instead of nothing
# ----------------------------------------------------------------------


def _nacl_pattern(tmp_path, *, cell_error=0.0):
    """A synthetic NaCl pattern, and a structure whose cell is off by a factor.

    ``cell_error=0.03`` reproduces §(c): a starting cell 3 % off puts every
    reflection outside the window it was compiled with.
    """
    from anatase.model.forward import compile_model
    from anatase.params.vector import ParameterTable

    truth = Structure.from_cif(_nacl_cif(tmp_path))
    truth.phases[0].scale.value = 20.0
    ins = Instrument.bragg_brentano(radiation="CuKa")
    ins.profile.w.value = 4e-3
    tt = np.arange(25.0, 75.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, blank, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0()))
    # counting noise, so the exact-cell case is a *fit* rather than an
    # identity — a zero residual makes several statistics degenerate
    y = np.random.default_rng(20281028).poisson(np.maximum(y, 1.0)).astype(float)
    pattern = PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    start = Structure.from_cif(_nacl_cif(tmp_path))
    start.phases[0].scale.value = 20.0
    for name in ("a", "b", "c"):
        p = getattr(start.phases[0].cell, name)
        p.value *= 1.0 + cell_error
    return start, ins, pattern


@pytest.mark.parametrize("max_iter, expect_status",
                         [(5, "max_iter"), (50, "converged")])
def test_a_fit_nowhere_near_the_data_is_reported_however_the_solver_exited(
        tmp_path, max_iter, expect_status):
    # the defect is the *converged* row: the refinement does not error, it
    # returns status="converged" and a batch caller believes it
    from anatase import Refinement
    from anatase.strategy.staged import Stage

    start, ins, pattern = _nacl_pattern(tmp_path, cell_error=0.03)
    ref = Refinement(start, ins)
    result = ref.run_stage(pattern, Stage(name="scale",
                                          turn_on=["phases.*.scale"],
                                          max_iter=max_iter))

    assert result.status == expect_status
    far = [d for d in result.diagnostics if d.code == "MODEL_FAR_FROM_DATA"]
    assert len(far) == 1
    assert far[0].level == "error"
    # the cause is *measured*, not asserted: with every reflection outside its
    # frozen window the calculated pattern is nearly all background
    assert "above-background intensity" in far[0].message
    assert "frozen" in far[0].suggestion


def test_the_bar_sits_below_the_zero_scale_attractor_not_above_it():
    # Rwp = 1 is exactly "no better than y_calc = 0", and driving the scale to
    # zero is the escape a windowed-out model converges to — measured 0.99999
    # on the reproduction above, so a threshold at 1.0 misses it by 1e-5
    from anatase.refine import MODEL_FAR_FROM_DATA_RWP

    assert MODEL_FAR_FROM_DATA_RWP < 0.99999
    # and still far above an honestly bad Rietveld fit (0.2-0.5 measured)
    assert MODEL_FAR_FROM_DATA_RWP > 0.5


def test_a_fit_on_the_data_reports_neither_robustness_diagnostic(tmp_path):
    from anatase import Refinement
    from anatase.strategy.staged import Stage

    start, ins, pattern = _nacl_pattern(tmp_path)          # exact cell
    ref = Refinement(start, ins)
    result = ref.run_stage(pattern, Stage(name="scale",
                                          turn_on=["phases.*.scale"],
                                          max_iter=20))

    assert result.statistics.rwp < 0.01
    codes = {d.code for d in result.diagnostics}
    assert "MODEL_FAR_FROM_DATA" not in codes
    assert "STAGE_MAX_ITER" not in codes


# ----------------------------------------------------------------------
# (e) March-Dollase r cannot underflow to zero and divide the residual
# ----------------------------------------------------------------------


def test_a_zero_lower_bound_lets_softplus_underflow_to_exactly_zero():
    # the mechanism, asserted where it lives: min=0.0 maps to an internal
    # bound of −∞, and log(1+e^u) is exactly 0.0 below u ≈ −745
    from anatase.params.transforms import internal_bounds, to_physical
    from anatase.schemas.structure import MARCH_R_MIN

    assert internal_bounds(0.0, np.inf, "softplus")[0] == -np.inf
    assert to_physical(-800.0, "softplus") == 0.0

    # a positive bound makes it finite, and the floor is then unreachable
    lo, _ = internal_bounds(MARCH_R_MIN, 6.0, "softplus")
    assert np.isfinite(lo)
    assert to_physical(lo, "softplus") == pytest.approx(MARCH_R_MIN)


def test_the_march_factor_is_what_a_zero_r_destroys():
    # A = r²cos²α + sin²α/r, term = A^(−3/2).  At r = 0 the bracket is inf off
    # the axis (→ term 0, silently wrong) and 0 *on* it (→ NaN), and every
    # derivative column is NaN — so the residual is garbage and nothing raises
    from anatase.model.preferred_orientation import march_term, march_term_and_dr

    cos2 = np.array([0.0, 0.5, 1.0])
    with np.errstate(divide="ignore", invalid="ignore"):
        term = march_term(cos2, 0.0)
        _, dterm = march_term_and_dr(cos2, 0.0)
    assert np.isnan(term[-1])          # scattering vector along the axis
    assert np.all(np.isnan(dterm))     # the whole Jacobian column


def test_a_zero_bound_is_repaired_even_when_it_comes_from_a_stored_document():
    # the broken bound outlives the default: a project or history node written
    # before the fix carries min=0.0 explicitly
    from anatase import Parameter
    from anatase.schemas.structure import MARCH_R_MAX, MARCH_R_MIN, PreferredOrientation

    po = PreferredOrientation(
        axis=(0, 0, 1),
        r=Parameter(value=0.8, vary=True, min=0.0, transform="softplus"))
    assert (po.r.min, po.r.max) == (MARCH_R_MIN, MARCH_R_MAX)
    assert po.r.value == pytest.approx(0.8)      # the value is not disturbed

    back = PreferredOrientation.model_validate_json(po.model_dump_json())
    assert back.r.min == MARCH_R_MIN

    # a positive bound a caller chose is left alone — it already maps to a
    # finite internal bound, so the underflow cannot happen there
    tight = PreferredOrientation(
        axis=(0, 0, 1),
        r=Parameter(value=0.8, min=0.5, max=2.0, transform="softplus"))
    assert (tight.r.min, tight.r.max) == (0.5, 2.0)


def test_the_march_bound_holds_through_the_parameter_table():
    from anatase import Instrument, Parameter
    from anatase.params.vector import ParameterTable
    from anatase.schemas.structure import MARCH_R_MIN, PreferredOrientation
    from tests.test_coordinates import make_rutile

    s = make_rutile()
    s.phases[0].preferred_orientation = PreferredOrientation(
        axis=(0, 0, 1),
        r=Parameter(value=1.0, vary=True, min=0.0, transform="softplus"))
    table = ParameterTable(s, Instrument.debye_scherrer(wavelength=1.5406))
    table.set_vary(["*"], False)
    table.set_vary(["phases.*.preferred_orientation.r"], True)

    lo, hi = table.bounds()
    k = table.free_paths.index("phases.0.preferred_orientation.r")
    # the solver sees a finite lower bound, so it can no longer reach a zero r
    assert np.isfinite(lo[k]) and np.isfinite(hi[k])
    x = table.x0().copy()
    x[k] = lo[k]
    assert table.decode(x)["phases.0.preferred_orientation.r"] == \
        pytest.approx(MARCH_R_MIN)


# ----------------------------------------------------------------------
# (i) the background envelope is extrapolated to the data edges, and a line
#     standing on extrapolated background says so
# ----------------------------------------------------------------------


def test_the_envelope_no_longer_clamps_flat_below_its_first_knot():
    # the mechanism: each knot's x is its window's *centre*, so the first sits
    # half a window inside the data and np.interp clamps flat below it.  On a
    # falling background that clamp is far under the truth and the whole first
    # half-window reads as positive net
    from anatase.background.diagnostics import background_envelope, envelope_measured_span

    tt = np.arange(5.0, 60.0, 0.02)
    truth = 1000.0 * np.exp(-(tt - 5.0) / 25.0)      # a falling background
    env = background_envelope(tt, truth)
    lo, _ = envelope_measured_span(tt)

    assert lo > tt[0] + 1.0              # the first knot really is inside
    # the envelope tracks the falling truth at the very first channel rather
    # than sitting at the first knot's (much lower) level
    assert env[0] == pytest.approx(truth[0], rel=0.05)
    assert env[0] > truth[np.searchsorted(tt, lo)]


def test_extrapolating_to_the_edges_only_extends():
    from anatase.background.diagnostics import _extrapolate_to_edges

    xs, ys = [2.0, 4.0, 6.0], [10.0, 8.0, 6.0]
    x2, y2 = _extrapolate_to_edges(list(xs), list(ys), 1.0, 7.0)
    assert x2 == [1.0, 2.0, 4.0, 6.0, 7.0]
    assert y2 == pytest.approx([11.0, 10.0, 8.0, 6.0, 5.0])

    # an edge already covered by a knot is left alone — a no-op, not a duplicate
    same_x, same_y = _extrapolate_to_edges(list(xs), list(ys), 2.0, 6.0)
    assert (same_x, same_y) == (xs, ys)


def test_a_line_on_extrapolated_background_is_flagged_and_still_usable():
    # report, don't refuse: the component is real intensity, just measured
    # against a background nobody observed, so the flag is deliberately not in
    # PEAK_UNUSABLE_FLAGS and is not a reuse of position_at_bound
    from anatase.schemas.indexing import PEAK_UNUSABLE_FLAGS, PeakFlag

    assert "background_extrapolated" in get_args(PeakFlag)
    assert "background_extrapolated" not in PEAK_UNUSABLE_FLAGS


def test_the_measured_span_matches_the_envelope_knots():
    # the two must not drift apart: the span is where interpolation happens,
    # which is exactly the first and last window centres
    from anatase.background.diagnostics import envelope_measured_span

    tt = np.arange(5.0, 150.0, 0.02)
    lo, hi = envelope_measured_span(tt)
    assert tt[0] < lo < tt[0] + 3.0
    assert tt[-1] - 3.0 < hi <= tt[-1]


# ----------------------------------------------------------------------
# (g) the Le Bail partition hands out the observed excess exactly once
# ----------------------------------------------------------------------


def _lebail_partition_ratio(n_phases, *, n_cycles=3):
    """Σ (calculated Bragg) / Σ (observed above background) after partitioning.

    A partition hands out each channel's excess exactly once, so this is 1.0
    at any phase count.  Before the fix the denominator was built per phase,
    so every phase claimed the whole excess in its own windows and the ratio
    settled above 1 wherever phases overlap.
    """
    from anatase.model.forward import compile_model
    from anatase.params.vector import ParameterTable
    from tests.test_qpa import _caf2_phase, make_lab6

    s = make_lab6()
    if n_phases > 1:
        s.phases.append(_caf2_phase())
    for phase in s.phases:
        phase.scale.value = 1.0
    ins = Instrument.bragg_brentano(radiation="CuKa")
    ins.profile.w.value = 5e-3
    tt = np.arange(20.0, 80.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    truth = compile_model(s, ins, blank, mode="rietveld")
    t0 = ParameterTable(s, ins)
    y = truth.evaluate(t0.decode(t0.x0()))

    pattern = PatternData(two_theta=tt.tolist(), intensity=y.tolist())
    model = compile_model(s, ins, pattern, mode="lebail")
    table = ParameterTable(s, ins)
    values = table.decode(table.x0())
    net = np.asarray(model.y_obs) - model.background(values)
    model.lebail_update(values, n_cycles=n_cycles)
    bragg = model.evaluate(values) - model.background(values)
    return float(bragg.sum() / net.sum())


def test_the_lebail_partition_is_a_partition_at_two_phases():
    # the defect: the denominator spanned one phase, so two overlapping phases
    # were each issued the same counts — measured 1.79x on this pattern
    assert _lebail_partition_ratio(2) == pytest.approx(1.0, abs=1e-6)


def test_the_single_phase_partition_is_unchanged():
    # one phase has nothing to overlap with, so the fix must be a no-op here
    assert _lebail_partition_ratio(1) == pytest.approx(1.0, abs=1e-6)


def test_an_unseeded_background_hands_the_pedestal_to_the_reflections():
    # (h): auto_background picks the knot spacing but starts every coefficient
    # at 0.0, and the first lebail_update runs before the background has ever
    # been fitted — so the partition is handed max(y_obs − 0, 0).  This is a
    # caller-protocol requirement (AGENT_PROTOCOL §2), pinned rather than
    # fixed: seeding every background would change where every fit starts
    from anatase.background.auto import auto_background
    from anatase.model.forward import compile_model
    from anatase.params.vector import ParameterTable
    from tests.test_qpa import make_lab6

    s = make_lab6()
    s.phases[0].scale.value = 1.0
    ins = Instrument.bragg_brentano(radiation="CuKa")
    ins.profile.w.value = 5e-3
    tt = np.arange(20.0, 80.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    t0 = ParameterTable(s, ins)
    peaks = compile_model(s, ins, blank, mode="rietveld").evaluate(t0.decode(t0.x0()))
    y = peaks + 5.0 * peaks.max()          # background 5× the strongest peak
    pattern = PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    ins.background = auto_background(pattern)
    assert all(c.value == 0.0 for c in ins.background.coefficients)

    model = compile_model(s, ins, pattern, mode="lebail")
    table = ParameterTable(s, ins)
    values = table.decode(table.x0())
    assert np.max(model.background(values)) == 0.0
    model.lebail_update(values, n_cycles=1)
    claimed = (model.evaluate(values) - model.background(values)).sum()
    assert claimed > 100.0 * peaks.sum()   # measured ~571×


def test_the_overcount_is_a_fixed_point_not_a_runaway():
    # worth pinning because the WP filed this as "inflate one another without
    # bound": the ratio is the same after 1 cycle and after 8, so what the
    # partition does is converge to the *wrong* answer, not diverge
    assert _lebail_partition_ratio(2, n_cycles=1) == \
        pytest.approx(_lebail_partition_ratio(2, n_cycles=8), abs=1e-6)


# ----------------------------------------------------------------------
# (f) QPA degrades to a diagnostic instead of raising from _build_result
# ----------------------------------------------------------------------


def _decoded(structure):
    from anatase.params.vector import ParameterTable

    table = ParameterTable(structure,
                           Instrument.debye_scherrer(wavelength=1.5406))
    return table.decode(table.x0())


def test_a_single_phase_is_a_hundred_percent_whatever_its_scale_did(tmp_path):
    # the computation should never have been on the critical path here: one
    # phase is 100 % by definition, and the scale is a brightness
    from anatase.optimize.qpa import compute_qpa

    structure = Structure.from_cif(_nacl_cif(tmp_path))
    structure.phases[0].scale.value = 0.0
    qpa = compute_qpa(structure, _decoded(structure))

    assert qpa is not None
    assert [r.weight_fraction for r in qpa.phases] == [1.0]
    # σ(W) stays absent: the fraction is a definition, not a measurement
    assert qpa.phases[0].weight_fraction_stderr is None


def test_a_dead_scale_in_a_mixture_returns_no_qpa_rather_than_raising(tmp_path):
    from anatase.optimize.qpa import compute_qpa

    structure = Structure.from_cif(_nacl_cif(tmp_path))
    structure.phases.append(
        Structure.from_cif(_nacl_cif(tmp_path)).phases[0].model_copy(deep=True))
    structure.phases[1].name = "phase_2"
    for phase in structure.phases:
        phase.scale.value = 0.0

    assert compute_qpa(structure, _decoded(structure)) is None


def test_the_missing_qpa_arrives_as_a_diagnostic_naming_the_dead_scales(
        tmp_path):
    from anatase.refine import _qpa_unavailable_diagnostics

    structure = Structure.from_cif(_nacl_cif(tmp_path))
    structure.phases.append(
        Structure.from_cif(_nacl_cif(tmp_path)).phases[0].model_copy(deep=True))
    structure.phases[1].name = "phase_2"
    values = _decoded(structure) | {"phases.0.scale": 0.0,
                                    "phases.1.scale": 0.0}

    diags = _qpa_unavailable_diagnostics(structure, values)
    assert [d.code for d in diags] == ["QPA_UNAVAILABLE"]
    assert diags[0].where == ["phases.0.scale", "phases.1.scale"]
    # a statement about the fit, not the specimen
    assert "not the specimen" in diags[0].suggestion


def test_a_stage_that_stopped_on_its_budget_is_surfaced_as_a_diagnostic():
    # StageResult.status has always carried "max_iter"; what was missing is a
    # diagnostic, because the *result's* status is the last stage's and can
    # still read "converged"
    from anatase.refine import _max_iter_diagnostics
    from anatase.schemas.results import StageResult

    def stage(name, status):
        return StageResult(name=name, status=status, n_iterations=1,
                           cost_initial=1.0, cost_final=1.0)

    assert _max_iter_diagnostics([stage("scale", "converged")]) == []

    one = _max_iter_diagnostics([stage("scale", "converged"),
                                 stage("profile", "max_iter")])
    assert [d.code for d in one] == ["STAGE_MAX_ITER"]
    assert "'profile'" in one[0].message and "budget rather" in one[0].message

    both = _max_iter_diagnostics([stage("scale", "max_iter"),
                                  stage("profile", "max_iter")])
    assert "'scale', 'profile'" in both[0].message
    assert "budgets rather" in both[0].message

