# WP-1040 — Engine C (second attempt): SVD-Index

Milestone: v1.0 · Status: ✅ 2026-08-05 — **built and landed**, every task done;
the scoreboard was re-measured in WP-1041 behind the two `trial_error` dedup fixes
measured here, and both of the failures this WP inherited now rank the truth first
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
- [x] The zero-error column and the two-pass strategy; check against WP-1038's
      measured shifts where both exist. *(Built as §2.4's three passes,
      `svd.svd_trial`; the check is two acceptance rows. What it buys is not
      what this WP predicted — see the 2026-08-05 task-3 entry.)*
- [x] The Monte Carlo strategy layer (Coelho Table 2), with the control parameters
      per system from his Table 3, and a seeded RNG recorded in the result.
- [x] Register as an engine; extend `consensus`, the agent schema and the CLI from
      the live registry (the meta-tests will fail if a registry member is missing).
- [x] Restate WP-1023's no-go line, and `CLAUDE.md`'s Monte Carlo rule, as
      "unrefined random-cell scoring does not rank".
- [x] Acceptance across the corpus + `validation_matrix.py` + regenerate
      `docs/VALIDATION.md`. *(38 rows green; two `Claim`s added, 63 total.)*
- [x] Re-measure the scoreboard with three engines. **Done in WP-1041**
      (2026-08-05), and the handoff condition was right: fixing `trial_error`'s
      dedup first turned over three rows, and the board itself turned out to
      have **nine** datasets rather than eight. Final: 6 rank the truth first,
      2 find it below first, 1 is refused before searching, **0 promoted** —
      with brucite and magnetite, this WP's two inherited "failures", both now
      first. It is generated from the acceptance run rather than typed.

## Acceptance

Task 0's table decides the WP. If built: the engine finds the truth on the datasets
the other two do, `found_by` shows genuine three-way agreement somewhere, and no
dataset regresses.

