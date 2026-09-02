"""The SessionStart workflow scan (.claude/hooks/session_start.py, WP-1061).

WP-1116 gave it its second coverage rule (commit order, which sees a miss
inside the same day) and taught it the heading entry form; the tests below
carry the measurement that shaped each.

The hook is stdlib-only and lives outside the package on purpose (it must not
depend on the venv it checks), so it is loaded here by file path and its scan
functions are driven directly against tmp_path git fixtures — no subprocess
output parsing.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / ".claude" / "hooks" / "session_start.py"

_spec = importlib.util.spec_from_file_location("wp_session_start_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _git(cwd: Path, *args: str, date: str | None = None) -> None:
    env = os.environ.copy()
    if date is not None:
        env["GIT_AUTHOR_DATE"] = f"{date}T12:00:00"
        env["GIT_COMMITTER_DATE"] = f"{date}T12:00:00"
    subprocess.run(
        ["git", "-c", "user.email=wp@test", "-c", "user.name=wp",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd, env=env, check=True, capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs" / "wp").mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    return root


def write_wp(
    root: Path, num: str, glyph: str, entry_dates: list[str], with_log: bool = True
) -> None:
    text = f"# WP-{num} — fixture\n\nMilestone: v1.0 · Status: {glyph}\n\n## Goal\n\nx.\n"
    if with_log:
        text += "\n## Handover log\n\n"
        text += "".join(f"- **{d}** — an entry.\n" for d in entry_dates)
    (root / "docs" / "wp" / f"{num}-fixture.md").write_text(text, encoding="utf-8")


def commit_wp(root: Path, num: str, date: str, code: bool = False) -> None:
    """Commit the tree as one ``WP-NNNN:`` commit.

    ``code=True`` also writes a source file, which is what makes the commit
    *substantive* — a commit touching only the WP file, docs or ``.claude/`` is
    ritual and owes no handover of its own (hook ``_is_ritual``).
    """
    if code:
        src = root / "src" / "fixture.py"
        src.parent.mkdir(exist_ok=True)
        src.write_text(f"# {num} {date}\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"WP-{num}: fixture work", date=date)


def make_venv(root: Path, target: Path) -> None:
    sp = root / ".venv" / "lib" / "python3.12" / "site-packages"
    sp.mkdir(parents=True)
    (sp / "_editable_impl_rietx.pth").write_text(f"{target}\n", encoding="utf-8")


def test_healthy_state_renders_one_line(repo: Path) -> None:
    write_wp(repo, "9001", "✅ 2026-08-02 — done", ["2026-08-02"])
    commit_wp(repo, "9001", "2026-08-01")
    make_venv(repo, repo / "src")
    assert hook.handover_findings(repo) == []
    out = hook.render(repo)
    assert len(out.splitlines()) == 1
    assert "venv ok" in out
    assert "⚠" not in out


def test_open_wp_with_later_commit_flags_repair(repo: Path) -> None:
    write_wp(repo, "9002", "🔄 2026-08-01 — in flight", ["2026-08-01"])
    commit_wp(repo, "9002", "2026-08-03")
    (finding,) = hook.handover_findings(repo)
    assert finding.severity == "repair"
    assert (finding.wp, finding.glyph) == ("9002", "🔄")
    assert (finding.commit_date, finding.entry_date) == ("2026-08-03", "2026-08-01")
    out = hook.render(repo)
    assert hook.REPAIR_HINT in out
    assert hook.in_flight_wps(repo) == ["9002"]
    assert "in flight: WP-9002" in out


def test_open_wp_with_no_handover_log_flags_repair(repo: Path) -> None:
    # the shape the first live run found on main: ⬜ WP, commits, no log section
    write_wp(repo, "9003", "⬜", [], with_log=False)
    commit_wp(repo, "9003", "2026-08-03")
    (finding,) = hook.handover_findings(repo)
    assert finding.severity == "repair"
    assert finding.entry_date is None
    assert "no handover entry" in hook.render(repo)


def test_closed_wp_with_later_commit_is_soft_note(repo: Path) -> None:
    write_wp(repo, "9004", "✅ 2026-08-01 — shipped", ["2026-08-01"])
    commit_wp(repo, "9004", "2026-08-03")
    (finding,) = hook.handover_findings(repo)
    assert finding.severity == "note"
    out = hook.render(repo)
    assert "post-close commits not in the log" in out
    assert hook.REPAIR_HINT not in out


def test_same_day_miss_is_caught_by_commit_order(repo: Path) -> None:
    """The pre-WP-1116 blind spot: three sessions in one day is this repo's
    normal cadence (WP-1109, 2026-08-20), so a day-dated rule could only catch
    a miss that survived past midnight.  Order catches it inside the day."""
    write_wp(repo, "9005", "🔄 2026-08-03 — in flight", ["2026-08-03"])
    commit_wp(repo, "9005", "2026-08-03")  # the handover: touches the WP file
    commit_wp(repo, "9005", "2026-08-03", code=True)  # then work, un-handed-over
    (finding,) = hook.handover_findings(repo)
    assert (finding.severity, finding.basis) == ("repair", "order")
    assert finding.entry_date == "2026-08-03"  # same day, and still flagged
    assert "WP file not touched since" in hook.render(repo)


def test_ritual_commits_after_the_handover_do_not_flag(repo: Path) -> None:
    """The handover ritual spans several commits — a CLAUDE.md rule, the
    ROADMAP sync, a merge — and they land *after* the WP file's own edit.
    Requiring the WP file to come last flagged three healthy WPs on this
    repo's history (1016, 1059, 1078)."""
    write_wp(repo, "9006", "✅ 2026-08-03 — shipped", ["2026-08-03"])
    commit_wp(repo, "9006", "2026-08-03", code=True)
    write_wp(repo, "9006", "✅ 2026-08-03 — shipped", ["2026-08-03", "2026-08-03"])
    commit_wp(repo, "9006", "2026-08-03")  # the handover entry
    (repo / "CLAUDE.md").write_text("a standing rule.\n", encoding="utf-8")
    commit_wp(repo, "9006", "2026-08-03")  # protocol step 6, its own commit
    assert hook.handover_findings(repo) == []


