# WP-1329 — the moment in a series: the onset, the hold, the trajectory

Milestone: v1.6 · Status: ⬜
Depends on: 1327 (the moment); 1326 soft (the satellite arm per pattern)

## Goal

A temperature series through a magnetic ordering transition refines the
moment on every pattern below the onset, holds it at its floor above, and
reports |m| against temperature as a measured trajectory with esds, with the
onset located by the data rather than declared. The k = 0 ambiguity 1326
names on one pattern is resolved the only way a powder can resolve it: by
the pattern of the same specimen above the transition.

## Context

Fourth rung of the magnetic scattering track (ROADMAP § Unscheduled). The
package's strength is the in-situ series (`sequential.py`, WP-1051, 1127,
1305), and an ordering transition is the series a neutron user runs: the
same specimen through T_N, the moment growing from zero.

**The hold is already the rule; the series is where it earns its keep.**
1327 holds a moment block at its floor when the data does not support it
(WP-1301's shape: a flat direction is held for the stage, never bounded, and
re-measured at the answer). Chained by warm start across 68 patterns, that
rule decides on every pattern whether the moment is *released* (the block
lifts off its floor) or *held*, exactly as 1301 decides whether a phase has
appeared. The onset is then the first pattern, in each direction of the
chain, where the block is released; `direction="both"` flags the two
disagreeing (`SEQUENTIAL_PATH_DEPENDENT`), and `SEQUENTIAL_PERSISTENT_FINDING`
says "held on 42 of 68" for what no per-pattern finding can say.

**What the trajectory is.** |m|(T) is the order parameter, and its esd on
each pattern is conditional on that pattern's fit; the series prints the
trajectory (WP-1305's fourth deliverable) with the held patterns marked as
held, not as zero with an esd. A critical-exponent fit m ∝ (1 − T/T_N)^β is
nonlinear in its coefficients and stays fenced with `Parameter.expr`
(WP-1119, WP-1325); the trajectory is the deliverable, and a user fits the
exponent to it.

**The satellites per pattern** (1326's arm) give the onset a second reading
for k ≠ 0: the pattern where the satellites first carry extracted intensity.
Two readings that disagree are reported as a disagreement, not averaged.

**Cost.** A magnetic supercell (1327) multiplies the atom and reflection
count on every pattern of the chain; the ratio against the nuclear-only
chain on the same data is reported as a range, never gated.

### Inherited

- **2026-09-17, from [1436](1436-k-is-the-wavevector-everywhere-else.md):
  `k` is free for the propagation vector.** The earlier note here warned that
  `scattering.py`, `structure_factor.py` and `dispersion.py` all spent `k` on
  sinθ/λ, in the same subpackage `crystallography/magnetic/` lives in, and
  asked this WP to spell the propagation vector out rather than add a second
  bare `k`. 1436 has landed: that quantity is `stol` in python and `s` in
  equations throughout, following Waasmaier & Kirfel and the IUCr core
  dictionary, and a tree-wide sweep found no line left pairing a bare `k` with
  sinθ/λ in `src/`, `tests/`, `examples/` or the manual. **So name the
  propagation vector `k` and add no qualifier.** Root CLAUDE.md § Conventions
  carries the rule that keeps it free. The same note is in 1326, 1327, 1328 and 1418.

## Non-goals

- A joint fit over the series with one θ (`multi.py`), or the parametric
  form of m(T): WP-1325's question, measured there.
- Locating T_N by any means other than the hold and the satellites.
- Anything the single-pattern rungs own.

## Tasks

- [ ] The series drives 1327's hold per pattern: released/held recorded in
      each entry, the onset in each direction of the chain, the
      path-dependence flag when they disagree.
- [ ] The trajectory: |m|(T) with esds, held patterns marked as held, printed
      by 1305's series view; the satellite reading beside it for k ≠ 0.
- [ ] Manual Part 1 (`using/series.md`), skill row, the diagnostic's
      protocol row.
- [ ] Tests on a synthetic ramp built from 1327's model (moment following a
      declared m(T), noise from the pattern's own σ): the onset lands within
      one pattern of the declared T_N in both directions; obs/calc/diff PNGs
      and the trajectory plot to `tests/output/`.
- [ ] A real ramp, if one is public: search the corpus, then ask.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_magnetic_series.py -q
.venv/bin/python -m ruff check src tests examples
```

- On the synthetic ramp, every pattern above the declared T_N reports the
  block held; every pattern below reports it released; the onset agrees
  between directions within one pattern.
- The trajectory's held entries carry no esd; the released entries' esds
  come from each pattern's covariance.
- The Cr₂WO₆ pair (4 K released, 150 K held) as a two-pattern series gives
  the same answers as 1327's single-pattern fits, bit-identical.

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* **40**, 87 —
  parametric Rietveld, the form this WP does not take (WP-1325 measures it).
- [1327](1327-magnetic-structure.md) the moment and its hold;
  [1326](1326-satellites-without-a-moment.md) the satellite arm;
  [1301](1301-hold-unsupported-phase.md) the hold rule;
  [1305](1305-series-deliverable.md) the series view;
  [1325](1325-parametric-series.md) the parametric question.

## Handover log

- **2026-09-02** — created, from the assessment of PR #221, which did not
  reach the series. Added because the ordering transition is the neutron
  series a user runs, and the hold rule the moment needs on one pattern is
  the onset detector on many. No code touched. First task is the per-pattern
  hold record.
