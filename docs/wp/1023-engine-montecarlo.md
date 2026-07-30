# WP-1023 — Engine C: whole-profile Monte Carlo (spike, then decide)

Milestone: v1.0 · Status: ⬜ not started
Depends on: 1020

## Goal

A third engine that scores trial cells against **the profile** rather than an
extracted line list, so that impurity peaks cost fit quality instead of
forbidding a cell outright. **Task 0 is a measured spike: a no-go is an
acceptable outcome and must be recorded as one** (WP-0605 precedent).

## Context

*Sources*: Le Bail (2004) — McMaille; Kariuki *et al.* (1999) and Harris *et
al.* (2000) — GAIN; Coelho (2003) for the Monte-Carlo/SVD framing. **Papers
only — no McMaille, GAIN or TOPAS code.**

- **Why a third engine at all, stated precisely.** WP-1021 and WP-1022 both
  work on extracted positions, so a single wrong line can prune or poison the
  true answer; they mitigate it differently but they share the *kind* of
  failure. A profile-based score does not: an unindexed impurity peak leaves
  residual and costs Rwp, but does not forbid the cell. Le Bail (2004) reports
  tolerance up to ~10-15 % of total intensity in impurity lines. **That
  independence is the entire reason this engine is in the confidence gate** —
  put it in the module docstring, because it is also the thing the fallback
  below would destroy.
- **The scorer already exists and needs no least squares.**
  `compile_model(structure, instrument, pattern, mode="lebail", …)` then
  `CompiledModel.lebail_update(values, n_cycles=3)` — a fixed-point intensity
  partition, `model/forward.py:871` — then `evaluate` and
  `optimize.statistics.compute_statistics` gives Rwp. No `run_least_squares`
  call in the inner loop.
- **But `compile_model` per trial is far too slow for 10⁵ trials**, which is
  what makes this a spike rather than a build. The proposed structure is a
  **two-tier scorer**:
  - *tier 1* (bulk, ~10⁵-10⁶ trials): a profile-free Q-space score on the peak
    list alone — intensity-weighted indexed fraction minus a `Σ|ΔQ|/σ` penalty.
    No `compile_model`. Metropolis on A..F with a geometric temperature
    schedule, local moves scaled to `σ_eff`, restarts from the WP-1019 volume
    envelope.
  - *tier 2* (top ~200 states): the real Le Bail Rwp over the whole profile.
    This is where impurity tolerance actually comes from.
- **The fallback that must NOT be taken silently.** If the spike shows tier 1
  cannot rank usefully, the tempting fix is to run this engine only on the
  candidates WP-1021/1022 produced. **That destroys its independence and
  therefore the consensus argument in WP-1024.** If it comes to that, engine C
  must be **dropped from the confidence gate** and reported as a re-scorer, not
  quietly demoted while still counting toward `found_by`.
- **Determinism is mandatory.** `seed: int`, `np.random.default_rng(seed)`,
  and the seed recorded in `Provenance`. A stochastic engine in a package whose
  tests pin numbers is only admissible if its seed is provenance.
- **Bounds and a reflection ceiling are not optional.** Measured (tag
  `guillemot-study`, `audit_tools.py` check B — see References): an
  unbounded cell on a 1.7 wt% phase started 3 % wrong ran away and *"the
  reflection generator asked for 1.6 PiB"*. This engine proposes random cells,
  so it is the most exposed code in the milestone: bound every proposal and
  check the predicted reflection count **before** calling
  `generate_reflections`.
- `Phase` requires a non-empty `atoms` list (`Phase._nonempty` raises), so a
  trial structure carries a dummy atom; it contributes nothing because
  `Refinement._run_stage` force-fixes every `.atoms.` path, `.scale` and
  `.source.lines.` in lebail mode (`refine.py:369-380`). WP-1024 owns the
  shared `structure_from_candidate` helper; until it lands, build trial
  structures locally and hand the helper over.
- If a full Le Bail refine is used at tier 2, pass **`history=False`
  explicitly**: `refine()` defaults it off but `Refinement()` defaults it *on*,
  and 200 trials must not build 200 trees.

### Inherited

From **WP-1020**: A..F parameterisation and the symmetry subspace (moves are in
the subspace, so a cubic sweep is 1-D), `refine_candidate`, the FoM panel,
χ² cell-equality for dedup.

From **WP-1019**: the volume envelope for restarts, `σ_eff` for move scaling.

From **WP-1020** (landed 2026-07-30) — the shared surface, and five things about
it that are not obvious from the names:

- **`refine_candidate(q, q_esd, hkl, *, system=...)` without a shift template is
  one `lstsq` on an (N, m) system** — no iteration, no scipy call, because it is
  this engine's inner loop. With `shift_template=` it becomes Gauss-Newton (≤ 8
  steps). **Do not put a shift column inside the search loop**: fit the shift
  after a candidate survives, which is also the order WP-1019's screen needs
  (it is conditional on reference positions, and a candidate is what supplies
  them).
