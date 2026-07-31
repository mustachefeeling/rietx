# WP-1031 — Planning-doc consolidation & handoff mechanization

Milestone: v1.0 · Status: 🔄 2026-07-31 — in flight
Depends on: — (touches CLAUDE.md/ROADMAP.md; land while no other WP is in flight)

## Goal

A session's fixed reading cost drops from ~65–75k tokens to ~30k (root
CLAUDE.md + ROADMAP + one WP file), every layer of the planning docs has a
stated retention rule with a mechanical test, and ending a WP session is one
command (`/wp-handover`) whose mechanical parts a meta-test enforces.

## Context

Measured 2026-07-31 (two independent surveys, spot-verified):

- **CLAUDE.md is 1142 lines (~20k tok, auto-loaded always) and ~48–54 % of it
  is dated measurement narrative that exists in at least one other file.** The
  WP-1026 indexing material is verbatim-triplicated (CLAUDE.md + ROADMAP
  "Current focus" + wp/1026); the GUI essays (WP-1010…1015, 1029) likewise.
  The *orphans* — content whose only home is CLAUDE.md — are almost entirely
  bookkeeping/measurement-hygiene rules, the inverse of the intended layering.
- **ROADMAP.md is 2301 lines, 79 % of which is "Current focus"** — a
  reverse-chronological session diary that the protocol's own text (line 37)
  says gets "rewritten when the next WP lands". It is prepended to instead;
  nothing has demoted since 2026-07-29 because the only demotion trigger is
  milestone-ship and v1.0 spans ~30 WPs.
- **The session protocol leaks in three places**: CLAUDE.md appears in no
  protocol step (no write rule, no eviction rule); no demotion at WP-close;
  `### Inherited` grows monotonically (1027 is 63 % Inherited and has never
  been started) because step 3b has no prune counterpart.
- **`ci.yml` `paths-ignore` skips every planning-doc path**, so a docs
  consistency test never runs on exactly the pushes it polices without a
  small docs workflow (priced: ~1 billed min per docs push).
- Convention drift: TEMPLATE.md declares `🔶`, which appears nowhere (practice
  is `🔄`/`🛑`); ~21 free-form Status spellings; three files use H2
  `## Inherited`.

User-ratified decisions: **move everything, delete nothing** (every outgoing
paragraph relocates to a milestone record; deletes only for grep-proven
duplicates); **split CLAUDE.md** into root + `gui/` + `tests/` nested files;
**mechanize the handoff** with a committed `.claude/commands/wp-handover.md`
plus `tests/test_docs_consistency.py`.

Design rules that bound the work:

- Headline test rules (quote-ranges, loadgroup, budget-is-a-guard, count
  bookkeeping) stay in **root**: nested CLAUDE.md files load when a session
  touches files in that subtree, and running pytest via Bash does not.
  Key-test-data stays in root for the same reason (physics sessions in src/).
- Size caps are pinned **after** measuring (achieved size + headroom), in the
  commit that lands the rewrite — never promised in advance.
- **No reordering of existing handover logs**: the oldest-first files carry
  cross-entry references ("third session") that reordering corrupts; ordering
  is enforced prospectively by the command only.
- `### Inherited` becomes a mailbox pruned at every session start on that WP;
  step 3b widens to "any WP that is not closed and not yours".

## Non-goals

- No content is judged or rewritten for correctness — this WP relocates and
  distills; contested claims move verbatim with their dates.
- `docs/AGENT_PROTOCOL.md`, `docs/VALIDATION.md`, `docs/solver-survey.md`,
  `docs/DESIGN.md`: untouched (own update rules / healthy).
- No change to what the *code* tests assert; the new meta-test reads only
  documentation files.

## Tasks

- [x] Merge origin/main into the working branch; verify no WP in flight;
      re-anchor all surveyed line refs by grep.
