"""The session-usage script behind the lane trial (.claude/hooks/session_usage.py).

It is stdlib-only and lives outside the package, so it is loaded by file path,
like the workflow hooks in test_workflow_hooks.py, and driven against
synthetic transcripts written in Claude Code's JSONL shape.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "session_usage", ROOT / ".claude" / "hooks" / "session_usage.py")
su = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = su   # its dataclasses look their module up while being built
_spec.loader.exec_module(su)


def _ts(n: int) -> str:
    return f"2026-10-01T10:{n // 60:02d}:{n % 60:02d}.000Z"


def _asst(n: int, mid: str, read: int, write: int = 0, blocks=(), sidechain=False,
          model="claude-opus-5-5") -> dict:
    split = {"ephemeral_5m_input_tokens": write, "ephemeral_1h_input_tokens": 0} if sidechain \
        else {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": write}
    return {"timestamp": _ts(n), "isSidechain": sidechain, "message": {
        "role": "assistant", "id": mid, "model": model, "content": list(blocks),
        "usage": {"input_tokens": 0, "cache_read_input_tokens": read,
                  "cache_creation_input_tokens": write, "cache_creation": split,
                  "output_tokens": 100}}}


def _use(uid: str, name: str, **inp) -> dict:
    return {"type": "tool_use", "id": uid, "name": name, "input": inp}


def _result(n: int, uid: str, body: str, sidechain=False, **extra) -> dict:
    return {"timestamp": _ts(n), "isSidechain": sidechain, **extra, "message": {
        "role": "user", "content": [{"type": "tool_result", "tool_use_id": uid, "content": body}]}}


def _write(path: Path, entries: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return path


def test_one_response_written_as_several_lines_is_one_request(tmp_path: Path) -> None:
    """Claude Code writes each content block of a response as its own line,
    every one carrying the response's usage; summing lines double-counts."""
    a = _asst(1, "m1", read=100_000, write=5_000, blocks=[{"type": "text", "text": "x"}])
    b = _asst(1, "m1", read=100_000, write=5_000, blocks=[_use("u1", "Bash", command="ls")])
    t = su.parse(_write(tmp_path / "s.jsonl", [a, b]))
    assert len(t.requests) == 1
    req = t.requests[0]
    assert req.context == 105_000
    reads, writes, out = req.parts()
    assert reads == pytest.approx(100_000 * 0.20 / 1e6)
    assert writes == pytest.approx(5_000 * 8.00 / 1e6)   # the main session writes at 1 h
    assert out == pytest.approx(100 * 20.00 / 1e6)


def _session(tmp_path: Path, contexts: list[int], commit_after: set[int]) -> Path:
    entries = []
    for i, c in enumerate(contexts):
        blocks = []
        if i in commit_after:
            blocks = [_use(f"c{i}", "Bash", command=f'git commit -m "WP-1234: item {i}"')]
        entries.append(_asst(i, f"m{i}", read=c, blocks=blocks))
    return _write(tmp_path / "s.jsonl", entries)


def test_items_split_at_wp_commits_and_the_commit_closes_its_item(tmp_path: Path) -> None:
    t = su.parse(_session(tmp_path, [10, 20, 30, 40, 50, 60], commit_after={1, 4}))
    assert [seg for _, seg in su.segments(t)] == [[10, 20], [30, 40, 50], [60]]


def test_a_replay_that_lanes_nothing_reads_every_request_once(tmp_path: Path) -> None:
    """The replay's identity: kept items carry the counterfactual main context,
    which must reproduce the measured one, compactions and jumps included."""
    ctx = [80_000, 90_000, 150_000, 140_000, 60_000, 75_000, 200_000]
    t = su.parse(_session(tmp_path, ctx, commit_after={1, 3, 5}))
    cost = su.replay(t, lambda m, n: False, u=0)
    reads = sum(ctx) * 0.20 / 1e6
    assert cost - reads == pytest.approx(sum(
        max(seg) - seg[0] for _, seg in su.segments(t)) * 8.00 / 1e6)


def test_a_late_long_item_is_cheaper_laned_and_an_early_short_one_is_not(tmp_path: Path) -> None:
    long_late = [400_000 + 2_000 * i for i in range(40)]
    t = su.parse(_session(tmp_path, long_late, commit_after={39}))
    assert su.replay(t, lambda m, n: True, u=20_000) < su.replay(t, lambda m, n: False, u=0)
    short_early = [80_000 + 2_000 * i for i in range(5)]
    t = su.parse(_session(tmp_path, short_early, commit_after={4}))
    assert su.replay(t, lambda m, n: True, u=20_000) > su.replay(t, lambda m, n: False, u=0)


def test_a_lane_is_measured_from_both_transcripts(tmp_path: Path) -> None:
    """Re-read counts the lane's reads of files the main session held at
    dispatch; the window runs from dispatch to the item's commit."""
    sid = "11111111-2222-3333-4444-555555555555"
    held = "/w/src/a.py"
    main = _write(tmp_path / "proj" / f"{sid}.jsonl", [
        _asst(1, "m1", read=200_000, blocks=[_use("r1", "Read", file_path=held)]),
        _result(2, "r1", "a" * 5_000),
        _asst(3, "m2", read=205_000, blocks=[
            {"type": "text", "text": "lanes: keep item 1 ~8\n"},
            _use("g1", "Agent", description="lane: item 2 ~25", prompt="...")]),
        _result(4, "g1", "launched", toolUseResult={"agentId": "abc"}),
        _asst(5, "m3", read=212_000, blocks=[_use("e1", "Edit", file_path=held, old_string="x",
                                                  new_string="y")]),
        _asst(6, "m4", read=215_000, blocks=[
            _use("c1", "Bash", command='git commit -m "WP-1234: item 2"')]),
        _asst(7, "m5", read=216_000),
    ])
    _write(tmp_path / "proj" / sid / "subagents" / "agent-abc.jsonl", [
        _asst(1, "s1", read=0, write=60_000, sidechain=True, blocks=[
            _use("v1", "Read", file_path=held), _use("v2", "Read", file_path="/w/src/b.py")]),
        _result(2, "v1", "a" * 5_000, sidechain=True),
        _result(2, "v2", "b" * 2_500, sidechain=True),
        _asst(3, "s2", read=60_000, write=10_000, sidechain=True),
    ])
    res = su.measure_lanes(main)
    (lane,) = res["lanes"]
    assert lane["item"] == "item 2" and lane["estimate"] == 25
    assert lane["requests"] == 2 and lane["base"] == 60_000 and lane["peak"] == 70_000
    assert lane["main_context"] == 205_000
    assert lane["reread"] == pytest.approx(5_000 / 2.5)
    assert lane["read"] == pytest.approx(7_500 / 2.5)
    assert lane["main_requests"] == 2 and lane["carried"] == 10_000
    assert lane["fixes"] == 1 and lane["redo"] == 0
    assert lane["lane_cost"] == pytest.approx((60_000 * 5.00 + 60_000 * 0.20 + 10_000 * 5.00
                                               + 200 * 20.00) / 1e6)
    (kept,) = res["kept"]
    assert kept == dict(item="item 1", estimate=8, requests=2, main_context=205_000)
