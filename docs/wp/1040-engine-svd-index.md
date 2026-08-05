# WP-1040 — Engine C (second attempt): SVD-Index

Milestone: v1.0 · Status: 🔄 2026-08-05 — **built and landed**; tasks 0-2 and 4-6
done, the zero-error column (task 3) and the scoreboard re-measure (task 7) open
Depends on: WP-1020, WP-1024 (1038 soft)

## Goal

A third indexing engine implementing Coelho's iterative-SVD method — the algorithm
behind TOPAS's indexing module, which is this package's stated design target. It
supersedes WP-1023's Monte Carlo no-go rather than reopening it.

## Context

### Why WP-1023's no-go does not fence this

WP-1023 measured that a Monte Carlo tier-1 ranked the true corundum cell **29 053 of
200 001**, and concluded against a Monte Carlo engine. Two source papers show the
conclusion was drawn about the wrong thing.

**Coelho (2003) §2** — TOPAS's SVD-Index *is* Monte Carlo: *"Built on top of the SVD
process is a Monte Carlo approach to searching parameter space and thus it is not an
exhaustive method."* But the Monte Carlo supplies only the **starting** metric;
Table 1 then iterates — assign each observed 1/d² to the nearest calculated one,
re-solve `H X = D` by SVD, repeat until the hkl assignment stops changing (~5
iterations).

**Le Bail (2004) §III** — McMaille has the same shape: a proposal is accepted on a
loose gate, then *"the cell parameters are adjusted by a Monte Carlo process,
testing randomly 200 to 5000 small parameter changes"*, reaching minima *"which a
least-squares refinement process would not have allowed"*, with a non-improving move
accepted ~15 % of the time. Table I measures P = 0 … 100 % and 15 % wins on all four
test cases (orthorhombic 45 vs 41 at P = 0; monoclinic 60 vs 47).

**WP-1023 scored raw random cells with no refinement stage at all.** Both working
Monte Carlo indexers refine every proposal; ours refined none. So WP-1023's number
stands for what it measured and does not transfer here. **Restate its no-go as
"unrefined random-cell scoring does not rank"** when this WP lands.

### What the algorithm buys that our two engines cannot

- **No tolerance input.** Coelho §1: SVD-Index *"does not require errors in the
  input d-spacings as input"*, in explicit contrast to the dichotomy method, which
  *"fails if the user-supplied d-spacing intervals do not encompass the true
  solution"*. That is precisely our `DEFAULT_UNKNOWN_SHIFT_DEG` bind.
- **The zero error is a column, not a window.** Eq. (7) appends
  `Ze·(π/360)·(4/λ²)·sin 2θ` to the design matrix and lets SVD return it. It is run
  in a **second pass**, after a zero-error-free pass has settled the hkl assignments,
  because *"the absolute value of Ze as returned by SVD is often too large (>0.1°)
  … due to grossly incorrect hkl assignments in the early iterations"*. Good to
  ±0.05° 2θ. Note the design column is `sin 2θ` because a **constant** 2θ shift
  perturbs Q that way — this is not our `sin_2theta` *template*, which is a
  transparency model in 2θ space. Do not conflate them.
- **Cost is small.** Average calls to the inner loop before the correct solution
  (Coelho Table 5, 20 d-spacings): triclinic **105**, monoclinic 78, orthorhombic
  63; and §4.3 tetragonal 26.1, trigonal/hexagonal 8.3, **cubic 1.3**.
- **It is a genuinely independent third opinion** — a different algorithm class
  from exhaustive dichotomy and exact-solve trial-and-error — so it *strengthens*
  `consensus.grade`'s two-engine requirement rather than diluting it. Coelho reports
  SVD-Index solved every test input given to ITO, TREOR90 and DICVOL91.

### Two prunes worth stealing even if the engine is never built

