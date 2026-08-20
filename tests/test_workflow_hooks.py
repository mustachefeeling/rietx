"""The SessionStart workflow scan (.claude/hooks/session_start.py, WP-1061).

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


def commit_wp(root: Path, num: str, date: str) -> None:
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


def test_same_day_commit_and_entry_is_invisible(repo: Path) -> None:
    # The documented blind spot, pinned as such: entries are day-dated, so a
    # commit followed by a missed handover on the same day cannot be seen.
    write_wp(repo, "9005", "🔄 2026-08-03 — in flight", ["2026-08-03"])
    commit_wp(repo, "9005", "2026-08-03")
    assert hook.handover_findings(repo) == []


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
