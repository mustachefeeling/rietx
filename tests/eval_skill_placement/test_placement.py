"""The placement round's instrument agrees with its registration.

Two texts are authored in `runner.py` and quoted by PROTOCOL.md, and a read-out
is only as good as the reach test under it, so both are pinned here.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.eval_skill_placement import runner

PROTOCOL = Path(__file__).with_name("PROTOCOL.md")


def _flat(text: str) -> str:
    return " ".join(re.sub(r"^> ?", "", text, flags=re.M).split())


def test_the_protocol_quotes_the_launched_prompt_and_sentence():
    protocol = _flat(PROTOCOL.read_text(encoding="utf-8"))
    assert _flat(runner.PROMPT) in protocol
    assert _flat(runner.GREP_SENTENCE) in protocol
    for prefix in runner.REMOVED_ROWS:
        assert f"`{prefix}`" in protocol
    for code in runner.SCORED_CODES:
        assert f"`{code}`" in protocol


def test_the_grep_body_drops_the_rows_and_refuses_a_body_without_them():
    body = "\n".join(["intro", "", runner.TABLE_HEAD, "|---|---|---|",
                      *(p + " | x | y |" for p in runner.REMOVED_ROWS),
                      "| kept | x | y |"])
    out = runner.grep_body(body)
    assert runner.GREP_SENTENCE in out and "| kept | x | y |" in out
    assert not any(line.startswith(runner.REMOVED_ROWS) for line in out.split("\n"))
    try:
        runner.grep_body(out)
    except SystemExit:
        pass
    else:
        raise AssertionError("a body without the rows must be refused")


def _use(ident: str, name: str, **args) -> dict:
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": ident, "name": name, "input": args}]}}


def _result(ident: str, text: str) -> dict:
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": ident,
         "content": [{"type": "text", "text": text}]}]}}


def test_reach_is_read_off_what_came_back():
    rows = [
        _use("1", "Skill", skill="rietx"),
        _result("1", "the body, naming FLAT_DIRECTION bare"),
        _use("2", "Grep", pattern="BACKGROUND_ABSORPTION",
             path="/ws/.claude/skills/rietx/references/"),
        _result("2", "diagnostics.md:20:| `BACKGROUND_ABSORPTION` | Quote ADPs"),
        _use("3", "Read", file_path="/Users/me/Code/rietx/docs/skill/rietx/SKILL.md"),
        _result("3", "nothing"),
    ]
    out = runner.read_out(rows)
    assert out["skill_loaded"]
    assert out["reached"] == {"BACKGROUND_ABSORPTION": "Grep"}
    assert len(out["leaks"]) == 1
