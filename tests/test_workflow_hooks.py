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
    (sp / "_editable_impl_pxrd_refine.pth").write_text(f"{target}\n", encoding="utf-8")


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
        / "_editable_impl_pxrd_refine.pth"
    ).write_text(f"{repo / 'src'}\n", encoding="utf-8")
    assert hook.venv_flag(repo) is None
