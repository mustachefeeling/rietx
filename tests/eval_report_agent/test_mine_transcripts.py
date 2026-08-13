"""Unit tests for the transcript miner (WP-1063).

Everything here runs against the committed two-cell record in
``fixture_round/`` (its README says what each cell is built to pin) or against
``tmp_path`` — no round record, no agent, no refinement.  The real record is
gitignored and deletable, so it can never be what tests the reader of it.

The rules under test are the ones the round taught, each of which had a
measured wrong answer before it:

- a token in **prompt prose** is not a delivery (the §5/§6 excerpts name the
  whole action vocabulary);
- an overlay is an overlay whether a ``Write`` payload or a Bash heredoc
  carried it;
- the trajectory is *answered* by ``tool_use_id``, not by adjacency, because
  an agent's own ``jq`` projection can strip every marker field out of a rung;
- voicing a word is not evidence of having been told it — three cells voiced
  ``exchangeable`` without the clause ever arriving, one of them in the arm
  that never had a report.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anatase.report.schemas import StageReport
from tests.eval_report_agent import mine_transcripts as mt

FIXTURE = Path(__file__).parent / "fixture_round"


@pytest.fixture(scope="module")
def mined() -> dict:
    return mt.mine(FIXTURE)


def _row(mined: dict, cell: str) -> dict:
    return next(r for r in mined["rows"] if r["cell"] == cell)


# ----------------------------------------------------------------------
# the vocabulary is quoted, never invented
# ----------------------------------------------------------------------
def test_every_field_token_names_a_live_field():
    """A renamed field must break the miner, not silently count zero — the
    derived-flag rot of WP-1037, one directory over."""
    for token, (model, name) in mt.FIELD_TOKENS.items():
        assert token == name
        assert name in model.model_fields, f"{model.__name__}.{name} is gone"


def test_action_vocabulary_is_the_live_one():
    from typing import get_args

    from anatase.report.schemas import ActionKind

    assert set(get_args(ActionKind)) <= set(mt.TOKENS)


def test_rung_markers_are_rung_only_and_non_empty():
    assert mt.RUNG_MARKERS
    assert mt.RUNG_MARKERS <= set(StageReport.model_fields)
    # ``stage`` is a rung field *and* an IterationRecord field, so the
    # derivation must disqualify it without an exclusion list
    assert "stage" not in mt.RUNG_MARKERS
    # ``actions`` survives because delivery is matched in JSON form
    assert "actions" in mt.RUNG_MARKERS
    assert mt._as_json("actions").search('"suggested_actions": []') is None
    assert mt._as_json("actions").search('"actions": []') is not None


# ----------------------------------------------------------------------
# surfaces
# ----------------------------------------------------------------------
def test_prompt_prose_is_not_a_delivery(mined):
    """Both fixture cells read a prompt naming ``add_impurity_phase`` and
    ``n_actions_vetoed`` in backticks; neither counts as the package having
    sent anything."""
    for cell in ("both__sonnet/E2", "report__haiku/E2"):
        counts = _row(mined, cell)["citations"]["add_impurity_phase"]
        assert counts["delivered"] == 0, cell


def test_delivered_counts_the_json_form(mined):
    row = _row(mined, "both__sonnet/E2")
    assert row["citations"]["exchangeable"]["delivered"] == 1
    assert row["citations"]["identifiability"]["probed"] == 1


def test_voiced_is_the_agents_own_prose(mined):
    """Assistant text and the ``answer.json`` it wrote, and nothing else."""
    assert _row(mined, "both__sonnet/E2")["citations"]["exchangeable"]["voiced"] == 2
    assert _row(mined, "report__haiku/E2")["citations"]["exchangeable"]["voiced"] == 1


def test_voicing_without_delivery_is_visible(mined):
    """The b cell says ``exchangeable`` out of its own head — no clause ever
    reached it.  A word-match eval would score that as reading the report."""
    row = _row(mined, "report__haiku/E2")
    assert row["citations"]["exchangeable"]["voiced"] == 1
    assert row["ridge"]["clause_delivered_index"] is None


# ----------------------------------------------------------------------
# the ridge
# ----------------------------------------------------------------------
def test_write_payload_overlay_is_found(mined):
    """The a cell's overlay is an escaped ``content`` string: a brace scan of
    the serialized tool input cannot reach it."""
    row = _row(mined, "both__sonnet/E2")["ridge"]
    assert row["both_free"] is True
    assert row["ridge_overlay_index"] is not None


def test_heredoc_overlay_is_found():
    """The b cell wrote its overlay with ``cat > … << 'EOF'`` — one of the
    seven real ridge cells did the same."""
    events = mt.read_events(
        FIXTURE / "transcripts" / "agent-fixture-b.jsonl")
    writes = mt.overlay_writes(events)
    assert len(writes) == 1
    assert mt.overlay_frees(writes[0][1], ["instrument.zero_shift"])
    assert not mt.overlay_frees(
        writes[0][1], ["instrument.geometry.sample_displacement"])


def test_clause_order_is_reported(mined):
    row = _row(mined, "both__sonnet/E2")["ridge"]
    assert row["clause_delivered_index"] < row["ridge_overlay_index"]
    assert row["clause_delivered_before"] is True
    assert row["clause_voiced_before"] is True


def test_one_rival_is_not_a_ridge(mined):
    assert _row(mined, "report__haiku/E2")["ridge"]["both_free"] is False


def test_a_preset_plan_claims_nothing():
    """Which paths a preset frees is not in the overlay, so the ridge column
    stays empty rather than being guessed."""
    assert not mt.overlay_frees({"plan": "lab_calibrate"},
                                ["instrument.zero_shift"])


def test_wildcard_reaches_a_watched_path():
    assert mt.overlay_frees(
        {"plan": {"stages": [{"turn_on": ["instrument.geometry.*"]}]}},
        ["instrument.geometry.sample_displacement"])


# ----------------------------------------------------------------------
# the trajectory
# ----------------------------------------------------------------------
def test_probe_is_answered_by_tool_use_id(mined):
    rungs = _row(mined, "both__sonnet/E2")["rungs"]
    assert rungs["probed_index"] is not None
    assert rungs["answered_index"] > rungs["probed_index"]
    assert rungs["marker_index"] is not None


def test_a_cell_with_no_trajectory_reports_none(mined):
    rungs = _row(mined, "report__haiku/E2")["rungs"]
    assert rungs == {"trajectory_rungs": None, "probed_index": None,
                     "answered_index": None, "marker_index": None,
                     "voiced_index": None}


# ----------------------------------------------------------------------
# the record itself
# ----------------------------------------------------------------------
def test_cells_are_named_and_agree_with_their_meta(mined):
    assert mined["n_transcripts"] == 2
    assert mined["n_cells_named"] == 2
    assert mined["notes"] == []


def test_two_cells_naming_one_workspace_is_reported():
    """A transcript that names two cells is a record problem to say out loud,
    never a tie to break."""
    assert mt.cell_of("RUNS/both__sonnet/E2 and RUNS/off__haiku/R1") is None
    assert mt.cell_of("RUNS/both__sonnet/E2 twice RUNS/both__sonnet/E2") == (
        "both", "sonnet", "E2")


def test_missing_record_is_said_not_raised(tmp_path, capsys):
    assert mt.main([str(tmp_path / "nope")]) == 2
    assert "no round record" in capsys.readouterr().err


def test_a_directory_without_transcripts_is_said(tmp_path, capsys):
    (tmp_path / "transcripts").mkdir()
    assert mt.main([str(tmp_path)]) == 2
    assert "no transcripts" in capsys.readouterr().err


def test_render_and_json_round_trip(tmp_path, capsys):
    out = tmp_path / "mined.json"
    assert mt.main([str(FIXTURE), "--json", str(out)]) == 0
    text = capsys.readouterr().out
    assert "## The ridge: cells that freed both rivals" in text
    assert json.loads(out.read_text(encoding="utf-8"))["n_transcripts"] == 2
