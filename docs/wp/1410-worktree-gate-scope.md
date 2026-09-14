# WP-1410 — the worktree gate guards this checkout, not every repository

Milestone: unscheduled · Status: 🔄 2026-09-14 — fix written and tested, landing
Depends on: —

## Goal

`.claude/hooks/worktree_only.py` refuses an edit only when the file belongs to
the main checkout of the repository **this session was launched in**. Auto
memory, a second repository, and an unrelated checkout are no longer its
business.

## Context

The gate exists because sessions launched in one checkout share its HEAD, index,
stash and tree (four collisions on 2026-08-26). That rationale is about *this*
checkout. The implementation is not: `is_in_main_checkout` resolves the path,
asks git for its top level and its common dir, and refuses whenever those agree.
Any repository's main checkout matches, so the gate governs repositories it was
never written for.

It surfaced when `~/.claude/projects/<slug>/memory` was symlinked into a
configuration repository shared between machines. `Path.resolve()` follows the
link, the target sits in that repository's main checkout, and every `Write` to
auto memory was refused. A Bash heredoc to the same path went through, because
the Bash branch tests `cwd` rather than the target, so two sessions worked around
it without recognising the cause.

Measured before the fix, with `cwd` in the rietx main checkout:

| target | before | correct |
|---|---|---|
| auto memory, symlinked into another repo | refused | allow |
| that configuration repo itself | refused | allow |
| an unrelated repo (`chessathon`) | refused | allow |
| rietx main checkout | refused | refuse |

Three of four wrong. The memory symlink made a pre-existing over-reach visible;
it did not create it.

**The fail-open needs a signal.** The module catches every exception and exits 0,
deliberately, because a bricked session costs more than a missed refusal. That
trade is right. What is missing is any sign that it fired: the first draft of
this fix used `os.environ` without importing `os`, and the whole matrix passed as
*allowed*, including the rietx main checkout. A silently disabled gate looks
exactly like a working one. Task 3 adds one line to stderr and changes nothing
else.

## Tasks

- [x] Scope the edit branch. Add `session_main_checkout(payload)`, reading
      `CLAUDE_PROJECT_DIR` and falling back to the payload `cwd`; give
      `is_in_main_checkout` an optional `session_main` and refuse only on a
      match. Leave the Bash branch alone, since testing `cwd` was already right.
- [x] Cover it. `tests/test_hooks.py`, six tests over the cases below, driving
      `refusal()` directly against real `tmp_path` git fixtures. The gate asks
      git what a path belongs to, so a mocked answer would test nothing.
- [x] Name the fail-open. One stderr line in the `except`, so a broken gate says
      so; exit code unchanged. Reached as a subprocess fed invalid JSON, which
      is how Claude Code reaches it.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_hooks.py -q
```

Eleven cases, `CLAUDE_PROJECT_DIR` set to the rietx root:

allowed — auto memory symlinked into another repo; that repo's own files; an
unrelated repo; a rietx worktree; a path in no repository; `git -C` against
another tree; a plain command.

refused — rietx `README.md`; rietx `CLAUDE.md`; a rietx `src/` file under `Edit`;
`git commit` with `cwd` in the rietx main checkout.

With `CLAUDE_PROJECT_DIR` unset, the rietx main checkout is still refused through
the payload `cwd`.

## Handover log
