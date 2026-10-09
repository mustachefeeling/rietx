# WP-1936 — a forward-difference step sized by its parameter

Milestone: unscheduled · Status: 🔄 2026-10-09 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: —
Priority: P1 2026-10-09 — the first rung under WP-1929's P1; on the LaB₆ + cBN fit the step constant alone chooses between two minima 0.27 % apart, and today's identity widths `u`, `v` already carry a 1.4e-3 column error that nothing flags

## Goal

Every forward-difference Jacobian column in `optimize/least_squares.py` is
taken with a step sized to its parameter's own scale. A converged fit's
minimum no longer depends on the step constant: the LaB₆ + cBN fit in physical
coordinates reaches one χ² at steps 1e-6, 1e-7 and 1e-8 of that scale.

## Context

**Where the step is.** Two sites, both `h = 1e-6 · max(1, |θ_c|)` in the
solver's coordinate: `_peak_chain_column` (the per-reflection scalar FD
behind the analytic peak chain) and the `fd_cols` loop in `_make_jacobian`
(the whole-model fallback). In softplus coordinates the step is effectively
relative, because u ≈ ln p for a small p. In identity coordinates it is
*absolute* for every parameter under 1, so a width of 1e-3 deg² is stepped by
a tenth of its size.

**Measured 2026-10-09** (WP-1929's second session and its adversarial review,
macOS arm64, `[dev]`, tree `35f4ac14`, softplus entries made identity with
`lo = max(lo, 0)` by a monkeypatch of `ParameterTable.__init__`):

- On LaB₆ + cBN at the TRF endpoint, `profile.w` (on its floor) has a forward
  column 1.47e-2 off a central difference at h = 1e-6, 1.5e-3 at 1e-7 and
  1.5e-4 at 1e-8: truncation error, linear in h. `profile.v`: 1.4e-3. The
  softplus step gave 1.7e-5.
- The step chooses the basin. Physical coordinates under TRF reach χ²_red
  9.661408 at h = 1e-6, 9.689010 at 1e-7 and 9.686655 at 1e-8. Under the LM
  driver with a BVLS step (WP-1937): 9.687–9.688, then 9.840220 at both
  smaller steps. Each point is a genuine minimum: each driver polishes the
  other's endpoint and stays there. The valley is `RESOLUTION_UNCONSTRAINED`
  (the Gaussian triple clamped), which WP-1930's protocol now holds.
- LaB₆ + cBN's degenerate plan moves the same way (5.450264 at 1e-6, 5.4397
  at 1e-7 and 1e-8). The other nine fits run (BT-1 both histograms, NAC, FAP,
  Si 640c, a capillary fit, the absent phase, brucite, corundum) keep their
  minimum across the three steps to within 2e-6 relative.
- `COLUMN_REL_L2_MAX` in `tests/test_cross_backend.py` is 2e-2, so a 1.5 %
  column passes the agreement matrix with 25 % margin.

**What a scale can come from.** `help.py` carries each family's unit and
typical range. WP-1930's `FLOOR_SEEDS` (`params/vector.py`) sizes a seed per
width unit (1e-3 of a degree, of a degree², and so on). Either gives a
per-parameter scale s, and the step becomes `h = ε · max(s, |p|)`. The
alternative is analytic width columns, which remove the step for the peak
chain altogether. The bar for either is the oracle rule in root CLAUDE.md: a
column is checked where its check is exact (a linear parameter at a 100 %
step; a central difference otherwise).

**Probe toggles used to measure this** (not committed): an env var scaled the
step constant at both sites, and a helper took the step in physical space for
a softplus row and chained it by dp/du. Re-create them from these two lines
rather than looking for them.

### Inherited

(empty)

## Non-goals

- The coordinates themselves: WP-1938. This WP lands first and is correct in
  either coordinate system.
- Which minimum LaB₆ + cBN *should* reach: WP-1930's held protocol decides
  that.

## Tasks

- [x] Choose the scale: `help.py`'s typical range, `FLOOR_SEEDS`' unit table,
      or analytic width columns. Measure each against central differences on
      the LaB₆ + cBN and brucite endpoints, every free column.
      `FLOOR_SEEDS` for an identity row, measured against the jax Jacobian.
      `help.py`'s `typical` is prose with no live authority, and analytic
      width columns were not needed.
- [x] One step function used by both FD sites, with the scale's source in its
      docstring. `least_squares.fd_step` and `_fd_typicals`.
- [x] Tighten `COLUMN_REL_L2_MAX` (or add a per-family bar) so a 1 % column
      error fails `tests/test_cross_backend.py`, and add a config with a width
      on its floor. The fp64 rows' bar is `REL_L2_MAX` = 5e-3, which a 1 %
      column already fails, so no bar moved. The `sharp_widths` config is the
      coverage that was missing; it fails under the old step.
- [x] The step-invariance check: the twelve-fit grid at three step constants,
      in both coordinate systems. No minimum moves by more than 1e-6 relative.
      Holds for every fit whose endpoint is reproducible at one step (2026-10-09
      handover has the table). Brucite with the Stephens block is not: a 1e-12
      change to the step spans 3.3e-5 in χ² under either rule.
- [x] Tests, and every golden that moves listed in the handover with its
      reason.
- [x] Skill: none expected (no new code or verb). None needed.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_acceptance_lab6_cbn.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1929 (the measurement), WP-1930 (`FLOOR_SEEDS`, the held Gaussian
  triple), WP-1121 (an oracle must be exact where its branch is).
- Dennis, J. E. & Schnabel, R. B. (1996). *Numerical Methods for Unconstrained
  Optimization and Nonlinear Equations*, SIAM, § 5.4 (forward-difference step
  sized by a typical value of the variable).

## Handover log

- **2026-10-09** — created from WP-1929's second session. No open WP owns the
  FD step: 1121 and 1112, which last changed these sites, are closed.
