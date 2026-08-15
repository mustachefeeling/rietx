"""Does the data support it: the observation count and the parameter split.

McCusker, Von Dreele, Cox, Louër & Scardi (1999) §9 says the Rietveld
algorithm's N — the number of profile steps — is not the number of
observations, and that only the integrated intensities of individual
reflections are.  Everything here pins that count against something the test
can state independently of the implementation:

* the count is the reflection list **minus what the grid did not measure**, so
  a range end that walks past a reflection steps it down by exactly the number
  of reflections it passed, and an excluded region punched over a peak removes
  that peak whether or not it sits between ``tt_min`` and ``tt_max``;
* a **Kα doublet does not double it** — the ``RefinementResult.ticks`` lesson
  the other way up.  Ticks carry every emission line, and a census that
  counted them would report twice the observations a doublet pattern holds;
* the ratio is against **structural** free parameters, so a plan that refines
  only the profile and the background leaves it undefined rather than
  flattering.

The exact-arithmetic anchor is a **cubic** cell, where (300)/(221) and
(411)/(330) are distinct reflections at identical 2θ.  §9 calls that pair one
observation and the raw count calls it two: the gap this file measures is the
one the effective count exists to close.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.model.forward import compile_model
from rietx.optimize.statistics import (
    STRUCTURAL_PARAMETER_GLOB,
    count_unique_reflections,
    measured_mask,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_refine_synthetic import (
    TRUE_A,
    TRUE_BKG,
    TRUE_SCALE,
    TRUE_W,
    TRUE_ZERO,
    WAVELENGTH,
    synthesize,
)
from tests.test_schemas import make_lab6

OUT = Path(__file__).parent / "output"


def _save(result, name: str) -> None:
    """Write an obs/calc/diff PNG (skipped if matplotlib is unavailable)."""
    pytest.importorskip("matplotlib")
    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result

    plot_result(result, path=str(OUT / name))


def _lab6(*, radiation: str | None = None):
    """LaB6 at the synthetic truth.

    ``radiation=None`` is the single-line synchrotron instrument the synthetic
    pattern was generated with; a name selects the lab preset, so ``"CuKa"``
    and ``"CuKa1"`` differ in **nothing but the second emission line** — the
    only difference the doublet test is allowed to have.
    """
    s = make_lab6()
    for c in ("a", "b", "c"):
        getattr(s.phases[0].cell, c).value = TRUE_A
    s.phases[0].scale.value = TRUE_SCALE
    if radiation is None:
        ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
        ins.profile.w.value = TRUE_W
    else:
        ins = Instrument.bragg_brentano(radiation=radiation)
        ins.profile.w.value = 0.005
    ins.zero_shift.value = TRUE_ZERO
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in TRUE_BKG])
    return s, ins


def _compiled(structure, instrument, tt: np.ndarray, *,
              excluded: list[tuple[float, float]] | None = None):
    """A model compiled on a bare grid, plus the decoded values at rest."""
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.ones_like(tt).tolist(),
                        excluded_regions=excluded or [])
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    return model, table.decode(table.x0())


def _tick_positions(model, values, ip: int = 0) -> np.ndarray:
    """Every emission line's peak position for phase ``ip`` — what ``ticks``
    carries, and the number the census must *not* reproduce on a doublet."""
    rows = [np.asarray(pos, dtype=np.float64)
            for pos, _w1, _w2, _i in model.phase_peaks(ip, values)]
    return np.concatenate(rows)


# --------------------------------------------------------------------------
# measured_mask — the criterion, on its own
# --------------------------------------------------------------------------

def test_measured_mask_reads_half_a_fwhm_either_side():
    """Half the peak's own FWHM, at both edges, on a uniform grid."""
    tt = np.arange(10.0, 20.0, 0.01)      # last channel 19.99
    fwhm = np.full(6, 0.20)                # half-width criterion: 0.10°
    pos = np.array([15.0,          # dead centre
                    10.0, 9.92,    # at the low edge, and 0.08° = 0.4·FWHM out
                    19.99, 20.07,  # the same either side
                    9.80])         # 1.0·FWHM out — the top is off the grid
    got = measured_mask(tt, pos, fwhm)
    assert got.tolist() == [True, True, True, True, True, False]


def test_measured_mask_is_false_off_the_ewald_sphere():
    """A non-finite position is not measured, and is not an error either."""
    tt = np.arange(10.0, 20.0, 0.01)
    got = measured_mask(tt, np.array([np.nan, np.inf, 15.0]), np.full(3, 0.2))
    assert got.tolist() == [False, False, True]


# --------------------------------------------------------------------------
# the count
# --------------------------------------------------------------------------

