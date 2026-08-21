"""What a :class:`RefinedParameter` row is allowed to assert (WP-1076).

The defect this file guards against is invisible to every other test in the
suite: a field that serializes on every result, that nothing writes, and whose
default reads as an answer.  ``at_bound`` was ``bool = False``, so each row of
each result said "this parameter is not against a bound" about a parameter no
code had looked at.  Nothing failed, because an absent writer fails nothing.

So the assertions here are about the *three states* and about where the answer
comes from.  The one that carries the weight is
``test_at_bound_names_exactly_the_paths_bound_hit_names``: the flag is the
``BOUND_HIT`` findings projected onto the rows, and asserting set equality
against the diagnostics is what pins it to that single source.  A test that
merely checked "the flagged parameter is at its bound" would pass just as well
against a second, independent bound test in ``_build_result`` — which is the
bug the WP exists to avoid.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.results import RefinedParameter
from rietx.strategy.staged import bound_findings
from rietx.viz import plot_result

DATA = Path(__file__).parent / "data"
WAVELENGTH = 0.4139090  # 11BM_NAC.fxye, from 11bm_gsas.prm
LIMITS = (2.0, 24.0)


def _nac():
    """The 11-BM NAC Le Bail setup — one fit is ~1 s, so this stays fast."""
    data = rx.read_pattern(DATA / "11BM_NAC.fxye")
    structure = rx.Structure.from_cif(str(DATA / "cod_1000236.cif"))
    instrument = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    instrument.background = BackgroundChebyshev.with_terms(6)
    return data, structure, instrument


def _bound_hit_paths(result) -> set[str]:
    return {p for d in result.diagnostics if d.code == "BOUND_HIT" for p in d.where}


@pytest.fixture(scope="module")
def lebail():
    """An ordinary converged Le Bail fit, no bound anywhere near the optimum."""
    data, structure, instrument = _nac()
    ref = rx.Refinement(structure, instrument)
    return data, ref, ref.fit(data, mode="lebail", two_theta_limits=LIMITS)


def test_a_free_row_is_measured_and_a_tied_row_is_not(lebail):
    """Three states, and the split is free-vs-tied, not fit-vs-no-fit.

    ``ParameterTable._free_idx`` is ``e.vary and e.tie is None`` while the row
    filter is ``e.vary or e.tie is not None``, so a tied row is *in*
    ``parameters`` and was never in the free vector the guard tested.  Its
    value follows its sources and can sit on its own declared bound while every
    source is interior, so ``False`` there would be the original defect wearing
    a different cause.  Measured on this fit: 31 rows, 13 free and 13 measured,
    18 symmetry-tied and 18 unmeasured.
    """
    _, ref, result = lebail
    assert result.status == "converged"

    rows = {p.path for p in result.parameters}
    tied = {r.path for r in ref.parameters() if r.tie is not None}
    free = {r.path for r in ref.parameters() if r.vary and r.tie is None}
    measured = {p.path for p in result.parameters if p.at_bound is not None}
    unmeasured = {p.path for p in result.parameters if p.at_bound is None}

    assert unmeasured == tied & rows
    assert measured == free & rows
    # not a vacuous partition in either direction
    assert len(measured) == 13 and len(unmeasured) == 18


def test_at_bound_names_exactly_the_paths_bound_hit_names():
    """The flag is the guard's finding list, projected — not a second opinion.

    The cell edge is capped 0.0013 Å below the value the free fit wants, so the
    trust region rides the upper bound: Rwp goes 0.1457 → 0.2194 and ``a`` lands
    on 10.250000 exactly.  Set equality against the ``BOUND_HIT`` diagnostics is
    the assertion; "is it really at its bound" is deliberately *not* asserted,
    because a re-derivation here would pass against the duplicate this WP
    removed.
    """
    data, structure, instrument = _nac()
    ref = rx.Refinement(structure, instrument)
    a = ref.structure.phases[0].cell.a
    a.value = 10.2490
    a.min, a.max = 10.2000, 10.2500
    result = ref.fit(data, mode="lebail", two_theta_limits=LIMITS)

    flagged = {p.path for p in result.parameters if p.at_bound is True}
    assert flagged == _bound_hit_paths(result) == {"phases.0.cell.a"}
    # and the rest of the free rows are a measured False, not a default one
    assert sum(1 for p in result.parameters if p.at_bound is False) == 12

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / "row_at_bound_capped_cell.png"))
    plot_result(result, path=str(out / "row_at_bound_capped_cell_lowangle.png"),
                two_theta_range=(2.0, 8.0))


def test_a_result_built_without_a_guard_reports_none(lebail):
    """``replay`` is evaluate-only, so it has no bound answer to give.

    This is the state that made ``bool | None`` the choice over forcing every
    call site to pass a flag: a builder with nothing to say says nothing,
    rather than saying ``False`` for convenience.
    """
    data, ref, result = lebail
    replayed = rx.replay(ref.history, result.node_id, data)
    assert len(replayed.parameters) == len(result.parameters)
    assert all(p.at_bound is None for p in replayed.parameters)


def test_the_field_defaults_to_unmeasured():
    """A hand-built row asserts nothing about a bound."""
    assert RefinedParameter(path="phases.0.scale", value=1.0).at_bound is None


def test_the_bound_test_lives_in_one_place():
    """``bound_findings`` is the only bound test, and it reports free paths only.

    Both the guard report and the row flag call it; a tied path is not in
    ``free``/``theta`` at all, which is why the flag needs a third state rather
    than a fourth branch here.
    """
    lo = np.array([0.0, -np.inf, 1.0, 0.0])
    hi = np.array([1.0, np.inf, 2.0, np.inf])
    names = ["two_sided", "unbounded", "interior", "one_sided"]
    # on its upper bound / free / interior / on its only bound
    found = bound_findings((lo, hi), names, np.array([1.0, 5.0, 1.5, 0.0]))
    assert [f.paths for f in found] == [("two_sided",), ("one_sided",)]
    assert {f.code for f in found} == {"BOUND_HIT"}
    # an infinite bound is skipped rather than compared, so it can neither
    # raise nor answer False for every column through a NaN
    assert bound_findings((lo, hi), names,
                          np.array([0.5, -1e12, 1.5, 1e-3])) == []


def test_a_generous_bound_does_not_pin_the_value_it_was_meant_to_free():
    """WP-1110 item 18: the tolerance is relative to the bound, not the span.

    A caller who writes ``Parameter(value=1.0, min=1e-14, max=1e14)`` is saying
    "do not constrain this".  Under the pre-WP-1110 span-relative rule that
    span was 1e14, hence a tolerance of 1e6, and the scale read as ``BOUND_HIT``
    at every stage of every pattern — 14 orders of magnitude from either bound.
    Reported by a real agent that had widened its own scale bounds for exactly
    the reason the rule then punished.

    The two ends still fire, which is the half a looser tolerance gets right by
    accident and a tighter one has to keep on purpose.
    """
    lo, hi = np.array([1e-14]), np.array([1e14])
    assert bound_findings((lo, hi), ["phases.0.scale"], np.array([1.0])) == []
    for pinned in (1e-14, 1e14):
        found = bound_findings((lo, hi), ["phases.0.scale"], np.array([pinned]))
        assert [f.paths for f in found] == [("phases.0.scale",)]


def test_the_bound_test_agrees_with_the_solver_it_reports_on():
    """``bound_findings`` names exactly the columns TRF calls active.

    The tolerance is quoted from ``scipy.optimize._lsq.common`` rather than
    chosen (see ``BOUND_HIT_RTOL``), so this is the check that keeps the
    diagnostic and the solver from holding different opinions about the same
    column.  It goes through the public ``active_mask``, not the private
    predicate, so a scipy refactor moves nothing here and a scipy *behaviour*
    change fails it — which is the way round that is worth being told about.

    The problem is a plain bounded linear least squares whose unconstrained
    solution is ``[2, -1, 0.5]``: the first two are cut off by their bounds and
    the third is interior, so the answer is not "all" or "none".
    """
    from scipy.optimize import least_squares

    from rietx.strategy.staged import bound_findings as _bf

    a = np.eye(3)
    b = np.array([2.0, -1.0, 0.5])
    lo = np.array([0.0, -0.25, -1e14])
    hi = np.array([1.0, 3.0, 1e14])
    res = least_squares(lambda x: a @ x - b, np.array([0.5, 0.0, 0.0]),
                        jac=lambda x: a, bounds=(lo, hi), method="trf")
    names = ["clipped_high", "clipped_low", "interior_but_widely_bounded"]

    active = {n for n, m in zip(names, res.active_mask, strict=True) if m != 0}
    flagged = {f.paths[0] for f in _bf((lo, hi), names, res.x)}
    assert active == {"clipped_high", "clipped_low"}
    assert flagged == active


def test_a_widely_bounded_scale_is_clean_on_a_real_fit():
    """Item 18 where it did its damage: the rows and the diagnostics of a fit.

    The unit test above pins the predicate; this one pins that nothing between
    it and a result re-introduces the flag.  The setup is the transcript's — a
    scale declared ``Parameter(min=1e-14, max=1e14)``, identity transform,
    which is what an agent writes when it means "do not constrain this" and is
    *not* what ``Parameter.positive()`` builds (softplus, whose lower bound
    goes to −∞ internally and so never met the span rule at all).  Measured
    before the fix: ``phases.0.scale`` flagged in 5 of the 5 stages, refining
    to 10.25.
    """
    data, structure, instrument = _nac()
    structure.phases[0].scale = rx.Parameter(value=1.0, min=1e-14, max=1e14)
    ref = rx.Refinement(structure, instrument)
    result = ref.fit(data, two_theta_limits=LIMITS)

    scale = next(p for p in result.parameters if p.path == "phases.0.scale")
    assert scale.at_bound is False
    assert 1e-6 < scale.value < 1e6, scale.value
    assert "phases.0.scale" not in _bound_hit_paths(result)
