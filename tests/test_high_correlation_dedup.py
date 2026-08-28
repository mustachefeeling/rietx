"""HIGH_CORRELATION deduplication and the per-fit cap (WP-1302).

Unit-level rather than a real refinement: the mechanism is pure list
processing over ``Diagnostic`` objects, and a persistently correlated real
pair (``tests/test_capillary_displacement.py``,
``tests/test_acceptance_lab6_cbn.py``) is expensive to reproduce on every
run just to re-check dedup arithmetic already covered here.
"""

from __future__ import annotations

from rietx.refine import (
    HIGH_CORRELATION_MAX,
    _cap_high_correlation,
    _dedup_high_correlations,
)
from rietx.schemas.common import Diagnostic


def _corr(a: str, b: str, rho: float) -> Diagnostic:
    return Diagnostic(level="warning", code="HIGH_CORRELATION",
                      message=f"{a} ~ {b} (ρ={rho:+.3f})",
                      where=[a, b], value=rho,
                      suggestion="consider fixing one of the correlated parameters")


def test_a_persistent_pair_across_five_stages_yields_one_diagnostic():
    """The acceptance line, literally: five stages, one pair, one finding."""
    a, b = "phases.0.cell.a", "instrument.zero_shift"
    hits = {frozenset((a, b)): [
        (f"stage{i}", _corr(a, b, rho))
        for i, rho in enumerate([0.981, 0.983, 0.986, 0.990, 0.991], start=1)
    ]}
    out = _dedup_high_correlations(hits)
    assert len(out) == 1
    assert out[0].value == 0.991  # the worst |rho|, not the last stage's
    assert "stage1" in out[0].message and "stage5" in out[0].message


def test_a_pair_seen_once_keeps_the_original_message_untouched():
    a, b = "phases.0.cell.a", "phases.0.scale"
    hits = {frozenset((a, b)): [("cell", _corr(a, b, 0.99))]}
    out = _dedup_high_correlations(hits)
    assert out[0].message == "phases.0.cell.a ~ phases.0.scale (ρ=+0.990)"


def test_distinct_pairs_stay_distinct_and_sort_worst_first():
    hits = {
        frozenset(("a", "b")): [("s1", _corr("a", "b", 0.90))],
        frozenset(("c", "d")): [("s1", _corr("c", "d", -0.99))],
    }
    out = _dedup_high_correlations(hits)
    assert [d.value for d in out] == [-0.99, 0.90]


def test_cap_passes_a_short_list_through_unchanged():
    diags = [_corr(f"a{i}", f"b{i}", 0.9) for i in range(HIGH_CORRELATION_MAX)]
    assert _cap_high_correlation(diags) == diags


def test_cap_keeps_the_worst_ten_and_names_the_rest():
    diags = [_corr(f"a{i}", f"b{i}", 0.90 + i * 0.001) for i in range(15)]
    out = _cap_high_correlation(diags)

    kept = [d for d in out if d.code == "HIGH_CORRELATION"]
    omitted = [d for d in out if d.code == "HIGH_CORRELATION_OMITTED"]
    assert len(kept) == HIGH_CORRELATION_MAX
    assert len(omitted) == 1
    assert omitted[0].level == "info"
    assert omitted[0].value == 5.0
    assert "result.identifiability" in omitted[0].suggestion
    # worst first, and nothing below the cap survived
    assert [round(d.value, 3) for d in kept] == sorted(
        (round(d.value, 3) for d in kept), reverse=True)
    assert min(d.value for d in kept) > max(
        (d.value for d in diags if d not in kept), default=0.0) - 1e-9


def test_cap_leaves_every_other_code_untouched():
    other = Diagnostic(level="warning", code="BOUND_HIT", message="x refined to its bound",
                       where=["x"], value=None, suggestion="widen the bound")
    diags = [other, *[_corr(f"a{i}", f"b{i}", 0.9) for i in range(12)]]
    out = _cap_high_correlation(diags)
    assert other in out
    assert sum(1 for d in out if d.code == "HIGH_CORRELATION") == HIGH_CORRELATION_MAX
    assert sum(1 for d in out if d.code == "HIGH_CORRELATION_OMITTED") == 1
