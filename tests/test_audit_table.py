"""WP-2001 — the generality audit table, held equal to the tree both ways.

``rietx._audit`` is the table, and its docstring says what each kind of row
is and why the growth guard reads no git.  A failure here prints the row to
add or change.  The tier is the audit's call: a new item enters with its
tier and evidence, or at ``unaudited`` with its name added to
``UNAUDITED_BASELINE``.  Either edit touches the table, so ``/wp-handover``
step 7 sends it to the ``generality-review`` agent.
"""

from __future__ import annotations

import dataclasses
import datetime
import pathlib

import pytest

from rietx import _audit

ROWS = {row.name: row for row in _audit.ROWS}


@pytest.fixture(scope="module")
def walked():
    return {"code": dict.fromkeys(_audit.codes()), "constant": _audit.constants(),
            "default": _audit.defaults(), "suggestion": _audit.suggestions()}


def _enter(missing: dict[str, object], kind: str) -> str:
    lines = "\n".join(_audit.row_source(name, kind, value)
                      for name, value in sorted(missing.items()))
    return (f"{len(missing)} {kind}(s) with no row in rietx._audit.ROWS.  Enter each "
            "with its tier and evidence (docs/milestones/generality.md § The rule), "
            "or at 'unaudited' with its name on UNAUDITED_BASELINE:\n" + lines)


def test_row_names_are_unique():
    names = [row.name for row in _audit.ROWS]
    assert len(names) == len(set(names)), sorted(n for n in set(names) if names.count(n) > 1)


def test_every_row_is_well_formed():
    for row in _audit.ROWS:
        assert row.kind in _audit.KINDS, row
        assert row.tier in _audit.TIERS, row
        if row.ambiguity is not None:
            assert row.ambiguity in (1, 2, 3), row
            assert row.kind in ("code", "action", "suggestion"), (
                f"{row.name}: ambiguity is stated on code, action and suggestion rows")
        if row.kind in ("code", "action"):
            assert row.value is None, f"{row.name}: a {row.kind} row stores no value"
        if row.approved is not None:
            datetime.date.fromisoformat(row.approved)


@pytest.mark.parametrize("kind", ["code", "constant", "default", "suggestion"])
def test_rows_of_each_walked_kind_are_the_tree_both_ways(kind, walked):
    """A new code, constant, default or suggestion site fails until it has a row."""
    live = walked[kind]
    rows = {name: row for name, row in ROWS.items() if row.kind == kind}
    missing = {name: live[name] for name in live.keys() - rows.keys()}
    assert not missing, _enter(missing, kind)
    gone = sorted(rows.keys() - live.keys())
    assert not gone, (f"{kind} rows naming nothing in the tree; delete each row and its "
                      f"UNAUDITED_BASELINE line, or rename it if the item moved: {gone}")


@pytest.mark.parametrize("kind", ["constant", "default", "suggestion"])
def test_a_valued_row_holds_the_live_value(kind, walked):
    """A retune fails, so the row's audit reopens with it."""
    moved = [f"{name}: table {row.value!r}, tree {walked[kind][name]!r}"
             for name, row in ROWS.items()
             if row.kind == kind and name in walked[kind]
             and not _audit.same(row.value, walked[kind][name])]
    assert not moved, (f"{kind} value(s) changed; update each row's value, and its "
                       "tier if the evidence was measured at the old one:\n"
                       + "\n".join(moved))


def test_every_record_field_is_an_action_row_or_declared_other():
    """A new field on StageResult, SeriesEntry or RefinementResult fails until placed."""
    fields = set(_audit.record_fields())
    actions = {name for name, row in ROWS.items() if row.kind == "action"}
    assert not actions - fields, f"action rows naming no record field: {sorted(actions - fields)}"
    assert not actions & _audit.OTHER_RECORD_FIELDS, sorted(actions & _audit.OTHER_RECORD_FIELDS)
    stale = _audit.OTHER_RECORD_FIELDS - fields
    assert not stale, f"OTHER_RECORD_FIELDS names no field: {sorted(stale)}"
    new = sorted(fields - actions - _audit.OTHER_RECORD_FIELDS)
    assert not new, ("record field(s) neither an action row nor in OTHER_RECORD_FIELDS. "
                     "A field reporting what the package did on its own is an action:\n"
                     + "\n".join(_audit.row_source(name, "action") for name in new))


def test_an_audited_row_carries_its_evidence():
    """Self-certification is the failure the table exists against, so a tier
    names its source; tier 3, and a tier-2 action, also carry the two-ground
    answer and the maintainer's dated approval."""
    for row in _audit.ROWS:
        if row.tier == "unaudited":
            continue
        assert row.evidence, f"{row.name}: tier {row.tier!r} with no evidence"
        if row.kind in ("code", "action"):
            assert row.ambiguity is not None, (
                f"{row.name}: an audited {row.kind} row states its kind under "
                "DESIGN.md § Rules, 1")
        if row.tier == 3 or (row.tier == 2 and row.kind == "action"):
            assert row.grounds and row.approved, (
                f"{row.name}: tier {row.tier} {row.kind} needs grounds and approved")


def test_every_unaudited_row_is_on_the_baseline():
    """The growth guard: a new item cannot land at 'unaudited' unlisted."""
    baseline = set(_audit.UNAUDITED_BASELINE)
    off = sorted(row.name for row in _audit.ROWS
                 if row.tier == "unaudited" and row.name not in baseline)
    assert not off, ("row(s) at 'unaudited' not on UNAUDITED_BASELINE.  Give each its "
                     f"tier, or add its name to the baseline for the judge to read: {off}")


def test_the_baseline_shrinks_as_rows_are_audited():
    """Every baseline name is a row still at 'unaudited', so auditing a row
    means deleting its baseline line."""
    baseline = _audit.UNAUDITED_BASELINE
    assert list(baseline) == sorted(set(baseline)), "UNAUDITED_BASELINE is sorted and unique"
    orphan = sorted(name for name in baseline if name not in ROWS)
    assert not orphan, f"baseline name(s) with no row: {orphan}"
    audited = sorted(name for name in baseline if ROWS[name].tier != "unaudited")
    assert not audited, f"audited row(s) still on UNAUDITED_BASELINE; delete: {audited}"


def test_the_declared_scope_resolves():
    package = pathlib.Path(_audit.__file__).parent
    for entry, owner in _audit.WALKED.items():
        assert (package / entry).exists(), entry
        assert 2002 <= owner <= 2007, (entry, owner)
    for seat, owner in _audit.DEFAULT_SEATS.items():
        assert callable(_audit.resolve(seat)), seat
        assert 2002 <= owner <= 2007, (seat, owner)


def test_row_source_round_trips():
    """The line a failure prints evaluates to the row it describes."""
    for row in _audit.ROWS:
        if row.tier != "unaudited":
            continue
        rebuilt = eval(_audit.row_source(row.name, row.kind, row.value).rstrip(","),
                       {"Row": _audit.Row})
        assert dataclasses.astuple(rebuilt) == dataclasses.astuple(row), row.name
