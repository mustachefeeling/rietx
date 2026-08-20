# WP-1111 — the refinement benchmark harness, and the trigger-shaped case

Milestone: v1.1 · Status: ✅ 2026-08-20 — seven cases, and the opening
baseline: 50 s cold and 4.5–22.4 s warm/pattern on the trigger-shaped case,
against low-single-digit and ~1 s targets
Depends on: — (1109's remaining tasks quote it once it exists, but do not wait on it)

## Goal

One command prints the performance table the v1.1 milestone is judged by —
named cases, wall-clock ranges, evaluation counts, per-stage iterations — and
the table includes the case none of the shipped baselines cover: a cold
4-phase large-cell Cu Kα fit shaped like the session that triggered WP-1109,
plus a warm-started series. Every later speed WP quotes this harness for its
before/after instead of inventing its own measurement.

## Context

- **The warm-start saving was never measured at this width** (from WP-1110's
  real-agent round, 2026-08-20, folded in here on arrival). An unaided agent
  built the 4-phase ZrMo₂O₈ model from the `.inp` and abandoned a warm-started
  `refine_sequential`: pattern 1 converged in ~50 s under the full
  `lab_bragg_brentano` plan, and pattern 2's `refit="single"` collapse ran past
  **150 s without finishing**; the `cell` stage alone cost **22 s** on one
  pattern, and cutting to 2 phases and the 5-stage plan ran in **5.2 s** with
  Rwp *improving* 0.185 → 0.110. Its reading: the collapse trades stage count
  for per-stage Jacobian *width* — one TRF call over ~30 simultaneous free
  parameters — so the per-iteration cost can outweigh the iteration-count
  saving WP-0505 measured at 904 vs 1623 on small-cell standards. Those numbers
  are one agent on one loaded box: a shape to reproduce, never a baseline. What
  this WP takes from it is a **case, not a number** — the series case carries
  *both* `refit` rungs, because "warm start is ≈3× cheaper" is currently quoted
  without the width caveat.
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

- [x] `examples/bench_refinement.py`: cases 1–3 from the acceptance fixtures,
      table printed with venv/platform stamped, `--profile` flag for the
      top-10. *11-BM NAC became **two** cases: 1109's 1.5–1.8 s row is the Le
      Bail leg plus the Rietveld leg together.*
- [x] The trigger-shaped case 4 (ask for real data first; else the simulated
      build, with the simulation parameters recorded in the script docstring)
      and the series case 5. *No real data available, so simulated — literature
      cells, invented coordinates, `sim-` phase names. The series is **two**
      cases, one per `refit` rung, per the folded-in Inherited.*
- [x] Run the full harness idle, best-of-3; record the opening-baseline
      appendix in `docs/milestones/v1.1.md` and cross-link it from the
      milestone Acceptance block. *Seven rows, all with venv + platform.*
- [x] Tests: a fast smoke test that the script imports and its case registry
      builds compiled models (not that it hits any wall-clock number —
      CLAUDE.md: a budget is a runaway guard, never a timer).
      *`tests/test_bench_refinement.py`, 7 tests, 1.6 s.*

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

### 2026-08-20 — the harness, and the number the milestone is behind by

v1.1 now has a "before". One command,
`.venv/bin/python examples/bench_refinement.py`, prints seven named cases with
wall clock as a range, evaluation counts and per-stage iterations, and the
milestone's opening baseline is recorded from it. The headline is a gap rather
than a win, which is what an opening baseline is for: on the case that
motivated the whole milestone — 4 phases, large cells, Cu Kα + FCJ, **1 188
(line, reflection) pairs** on 4 165 points — a cold fit takes **50 s** against
an Acceptance target of low single-digit seconds, and a warm-started series
costs **4.5–22.4 s per pattern** against ~1 s. That is an order of magnitude
on the cold fit and one to two on the series, now measured on the shape that
matters instead of inferred from small-cell standards. Every later speed WP
quotes this table rather than making its own.

*Done.* All four tasks.

- `examples/bench_refinement.py`, seven cases. Three from the acceptance
  fixtures themselves (never restated protocols, so a disagreement can never be
  the protocol), the trigger-shaped simulation, and two series rungs.
  `--cases` selects, `--list` names them, `--profile` adds the cProfile top-10.
- `tests/test_bench_refinement.py` — 7 tests, 1.6 s. It pins **structure and
  never a wall clock**: the registry, the trigger case's peak count, the
  pattern's determinism under its seed, and that the counting scaffold restores
  the name it patched on both exits. It builds only the two cases that cost
  about a second, because building them all is what *running* the harness is.
- The opening-baseline appendix in `milestones/v1.1.md`, cross-linked from that
  file's Acceptance block.

*Measured.* `[dev]`, darwin/arm64, Python 3.12.12, numpy 2.5.2, this
worktree's own venv. Fast selection **2513 passed, 117 skipped** in ~2 min 55 s;
the same selection with `--ignore=tests/test_bench_refinement.py` gives **2506
passed, 117 skipped**, so passed+skipped moved by exactly the 7 tests added,
all 7 passes, no new skip. `ruff check src tests examples` clean. **No
full-suite run**: the branch touches `docs/`, one `examples/` script and one
new test file — nothing under `src/` — so it can move no measured number
(`tests/CLAUDE.md` § Running, rung 3).

*Three findings, all of which change what a later session should quote.*

1. **11-BM NAC is two fits and 1109's row is both.** That WP's opening
   1.5–1.8 s NAC row is the Le Bail leg *plus* the Rietveld leg (0.63–0.67 s
   and 0.64–0.64 s here). Timing only the Rietveld leg against it reads a 2.4×
   discrepancy that is not a speed change and would be credited to whatever
   landed last. They are `nac-lebail` and `nac` now.
2. **The harness reproduces the 2026-08-20 review profile**, which is what
   makes it usable as a "before": `cpd-2` gives **534 nfev / 424 njev** against
   the recorded 534/425 with the per-stage iteration table matching stage for
   stage. The one-call njev difference is the counting path (scipy's
   `OptimizeResult` here, a profile there), not the fit.
3. **The trigger case is dominated by window width, not peak count.** 1 188
   pairs against `cpd-2`'s 308 is 3.9×, but the mean window is 400 points
   against 192, so peak-loop work is ~8× while wall clock is 3.4× and the
   **evaluation count is half** (276 vs 534). Its expensive stage is
   `lines_axial` at 112 iterations where `cpd-2` spends 131 in `cell` and 32 in
   `lines_axial`. An optimisation ranked on `cpd-2`'s profile is ranked on a
   different distribution — which is the whole reason this WP exists.

*The Inherited, and what happened to it.* Folded into Context on arrival (the
entry is now the "warm-start saving was never measured at this width" bullet)
and acted on: the series carries **both** `refit` rungs. **The predicted
pathology did not reproduce.** On this case the default collapse is the
*faster* rung — 4.46–22.38 s per warm pattern against 19.76–26.15 s staged, at
1 238 nfev against 1 549 — even though its single stage frees 61 parameters,
twice the ~30 the agent's model gave it. They differ in *shape*, not speed: the
collapse is fast and spiky (5.0× spread, one escalation to `warm_staged`), the
staged rung uniformly slower and steady (1.3× spread, no escalations). **Why
it did not reproduce is the limitation to carry**: the truth model *is* the fitted
model, so a warm start begins a few hundred ppm out with no model error to
fight, and the pathology needs a collapse that starts wrong. So the row bounds
the claim instead of settling it, and neither rung is generally cheaper until
someone runs real series data. The Inherited's other half — a callable cost
estimate, reflections × free parameters — is a **production** surface and this
WP's non-goals forbid production changes outright, so it is pushed to
[1113](1113-evaluation-count.md)'s `Inherited` rather than dropped.

*Gotchas.* Four, each paid for here.

- **`docs/ROADMAP.md` sits exactly on its 438-line cap**, so the Current-focus
  update had to be compressed to the same line count it replaced. Budget for
  that; it is not free.
- **`tests/output/` is not created by anything** the harness touches, and the
  first baseline run died on the missing directory after `mkdir -p` had been
  assumed. It is gitignored, so it will be missing in a fresh worktree.
- **The simulated case cannot show a model-error pathology**, by construction.
  Anything about *robustness* measured on `trigger`/`trigger-series` is
  measuring a fit that starts nearly right. Only the timing transfers.
- **`nfev`/`njev` come from a monkeypatch**, not an API: the harness wraps the
  module-level `least_squares` name in `optimize/least_squares.py` for the
  duration of a run. That name moving, or a solver routing around it (the
  in-tree LM driver already does), silently turns the counts into `-` rather
  than failing. The package records `nfev` per stage as
  `StageResult.n_iterations` and `njev` nowhere, which is 1113's ground.

*Next.* Nothing here is in flight; the WP is closed and its `Inherited` is
consumed and deleted. [1112](1112-batched-derivative-bases.md) is next in the
series and should judge its FCJ-padding go/no-go on the `trigger` case, whose
400-point mean window is the padding waste it is arguing about. The one thing
this harness still cannot answer is whether the `refit` trade flips under real
model error — that needs a real in-situ series, and asking the maintainer for
one is cheaper than another simulation.

- **2026-08-20** — created by the 1109 review session as the series' first
  WP: the measurement authority the other five quote.