```sh
# NB test_agent_surface.py, not test_agent.py — the name this file carried until
# 2026-08-05.  A path that does not exist makes the whole selection collect
# nothing (exit 5), and piping the run through `tail` hides that exit code.
.venv/bin/python -m pytest tests/test_indexing_engines.py tests/test_indexing_consensus.py \
    tests/test_capabilities.py tests/test_agent_surface.py -n auto
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

- **2026-08-05 (task 3)** — **the zero-error column is built, it does the
  opposite of what this WP predicted, and the opposite is the better result.**
  `svd.zero_error_column` / `svd.svd_trial` / `SvdPass`, six new fast tests and
  two new acceptance rows.

  **What was predicted.** The entry above said *"expect it to unlock A-D; if it
  does, the milestone's benchmark bar becomes scorable"*, on the measured
  observation that those sets' lines sit a median 2.5 % in Q from the published
  cell's predictions. **It does not, and the 2.5 % was the wrong diagnosis.**
  Closest approach to the true lattice over 1500 random starts, in
  `equal_reduced`'s own relative units where 0.005 is a hit:

  | | pass 1 | +Ze | +cut | +Ze+cut |
  |---|---|---|---|---|
  | Aa Ab Ba Ca Cb Da | 0.23-0.33 | 0.21-0.33 | 0.23-0.32 | 0.22-0.33 |
  | Bb | 0.122 | 0.032 | 0.020 | **0.007** |
  | Db | 0.011 | 0.032 | 0.010 | **0.007** |
  | E | 0.017 | 0.005 | 0.007 | **0.005** |
  | F | **0.0009** | 0.011 | 0.004 | 0.004 |

  Six of the ten sets are never within a *third* of the true lattice under any
  strategy, so nothing about the shift was ever going to reach them. The cause
  is in the fixture's own README: the `a` entries (PDF 43-1748) carry **7
  impurity lines in 20**, past the 33 % Coelho's §2 says the N_c/N_o gate
  tolerates and past anything his Table 6 tests. And half the A-D sets barely
  have a shift at all — the paper's blanket −0.100° is right for 43-1748 and
  wrong for 46-1964, so `Ab`/`Bb` need ~0.003° and the "corrected" `Cb`/`Db`
  need −0.103°. **A measured number can still be the wrong explanation**: 2.5 %
  in Q was real and was not the blocker.

  Of the four sets that *are* reached, three improve and **F gets worse** — the
  synchrotron set has the most precise positions and essentially no shift, so a
  free column has nothing to absorb and costs 0.0009 → 0.004. That does not
  reach the answer, because `_keep` re-fits every converged metric on 1/σ(Q)
  before anything is reported, but it is why the strategy is not claimed free.

  **What it actually buys — it does not make the search converge, it stops a
  converged answer from being wrong.** Started **at** the truth on a synthetic
  monoclinic with a zero error injected, so the search is out of the question
  and only the modelling is measured:

  | injected Ze | recovered | lattice, 1 pass | lattice, 3 passes |
  |---|---|---|---|
  | +0.020 | +0.0200 | 0.0030 | 0.0000 |
  | +0.050 | +0.0497 | 0.0260 | 0.0000 |
  | +0.100 | +0.0989 | **0.0354** | **0.0001** |
  | −0.080 | −0.0807 | 0.0334 | 0.0001 |

  One pass has no way to express a shift, so it puts the shift into the axes —
  3.5 % out at 0.10°, which every equality test in the package calls a different
  lattice. This is the package's own `refine_with_shift` lesson (+1400 ppm on
  corundum) one rank lower down, inside the search's own loop. With a realistic
  0.005° of scatter the three-pass result sits at 0.0044 *independently of the
  injected shift*, which is the residual of the scatter and not of the shift.

  End to end, same spec and seed, `search_svd` per system: **qarr corundum 0
  candidates → 1, the truth ranked first at 3e-4**, while zincite and zircon
  return the same cells at the same ranks to five figures. Cost 1.2-2× the wall
  clock (2.0→2.8 s, 4.2→4.4 s, 3.5→7.2 s). No dataset regressed, which is this
  WP's stated acceptance.

  **The check task 3 asked for, and it is the strongest result here.** Three
  methods measure the shift and **none sees what the others do** — the
  reference-based screen sees certified positions, WP-1038's pair screen sees
  only harmonic pairs among the observed lines, Coelho's column sees only a
  candidate lattice:

  | dataset | pairs (`constant`) | vs reference | SVD Ze |
  |---|---|---|---|
  | SRM 660c LaB6 | +0.0359 | +0.0367 | **+0.0329** |
  | qarr corundum | −0.0670 | −0.0650 | **−0.0666** |

  Within 0.003° both times. It also reaches where the pair screen declines: a
  bare 20-line list has too few pairs to concentrate (the published bethanechol
  failure `test_indexing_pairs.py` reproduces) and this needs none.

  **The one design decision, and it went against the paper's grain.** Coelho's
  column *is* the `constant` template by construction, and WP-1038 measured that
  `constant` and `cos_theta` concentrate within one pair of each other — the
  magnitude is knowable and the cause is not. The package already has the rule
  for that case, in `effective_sigma_sys`: **a shift measured without an
  attribution sizes windows; only a template the caller declared corrects a
  cell.** So the fitted Ze centres the matching window inside `_keep`, is
  reported as `<system>.ze_deg` in the engine's stats, and never writes the
  reported cell — `refine_with_shift` stays the single authority. Letting it
  write one would have created a second, disagreeing about which template the
  shift belongs to, on candidates whose template the caller may have declared to
  be something else.

  **The acceptance run found two things the synthetic and per-dataset checks
  did not, and I had already written "nothing regressed" on the strength of
  three datasets. One of them had.**

  **A regression, and a latent bug of the same family as last session's.**
  11-BM NAC came back **cubic P with 92 predicted-and-absent reflections** in
  place of the cubic **I** description of the *identical* axes (a = 10.25120
  either way, +19 ppm). Cause: `_keep`'s `seen` set spans the whole centring
  loop while `_solution_key` keys on the metric alone, so **the first centring
  tried claims a metric and every later one is silently discarded** — and `P` is
  first in `centrings_for`. It never fired before because the P pass did not
  converge on that metric; the three-pass made it converge. This directly
  contradicts `dedup_groups`' own documented rule — *"the same metric with two
  different centrings is two different lattices … merging them would silently
  drop a hypothesis the figures of merit are there to choose between"* — so the
  key now carries the centring. **`trial_error._solution_key` has the same
  defect in the same shape** (its `seen` is also outside the centring loop),
  alongside the scale-invariance already handed to 1041.

  **A ranking defect it exposed, filed rather than attempted.** With both
  descriptions returned, the panel leads with the **wrong** one. The panel has
  the answer — `m_rev` is **356.1 for I against 0.69 for P**, a 516×
  separation, precisely the reversed-member behaviour Oishi-Tomiyasu was adopted
  for — but `borda_scores` weighs every member alike, so the four forward
  members (M₂₀ 2.60 vs 1.57, F_N 10.5 vs 7.8, both indexed fractions) outvote
  the three reversed ones **4-3**. That docstring says a weighted sum *"would
  need weights, and there is no data on which to set them"*; this is the first
  decisive datum. Note the obvious fix does **not** work: balancing the two
  directions gives 0.5 each, a tie. It needs a magnitude-aware aggregate and a
  measurement across every row, so it is filed, and the NAC row pins the current
  order with an assertion that inverts when it lands.

  **And a capability gain, in the row that filed the σ_sys trap.** The LaB6
  calibrated row asserted that declaring the screen's *residual scatter*
  (0.0078°) instead of the shift *amplitude* (0.038°) — a window 4.3× too tight
  to span the shift — returns **no candidate at all**. It now returns the
  certified cell at **+5 ppm**, `found_by == ["svd"]`, reporting Ze = +0.033°.
  A search that can *measure* a shift no longer needs its window widened to span
  one. WP-1028's σ_sys semantics are not thereby fixed — the two engines that
  cannot model a shift still need the wide window — but one engine has stepped
  out of the trap, and that row now asserts which.

  **Three smaller things.**
  1. **This WP's acceptance command named a file that does not exist** —
     `tests/test_agent.py` for `tests/test_agent_surface.py` — since it was
     written. Under `-n auto` that collects nothing and exits **5**, and piping
     the run through `tail` hides the exit code, so it reads as a clean run.
     Fixed above; the trap is worth remembering for any multi-file selection.
  2. **The paper contradicts itself on the m range and neither reading of it was
     a misreading.** §2.2 says *"randomizing m between 0 and 4"*; §3.1's actual
     experiment says the values *"were randomly varied between 0 and 6"*. The
     entry below called the WP's "0-4" a misreading — it was a faithful quote of
     the other sentence. Only §3.1's is attached to a number, and both the 4.4 %
     and the 8.4/11.8 % figures are in §3.1, not §3.2.
  3. `svd_iterate` now returns a `SvdPass` rather than a 4-tuple, because the
     fitted Ze needed somewhere to live and a fifth positional slot on a
     pre-freeze public function is worse than a named record.

- **2026-08-05** — **task 0 measured, the engine built, and it is a go.**
  `src/anatase/indexing/svd.py`, registered as `"svd"`, 10 new tests
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
