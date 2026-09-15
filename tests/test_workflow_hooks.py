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
import sys
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


def test_gate_guards_this_checkout_and_not_another_repository(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path
) -> None:
    """WP-1410: the gate exists because sessions share ONE checkout's tree.

    Before scoping it refused any repository's main checkout, which caught auto
    memory the moment ``~/.claude/projects/<slug>/memory`` was symlinked into a
    configuration repo, and caught every unrelated clone besides. The session's
    own checkout must stay refused; the rest are not this gate's business.
    """
    main, _ = repo_with_worktree
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    (other / "README").write_text("x\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "init")

    # auto memory, as it is once linked into a repo shared between machines
    memory = tmp_path / "dotclaude" / "projects" / "-main"
    memory.mkdir(parents=True)
    (memory / "memory").symlink_to(other / "notes")
    (other / "notes").mkdir()

    def edit_from_session(path: Path) -> dict:
        return {"tool_name": "Edit", "tool_input": {"file_path": str(path)},
                "cwd": str(main)}

    assert gate.refusal(edit_from_session(main / "README")) is not None
    assert gate.refusal(edit_from_session(memory / "memory" / "note.md")) is None
    assert gate.refusal(edit_from_session(other / "README")) is None


def test_gate_without_a_cwd_guards_every_checkout(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path
) -> None:
    """No ``cwd`` is no claim about the session, so the gate fails closed.

    Scoping reads the payload's ``cwd`` and nothing else. ``CLAUDE_PROJECT_DIR``
    describes the process rather than the call, so under a test harness it named
    a repository the payload never mentioned and allowed an edit that should
    have been refused.

    *Every* checkout, which is what fails closed means: the second repository
    below is the assertion the name makes, and without it a fallback flipped to
    "allow when the scope is unknown" would leave this test green.
    """
    main, wt = repo_with_worktree
    other = tmp_path / "another"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    (other / "README").write_text("x\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "init")

    assert gate.refusal(_edit(main / "README")) is not None
    assert gate.refusal(_edit(other / "README")) is not None
    assert gate.refusal(_edit(wt / "README")) is None


def test_gate_fail_open_announces_itself() -> None:
    """A gate disabled by an internal error must not look like a working one.

    The first draft of WP-1410's scoping referenced an unimported ``os``; every
    case passed as allowed, the main checkout included, and nothing said so. The
    fail-open stays, because a bricked session costs more than a missed refusal.
    Reached here as a subprocess fed a payload that raises, which is how Claude
    Code reaches it.

    The exit code is the whole message. A ``PreToolUse`` hook's stderr reaches
    the session only on a non-zero, non-2 exit, which Claude Code renders as a
    hook error and runs the tool anyway; on exit 0 the line goes to the debug
    log and announces nothing. 2 would block, which is not fail-open.
    """
    proc = subprocess.run(
        [sys.executable, str(ROOT / ".claude" / "hooks" / "worktree_only.py")],
        input="not json", text=True, capture_output=True,
    )
    assert proc.returncode != 2, "must still fail open"
    assert proc.returncode != 0, "exit 0 sends stderr to the debug log, not the session"
    assert "gate disabled by" in proc.stderr


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


# --------------------------------------------------------------------------- #
# The WP claim (.claude/hooks/wp_claim.py, WP-1422): one WP per session, so two
# sessions never spend a day on the same work.
# --------------------------------------------------------------------------- #

_claim_spec = importlib.util.spec_from_file_location(
    "wp_claim_hook", ROOT / ".claude" / "hooks" / "wp_claim.py"
)
claim = importlib.util.module_from_spec(_claim_spec)
_claim_spec.loader.exec_module(claim)

_create_spec = importlib.util.spec_from_file_location(
    "worktree_create_hook", ROOT / ".claude" / "hooks" / "worktree_create.py"
)
create = importlib.util.module_from_spec(_create_spec)
_create_spec.loader.exec_module(create)


@pytest.mark.parametrize(
    "name,wp",
    [
        ("wp1422-the-wp-two-sessions-picked", "1422"),
        ("1331-landing-page", "1331"),  # the repo writes both spellings
        ("wp-1422-x", "1422"),
        ("1422", "1422"),
        ("pr-bench", None),  # the bench claims nothing and must not
        ("termplot", None),
        ("wpem-benchmark", None),  # four digits required, not "any digits"
        ("main", None),
    ],
)
def test_a_name_declares_a_wp_or_declares_nothing(name: str, wp: str | None) -> None:
    assert claim.wp_from_name(name) == wp


@pytest.fixture
def two_trees(repo: Path) -> tuple[Path, Path, Path]:
    """A checkout with two WP worktrees, one of them nested inside the other.

    Nested because this repo really does that — ``.claude/worktrees/wp1402-x/
    .claude/worktrees/wp1403-y`` on 2026-09-15 — and containment alone would
    then assign the inner tree's session to the outer one as well.
    """
    (repo / "README").write_text("x\n", encoding="utf-8")
    # The real repo's rule, so the porcelain assertion below is about the claim
    # store and not about the fixture's own worktree directories.
    (repo / ".gitignore").write_text(".claude/worktrees/\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    outer = repo / ".claude" / "worktrees" / "wp9101-outer"
    _git(repo, "worktree", "add", "-q", "-b", "wp9101-outer", str(outer))
    inner = outer / ".claude" / "worktrees" / "wp9102-inner"
    _git(repo, "worktree", "add", "-q", "-b", "wp9102-inner", str(inner))
    return repo, outer, inner


def _sess(pid: int, cwd: Path, age: str = "01:00"):
    return hook.Session(pid, age, str(cwd))


def _porcelain(tree: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"], cwd=tree, capture_output=True, text=True
    ).stdout.strip()


def test_the_main_checkout_claims_nothing(two_trees: tuple[Path, Path, Path]) -> None:
    """It is read-only for a session (worktree_only.py), so it holds no WP."""
    main, _outer, _inner = two_trees
    trees = claim.worktree_branches(main)
    assert claim.main_checkout(trees) == main.resolve()
    assert [h.wp for h in claim.occupancy(trees, [], set(), {}, main)] == ["9101", "9102"]


def test_a_session_holds_the_deepest_tree_that_contains_it(
    two_trees: tuple[Path, Path, Path]
) -> None:
    main, outer, inner = two_trees
    trees = claim.worktree_branches(main)
    sessions = [_sess(11, outer), _sess(22, inner / "src"), _sess(33, main)]
    by_wp = {h.wp: h for h in claim.occupancy(trees, sessions, set(), {}, main)}
    assert [s.pid for s in by_wp["9101"].sessions] == [11]
    assert [s.pid for s in by_wp["9102"].sessions] == [22]


def test_the_scanning_session_is_not_reported_as_a_holder(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """Excluded by pid, so a session is never blocked by its own presence."""
    main, outer, _inner = two_trees
    trees = claim.worktree_branches(main)
    holders = claim.occupancy(trees, [_sess(11, outer)], {11}, {}, main)
    assert [h.held for h in holders] == [False, False]


def test_a_claim_overrides_the_branch_the_tree_is_on(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """The measured case: a tree resumed for a different WP than it is named
    for (2026-09-15, tree ``wp1404-*``, branch ``wp1413-*``, working 1413)."""
    main, outer, _inner = two_trees
    assert claim.write_claim(main, outer, "9199", by="session") is not None
    trees = claim.worktree_branches(main)
    held = {
        h.worktree: h
        for h in claim.occupancy(trees, [], set(), claim.read_claims(main), main)
    }[outer.resolve()]
    assert (held.wp, held.source, held.branch) == ("9199", "claim", "wp9101-outer")

    assert claim.release_claim(main, outer) is True
    assert claim.release_claim(main, outer) is False  # idempotent
    back = {
        h.worktree: h
        for h in claim.occupancy(trees, [], set(), claim.read_claims(main), main)
    }[outer.resolve()]
    assert (back.wp, back.source) == ("9101", "branch")


def test_the_store_is_shared_by_every_worktree_and_tracked_by_none(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """Git guarantees the common dir is one directory for the whole repository,
    which is why a claim crosses branches that never merge."""
    main, outer, inner = two_trees
    dirs = {claim.claims_dir(t) for t in (main, outer, inner)}
    assert len(dirs) == 1 and None not in dirs
    claim.write_claim(main, outer, "9199")
    for tree in (main, outer, inner):
        assert claim.read_claims(tree, prune=False)[outer.resolve()].wp == "9199"
        assert _porcelain(tree) == ""


def test_a_claim_dies_with_its_worktree(two_trees: tuple[Path, Path, Path]) -> None:
    """Pruned on read, so the ledger can never describe a tree that is gone and
    there is no expiry policy to tune.  A stale claim would be a false alarm,
    and a false alarm costs more than no alarm (session_start.py's docstring)."""
    main, outer, _inner = two_trees
    claim.write_claim(main, outer, "9199")
    _git(main, "worktree", "remove", "--force", str(outer))
    assert claim.read_claims(main) == {}
    assert list(claim.claims_dir(main).glob("*.json")) == []


def test_an_unreadable_claim_is_dropped_rather_than_raised(
    two_trees: tuple[Path, Path, Path]
) -> None:
    main, outer, _inner = two_trees
    claim.write_claim(main, outer, "9199")
    junk = claim.claims_dir(main) / "junk.json"
    junk.write_text("{not json", encoding="utf-8")
    assert set(claim.read_claims(main)) == {outer.resolve()}
    assert not junk.exists()


def test_two_live_trees_on_one_wp_are_the_clash(
    two_trees: tuple[Path, Path, Path]
) -> None:
    main, outer, inner = two_trees
    claim.write_claim(main, inner, "9101")  # inner now says it is on outer's WP
    trees = claim.worktree_branches(main)
    holders = claim.occupancy(
        trees, [_sess(11, outer), _sess(22, inner)], set(), claim.read_claims(main), main
    )
    assert claim.clashes(holders) == ["9101"]
    assert claim.clashes([h for h in holders if h.worktree == outer.resolve()]) == []


def test_a_closed_wp_whose_tree_was_kept_is_not_reported(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """Four of this repo's six trees on 2026-09-15 were finished work whose
    directory had not been removed.  Printing them puts the live row fifth."""
    main, _outer, inner = two_trees
    trees = claim.worktree_branches(main)
    holders = claim.occupancy(trees, [_sess(11, inner)], set(), {}, main)
    rows = claim.bears_on_a_clash(holders, {"9101": "✅", "9102": "✅"})
    assert [(h.wp, h.held) for h in rows] == [("9102", True)]  # held survives closing
    assert [h.wp for h in claim.bears_on_a_clash(holders, {"9101": "🔄"})] == ["9101", "9102"]


def test_held_elsewhere_excludes_this_tree(two_trees: tuple[Path, Path, Path]) -> None:
    main, outer, inner = two_trees
    trees = claim.worktree_branches(main)
    holders = claim.occupancy(trees, [_sess(11, outer), _sess(22, inner)], set(), {}, main)
    assert [h.wp for h in claim.held_elsewhere(holders, outer)] == ["9102"]
    assert [h.wp for h in claim.held_elsewhere(holders, None)] == ["9101", "9102"]


def test_the_refusal_names_the_holder_and_the_way_past_it(
    two_trees: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal with no override is a trap: a session parked idle in a tree it
    has finished with would block the next one for ever."""
    main, outer, _inner = two_trees
    monkeypatch.setattr(create.session_start, "live_sessions", lambda: [_sess(11, outer)])
    monkeypatch.setattr(create.session_start, "_ancestors", lambda: set())

    message = create.clash_refusal(main, "9101")
    assert "pid 11" in message and "wp9101-outer" in message
    assert f"release --worktree {outer.resolve()}" in message

    assert create.clash_refusal(main, "9102") == ""  # a dormant tree never refuses
    assert create.clash_refusal(main, "9999") == ""  # nothing at all


def test_the_session_start_line_is_silent_without_a_second_tree(repo: Path) -> None:
    """A machine running one session prints nothing here, so the flag stays
    worth reading on the day it fires."""
    write_wp(repo, "9001", "✅ 2026-08-02 — done", ["2026-08-02"])
    commit_wp(repo, "9001", "2026-08-01")
    make_venv(repo, repo / "src")
    assert hook.claim_lines(repo) == []
    assert len(hook.render(repo).splitlines()) == 1


def test_the_session_start_line_names_the_other_session(
    two_trees: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    main, outer, inner = two_trees
    write_wp(main, "9102", "🔄 2026-09-15 — in flight", ["2026-09-15"])
    monkeypatch.setattr(hook, "live_sessions", lambda: [_sess(22, inner, "03:14")])
    monkeypatch.setattr(hook, "_ancestors", lambda: set())

    (line,) = hook.claim_lines(outer)
    assert "WP-9102 held by pid 22 up 03:14" in line
    assert "wp9102-inner" in line and hook.CLAIM_HINT in line
    assert hook.claim_lines(inner) == []  # its own tree is not news to it


def test_a_wp_tree_with_no_wp_branch_falls_back_to_its_own_name(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """The third ``source`` value, which nothing else reaches.

    A detached HEAD has no branch to read, and a branch renamed to something
    that names no WP is the same case.  Declared as a vocabulary member, so it
    needs a producer and a test naming it (WP-1076's class).
    """
    main, outer, _inner = two_trees
    _git(outer, "checkout", "-q", "--detach")
    trees = claim.worktree_branches(main)
    assert trees[outer.resolve()] is None
    held = {h.worktree: h for h in claim.occupancy(trees, [], set(), {}, main)}[outer.resolve()]
    assert (held.wp, held.source, held.branch) == ("9101", "tree", None)
    assert held.provenance == "from the tree"


def test_a_claim_says_who_declared_it_and_when(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """``by`` and ``declared`` are written into every claim; this reads them.

    The create hook's automatic claim and a session's correction are the two
    cases, and ``source`` alone says "claim" for both.
    """
    main, outer, inner = two_trees
    claim.write_claim(main, outer, "9199", by="worktree")
    claim.write_claim(main, inner, "9198", by="session")
    stored = claim.read_claims(main)
    assert {c.by for c in stored.values()} == {"worktree", "session"}

    trees = claim.worktree_branches(main)
    by_path = {h.worktree: h for h in claim.occupancy(trees, [], set(), stored, main)}
    # The stored date, not today's: this asserts that provenance renders the
    # fields the claim carries, never that the clock agrees with itself.
    when = stored[outer.resolve()].declared
    assert by_path[outer.resolve()].provenance == f"from the claim, by worktree {when}"
    assert by_path[inner.resolve()].provenance == f"from the claim, by session {when}"
    assert claim.describe(by_path[outer.resolve()], main).endswith(
        f"(from the claim, by worktree {when})"
    )
