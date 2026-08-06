# WP-1060 — Docs/CI consolidation: trim what the evidence indicts

Milestone: v1.0 · Status: ⬜
Depends on: — (touches `.claude/commands/wp-handover.md`, as does 1061; different
steps, lands in either order)

## Goal

The always-loaded docs shrink to what is load-bearing (CLAUDE.md ~720 → ~530
lines, indexing rules moved to an auto-loading subsystem rulebook), CI stops
paying for reruns and platforms the evidence does not support, and every
hand-maintained number is replaced by a measurement recipe — without dropping
one test or one fact.

## Context

Planned 2026-08-06 from three measurement surveys (docs inventory, CI/test
cost, growth-vs-payoff history), at the user's request to be *persuaded by
evidence* before anything was cut. Line numbers below were measured that day —
re-verify before editing; the facts stand.

**The verdict the surveys support.** The test suite is not the balloon: ~13
documented cases where only a heavy layer caught a real bug (115 fast indexing
tests green through the WP-1030 LaB6 regression; the Rᵀ trap passing a
DOF-count criterion; 79/564 settings wrong under a correct parameter count;
`features["indexing"]` False its whole life; the Kα2-ticks bug; five GUI
defects jsdom cannot see), test/src plateaued at ~0.84 since v0.5, and the
per-push feedback loop is already the ~3-min fast suite. The docs *are* the
balloon: docs/src 0.24 → 0.78 since v0.3 and still climbing, docs the
most-touched directory (277 commits vs src's 232), the ~196-line indexing
dossier in CLAUDE.md duplicating the v1.0 appendix (the 2026-07-31 "move" was
a copy), the session protocol stated in 3 places, single facts in up to 11
files, CLAUDE.md at exactly its 720-line cap. CI has *specific* waste: every
merged PR pays twice (pull_request run + identical post-merge rerun, ~9–22
billed min); the monthly macOS job bills ~70 of its 86 min at 10× to test the
platform the dev machine already is; the weekly full run drifted 44:21 →
77:52 while YAML comments still assert 303 scheduled min/month against ≈495
measured — the hand-quoted-figure rot this repo already warns itself about.

**Deliberate consequence:** this WP does nothing about local *full*-suite wall
clock — it is dominated by four fixture setups of 482–861 s, and shrinking it
means shrinking acceptance scope.

**Interactions.** Task 9 edits `.claude/commands/wp-handover.md` step 6;
WP-1061 adds a separate section to the same file — either order merges
trivially. Task 11 (caps) is LAST: every earlier task only shrinks files, so
the old caps stay green throughout.

## Non-goals

- **Any test coverage**: acceptance suites, misfit injection, cross-backend
  matrix, every meta-test. The 13 documented catches are the grounds.
- `tests/test_docs_consistency.py`'s eight checks — only `SIZE_CAPS`, the
  `_planning_docs` tuple, and their comments change.
- `docs/wp/` content: no deletion/renumbering — closed WPs are cited by WP-ID
  from ~320 code comments and pinned by the bijection + link tests.
- The weekly full-suite job (only its `pythons` matrix sibling is trimmed);
  the monthly torch job (the only torch coverage); the bit-identity goldens
  and `GOLDEN_PLATFORM` pin; `docs.yml` (sole gate for direct docs pushes).
- The WP/ROADMAP/handover protocol itself.
- A full gui/CLAUDE.md↔v1.0.md dedupe (highest-overlap pair, 277 shared
  10-grams) — deferred; task 11's cap stops regrowth meanwhile.

## Tasks

- [ ] 1. Fix the stale acceptance line: `docs/milestones/v1.0.md:24-26` still
  carries the uncorrected "≥ +9 bethanechol" bar; restate per the corrected
  version at ROADMAP:110-114 (the `first_4` oracle correction).
- [ ] 2. One authority for the Current-focus cap: ROADMAP:47-48,
  CLAUDE.md:470 and `.claude/commands/wp-handover.md:31` all say "~40 lines"
  while the test enforces 60; all three become "within `CURRENT_FOCUS_CAP`
  (tests/test_docs_consistency.py)".
- [ ] 3. CI, stop paying twice per merged PR: keep both triggers on `ci.yml`
  and `gui.yml`; add to each job
  `if: github.event_name != 'push' || !startsWith(github.event.head_commit.message, 'Merge pull request')`.
  NOT PR-only triggers — measured, 23 of the last 60 direct-to-main commits
  touch code and would go untested until Sunday. Header comment states the
  accepted risks: (a) merging after main moved lands a combined tree untested
  until the next tested push or weekly; (b) a push bundling direct commits
  under a merge head commit is skipped whole — rare, heals at the next tested
  push since CI tests trees, not diffs. A switch to squash merges makes the
  condition match nothing, which fails toward extra runs, never lost
  coverage. `docs.yml` unchanged (1 min; the push leg is most commits' only
  CI).
- [ ] 4. CI, monthly macOS → dispatch-only: `if: github.event_name ==
  'workflow_dispatch'` on the `macos` job (keep all steps + `full_macos`
  input). Grounds: the dev machine is darwin/arm64 and runs fast suite +
  goldens on every local run; the hosted runner is measurably not the capture
  machine (1 ulp off, job only warns); ~70 of 86 monthly billed min. Same
  commit adds the one guard it carried to `tests/test_backend_shim.py`: on
  `GOLDEN_PLATFORM`, assert the goldens' skip condition is false and the
  golden files load. Known pre-existing limitation: if the dev machine stops
  being darwin/arm64 the goldens run nowhere; the guard makes that visible
  locally. Torch job untouched.
- [ ] 5. CI, weekly matrix → `["3.11", "3.14"]` (3.12 is the dev venv,
  exercised daily; 3.13 runs per-push; keep the support-window boundaries).
  Full-job `timeout-minutes` 90 → 120 (measured drift 44:21 → 77:52; a drift
  past 120 should fail loudly, not get another silent raise).
- [ ] 6. CI, price comments become rules + dated ranges: keep the stable
  rules (2000 free min/mo, billed rounded up, macOS 10×, "price a job before
  adding it") and at most one dated per-job *range*; drop every
  cross-workflow monthly total in favor of "read totals from the Actions
  usage page / `gh run list`, never from comments", citing the measured rot
  (303 written vs ≈495). Same treatment in `tests/CLAUDE.md` § CI and
  `docs/DESIGN.md` ~504.
- [ ] 7. CLAUDE.md indexing block (~497-692) → ~25-line digest at root + new
  subsystem rulebook `src/pxrdref/indexing/CLAUDE.md`. The dossier's *rules*
  (compressed, one-clause evidence + pointer each) move to the new rulebook,
  which auto-loads exactly when a session works under `indexing/` (the
  repo's own mechanism — `gui/`, `tests/`); the *stories* stay in the v1.0
  appendix + WP files. Root keeps only what governs behavior outside
  `indexing/`: (a) tolerance-vs-window (fitted σ is the right weight and the
  wrong matching window; corundum 11σ; `INDEX_SHIFT_ALLOWANCE`; an
  un-shift-refined cell is biased ~+1400 ppm); (b) no confident singleton
  (`best_or_none()`, ranked extinction classes); (c) the gate (`high` = zero
  caveats; mandatory Le Bail validation; `predicted_but_absent` = "predicts
  absent lines", never "too big"); (d) confidence-is-agreement (three engines
  failing differently; the panel ranks, never scores); (e) run
  `tests/test_acceptance_indexing.py` before closing anything touching an
  engine; (f) pointer to the rulebook + appendix, with the admission rule "a
  new indexing rule lands in `src/pxrdref/indexing/CLAUDE.md`; it earns a
  clause at root only if it changes behavior outside `indexing/`". Add the
  new path to `_planning_docs()` so its links are checked. Safety rule (the
  cap test's own message — "move narrative, never delete facts"): for each
  clause dropped from root, verify it lands in the rulebook or already exists
  in v1.0.md / its WP file; anything found nowhere else moves verbatim in the
  same commit.
- [ ] 8. CLAUDE.md testing rules + protocol restatement compressed: lines
  24-47 keep `--dist loadgroup` rationale (~4 lines),
  wall-clock-as-a-range + extras-with-any-count, say-which-numbers-moved,
  and one compressed budget clause ("a wall-clock budget in a test is a
  runaway guard, never a timer — and the budget may live one rank down, in
  the library"); demote group-ordering and budget-narrowing detail to a
  tests/CLAUDE.md pointer. Lines 487-491 → pointer to ROADMAP § Session
  protocol + two clauses (commit prefix; "rules, not findings"). Promote ONE
  line from tests/CLAUDE.md that bites sessions which never load it: "a
  worktree needs its own venv" (into Commands, after the setup line).
- [ ] 9. `### Current numbers` → ~6-line `### Numbers` (measure, never
  quote): local fast-suite command is the recipe (never add `-q` — addopts
  has one, `-qq` prints no summary); full-suite counts + `--durations` from
  the latest weekly `full` job log (`gh run list --workflow weekly.yml`,
  `[dev,jax]`, Linux); quote any count with venv + platform; a session's own
  counts go in its WP handover entry. Same commit updates the two consumers:
  `.claude/commands/wp-handover.md` step 6 (→ "record in the handover
  entry"; keep the passed+skipped-moves-by-exactly-N check) and ROADMAP:44
  protocol rule 4. Trade-offs stated here: the weekly log is ~90-day
  retention, up to 7 days stale, one platform/venv point — cross-venv claims
  still need the local recipe. Grepped 2026-08-06: no test parses the
  section; closed-WP mentions are frozen archive.
- [ ] 10. ROADMAP, move closed-WP narrative to the milestone record: blocks
  at ~185-191, 254-427, 455-514, 528-540 (verify — lines will have moved) go
  to `docs/milestones/v1.0.md` § "How v1.0 is getting here"; re-base links;
  rewrite Current focus to ~35 lines.
- [ ] 11. Pin the caps (LAST): `SIZE_CAPS` CLAUDE.md 720 → landed+~50
  (expect ~580), ROADMAP 650 → landed+~60 (expect ~400); NEW caps for the
  so-far-uncapped always-loaded rulebooks at landed+headroom —
  `gui/CLAUDE.md` (494 today), `tests/CLAUDE.md` (145),
  `src/pxrdref/indexing/CLAUDE.md`. Rewrite the SIZE_CAPS comment block
  (test_docs_consistency.py:43-60) to record this pass and the admission
  rule, per its own instruction ("make it in a commit that says so").

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_manual.py tests/test_backend_shim.py
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # passed+skipped moves by exactly the one new shim-guard test
```

`tests/test_docs_consistency.py` green at every commit (caps only tighten in
task 11). After the first post-merge push: `gh run list --limit 10` shows the
push-event CI run for a merge commit skipped and a direct code push still
tested; `workflow_dispatch` on monthly.yml still offers the macOS job.

Expected effect, to re-measure at close: CLAUDE.md ~720 → ~530 lines;
scheduled CI ≈495 → ≈400 billed min/month (macOS cron −70, weekly matrix
−~26); each merged PR stops paying its ~9–22 min rerun.

## References

Survey measurements 2026-08-06 (docs inventory / CI cost / growth-and-payoff),
recorded in this file's Context; documented-catch citations live in the files
they name (CLAUDE.md invariants, `docs/wp/1030`, `1036`, `1037`, `1040`,
`1041`, `docs/milestones/v1.0.md` appendix).

## Handover log

- **2026-08-06** — created, from the approved two-WP plan (trim + workflow
  robustness, this one the trim). Planning session measured everything cited
  in Context; nothing has been executed yet. Line numbers are 2026-08-06
  measurements — re-verify before editing.