def test_heading_entries_count_as_entries(repo: Path) -> None:
    """A multi-session day needs a per-session heading, which a date bullet
    cannot express.  Reading only bullets is what made this scan flag WP-1109
    and WP-1110 on 2026-08-20 when both had been handed over."""
    path = repo / "docs" / "wp" / "9007-fixture.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# WP-9007 — fixture\n\nMilestone: v1.1 · Status: 🔄 2026-08-03 — x\n\n"
        "## Handover log\n\n"
        "### 2026-08-03 (second session) — more\n\nbody.\n\n"
        "### 2026-08-03 — first\n\nbody.\n",
        encoding="utf-8",
    )
    commit_wp(repo, "9007", "2026-08-03")
    assert hook.wp_file_state(repo, "9007")[2] == "2026-08-03"
    assert hook.handover_findings(repo) == []


def test_repo_line_measures_against_origin_main(repo: Path, tmp_path: Path) -> None:
    """The local ``main`` is whatever was last fetched into it; on 2026-08-26 it
    sat 91 commits stale and the scan called a merged branch "ahead 90"."""
    write_wp(repo, "9008", "✅ 2026-08-02 — done", ["2026-08-02"])
    commit_wp(repo, "9008", "2026-08-01")
    _git(repo, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    _git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "checkout", "-q", "-b", "feature")
    make_venv(repo, repo / "src")
    assert "ahead 0 / behind 0 vs origin/main · merged" in hook.repo_line(repo)
    commit_wp(repo, "9008", "2026-08-02", code=True)
    line = hook.repo_line(repo)
    assert "ahead 1 / behind 0 vs origin/main" in line and "merged" not in line


def test_sessions_sharing_assigns_a_cwd_to_its_deepest_worktree(tmp_path: Path) -> None:
    """``.claude/worktrees/pr-bench`` lies *under* the main checkout and is a
    different tree, so containment alone would report a bench session to a
    main-checkout session and the reverse.  Deepest registered root wins."""
    main = tmp_path / "repo"
    bench = main / ".claude" / "worktrees" / "pr-bench"
    bench.mkdir(parents=True)
    sessions = [
        hook.Session(1, "05-04:02:33", str(main)),
        hook.Session(2, "00:10", str(bench)),
        hook.Session(3, "00:05", str(main / "src")),  # below the root: still its tree
        hook.Session(4, "00:01", str(tmp_path / "elsewhere")),
        hook.Session(5, "00:01", str(main)),  # the session running the scan
    ]
    roots = [main, bench]
    assert [s.pid for s in hook.sessions_sharing(main, sessions, roots, {5})] == [1, 3]
    assert [s.pid for s in hook.sessions_sharing(bench, sessions, roots, set())] == [2]
    out = hook.SHARED_HINT
    assert "one session per tree" in out


