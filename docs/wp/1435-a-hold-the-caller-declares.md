# WP-1435 — a hold the caller declares, which a plan may not quietly override

Milestone: unscheduled · Status: 🔄 2026-09-18 — claimed by @yue-here
Depends on: — (WP-1070 is the shape to copy, already shipped)

## Goal

A caller can say "this parameter does not move, whatever the plan asks for",
and that declaration outranks a stage's `turn_on` glob. A plan that would have
freed a held path says so instead of doing it silently.

## Context

From issue #211, and from [1310](1310-report-repeats-itself.md), which
reproduced it and measured the fix the issue proposed into a dead end.

**The defect.** A stage's `turn_on` glob frees a parameter the caller declared
`vary=False`. `ParameterTable.set_vary` cannot tell a deliberate pin from a
default, and `apply_to_models` writes the refined value back without writing
`vary`, so the value moves while the model still reads `vary=False`.
Reproduced 2026-09-16: a LaB6 whose six cell parameters are declared
`vary=False`, fitted under a plan whose second stage carries
`phases.*.cell.*`, refines `cell.a` from the declared 4.15660 to 4.156599952
while `ref.structure.phases[0].cell.a.vary` still reads `False` and no
diagnostic names it. `RefinementResult.parameters` does report `vary=True`, so
the result and the fitted model contradict each other about one parameter.

