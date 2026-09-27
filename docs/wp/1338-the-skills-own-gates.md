# WP-1338 — the skill's own gates: the references, the private corpus, the cap race

Milestone: unscheduled · Status: 🔄 2026-09-28 — claimed by @yue-here
Track: The repo's own process
Depends on: —
Priority: P2 2026-09-27 — was P4: the maintainer raised it with 1506 and 1507; `SKILL.md` has 2 B of headroom, so every body addition now races every other

## Goal

The three gates protecting the agent skill cover what they are named after: a
dotted name in a reference file is walked like one in the body, a private
`(Measured: …)` tag names the corpus its file declares, and two contributors
adding a sentence each to the same skill file do not fail on the merge with no
warning beforehand. A new feature's guidance lands outside the body unless
every fit needs it, so the body can shrink toward the specification's 5 000
tokens while the package grows.

## Context

Three issues, all about `tests/test_skill.py` and the process around it
(#238, #241, #247). None has cost a wrong answer. Each is a gate that reads as
covering the tree and does not: the WP-1037 shape, one document over. The
maintainer added a fourth concern on 2026-09-27 after the merge-drag review:
every feature adds to the body, so the cap race is growth meeting a fixed
number.

**Superseded in part, 2026-09-28.** #241's gate landed on 2026-09-08
(`e89c8b92`, "a Measured tag names this repository or the declared corpus")
with its liveness guard and the classification reason written beside it, so
this file's claim that it was blocked on #233 was stale. What it lacked was a
deliberately broken fixture, which the acceptance line asks for. #284 and #287
are closed (the 2026-09-23 triage): #284 landed as PR #292, #287's `RECIPE_*`
half as PR #291. The 2026-09-03 decision to warn at 95 % is replaced below:
with `SKILL.md` at 99.99 % of its cap it would be a warning that is always on.

**#238 — the dotted-name walk ran on the body only.** `RX_DOT_NAME` (`rx.X`)
was checked across the whole tree and the generated `api*.md` byte for byte.
Between them sat the hand-written reference files, whose `report.x` /
`result.x` / type-level names were checked by hand at review. Two decisions
come with widening it: which roots (the body's four instance names reach no
`StageResult.x`), and what to do about a **negative** claim (*"`StageResult`
carries no `rwp`"*), which a walk cannot check and which WP-1334 proposes to
falsify.

**#241 — a private tag names its declared corpus.** Landed (above). The chosen
rule requires every `Measured` tag to open with `WP-` or with the file's
declared corpus, per tag and never per file, because a repo-shaped tag has no
fixed spelling.

**WP-1409's finding, 2026-09-14: a code span inside a table cell.**
`references/abstention.md` wrote `scale × |F|² × profile` as a code span in a
table cell. The first `|` ends the cell, the span never closes, and the
backticks render literally. The manual's HTML scan caught it only because
`using/skill.md` includes the body whole; no skill test covers a reference
file.

**#247 — the byte caps are checked on the merge result, so two passing PRs can
fail together.** Each PR's CI sees its own merge with `main` as it stood at push
time. It fired on `batch.md` (#233 green at 35 570 B, the merge 36 599 B against
36 000), on `diagnostics-projects.md` (#346 and #291 together 37 641 B), and on
`SKILL.md` on 2026-09-27 (`603b7ca5`: 33 027 of 33 000 after merging main,
WP-1470 trimming two commas and a clause to reach 32 998). A cap failure names
only a total, so the second author has to find bytes in a file they may not
have written, and the cheapest pass is deleting someone else's prose. Three
attempts to absorb 599 B once produced 36 209, 36 136, then 37 083.

**Where the pressure is, measured 2026-09-28 on `3b3a9dc5`.** The body is
32 998 B and 479 lines against caps of 33 000 B and 500 lines, about 8 200
tokens at 4 B a token. The Agent Skills specification recommends under 5 000
tokens and 500 lines for the body (agentskills.io/specification, § Progressive
disclosure); the line cap matches it, and the byte cap is a truncation ceiling,
not that budget. The references are 358 kB across 17 files and cost nothing
until read. Anthropic's best-practices guide says to bundle comprehensive
resources for that reason. The body sat within about 150 B of its cap for most
of September: PR #292 cut 2 kB on 2026-09-10 and main refilled it by
2026-09-17 (routing table +619 B for two rows, §1 +669 B, §2 +309 B).

**Direction, 2026-09-27: a placement rule, cheapest first.** A new feature's
guidance goes to the first of these that can hold it.

1. The package's own output: `Diagnostic.suggestion`, an entry in `help.py`.
   It costs nothing until the output appears and it matches the installed
   version, while the installed skill is a copy that can be stale after an
   upgrade.
2. A reference row keyed by an identifier the agent already holds: a
   diagnostic code, a verb, a file extension, a result type. One standing
   sentence in the body ("grep `references/` for the name in front of you")
   replaces a routing row per feature. About 6 of the 15 routing rows are of
   this kind.
3. A routing row, only for a task shape no identifier names (a ramp, a batch,
   "you are about to quote a number").
4. The body, only for a rule every fit needs, paid for by a cut.

References stay one level deep. Anthropic's guide reports that from a file
referenced by another referenced file an agent may preview with `head -100`
rather than read it whole, and names two mitigations: a reference over 100
lines opens with a table of contents, and lookup by grep lands on the section
directly. Held in reserve: one skill per whole task shape, routed by the
harness from each description, at about 100 tokens a description in every
session and with the risk of a shape activating without the core.

**The mechanical guard: a ceiling and a budget per capped file.** The ceiling
keeps its truncation derivation and fails on any tree. The budget sits below
it and fails only a change that grows the file past it, measured against the
change's base. The gap absorbs PRs that merge together, and the cut falls on
the author while writing, in their own text.

**Order.** The eval first, as the guide says. Then the placement rule where
WP-1330's rule lives. Then body material moved into references toward 5 000
tokens; by size the candidates are §4 (6 806 B), §10's worked default
(2 500 B) and the routing table's manual-page column.

## Non-goals

- Cutting skill content to make room. The caps question is decided here as
  policy; individual rows are their own WPs' business. Moving body material
  into references under the placement rule is in scope, after the eval.
- The skill's routing structure and the per-shape references — WP-1330, closed.
- Anything in `references/api.md`, which is generated and already gated.

## Tasks

- [x] Run the dotted-name walk over every authored file, parametrised per
      file; re-site the `> 15` liveness assertion; decide and record whether
      type-level roots widen.
- [x] The private-corpus check, per tag, with its liveness guard, and the
      reason the chosen classification rule was preferred written beside it.
      Landed 2026-09-08 in `e89c8b92`; its broken fixture is the next item's.
- [x] A deliberately broken fixture for each gate, the corpus gate included.
- [x] A code span opened inside a table cell fails, in every skill file
      (WP-1409's finding).
- [x] Cap policy (replaces 2026-09-03's 95 % warning): a ceiling and a budget
      per capped file, the budget failing only a change that grows the file
      past it. Buffer size chosen from the measured concurrency of additions.
- [x] Every PR that changes a capped file reports its delta and headroom, so
      the near-full state is visible before CI fails.
- [ ] The placement eval: the keyed routing rows replaced by one grep
      sentence, real agents on tasks where a diagnostic fires, against
      today's body. Registered before it runs (tests/CLAUDE.md § Three eval
      protocols).
- [ ] The placement rule written where WP-1330's lives: CONTRIBUTING.md
      § The agent skill and root CLAUDE.md's skill bullet.
- [ ] After the eval, body material moved into references toward 5 000
      tokens, each move recorded with the bytes it freed.
- [ ] Tests: every gate lands as a test, expected **green on the tree as it
      stands**. These close gaps rather than fixing breaks, so a red run means
      the gate found something real, to be reported, not accommodated.
- [ ] Skill: the gates change no row. The placement eval may replace the
      keyed routing rows with one grep sentence, and only if it supports it.

## Acceptance

The gates run over every authored skill file and pass on the tree; a
deliberately broken fixture of each kind fails.

```sh
.venv/bin/python -m pytest tests/test_skill.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issues #238, #241, #247. Caps read from `tests/test_skill.py`:
  `SKILL_MAX_BYTES = 33_000`, `REFERENCE_MAX_BYTES = 36_600`,
  `API_INDEX_MAX_BYTES = 39_000`.
- agentskills.io/specification § Progressive disclosure; Anthropic's skill
  authoring best practices (bundled resources, one level deep, grep lookup).
- `CONTRIBUTING.md` § The agent skill — the two prose obligations #241 gates.

## Handover log

- **2026-09-27** — Folded, not worked: the maintainer re-rated this to P2
  and asked for the skill-scaling review to land here. The cap race now has
  a cause, a body that every feature adds to, and a direction: a placement
  rule that keeps feature guidance out of the body, tested by an eval first,
  with a ceiling and budget per capped file as the guard. Tasks rewritten to
  match; the reasoning and numbers are the first Inherited entry. Status
  stays ⬜. Next: the maintainer's pick of a 1 or 2 kB buffer, then the eval.
- **2026-09-03** — created, from the 2026-09-03 issue triage (issues #238,
  #241, #247). The cap table was re-measured rather than copied: `SKILL.md`
  now has 22 B of headroom, not the 34 the issue reported. Decided the same
  day: warn at 95 % first, split versus raise deferred to the next row.
- **2026-09-16** — the `diagnostics-projects.md` half of the cap race is
  settled by a split, and `REFERENCE_MAX_BYTES` is still 36 000. PR #346 put
  17 `GSAS2_*` rows (10 127 B) into that file while PR #291 waited, and the two
  together came to 37 641 B against the cap, which is how a docs change fails a
  gate neither author touched. The 2026-09-09 ruling above says the constant
  stays, so the fix is the one the cap's own docstring names: the 29 GSAS and
  GSAS-II rows moved to `references/diagnostics-gsas.md` as §7h, in main's
  order, so the `.EXP` rows still sit beside the `.gpx` rows they share five
  suffixes with and the `.prm` rows beside the `.instprm` ones. The seam is a
  program rather than a file kind, and the writer rows go with it, because this
  build writes a `.EXP`, a `.prm`, an `.instprm` and a GSAS-II phase CIF and no
  other foreign format's writer has a row. Measured after:
  `diagnostics-projects.md` 10 448 B, `diagnostics-gsas.md` 21 436 B,
  `SKILL.md` 32 068 B of 33 000, `diagnostics.md` 35 963 B of 36 000. #291
  rebases onto about 17 kB of room, and #289 onto what #291 then frees in
  `diagnostics.md`. **What this does not do**: the three unticked tasks are
  untouched and Status stays ⬜, since the split executes a ruling rather than
  landing a gate. `diagnostics.md` still has 37 B of headroom until #291 lands,
  so a new engine row is blocked today exactly as it was. The count moves by
  four, one per `REFERENCES`-parametrised gate in `tests/test_skill.py`, and by
  nothing else.
