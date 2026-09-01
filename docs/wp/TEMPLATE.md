# WP-NNNN — <title>

Milestone: v0.X · Status: ⬜
Depends on: WP-MMMM (or —)

<!--
Numbering: MMNN — the block of the milestone this WP is OPENED for, then the
next free sequence number (v1.1 → 11xx); an unscheduled WP takes the newest
block. The number never changes when the WP moves, so it is not where the WP
stands: the Milestone line is, and the ROADMAP section the row sits under
mirrors it (tests/test_docs_consistency.py). Never recycle a retired number.
Milestone values: vN.N (a row of ROADMAP's table), vN.N.x (shipped after that
milestone, in its patch releases), unscheduled.
Status values: ⬜ not started · 🔄 in progress · ✅ shipped · 🛑 no-go.
Format: "Status: <glyph> <YYYY-MM-DD> — <free text>". The date is required
for every glyph except ⬜; the free text is optional and may wrap.
Keep the Status line here and the WP's row in ../ROADMAP.md in sync
(tests/test_docs_consistency.py asserts both). The ROADMAP cell carries the
glyph and the date only; the free text lives on this line.
A WP file must be self-contained: a session that reads ONLY this file
(plus the auto-loaded CLAUDE.md) can start work. Link specific DESIGN.md
sections instead of restating them, but restate anything short and
load-bearing (a formula, a threshold, a fence) directly.
-->

## Goal

1–2 sentences: what exists, and works, when this WP is done.

## Context

Everything a fresh session needs and cannot get from CLAUDE.md alone:
- Source files to touch, and the seams to extend.
- Relevant invariants (link `../DESIGN.md#...` sections; restate the short ones).
- Prior measured findings that constrain the design.
- Licensing fences (what may be ported, what is concepts-only).

### Inherited

Facts another WP's session established that change the work here. The
session protocol forbids reading other WP files, so a note left in some other
WP's handover log is unreachable from this one — if it matters here, it has to
be restated here, with the source WP named so it can be audited.

Written by the **other** session as it signs off (protocol step 3), not by
whoever works this WP. Typical entries: a constant or helper now exported for
reuse (import it, do not redeclare); a design bullet in this file that has
since gone stale; a deliberate deferral *into* this WP; a measured gotcha
that would silently mislead the work here.

**This is a mailbox, not an archive**: every session on this WP prunes it on
arrival (fold still-true entries into Context or Tasks, delete stale ones and
say why in the handover entry), and closing the WP deletes the section —
consumed. `tests/test_docs_consistency.py` asserts no WP closed after
2026-07-31 still carries one.

## Non-goals

Explicit fences: what looks adjacent but belongs to another WP or milestone.

## Tasks

Each item ≈ one commit, independently landable, prefixed in the commit
message with the WP id (`WP-NNNN: ...`). Check off as they land.

- [ ] ...
- [ ] ...
- [ ] Tests (unit/property; acceptance if this WP carries it) + obs/calc/diff PNGs to `tests/output/`

## Acceptance

Measurable criterion + the exact command(s) that verify it, e.g.:

```sh
.venv/bin/python -m pytest tests/test_xxx.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

Papers (author, year, journal), datasets, cross-code targets.

## Handover log

Append-only, newest first. An entry is REQUIRED before ending any session
that touched this WP.

**Two entry forms, both dated, both read by
`.claude/hooks/session_start.py`** (which is why
`tests/test_docs_consistency.py` pins them): a one-line
`- **YYYY-MM-DD** — <text>` bullet, or, once a WP takes more than one session
in a day — the normal cadence here — a `### YYYY-MM-DD [(Nth session)] —
<title>` heading with the entry below it. Nothing else counts as an entry, and
an entry the hook cannot see is a handover that did not happen.

**Every entry opens with a plain-language paragraph saying what the work
*means*** — what a reader who has not seen the diff now knows, or can do, that
they could not before — and closes by naming the next action. Between them go
the working details: *Done* / *Measured* / *In flight* / *Next* / *Gotchas*.
The lede is the part a person reads; the rest is the part a successor reads.
Write it as the answer to "so what?", never as a list of commits.

- **YYYY-MM-DD** — created.
