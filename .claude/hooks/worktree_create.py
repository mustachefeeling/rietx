#!/usr/bin/env python3
"""WorktreeCreate hook: make the worktree Claude Code asked for, with its venv.

Claude Code hands the creation to this hook whenever one is configured — for
``claude -w``, ``EnterWorktree``, a subagent with ``isolation: worktree`` — and
uses whatever path it prints as the session's working directory.  Two things
are gained over the built-in creation, and they are why this file exists:

* **The venv is built here**, so a fresh tree is ready to test in the minute
  ``uv`` takes from a warm cache, and no session forgets it (a worktree
  running the main checkout's venv measures the main checkout's code —
  tests/CLAUDE.md § Quoting numbers).
* **Memory stays shared**: a worktree made by this hook keeps its transcript
  and auto-memory at the launch directory (docs, worktrees § Resume), where
  the built-in path gives each tree an empty memory of its own.

The branch is named after the worktree — ``wp1208-foo`` is the branch
``wp1208-foo``, the repo's convention — cut from ``origin/main`` after a fetch;
an existing branch of that name is checked out instead, which is how a session
resumes work on a branch after its tree was removed.  Failure to build the venv
is reported on stderr and does not block the tree: ``/wp-start`` step 4 sees
the hook's flag and builds it.  Any other failure exits nonzero, which is the
one blocking exit for this event.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

VENV = 'uv venv --python 3.12 && uv pip install -e ".[dev]"'


def sh(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}: {proc.stderr.strip()}")
    return proc


def main() -> int:
    payload = json.load(sys.stdin)
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or Path.cwd())
    name = payload.get("name")
    if not name:
        raise KeyError(f"no worktree name in payload (keys: {sorted(payload)})")
    # Claude Code names the tree and (2.1.246, measured) sends no path; its own
    # location is .claude/worktrees/<name> under the launch checkout, kept here
    # so `EnterWorktree` with `path` and the gitignore rule still apply.
    path = Path(payload.get("path") or root / ".claude" / "worktrees" / name).resolve()

    sh("git", "fetch", "-q", "origin", "main", cwd=root, check=False)
    if sh("git", "rev-parse", "--verify", "-q", f"refs/heads/{name}", cwd=root, check=False).returncode == 0:
        sh("git", "worktree", "add", str(path), name, cwd=root)
    else:
        sh("git", "worktree", "add", "-b", name, str(path), "origin/main", cwd=root)

    venv = subprocess.run(VENV, shell=True, cwd=path, capture_output=True, text=True)
    if venv.returncode != 0:
        print(f"worktree {name}: venv build failed — run `{VENV}` there:\n{venv.stderr}", file=sys.stderr)
    else:
        print(f"worktree {name}: branch {name} from origin/main, [dev] venv built", file=sys.stderr)
    print(path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"worktree_create: {exc}", file=sys.stderr)
        sys.exit(1)
