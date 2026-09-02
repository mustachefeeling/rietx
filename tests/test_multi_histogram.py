"""Multi-histogram joint refinement (WP-0308).

Synthesize two LaB6 patterns of the *same* crystal at two wavelengths, refine
them jointly, and check the shared cell is recovered — better than either
pattern alone — with per-histogram Rwp reported separately.  A second test
corrupts one histogram and checks its own Rwp exposes it rather than the pooled
number masking it.
"""

import math
from pathlib import Path

import numpy as np
import pytest

from rietx import (
    Instrument,
    MultiHistogramRefinement,
    Parameter,
    PatternData,
    Refinement,
    refine_multi,
)
from rietx.model.forward import compile_model
from rietx.model.profiles.caglioti import (
    apparent_size_from_size_coefficient,
    microstrain_from_strain_coefficient,
    size_coefficient_for_size,
    strain_coefficient_for_microstrain,
)
from rietx.optimize.least_squares import (
    _longest_line_wavelength,
    _multi_closures,
)
from rietx.params.multi import (
    MultiParameterTable,
    SharingMap,
    _longest_wavelength,
    size_value_scales,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.strategy.staged import RefinementPlan, Stage
from tests.test_schemas import make_lab6

TRUE_A = 4.15660
OUT = Path(__file__).parent / "output"


def synthesize(wavelength: float, tt_lo: float, tt_hi: float, *,
               scale: float, zero: float, bkg: list[float],
               step: float = 0.005, seed: int = 7) -> PatternData:
    """A single-wavelength Debye-Scherrer LaB6 pattern with known parameters."""
    structure = make_lab6()
    for k in ("a", "b", "c"):
        getattr(structure.phases[0].cell, k).value = TRUE_A
    structure.phases[0].scale.value = scale
    ins = Instrument.debye_scherrer(wavelength=wavelength)
    ins.zero_shift.value = zero
    ins.profile.w.value = 3e-4
    ins.background = BackgroundChebyshev(coefficients=[Parameter(value=v) for v in bkg])

    tt = np.arange(tt_lo, tt_hi, step)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def perturbed_inputs():
    """Shared structure (cell off by ~0.1 %) + two fresh instruments to refine."""
    structure = make_lab6()
    for k in ("a", "b", "c"):
        getattr(structure.phases[0].cell, k).value = TRUE_A + 0.004
    ins0 = Instrument.debye_scherrer(wavelength=0.41390)
    ins0.background = BackgroundChebyshev.with_terms(3)
    ins1 = Instrument.debye_scherrer(wavelength=0.71070)
    ins1.background = BackgroundChebyshev.with_terms(3)
    return structure, [ins0, ins1]


@pytest.fixture(scope="module")
def two_patterns() -> list[PatternData]:
    return [
        synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                   bkg=[40.0, -6.0, 1.5], seed=1),
        synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                   bkg=[70.0, 5.0, -2.0], seed=2),
    ]


def _single_cell_esd(pattern: PatternData, wavelength: float) -> float:
    """esd(a) from refining one histogram alone (for the joint-vs-single check)."""
    structure = make_lab6()
    for k in ("a", "b", "c"):
        getattr(structure.phases[0].cell, k).value = TRUE_A + 0.004
    ins = Instrument.debye_scherrer(wavelength=wavelength)
    ins.background = BackgroundChebyshev.with_terms(3)
    res = Refinement(structure, ins, history=False).fit(pattern, plan="mccusker_default")
    return res.parameter("phases.0.cell.a").stderr


