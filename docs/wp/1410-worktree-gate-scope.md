# WP-1410 — the worktree gate guards this checkout, not every repository

Milestone: unscheduled · Status: ✅ 2026-09-14 — scoped to the session's own
checkout, covered in the hook suite, and the fail-open now says when it fired
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
exactly like a working one. Task 3 adds one line to stderr, and the exit code
that puts it in front of the session; the call still goes through.

## Tasks

- [x] Scope the edit branch. Add `session_main_checkout(payload)`, reading the
      payload `cwd` and nothing else; give `is_in_main_checkout` an optional
      `session_main` and refuse only on a match. No `cwd` is no claim about the
      session, so the gate falls back to guarding every checkout, which fails
      closed. Leave the Bash branch alone, since testing `cwd` was already
      right. `CLAUDE_PROJECT_DIR` was tried first and dropped: it describes the
      process, so under a test harness it scopes the gate to a repository the
      payload never mentioned.
- [x] Cover it. The gate's section of `tests/test_workflow_hooks.py`, beside the
      three tests it already had, driving `refusal()` against real `tmp_path`
      git fixtures. The gate asks git what a path belongs to, so a mocked answer
      would test nothing.
- [x] Name the fail-open. One stderr line in the `except`, so a broken gate says
      so, and exit **1** rather than 0, which is what puts that line in front of
      the session while still running the tool. Reached as a subprocess fed
      invalid JSON, which is how Claude Code reaches it.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_workflow_hooks.py -q
```

The gate's cases, with the payload `cwd` in the session's own checkout:

allowed — auto memory symlinked into another repo; that repo's own files; a
worktree of the session's checkout; a path in no repository; a `Read` of the
main checkout; `git -C` against another tree; a read-only `git` verb; a plain
command.

refused — the session checkout's `README`; a file under a directory of it that
does not exist yet; `git commit`, `git checkout -b` and `git stash push` with
`cwd` in it.

With no `cwd` in the payload, every main checkout is refused again, the session's
own and a second repository alike: no `cwd` is no claim about the session.

## Handover log

- **2026-09-14** — A session can now write its own auto memory again, and edit a
  second repository, without the worktree gate refusing it. The gate had been
  guarding every git checkout on the machine rather than the one the session was
  launched in, so three of its four refusals were wrong; only rietx's own main
  checkout should ever have been refused. Nothing about the protection that
  matters has changed: the rietx main checkout is still read-only for a session,
  by the same test, and the Bash branch was already correct. The cost of finding
  it was a day of two sessions silently routing around a refusal with Bash
  heredocs, neither recognising it as a bug.

  *Done.* `session_main_checkout(payload)` reads the payload `cwd`;
  `is_in_main_checkout` takes an optional `session_main` and refuses only when
  the file's main checkout is that one. `CLAUDE_PROJECT_DIR` was the first
  answer and is the wrong one: it describes the process rather than the call, so
  under a test harness it scopes the gate to a repository the payload never
  mentioned. No `cwd` is no claim about the session, and the gate then guards
  every main checkout, which fails closed. The Bash branch is untouched, since
  testing `cwd` was already right. The module docstring gained the "only this
  checkout" clause. The gate's tests join the three it already had in
  `tests/test_workflow_hooks.py`, driving `refusal()` against real `tmp_path`
  git fixtures, one of which symlinks a memory directory into a second repo,
  because the gate asks git what a path belongs to and a mocked answer would
  test nothing.

  *Measured.* Before the fix, with `cwd` in the rietx main checkout: auto memory
  symlinked into another repo, that repo's own files, and an unrelated clone were
  all refused; only the fourth case, rietx itself, was correct. After: those
  three are allowed and rietx stays refused, under `Write` and `Edit`, with a
  payload `cwd` and without one. Counts are in the PR body. A `pytest` in
  `echemlab` was running throughout, so the figures are counts and not timings,
  and no wall clock is quoted.

  *Gotchas.* Two, and the second is the more useful. The running hook is
  `$CLAUDE_PROJECT_DIR/.claude/hooks/`, which is the **main checkout's** copy
  even from inside a worktree, so this fix does not take effect for any session
  until it merges; a `Write` to auto memory is still refused on this branch and
  that is expected, not a failure. And the fail-open swallowed the first draft of
  this fix: it referenced an unimported `os`, every case passed as *allowed*
  including the main checkout, and nothing said so. The fail-open stays, because
  a bricked session costs more than a missed refusal, but it now prints to
  stderr and exits 1. The exit code is the whole message: a `PreToolUse` hook's
  stderr reaches the session only on a non-zero, non-2 exit, which Claude Code
  renders as a hook error and runs the tool anyway, while exit 0 sends the same
  line to the debug log. A gate disabled by a typo was indistinguishable from a
  working one.

  *Next.* Nothing here; the WP closes. The one thing a successor might pick up is
  the sibling class this did **not** generalise: the `session_start.py` and
  `handover_owed.py` hooks were not audited for the same over-reach, because
  neither takes a file path and neither refuses anything. If a third hook is ever
  given a path argument, scope it at the same seam rather than re-deriving.
