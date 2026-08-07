"""WP-1028 regressions: robustness on data and CIFs we did not author.

One section per WP item, and every test here failed before its fix.  The
defects were measured on external files (COD entries, ICSD exports, the
PyWPEM CASES data) and are reproduced as synthetic minimal cases so the
suite carries no third-party data; the measured stories live in the WP file.
"""

from __future__ import annotations

import numpy as np
import pytest

from pxrdref import Instrument, PatternData
from pxrdref.schemas.structure import Structure

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
    path.write_text(NACL_CIF.format(na=na, cl=cl))
    return str(path)


def test_normalize_cif_species_covers_both_wild_forms_and_only_them():
    from pxrdref.crystallography.cif import normalize_cif_species

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
    from pxrdref.model.forward import compile_model

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
# (b) generate_reflections refuses a petabyte grid before allocating it
# ----------------------------------------------------------------------


def test_a_collapsed_cell_is_refused_before_the_grid_is_allocated():
    # the real case allocated 2.35 PiB and killed the process; the guard has
    # to fire before np.meshgrid, so the test's only budget is the raise
    from pxrdref.crystallography.symmetry import generate_reflections

    with pytest.raises(ValueError, match="grid points") as err:
        generate_reflections("P 1", (56800.0, 56800.0, 72600.0,
                                     90.0, 90.0, 90.0),
                             wavelength=1.5406, two_theta_max=120.0)
    # the message names the cell and the likely cause, not just the size
    assert "56800" in str(err.value)
    assert "collapsed or mis-scaled" in str(err.value)


def test_the_grid_limit_clears_every_physical_cell():
    from pxrdref.crystallography.symmetry import MAX_HKL_GRID_POINTS, generate_reflections

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
    from pxrdref.model.forward import compile_model
    from pxrdref.params.vector import ParameterTable

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
    from pxrdref import Refinement
    from pxrdref.strategy.staged import Stage

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
    from pxrdref.refine import MODEL_FAR_FROM_DATA_RWP

    assert MODEL_FAR_FROM_DATA_RWP < 0.99999
    # and still far above an honestly bad Rietveld fit (0.2-0.5 measured)
    assert MODEL_FAR_FROM_DATA_RWP > 0.5


def test_a_fit_on_the_data_reports_neither_robustness_diagnostic(tmp_path):
    from pxrdref import Refinement
    from pxrdref.strategy.staged import Stage

    start, ins, pattern = _nacl_pattern(tmp_path)          # exact cell
    ref = Refinement(start, ins)
    result = ref.run_stage(pattern, Stage(name="scale",
                                          turn_on=["phases.*.scale"],
                                          max_iter=20))

    assert result.statistics.rwp < 0.01
    codes = {d.code for d in result.diagnostics}
    assert "MODEL_FAR_FROM_DATA" not in codes
    assert "STAGE_MAX_ITER" not in codes


def test_a_stage_that_stopped_on_its_budget_is_surfaced_as_a_diagnostic():
    # StageResult.status has always carried "max_iter"; what was missing is a
    # diagnostic, because the *result's* status is the last stage's and can
    # still read "converged"
    from pxrdref.refine import _max_iter_diagnostics
    from pxrdref.schemas.results import StageResult

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