def test_joint_recovers_shared_cell(two_patterns):
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(two_patterns, plan="mccusker_default")

    assert result.status == "converged"
    assert len(result.histograms) == 2

    # per-histogram Rwp is reported separately and both fit well
    for h, hist in enumerate(result.histograms):
        assert hist.statistics.rwp < 0.12, f"hist {h} Rwp {hist.statistics.rwp}"
        OUT.mkdir(exist_ok=True)
        result.for_histogram(h).plot(OUT / f"multihist_joint_h{h}.png")

    # the shared cell is one refined number, recovered within esds
    a = ref.fitted_structures[0].phases[0].cell.a.value
    a_esd = result.parameter("phases.0.cell.a").stderr
    assert a_esd is not None and a_esd > 0
    assert a == pytest.approx(TRUE_A, abs=max(5 * a_esd, 5e-5))

    # …and every histogram's structure carries the *same* shared cell
    assert ref.fitted_structures[1].phases[0].cell.a.value == pytest.approx(a, rel=1e-12)
    # cubic tie still holds inside the shared structure
    assert ref.fitted_structures[0].phases[0].cell.b.value == pytest.approx(a, rel=1e-12)

    # joint esd beats either histogram alone (two measurements of one quantity)
    esd_single = [_single_cell_esd(two_patterns[0], 0.41390),
                  _single_cell_esd(two_patterns[1], 0.71070)]
    assert a_esd < min(esd_single), f"joint {a_esd} vs singles {esd_single}"

    # per-histogram scales are genuinely independent columns (different values)
    s0 = result.parameter("hist.0.phases.0.scale").value
    s1 = result.parameter("hist.1.phases.0.scale").value
    assert s0 != s1
    # provenance records the (unit) weighting explicitly
    assert "histogram_weights" in result.provenance.notes


def test_bad_histogram_shows_in_its_own_rwp(two_patterns):
    # corrupt the second pattern with a large unmodelled impurity peak: the
    # shared model can still fit histogram 0, so a pooled Rwp would understate
    # the damage — the per-histogram Rwp must expose it.
    good = two_patterns[0]
    tt = np.asarray(two_patterns[1].two_theta)
    y = np.asarray(two_patterns[1].intensity, dtype=float)
    y = y + 4000.0 * np.exp(-0.5 * ((tt - 20.0) / 0.05) ** 2)
    bad = PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    structure, instruments = perturbed_inputs()
    result = refine_multi([good, bad], structure, instruments, plan="mccusker_default")

    r_good = result.histograms[0].statistics.rwp
    r_bad = result.histograms[1].statistics.rwp
    assert r_good < 0.12
    assert r_bad > 2.0 * r_good, f"bad hist Rwp {r_bad} did not stand out from {r_good}"
    # the pooled number sits below the bad histogram's own — i.e. it *would*
    # have masked it without the per-histogram breakdown
    assert result.statistics.rwp < r_bad

    OUT.mkdir(exist_ok=True)
    for h in range(2):
        result.for_histogram(h).plot(OUT / f"multihist_bad_h{h}.png")


def test_a_narrow_declared_peak_is_flagged_per_histogram(two_patterns):
    """The joint path runs the width guard too (candidate 2).

    A disguised-Bragg background peak — free position/height/width with a fitted
    width at the resolution — declared on one histogram surfaces
    ``BACKGROUND_PEAK_TOO_NARROW`` in *that histogram's* own diagnostics, the
    channel a joint fit reports degeneracy evidence through.  Before this the
    joint path was the only one that never called ``check_background_peak_width``,
    so such a peak produced no warning anywhere.
    """
    from rietx.schemas.instrument import BackgroundPeak

    structure, instruments = perturbed_inputs()
    instruments[0].background_peaks = [BackgroundPeak(
        label="disguised",
        position=Parameter(value=12.0, unit="deg", vary=False),
        height=Parameter(value=150.0, min=0.0, unit="counts",
                         transform="softplus", vary=False),
        fwhm=Parameter(value=0.02, min=0.01, unit="deg",
                       transform="softplus", vary=False))]
    result = refine_multi(two_patterns, structure, instruments,
                          plan="mccusker_default")

    codes0 = {d.code for d in result.histograms[0].diagnostics}
    codes1 = {d.code for d in result.histograms[1].diagnostics}
    assert "BACKGROUND_PEAK_TOO_NARROW" in codes0
    assert "BACKGROUND_PEAK_TOO_NARROW" not in codes1   # no peak declared there


