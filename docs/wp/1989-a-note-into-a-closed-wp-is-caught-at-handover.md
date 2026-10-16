# WP-1989 — A note written into a closed WP is caught at handover

Milestone: unscheduled · Status: ✅ 2026-10-16 — `closed_wp_writes.py` lists what a branch adds to a ✅/🛑 WP, and `/wp-handover` step 5 runs it
Track: The repo's own process
Depends on: —

## Goal

A session that writes into a WP that is already closed is told so before its
branch merges. No session reads a closed WP again, so a note there that asks
for work never reaches anyone.

## Context

**The rule existed and did not hold.** `docs/wp/TEMPLATE.md` ("Never into a
✅/🛑 WP") and `/wp-handover` step 5 ("a WP that is not closed") both say it
in prose. `tests/test_docs_consistency.py::test_inherited_is_h3_and_closed_wps_have_consumed_theirs`
is the only mechanical check. It asks whether a WP closed after 2026-07-31
still carries an `### Inherited` heading, and that cannot see either of the
two ways a note got lost:

- **Into a WP closed before the epoch.** WP-0406 deferred joint-fit soft
  restraints into WP-0308's `### Inherited` on 2026-07-27, after 0308 closed
  (2026-07-23). `_multi_closures`' refusal pointed readers at that file for 81
  days. Three open WPs (1325, 1962, 1963) worked around the refusal, and none
  owned it. It is now [WP-1988](1988-soft-restraints-in-a-joint-fit.md).
- **In prose rather than under the heading.** WP-1907's close (2026-10-07)
  wrote "WP-1903's Inherited has both" about two lane-tool defects, after
  1903's ✅. It reached a reader only because 1903 was worked again the next
  day.

**The audit (2026-10-16).** It was run on full history over all 232 closed WP
files. For each file it found the commit that closed it, then every later
commit from another WP that added lines to the file. Rename and header
sweeps were set aside (1062, 1066, 1067, 1031, 1507, 1540). About 25
substantive writes remained, and each was checked against the tree. WP-0308's
was the only one still unconsumed. The rest were consumed by a reopening
(1026, which 1030, 1039, 1041 and 1042 had all written into), consumed by
the next day's session (1903, and 1953's mailbox), satisfied in code (0405's
and 0406's backend notes), moot (1027, 1041), or records and pointers.

## Tasks

- [x] `.claude/hooks/closed_wp_writes.py`: diff against the merge-base with
      `origin/main` and report each WP file that was ✅/🛑 at the base, is
      still closed, and gains lines net of what it loses. A sweep rewriting a
      line in place adds nothing, and a reopened WP is not reported. Exit 1
      when it reports.
- [x] `/wp-handover` step 5 runs it after the forward references are pushed.
- [x] `tests/test_closed_wp_writes.py`: a heading note, a prose note and a
      committed note are each reported; a sweep, a reopening, an open WP, a
      new WP and the session closing its own WP are not; the handover step
      that runs it is still there. Joined to CI's `docs` job, since it reads
      the handover command.
- [x] Skill: none. This changes how the package is worked on, not how it is
      driven.

## Non-goals

- Making the check a gate. A correction to a closed WP's own record is
  legitimate (WP-1041 superseding 1026's scoreboard), and only the writer can
  tell a record from a request.
- Rewriting the 40 pre-epoch `### Inherited` archives. They are records, and
  the audit found one unconsumed note among them.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_closed_wp_writes.py tests/test_docs_consistency.py
python3 .claude/hooks/closed_wp_writes.py   # on this branch: reports 0308's pointer, a record note
```

## Handover log

- **2026-10-16** — Closed in the session that filed it. A note written into
  a closed WP is now named at handover: the script lists what the branch
  adds to each ✅/🛑 WP, and the writer moves the note to an open owner or
  says why it stays. No open WP owned the guard, so it was filed and landed
  together.
  *Measured:* `tests/test_closed_wp_writes.py` 9 passed (`[dev]`, Linux
  x86_64, python 3.12). Its first case is the guard failing on purpose: the
  wiring test went red before the handover step existed. On this branch the
  script reports one file, WP-0308, +2 lines. That is the pointer to
  WP-1988, a record note that stays. Next: none.
