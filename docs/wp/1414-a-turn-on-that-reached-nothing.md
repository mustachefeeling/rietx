# WP-1414 — a `turn_on` that reached nothing says so

Milestone: unscheduled · Status: ✅ 2026-09-22 — a literal that names nothing warns with the nearest path; a joint stage that reached one histogram says which it missed
Depends on: — (1341 soft: the joint fit's report is where the per-histogram
finding is rendered)

## Goal

A stage that asked for a parameter and did not get it says so. A literal
`turn_on` path that matches no entry is reported with the nearest real path,
and a stage that freed nothing in a histogram is reported per histogram.
A glob that legitimately matches nothing in this model stays silent, because
the shipped plans depend on that.

## Context

Issue #265 (2026-09-04), measured on `origin/main` `4a0df3d1` with the
repo's own `make_lab6` and a flat synthetic pattern, plus its comment of
2026-09-08 from the fork's TOF and joint-fit branches.

**What happens.** A stage whose `turn_on` names `instrument.source.wavelength`
frees nothing and says nothing. The table offers
`instrument.source.lines.0.wavelength` (the only shape `_is_wavelength`
recognises, `params/vector.py`, `WAVELENGTH_SUFFIX`), and freeing that path
behaves as documented (`WAVELENGTH_CALIBRATION` fires). Four cases from the
reproduction:

| case | n_free | anything said |
|---|---|---|
| literal path that does not exist | 0 | nothing |
| the working spelling | 1 | `WAVELENGTH_CALIBRATION` |
| a legitimate glob that matches nothing in this model (`phases.*.microstrain.dof.*`, which `lab_sample_refine` ships) | 0 | nothing |
| a typo inside a glob (`phases.*.cel.*`) | 0 | nothing |

Rows 3 and 4 are why "warn when a `turn_on` entry matches nothing" is the
wrong rule. It would fire on every healthy plan. What is unambiguous is a
**literal** path, one with no `*`, `?` or `[`. It names one parameter, and
if the table has no such entry the caller is wrong: a typo, or a path renamed
under them (`schemas/migrate.py` migrates stored *values* by name and stored
*globs* load clean and free nothing, root CLAUDE.md § Conventions; a literal
path in a plan is the value case).

**Why `set_vary`'s docstring does not already cover it.**
`ParameterTable.set_vary` explains why a wavelength row is skipped by glob
rather than raising: a staged plan frees by glob, and turning a broad plan
into an error would be worse than declining one row of it. That reasoning is
about a path that exists and is declined. A path that matches no entry is a
different fact. Nothing was declined, because nothing was found.

**What the result already says.** `StageResult.freed` (`schemas/results.py`)
records what a stage freed, written from `table.set_vary(stage.turn_on,
True)` at the top of `Refinement._run_stage`. So "what did this stage free"
is answered. "What did it ask for and not get" is not, and a caller who reads
`freed` sees the absence only by knowing what to expect.

**One case of this is already reported, and it is the shape to copy**
(WP-1435, folded from its `### Inherited` note on 2026-09-22). A `turn_on` has
a fourth reason to free nothing beside a locked row, a tied row and the
free-cell wavelength rule: a caller's `Refinement.hold`.
`StageResult.blocked_by_hold` is the per-stage record of what a glob matched
and could not free, and `HOLD_BLOCKED_PLAN` (info) is its diagnostic, built
from the records once per fit with `where` the union and the message naming
the stages, because a cumulative plan names the same glob in several stages
and per-stage rows print one sentence four times. Two rules came with it.
A `vary`-keyed report cannot be built: `vary=False` is the default rather
than a decision (38 of 46 entries on the shipped LaB6, measured 2026-09-18),
so a signal keyed on it names most of the table. And the reasons a row
cannot be freed are read off the row (`ParameterRow.held_because`) and off
`set_vary`'s **return**, never the list it was offered — 1435 found
`optimize/identifiability.py` indexing by a candidate `set_vary` had declined.