def test_count_steps_down_as_the_range_end_passes_reflections():
    """The count is the reflection list minus what the grid did not measure.

    Walking the upper limit down past each reflection must drop the count by
    exactly the number of reflections passed — including the *pair* at one 2θ,
    which leaves together and takes two observations with it.
    """
    structure, instrument = _lab6()
    full = np.arange(3.0, 26.0, 0.005)
    model, values = _compiled(structure, instrument, full)
    ticks = np.sort(_tick_positions(model, values))
    inside = ticks <= full[-1]
    assert count_unique_reflections(model, values) == int(inside.sum())
    # the reflection left out sits well past the last channel, so this pins the
    # count rather than the knife edge of the half-FWHM allowance
    assert ticks[~inside].min() - full[-1] > 0.1

    # cut only where a gap of >0.1° opens, so half a FWHM (widths here are
    # ≪0.05°) cannot reach back over the limit and no coincident pair is split
    cuts = [k for k in range(2, len(ticks))
            if ticks[k] - ticks[k - 1] > 0.10]
    assert len(cuts) >= 4
    for cut_after in cuts[::max(len(cuts) // 4, 1)]:
        hi = float(ticks[cut_after - 1] + 0.05)
        m, v = _compiled(structure, instrument, np.arange(3.0, hi, 0.005))
        assert count_unique_reflections(m, v) == cut_after


def test_a_kalpha_doublet_does_not_double_the_count():
    """Ticks carry every emission line; observations do not (WP-1071).

    The Kα2 companion is the same reflection measured a second time.  A census
    reading ``ticks`` would report 2× here — which is the bug this asserts is
    absent, in the same shape as the Layer-0 impurity bug that made ``ticks``
    carry both lines in the first place.
    """
    single_s, single_i = _lab6(radiation="CuKa1")
    double_s, double_i = _lab6(radiation="CuKa")
    # the same lab instrument either way, so the only difference is the Kα2
    # line; the range starts below the first reflection and ends in open
    # pattern, so no reflection is half-in at an edge on either line set
    tt = np.arange(15.0, 90.0, 0.01)

    m1, v1 = _compiled(single_s, single_i, tt)
    m2, v2 = _compiled(double_s, double_i, tt)
    n1 = count_unique_reflections(m1, v1)
    n2 = count_unique_reflections(m2, v2)

    assert len(_tick_positions(m2, v2)) == 2 * len(_tick_positions(m1, v1))
    assert n2 == n1 > 0


def test_an_excluded_region_removes_the_reflections_under_it():
    """WP-1033's fitted-mask rule: an excluded peak was not observed.

    ``tt_min``/``tt_max`` cannot answer this — the removed reflections sit in
    the middle of the range — so a census reading the ends would count them.
    """
    structure, instrument = _lab6()
    tt = np.arange(3.0, 26.0, 0.005)
    model, values = _compiled(structure, instrument, tt)
    ticks = np.sort(_tick_positions(model, values))
    base = count_unique_reflections(model, values)

    lo, hi = ticks[3] - 0.1, ticks[5] + 0.1      # three reflections inside
    n_inside = int(((ticks >= lo) & (ticks <= hi)).sum())
    assert n_inside == 3

    cut, cut_values = _compiled(structure, instrument, tt,
                                excluded=[(float(lo), float(hi))])
    assert count_unique_reflections(cut, cut_values) == base - 3


def test_the_raw_count_over_counts_a_coincident_pair():
    """Two reflections at one 2θ are one observation and are counted as two.

    §9's own example, and the reason the effective count exists.  Stated as a
    test so the raw number is never mistaken for the paper's observation count.
    """
    structure, instrument = _lab6()
    model, values = _compiled(structure, instrument, np.arange(3.0, 26.0, 0.005))
    pos = np.sort(_tick_positions(model, values))
    coincident = int(np.count_nonzero(np.diff(pos) < 1e-9))
    assert coincident > 0
    assert count_unique_reflections(model, values) > len(pos) - coincident


# --------------------------------------------------------------------------
# the parameter split and the ratio, on a real fit
# --------------------------------------------------------------------------

def test_a_profile_plan_frees_no_structural_parameter():
    """The ratio is about structural parameters, so a profile/background plan
    leaves it ``None`` rather than reporting a flattering number against the
    eleven free parameters it did refine."""
    pattern = synthesize()
    structure, instrument = _lab6()
    result = Refinement(structure, instrument, history=False).fit(
        pattern, plan="mccusker_default")
    _save(result, "data_support_profile_plan.png")

    ds = result.data_support
    assert ds is not None
    assert ds.n_structural_parameters == 0
    assert ds.observations_per_parameter is None
    assert result.statistics.n_free_parameters > 0
    assert ds.n_unique_reflections < result.statistics.n_points


def test_the_ratio_counts_only_the_atom_paths():
    """Structural = ``phases.*.atoms.*``: coordinate DOFs, occupancies, Biso
    and ADP DOFs, and nothing the peak *positions* determine."""
    pattern = synthesize()
    structure, instrument = _lab6()
    ref = Refinement(structure, instrument, history=False)
    result = ref.fit(pattern, plan="mccusker_structural")
    _save(result, "data_support_structural_plan.png")

    ds = result.data_support
    assert ds is not None
    varied = [p.path for p in result.parameters if p.vary]
    atom_paths = [p for p in varied if ".atoms." in p]
    assert ds.n_structural_parameters == len(atom_paths) > 0
    assert ds.n_structural_parameters < result.statistics.n_free_parameters
    assert ds.observations_per_parameter == pytest.approx(
        ds.n_unique_reflections / ds.n_structural_parameters)

    import fnmatch
    assert all(fnmatch.fnmatch(p, STRUCTURAL_PARAMETER_GLOB) for p in atom_paths)
    assert not any(fnmatch.fnmatch(p, STRUCTURAL_PARAMETER_GLOB)
                   for p in varied if ".atoms." not in p)


def test_the_glob_reaches_every_kind_of_atom_parameter():
    """Coordinate DOF, occupancy, Biso and ADP DOF all match, and the cell,
    profile, background and scale do not — the split the docstring claims."""
    import fnmatch

    inside = ["phases.0.atoms.1.dof.0", "phases.0.atoms.1.occ",
              "phases.2.atoms.11.biso", "phases.0.atoms.0.adp.3"]
    outside = ["phases.0.cell.a", "phases.0.scale", "phases.0.extinction",
               "phases.0.preferred_orientation.r", "phases.0.lor_size",
               "phases.0.microstrain.dof.0", "instrument.profile.w",
               "instrument.background.c2", "instrument.zero_shift"]
    assert all(fnmatch.fnmatch(p, STRUCTURAL_PARAMETER_GLOB) for p in inside)
    assert not any(fnmatch.fnmatch(p, STRUCTURAL_PARAMETER_GLOB) for p in outside)
