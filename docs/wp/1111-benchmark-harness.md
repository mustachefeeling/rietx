# WP-1111 — the refinement benchmark harness, and the trigger-shaped case

Milestone: v1.1 · Status: ⬜
Depends on: — (1109's remaining tasks quote it once it exists, but do not wait on it)

## Goal

One command prints the performance table the v1.1 milestone is judged by —
named cases, wall-clock ranges, evaluation counts, per-stage iterations — and
the table includes the case none of the shipped baselines cover: a cold
4-phase large-cell Cu Kα fit shaped like the session that triggered WP-1109,
plus a warm-started series. Every later speed WP quotes this harness for its
before/after instead of inventing its own measurement.

## Context

### Inherited

From WP-1110's real-agent round (2026-08-20), a measurement on a
trigger-shaped model that this harness should keep rather than re-derive. An
unaided agent built the 4-phase ZrMo₂O₈ model from the `.inp` and abandoned a
warm-started `refine_sequential`: pattern 1 converged in ~50 s under the full
`lab_bragg_brentano` plan, and pattern 2's `refit="single"` collapse ran past
**150 s without finishing**; on the same model the `cell` stage alone cost
**22 s** on one pattern. Its reading is that the collapse trades stage count
for per-stage Jacobian *width* — one TRF call over ~30 simultaneous free
parameters — so the per-iteration cost can outweigh the iteration-count saving
WP-0505 measured at 904 vs 1623. The same agent cut to 2 phases and the
5-stage plan then ran in **5.2 s** with Rwp *improving* 0.185 → 0.110.

Two things to take from it: the trigger-shaped case in this harness should
carry **both** `refit` settings, because "warm start is ≈3× cheaper" is
currently quoted without the width caveat; and the agent asked for something
this harness is well placed to give — a cheap callable cost estimate
(reflections × free parameters) so a caller can size a model before spending
minutes discovering it is too big. Numbers are one agent on one machine under
a loaded box: treat them as a shape to reproduce, not a baseline.


- **Why a harness, and why this shape.** WP-1109's candidates were ranked on
  three baselines (11-BM NAC, `cpd-1a`, `cpd-2`) with ≤ ~250 (line,
  reflection) pairs each. The trigger session — 68-pattern in-situ series,
  4 phases of ZrMo₂O₈, 4165 points, 41 free, Cu Kα, 105–600 s/pattern — has
  roughly an order of magnitude more peaks, and peak-loop cost scales with
  peak count × window width. A ranking measured only on small-cell standards
  under-weights exactly the term the trigger case is dominated by. The 2026-08-20
  review (1109's Context) is the source for all numbers restated here.
- **Precedent for the script shape**: `examples/bench_solver.py`,
  `examples/bench_torch_mps.py`, `examples/bench_batched_peak_loop.py` — all
  standalone `.venv/bin/python examples/…` scripts that print tables; there
  is deliberately no pytest-benchmark dependency. Follow that shape:
  `examples/bench_refinement.py`.
- **Measurement rules that bind every number** (CLAUDE.md § Commands +
  1109's gotchas): wall clock is a range, best-of-3 on an idle machine (a
  concurrent `-n auto` suite inflated a 1.24 s fit to 4.78 s — 3.9×); quote
  venv and platform; never compare across machines or against a remembered
  figure.
- **Cases.** Reuse the acceptance fixtures rather than restating protocols
  (`tests/test_acceptance_qpa_roundrobin.py` builds phases/instrument/plan;
  import from `tests/` the way this repo's benches import compiled states):
  1. 11-BM NAC (synchrotron, no FCJ, 22 003 pts) — the dispatch-light case.
  2. `cpd-1a` (lab FCJ, 3 phases) — the FCJ-heavy small case.
  3. `cpd-2` under the 9-stage QPA acceptance protocol (texture) — the
     measured 17.5–17.8 s / 534+425-evaluation reference of 1109's review.
  4. **Trigger-shaped (new)**: 4 phases, large cells, Cu Kα doublet + FCJ,
     ~4165 points, ~1000+ (line, reflection) pairs, ~40 free. Prefer the
     real ZrMo₂O₈ session's data if the maintainer can supply a pattern and
     the four phase CIFs (ask — memory says papers/data arrive on request);
     otherwise simulate: build the phases from literature cells, evaluate a
     converged-looking model on a 2θ grid, add Poisson noise, and fit the
     standard QPA-style plan cold. For a *performance* benchmark the truth
     of the fractions is irrelevant; what must be realistic is peak count,
     overlap and window structure.
  5. **Series**: N ≈ 10 warm-started copies of case 4 with a small simulated
     ramp (cell drift ~100 ppm/step), through `refine_sequential` — the
     workflow the milestone's ~1 s/pattern target names. `direction="both"`
     off (this is a timing case, not a science case).
- **Columns per case**: wall range (best-of-3), nfev/njev totals, per-stage
  `n_iterations`, Rwp (as an identity check between runs, never as the
  metric), and — behind a flag — the cProfile top-10 by tottime. The series
  case reports per-pattern wall for cold vs warm.
- The first full run on this machine is the milestone's **opening baseline**:
  record it as a dated appendix in `docs/milestones/v1.1.md` and quote it in
  the milestone's Acceptance section as the "before".

## Non-goals

No production-code changes at all (a harness that lands with an optimisation
in the same WP can no longer measure it); no CI wiring (the numbers are
machine-relative — the nightly quotes counts, not wall clock); no GPU/backend
axes (`bench_torch_mps.py` owns that story).

## Tasks

- [ ] `examples/bench_refinement.py`: cases 1–3 from the acceptance fixtures,
      table printed with venv/platform stamped, `--profile` flag for the
      top-10.
- [ ] The trigger-shaped case 4 (ask for real data first; else the simulated
      build, with the simulation parameters recorded in the script docstring)
      and the series case 5.
- [ ] Run the full harness idle, best-of-3; record the opening-baseline
      appendix in `docs/milestones/v1.1.md` and cross-link it from the
      milestone Acceptance block.
- [ ] Tests: a fast smoke test that the script imports and its case registry
      builds compiled models (not that it hits any wall-clock number —
      CLAUDE.md: a budget is a runaway guard, never a timer).

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py            # prints the table
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The opening-baseline appendix exists in `milestones/v1.1.md` with every
number carrying venv + platform, and case 4's peak count is within the
trigger's order of magnitude (~1000+ (line, reflection) pairs).

## References

- WP-1109's Context — the 2026-08-20 review profile this harness makes
  repeatable.
- The trigger session log (maintainer-local; the summary numbers are in
  1109's Context).

## Handover log

- **2026-08-20** — created by the 1109 review session as the series' first
  WP: the measurement authority the other five quote.