1. **The `N_c/N_o` gate** (§2, Table 1 step ii): abandon a trial when the number of
   calculated d-spacings inside the observed sphere is `< 1/3` or `> 4` times the
   observed count. Cheap, in-loop, and we have no equivalent — our
   `predicted_but_absent` is a post-hoc detector.
2. **The weighting function** (§2.2): `W_hkl = d_o^m · |Δ2θ_hkl| · I_o`, with m
   randomised 0–4. Measured per-trial success 4.4 % → 8.4 % (m randomised) → 11.8 %
   (full form). **This is the only use of observed intensity in any search algorithm
   reviewed here** — McMaille's columnar-overlap R_p is the second — and
   `PeakList` carries intensities that no part of our search reads.

### Fences learned from WP-1023

An engine's independence is what makes consensus mean anything. WP-1023's own rule:
a re-scorer running on WP-1021/1022's candidates *"is not an engine and must not
count toward `found_by`"*. SVD-Index proposes its own cells from scratch, so it is a
real engine — but do not let it degenerate into a refiner of the others' output.

### Licensing — read this before writing a line

TOPAS is closed source; CLAUDE.md's rule is **papers only, never code**. Coelho
(2003) is the full algorithm published in *J. Appl. Cryst.*, which is exactly what
that rule permits. Implement from the paper. Do not consult TOPAS, its scripts, or
any decompiled artefact.

## Non-goals

- Conograph's topograph/zone enumeration — still v2-fenced; its figures of merit
  were already adopted in WP-1030.
- Reviving WP-1023's whole-profile tier-2 Le Bail rescorer as an *engine*; if built
  at all it is a re-scorer under WP-1023's fence.

## Tasks

- [x] **Task 0 — spike Table 1 alone.** Implement the iterative-SVD inner loop and
      measure, on the known-cell corpus: calls-to-convergence, wall clock per call,
      and whether the truth is reached at all. Compare against Coelho's Table 5
      averages (triclinic 105 / monoclinic 78 / orthorhombic 63). **Go/no-go on this
      table**, as WP-1023 was — and unlike WP-1023, on a peak list with the
      `not_separable` screen already applied.
- [x] The weighting function and the `N_c/N_o` gate, measured separately so their
      contributions are attributable (Coelho's own 4.4 → 11.8 % decomposition is the
      template).
- [ ] The zero-error column and the two-pass strategy; check against WP-1038's
      measured shifts where both exist.
- [x] The Monte Carlo strategy layer (Coelho Table 2), with the control parameters
      per system from his Table 3, and a seeded RNG recorded in the result.
- [x] Register as an engine; extend `consensus`, the agent schema and the CLI from
      the live registry (the meta-tests will fail if a registry member is missing).
- [x] Restate WP-1023's no-go line, and `CLAUDE.md`'s Monte Carlo rule, as
      "unrefined random-cell scoring does not rank".
- [ ] Acceptance across the corpus + `validation_matrix.py` + regenerate
      `docs/VALIDATION.md`; re-measure the 8-dataset scoreboard with three engines.

## Acceptance

Task 0's table decides the WP. If built: the engine finds the truth on the datasets
the other two do, `found_by` shows genuine three-way agreement somewhere, and no
dataset regresses.

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py tests/test_indexing_consensus.py \
    tests/test_capabilities.py tests/test_agent.py -n auto
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Coelho (2003), *J. Appl. Cryst.* **36**, 86 — the algorithm. Tables 1–3 are the
  implementation; §2.2 the weighting; §2.3 the zero error; Table 6 impurity rates.
  `/Users/yue/zotero-linker/derived/5RI7CB42/`
- Le Bail (2004), *Powder Diffr.* **19**, 249 — McMaille; §III tricks (a)–(d) and
  Table I are the independent confirmation that MC needs local refinement.
  `/Users/yue/zotero-linker/derived/7AEVVGH6/`
- Boultif & Louër (2004), *J. Appl. Cryst.* **37**, 724 — Table 3 indexes Coelho's
  own 12 examples with DICVOL04, a ready-made cross-code comparison.
  `/Users/yue/zotero-linker/derived/I2VA3ZAB/`
