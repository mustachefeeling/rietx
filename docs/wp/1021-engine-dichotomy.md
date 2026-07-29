# WP-1021 — Engine A: successive dichotomy

Milestone: v1.0 · Status: ⬜ not started
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

## Non-goals

- No consensus, no confidence gate, no Le Bail validation (WP-1024).
- No leave-k-out over *base* lines — this engine uses all lines and tolerates
  a declared count of unindexed ones instead; leave-k-out belongs to WP-1022,
  whose failure mode it addresses.
- Triclinic completeness is **not** claimed; see Acceptance.

## Tasks

- [ ] `indexing/dichotomy.py`: the A..F domain map, corner-exact Q bounds, the
      prune test with tolerated unindexed lines, bisection and recursion.
- [ ] Volume-shell / symmetry search order; the predicted-reflection ceiling.
- [ ] Time budget per system; `search_complete[system]`;
      `INDEX_SEARCH_INCOMPLETE`.
- [ ] Registry entry so `engines=("dichotomy",…)` resolves, and so
      WP-1024's agent schema can quote it from the live registry.
- [ ] `tests/test_indexing_engines.py::dichotomy`: recover a known cell in
      every system from a synthetic peak list (cubic through monoclinic);
      recover it with 1 and 2 injected impurity lines at `n_unindexed=2`;
      assert the corner-bound property directly (sampled `Q(hkl)` inside a box
      never exceeds the computed bounds); assert the reflection ceiling
      triggers instead of allocating.

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
