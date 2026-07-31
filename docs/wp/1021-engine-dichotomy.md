# WP-1021 — Engine A: successive dichotomy

Milestone: v1.0 · Status: ✅ 2026-07-30
Depends on: 1020

## Goal

An **exhaustive** branch-and-bound cell search whose silence is evidence: when
it completes a domain and finds nothing, no cell of that symmetry and volume
fits the peak list within tolerance.

## Context

Successive dichotomy divides an n-dimensional parameter domain into 2ⁿ
subdomains, discards any that provably cannot contain a solution, and recurses.
*Sources*: Louër & Louër (1972), Boultif & Louër (1991, 2004). **Papers only —
no DICVOL code may be read or ported** (CLAUDE.md licensing fence).

- **Search A..F, not (a,b,c,α,β,γ).** Q is linear in the metric components
  (WP-1020), so over an axis-aligned box in A..F the extremes of `Q(hkl)` are
  attained **exactly at box corners** — no interval arithmetic over
  trigonometric functions, no monotonicity case analysis for the cross terms,
  and the bound is tight rather than conservative. The literature formulation
  works in direct space (and switches to reciprocal space for triclinic
  precisely because the direct expression gets unmanageable); the A..F
  formulation is derived from the linearity and removes that case split
  entirely. Physical bounds (`max_axis`, positive-definiteness of G*, volume
  shells) map into the A..F domain.
- **The prune test**, per box:

  ```
  for each observed line i, in increasing Q:
      if no hkl in the trial index set has
         [Q_min(hkl, box), Q_max(hkl, box)] ∩ [Qᵢ − kσ_eff,i, Qᵢ + kσ_eff,i]:
             return IMPOSSIBLE           # unless i is one of the tolerated unindexed
  return POSSIBLE
  ```

  Bisect the widest dimension; accept when every box dimension's induced
  Q-width is below the tolerance of the highest-Q line used; then
  `refine_candidate` and score with the WP-1020 panel.
- **Per-line tolerance, not a global ε.** `σ_eff,i² = σ(Qᵢ)² + σ_sys²` from
  WP-1018/1019. This is what the extra work in those WPs bought.
- **Tolerated unindexed lines are the single most valuable option** — DICVOL06's
  own reported gain. Without it one impurity line prunes the true box and the
  engine returns nothing, confidently. Default `n_unindexed = 2`; document that
  raising it manufactures cells.
- **Search order**: volume shells of 400 Å³, axis interval p = 0.4 Å and angle
  step 5° at the top level (IT-H ch. 3.4 §3.4.3.1.5), highest symmetry first —
  a cubic answer costs seconds.
- **Cost is exponential in metric DOF**: cubic (1) and tetragonal/hexagonal (2)
  seconds, orthorhombic (3) tens of seconds, monoclinic (4) minutes,
  **triclinic (6) will blow any budget**. Budget per system and report.
- **Reflection-count ceiling before enumeration.** Measured (tag
  `guillemot-study`, `audit_tools.py` check B — read it with `git show
  guillemot-study:studies/guillemot/out/audit_full.txt`; **the study is
  deliberately not merged into `main`**): a runaway cell made the reflection
  generator ask for **1.6 PiB**.
  `generate_reflections` enumerates a box `hmax = floor(a/d_min)+1` per axis,
  so volume enters cubed. Check the predicted count against a ceiling *before*
  calling it. This is a crash guard, not a quality guard.

### Inherited