def test_every_row_carries_a_bound_answer_or_says_it_has_none(two_patterns):
    """`multi.py` builds its own rows, so it needs its own at_bound pin.

    The WP-1076 rules are asserted on the single-histogram path in
    `test_result_rows.py`; this is the second builder, and the thing it can get
    wrong that the first cannot is the *key*.  A row's path is the combined
    path — shared rows unprefixed, per-histogram rows `hist.h.…` — and that is
    also how `MultiParameterTable.free_paths` spells them, so a projection
    keyed on anything else would silently mark every per-histogram row
    unmeasured while every assertion about counts still passed.
    """
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(two_patterns, plan="mccusker_default")

    named = {p for d in result.diagnostics if d.code == "BOUND_HIT" for p in d.where}
    assert {p.path for p in result.parameters if p.at_bound is True} == named

    measured = {p.path for p in result.parameters if p.at_bound is not None}
    assert measured == set(ref.mtable.free_paths) & {p.path for p in result.parameters}
    # both halves of the key are exercised: shared rows and per-histogram rows
    assert any(p.startswith("hist.") for p in measured)
    assert any(not p.startswith("hist.") for p in measured)
    # the unmeasured rows are the tied ones (cubic b←a, c←a), not an empty set
    unmeasured = {p.path for p in result.parameters if p.at_bound is None}
    assert {"phases.0.cell.b", "phases.0.cell.c"} <= unmeasured


def test_rietveld_only():
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    dummy = PatternData(two_theta=[1.0, 2.0], intensity=[1.0, 1.0])
    with pytest.raises(NotImplementedError):
        ref.fit([dummy, dummy], mode="lebail")


# --- WP-1131: a size is a specimen property, a size *coefficient* is not ----

TRUE_SIZE_A = 400.0
TRUE_STRAIN = 1e-3
#: the two wavelengths above, and the ratio that is the whole finding
LAM_RATIO = 0.71070 / 0.41390


def _true_width(term: str, lam: float) -> float:
    """The coefficient a 400 Å / Δd/d = 1e-3 specimen needs, never typed.

    The Gaussian pair are *variances*, so each is the square of its Lorentzian
    twin's coefficient — which is the whole of why ``gauss_size`` goes as λ².
    """
    if term == "lor_size":
        return size_coefficient_for_size(TRUE_SIZE_A, lam)
    if term == "gauss_size":
        return size_coefficient_for_size(TRUE_SIZE_A, lam) ** 2
    if term == "gauss_strain":
        return strain_coefficient_for_microstrain(TRUE_STRAIN) ** 2
    return strain_coefficient_for_microstrain(TRUE_STRAIN)


def _broadened(term: str, lam: float, tt_lo: float, tt_hi: float, seed: int):
    """One LaB6 pattern whose *only* sample broadening is ``term``.

    ``profile.x`` is held at 0 so every degree of 1/cosθ width is the
    specimen's, which is what lets the fitted coefficient be compared with the
    one the synthesis put in.  The width is set from the physics, never typed:
    a 400 Å crystallite at this λ, or Δd/d = 1e-3 at any λ.
    """
    value = _true_width(term, lam)
    structure = make_lab6()
    for k in ("a", "b", "c"):
        getattr(structure.phases[0].cell, k).value = TRUE_A
    structure.phases[0].scale.value = 5e-4
    getattr(structure.phases[0], term).value = value
    ins = Instrument.debye_scherrer(wavelength=lam)
    ins.profile.w.value = 3e-4
    ins.profile.x.value = 0.0
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (40.0, -6.0, 1.5)])

    tt = np.arange(tt_lo, tt_hi, 0.005)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist()), value


def _width_start(lam: float):
    """A fresh structure/instrument pair: cell off, width at zero."""
    structure = make_lab6()
    for k in ("a", "b", "c"):
        getattr(structure.phases[0].cell, k).value = TRUE_A + 0.002
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=lam)
    ins.profile.w.value = 3e-4
    ins.profile.x.value = 0.0
    ins.background = BackgroundChebyshev.with_terms(3)
    return structure, ins