**The comment's two instances, one entry point over.** On a joint fit, a plan
written with `instrument.profile.*` globs freed four rows on the one
constant-wavelength histogram and zero on every bank, and the joint result
reported `converged` at Rwp 0.115 where the right globs give 0.066. That cost
a whole refinement. `MultiParameterTable.set_vary` returns its scoped hits
(`params/multi.py`), `multi.py` keeps `freed` per stage, and nothing surfaces
"zero on histogram h". The second instance, a row the forward model never
reads (`lor_size` on a flight-time bank), is fork-only: on `main` every table
row is read or force-fixed (WP-1073's rule: a parameter the forward branch
skips is force-fixed, never merely unfree), so it needs no code here and is
recorded so a TOF arm inherits the check.

**Design, and the triage's recommendation (2026-09-15).** A literal path that
matches nothing becomes a `warning` diagnostic at stage start, `where=[path]`,
naming the near-miss the way `rietx/__init__.py`'s `__getattr__` names a
module attribute ("did you mean …"). A diagnostic and no raise, because
one plan runs across a series where a pattern's model may lack the path, and
a raise would take the chain with it (1333's class). A stage whose whole
`turn_on` matched zero rows in a histogram gets `STAGE_FREED_NOTHING` (info)
per histogram, naming the globs. A single glob that matched nothing on its
own stays silent. Whether a `PlanSpec` validator should refuse the literal
case before any fit is the maintainer's call; the diagnostic is the floor.

*Superseded in part, 2026-09-22:* the neighbour this paragraph named (1310's
#211, a `turn_on` glob overriding an explicit `vary=False`) shipped as
WP-1435, whose report is described above. There is nothing left to land
beside it.

## Non-goals

- The glob-skips-rather-than-raises trade-off in `set_vary`'s docstring.
- A joint fit's report surface (1341) and its per-histogram diagnostics
  entitlement (1344). This WP adds one finding they render.
- TOF banks and their parameter families.

## Tasks

- [x] `set_vary` (single and multi) distinguishes a literal path from a glob
      and returns, or exposes, the literals that matched no entry.
- [x] The stage runner emits the literal-path diagnostic with the nearest
      real path (one shared near-miss helper with `__getattr__`), and
      `STAGE_FREED_NOTHING` per histogram when a stage's whole free list
      matched zero rows there.
- [x] A `StageResult` field per finding, with the two diagnostics built from
      the records the way `HOLD_BLOCKED_PLAN` is, and a `SCHEMA_VERSION` bump.
      *Superseded in part, 2026-09-22:* this task read "`GuardFinding`
      constructors and `help.py` entries for both codes (`tests/test_help.py`
      fails until they exist)". Neither is where a code like these lives.
      `GuardFinding` (`strategy/staged.py`) holds what the post-solve guards
      found, and nothing about a plan's reach is decided after the solve.
      `help.py` carries `PEAK_*` codes only. An engine code is meta-tested by
      `test_docs_consistency.test_every_engine_diagnostic_code_has_a_protocol_row`
      against the skill's references, which the last task covers.
- [x] Tests: the four-row reproduction above as a parametrised test, and a
      two-histogram fit whose plan reaches one histogram only.
- [x] Skill: a `references/diagnostics.md` row per code, and a
      `references/surprises.md` row that a glob matching nothing is normal
      and a literal matching nothing is a typo.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_params_surface.py tests/test_multi_histogram.py tests/test_help.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #265 (2026-09-04) and its comment of 2026-09-08.
- WP-1073 (the force-fixed rule); WP-1310 (#211); WP-1341, WP-1344.

## Handover log

- **2026-09-23** — The count the close entry deferred, and nothing else
  changed. The fast suite on the final tree (`0f0feaa`; `[dev]` only, Linux
  cloud container, uid 0) ran 5482 passed / 147 skipped / 1 failed in
  12:51. The failure is the uid-0 `unwritable-directory` telemetry case
  below, and passed is +1 on the pre-review run, which is the review pass's
  one added test, so the branch's +13 against `main` holds.

  **Later that day: pushed, and stacked on WP-1333's PR #420** at the
  maintainer's request, once GitHub access returned. PR #421's base is
  `claude/bold-albattani-him8uh`, merged in rather than rebased. The one
  conflict was `SCHEMA_VERSION`, since #420 took 0.24 → 0.25, so this WP's
  fields are now 0.25 → 0.26. #421's diff against its base is the same 27
  files this branch changed against `main`, so it does not reach into #420's
  code. Fast suite on the stacked tree (same venv and container): 5499 passed /
  147 skipped / 1 failed in 12:45, the same uid-0 case. That is 5647 items,
  which is this branch's 5630 plus 17 from #420. #420's diff adds 16 test
  functions, one parametrized twice, so 17 is right and its body's "+18" is
  off by one. **No second review ran over the stack**: a branch-vs-`main`
  review now reads both PRs, so any further pass reads #421's diff against its
  base alone. Next: #420 merges first. If its handover adds commits, merge
  them in here again. Then retarget #421 to `main`, where `Closes #265` takes
  effect.

- **2026-09-22** — **closed.** A refinement plan that asks for a parameter by
  a name the model does not have now says so, and names the parameter it
  probably meant. Before this, the stage freed nothing, converged, and the
  result looked like any other. On a joint fit, a stage whose patterns
  reached one histogram's parameters and none of another's now names the
  histogram it missed. That was the silence that cost the issue's reporter a
  whole refinement. What this rules out is the simple version, a warning on
  anything that matched nothing: the shipped plans depend on patterns that
  match nothing on some models. So a typo *inside* a pattern is still
  silent, and the answer to it is reading what each stage freed.

  **Done.** `params.vector.is_literal_path` is the one test for "names one
  path" (it replaces four open-coded `"*?["` checks in `refine.py`), and
  `ParameterTable.unknown_literals` / `MultiParameterTable.unknown_literals`
  answer the half of `set_vary` its return cannot, as a separate question
  so no caller of the return changes. `MultiParameterTable.unreached_histograms`
  is the joint rule: histogram `h` is unreached when no glob addressing it
  matched any of its rows (locked, tied and held rows count as reached) while
  one of those globs matched another histogram's. A glob addresses `h` by a
  `hist.<seg>.` prefix, or by having matched a bare path anywhere, or else
  only where its scoped matches landed. Both runners record
  `StageResult.unknown_paths` and `.unreached_histograms`, and the diagnostics
  are built from the records the way `HOLD_BLOCKED_PLAN` is.
  `STAGE_PATH_UNKNOWN` (warning) is one per path naming its stages, and
  `STAGE_FREED_NOTHING` (info, top level) is one per histogram with `value`
  the index. The first also rides `stage_start` events (both of them, when a
  released phase sends a second). `rietx._nearmiss` is now the single "did
  you mean" for the three `__getattr__` hooks and the new code, and it folds
  case before `difflib` ranks: `instrument.profile.U`, Caglioti's U as papers
  print it, was answered `instrument.profile.y`. Manual (`refining.md`,
  the `StageResult` table and three paragraphs), skill (§7 rows for both
  codes, surprises § 8.28), release notes (`releases/1.5.1.md`), v1.6 record.
  `SCHEMA_VERSION` 0.24 → 0.25 as written, and 0.25 → 0.26 once stacked on
  WP-1333's PR #420, which took 0.25 first.

  **The two fields default to `None`, not empty, and that differs from
  1435's precedent on purpose.** No hold could exist before its field, so `[]`
  was true of every older result. A typo'd literal freed nothing in silence
  long before this one, so `[]` on a result stored before 0.26 would claim a
  check that never ran, which is WP-1076's rule. Every runner writes a value.
  A single-histogram fit writes `unreached_histograms={}`.

  **Review** (`/code-review high --fix`): eight findings, seven fixed in
  `e16c44e`. The five it applied: the joint `STAGE_PATH_UNKNOWN` named
  `ref.parameters()`, which `MultiHistogramRefinement` lacks (the suggestion
  now takes the caller's `listing=`); `STAGE_FREED_NOTHING` named no working
  listing; the second `stage_start` dropped `unknown_paths`; `multi.py`
  reached into a private helper (now `MultiParameterTable.known_paths()`);
  and the manual said "raises" of two diagnostics that are not exceptions.
  Two it declined, taken by me: `*.1.instrument.zero_shift` addressed every
  histogram and reported a miss on the others, and the empty defaults above.
  **Declined:** `unreached_histograms` re-matches the globs itself rather than
  reusing `set_vary`'s matching, so there are two statements of "this glob
  reached histogram h". Unifying them means changing `set_vary`'s return,
  which a dozen callers read, and that is out of this WP's reach. Both use
  bare-or-scoped `fnmatchcase`, and `test_a_glob_that_reached_one_histogram…`
  pins the cases.

  **Measured** (`[dev]` only, no jax/torch; Linux cloud container, uid 0,
  load-contended). Issue #265's four rows reproduce as the WP's table said,
  and after the change only the literal row speaks: `STAGE_PATH_UNKNOWN` with
  "did you mean 'instrument.source.lines.0.wavelength'". Every literal in
  every shipped preset exists on all five instrument constructors
  (Debye-Scherrer, Bragg-Brentano, flat-plate transmission, CW neutron with
  and without harmonics), force-fixed where unused, so the warning cannot
  fire on a shipped plan (pinned by
  `test_the_shipped_presets_name_no_path_a_shipped_instrument_lacks`). Fast
  suite on `3400f15`, before the review pass: 5481 passed / 147 skipped /
  1 failed in 13:04, the one failure the container's (below); the
  final-tree run is quoted in the next entry line once it lands. +13 tests exactly (11 in
  `test_params_surface.py`, 2 in `test_multi_histogram.py`), the only test
  diff being additions, and no new skip. **The full suite was not run**: no
  forward model, solver or statistic changed, and the one way a new
  diagnostic could move an acceptance suite is a diagnostics-set assertion.
  So the slow tests of every file that runs a joint fit, or that asserts on
  warning levels, ran instead: 20 passed and 1 failed, the wall-clock guard
  below.

  **Two failures that are the container's, not this change's.**
  `test_telemetry.py::…[unwritable-directory]` provokes a read-only
  directory with `chmod 0o500`, which uid 0 ignores (shown directly: root
  creates a directory inside one). It fails on any root runner, CI's
  included if it ever ran as root. `test_held_phase.py::test_the_ramp_reproduction_no_longer_runs_away`
  blew its 60 s wall-clock runaway guard under a saturated xdist run and
  passes alone in 11.75 s, with its deterministic iteration-count assertion
  passing both times.

  **Not delivered: the push.** Every `git push` from this cloud session got
  GitHub 403 ("Claude doesn't have GitHub access to yue-here/rietx"), so there
  is no draft PR and no claim visible off this machine. The commits were
  handed to the maintainer as a patch series and a git bundle.

  **Next.** (1) Apply the bundle on a local clone and push the branch; the
  PR body is the entry above. (2) The maintainer's call the WP left open,
  whether a `PlanSpec` validator should refuse an unknown literal before any
  fit, now has a floor to decide against. `STAGE_PATH_UNKNOWN` is that floor,
  and a validator could not know the model a plan will meet, which is the
  argument against. (3) The same unknown-literal answer is still missing on
  the verbs: `Refinement.set_vary("instrument.zero")` returns `[]` silently,
  while `hold` raises "unknown parameter path" with no near-miss. Both are
  one call to `rietx._nearmiss` away, and are unowned. (4) 1341 and 1344
  inherit where the joint finding renders.

- **2026-09-15** — created, from the 2026-09-15 issue triage (issue #265).
  Checked against the tree: `StageResult.freed` already answers "what was
  freed", so the gap is the unmet ask; the comment's forward-model-unread
  row is fork-only on `main`. Recommendation recorded: diagnostic, not raise.
