# WP-1023 — Engine C: whole-profile Monte Carlo (spike, then decide)

Milestone: v1.0 · Status: 🛑 **no-go, recorded 2026-07-30** (Task 0 complete; engine not built)
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

From **WP-1021** (landed 2026-07-30) — **the shared engine surface exists; build
on it rather than beside it.** `indexing/engines.py` holds everything the three
engines have in common, and six things about it are not obvious from the names:

- **`SearchSpec` is the one option object** (systems, centrings, `min_d_axis` /
  `max_d_axis`, `min_volume` / `max_volume`, `n_unindexed`, `n_search_lines`,
  `k_sigma`, `budget_seconds`, `max_candidates`, `seed`). The three engines must
  mean the *same* thing by `max_volume` and `n_unindexed` or their agreement is not
  evidence of anything, so take a `SearchSpec` and do not add per-engine keywords
  for anything it already carries. `spec.centrings_for(system)` and
  `spec.volume_limit(system, fallback)` are the accessors.
- **Return an `EngineResult`, and fill `search_complete` per system.** It carries
  `candidates: list[EngineCandidate]`, `systems_searched`, `search_complete`,
  `stats` and `diagnostics`. `EngineCandidate` holds the `CandidateFit` itself
  (not just the cell) because WP-1024's dedup is a χ² test needing `cov_af`, plus
  the hkl assignment and the `line_index` it was fitted on. **`search_complete` is
  the half that makes a negative result mean anything** — use
  `engines.incomplete_diagnostic` for `INDEX_SEARCH_INCOMPLETE`.
- **`engines.rank_candidates(cands, peaks, n_unindexed=…)` is how a ranked list is
  produced** — dedup, then the FoM panel, then Borda over the whole panel. Do not
  sort on `n_indexed` or χ²: on synthetic data supercells index every observed line
  *exactly* and tie the truth on every forward-looking figure, losing only on
  `predicted_seen_fraction`. Pass `spec.n_unindexed` through: the figures' mean
  discrepancy is trimmed by the same count the search was allowed to leave
  unindexed, and getting that wrong ranks an impurity-covering supercell first
  (measured: M₂₀ 13.2 for the truth against 62.5 for an a√5 supercell).
- **`engines.reflection_ceiling_ok(cell, λ, 2θ_max)` before every
  `generate_reflections`** — the measured 1.6 PiB guard. It is arithmetic on the
  cell, so it costs nothing and never touches memory.
- **`engines.trial_hkl(max_index, centring)`** (re-exported from `qspace`) is the
  centring-filtered, Friedel-halved trial set, and
  **`engines.assign_lines(q, σ, hkl, af, design=…)`** gives each line its nearest
  hkl within k·σ. Pass `design=design_matrix(hkl)` if you call it in a loop —
  rebuilding the (N, 6) matrix per candidate was 90 % of one search's runtime.
- **`engines.Budget(seconds, cancel)`** wraps the deadline *and* WP-1006's
  `CancelToken`; `budget.expired()` is cheap enough to call per unit of work, and a
  cancelled search returns what it has rather than raising.

**Also from WP-1021: `metric_basis` is memoised and its arrays are read-only.**
It re-derived the exact rational nullspace once per accepted box before that (2.5 s
of a 15 s run). Do not mutate what it returns.

**And the sharper lesson, if you are about to reach for a tolerance:** stopping
rules and measurement tolerances are different numbers. WP-1021 conflated them and
the 4-D search stopped terminating — zero leaves reached in 445 000 boxes. Its
exhaustiveness comes from the pruning, which is exact however coarse the leaves
are; the tolerance belongs in the *scoring*, not in the stopping rule.

**Specific to this WP (WP-1021, 2026-07-30): two numbers for your spike.**
`predicted_lines` is now a vectorised enumeration rather than an orbit
canonicalisation — 1.8 ms for a 17 Å cubic cell against 683 ms — so a *tier-1*
Q-space score over a trial cell is cheap in a way the plan assumed it would not be;
budget your throughput measurement against the new number, not the old one. And
`engines.rank_candidates` already does dedup → panel → Borda, so the spike only has
to answer whether tier-1 *ordering* puts the truth in the top ~200; it does not
need its own scoring stack.

## Non-goals

- No genetic algorithm — the GAIN lineage is cited for the whole-profile idea,
  not implemented.
- No consensus or confidence gate (WP-1024).
- Triclinic is budgeted like every other engine, not claimed complete.

## Tasks

- [x] **Task 0 — the spike.** Done 2026-07-30; numbers and the decision are in the
      handover log. **Outcome: no-go.** The tasks below are therefore *not* done and
      are not to be started without new evidence.
- [ ] ~~**Task 0 — the spike.**~~ Measure, on synthetic patterns of known cells and
      on one real lab pattern: tier-1 throughput (trials/s), whether tier-1
      rank correlates with tier-2 Rwp well enough that the true cell reaches
      the top 200, and tier-2 cost per state. Write the numbers into this
      WP's handover log **and decide**: build, or no-go with engine C dropped
      from the confidence gate. Do not proceed to the tasks below before this
      is recorded.
