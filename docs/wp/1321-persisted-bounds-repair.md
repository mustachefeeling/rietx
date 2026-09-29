# WP-1321 — the bounds a Parameter field declared: repair and audit

Milestone: unscheduled · Status: 🔄 2026-09-29 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: — (PR #206 landed 2026-09-01: its validator and `model_fields_set`
discriminator are this WP's reference behaviour)
Priority: P2 2026-09-23 — bounds dropped in silence on documents already saved, and the sibling hazard unmeasured

## Goal

Everything issue #204 uncovered that PR #206 does not reach, in three parts:
documents already persisted with the dropped bounds are repaired at read
with a diagnostic that says so (#209); the same `default_factory` hazard on
`Phase`, `PreferredOrientation` and `Instrument` is sorted and closed; and
the skill guidance that hid the defect for a session is reworded. The
shipping PR closes **#209 and #204**.

## Context

### Findings re-checked 2026-09-29, and the Inherited folded

The WP was written on 2026-09-01. Against `f1b89d6`, five things it assumed
have moved, and four Inherited entries are folded here rather than kept as
mail.

- **PR #206 landed**, and so did WP-1311's rider on it (2026-09-18,
  `Atom._inherit_declared_bounds`' docstring): the 25 Å² `biso` ceiling is
  this package's own and not a physical limit (25 Å² needs 109–338 Å³ per
  atom to be reachable below melting, Gilvarry 1956 via
  `strategy.staged.biso_melting_bound`), and it was **kept** on the
  maintainer's ruling that changing a v0.1 default is a user-facing break.
  A persisted unbounded `biso` is a repair, not that break: the repair
  restores the default that was always declared.
- **Superseded in part: the scope clause "a stored bound wider than the
  declared default is repaired".** WP-1311 made an explicit *wider* bound the
  documented escape for a hot specimen (`biso=Parameter(value=8.0, max=60.0)`),
  so width is no longer the defect's signature. The signature is an attribute
  holding the bare `Parameter`'s own default (±∞, no unit, `identity`) in a
  document written **before** its class inherited, the only trace an omission
  leaves once serialized. After that version an explicit `min=-inf` is a
  deliberate choice, and #206 says it wins, so the gate is the tree header's
  `schema_version`.
- **Superseded in part: the audit's two classes.** Context below sorts fields
  into zero-is-off-state ("the transform already floors") and the rest. A
  caller's bare `Parameter` carries `transform="identity"`, so it drops the
  softplus floor together with the bound, and `ParameterTable` takes the
  transform from the `Parameter` (`params/vector.py`), never from the path.
  The floor exists only where the transform is inherited, and a transform may
  travel only with the bounds it enforces: softplus inherited under a
  caller's explicit `min=-1` would clamp their value to 1e-12 at the first
  decode.
- **The instrument profile already has a stance** (WP-1312, 2026-09-11):
  `ProfileTCHZ._refuse_bare_widths` refuses a bare *number* by name, and a
  `Parameter` passes untouched, so `ProfileTCHZ(u=Parameter(value=1.576))`
  is still the #204 shape. `PreferredOrientation._r_bound_is_reachable` and
  `HumpComponent._fwhm_floor_is_reachable` repair a floor softplus cannot
  enforce on every path, silently, licensed by the pole; the reader-side
  repair here is not that precedent (Context below).
- **The infinite-bound-means-no-claim readers, audited first** as WP-1440
  asked, since that reading is why PR #289's `Cell` bounds were withdrawn
  (issue #283's bounds half, which the 2026-09-23 triage placed here).
  `cell_window`/`freeze_cell_windows` and the TOPAS reader's
  `cell_limits` read only `Cell`, whose fields declare no bound and so are
  not this hazard's shape; a physical box for the cell is new bounds policy,
  this WP's non-goal, and stays the maintainer's, so **#283 stays open**.
  `strain_cap_hi`/`size_cap_hi` read an infinite `max` on the four `Phase`
  widths as no claim, and those fields declare `max=inf`, so inheriting
  their declared `min`/`transform`/`unit` leaves the cap's reading alone.
  `_tie_windows` builds a window from any finite bound on a tied entry, so a
  bare `Parameter` newly inheriting one also windows its tie source, which is
  the declared range doing its job. `PeakComponent._window_bounds_are_finite`
  refuses a non-finite window bound, which an inherited `fwhm` box then
  satisfies; `center` declares no bound and stays refused.
- **Recorded, no action here** (from WP-1463, 2026-09-28): a softplus field at
  its floor reads `at_bound=None` (`staged.bound_untested`), and a width near
  zero whose column goes through the peak chain can lose its esd outright,
  since once σ(u)·h moves it by less than an ulp the finite-differenced column
  is exactly zero (`test_multi_histogram`'s joint fit leaves
  `instrument.profile.y` at 4.5e-69 with no esd, on main too). Inheriting the
  softplus floor does not remove that cost.
- **The skill body is over budget** (from WP-1338, 2026-09-28): 30 509 B
  against the specification's 17 000, so a change may not grow it
  (`tests/skill_caps.py`), and a body sentence is paid for by a cut. Task 4's
  rewording is therefore a replacement of equal or smaller size.

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