def test_session_rows_skip_the_pty_host_helpers() -> None:
    """A session's background shells run as ``claude --bg-pty-host``; one such
    orphan sat in the checkout for five days (pid 48273, 2026-08-26)."""
    ps = (
        "15964 11:44 /Users/yue/.local/share/claude/ClaudeCode.app/Contents/MacOS/claude"
        " --bg-pty-host /tmp/cc-x\n"
        "45077 06:46:12 claude\n"
        "17432 05:10 claude --model sonnet\n"
        "  999 00:01 /usr/bin/python3 claude-something\n"
    )
    assert hook._session_rows(ps) == [(45077, "06:46:12"), (17432, "05:10")]


def test_hook_cwd_without_a_payload_is_none() -> None:
    """Under pytest stdin is not a hook pipe; the read must answer None, and
    quickly, rather than raise or wait."""
    assert hook.hook_cwd() is None


# --------------------------------------------------------------------------- #
# The worktree-only gate (.claude/hooks/worktree_only.py): the main checkout is
# read-only for a session.
# --------------------------------------------------------------------------- #

_gate_spec = importlib.util.spec_from_file_location(
    "worktree_only_hook", ROOT / ".claude" / "hooks" / "worktree_only.py"
)
gate = importlib.util.module_from_spec(_gate_spec)
_gate_spec.loader.exec_module(gate)


@pytest.fixture
def repo_with_worktree(repo: Path) -> tuple[Path, Path]:
    (repo / "README").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    wt = repo / ".claude" / "worktrees" / "wp9001"
    _git(repo, "worktree", "add", "-q", "-b", "wp9001", str(wt))
    return repo, wt


def _edit(path: Path) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path)}}


def _bash(command: str, cwd: Path) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}


def test_gate_refuses_edits_in_the_main_checkout_only(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path
) -> None:
    main, wt = repo_with_worktree
    assert gate.refusal(_edit(main / "src" / "new.py")) is not None  # dir need not exist
    assert gate.refusal(_edit(main / "README")) is not None
    assert gate.refusal(_edit(wt / "README")) is None  # a worktree under the checkout
    assert gate.refusal(_edit(tmp_path / "elsewhere" / "note.md")) is None  # no repo
    assert gate.refusal({"tool_name": "Read", "tool_input": {"file_path": str(main / "README")}}) is None


def test_gate_refuses_head_moving_git_in_the_main_checkout_only(
    repo_with_worktree: tuple[Path, Path],
) -> None:
    main, wt = repo_with_worktree
    assert gate.refusal(_bash("git add -A && git commit -m x", main)) is not None
    assert gate.refusal(_bash("git checkout -b feature", main)) is not None
    assert gate.refusal(_bash("git stash push -u", main)) is not None
    assert gate.refusal(_bash("git log --oneline -3 && gh pr list", main)) is None
    assert gate.refusal(_bash("git fetch origin main && git worktree list", main)) is None
    assert gate.refusal(_bash("git commit -m x", wt)) is None
    # addressed at another tree by -C: that tree's business, not this gate's
    assert gate.refusal(_bash(f"git -C {wt} reset --hard origin/main", main)) is None


def test_gate_reason_names_the_fix(repo_with_worktree: tuple[Path, Path]) -> None:
    main, _ = repo_with_worktree
    reason = gate.refusal(_edit(main / "README"))
    assert "EnterWorktree" in reason and "claude -w" in reason


def test_venv_pointer_resolution(repo: Path, tmp_path: Path) -> None:
    assert "no .venv" in hook.venv_flag(repo)
    make_venv(repo, tmp_path / "other-tree" / "src")
    flag = hook.venv_flag(repo)
    assert "not this tree" in flag
    assert hook.VENV_FIX in flag  # the fix is printed verbatim
    (
        repo / ".venv" / "lib" / "python3.12" / "site-packages"
        / "_editable_impl_rietx.pth"
    ).write_text(f"{repo / 'src'}\n", encoding="utf-8")
    assert hook.venv_flag(repo) is None


# --------------------------------------------------------------------------- #
# The parser against the REAL corpus.
#
# Every test above builds its own WP file, in the one spelling the parser was
# written for -- so between them they could not notice that no WP in this repo
# uses it.  TEMPLATE.md writes `- **YYYY-MM-DD**`; every real handover log
# writes `### YYYY-MM-DD — title`, so the scan read the whole corpus as having
# no handover entries and flagged every open WP with recent commits as
# `repair first`.  tests/CLAUDE.md § Guards that go quiet: a guard that pins a
# copy of a string living somewhere else tests the copy, not the thing.
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[1]