def _width_plan(term: str) -> RefinementPlan:
    """scale+background, then cell, then the one width — nothing else moves."""
    return RefinementPlan(stages=[
        Stage(name="scale+bkg", turn_on=["phases.*.scale", "instrument.background.*"]),
        Stage(name="cell", turn_on=["phases.*.cell.*"]),
        Stage(name="width", turn_on=[f"phases.*.{term}"], seed=1e-3),
    ])


@pytest.fixture(scope="module")
def size_fixture():
    """Two patterns of ONE 400 Å specimen, at two wavelengths (WP-1131)."""
    p0, v0 = _broadened("lor_size", 0.41390, 3.0, 24.0, seed=1)
    p1, v1 = _broadened("lor_size", 0.71070, 5.0, 42.0, seed=2)
    return [p0, p1], [v0, v1]


def test_a_joint_fit_recovers_one_crystallite_at_both_wavelengths(size_fixture):
    """The WP-1131 acceptance: one specimen, one size, two coefficients.

    Before the fix this fit served one ``lor_size`` column to both histograms
    and landed −2.2 % / −43.0 % from the two truths — 408.8 Å against 702.0 Å
    for one specimen, the two implied sizes exactly ``LAM_RATIO`` apart — while
    reporting ``converged`` and taking histogram 1's Rwp from 0.137 to 0.245.
    Now the column is the coefficient at λ₀ and each histogram carries its own.

    The size agreement is asserted **tight**, because after the fix it is
    structural rather than statistical: the two coefficients are one number
    times two wavelengths, so they read back as the same size to floating point.
    The accuracy against the truth is the loose one, and matches what each
    pattern gives alone (−2.2 %).
    """
    patterns, truths = size_fixture
    structure, _ = _width_start(0.41390)
    instruments = [_width_start(lam)[1] for lam in (0.41390, 0.71070)]
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(patterns, plan=_width_plan("lor_size"))

    assert result.status == "converged"
    sizes = [apparent_size_from_size_coefficient(
        ref.fitted_structures[h].phases[0].lor_size.value, lam)
        for h, lam in enumerate((0.41390, 0.71070))]
    assert sizes[0] == pytest.approx(sizes[1], rel=1e-9), (
        f"one specimen, two crystallite sizes: {sizes}")
    for h, size in enumerate(sizes):
        assert size == pytest.approx(TRUE_SIZE_A, rel=0.05), f"hist {h}: {size} Å"

    # each histogram's *coefficient* differs by exactly the wavelength ratio
    coeffs = [ref.fitted_structures[h].phases[0].lor_size.value for h in (0, 1)]
    assert coeffs[1] / coeffs[0] == pytest.approx(LAM_RATIO, rel=1e-12)

    # and the fit is as good as each pattern alone, where sharing the degrees
    # left histogram 1 at Rwp 0.245
    for h, hist in enumerate(result.histograms):
        assert hist.statistics.rwp < 0.16, f"hist {h} Rwp {hist.statistics.rwp}"
        OUT.mkdir(exist_ok=True)
        result.for_histogram(h).plot(OUT / f"wp1131_size_joint_h{h}.png")

    codes = [d.code for d in result.diagnostics]
    assert "SIZE_NORMALISED_ACROSS_WAVELENGTHS" in codes
    row = next(d for d in result.diagnostics
               if d.code == "SIZE_NORMALISED_ACROSS_WAVELENGTHS")
    assert row.where == ["phases.0.lor_size"]
    assert row.value == pytest.approx(LAM_RATIO, rel=1e-12)


