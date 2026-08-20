# WP-1116 — session-protocol hygiene: the scan that cried wolf

Milestone: v1.1 · Status: ✅ 2026-08-20 — the scan reads both entry forms and
sees a same-day miss; the handover entry now opens on meaning
Depends on: —

## Goal

The SessionStart scan flags a WP when, and only when, a handover is genuinely
owed — and the entry it asks for opens with a paragraph a person can read
without opening the diff.

## Context

`/wp-handover` was reported as "often not run". It is not: measured over the
whole history, **5 of 131 WP commit-days** carried no handover entry (4 %), all
on or before 2026-08-07, and **none since 2026-08-08** — the scan
(`.claude/hooks/session_start.py`, WP-1061) landed 2026-08-06 and the one miss
after it was repaired at the next session. What was failing was the *signal*.

**The scan was crying wolf.** On 2026-08-20 it flagged WP-1109 and WP-1110 as
owing handovers. Both had been handed over that day. Its entry-date regex read
only the template's `- **YYYY-MM-DD**` bullet, and those two files — the only
two in the repo — had adopted `### YYYY-MM-DD (Nth session)` headings. The
drift was rational: WP-1109 ran **three sessions in one day** and a date bullet
cannot tell them apart. The template never sanctioned the heading and no test
pinned either form, so the format and its only reader drifted apart in silence.

**And the cadence exposed the scan's declared blind spot as the real hole.**
Comparing *dates* means a commit-then-no-handover inside one day is invisible.
With three sessions a day that is the common case, not the corner: the scan
could only ever catch a miss that survived past midnight.

**A false alarm costs more than no alarm.** It spends the successor's first act
on a repair that was not needed, and it teaches the reader to skip the one line
of the session-start report that is ever load-bearing.

## Non-goals

- A `Stop`-hook nag. It fires at every turn end and cannot tell "session over"
  from "turn over", so it would print on every turn after the first commit.
  The measured miss rate does not justify it.
- Changing what `/wp-handover` verifies (steps 4-10 are unchanged).

## Tasks

- [x] The scan reads **both** sanctioned entry forms, and both readers bound
      the log section at the next H2 (several WPs put `## References` after it).
- [x] A second, **order-based** coverage rule: the WP file must have been
      touched at or after the newest *substantive* `WP-NNNN:` commit — one that
      is not a merge, does not touch the WP's own file, and touches something
      outside `docs/`, `CLAUDE.md` and `.claude/`. Being SHA-ordered it sees a
      same-day miss. The two rules cover each other: order is blind to a WP
      whose every commit was ritual, date is blind inside a day.
- [x] `docs/wp/TEMPLATE.md` sanctions both forms, names the hook as their
      reader, and requires every entry to open on **meaning** and close on the
      **next actions**.
- [x] `/wp-handover` carries that requirement, gains a one-line early exit when
      the session committed nothing, and **runs the scan as its own step 9** —
      a handover that its reader cannot see is not done.
- [x] `/wp-start` explains which rule fired and names the triggers for running
      `/wp-handover`, since it is missed by drifting past it, not by deciding
      against it.
- [x] Tests: the format pinned in `tests/test_docs_consistency.py`, the two
      rules and the ritual exclusion in `tests/test_workflow_hooks.py`.

## Acceptance

Both rules were tuned against the repo's own history rather than invented: the
naive order rule flagged three healthy WPs (1016, 1059, 1078, whose handover
ritual spans several commits and ends on a merge, a `CLAUDE.md` rule and a
ROADMAP sync respectively); with the ritual exclusion it flags **0 of 93**.

```sh
.venv/bin/python -m pytest tests/test_workflow_hooks.py tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
python3 .claude/hooks/session_start.py   # must not flag a handed-over WP
```

## References

- WP-1061 — the scan and `/wp-start`; WP-1031 — `/wp-handover`.
- `docs/ROADMAP.md` § Session protocol, the one authority the commands encode.

## Handover log

### 2026-08-20 — the scan that cried wolf

The complaint was that the handover ritual keeps getting skipped. It does not:
over the project's whole history only 5 of 131 WP commit-days lack an entry,
all of them on or before 2026-08-07, and none since. What was broken was the
alarm. The session-start scan read handover entries in only one of the two
formats in use, so on the morning of 2026-08-20 it reported two WPs as
un-handed-over when both had been handed over the day before — and an alarm
that fires on healthy work is how a person learns to ignore it. Underneath that
sat a bigger gap: the scan compared dates, and this project routinely runs three
sessions in a day, so a session that committed and skipped its handover was
invisible until the next midnight.

Both are now closed. The scan reads both entry formats, and it gained a second
rule that compares commit *order* rather than dates, so a miss is caught inside
the same day. The two rules are deliberately different in what they are blind
to, so each covers the other. Separately, and because the ritual should produce
something worth reading, every handover entry must now open with a paragraph
saying what the work *means* to someone who has not seen the diff and close by
naming the next actions — this entry is written to that shape, and
`/wp-handover` now reports the same paragraph to the person before the PR link.

*Done.* All six tasks above; each is checked with what it changed.

*Measured.* `[dev]`, darwin/arm64, this worktree's own venv.
`tests/test_workflow_hooks.py` 6 → 8 (one blind-spot test replaced by three:
same-day miss caught, ritual commits not flagged, heading entries read);
`tests/test_docs_consistency.py` 17 → 19. Fast selection **2507 passed, 117
skipped** in ~2 min: passed+skipped is +4 on the four added tests, all four
passes, no new skip. No full-suite run — the change touches `.claude/`,
`docs/` and two test files, and can move no measured number (`tests/CLAUDE.md`
§ Running, rung 3). `ruff check src tests examples` clean, and the scan itself
returns a single healthy line on the final tree.

*Gotchas.* Two, both paid for here. `docs/ROADMAP.md` sits **exactly** on its
438-line cap, so adding the index row meant compressing the v1.1 focus
paragraph by the same amount — budget for that, it is not free. And both the
scan and the consistency test must bound the handover section at the next H2,
because several WPs carry `## References` after it; without the bound the
format check trips over that heading.

*Next.* Nothing here is in flight. The thing to watch is whether the meaning
paragraph survives contact: it is enforced by `/wp-handover`'s wording and by
`TEMPLATE.md`, not by a test, because no test can tell a real summary from a
restated commit list. If entries drift back into activity summaries, the next
lever is a review step, not a stricter regex. The scan's remaining honest
limit is that work committed *and* handed over in one session satisfies both
rules whatever the entry says — a quiet report is a prompt, never proof.
