"""The worktree gate (.claude/hooks/worktree_only.py, WP-1410).

The gate exists because sessions launched in one checkout share its HEAD, index,
stash and tree.  That rationale is about *this* checkout, and until WP-1410 the
implementation was not: it refused an edit to any repository's main checkout,
which caught auto memory the moment ``~/.claude/projects/<slug>/memory`` was
symlinked into a configuration repo, and caught every unrelated clone besides.

Like ``test_workflow_hooks.py``, the hook is stdlib-only and lives outside the
package on purpose, so it is loaded by file path and ``refusal()`` is driven
directly rather than through a subprocess.  Real git fixtures under ``tmp_path``:
the gate asks git what a path belongs to, so a mocked answer would test nothing.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / ".claude" / "hooks" / "worktree_only.py"

_spec = importlib.util.spec_from_file_location("wp_worktree_only_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=wp@test", "-c", "user.name=wp",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd, check=True, capture_output=True,
    )


def _repo(path: Path) -> Path:
    """A real repository with one commit, so it has a HEAD to share."""
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    (path / "README.md").write_text("x\n")
    _git(path, "add", "README.md")
    _git(path, "commit", "-qm", "init")
    return path


@pytest.fixture
def trees(tmp_path, monkeypatch):
    """The session's own repo, a second repo, and memory symlinked into it."""
    session = _repo(tmp_path / "session")
    other = _repo(tmp_path / "other")

    _git(session, "worktree", "add", "-q",
         str(session / ".claude" / "worktrees" / "wt"), "-b", "wt")

    memory_target = other / "memory" / "session"
    memory_target.mkdir(parents=True)
    (memory_target / "MEMORY.md").write_text("# index\n")
    link_parent = tmp_path / "dotclaude" / "projects" / "-session"
    link_parent.mkdir(parents=True)
    (link_parent / "memory").symlink_to(memory_target)

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(session))
    return {
        "session": session,
        "other": other,
        "worktree": session / ".claude" / "worktrees" / "wt",
        "memory": link_parent / "memory",
    }


def _edit(path: Path, cwd: Path, tool: str = "Write") -> bool:
    """True when the gate refuses this edit."""
    payload = {"tool_name": tool, "tool_input": {"file_path": str(path)}, "cwd": str(cwd)}
    return hook.refusal(payload) is not None


def _bash(command: str, cwd: Path) -> bool:
    return hook.refusal({"tool_name": "Bash", "tool_input": {"command": command},
                         "cwd": str(cwd)}) is not None


def test_the_session_own_main_checkout_is_refused(trees):
    session = trees["session"]
    assert _edit(session / "README.md", session)
    assert _edit(session / "CLAUDE.md", session)
    assert _edit(session / "src" / "pkg" / "mod.py", session, tool="Edit")


def test_other_repositories_are_not_this_gate_business(trees):
    """WP-1410: three of the four cases below were refused before scoping."""
    session = trees["session"]
    assert not _edit(trees["memory"] / "note.md", session)
    assert not _edit(trees["other"] / "README.md", session)
    assert not _edit(trees["other"] / "deep" / "file.py", session, tool="Edit")


def test_a_worktree_and_an_unversioned_path_stay_writable(trees, tmp_path):
    session = trees["session"]
    assert not _edit(trees["worktree"] / "README.md", session)
    assert not _edit(tmp_path / "scratch" / "note.md", session)


def test_scope_falls_back_to_the_payload_cwd(trees, monkeypatch):
    """A session without CLAUDE_PROJECT_DIR still protects the tree it runs in."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    session = trees["session"]
    assert _edit(session / "README.md", session)
    assert not _edit(trees["other"] / "README.md", session)


def test_the_bash_branch_is_unchanged(trees):
    session = trees["session"]
    assert _bash("git commit -m x", session)
    assert not _bash(f"git -C {trees['other']} commit -m y", session)
    assert not _bash("ls", session)
    assert not _bash("git status", session)


def test_the_fail_open_announces_itself():
    """A gate disabled by an internal error must not look like a working one.

    The first draft of the scoping fix referenced an unimported ``os``; every
    case passed as allowed, the main checkout included, and nothing said so.
    The fail-open lives under ``if __name__ == "__main__"``, so it is reached
    here the way Claude Code reaches it: as a subprocess fed a payload that
    raises, which invalid JSON on stdin does inside ``main()``.
    """
    proc = subprocess.run(
        ["python3", str(HOOK_PATH)], input="not json", text=True, capture_output=True,
    )
    assert proc.returncode == 0, "must still fail open"
    assert "gate disabled by" in proc.stderr