- **`metric_basis(system)` is the search space.** Its row count is the box
  dimension — 1 cubic … 6 triclinic — and it is derived from the operators, so it
  is right in any setting. Import it; do not hardcode 1/2/2/2/3/4/6. It takes the
  rotations **untransposed**, and getting that wrong is invisible in the dimension
  (see 1020's handover: the transposed call returns the *direct* metric's
  invariants, same dimension in every system, wrong subspace for hexagonal and
  trigonal).
- **`cell_from_af` raises on a non-positive-definite metric** rather than
  returning NaNs. A search that steps outside the cone will hit this, so catch
  `ValueError` at the point where a trial metric is turned into a cell rather than
  letting it abort a sweep.
- **`reduce.same_lattice(af_a, af_b, cov_a=…, cov_b=…)` is the dedup**, returning
  `(verdict, χ²)`; it Niggli-reduces both first, so a setting change is *equality*
  and never an ambiguity. Feed it `CandidateFit.cov_af`, which is already the
  delta-method covariance; the relative fallback (χ² = NaN) means one of the
  covariances was missing.
- **`fom_panel(...)` returns the whole panel and `borda_scores` ranks it.** Rank on
  the panel, never on a member: `indexed_fraction` alone prefers a large cell, and
  1020's test reproduces that failure on synthetic data (an impostor ties or beats
  the truth on the forward direction and loses 5× on `predicted_seen_fraction`).
  Two figures' means are **floored at the measured precision** — a candidate that
  fits within fp noise would otherwise score 0 or ∞.

## Non-goals

- No genetic algorithm — the GAIN lineage is cited for the whole-profile idea,
  not implemented.
- No consensus or confidence gate (WP-1024).
- Triclinic is budgeted like every other engine, not claimed complete.

## Tasks

- [ ] **Task 0 — the spike.** Measure, on synthetic patterns of known cells and
      on one real lab pattern: tier-1 throughput (trials/s), whether tier-1
      rank correlates with tier-2 Rwp well enough that the true cell reaches
      the top 200, and tier-2 cost per state. Write the numbers into this
      WP's handover log **and decide**: build, or no-go with engine C dropped
      from the confidence gate. Do not proceed to the tasks below before this
      is recorded.
- [ ] `indexing/montecarlo.py`: seeded RNG, A..F moves in the symmetry
      subspace, Metropolis with a geometric schedule, restarts.
- [ ] Tier-1 scorer; bounds + predicted-reflection ceiling.
- [ ] Tier-2 Le Bail scorer over `compile_model` + `lebail_update`
      (`history=False` on any full refine).
- [ ] Registry entry; time budget; `search_complete`; seed into `Provenance`.
- [ ] `tests/test_indexing_engines.py::montecarlo`: recover known cells;
      **the impurity test that justifies the engine** — a peak list with
      impurity lines left in, on which WP-1021/1022 need their mitigations and
      this engine does not; **determinism** (same seed ⇒ bit-identical reduced
      cells); the reflection ceiling triggers instead of allocating.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py -k montecarlo -q
.venv/bin/python -m ruff check src tests examples
```

Criterion: **the spike's numbers are in the handover log and a build/no-go
decision is recorded**, whichever way it went. If build: known cells recovered
from synthetic lists, the impurity test passes, and the engine is deterministic
under a fixed seed. If no-go: WP-1024's confidence gate is updated to a
two-engine consensus in the same change, and the reasons are recorded here and
in `docs/milestones/`.

## References

- Le Bail, A. (2004). *Powder Diffr.* **19**, 249-254 — McMaille; the
  10-15 % impurity-intensity tolerance figure.
- Kariuki, B. M. *et al.* (1999). *J. Synchrotron Rad.* **6**, 87-92;
  Harris, K. D. M. *et al.* (2000) — GAIN.
- Coelho, A. A. (2003). *J. Appl. Cryst.* **36**, 86-95 — SVD-Index.
- Altomare *et al.* (2019), IT Vol. H ch. 3.4 §3.4.3.2.2.
- `docs/wp/0605-batched-peak-loop.md` — the spike-then-decide precedent, and
  what a recorded no-go looks like.
- Prior art at the tag `guillemot-study` (**not merged into `main`**; §B's
  finding is restated in Context, so this is corroboration):

  ```sh
  git show guillemot-study:studies/guillemot/out/audit_full.txt   # §B
  ```

## Handover log

- **2026-07-29** — created from the indexing plan. Structured deliberately as
  spike-first: the cost of `compile_model` per trial is the open question the
  whole engine rests on, and WP-0605 established that measuring it before
  building is the house response.
