"""``SequentialRefinement`` had no per-pattern exception handling: an uncaught
exception anywhere inside ``_chain`` — deterministic on a genuinely
near-singular warm-carried block, ``numpy.linalg.LinAlgError: SVD did not
converge`` in the trigger case — propagated straight through ``fit()`` and
lost the *entire* chain, including every already-converged earlier pattern.
``on_result`` (a per-pattern callback) had already seen those results; only
the series' own aggregated state (``results_``, ``trees_``, the returned
``SeriesResult``) was empty afterwards.

This is a different failure from ``SeriesEntry.status == "diverged"``: a
diverged fit is a *result* (converged somewhere the reseed fence rejects) and
the WP-1051 quarantine already carries the chain through it with no policy
needed. This module is about a fit that never returns at all.

Reproduction: eight synthetic LaB6 patterns (``tests/test_refine_synthetic``'s
own synthesis routine, reused rather than re-derived), one of which is made
to raise via a monkeypatched ``Refinement.fit`` — the cleanest way to inject a
deterministic, position-independent failure without needing a genuinely
near-singular parameterisation on toy data (the brief's own suggested
alternative). The exception type and message match the real trigger
(``LinAlgError: SVD did not converge for slice = 0``); nothing about *which*
pattern fails or *why* is data from the private series that surfaced this.
"""

from __future__ import annotations

import sys

import numpy as np
import pytest

from rietx import Instrument
from rietx.schemas.pattern import PatternData
from rietx.sequential import ON_ERROR_POLICIES, SequentialRefinement
from tests.test_refine_synthetic import TRUE_A, WAVELENGTH
from tests.test_schemas import make_lab6

pytestmark = pytest.mark.xdist_group("series-error-policy")

N_PATTERNS = 8
FAIL_INDEX = 4  # 0-based -> "pattern 5" in the brief's 1-based telling


def _make_pattern(a: float, noise_seed: int) -> PatternData:
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    structure = make_lab6()
    for n in "abc":
        getattr(structure.phases[0].cell, n).value = a
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    tt = np.arange(3.0, 24.0, 0.01)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(noise_seed)
    y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


@pytest.fixture(scope="module")
def eight_patterns() -> list[PatternData]:
    return [_make_pattern(TRUE_A + 0.0003 * i, noise_seed=100 + i)
            for i in range(N_PATTERNS)]


def _series() -> SequentialRefinement:
    structure = make_lab6()
    structure.phases[0].cell.a.value = TRUE_A
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    return SequentialRefinement(structure, ins)


@pytest.fixture
def fail_on_pattern(monkeypatch, eight_patterns):
    """Monkeypatch ``Refinement.fit`` to raise ``LinAlgError`` on exactly the
    pattern object at ``FAIL_INDEX`` (matched by identity, not content — a
    series never repeats a ``PatternData`` object), every other pattern
    fitting normally through the real method.

    ``rietx.refine`` is patched via ``sys.modules`` rather than the
    ``rietx.refine`` *attribute*, because ``rietx/__init__.py`` re-exports a
    top-level ``refine()`` convenience function under that same name, which
    shadows the submodule on the package object after import — a plain
    ``import rietx.refine as m`` binds ``m`` to that function, not the module,
    and silently patching the wrong ``Refinement.fit`` (a fresh, unrelated
    class) fits every pattern for real and never reproduces anything.
    """
    import rietx.refine  # noqa: F401  (registers rietx.refine in sys.modules)

    refine_mod = sys.modules["rietx.refine"]
    orig_fit = refine_mod.Refinement.fit
    target = eight_patterns[FAIL_INDEX]

    def patched_fit(self, data, *args, **kwargs):
        if data is target:
            raise np.linalg.LinAlgError("SVD did not converge for slice = 0")
        return orig_fit(self, data, *args, **kwargs)

    monkeypatch.setattr(refine_mod.Refinement, "fit", patched_fit)
    return orig_fit


# ----------------------------------------------------------------------
# the crash itself, unmodified
# ----------------------------------------------------------------------
def test_an_invalid_policy_is_refused_by_name():
    series = _series()
    with pytest.raises(ValueError, match="on_error"):
        series.fit([_make_pattern(TRUE_A, 1)], on_error="ignore")


def test_the_reproduction_still_raises_the_trigger_error(
        eight_patterns, fail_on_pattern):
    """Confirms the monkeypatch actually reaches ``SequentialRefinement`` —
    the failure this whole module is about."""
    series = _series()
    with pytest.raises(np.linalg.LinAlgError, match="SVD did not converge"):
        series.fit(eight_patterns)


