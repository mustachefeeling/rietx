# WP-1040 — Engine C (second attempt): SVD-Index

Milestone: v1.0 · Status: ⬜
Depends on: WP-1020, WP-1024 (1038 soft)

## Goal

A third indexing engine implementing Coelho's iterative-SVD method — the algorithm
behind TOPAS's indexing module, which is this package's stated design target. It
supersedes WP-1023's Monte Carlo no-go rather than reopening it.

## Context

### Inherited

**From WP-1039, closed 2026-08-05.** A third engine must select its driven lines
through `engines.search_line_order` like the other two — the whole point of that
seam is that "which lines drive the search" means the same thing in every engine,
or their agreement stops being evidence. It returns the strongest `n_search_lines`
in Q order, and ties fall back to Q, so a position-only list behaves as before.

Two measured facts that bear directly on an SVD engine. **Do not raise
`n_search_lines` to feed the SVD more rows**: `indexes_the_search_lines` is an
absolute budget, so each foreign line admitted *refutes* the true cell rather than
ranking it lower (zircon loses its certified lattice going from 20 to 32). And the
base-line lesson from `trial_error` transfers — its exact solve was failing on SRM
660c not because the method was wrong but because it was handed the pattern's
low-angle background components to solve from. Any engine that assumes indices for
a small set of lines wants that set drawn from the *selection*, not from the raw
low-Q end.

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

- [ ] **Task 0 — spike Table 1 alone.** Implement the iterative-SVD inner loop and
      measure, on the known-cell corpus: calls-to-convergence, wall clock per call,
      and whether the truth is reached at all. Compare against Coelho's Table 5
      averages (triclinic 105 / monoclinic 78 / orthorhombic 63). **Go/no-go on this
      table**, as WP-1023 was — and unlike WP-1023, on a peak list with the
      `not_separable` screen already applied.
- [ ] The weighting function and the `N_c/N_o` gate, measured separately so their
      contributions are attributable (Coelho's own 4.4 → 11.8 % decomposition is the
      template).
- [ ] The zero-error column and the two-pass strategy; check against WP-1038's
      measured shifts where both exist.
- [ ] The Monte Carlo strategy layer (Coelho Table 2), with the control parameters
      per system from his Table 3, and a seeded RNG recorded in the result.
- [ ] Register as an engine; extend `consensus`, the agent schema and the CLI from
      the live registry (the meta-tests will fail if a registry member is missing).
- [ ] Restate WP-1023's no-go line, and `CLAUDE.md`'s Monte Carlo rule, as
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

- **2026-08-04** — created from the source-literature review. Nothing measured this
  session; every figure is quoted from the papers. The WP exists because reading
  Coelho showed the stated design target (TOPAS) is a Monte Carlo method, which put
  WP-1023's no-go and the project's own goal in direct contradiction — resolved by
  noticing that both working MC indexers refine each proposal and WP-1023's spike
  refined none.