- [ ] ~~`indexing/montecarlo.py`: seeded RNG, A..F moves in the symmetry
      subspace, Metropolis with a geometric schedule, restarts.~~ **not built**
- [ ] ~~Tier-1 scorer; bounds + predicted-reflection ceiling.~~ **not built**
- [ ] ~~Tier-2 Le Bail scorer over `compile_model` + `lebail_update`.~~ **not
      built** — though it was measured and it works (13-15 ms/state, and it
      discriminates); see the handover log, because a *re-scorer* built on it is
      the one thing this no-go leaves on the table.
- [ ] ~~Registry entry; time budget; `search_complete`; seed into `Provenance`.~~
- [ ] ~~`tests/test_indexing_engines.py::montecarlo`.~~

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
- **2026-07-30** — **Task 0 complete. Decision: NO-GO.** Engine C is not built and
  is **dropped from the confidence gate**; WP-1024's gate becomes a two-engine
  consensus (its `### Inherited` says so). The spike script measured on the bundled
  qarr corundum pattern (Cu Kα, certified cell 4.7593 / 12.9917 Å, R-3c) plus a
  32-line fitted peak list from `pick_peaks`.

  **The three numbers the WP asked for.**

  | quantity | measured |
  |---|---|
  | tier-1 throughput | **~25 000 trials/s** (single thread, 32 lines, index ≤ 12 trial set) |
  | tier-1 rank of the true cell | **29 053 of 200 001** — *not* in the top 200 |
  | tier-2 cost per state | **13-15 ms** (10-12 ms `compile_model` + 3 ms `lebail_update` + `evaluate`) |

  Tier 2 is affordable (200 states ≈ 3 s) and it *discriminates*: Rwp 1.29 for the
  certified cell against 7.25 for one 1 % off. **The engine fails on tier 1, and
  the failure is not a tuning problem.**

  **What tier-1 actually does, measured.** With the peak list's own fitted σ
  (median 0.0056° 2θ) the true cell scores **exactly 0.0000** and ranks 29 053rd,
  while random large cells score up to 0.33. The cause is not the score's shape but
  the data: the pattern's lines sit a median **0.060°** from the certified cell's
  positions — a cos θ specimen displacement of −0.065°, an **11σ** systematic — so at
  3σ the true cell indexes *no lines at all*. Opening the window walks into the
  opposite failure:

  | σ_sys added | truth's score / rank | best random cell |
  |---|---|---|
  | 0.00° | 0.0000 / 29 053 | 0.329 |
  | 0.01° | 0.0094 / 36 007 | 0.530 |
  | 0.02° | 0.5098 / **13** | 0.710 |
  | 0.05° | 0.8960 / **4** | 0.969 |

  So tier-1's discriminating power is **bracketed**: too tight and the truth scores
  zero; too loose and coincidence-rich large cells outrank it — the same failure the
  FoM panel exists to prevent, except now inside the *proposal* mechanism where no
  panel can see it. There is a usable window near 0.02°, and its width depends on a
  quantity indexing does not know (the shift). A Metropolis walk needs a landscape
  whose maxima are near the answer; measured, the answer is a **zero** in a landscape
  whose maxima are large cells.

  **The bracket is the whole argument, and it closes both escapes.** The fix for the
  ranking is to refine each proposal before scoring it — which is precisely what
  makes 10⁵-10⁶ trials unaffordable, since a refinement is not a 40 µs score. The
  fix for the throughput is to score raw proposals — which is what makes the ranking
  fail. And the WP's own named fallback (run engine C only on WP-1021/1022's
  candidates) is forbidden here for the reason the WP states: it destroys the
  independence the consensus argument is built on. A re-scorer is a legitimate thing
  to want, but it is not an engine and must not count toward `found_by`.

  **What the spike found that outlives it, and it is bigger than engine C.**
  Chasing the tier-1 zero led to running the two *landed* engines on the same real
  pattern, and **neither indexed it**: dichotomy 0 candidates, trial-and-error 0
  candidates, on a pattern whose answer is certified. Same cause — their tolerance
  was the fitted per-line σ, which is 11× too tight for the systematic the data
  carries. Both engines now take `engines.DEFAULT_UNKNOWN_SHIFT_DEG` (0.05° 2θ) in
  quadrature when no shift has been *measured*, report it with
  `INDEX_SHIFT_ALLOWANCE`, and consume `SearchSpec.shift_template` through
  `engines.refine_with_shift` so an accepted candidate is corrected rather than left
  carrying the shift in its cell. That is **not** yet enough to index corundum — at
  0.05 trial-and-error still finds nothing and dichotomy ranks a wrong 618 Å³ cell
  first; at 0.08 trial-and-error recovers a = 4.7659 Å against 4.7593 (+1400 ppm,
  the shift absorbed). The gap is recorded in the constant's docstring and handed to
  **WP-1026** with the measurement, because real-data acceptance is that WP.

  **If anyone reopens this**, the two things that would change the answer are (a) a
  tier-1 score that is *shift-invariant* — scoring Q *ratios* or differences rather
  than absolute Q would sidestep the whole 11σ problem and is not something the
  plan considered; and (b) a proposal mechanism that is not random, at which point it
  is not a Monte Carlo engine any more. Neither is a small change, and both need
  their own spike.
