#!/usr/bin/env python3
"""PreToolUse gate: work happens in a worktree, never in the main checkout.

Sessions launched in one checkout share its HEAD, index, stash and working
tree, so one session's ``checkout``, ``reset --hard`` or ``git add -A`` lands
in another's work — four times on 2026-08-26, with four live sessions in the
main checkout at once.  Prose about this lost every time; a gate does not.

So the main checkout is **read-only for a session**.  An ``Edit``/``Write``/
``NotebookEdit`` whose file lives in it, or a ``Bash`` command that would move
its HEAD or index, is refused with the one-line fix: ``EnterWorktree`` (or
``claude -w`` from the terminal).  Reads, ``gh``, fetches and tests are
untouched, a worktree under ``.claude/worktrees/`` is not the main checkout,
and a file outside any repository is nobody's.  Stdlib-only and **fails
open**: any internal error lets the call through, because a bricked session
costs more than a missed refusal.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
# git verbs that move HEAD, the index or the working tree of the tree they run in
MUTATING = re.compile(
    r"(?:^|[;&|(\s])git\s+(?:-c\s+\S+\s+)*"
    r"(commit|checkout|switch|reset|stash|merge|rebase|cherry-pick|revert|add|rm|mv|restore|am|apply|clean)\b"
)

REASON = """Refused: this would change the main checkout, which sessions share.
Work in a worktree instead — call EnterWorktree (name it after the WP), or start
the session with `claude -w <name>`; the venv is built for you. The main checkout
is read-only for a session: %s"""


def _git(cwd: Path, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _existing_dir(path: Path) -> Path:
    for p in [path, *path.parents]:
        if p.is_dir():
            return p
    return Path("/")


def main_checkout_of(cwd: Path) -> Optional[Path]:
    """The main checkout's root for the repository ``cwd`` is in, else None."""
    common = _git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        return None
    return Path(common).resolve().parent


def is_in_main_checkout(path: Path) -> bool:
    """True when ``path`` belongs to the main checkout's own tree (not a worktree of it)."""
    where = _existing_dir(path.resolve())
    top = _git(where, "rev-parse", "--show-toplevel")
    main = main_checkout_of(where)
    return bool(top) and main is not None and Path(top).resolve() == main


def refusal(payload: dict) -> Optional[str]:
    """The reason to refuse this tool call, or None to let it through."""
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    if tool in EDIT_TOOLS:
        target = tool_input.get("file_path") or tool_input.get("notebook_path")
        if target and is_in_main_checkout(Path(target)):
            return REASON % f"`{target}`"
        return None
    if tool == "Bash":
        command = tool_input.get("command") or ""
        m = MUTATING.search(command)
        if not m or " -C " in command:
            return None
        cwd = Path(payload.get("cwd") or Path.cwd())
        if is_in_main_checkout(cwd):
            return REASON % f"`git {m.group(1)}` in {cwd}"
    return None


def main() -> int:
    payload = json.load(sys.stdin)
    reason = refusal(payload)
    if reason is None:
        return 0
    print(reason, file=sys.stderr)
    return 2  # the blocking exit code; stderr goes back to the session


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # fail open, deliberately: see the module docstring
        sys.exit(0)