def test_the_lambda_free_strain_control_is_shared_exactly_as_before():
    """The control that makes the size result a measurement, not an argument.

    Microstrain has no λ in it, so ``SharingMap`` is right about it and this WP
    must not touch it: one column, both histograms, and the value the joint fit
    lands on is the one each pattern gives alone.  Run with the same machinery
    and the same wavelengths as the size case, which is the point — the
    difference between the two tests is the physics, not the fixture.
    """
    patterns = [_broadened("lor_strain", 0.41390, 3.0, 24.0, seed=1)[0],
                _broadened("lor_strain", 0.71070, 5.0, 42.0, seed=2)[0]]
    structure, _ = _width_start(0.41390)
    instruments = [_width_start(lam)[1] for lam in (0.41390, 0.71070)]
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(patterns, plan=_width_plan("lor_strain"))

    assert result.status == "converged"
    values = [ref.fitted_structures[h].phases[0].lor_strain.value for h in (0, 1)]
    assert values[0] == values[1], "a λ-free quantity must stay one number"
    assert microstrain_from_strain_coefficient(values[0]) == pytest.approx(
        TRUE_STRAIN, rel=0.05)
    # no size term was freed, so nothing to normalise and nothing to say
    assert "SIZE_NORMALISED_ACROSS_WAVELENGTHS" not in [
        d.code for d in result.diagnostics]


def test_the_two_wavelength_selectors_agree():
    """``params.multi._longest_wavelength`` is the compiled selector's twin.

    Two spellings on purpose — one reads a schema object before anything is
    compiled, the other a ``CompiledModel`` — so the pin is here rather than in
    a comment, exactly as ``_SIZE_CAP_SCHERRER_K`` is pinned against
    ``caglioti.SCHERRER_K``.
    """
    for lam in (0.41390, 0.71070, 1.5406):
        ins = Instrument.debye_scherrer(wavelength=lam)
        tt = np.arange(5.0, 20.0, 0.05)
        blank = PatternData(two_theta=tt.tolist(),
                            intensity=np.ones_like(tt).tolist())
        model = compile_model(make_lab6(), ins, blank, mode="rietveld")
        assert _longest_wavelength(ins) == _longest_line_wavelength(model)
    # a Kα1/Kα2 doublet: both selectors take the *longer* line
    ins = Instrument.bragg_brentano(radiation="CuKa")
    lams = [line.wavelength.value for line in ins.source.lines]
    assert len(lams) > 1
    assert _longest_wavelength(ins) == max(lams)


def test_equal_wavelengths_declare_no_scaling_at_all():
    """Every joint fit that predates WP-1131 must be bit-identical.

    The factor is ``λ_h/λ_0``, so equal wavelengths give exactly 1.0 and the
    map is empty — not "1.0 everywhere", empty, so ``ParameterTable`` takes the
    same branch it always took and no multiplication happens at all.

    The third empty case, a source declaring no positive wavelength, is not
    exercised here because the schema refuses to build one (``EmissionLine``
    carries ``min = 0.001`` Å); the guard stands for a radiation kind that
    arrives without one.
    """
    structure = make_lab6()
    same = [Instrument.debye_scherrer(wavelength=0.41390) for _ in range(3)]
    assert size_value_scales(structure, same, SharingMap()) == [{}, {}, {}]
    # one histogram has nothing to normalise against
    assert size_value_scales(structure, same[:1], SharingMap()) == [{}]


def test_the_scale_map_is_the_wavelength_ratio_and_its_square():
    """``lor_size`` goes as λ and ``gauss_size`` (a variance) as λ²."""
    structure = make_lab6()
    instruments = [Instrument.debye_scherrer(wavelength=lam)
                   for lam in (0.41390, 0.71070)]
    scales = size_value_scales(structure, instruments, SharingMap())
    assert scales[0] == {}, "histogram 0 carries the reference wavelength"
    assert scales[1]["phases.0.lor_size"] == pytest.approx(LAM_RATIO, rel=1e-15)
    assert scales[1]["phases.0.gauss_size"] == pytest.approx(LAM_RATIO ** 2,
                                                             rel=1e-15)
    assert "phases.0.lor_strain" not in scales[1]
    assert "phases.0.gauss_strain" not in scales[1]
    # a caller who wants an independent size per histogram says so, and then
    # there is nothing shared to normalise
    per_hist = SharingMap(per_histogram=["phases.*.lor_size"])
    scales = size_value_scales(structure, instruments, per_hist)
    assert "phases.0.lor_size" not in scales[1]
    assert "phases.0.gauss_size" in scales[1]


