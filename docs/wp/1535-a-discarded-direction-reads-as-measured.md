# WP-1535 — A direction the covariance discards reads as measured

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-02 — a confident esd on an exactly degenerate pair, with only `FLAT_DIRECTION` beside it; WP-1534 holds the one shape it measured, and this WP measures how many others there are

## Goal

When two or more live columns are exactly degenerate, the parameters that
direction touches report no esd rather than a small one. This is WP-1110
item 14's rule, extended from a single column to a combination of columns.

## Context

**What WP-1534 measured (2026-10-02).** The equilibrated normal matrix goes
to `pinv` with `PINV_RCOND` (1e-15, `optimize/statistics.py`). An eigenvalue
under the cut is *discarded*, so its direction comes back with **zero**
variance. Each parameter's esd then shows only its projection onto the
directions the data did measure. On a 25–50° Cu Kα mixture, bcc Fe's scale
and B columns were collinear to rounding (1 − |cos| = 2.2e-16). Their
direction's eigenvalue was −3.8e-18 against a cut of 2.9e-15. Fe's scale came
back "measured to 2.7 %", and its fraction read 0.000 ± 0.000 wt% at
B = −150 Å². `_cov_free` and `ParameterTable.unmeasured_rows` catch a column
with **no** gradient. Nothing catches a combination with none. WP-1534 holds
the scale–B shape before the solve (`SCALE_B_INSEPARABLE`), which removes the
direction from that pair, but every other exactly degenerate pair is
untouched.

**Candidate shapes (hypothesis, unmeasured).**

- A one-site phase's occupancy against its scale. |F|² ∝ occ², so on any
  range the occupancy is exactly a reparameterisation of the scale.
- A phase's displacement against its scale on an all-anisotropic phase, which
  WP-1534's probe skips because it has no isotropic site to step.
- Any user tie or `vars.X` that makes two free columns identical.

**Why this is not a one-line fix.** Marking every parameter that a discarded
eigenvector touches would change the esds of every fit that has such a
direction. The moment probe's docstring (`refine.MOMENT_DIRECTION_SUPPORT`)
records the same reluctance about widening `_cov_free`. So measure first: how
many fits in the acceptance suites have a cut direction at all, and which
parameters it touches.

**Machinery.** `statistics.normal_factors` (the cut), `covariance_from_factors`
(where `inf` is written for a dead column), `ParameterTable.unmeasured_rows`
and the "consumers mark, never clamp" rule (root CLAUDE.md, WP-1110 item 14),
and WP-1460 (how a flat direction is *reported*; this WP is about its *esd*).

## Non-goals

- Reporting the pair once. That is WP-1460.
- Holding anything. WP-1534 holds the scale–B shape; a hold for another
  shape is a WP of its own once this one has measured it.

## Tasks

- [ ] **Measure first.** Count discarded eigen-directions (eigenvalue under
      `PINV_RCOND × λmax`) across the fast suite's fits and the acceptance
      fixtures, and record which parameters each one touches. Build the
      one-site occupancy–scale case and confirm or refute the hypothesis.
- [ ] Decide from the count: mark the touched parameters unmeasured in the
      covariance, or add a finding naming the direction and leave the esds.
      Write down the threshold for "touches" (a loading on the discarded
      eigenvector), derived, not tuned.
- [ ] Tests, and the record line or diagnostic that states what changed.
- [ ] Manual Part 2: the equilibrated cut in `estimation.md`, beside
      WP-1534's ridge section.
- [ ] Skill: the row for whatever the decision adds.

## Acceptance

No exactly degenerate pair on the fixtures returns a finite esd for a
parameter its discarded direction touches, or a finding says which esds are
conditional.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1534 (the measurement), WP-1110 item 14 (equilibration), WP-1463
  (column rescale), WP-1460 (reporting a degeneracy once).
- van der Sluis, A. (1969). Numer. Math. 14, 14–23.

## Handover log

- **2026-10-02** — filed from WP-1534's handover. No open WP owns the esd of
  a discarded *combination*: 0407 and 1056 are closed, and 1460 reports pairs
  without touching their esds. Next: task 1's count, because it decides
  whether this is a covariance change or a finding.
