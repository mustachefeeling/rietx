# WP-1456 — one flat direction, one finding

Milestone: unscheduled · Status: ⬜
Depends on: — (1455 soft: both touch the P-spline)
Priority: P3 2026-09-24 — every row is true; at fine knots the list runs to a thousand rows and buries the few that matter

## Goal

A degeneracy among n parameters arrives as one finding naming its members.
Today it arrives as n(n−1)/2 pair rows plus as many flat-direction rows. The
air-scatter term stays off when `auto_background` left it off.

## Context

**Where the rows come from.** `check_guards` loops over every pair of free
parameters (`src/rietx/strategy/staged.py:1544-1561`). Each pair above
`correlation_guard` (0.98) appends a `HIGH_CORRELATION` finding. Each pair
at or above `FLAT_DIRECTION_RHO` (1 − 5·10⁻⁴) also appends a
`FLAT_DIRECTION` finding. One rank-deficient direction across n columns can
therefore produce n(n−1) rows.

**Measured 2026-09-24 on a public pattern.** The pattern is 11-BM NAC,
started from `examples/nac_11bm.py`'s converged model. The background was
`BackgroundPSpline.for_range(1.9, 24.1, …)`, seeded at the 5th percentile,
and the fit used the default Rietveld plan over 2-24°.

| knots | λ | coefficients | rows | background-only rows | Rwp |
|---|---|---|---|---|---|
| 8° | 1 | 6 | 2 | 1 | 0.09366 |
| 2° | 10⁻⁴ | 14 | 1 | 0 | 0.08628 |
| 0.75° | 10⁻⁴ | 33 | 1075 | 1074 | 0.08484 |

At 0.75° the 1074 rows are 561 `HIGH_CORRELATION` and 513 `FLAT_DIRECTION`.
561 is every pair among the 34 background parameters. The same fit with
`ref.hold("instrument.background.air")` gives **zero** correlation rows, at
Rwp 0.08484 both ways. So the whole flood is one direction: the 1/(2θ) air-scatter
column lies inside the span of a fine spline.

**Why the air term is free.** Its default is off: `Parameter(value=0.0,
min=0.0, transform="softplus")`, with `vary` False
(`src/rietx/schemas/instrument.py:1078`). `auto_background` turns it on only
when `diag.air_scatter_gain > AIR_SCATTER_TRIGGER`
(`src/rietx/background/auto.py`). But every preset plan frees
`instrument.background.*` (`staged.py:284-431`), and that glob includes
`.air`. A plan replaces the vary flags (WP-1208), so `auto_background`'s
decision is overridden on every fit. This is issue #211's shape, which
WP-1435 fixed for a caller's own holds.

**Private evidence.** The session WP-1453 describes hit the same wall. On
one fit, 1643 of 1644 rows were about background coefficients alone, and the
agent's first fit printed 8 kB of them. The agent then dropped every
background-only row. An info finding, `CAPILLARY_OFFSET_UNAVAILABLE`, asked
for a goniometer radius on every fit that followed. The instrument file
stated one, and the agent never set it.

**The skill.** `references/judging.md` and `references/batch.md` quote
`worst_absorption` only as 0.46 against 0.08. The guard is
`BACKGROUND_ABSORPTION_GUARD = 0.25` (`staged.py:878`), and no skill file
names it.

**What reads these rows.** Audit every reader before changing the shape. The
lesson is WP-1103's: seven counts and builders were right only while one
case existed. Readers include `GuardReport.high_correlations` and
`.flat_directions`, the `Diagnostic` list, `SEQUENTIAL_PERSISTENT_FINDING`'s
counts, the report's identifiability layer (WP-1056,
`measured_top_correlations`) and the GUI's panels.

## Non-goals

- Changing `correlation_guard` or `FLAT_DIRECTION_RHO`.
- Suppressing background rows by name. A background degeneracy with a
  structural column is the finding that matters most (root CLAUDE.md
  § background flexibility).

## Tasks

- [ ] Audit the readers listed above, and write down what each one counts.
- [ ] Group the findings. The candidates are connected components of the
      thresholded pairs, or the flat eigen-directions of the Jacobi-scaled
      normal matrix (`optimize.statistics.normal_covariance`). Emit one
      finding per group that names its members. A group of two stays a pair
      row, byte for byte (`str(finding)` is pinned).
- [ ] Decide the air term, and write the decision here. The candidates:
      presets free `instrument.background.c*` plus the air term only where
      the model turned it on; or `auto_background`'s declined term is held
      the way a caller's hold is. The second needs a seam, because a model
      carries no holds.
- [ ] Tests, in a new `tests/test_flat_direction_groups.py`: NAC at 0.75°
      knots gives one finding naming the air term, and no pair rows.
- [ ] Skill: a `references/diagnostics.md` row for the grouped finding, and
      the 0.25 threshold beside the 0.46 example.

## Acceptance

NAC at 0.75° knots reports the degeneracy as one finding. Every other fit in
the fast selection reports the same rows as before.

```sh
.venv/bin/python -m pytest tests/test_flat_direction_groups.py tests/test_covariance_scaling.py -q   # the first is this WP's new file
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1056 (identifiability), WP-1103 (reader audit), WP-1208 and WP-1435
  (a plan replaces vary flags; a hold outranks a glob), issue #211.

## Handover log

- **2026-09-24** — created from the review of an agent session on a private
  series. Measured the same day on public NAC, including the zero-row
  result with the air term held (the table above), at `2d42303a`. Next: the
  reader audit.