def _wp_files_with_a_log() -> list[Path]:
    out = []
    for path in sorted((REPO_ROOT / "docs" / "wp").glob("[0-9]*.md")):
        _, sep, log = path.read_text(encoding="utf-8").partition("## Handover log")
        if sep and log.strip():
            out.append(path)
    return out


def test_the_parser_reads_every_real_handover_log() -> None:
    """The scan must find an entry date in every WP that has entries.

    This is the guard the synthetic tests cannot be: it reads the corpus the
    hook actually runs against, so a WP-file convention that drifts away from
    the parser fails here instead of going quiet.
    """
    files = _wp_files_with_a_log()
    assert len(files) > 5, f"expected a real corpus, found {len(files)} WP logs"
    unread = [
        p.name for p in files
        if hook.wp_file_state(REPO_ROOT, p.name[:4])[2] is None
    ]
    assert not unread, (
        "handover logs the session-start scan cannot read a date out of "
        f"(so every open one of them is flagged 'repair first'): {unread}"
    )


def test_both_entry_spellings_parse() -> None:
    """The template's bullet and the corpus's heading are both entries.

    Pinned together so neither can be dropped in favour of the other without
    a red test -- the drift above was silent precisely because only one of
    them was ever exercised.
    """
    assert hook._ENTRY_DATE_RE.findall("- **2026-08-20** — an entry.") == ["2026-08-20"]
    assert hook._ENTRY_DATE_RE.findall("### 2026-08-20 — an entry") == ["2026-08-20"]
    assert hook._ENTRY_DATE_RE.findall("## 2026-08-20 — an entry") == ["2026-08-20"]
    # not an entry: prose that merely opens with a date, and an undated heading
    assert hook._ENTRY_DATE_RE.findall("2026-08-20 was the day") == []
    assert hook._ENTRY_DATE_RE.findall("### the third session") == []


# --------------------------------------------------------------------------- #
# The handover-owed nudge (.claude/hooks/handover_owed.py): a WP session's last
# act is /wp-handover, not a summary of it.  Fires on Stop, once, only where a
# WP branch is at rest with the command never run (measured 2026-09-02).
# --------------------------------------------------------------------------- #

_owed_spec = importlib.util.spec_from_file_location(
    "handover_owed_hook", ROOT / ".claude" / "hooks" / "handover_owed.py"
)
owed = importlib.util.module_from_spec(_owed_spec)
_owed_spec.loader.exec_module(owed)


