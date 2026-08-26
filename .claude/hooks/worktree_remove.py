#!/usr/bin/env python3
"""WorktreeRemove hook: the twin of worktree_create.py.

Claude Code calls it when a worktree it created through the create hook is to
go — at session exit on the user's say-so, or when a subagent finishes.  The
tree goes; the **branch stays**, because a branch is the only record of work
not yet pushed and deleting it is the user's call (``git branch -d`` when the
PR has merged).  Never blocks: Claude Code ignores this hook's exit code, so
a failure is printed and left for ``git worktree prune``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    payload = json.load(sys.stdin)
    path = payload.get("path") or payload.get("cwd")
    if not path:
        print("worktree_remove: no path in payload", file=sys.stderr)
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    proc = subprocess.run(
        ["git", "-C", str(root), "worktree", "remove", "--force", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"worktree_remove: {proc.stderr.strip()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"worktree_remove: {exc}", file=sys.stderr)
        sys.exit(0)
