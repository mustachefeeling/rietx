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
from rietx.schemas.structure import Structure
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


def test_every_histograms_ticks_name_their_reflections(two_patterns):
    """`multi.py` keeps its own tick builder, so it owes the same pairing.

    CLAUDE.md names this exact shape — a second builder of anything is the
    miss — and the failure it prevents is the one surface where pointing at a
    tick tells the reader nothing (WP-1438).
    """
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(two_patterns, plan="mccusker_default")

    for h, hist in enumerate(result.histograms):
        assert hist.ticks, f"hist {h} has no ticks"
        assert set(hist.tick_hkl) <= set(hist.ticks), h
        for phase, positions in hist.ticks.items():
            if phase not in hist.tick_hkl:
                continue        # the declared-peak key has no Miller index
            assert len(hist.tick_hkl[phase]) == len(positions), (h, phase)
            assert all(len(k) == 3 for k in hist.tick_hkl[phase]), (h, phase)
            assert positions == sorted(positions), (h, phase)
    # the two histograms see the same phase and so name the same reflections,
    # each at its own wavelength's angles
    first, second = result.histograms
    assert set(first.tick_hkl) == set(second.tick_hkl)


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
    ``HUMP_TOO_NARROW`` in *that histogram's* own diagnostics, the
    channel a joint fit reports degeneracy evidence through.  Before this the
    joint path was the only one that never called ``check_hump_width``,
    so such a peak produced no warning anywhere.
    """
    from rietx.schemas.instrument import HumpComponent

    structure, instruments = perturbed_inputs()
    instruments[0].extra_components = [HumpComponent(
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
    assert "HUMP_TOO_NARROW" in codes0
    assert "HUMP_TOO_NARROW" not in codes1   # no peak declared there


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


def _hump_on_histogram_0():
    """The joint inputs with a hump declared on histogram 0 only.

    The one family on ``main`` that exists on one histogram and not the other
    without being an emission line, so the nearest a constant-wavelength
    fixture comes to issue #265's banks, whose profile rows went by other
    names.
    """
    from rietx.schemas.instrument import HumpComponent

    structure, instruments = perturbed_inputs()
    instruments[0].extra_components = [HumpComponent(
        label="hump",
        position=Parameter(value=12.0, unit="deg", vary=False),
        height=Parameter(value=20.0, min=0.0, unit="counts",
                         transform="softplus", vary=False),
        fwhm=Parameter(value=1.5, min=0.1, unit="deg",
                       transform="softplus", vary=False))]
    return structure, instruments


def test_a_glob_that_reached_one_histogram_is_told_apart_from_the_rest():
    """What ``unreached_histograms`` reports, and the three silences (WP-1414).

    Reported: a glob that matched rows of one histogram and none of another.
    Silent: a glob scoped to the histogram it reached (deliberate), a row
    that exists on both and is force-fixed on both (reached, then declined),
    and a glob matching nowhere (the single-histogram healthy case).
    """
    structure, instruments = _hump_on_histogram_0()
    mt = MultiParameterTable(structure, instruments)
    humps = "instrument.extra_components.*"

    assert mt.unreached_histograms([humps]) == {1: [humps]}
    assert mt.unreached_histograms(["phases.*.scale", humps]) == {}, (
        "a glob that reaches histogram 1 elsewhere in the stage reaches it")
    assert mt.unreached_histograms([f"hist.0.{humps}"]) == {}
    # scoped by what it matched rather than by its prefix: only histogram 1's
    # scoped name answers it, so it is aimed there and histogram 0 is no miss
    assert mt.unreached_histograms(["*.1.instrument.zero_shift"]) == {}
    assert mt.unreached_histograms(["hist.*.instrument.extra_components.*"]) == {
        1: ["hist.*.instrument.extra_components.*"]}
    assert mt.unreached_histograms(["instrument.geometry.sample_displacement"]) == {}
    assert mt.unreached_histograms(["phases.*.microstrain.dof.*"]) == {}
    assert mt.unreached_histograms(["instrument.profile.*"]) == {}

    # known means a bare path of some histogram or a scoped one of a real one
    assert mt.unknown_literals([
        "hist.7.instrument.zero_shift", "hist.1.instrument.zero_shift",
        "instrument.zero_shift", "instrument.zero", "hist.0.instrument.extra_components.0.fwhm",
        "hist.1.instrument.extra_components.0.fwhm",
    ]) == ["hist.7.instrument.zero_shift", "instrument.zero",
           "hist.1.instrument.extra_components.0.fwhm"]


def test_a_joint_plan_that_reaches_one_histogram_says_which_it_missed(two_patterns):
    """Issue #265's comment, on the fixture ``main`` can build.

    The fork's case was ``instrument.profile.*`` freeing the one
    constant-wavelength histogram and none of the banks; the result said
    ``converged`` and cost a refinement.  Here a stage's glob reaches a hump
    declared on histogram 0 only, and the record and the diagnostic both
    name histogram 1.  A literal no histogram has is the other finding, and
    a joint fit reports it the way a single one does.
    """
    structure, instruments = _hump_on_histogram_0()
    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
              max_iter=10),
        Stage("humps", ["instrument.extra_components.*", "instrument.zero"],
              max_iter=5),
    ])
    result = refine_multi(two_patterns, structure, instruments, plan=plan)

    assert [s.unreached_histograms for s in result.stages] == [
        {}, {1: ["instrument.extra_components.*"]}]
    freed_nothing = [d for d in result.diagnostics
                     if d.code == "STAGE_FREED_NOTHING"]
    assert len(freed_nothing) == 1
    d = freed_nothing[0]
    assert d.level == "info" and d.value == 1.0
    assert d.where == ["instrument.extra_components.*"]
    assert "'humps'" in d.message and "histogram 1" in d.message

    assert result.stages[1].unknown_paths == ["instrument.zero"]
    unknown = [d for d in result.diagnostics if d.code == "STAGE_PATH_UNKNOWN"]
    assert [u.where for u in unknown] == [["instrument.zero"]]
    assert "did you mean 'instrument.zero_shift'" in unknown[0].message

    # the record round-trips: histogram keys are ints in JSON's string keys
    again = type(result).model_validate_json(result.model_dump_json())
    assert again.stages[1].unreached_histograms == {
        1: ["instrument.extra_components.*"]}


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


def test_a_joint_fit_reports_its_microstructure(size_fixture):
    """The block must not be empty on the fits this WP exists for.

    ``RefinementResult.microstructure`` defaults to an empty list, and an empty
    list reads as *no microstructure* — the WP-1076 shape — so a joint fit that
    never filled it would say that about a specimen it had just measured a
    crystallite size for. Read off histogram 0, whose value scale is exactly
    1.0, so its coefficients are the shared column and the size behind them is
    the specimen's one number.
    """
    patterns, _ = size_fixture
    structure, _ = _width_start(0.41390)
    instruments = [_width_start(lam)[1] for lam in (0.41390, 0.71070)]
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(patterns, plan=_width_plan("lor_size"))

    assert len(result.microstructure) == 1
    block = result.microstructure[0]
    assert block.wavelength == pytest.approx(0.41390), "the reference histogram"
    size = block.term("lor_size")
    assert size.unavailable is None
    assert size.esd is not None and size.esd > 0.0
    # the same crystallite the two structure copies imply, read either way
    per_copy = apparent_size_from_size_coefficient(
        ref.fitted_structures[1].phases[0].lor_size.value, 0.71070)
    assert size.value == pytest.approx(per_copy, rel=1e-9)
    assert size.value == pytest.approx(TRUE_SIZE_A, rel=0.05)
    # and the joint result carries the constant it used, never a defaulted zero
    assert block.scherrer_k > 0.0


# ----------------------------------------------------------------------
# review of #385 (2026-09-22): the joint runner (multi.py:301-318, per that
# review) has the single-histogram stage runner's shape line for line and had
# no clamp_cell_runaway at all -- extended in rietx.multi._clamp_cell_runaway_multi.
# ----------------------------------------------------------------------
def _degenerate_pair_structure(decoy_scale: float) -> Structure:
    """The single-histogram degenerate-pair construction
    (``test_cell_runaway_safety._degenerate_pair``): two LaB6-shaped phases
    sharing one starting cell, one at full scale and one at a trace.  Reused
    here because the joint runner shares the cell across histograms by
    default, and the same joint degeneracy trips it there too."""
    real = make_lab6()
    for n in "abc":
        getattr(real.phases[0].cell, n).value = TRUE_A
    real.phases[0].scale.value = 5e-4
    decoy_s = make_lab6()
    decoy = decoy_s.phases[0]
    decoy.name = "decoy"
    for n in "abc":
        getattr(decoy.cell, n).value = TRUE_A
    decoy.scale.value = decoy_scale
    return Structure(phases=[real.phases[0], decoy])


def _degenerate_pair_instruments() -> list[Instrument]:
    out = []
    for lam in (0.41390, 0.71070):
        ins = Instrument.debye_scherrer(wavelength=lam)
        ins.background = BackgroundChebyshev.with_terms(3)
        out.append(ins)
    return out


def test_the_joint_clamp_fires_on_a_shared_degenerate_cell():
    """Unit-level, at the level ``test_cell_runaway_safety.py`` tests the
    single-histogram function: escape the shared cell directly on both
    histograms' own tables -- exactly what ``mtable.commit(outcome.theta)``
    after a runaway joint TRF step leaves behind -- rather than driving a
    real solve there, which needs ~20 unwindowed iterations on purpose
    (the single-histogram fixture's own docstring)."""
    from rietx.multi import _clamp_cell_runaway_multi
    from rietx.params.vector import CELL_SAFETY_ANGLE_DEG, CELL_SAFETY_FRACTION, cell_window
    from rietx.refine import _cell_runaway_diagnostic

    structure = _degenerate_pair_structure(5e-4)
    mtable = MultiParameterTable(structure, _degenerate_pair_instruments())
    mtable.set_vary(["phases.*.cell.a"], True)
    start_values = mtable.decode(mtable.x0())

    escaped = TRUE_A * 50.0  # far outside +/-15%, same escape as the single-histogram tests
    for table in mtable.tables:
        table.entries[table._paths["phases.0.cell.a"]].value = escaped

    clamped = _clamp_cell_runaway_multi(mtable, start_values)
    assert len(clamped) == 1, clamped  # shared -> named once, not once per histogram
    path, old, new = clamped[0]
    assert path == "phases.0.cell.a"   # bare: shared, never hist.h.-scoped
    assert old == pytest.approx(escaped)
    lo, hi = cell_window("a", start_values[0][path], -math.inf, math.inf,
                         fraction=CELL_SAFETY_FRACTION,
                         angle_deg=CELL_SAFETY_ANGLE_DEG)
    assert new == pytest.approx(hi)

    # both histograms' own entries were actually clamped, not just the report
    for table in mtable.tables:
        assert table.entries[table._paths["phases.0.cell.a"]].value == pytest.approx(hi)

    diag = _cell_runaway_diagnostic(clamped)
    assert diag is not None
    assert diag.where == ["phases.0.cell.a"]
    assert diag.code == "CELL_RUNAWAY"


def test_a_shared_cell_inside_the_window_is_left_alone_jointly():
    """The bit-identity companion: nothing to clamp in either histogram is
    nothing changed in either."""
    from rietx.multi import _clamp_cell_runaway_multi

    structure = _degenerate_pair_structure(5e-4)
    mtable = MultiParameterTable(structure, _degenerate_pair_instruments())
    mtable.set_vary(["phases.*.cell.a"], True)
    start_values = mtable.decode(mtable.x0())

    for table in mtable.tables:
        table.entries[table._paths["phases.0.cell.a"]].value = TRUE_A * 1.001

    assert _clamp_cell_runaway_multi(mtable, start_values) == []


@pytest.fixture(scope="module")
def degenerate_pair_multi_fit():
    """The joint-runner analogue of the single-histogram ``degenerate_pair_fit``
    fixture: two histograms sharing the degenerate-pair structure, scale+cell
    of both phases freed together in one stage, then a second stage forcing
    the next compile -- the construction that crashed the single-histogram
    runner before its own fix, reused here to reach ``multi.py``'s equivalent
    gap (review of #385 finding 2)."""
    structure = _degenerate_pair_structure(1e-5)
    instruments = _degenerate_pair_instruments()
    data = [synthesize(lam, 3.0, 24.0, scale=1e-5, zero=0.0,
                       bkg=[40.0, 0.0, 0.0], seed=s)
            for lam, s in ((0.41390, 11), (0.71070, 12))]
    ref = MultiHistogramRefinement(structure, instruments)
    plan = RefinementPlan(stages=[
        Stage("both", ["phases.*.scale", "phases.*.cell.*"], max_iter=20),
        Stage("zero", ["instrument.zero_shift"], max_iter=20),
    ])
    result = ref.fit(data, plan=plan)
    return ref, result, data


def test_the_joint_runner_does_not_crash_on_the_trigger_construction(
        degenerate_pair_multi_fit):
    _, result, _ = degenerate_pair_multi_fit
    assert result.status in ("converged", "max_iter")


def test_the_joint_runner_reports_and_clamps_the_runaway(degenerate_pair_multi_fit):
    ref, result, _ = degenerate_pair_multi_fit
    fired = [d for d in result.diagnostics if d.code == "CELL_RUNAWAY"]
    assert len(fired) >= 1, [d.code for d in result.diagnostics]
    for phase in ref.fitted_structures[0].phases:
        a = phase.cell.a.value
        assert 1.0 < a < 100.0, f"{phase.name}: a = {a:.6g} Å ran away"
    # every histogram's own structure copy carries the same clamped cell
    assert ref.fitted_structures[1].phases[0].cell.a.value == pytest.approx(
        ref.fitted_structures[0].phases[0].cell.a.value, rel=1e-9)


def test_the_joint_runners_reported_parameters_agree_with_its_statistics(
        degenerate_pair_multi_fit):
    """The finding-1 regression, replayed at the joint level: a firing clamp
    must leave ``result.parameter(...)``/``fitted_structures`` and
    ``result.histograms[h].y_calc``/``statistics`` agreeing about the *same*
    cell -- never the reported parameter at the clamped value while the
    curve and Rwp were built from the pre-clamp (escaped) one."""
    ref, result, data = degenerate_pair_multi_fit
    assert any(d.code == "CELL_RUNAWAY" for d in result.diagnostics)
    a = result.parameter("phases.0.cell.a").value
    assert a == pytest.approx(ref.fitted_structures[0].phases[0].cell.a.value)
    for h in range(len(result.histograms)):
        structure_h = ref.fitted_structures[h]
        assert structure_h.phases[0].cell.a.value == pytest.approx(a, rel=1e-9)
        model = compile_model(structure_h, ref.fitted_instruments[h], data[h],
                              mode="rietveld")
        table = ParameterTable(structure_h, ref.fitted_instruments[h])
        y_calc = model.evaluate(table.decode(table.x0()))
        assert np.asarray(result.histograms[h].y_calc) == pytest.approx(
            y_calc, abs=1.0), (
            f"histogram {h}: reported y_calc disagrees with a recompute at "
            "the reported parameters -- the joint runner's theta was not "
            "re-derived after the clamp fired")