@pytest.fixture
def wp_branch_at_rest(repo: Path, tmp_path: Path) -> tuple[Path, Path]:
    """A pushed ``wp9001`` worktree carrying one substantive WP commit."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    (repo / "README").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "-u", "origin", "main")
    wt = repo / ".claude" / "worktrees" / "wp9001"
    _git(repo, "worktree", "add", "-q", "-b", "wp9001-fixture", str(wt))
    (wt / "docs" / "wp").mkdir(parents=True, exist_ok=True)
    write_wp(wt, "9001", "🔄", ["2026-09-02"])
    commit_wp(wt, "9001", "2026-09-02", code=True)
    _git(wt, "push", "-q", "-u", "origin", "wp9001-fixture")
    return repo, wt


def _stop(tree: Path, transcript: Path | None = None, **extra) -> dict:
    payload = {"cwd": str(tree), "session_id": "s1", "hook_event_name": "Stop"}
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    payload.update(extra)
    return payload


def _transcript(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_nudge_fires_on_a_wp_branch_at_rest(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    _, wt = wp_branch_at_rest
    t = _transcript(tmp_path, "quiet.jsonl", '{"type":"assistant","text":"done"}\n')
    reason = owed.nudge(_stop(wt, t))
    assert reason is not None
    assert "WP-9001" in reason and "wp9001-fixture" in reason
    assert "/wp-handover 9001" in reason  # the command, spelled to be run


def test_nudge_names_the_branch_s_wp_not_the_newest_commit_s(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """A session that also touched another WP is still handed over on its own."""
    _, wt = wp_branch_at_rest
    _git(wt, "branch", "-m", "wp9001-fixture", "wp9002-fixture")
    t = _transcript(tmp_path, "quiet.jsonl", "{}\n")
    reason = owed.nudge(_stop(wt, t))
    assert reason is not None and "WP-9002" in reason  # not 9001, the commit's


def test_the_hook_s_own_source_does_not_look_like_a_handover(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """Reading the hook or these tests must not silence the hook.

    Both sentinels are assembled from fragments precisely so that neither file
    contains one; spelled out, they matched the transcript of every session
    that opened either, which is a false negative in the one place it hurts —
    the session maintaining the gate (measured 2026-09-02).
    """
    for path in (
        ROOT / ".claude" / "hooks" / "handover_owed.py",
        Path(__file__),
    ):
        assert not owed._HANDOVER_RAN_RE.search(path.read_text(encoding="utf-8")), path
    # and the reason it prints is not a match either, or one nudge silences the next
    _, wt = wp_branch_at_rest
    reason = owed.nudge(_stop(wt, _transcript(tmp_path, "quiet.jsonl", "{}\n")))
    assert reason and not owed._HANDOVER_RAN_RE.search(reason)


def test_nudge_is_silent_once_the_command_has_run(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    _, wt = wp_branch_at_rest
    # Assembled, not spelled: a literal here would land in the transcript of
    # any session that reads this file and silence the hook for it.
    cmd = "wp-" + "handover"
    for name, body in (
        ("skill.jsonl", '{"name":"Skill","input":{"skill": "%s"}}\n' % cmd),
        ("typed.jsonl", f"<command-{'name'}>/{cmd}</command-name>\n"),
    ):
        assert owed.nudge(_stop(wt, _transcript(tmp_path, name, body))) is None
    # merely reading or naming the command is not running it
    named = '{"name":"Bash","input":{"command":"cat .claude/commands/wp-handover.md"}}\n'
    assert owed.nudge(_stop(wt, _transcript(tmp_path, "named.jsonl", named))) is not None


def test_nudge_never_blocks_two_stops_in_a_row(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    _, wt = wp_branch_at_rest
    t = _transcript(tmp_path, "quiet.jsonl", "{}\n")
    assert owed.nudge(_stop(wt, t, stop_hook_active=True)) is None


def test_nudge_is_silent_mid_flight(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """Dirty tree or unpushed work is a session still working, not one ending."""
    _, wt = wp_branch_at_rest
    t = _transcript(tmp_path, "quiet.jsonl", "{}\n")
    (wt / "src" / "fixture.py").write_text("# edited\n", encoding="utf-8")
    assert owed.nudge(_stop(wt, t)) is None
    commit_wp(wt, "9001", "2026-09-02")
    assert owed.nudge(_stop(wt, t)) is None  # clean again, but unpushed
    _git(wt, "push", "-q")
    assert owed.nudge(_stop(wt, t)) is not None


def test_nudge_needs_a_wp_branch_that_added_something(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    main, wt = wp_branch_at_rest
    t = _transcript(tmp_path, "quiet.jsonl", "{}\n")
    assert owed.nudge(_stop(main, t)) is None  # main adds nothing to origin/main
    _git(wt, "branch", "-m", "wp9001-fixture", "tidy-up")
    assert owed.nudge(_stop(wt, t)) is None  # commits, but not a WP branch
    assert owed.nudge(_stop(tmp_path, t)) is None  # not a repository at all


def test_nudge_does_not_require_a_wp_prefixed_commit(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """A docs-only WP session owes its handover as much as a code one.

    Its commits are ``docs:``/``tooling:`` (39 of the last 400 on main), and
    the branch — not the commit subject — is what names the WP.
    """
    main, wt = wp_branch_at_rest
    _git(wt, "reset", "-q", "--hard", "origin/main")
    (wt / "note.md").write_text("prose\n", encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "docs: a paragraph")
    _git(wt, "push", "-q", "--force")
    reason = owed.nudge(_stop(wt, _transcript(tmp_path, "quiet.jsonl", "{}\n")))
    assert reason is not None and "WP-9001" in reason


def test_nudge_asks_once_per_head(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """A session that says "not finished" is not asked again until work lands."""
    _, wt = wp_branch_at_rest
    t = _transcript(tmp_path, "quiet.jsonl", "{}\n")
    assert owed.nudge(_stop(wt, t)) is not None
    assert owed.nudge(_stop(wt, t)) is None
    assert owed.nudge(_stop(wt, t, session_id="s2")) is not None  # a new session asks
    commit_wp(wt, "9001", "2026-09-03", code=True)
    _git(wt, "push", "-q")
    assert owed.nudge(_stop(wt, t)) is not None  # more work landed


def test_nudge_fails_silent_on_a_signal_it_cannot_measure(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """No readable transcript reads as "ran": never block on an unmeasured claim."""
    _, wt = wp_branch_at_rest
    assert owed.nudge(_stop(wt)) is None
    assert owed.nudge(_stop(wt, tmp_path / "missing.jsonl")) is None
