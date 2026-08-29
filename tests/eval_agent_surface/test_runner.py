"""The registered prompt and the launched prompt are the same text.

A protocol that paraphrases its own prompt has registered a condition nobody
can reproduce, and the paraphrase is invisible: both halves read fine on their
own.  So the prompts are authored in `runner.py`, quoted in `PROTOCOL.md`, and
held together here.

Nothing in this file launches anything.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.eval_agent_surface import runner

PROTOCOL = (Path(__file__).parent / "PROTOCOL.md").read_text(encoding="utf-8")

# Package vocabulary an unprimed prompt must not contain.  Ordinary English
# that happens to name the science ("refined", "phase") is not on the list:
# what the condition withholds is how to drive *this* package.
PRIMING = ("rietx", "AGENT_PROTOCOL", "SKILL.md", "capabilities(", "read_pattern",
           "Refinement", "refine(", "plan=", "mccusker", "lebail", "pawley")


def _flat(text: str) -> str:
    return " ".join(re.sub(r"(?m)^>\s?", "", text).split())


@pytest.mark.parametrize("episode", sorted(runner.PROMPTS))
def test_the_protocol_quotes_the_prompt_that_is_launched(episode: str):
    assert _flat(runner.PROMPTS[episode]) in _flat(PROTOCOL), (
        f"PROTOCOL.md no longer quotes the {episode} prompt verbatim — "
        "the registration and the launch have drifted"
    )


@pytest.mark.parametrize("episode", sorted(runner.PROMPTS))
def test_a_prompt_names_no_way_to_drive_the_package(episode: str):
    text = runner.PROMPTS[episode].lower()
    named = [token for token in PRIMING if token.lower() in text]
    assert not named, f"{episode} prompt is primed: it names {named}"


def test_the_preamble_gives_the_interpreter_and_the_directory_and_no_more():
    assert set(re.findall(r"\{(\w+)\}", runner.PREAMBLE)) == {"python", "workspace"}
    assert not any(token.lower() in runner.PREAMBLE.lower() for token in PRIMING)


def test_the_eight_cells_are_the_ones_the_protocol_declares():
    cells = [f"{e}-{c}-{m}" for e in runner.EPISODES
             for c in runner.CONDITIONS for m in runner.MODELS]
    assert len(cells) == 8
    for cell in cells:
        assert runner.split(cell) == tuple(cell.split("-"))
    with pytest.raises(SystemExit):
        runner.split("ramp-pointed-opus5")  # round 1.0's cell, which has no successor


def test_the_workspace_holds_no_harness_file(tmp_path):
    """Venv, trace log and run record all live outside the agent's directory."""
    p = runner.paths(tmp_path, "ramp-bare-sonnet")
    workspace = p.pop("workspace")
    assert workspace == tmp_path / "ramp-bare-sonnet"
    for name, path in p.items():
        assert workspace not in path.parents, f"{name} sits inside the workspace"


def test_the_prompt_carries_this_cells_own_interpreter(tmp_path):
    text = runner.prompt_for("ramp-skill-opus5", tmp_path)
    assert str(tmp_path / "venvs" / "ramp-skill-opus5" / "bin" / "python") in text
    assert str(tmp_path / "ramp-skill-opus5") in text
    assert runner.PROMPTS["ramp"] in text
