"""The skill eval suite's instrument agrees with itself and with the harness (WP-1905).

Nothing here runs a model. What it pins is everything a round would otherwise
discover at its own expense: a case whose fixture is missing, a grader the
harness would refuse to load, a built plugin carrying a tree other than the one
handed in, and a prompt `PROTOCOL.md` does not register.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

from tests.eval_skill import build as B
from tests.eval_skill_placement import runner as placement

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parents[1]
TREE = REPO / "docs" / "skill" / "rietx"

#: `claude plugin eval`'s vocabulary (https://code.claude.com/docs/en/plugin-evals,
#: § Eval suite reference, read 2026-10-04). An unknown prompt.md key is an
#: error there, so it is one here.
PROMPT_KEYS = {"schema_version", "name", "description", "tags", "plugins", "runs",
               "expected_outcome", "model", "max_turns", "timeout_seconds",
               "allowed_tools", "append_system_prompt", "env"}
COMMON = {"type", "weight", "arm"}
GRADER_KEYS = {
    "regex": {"pattern", "flags", "match", "target"},
    "tool_used": {"tool", "input_match", "min", "max"},
    "tool_order": {"before", "after"},
    "file_exists": {"path", "exists"},
    "llm": {"criteria", "focus"},
    "baseline": {"baseline_file", "criteria"},
}
VIEWS = {"last_message", "trace", "files", "mock_calls"}


def _front(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = re.fullmatch(r"---\n(.*?)\n---\n?(.*)", text, flags=re.S)
    assert m, f"{path}: no frontmatter"
    return (yaml.safe_load(m.group(1)) or {}), m.group(2).strip()


def _cases() -> list[Path]:
    return B.cases()


def _id(case: Path) -> str:
    return str(case.relative_to(B.CASES))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """A whole build, with the placement episode stubbed: running its fit is
    the slow test's business, and every other layout fact is the same."""
    def stub(dest: Path, python: Path) -> None:
        dest.mkdir(parents=True)
        for name in (*placement.DATA_FILES, "fit.py", "fit_output.txt"):
            (dest / name).write_text(f"stub {name}\n")

    out = tmp_path_factory.mktemp("plugin") / "p"
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(B.EPISODES, "placement", stub)
        stamp = B.build(TREE, out, python=Path("/opt/venv/bin/python"))
    return out, stamp


def test_the_case_set_is_not_empty_and_names_are_unique():
    names = [c.name for c in _cases()]
    assert "fap-judge" in names
    assert len(names) == len(set(names)), "the harness keys its report on the name"


@pytest.mark.parametrize("case", _cases(), ids=_id)
def test_every_prompt_parses_and_says_which_role_it_plays(case):
    meta, body = _front(case / "prompt.md")
    assert set(meta) <= PROMPT_KEYS, set(meta) - PROMPT_KEYS
    assert body, "an empty prompt"
    assert str(meta.get("description", "")).startswith(B.ROLES), (
        f"description must open with one of {B.ROLES}")
    assert 1 <= meta.get("runs", 3) <= 50
    assert meta.get("timeout_seconds", 300) <= 3600 and meta.get("max_turns", 10) <= 200


@pytest.mark.parametrize("case", _cases(), ids=_id)
def test_every_grader_is_one_the_harness_loads(case):
    graders = sorted((case / "graders").glob("*.md"))
    assert graders, "a case without a grader fails to load"
    for g in graders:
        meta, body = _front(g)
        kind = meta.get("type")
        assert kind in GRADER_KEYS, f"{g.name}: type {kind!r}"
        assert set(meta) <= COMMON | GRADER_KEYS[kind], f"{g.name}: {set(meta)}"
        assert meta.get("arm") in (None, "with-only", "both"), g.name
        assert meta.get("weight", 1) > 0, g.name
        view = meta.get("target" if kind == "regex" else "focus", "last_message")
        if isinstance(view, dict):
            assert view.get("source") == "file" and view.get("path"), g.name
        else:
            assert view in VIEWS, f"{g.name}: {view!r}"
        if kind == "regex":
            re.compile(meta["pattern"])  # the harness's is JavaScript; these are the shared subset
        if kind == "tool_used":
            if "input_match" in meta:
                re.compile(meta["input_match"])
            assert meta.get("min", 1) <= meta.get("max", 10**9), g.name
        if kind == "llm":
            assert body or meta.get("criteria"), f"{g.name}: a rubric with no criteria"


@pytest.mark.parametrize("case", [c for c in _cases() if (c / B.INPUTS).exists()], ids=_id)
def test_every_fixture_source_exists(case):
    rows = B.parse_inputs((case / B.INPUTS).read_text(encoding="utf-8"))
    assert rows
    for verb, source, _ in rows:
        if verb == "copy":
            assert (REPO / source).is_file(), source
        else:
            assert source in B.EPISODES


def test_inputs_refuse_what_they_cannot_read():
    assert B.parse_inputs("copy a/b.txt as c.txt\n# note\nepisode placement\n") == [
        ("copy", "a/b.txt", "c.txt"), ("episode", "placement", "")]
    for bad in ("cp a b", "copy a b c", "episode nowhere", "copy"):
        with pytest.raises(ValueError, match="line 1"):
            B.parse_inputs(bad)


