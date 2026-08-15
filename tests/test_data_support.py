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
from rietx.background.diagnostics import sampling_steps_per_fwhm
from rietx.model.forward import compile_model
from rietx.optimize.statistics import (
    STRUCTURAL_PARAMETER_GLOB,
    count_unique_reflections,
    effective_observations,
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


def _arrays(pattern: PatternData):
    """``(2θ, y, σ)`` — what :func:`sampling_steps_per_fwhm` takes."""
    return pattern.tt(), pattern.y(), pattern.sig()


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
# the effective count — Altomare et al. (1995)
# --------------------------------------------------------------------------

def test_a_coincident_pair_is_one_effective_observation():
    """Altomare's Fig. 1, on a cubic cell that has the pair for real.

    Every LaB6 reflection here is isolated except the exact coincidences, so
    M_ind must come out at the raw count minus one per coincident pair — an
    integer, and the arithmetic anchor for everything below.
    """
    structure, instrument = _lab6()
    model, values = _compiled(structure, instrument, np.arange(3.0, 26.0, 0.005))
    pos = np.sort(_tick_positions(model, values))
    pos = pos[pos <= model.tt[-1]]
    n_extra = int(np.count_nonzero(np.diff(pos) < 1e-9))
    assert n_extra >= 2                       # (300)/(221), (411)/(330), …

    raw = count_unique_reflections(model, values)
    assert effective_observations(model, values) == pytest.approx(
        raw - n_extra, abs=1e-9)


def test_overlap_drives_the_effective_count_down_monotonically():
    """A severely overlapped pattern's effective count sits well below its raw
    one, and nothing else moved: same cell, same range, same reflections.

    Lorentzian size broadening is the lever because it widens the peaks without
    touching their positions or the reflection list, so M_ind is the only thing
    in the table that can move.
    """
    structure, instrument = _lab6(radiation="CuKa")
    tt = np.arange(15.0, 140.0, 0.01)
    got = []
    for lor_size in (0.0, 2.0, 5.0, 15.0):
        s, ins = _lab6(radiation="CuKa")
        s.phases[0].lor_size.value = lor_size
        model, values = _compiled(s, ins, tt)
        raw = count_unique_reflections(model, values)
        got.append((raw, effective_observations(model, values)))

    raws = {r for r, _ in got}
    assert len(raws) == 1                     # the raw count cannot see overlap
    eff = [e for _, e in got]
    assert eff == sorted(eff, reverse=True)   # monotone in the broadening
    assert eff[0] / raws.pop() > 0.8          # sharp: nearly every line counts
    assert eff[-1] < 0.2 * eff[0]             # merged: the pattern is one hump
    assert structure is not None


def test_the_effective_count_never_exceeds_the_raw_one():
    """M_ind ≤ M by construction — every contribution is a fraction of 1."""
    for lor_size in (0.0, 1.0, 6.0):
        structure, instrument = _lab6(radiation="CuKa")
        structure.phases[0].lor_size.value = lor_size
        model, values = _compiled(structure, instrument,
                                  np.arange(15.0, 140.0, 0.01))
        raw = count_unique_reflections(model, values)
        eff = effective_observations(model, values)
        assert 0.0 < eff <= raw + 1e-9


def test_an_excluded_region_removes_effective_observations_too():
    """The integral runs over fitted channels, so an exclusion costs both
    counts — and the effective one cannot fall by more than the raw one."""
    structure, instrument = _lab6()
    tt = np.arange(3.0, 26.0, 0.005)
    model, values = _compiled(structure, instrument, tt)
    ticks = np.sort(_tick_positions(model, values))
    lo, hi = float(ticks[3] - 0.1), float(ticks[5] + 0.1)

    cut, cut_values = _compiled(structure, instrument, tt, excluded=[(lo, hi)])
    assert (count_unique_reflections(cut, cut_values)
            == count_unique_reflections(model, values) - 3)
    assert (effective_observations(cut, cut_values)
            == pytest.approx(effective_observations(model, values) - 3, abs=1e-9))


def test_no_reflection_measured_gives_none_not_zero():
    """Nothing to estimate says ``None``, never 0.0.

    Zero effective observations is a claim about a pattern; no measured
    reflection is the absence of one, and the two must not arrive as the same
    number.  Driven through the census directly because a fit range holding no
    reflection at all does not reach here — ``compile_model`` raises on the
    empty reflection list first, one rank up and outside this WP.
    """
    from rietx.optimize.statistics import _effective_from_census

    structure, instrument = _lab6()
    model, _values = _compiled(structure, instrument,
                               np.arange(3.0, 26.0, 0.005))
    assert _effective_from_census(model, []) is None


# --------------------------------------------------------------------------
# steps per FWHM — McCusker §2
# --------------------------------------------------------------------------

def _sampled(step: float, w: float, *, seed: int = 7) -> PatternData:
    """A noisy LaB6 pattern at a chosen step size and Gaussian width, so the
    steps-per-FWHM answer is known before it is measured."""
    structure, instrument = _lab6()
    instrument.profile.w.value = w
    tt = np.arange(3.0, 24.0, step)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    return PatternData(two_theta=model.tt.tolist(),
                       intensity=rng.poisson(np.maximum(y, 1.0))
                       .astype(float).tolist())


@pytest.mark.parametrize(("step", "w"), [
    (0.005, 2.5e-4),    # 3.2 nominal steps per FWHM — undersampled
    (0.002, 2.5e-4),    # 7.9 — inside the band
    (0.005, 4.0e-3),    # 12.6 — oversampled
    (0.002, 4.0e-3),    # 31.6 — heavily oversampled
])
def test_steps_per_fwhm_tracks_the_step_size_it_was_collected_at(step, w):
    """The measurement is checked against a width that was *set*, not fitted.

    √W is the Gaussian FWHM the pattern was generated with, so √W/step is the
    nominal answer; the measured one runs a few per cent high because the
    instrument's Lorentzian X and Y broaden the peak beyond the Gaussian part.
    """
    got, n = sampling_steps_per_fwhm(*_arrays(_sampled(step, w)))
    nominal = np.sqrt(w) / step
    assert n >= 10
    assert nominal <= got <= 1.1 * nominal


def test_the_prominence_floor_is_a_floor_and_not_a_tuning():
    """5σ and 20σ must give the same answer, or the number is fitted to its
    own threshold rather than measured (the guard on the guard)."""
    from rietx.background import diagnostics as diag

    pattern = _sampled(0.005, 2.5e-4)
    at5, n5 = sampling_steps_per_fwhm(*_arrays(pattern))
    old = diag.SAMPLING_PROMINENCE_SIGMA
    try:
        diag.SAMPLING_PROMINENCE_SIGMA = 20.0
        at20, n20 = sampling_steps_per_fwhm(*_arrays(pattern))
    finally:
        diag.SAMPLING_PROMINENCE_SIGMA = old
    assert (at20, n20) == (at5, n5)


def test_without_the_prominence_floor_a_strong_peak_reads_as_undersampled():
    """The measured failure the floor exists for: noise on a 10⁵-count peak's
    own top puts several 5σ maxima across it, and the median width collapses
    below one step — the *opposite* answer on a pattern that is merely noisy."""
    from scipy.signal import find_peaks, peak_widths

    from rietx.background.diagnostics import background_envelope

    pattern = _sampled(0.005, 4.0e-3)     # 12.6 nominal: comfortably sampled
    tt, y, sigma = _arrays(pattern)
    net = y - background_envelope(tt, y)
    z = np.where(net > 0, net, 0.0) / sigma
    bare, _ = find_peaks(z, height=5.0, distance=3)
    kept, _ = find_peaks(z, height=5.0, distance=3, prominence=5.0)
    assert len(bare) > len(kept)

    measured, _ = sampling_steps_per_fwhm(tt, y, sigma)
    unfiltered = float(np.median(
        peak_widths(np.maximum(net, 0.0), bare, rel_height=0.5)[0]))
    assert unfiltered < measured
    assert measured > 10.0


def test_diagnose_reports_the_same_number_as_the_function():
    """One authority: ``PatternDiagnostics.steps_per_fwhm`` is the shared
    measurement, not a second one taken on the same pattern."""
    from rietx.background.diagnostics import diagnose

    pattern = _sampled(0.002, 2.5e-4)
    got = diagnose(pattern)
    expected, n = sampling_steps_per_fwhm(*_arrays(pattern))
    assert got.steps_per_fwhm == expected
    assert got.n_peaks_measured == n


def test_a_featureless_pattern_measures_nothing_and_says_so():
    """No resolved peak means no answer, reported as ``None`` rather than as a
    zero that would read as catastrophic undersampling."""
    tt = np.arange(5.0, 60.0, 0.02)
    rng = np.random.default_rng(3)
    flat = PatternData(two_theta=tt.tolist(),
                       intensity=rng.poisson(np.full(tt.shape, 200.0))
                       .astype(float).tolist())
    got, n = sampling_steps_per_fwhm(*_arrays(flat))
    assert got is None and n == 0


# --------------------------------------------------------------------------
# the two diagnostic codes
# --------------------------------------------------------------------------

def test_undersampling_is_flagged_and_good_sampling_is_not():
    """``PATTERN_UNDERSAMPLED`` fires below five steps and stays silent above
    it, including well above ten — the band's upper end costs beam time, not
    validity, so it is reported and never flagged."""
    structure, instrument = _lab6()
    ref = Refinement(structure, instrument, history=False)
    coarse = ref.fit(_sampled(0.005, 2.5e-4), plan="mccusker_default")
    _save(coarse, "data_support_undersampled.png")

    structure, instrument = _lab6()
    fine = Refinement(structure, instrument, history=False).fit(
        _sampled(0.002, 4.0e-3), plan="mccusker_default")
    _save(fine, "data_support_oversampled.png")

    assert "PATTERN_UNDERSAMPLED" in {d.code for d in coarse.diagnostics}
    assert "PATTERN_UNDERSAMPLED" not in {d.code for d in fine.diagnostics}


def test_the_ratio_diagnostic_grades_against_the_papers_two_part_band():
    """``DATA_SUPPORT_LOW`` is a warning below three, information between
    three and five, and absent above — "at least three and preferably five",
    read off the *effective* ratio because that is the one the band is about.
    """
    from rietx.optimize.statistics import OBS_PER_PARAMETER_MIN, OBS_PER_PARAMETER_PREFERRED
    from rietx.refine import _data_support_diagnostics
    from rietx.schemas.results import DataSupport

    structure, instrument = _lab6()
    model, _values = _compiled(structure, instrument,
                               np.arange(3.0, 26.0, 0.005))
    seen = {}
    for ratio in (1.5, 4.0, 8.0):
        support = DataSupport(
            n_unique_reflections=20, n_effective_observations=ratio * 4,
            n_structural_parameters=4, observations_per_parameter=5.0,
            effective_observations_per_parameter=ratio)
        found = [d for d in _data_support_diagnostics(support, model)
                 if d.code == "DATA_SUPPORT_LOW"]
        seen[ratio] = found[0].level if found else None
    assert seen == {1.5: "warning", 4.0: "info", 8.0: None}
    assert OBS_PER_PARAMETER_MIN == 3.0
    assert OBS_PER_PARAMETER_PREFERRED == 5.0


def test_neither_code_gates_anything():
    """Both are evidence: the fit that raised them converged, kept its
    parameters, and carries the numbers on the result either way."""
    structure, instrument = _lab6()
    result = Refinement(structure, instrument, history=False).fit(
        _sampled(0.005, 2.5e-4), plan="mccusker_structural")

    assert result.status == "converged"
    assert "PATTERN_UNDERSAMPLED" in {d.code for d in result.diagnostics}
    assert result.data_support is not None
    assert result.data_support.n_effective_observations > 0
    assert result.statistics.rwp < 0.5


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