def test_a_scaled_path_may_not_be_tied():
    """The refusal ``apply_value_scale`` exists to make, checked by name."""
    structure, ins = _width_start(0.41390)
    table = ParameterTable(structure, ins)
    with pytest.raises(KeyError):
        table.apply_value_scale({"phases.0.no_such_thing": 2.0})
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite and positive"):
            table.apply_value_scale({"phases.0.lor_size": bad})
    # a symmetry tie: b ← a in a cubic cell
    with pytest.raises(ValueError, match="tied"):
        table.apply_value_scale({"phases.0.cell.b": 2.0})
    with pytest.raises(ValueError, match="sources must be unscaled"):
        table.apply_value_scale({"phases.0.cell.a": 2.0})


def test_the_gaussian_size_variance_is_normalised_as_lambda_squared():
    """``gauss_size`` is a *variance*, so it goes as λ² and was hurt worse.

    Measured on this fixture with the normalisation switched off: +11.9 % /
    −62.1 % against the two truths, implied sizes 378.2 Å and 649.3 Å, and
    histogram 1's Rwp 0.0817 → 0.3807 — against ``lor_size``'s 0.2450, because
    the error in the width is squared into the variance.  With it, 400.2 Å in
    both and both Rwp exactly what each pattern gives alone.

    Asserted through the square root, which is where the λ² lives: ``sqrt`` of
    the variance coefficient is a FWHM coefficient and reads as a size through
    the same function ``lor_size`` uses.
    """
    p0, _ = _broadened("gauss_size", 0.41390, 3.0, 24.0, seed=1)
    p1, _ = _broadened("gauss_size", 0.71070, 5.0, 42.0, seed=2)
    structure, _ = _width_start(0.41390)
    instruments = [_width_start(lam)[1] for lam in (0.41390, 0.71070)]
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit([p0, p1], plan=_width_plan("gauss_size"))

    assert result.status == "converged"
    coeffs = [ref.fitted_structures[h].phases[0].gauss_size.value for h in (0, 1)]
    assert coeffs[1] / coeffs[0] == pytest.approx(LAM_RATIO ** 2, rel=1e-12)
    sizes = [apparent_size_from_size_coefficient(math.sqrt(c), lam)
             for c, lam in zip(coeffs, (0.41390, 0.71070), strict=True)]
    assert sizes[0] == pytest.approx(sizes[1], rel=1e-9)
    for h, size in enumerate(sizes):
        assert size == pytest.approx(TRUE_SIZE_A, rel=0.05), f"hist {h}: {size} Å"
    for h, hist in enumerate(result.histograms):
        assert hist.statistics.rwp < 0.12, f"hist {h} Rwp {hist.statistics.rwp}"
        OUT.mkdir(exist_ok=True)
        result.for_histogram(h).plot(OUT / f"wp1131_gauss_size_joint_h{h}.png")

    row = next(d for d in result.diagnostics
               if d.code == "SIZE_NORMALISED_ACROSS_WAVELENGTHS")
    assert row.where == ["phases.0.gauss_size"]
    assert row.value == pytest.approx(LAM_RATIO ** 2, rel=1e-12)
    assert "λ²" in row.message