- [ ] Create this WP file + ROADMAP index row.
- [ ] Normalize conventions (content-preserving): TEMPLATE.md status
      vocabulary → `⬜ 🔄 ✅ 🛑` with format `glyph date — free text`; the
      three H2 `## Inherited` → H3; Status-line prefixes across docs/wp/.
- [ ] Land `tests/test_docs_consistency.py` (vocabulary, WP↔ROADMAP bijection
      + glyph equality, Inherited placement, link resolution, milestone
      records; size caps deferred to the final pass) + `.github/workflows/docs.yml`.
- [ ] Create `docs/milestones/v1.0.md`; MOVE the Current-focus diary into it;
      rewrite Current focus ≤40 lines.
- [ ] MOVE the three `<details>` blocks + 05xx tail into v0.6/v0.5/v0.4
      appendices.
- [ ] Create `tests/CLAUDE.md`; shrink root `## Commands` (headline rules +
      `### Current numbers`, replace-only).
- [ ] Create `gui/CLAUDE.md` + `src/pxrdref/gui/CLAUDE.md` pointer stub;
      shrink root `## Data flow`; promote `sig()` to Invariants.
- [ ] Root CLAUDE.md final pass (Roadmap section → pointer, indexing dossier
      distilled, recaps deleted, `###` headings); measure; enable size caps.
- [ ] Replace `## Session protocol` (Inherited-prune-on-arrival, /wp-handover,
      CLAUDE.md-takes-rules, demote-at-WP-close).
- [ ] Commit `.claude/commands/wp-handover.md` + `.gitignore` entries for
      `.claude/worktrees/` and `.claude/settings.local.json`.
- [ ] Resolve or file the `--collect-only` two-short discrepancy (timeboxed).
- [ ] Close out via `/wp-handover` itself; final sentinel sweep; before/after
      sizes recorded here and in v1.0.md; memory-note maintenance; PR to main.

### Sentinel ledger

Every commit in this WP must keep each string below greppable somewhere in
the tree (`git grep -F`), so no orphan fact is lost in a move. Verified
present 2026-07-31 before the first move:

1. `two short of passed+skipped in both` — the unowned --collect-only defect
2. `1772 collected` — the merged-tree suite state
3. `Quote wall clock as a range` — the range rule
4. `One dataset, one group` — the xdist regrouping lesson
5. `runaway guard, never a timer` — the budget rule
6. `RefinementResult.sig()` — the weighted-residual invariant
7. `add a row there whenever a new correction lands` — the compare-UI obligation
8. `adopting its protocol` — the cross-code comparison rule
9. `1268 passed / 117 skipped` — the numpy-only [dev] counts
10. `85 → 139 → 184 → 207 → 221 → 255` — the vitest ladder
11. `three vite builds` — the machine-state timing evidence
12. `narrowing what is searched is the lever` — honest-budget vs scope
13. `` xdist_group` marks `` — why --dist loadgroup is not optional
14. `never wrong, and silent more often than right` — the indexing scoreboard
15. `performance filter's failure mode is a wrong answer` — the _box_key lesson
16. `the budget a test depends on may be one rank down` — the library-budget trap

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py -q   # green, incl. size caps
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"  # fast suite green
.venv/bin/python -m ruff check src tests examples
for s in <each sentinel above>; do git grep -Fq "$s" || echo "LOST: $s"; done  # no output
```

Plus the measured claim: root CLAUDE.md + ROADMAP.md combined ≤ ~1000 lines
(from 3443), with before/after `wc -l` recorded in the handover log.

## References

Internal only: the 2026-07-31 survey (two Explore passes + design review) in
the session that opened this WP; ROADMAP.md §Session protocol (the text being
replaced); `tests/test_manual.py` and `tests/test_compare_ui.py` as the house
meta-test pattern.

## Handover log

Append-only, newest first. An entry is REQUIRED before ending any session
that touched this WP — done / in flight / next / gotchas.

- **2026-07-31** — created, with the survey findings in Context and the
  sentinel ledger seeded from the live tree.