# ----------------------------------------------------------------------
# on_error="raise" (the default): still raises, but nothing already
# converged is lost with it
# ----------------------------------------------------------------------
def test_raise_still_raises_but_keeps_the_partial_results(
        eight_patterns, fail_on_pattern):
    series = _series()
    seen: list[int] = []
    with pytest.raises(np.linalg.LinAlgError) as excinfo:
        series.fit(eight_patterns, on_result=lambda k, r: seen.append(k))

    # what on_result already knew before the crash — the four converged
    # patterns preceding the one that failed
    assert seen == [0, 1, 2, 3]

    # before this fix this was empty: the whole chain was lost with the
    # exception, even though four patterns had already converged
    assert len(series.results_) == 4
    assert len(series.trees_) == 4
    assert len(series._structures) == 4 and len(series._instruments) == 4
    assert len(series.failures_) == 1
    assert series.failures_[0].index == FAIL_INDEX

    # attached to the exception too, so a caller need not hold a reference
    # to the SequentialRefinement instance to read what completed
    assert excinfo.value.series_results is series.results_
    assert excinfo.value.series_failures is series.failures_


# ----------------------------------------------------------------------
# on_error="skip": the chain continues, cold after the failure
# ----------------------------------------------------------------------
def test_skip_returns_seven_results_and_one_recorded_failure(
        eight_patterns, fail_on_pattern):
    series = _series()
    seen: list[int] = []
    result = series.fit(eight_patterns, on_result=lambda k, r: seen.append(k),
                        on_error="skip")

    assert len(result.entries) == N_PATTERNS - 1
    assert result.n_failed == 1
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.index == FAIL_INDEX
    assert "SVD did not converge" in failure.exception
    # the failed index is simply absent, not present with a placeholder
    assert FAIL_INDEX not in [e.index for e in result.entries]
    assert seen == [0, 1, 2, 3, 5, 6, 7]
    assert len(series.results_) == N_PATTERNS - 1
    assert len(series.failures_) == 1


def test_skip_fits_the_next_pattern_cold(eight_patterns, fail_on_pattern):
    """"skip"'s documented difference from "carry": no warm start survives
    a pattern that never returned."""
    series = _series()
    result = series.fit(eight_patterns, on_error="skip")
    successor = next(e for e in result.entries if e.index == FAIL_INDEX + 1)
    assert successor.rung == "cold"
    assert successor.rungs_tried == ["cold"]


def test_skip_reports_series_pattern_failed(eight_patterns, fail_on_pattern):
    series = _series()
    result = series.fit(eight_patterns, on_error="skip")
    fired = [d for d in result.diagnostics if d.code == "SERIES_PATTERN_FAILED"]
    assert len(fired) == 1
    assert fired[0].level == "warning"
    assert "SVD did not converge" in fired[0].message
    assert str(FAIL_INDEX) in fired[0].message


# ----------------------------------------------------------------------
# on_error="carry": the chain continues, warm from the last good state
# ----------------------------------------------------------------------
def test_carry_also_returns_seven_results_and_one_failure(
        eight_patterns, fail_on_pattern):
    series = _series()
    result = series.fit(eight_patterns, on_error="carry")
    assert len(result.entries) == N_PATTERNS - 1
    assert result.n_failed == 1
    assert result.failures[0].index == FAIL_INDEX


def test_carry_fits_the_next_pattern_warm(eight_patterns, fail_on_pattern):
    series = _series()
    result = series.fit(eight_patterns, on_error="carry")
    successor = next(e for e in result.entries if e.index == FAIL_INDEX + 1)
    assert successor.rung != "cold"
    assert "warm" in successor.rung


# ----------------------------------------------------------------------
# bit-identity: a chain that never fails is untouched by any of this
# ----------------------------------------------------------------------
def test_a_chain_with_no_failures_is_unaffected_by_the_new_parameter(
        eight_patterns):
    series = _series()
    result = series.fit(eight_patterns)  # default on_error="raise"
    assert len(result.entries) == N_PATTERNS
    assert result.n_failed == 0
    assert result.failures == []
    assert not any(d.code == "SERIES_PATTERN_FAILED" for d in result.diagnostics)
    assert series.failures_ == []


def test_on_error_policies_is_the_one_vocabulary_the_validator_uses():
    assert ON_ERROR_POLICIES == ("raise", "skip", "carry")