- `docs/wp/1023-engine-montecarlo.md` — the superseded no-go and its numbers.

## Handover log

- **2026-08-05** — **task 0 measured, the engine built, and it is a go.**
  `src/pxrdref/indexing/svd.py`, registered as `"svd"`, 10 new tests
  (`tests/test_indexing_engines.py`, one `slow`).  Branch
  `wp1040-engine-svd-index`.

  **Task 0's table**, on the known-cell corpus, calls to Table 1 before the true
  lattice is first reached (median of five seeded runs; Coelho's simulated
  averages beside):

  | dataset | system | calls to truth | Coelho |
  |---|---|---|---|
  | SRM 660c LaB6 | cubic | **1** | 1.3 |
  | 11-BM NAC | cubic | **6** | 1.3 |
  | qarr zincite | hexagonal | **107** | 8.3 |
  | qarr zircon | tetragonal | **150** | 26.1 |
  | GSAS-II FAP | hexagonal | **389** | 8.3 |
  | bethanechol F | monoclinic | **~15 000** | 78 |
  | qarr corundum | trigonal | never (see rule 4) | — |

  A Table 1 call is **0.2-3 ms**, so the whole ladder is seconds where dichotomy
  is minutes.  The bethanechol row is what made it a go: the acceptance file
  records that an exhaustive dichotomy over the paper's own domain returns **0
  candidates and never finishes**, at 240 s *and* at 900 s.

  **Four measured rules, each contradicting something reasoned from the
  algorithm's structure** — they are in the module docstring and the shortest
  forms are in CLAUDE.md:

  1. **the N_c/N_o gate is a volume window**, computable before the search from
     one κ probe, and it contained the truth on all nine corpus datasets;
  2. **N_c counts distinct calculated d-spacings, not hkl** — the paper's caption
     and its prose disagree and only the prose can be right;
  3. **the impurity cut belongs in the last pass only, as Coelho says and
     contrary to what real data suggests** — in pass 1 it takes zincite 5/5 → 1/5
     and zircon and FAP to 0/5;
  4. **one line below the lattice's longest d destroys the eq. (4) weighting** —
     corundum's 5.17° edge artifact is 3.9× beyond anything its lattice can
     produce, and gives **0 convergences in 4000 starts** against 3293 with that
     one line removed.  Coelho's impurity tests only reach 1.5×.

  **Two defects in existing code, both surfaced by the new engine exercising it.**
  `_solution_key`'s scale-*invariant* hash maps every cubic cell to one key, so
  the first random start blocks all later ones (a clean synthetic cubic returned
  0 candidates from 72 starts that included the truth).  Fixed in `svd.py`;
  **`trial_error.py` carries the same form and the same blind spot** — untouched
  here deliberately, because changing a shipped engine's dedup inside a WP about
  a third engine is an unmeasured behaviour change, and it is narrow (cubic is
  the only 1-DOF system).  Worth a WP or a task in 1041.  And the progress-ladder
  test in `test_indexing_ceiling.py` spelled its engine names out rather than
  quoting `engine_names()`; now quoted, as `found_by` on the LaB6 row is too.

  **Two acceptance rows turned over, both toward capability.**  11-BM NAC is now
  indexed *as measured* — a = 10.2512 Å cubic **I**, +19 ppm, `predicted_but_absent`
  0 of 837 — where the row previously asserted that it cannot be.  The dichotomy
  still explores zero boxes (premise unchanged and still asserted); `search_svd`
  enumerates no box at all, so the resolution that defeats a box search never
  arises for it.  The gate is untouched: one engine is not agreement, so it stays
  `low` with `best_or_none()` None.  **Two recorded no-goes died there** — WP-1026's
  2θ-truncation no-go was measured with the 2θ-ordered selection WP-1039 replaced,
  and that row's own closing sentence predicted its own reversal.  *A recorded
  no-go inherits the defects of the run that produced it.*  And SRM 660c LaB6 is
  now found by all three engines.

  **What is open, and the order to take it.**

  1. **Task 3, the zero-error column** — and the corpus says it is not optional.
     Bethanechol sets **E and F are reached** (E 3/3 seeded runs, F 1/3-3/3);
     **A-D never are**, and the reason is measurable rather than mysterious: at
     the published cell, set Aa's lines sit a median **2.5 % in Q** from their
     predictions against set F's 1.9e-4.  Those sets carry the zeroshift the
     benchmark was built to test, and Coelho §2.3's zero-error column in a second
     pass is exactly the instrument for it.  Expect it to unlock A-D; if it does,
     the milestone's benchmark bar becomes scorable.
  2. **Task 7, the scoreboard**, which is 1041's as much as this WP's.
  3. **A reported cell may be in an odd setting.**  SVD-Index starts from random
     metrics and quotients by nothing, so the synthetic monoclinic truth came back
     as (11.010, 16.408, 8.875, β = 139.70°) — the same lattice, volume 1037.0 to
     four figures.  Consensus dedups on the *reduced* form so nothing downstream
     is wrong, but a user reading `candidates[0].cell` sees β = 139.7°.  Deciding
     whether engines should normalise their reported setting touches all three and
     consensus, so it is a decision rather than a fix.  It also caught me: the
     first version of the monoclinic test compared sorted axes and scored the
     correct answer a miss, which is CLAUDE.md's "a candidate cell is a lattice,
     not a tuple" in the one place it bites hardest.

  **Two corrections to this WP's own context section**, both from reading the
  paper rather than the summary of it (the WP-1039 edge, paid a second time).
  §3.2 randomises m between **0 and 6**, not 0-4 — 4 is where "an optimum setting
  for m occurs", a different sentence.  And the "4.4 → 8.4 → 11.8 %
  decomposition" is **two experiments**: 4.4 % is §3.1's triclinic Δ = 0.3
  perturbation rate, while 8.4 and 11.8 are §3.2 single-pass Table 2 runs.
  Measured here, randomising m is not free either — it helps LaB6 at large Δ and
  takes NAC from 100 % to 51-67 % — so `WEIGHT_EXPONENT` is fixed at 4 and the
  randomisation is recorded as unreproduced rather than adopted on the paper's
  word.

  **Numbers**, `[dev,jax]` no torch, darwin/arm64 M4, in `worktree-indexer`: fast
  **1718 passed / 67 skipped** (1039's 1708 + 10, no new skips), full **1813 / 72**
  at 24:03, indexing acceptance **36 rows, 20:03** against 11:58 with two engines.

  **One cost is worth the successor's attention before anything else**: the *fast*
  suite went from ~55 s to **~3 min**, and only ~10 s of that is the new rows. The
  rest is every `index_pattern`-driven fast test now running three engines —
  `test_a_restricted_search_is_not_a_verdict_about_the_specimen` alone is **51 s**.
  Nothing is wrong; three engines cost three engines. But the developer loop is a
  design input (CLAUDE.md), and the lever is narrowing what those rows *search*,
  never their budgets and never a silent cap.

  **The spike lives in the job scratchpad, not the repo** (`svd_table1.py`,
  `svd_table2.py`, `corpus.py`, `exp_*.py`): every rule it measured is now either
  a test or a docstring, so the scripts are superseded evidence rather than
  something to maintain.  The corpus builder is the one worth re-deriving if task
  3 needs it — 30 lines over `pick_peaks` and the acceptance fixtures.

- **2026-08-04** — created from the source-literature review. Nothing measured this
  session; every figure is quoted from the papers. The WP exists because reading
  Coelho showed the stated design target (TOPAS) is a Monte Carlo method, which put
  WP-1023's no-go and the project's own goal in direct contradiction — resolved by
  noticing that both working MC indexers refine each proposal and WP-1023's spike
  refined none.