From **WP-1020**: `refine_candidate`, the FoM panel, `reduce.py`'s χ²
cell-equality (use it to dedup this engine's own output before returning), and
the symmetry-allowed metric subspace — the box dimension **is** the subspace
dimension, so a cubic search is genuinely 1-D.

From **WP-1019**: `σ_sys` and the chosen shift template; the volume envelope
that bounds the outermost shell.

**Correction from WP-1019 (2026-07-30): `INDEX_DOMINANT_ZONE` does not exist,
and detecting a dominant zone or row is owed to *this* WP.** 1019's plan said
both are "detectable in Q-space before any search"; measured, they are not.
Neither is a summary statistic of a peak list — a dominant zone is the statement
that the low-angle lines satisfy a **two-dimensional** quadratic form, and a
dominant row is an arithmetic progression k²B among the low Q values. Each is a
search, which is why it lands here. The census that was tried and removed (Ito's
most-repeated Q difference) scored dominant-zone cells (c = 3.1, 2.7 Å) at +0.9σ
and +0.8σ against a permutation null while scoring a *general* monoclinic cell at
+3.3σ; against a uniform null a **cubic** list scores +15.6σ, because
Q = A(h²+k²+l²) makes every difference a multiple of A. Two lessons for any
statistic this engine invents: use a **permutation** null (same spacing multiset,
order destroyed) rather than a uniform one, since the uniform null would have
"confirmed" the useless statistic; and check the negative case (a general cell)
before believing the positive one. A test in `tests/test_indexing_quality.py`
asserts the code's absence so it cannot creep back as an unmeasured claim.

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

- No consensus, no confidence gate, no Le Bail validation (WP-1024).
- No leave-k-out over *base* lines — this engine uses all lines and tolerates
  a declared count of unindexed ones instead; leave-k-out belongs to WP-1022,
  whose failure mode it addresses.
- Triclinic completeness is **not** claimed; see Acceptance.

## Tasks

- [x] `indexing/dichotomy.py`: the A..F domain map, corner-exact Q bounds, the
      prune test with tolerated unindexed lines, bisection and recursion.
- [x] Volume-shell / symmetry search order; the predicted-reflection ceiling.
      **Shells were tried and removed** — see the handover log: the grid pass is
      nearly shell-independent, so iterating shells pays the grid again per shell
      with the answer's shell last. Ordering the *survivors* by volume gives the
      same "cheap answers first" property for one grid pass.
- [x] Time budget per system; `search_complete[system]`;
      `INDEX_SEARCH_INCOMPLETE`.
- [x] Registry entry so `engines=("dichotomy",…)` resolves, and so
      WP-1024's agent schema can quote it from the live registry
      (`engines.register_engine` / `engine_names`).
- [x] `tests/test_indexing_engines.py`: recovery in every system cubic through
      monoclinic; 1 and 2 injected impurity lines at `n_unindexed=2`, **with the
      negative half** (at `n_unindexed=0` the impurity prunes the truth); the
      corner bound asserted in both directions (no interior point outside the
      interval *and* the interval attained, so a merely-valid bound fails);
      the reflection ceiling refusing instead of allocating; an unfinished
      search reporting itself; a restricted search reporting only what it
      searched.
- [x] Dominant zone / dominant row: **not** detected here. See the handover log
      — it is owed to WP-1022, which is where the evidence for it arises.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py -k dichotomy -q
.venv/bin/python -m ruff check src tests examples
```

Criterion: cubic / tetragonal / hexagonal / orthorhombic / monoclinic cells
recovered from synthetic lists within the per-line tolerance, with wall clock
per system recorded in the handover log. **Triclinic ships budgeted and its
incompleteness is reported** — do not assert exhaustiveness for it here or in
`docs/VALIDATION.md`.

## References

- Louër, D. & Louër, M. (1972). *J. Appl. Cryst.* **5**, 271-275.
- Boultif, A. & Louër, D. (1991). *J. Appl. Cryst.* **24**, 987-993.
- Boultif, A. & Louër, D. (2004). *J. Appl. Cryst.* **37**, 724-731 — the
  tolerated-unindexed-lines and zero-point handling.
- Altomare *et al.* (2019), IT Vol. H ch. 3.4 §3.4.3.1.5 — the interval scheme
  and step sizes.
- Prior art at the tag `guillemot-study` (**not merged into `main`**; check B's
  finding is restated in Context, so this is corroboration):

  ```sh
  git show guillemot-study:studies/guillemot/out/audit_full.txt   # §B
  ```

## Handover log

- **2026-07-29** — created from the indexing plan.
- **2026-07-30** — **complete.** `indexing/engines.py` (the shared surface) and
  `indexing/dichotomy.py` (the engine), 20 fast tests + 1 slow, green; ruff clean.

  **Done.** Corner-exact Q bounds over the A..F box, the prune test with
  tolerated unindexed lines, the grid-then-dichotomy structure, canonical axis
  ordering, per-system budget and `search_complete`, the reflection ceiling, the
  registry. Measured recovery with the truth **ranked first** and
  `search_complete` true: cubic 0.02 s, hexagonal 0.05 s, tetragonal 0.12 s,
  trigonal 0.14 s, orthorhombic 0.73 s (all over d ∈ [2, 12-16] Å, V ≤ 1500 Å³),
  monoclinic **84 s** over d ∈ [6, 18] Å. NaCl comes back as `F` with the right
  centring in 0.01 s.

  **The acceptance criterion is met with one qualification, stated plainly:
  monoclinic recovery needs a *declared axis range*.** Over d ∈ [6, 18] Å it
  completes in 84 s; over d ∈ [2, 18] Å the same list does not finish in 90 s and
  reports `search_complete = False` rather than "nothing found". That is the
  domain cost, not a defect: the grid is (range/0.4)³ × angle slabs, so tripling
  the axis range is ~27× the work. Triclinic is not claimed, as planned.

  **Five structural facts that had to be measured, not designed.** Each replaced
  a plausible design that silently did not work:

  1. **Grid pass and dichotomy must be separate phases.** One combined
     depth-first stack dives to a leaf through the first grid cell it likes and
     exhausts that cell's subtree before looking at the second: 11.9 M boxes in
     240 s on a monoclinic domain *without ever visiting the cell that held the
     answer*, even with the volume shell narrowed to the one containing it.
  2. **The off-diagonal grid must use the box's own Cauchy-Schwarz bound.**
     |2G*ᵢⱼ| ≤ 2√(G*ᵢᵢ·G*ⱼⱼ) is a **cone**, so gridding E over the global bound
     (both axes at their shortest) hands most cells a range they cannot reach and
     *nothing prunes them*. Since the grid is staged, A and C are already narrowed
     when E is cut, so the bound is free.
  3. **Where to stop bisecting is not the measurement tolerance.**
     Exhaustiveness comes from the pruning, which is exact however coarse the
     leaves are. Requiring a box to resolve a line to its own 3σ forces ~15
     halvings per dimension — depth 60 in monoclinic, the cap — so the leftmost
     branch never terminates: **zero** leaves reached in 445 000 boxes. The right
     scale is a quarter of the observed line spacing.
  4. **The leaf's assignment window must be annealed** from the box's own
     resolution down to σ. At a flat 3σ the box holding the true cubic cell
     assigned *zero* lines (its centre is 2.6σ off) — the search had found the
     answer and acceptance threw it away. Jumping straight to the wide window
     instead locks in a mis-assignment: the orthorhombic truth came back as
     (7.0002, 7.9972, 9.0002) indexing 57 of 88 lines and lost the ranking to an
     exact supercell.
  5. **Volume shells are a trap here.** The grid pass is nearly
     shell-independent (its top stages leave whole dimensions undetermined, so
     the volume interval is too wide to prune), so eight shells cost eight grid
     passes with the answer's shell last. Ordering the *survivors* by volume gives
     the same property once.

  **Four upstream defects, three of them in WP-1020's own modules, all fixed
  here with tests in `tests/test_indexing_core.py`:**

  - `borda_scores` gave **tied** candidates distinct ranks in input order. Two of
    five panel members are fractions that saturate at 1.0, so most candidates tie
    on them and the noise is up to N−1 points per tied member — measured, two
    derivative lattices outranked a truth that beat them on *every* member. Ties
    now share an averaged rank (`scipy.stats.rankdata`), and non-finite values
    rank worst rather than best.
  - `predicted_lines` counted symmetry **orbits**, not lines: cubic 333 and 511
    both give 27A, two orbits at one 2θ. Counting distinct lines is both the right
    denominator for de Wolff's and Smith & Snyder's figures and **380× faster**
    (683 ms → 1.8 ms for a 17 Å cubic cell), which is what had made ranking the
    bottleneck. Orthorhombic, monoclinic and triclinic counts are unchanged, and
    that asymmetry is what identifies the gap as coincidence rather than a
    different rule.
  - `m20` / `f_n` took a **plain** mean discrepancy, so a tolerated-unindexed line
    wrecked the score of the cell the search was right to keep: on a tetragonal
    list with one impurity the truth scored M₂₀ = 13.2 against **62.5** for an
    a√5 supercell whose extra reflections cover the impurity — and the supercell
    won, while showing 28 % of its own predicted lines against the truth's 100 %.
    The mean is now trimmed by the same count the search was allowed
    (`fom.trimmed_mean`), and the trim is reported in `blind_spot` because it buys
    a new blind spot.
  - `metric_basis` is now memoised. `refine_candidate` re-derived the exact
    rational nullspace once per accepted box: 2.5 s of a 15 s run, for seven
    possible answers.

  **Corrected 2026-07-30 by WP-1022, same day.** The acceptance rule here read
  "index at least `n_search_lines − n_unindexed` lines" as *anywhere in the
  pattern* rather than *among the search lines*; WP-1022 found it (17 607 candidates
  kept on a 75-line monoclinic list) and both engines now share
  `engines.indexes_the_search_lines`. Two consequences for the numbers above:
  monoclinic **completes** where it previously did not (103 s over d ∈ [6, 18] Å,
  truth ranked first), and the small-system timings moved slightly (cubic 0.02 s,
  hexagonal 0.06 s, tetragonal 0.13 s, trigonal 0.16 s, orthorhombic 0.81 s). The
  qualification about the *declared axis range* stands: cost is the grid, and the
  grid is (range/0.4)³ × angle slabs.

  **In flight:** nothing.

  **Next / gotchas for a successor on this WP.**
  - The junk-cell guard `_inside_domain` exists because refinement wanders: an
    accepted box near the obliquity bound refined out to β = 174° with a 49 Å
    axis. A cell outside the searched domain carries none of the engine's
    exhaustiveness, so it is rejected on **scope**, not quality. If you widen
    `MAX_ANGLE_COSINE`, that guard follows automatically — do not special-case it.
  - `_pivots` raises if `adp_basis` ever returns a non-echelon basis. That is
    deliberate: the failure it prevents is a *loose* bounding box, which returns
    correct cells an order of magnitude slower and no test would notice.
  - Cost is dominated by the grid, not by the line count, so a longer peak list is
    nearly free while a wider axis range is cubic. If monoclinic/triclinic ever
    need to be affordable from a bare `SearchSpec()`, the lever is the domain
    (or engine B), not the tolerances.