def test_a_committed_case_cannot_carry_what_build_writes(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "prompt.md").write_text("---\n---\nhi\n")
    (tmp_path / "x" / "fixture.sh").write_text("")
    with pytest.raises(ValueError, match="written by build"):
        B.cases(tmp_path)


def test_the_trigger_set_is_balanced_and_scored_in_both_arms():
    """Tier 0: half should fire and half are near-misses that should not, each
    graded by whether `Skill` was called and nothing else (agentskills.io's
    description recipe). `arm: both`, or a two-arm run would drop the grader."""
    roles = {}
    for case in (B.CASES / "trigger").iterdir():
        meta, _ = _front(case / "prompt.md")
        role = next(r for r in B.ROLES if meta["description"].startswith(r))
        roles.setdefault(role, []).append(case.name)
        graders = list((case / "graders").glob("*.md"))
        assert len(graders) == 1, case.name
        g, _ = _front(graders[0])
        assert g["type"] == "tool_used" and g["tool"] == "Skill" and g["arm"] == "both"
        if role == "Should fire.":
            assert g.get("min", 1) >= 1 and "max" not in g, case.name
        else:
            assert role == "Should not fire." and g["min"] == g["max"] == 0, case.name
    assert {r: len(v) for r, v in roles.items()} == {"Should fire.": 10, "Should not fire.": 10}


def test_fap_judge_quotes_the_placement_rubric():
    """One authority for the four rubric items: the placement runner's."""
    graders = B.CASES / "fap-judge" / "graders"
    for name, text in placement.RUBRIC.items():
        meta, body = _front(graders / f"{name}.md")
        assert meta == {"type": "llm", "focus": "last_message"}
        assert body.endswith(text), name
    _, body = _front(B.CASES / "fap-judge" / "prompt.md")
    assert body.startswith(placement.PROMPT)


def test_the_build_carries_the_tree_it_was_handed(built):
    out, stamp = built
    assert B.tree_sha256(out / "skills" / "rietx") == B.tree_sha256(TREE) == stamp["tree_sha256"]
    manifest = json.loads((out / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == B.PLUGIN_NAME
    assert json.loads((out / B.STAMP).read_text()) == stamp
    assert sorted(stamp["cases"]) == sorted(_id(c) for c in _cases())


def test_the_build_writes_the_interpreter_and_the_scaffold(built, tmp_path):
    out, _ = built
    for rel in map(_id, _cases()):
        prompt = (out / "evals" / rel / "prompt.md").read_text()
        assert B.PYTHON_MARK not in prompt
        assert not (out / "evals" / rel / B.INPUTS).exists()
    judge = out / "evals" / "fap-judge"
    assert "/opt/venv/bin/python" in (judge / "prompt.md").read_text()
    assert yaml.safe_load((judge / "case.yaml").read_text()) == {
        "schema_version": "1.1", "name": "fap-judge",
        "context": {"scaffold_script": "fixture.sh"}}
    # The scaffold runs in an empty workspace with no variable naming the case.
    ws = tmp_path / "ws"
    ws.mkdir()
    subprocess.run(["bash", str(judge / "fixture.sh")], cwd=ws, check=True, env={"PATH": "/usr/bin:/bin"})
    assert sorted(p.name for p in ws.iterdir()) == sorted(
        (*placement.DATA_FILES, "fit.py", "fit_output.txt"))


def test_a_body_swaps_only_the_body(tmp_path):
    body = tmp_path / "SKILL.md"
    body.write_text("---\nname: rietx\ndescription: x\n---\nshort\n")
    stamp = B.build(TREE, tmp_path / "p", body=body, only=["no-case-matches"])
    assert (tmp_path / "p" / "skills" / "rietx" / "SKILL.md").read_bytes() == body.read_bytes()
    assert stamp["tree_sha256"] != B.tree_sha256(TREE) and stamp["cases"] == []
    for ref in (TREE / "references").iterdir():
        assert (tmp_path / "p" / "skills" / "rietx" / "references" / ref.name).read_bytes() \
            == ref.read_bytes()


def test_the_build_clears_only_its_own_output(tmp_path):
    keep = tmp_path / "mine"
    keep.mkdir()
    (keep / "notes.txt").write_text("not a build")
    with pytest.raises(SystemExit, match="left alone"):
        B.build(TREE, keep, only=["none"])
    assert (keep / "notes.txt").exists()
    B.build(TREE, tmp_path / "p", only=["none"])
    B.build(TREE, tmp_path / "p", only=["none"])  # its own stamp: cleared and rebuilt


def test_the_suite_stays_out_of_the_wheel_and_the_sdist():
    cfg = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"]["hatch"]["build"]["targets"]
    assert cfg["wheel"]["packages"] == ["src/rietx"]
    assert "/tests" in cfg["sdist"]["exclude"]
    assert not any("eval_skill" in str(v) for v in cfg["wheel"].get("force-include", {}).values())


@pytest.mark.slow
def test_the_placement_episode_builds_and_fires_its_codes(tmp_path):
    """The real episode, fit and all: `build_episode` refuses an output missing
    a scored code, so this is also the guard that the episode still says what
    the rubric grades."""
    B.build(TREE, tmp_path / "p", only=["fap-judge"])
    files = tmp_path / "p" / "evals" / "fap-judge" / "files"
    out = (files / "fit_output.txt").read_text()
    assert all(f" {c} " in out for c in placement.SCORED_CODES)