**It is the failure mode of calibrate-on-a-certified-standard.** You hold a
certified cell precisely so the zero, the displacement and the profile terms
have something fixed to decorrelate against (`lab_calibrate`, and root
CLAUDE.md § Instrument ⊕ sample profile split says it in one line: "with its
**certified cell held fixed** — that is what decorrelates
zero/displacement/cell"). A plan that frees that cell leaves a calibration
that is worthless and looks clean. The issue's measured cost is an invalidated
pin-and-scan study.

**The diagnostic the issue asks for cannot be built.** Measured on the shipped
LaB6: **41 of 42 entries are declared `vary=False`**, because that is the
default rather than a decision. So "declared fixed and freed by the plan"
names nearly everything a plan touches:

| plan | frees | of which declared fixed | with the cell pinned |
|---|---|---|---|
| `mccusker_default` | 17 | 16 | 17 |
| `mccusker_structural` | 21 | 20 | 21 |
| `lab_bragg_brentano` | 21 | 20 | 21 |
| `lab_calibrate` | 17 | 17 | 17 |

A caller's pin moves one number in seventeen. A diagnostic keyed on it would
print sixteen useless lines and one that matters, which is the
confident-wrong-signal shape this repo gates against rather than ships.
`__pydantic_fields_set__` *does* separate an explicit `vary=False` from a
default one in memory, and does **not** survive a JSON round trip — every
field comes back set — so a project opened from disk would report every
parameter as deliberately pinned, and that is the commonest path.

**So the missing thing is an authority, not a message.** A user's declaration
has nowhere to live that a plan can read, which is exactly the problem WP-1070
solved for *ties*: `Refinement._ties` is the one authority for which ties are
the user's, every `ParameterTable` build rederives the symmetry ties and knows
nothing of a user's, and `RefinementState.ties` is why a checkout restores the
parameter count. A hold is the same construction over `vary` instead of over
ties, and it inherits WP-1070's precedence discipline: symmetry outranks a
user tie, enforced in `_apply_ties` and not only in the verbs' refusals,
because a model edit can make an already-tied path symmetry-tied after the
fact. The hold analogue: a locked or `mode_fixed` row outranks a user hold,
and a user hold outranks a plan's glob.

**Prior art, and it is close.** GSAS-II carries constraint type `'h'`: it
"defines a variable to hold (not vary)", and "any variable on this list is not
varied, **even if its refinement flag is set**". Its documented purpose is the
case here — "of particular value when needing to hold one or more variables
where a single flag controls a set of variables such as, coordinates, the
reciprocal metric tensor or anisotropic displacement parameter". That is a
`turn_on` glob in other words. GSAS-II is GPL: **concepts only, never code**.
FullProf's codewords express the same thing differently, a code of 0 being
fixed, with no separate override channel. TOPAS fixes by default and marks a
refinable parameter with `@`, so a macro that refines something overrides in
the same way rietx's plan does.

**No conflict with WP-1208.** Its rule is that a plan *replaces* the vary
flags rather than continuing them, which stays true. A hold is not a vary
flag, and the whole point of GSAS-II's separate list is that it is a different
kind of statement.

## Non-goals

- **Not the `vary` write-back on its own.** Making `apply_to_models` write
  `vary` would stop the model contradicting the result, and the flag would then
  persist into a later unplanned fit and free the parameter there. That is a
  behaviour change smuggled in under a record fix, so it lands with the hold or
  not at all.
- **Not user constraints.** `tie`/`tie_equal`/`untie` are WP-1070's and
  shipped; this reuses their shape and touches none of them.
- **Not plan authoring.** Whether a preset plan *should* free the cell is a
  question about the presets, not about whether a caller can refuse.

## Tasks

- [ ] `Refinement._holds` as the one authority, on `_ties`' model, with
      `hold`/`unhold` verbs taking the same globs `set_vary` does and
      auto-committing nodes. A held path refuses an edit that would free it
      and names the hold, as a tied path refuses and names its sources.
- [ ] Precedence in the one place that applies it, never at the call sites:
      `locked`/`mode_fixed` outranks a hold, a hold outranks a stage's
      `turn_on`. A model edit can make a held path locked after the fact, so
      the check is re-asked where it is applied (WP-1070's lesson).
- [ ] `RefinementState.holds` so a checkout restores them, and the project
      document carries them. A hold that does not survive reopening a `.rex`
      is worse than none, because it is a promise that lapses silently.
- [ ] `ParameterRow.held_because` gains the hold as a fourth reason, and
      `parameters()` reports it. The row already names which of three reasons
      holds a path, so this is one member, not a new channel.
- [ ] A plan that matched a held path reports it: `StageResult` records what
      the glob would have freed, and one diagnostic names the paths. This is
      now a real signal because the set is the caller's own declarations
      rather than every default.
- [ ] Tests: the calibrate-on-a-standard case end to end, asserting the cell
      does not move and the report names the plan's attempt; a checkout
      restoring holds; the precedence pairs; and the refusals. Plus
      obs/calc/diff PNGs to `tests/output/`.
- [ ] Manual: `using/` gains the hold beside the user constraints, and the
      calibration chapter says plainly that holding a certified cell is what a
      hold is for.
- [ ] Skill: a body rule, since it holds for every fit — a caller who needs a
      parameter to stay put says so with a hold, because a plan's glob
      outranks `vary=False`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_params_surface.py tests/test_project.py tests/test_history.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: a LaB6 with its cell held, fitted under a plan carrying
`phases.*.cell.*`, comes back with the cell bit-identical to the declared
value and a diagnostic naming what the plan wanted to free; the hold survives
a save and reopen; a locked path still refuses a hold that would contradict
it.

The shipping PR carries `Closes #211`.

## References

- Issue #211 — the invalidated pin-and-scan study.
- [1310](1310-report-repeats-itself.md) § 5 — the reproduction, and the 41-of-42
  measurement that rules out a `vary`-keyed diagnostic.
- [1070](1070-user-facing-constraints.md) — the authority shape to copy, and its
  precedence discipline.
- GSAS-II constraint type `'h'`, [GUI components](https://gsas-ii.readthedocs.io/en/latest/GSASIIGUI.html)
  and [data object organization](https://gsas-ii-scripting.readthedocs.io/en/latest/objvarorg.html).
  GPL: concepts only.

## Handover log

- **2026-09-16** — created by WP-1310's session, which reproduced issue #211
  and measured its proposed fix into a dead end. The issue asks for a
  diagnostic; 41 of 42 parameters are declared fixed by default, so no
  diagnostic keyed on `vary` can separate a caller's pin from the default.
  The first action is `Refinement._holds` on WP-1070's model, because every
  other task reads it.