def test_a_seed_lands_on_one_number_in_the_shared_column():
    """A scaled entry is seeded in *column* units, so the histograms agree.

    ``Stage.seed`` lifts a softplus coefficient off the exact-zero floor before
    solving.  Seeded as a physical value it would put the two histograms at
    different internal coordinates for one shared column, and
    ``_rebuild_columns``'s "identical values from each histogram" would silently
    stop holding — the last write would win and the reference histogram would
    end up seeded to the *other* one's number.
    """
    structure = make_lab6()
    instruments = [Instrument.debye_scherrer(wavelength=lam)
                   for lam in (0.41390, 0.71070)]
    mt = MultiParameterTable(structure, instruments)
    mt.set_vary(["phases.*.lor_size"], True)
    mt.seed_softplus(["phases.0.lor_size"], 1e-3)

    values = mt.decode(mt.x0())
    # each histogram's own physical value is the seed times its own factor …
    assert values[0]["phases.0.lor_size"] == pytest.approx(1e-3, rel=1e-12)
    assert values[1]["phases.0.lor_size"] == pytest.approx(1e-3 * LAM_RATIO,
                                                           rel=1e-12)
    # … which is one crystallite size, which is the whole point
    sizes = [apparent_size_from_size_coefficient(
        values[h]["phases.0.lor_size"], lam)
        for h, lam in enumerate((0.41390, 0.71070))]
    assert sizes[0] == pytest.approx(sizes[1], rel=1e-9)


def test_a_scaled_column_is_the_jacobian_the_residual_actually_has():
    """The claim behind ``apply_value_scale``, checked where it is used.

    The factor is folded into C, so ``decode`` multiplies — and
    ``_peak_chain_column`` finite-differences θ *through* ``decode``, which is
    why the analytic column picks it up with no edit to any derivative branch.
    That is an argument, and this is the measurement: every column of the
    stacked multi-histogram Jacobian against a central difference of the
    stacked residual, with the two scaled columns (λ and λ²) among them.

    Un-checked, a wrong factor here would be a column short by 1.72× or 2.95×
    on a converging fit — a slower solve and a wrong covariance, neither of
    which raises.
    """
    lams = (0.41390, 0.71070)
    ranges = ((3.0, 20.0), (5.0, 34.0))
    patterns, structures, instruments = [], [], []
    for h, lam in enumerate(lams):
        structure = make_lab6()
        structure.phases[0].scale.value = 5e-4
        structure.phases[0].lor_size.value = size_coefficient_for_size(400.0, lam)
        structure.phases[0].gauss_size.value = (
            size_coefficient_for_size(600.0, lam) ** 2)
        ins = Instrument.debye_scherrer(wavelength=lam)
        ins.profile.w.value = 3e-4
        ins.background = BackgroundChebyshev(
            coefficients=[Parameter(value=v) for v in (40.0, -6.0)])
        tt = np.arange(ranges[h][0], ranges[h][1], 0.02)
        blank = PatternData(two_theta=tt.tolist(),
                            intensity=np.zeros_like(tt).tolist())
        model = compile_model(structure, ins, blank, mode="rietveld")
        table = ParameterTable(structure, ins)
        y = model.evaluate(table.decode(table.x0()))
        y = np.random.default_rng(1 + h).poisson(np.maximum(y, 1.0)).astype(float)
        patterns.append(PatternData(two_theta=model.tt.tolist(),
                                    intensity=y.tolist()))
        structures.append(structure)
        instruments.append(ins)

    mt = MultiParameterTable(structures[0], instruments)
    mt.set_vary(["phases.*.lor_size", "phases.*.gauss_size", "phases.*.scale",
                 "phases.*.cell.a"], True)
    mt.apply_to_models()
    models = [compile_model(mt.structures[h], mt.instruments[h], patterns[h],
                            mode="rietveld") for h in range(2)]
    residual, jacobian, _ = _multi_closures(models, mt)

    # the two size columns really are scaled, or the rest proves nothing
    assert mt.value_scales[1]["phases.0.lor_size"] == pytest.approx(LAM_RATIO)
    assert mt.value_scales[1]["phases.0.gauss_size"] == pytest.approx(LAM_RATIO ** 2)

    x = mt.x0()
    J = jacobian(x)
    for c, path in enumerate(mt.free_paths):
        step = 1e-6 * max(1.0, abs(x[c]))
        plus, minus = x.copy(), x.copy()
        plus[c] += step
        minus[c] -= step
        fd = (residual(plus) - residual(minus)) / (2 * step)
        scale = max(np.abs(J[:, c]).max(), np.abs(fd).max(), 1e-30)
        assert np.abs(J[:, c] - fd).max() / scale < 2e-5, path
