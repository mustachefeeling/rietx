# WP-1938 — every parameter refined in its own units

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 1936 (the FD step, landed 2026-10-09), 1937 (a driver that handles widths on zero)
Priority: P2 2026-10-09 — the base WP-1929's P1 rests on; WP-1936 landed, so only 1937 still blocks it

## Goal

The solver refines every parameter in physical units, with its declared
`min`/`max` passed to the driver as box bounds. Softplus, logit and exp stop
being solver coordinates. A fit whose minimum sits on a floor reaches the same
point and reports the same esds on every platform, with no seed and no
special case for a tiny column.

## Context

**Why** (WP-1929's second session, 2026-10-09; macOS arm64, `[dev]`, tree
`35f4ac14`). Softplus p = log(1 + eᵘ) (`params/transforms.py`; a lower bound
≤ 1e-12 maps to internal −∞) does two harmful things near zero. Its column
is expit(u)·∂r/∂p, so a step in u moves p below rounding and the column is
noise that equilibration turns into a direction: BT-1's `profile.x` esd came
out 0.0032, 0.0066 or 0.0089 at one χ² depending on where u stopped. And its
gradient vanishes, so rounding chooses whether a floored width ever leaves
(WP-1930): LaB₆ + cBN reached four minima, χ²_red 9.69–12.51, across five
starts nudged by 1e-14. With softplus entries made identity and
`lo = max(lo, 0)` (a monkeypatch of `ParameterTable.__init__`), TRF reached
one minimum on every fit except where TRF's own bound handling crawls
(WP-1937), and BT-1's `profile.x` esd was 0.0098437 at every stopping point,
the value a hand-computed physical column gives.

**What a softplus coordinate was buying.** Log-like steps for a value near
zero, so a floored width stops moving and redundant widths settle (why
brucite and corundum converge under softplus + TRF). An active-set driver
(WP-1937) does that explicitly. A per-parameter FD scale (WP-1936) replaces
the relative step softplus gave by accident.

**Readers that branch on the word** (the adversarial review's list, and a grep
of the merged tree). Each would silently change meaning:

- `ParameterTable.seed_softplus` (`params/vector.py`, the `transform ==
  "softplus"` filter): `Stage.seed` and `suggest()`'s probe
  (`SUGGEST_SEED_SOFTPLUS`, `refine.py` near `seed_softplus(cand_paths`) do
  nothing under identity. The review measured a joint `lor_size` stage
  starting at cost 1 022 348 instead of 990 890. Decide per caller whether a
  seed is still needed once the gradient at a floor is physical.
- WP-1930's `seed_floor` / `FLOOR_SEEDS` / `SOFTPLUS_FREED_AT_FLOOR`
  (PR #849, not on `main` at this writing) exist only because of the trap.
- `io/recipe.py:739` and `:771`, `io/instrument_profile.py:1301`.
- `schemas/common.py`: `_TRANSFORM_ENFORCES`, `Parameter.positive`, and the
  `TransformKind` literal.
- `strategy/staged.bound_untested` (WP-1463): a floor becomes an ordinary
  bound, so the function and its `None` third state go.
- `backend/linalg64.column_agreement`'s 1e-12 skip; `backend/traced.py`'s
  transform application; `gui/textdoc.py`'s `softplus`/`logit` flag words;
  three `help.py` texts; `viz/compare.py` and the `io/projects/` writers
  that build `transform="softplus"` parameters.
- Root CLAUDE.md: the "softplus `min=0.0` … a pole at zero" invariant, the
  WP-1463 "a tiny column is live" clause in the equilibration invariant, and
  the parameter-system line of `docs/DESIGN.md` ("softplus for widths and
  scales (hard lower bounds stall TRF)"), which this WP's measurements answer.

**The stored field.** `Parameter.transform` is in every saved project, `.rxt`
document and history line. Old files must always open (root CLAUDE.md,
breaking by direction). So a stored `"softplus"` reads as "bounded below at
`max(min, 0)`", `"logit"` as `[max(min, 0), min(max, 1)]`, and the field is
either migrated away at the read points (`schemas/migrate.py`) or kept inert.
A pole at zero still needs a real floor (`MARCH_R_MIN`), which is now just a
`min`.

**Every pinned number moves.** Most acceptance fits agree between the two
coordinate systems to 1e-9. LaB₆ + cBN and the joint `lor_size` fixture do
not (the review: χ² 4.2987 against 4.0619 at parameters within one esd, both
a poor basin). VALIDATION.md's rows and the landing page are re-measured.

### Inherited

- **From WP-1936 (2026-10-09): the FD step is one more reader that branches on
  the transform.** `least_squares._fd_typicals` sizes a column's step by
  `FLOOR_SEEDS` only when the row is `identity` *and* its lower bound is at
  least 0, or its unit is deg². A softplus row keeps 1, its θ being
  logarithmic. Under physical coordinates with `lo = max(lo, 0)` every width
  qualifies. A width given a negative lower bound would not, and would go
  back to an absolute step. The bound is how an offset (zero shift, peak
  position, both in degrees) is told from a width.
- **Two baselines that are not minima.** Brucite with the Stephens block under
  softplus + TRF spans χ²_red 7.635871–7.636119 across four FD steps that
  differ by 1e-12, and two of eight runs stop on `max_iter`, under the old step
  and the new. LaB₆ + cBN with `u v w x y` free now reaches 9.793673 under
  softplus and 9.840220 under physical coordinates, each at every step, so the
  two coordinate systems no longer meet on that fit (both met at 9.6614 under
  the old step).

## Non-goals

- The esd rule for a row on its bound, and the floor diagnostic: WP-1929.
- The driver (WP-1937) and the FD step (WP-1936).
- Moment angles at a stationary direction: already identity, so untouched
  here (WP-1929 task 4).

## Tasks

- [ ] The table builds identity entries for every declared transform, with
      the bounds above; `transforms.py` keeps only what migration needs.
- [ ] Read-point migration for a stored `transform`, with a fixture of a
      pre-change project and history opening unchanged in meaning.
- [ ] Every reader in the list above, each fixed or deleted, and the grep that
      finds no `"softplus"` branch left outside migration.
- [ ] Seeds: for each caller of `seed_softplus` and WP-1930's floor seed,
      measure whether it still changes an answer, and delete what does not.
- [ ] The traced backends (`backend/traced.py`) and the cross-backend matrix.
- [ ] Re-measure every acceptance suite and VALIDATION.md's rows; list every
      number that moves by more than 1 % with its reason.
- [ ] Root CLAUDE.md and DESIGN.md clauses rewritten in the same change.
- [ ] Tests, plus obs/calc/diff PNGs to `tests/output/` for the fits whose
      answer moves.
- [ ] Skill: any rule that tells an agent to seed a width before freeing it.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The twelve-fit grid of WP-1929's second session, rerun on the default driver,
reaches one minimum per fit (spread under 1e-9) and one `profile.x` esd on
BT-1.

## References

- WP-1929 (the measurement and the review), WP-1930 (the trap), WP-1463 (the
  tiny-column rule this retires), WP-1102 (the read-point migration pattern).
- TOPAS 5 Technical Reference § 2.4-2.5 (limits inside the solver, physical
  derivatives); ROOT `TMinuit` documentation, parameter limits (why a
  transformed parameter's error is meaningless near its limit).

## Handover log

- **2026-10-09** — created from WP-1929's second session. No open WP owns the
  parameter transforms: 1463 and 1535, which last changed the floor handling,
  are closed; 1930 seeds a floor rather than removing it; 1914 reads a
  coefficient after the fit.
