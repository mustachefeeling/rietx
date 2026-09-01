# WP-1321 — the bounds a Parameter field declared: repair and audit

Milestone: unscheduled · Status: ⬜
Depends on: — (PR #206 merges first: its validator and `model_fields_set`
discriminator are this WP's reference behaviour)

## Goal

Everything issue #204 uncovered that PR #206 does not reach, in three parts:
documents already persisted with the dropped bounds are repaired at read
with a diagnostic that says so (#209); the same `default_factory` hazard on
`Phase`, `PreferredOrientation` and `Instrument` is sorted and closed; and
the skill guidance that hid the defect for a session is reworded. The
shipping PR closes **#209 and #204**.

## Context

From issues #204 and #209 (the maintainer's follow-up filed from PR #206's
review), 2026-09-01 benchmarking campaign.

**The defect and its cost (#204).** `Atom.biso`/`Atom.occ` declared their
physical range in a `default_factory`, so a caller-supplied
`Parameter(value=…, vary=…)` silently got `(-inf, inf)` and no unit. On a
narrow 25–50° four-phase QPA scan, Fe's Biso ran to **−165 Å²** with its
scale at 4.66e-12, and two staging orderings returned Fe at **0.0 wt%** and
**80.9 wt%** (TOPAS: 27.1) at Rwp agreeing to ~11 significant figures —
the same solution on a single `scale·exp(−2Bk²)` ridge, scales 4.4×10⁹
apart, `ln(scale ratio)/(ΔB·k²) = 1.98 ≈ 2`. Bounded 0.5–4.0, the worst
standardised pull drops >3σ → 0.16σ and Rwp does not move. PR #206 fixes
construction: bounds/unit inherit from the declared default wherever the
caller's `Parameter` left them out of `model_fields_set`, so an explicit
bound still wins and only a true omission inherits.

**Task group 1 — the reader-side repair (#209, scope as filed).** #206
cannot reach documents the defect already produced: `model_dump` writes
`min`/`max` explicitly, so a project or history node saved from an affected
run arrives with `model_fields_set` complete, inherits nothing, and reloads
unbounded (verified on the #206 tree with a stored
`biso: {"value": -165.0, "min": "-Infinity", "max": "Infinity"}`). The
repair belongs **in the reader, with a `Diagnostic`, not in a schema
validator**: the root rule — a silent correction is a reader's to make,
never a table's, because only the read path has a diagnostics channel — and
explicitly *not* the `PreferredOrientation._r_bound_is_reachable`
silent-validator precedent, whose licence rests on severity (a pole feeding
the solver NaNs) that a merely-loose bound does not carry. Seam: the
history/project load path; whether it needs a diagnostics channel *added*
is an open design point decided in-WP, not assumed. Scope: a persisted
`occ`/`biso` whose stored bound is wider than the declared default is
repaired, the new code naming the atom and both bounds.

**Task group 2 — the wider audit #206 flagged and nobody owns.** The same
shape (`Parameter` field, bound-carrying `default_factory`) exists on
`Phase` (`scale`, `extinction`, `lor_size`, `lor_strain`, `gauss_size`,
`gauss_strain`), `PreferredOrientation.r`, and extensively on `Instrument`
(Caglioti U/V/W/X/Y, zero-shift, displacement/transparency, background-peak
parameters, emission-line weight). Not mechanical: the root softplus rule
means each field is sorted by hand into zero-is-off-state (an omitted
`min=0` is a milder hazard — the transform already floors) versus
physics-divides or a genuinely two-sided range (a real loss). Extend the
inheritance where the bound is real; record the sorting field by field.
#206's generic discovery test over `Atom.model_fields` is the template —
each class gets one, so a field added later is covered without naming it.

**Task group 3 — the guidance that hid it (#204's doc residue).**
`SKILL.md` §9 and `references/judging.md` say the McCusker
`max_shift_over_esd` band gates nothing and "a converged solve satisfies it
a fortiori, so read it where a stage stopped on `STAGE_MAX_ITER`". The
campaign's run reported `converged` on all six stages while
`max_shift_over_esd` sat at **70.1** (4.02e-05 once bounded): the clause
instructs the reader to ignore the one number that pointed at the cause.
Reword: read it on *every* solve; a large value on a nominally converged
one is the signature of an unbounded or degenerate direction. Wording only
— the band still gates nothing.

**Recorded, no action here**: #204's sub-finding that
`internal_bounds(0.0, inf, "softplus") → (-inf, inf)` means `BOUND_HIT` can
never report "scale went to zero" is intended behaviour (the transform
enforces positivity; there is no bound to hit) and is noted in WP-1311's
Inherited for its flat-direction item.

## Non-goals

- **Not the construction-time fix** — PR #206's, merged before this runs.
- **Not a repair of values** — only bounds/unit are healed; a stored −165
  then *raises* through `Parameter._check_bounds` exactly as a fresh one
  would, and choosing a replacement value is the caller's.
- **Not new bounds policy** — the declared defaults are the reference;
  inventing tighter ranges is WP-1311's flags-not-caps territory.

## Tasks

- [ ] Reader-side repair for persisted `occ`/`biso` wider than the declared
      default, emitting a new diagnostic code naming the atom and both
      bounds; the load path's diagnostics channel decided and, if new,
      minimal.
- [ ] Test: a document written before #206 loads repaired *and* reports; a
      document already within the declared bounds is untouched byte-for-byte.
- [ ] The audit: every bound-carrying `default_factory` field on `Phase`,
      `PreferredOrientation`, `Instrument` sorted into the two classes with
      the sorting recorded; inheritance extended where the bound is real;
      per-class generic discovery tests on #206's template.
- [ ] `max_shift_over_esd` rewording in `SKILL.md` §9 and
      `references/judging.md` (all committed skill copies re-synced).
- [ ] Skill diagnostics row for the new code (all committed copies) +
      `help.py`/manual coverage per standing gates.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_schemas.py tests/test_project.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: the #209 fixture (a pre-#206 document carrying an unbounded biso)
loads with the declared bounds restored and one diagnostic naming atom and
bounds; every audited field's class is written down; no accepted value
moves on any clean document.

The shipping PR carries `Closes #209` and `Closes #204`.

## References

- Issues #204 and #209; PR #206 — the validator, the discriminator, the
  field list, the discovery-test template.
- Root CLAUDE.md — the silent-correction rule (`CIF_SPECIES_NORMALISED` /
  `CIF_CELL_ANGLE_CORRECTED` shape) and the softplus min=0 rule.
- [1311](1311-walking-parameter-bounds.md) — the adjacent flags work; its
  Biso low-side premise now rests on #206.

## Handover log

- **2026-09-01** — created, from issues #204/#209 and PR #206's review
  (2026-09-01 triage, second batch). Settled: repair in the reader with a
  diagnostic, never a validator; values raise, bounds heal; the audit is
  by-hand sorting under the softplus rule, not a mechanical sweep. First
  open decision is the load path's diagnostics channel.
