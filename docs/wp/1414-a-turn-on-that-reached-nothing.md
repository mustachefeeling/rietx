# WP-1414 — a `turn_on` that reached nothing says so

Milestone: unscheduled · Status: 🔄 2026-09-22 — claimed by @yue-here (cloud session)
Depends on: — (1341 soft: the joint fit's report is where the per-histogram
finding is rendered)
Priority: P2 2026-09-23 — a stage that freed nothing converges anyway; the parameter table shows it held, nothing fires

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

- **2026-09-15** — created, from the 2026-09-15 issue triage (issue #265).
  Checked against the tree: `StageResult.freed` already answers "what was
  freed", so the gap is the unmet ask; the comment's forward-model-unread
  row is fork-only on `main`. Recommendation recorded: diagnostic, not raise.
