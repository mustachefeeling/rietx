# WP-1518 — the dedup χ² test weighs a difference in the frame it was taken in

Milestone: unscheduled · Status: ✅ 2026-09-28 — dedup χ² reads each covariance in its difference's frame, which
77-98 % of real comparisons did not; no grade moved, bethanechol Db truth rank 1 → 2 (manual −2 → −3), thresholds 1.6
Track: What fires, and what stays silent
Depends on: — (1020 built the test; 1509 built the caches it reads)

## Goal

`engines.dedup_groups` compares two candidates' Niggli-reduced A..F against a
covariance expressed in the **same** reduced frame, and every group, rank and
grade that changes on the acceptance corpus and the bethanechol benchmark is
listed. Until then a same-lattice verdict can be wrong in either direction, and
nothing reports it.

## Context

**The defect, read off the code (2026-09-28, `d88f7ff`).** `_dedup_groups`
(`src/rietx/indexing/engines.py`) reduces each candidate's metric with
`reduce.reduced_af(cand.fit.af)` and then calls

```python
equal_reduced(red, other_red, cov_a=cand.fit.cov_af, cov_b=other.fit.cov_af)
```

`red` is in the **reduced** frame. `cov_af` comes from `qspace.refine_candidate`
as `basis.T @ cov @ basis`, which is in the candidate's **own** A..F frame (the
setting its engine refined in). `equal_reduced` then forms Δ = red_a − red_b,
Σ = cov_a + cov_b and χ² = Δᵀ·pinv(Σ, hermitian=True)·Δ against
`CELL_EQUALITY_CHI2` = 16.81. Wherever the reduction is not the identity, Δ's
components are weighed with the variances of other components, and whatever
lands where Σ has no variance is truncated by `pinv` and never seen.

**Where the frames differ** (probe, `reduced_af(af_from_cell(cell))` against
`af_from_cell(cell)`):

| cell | reduced frame |
|---|---|
| tetragonal (6, 6, 4) — c < a | (A, B, C) → (C, A, B) |
| hexagonal (6, 6, 4, γ 120) — c < a | (C, A, B), and F moves to D |
| monoclinic b-unique (7.1, 9.3, 5.2, β 104) | (C, A, B), and E moves to F |
| tetragonal (4, 4, 6), corundum hexagonal (4.759, 4.759, 12.99) | unchanged |

So corundum's own hexagonal cell is untouched, and any c < a cell or any
monoclinic cell is not.

**Both wrong verdicts occur** (synthetic covariances, 2026-09-28, `[dev]`,
Linux x86-64, py3.12; the scripts were session scratch, rebuilt from this):
- **A false merge.** b-unique monoclinic (7.1, 9.3, 5.2) at two β, each with a
  diagonal own-frame covariance at 1e-4 relative esd on A, B, C, E (D = F = 0
  structurally). β 91.0 vs 91.1, 91.0 vs 91.2 and 90.5 vs 90.7: χ² 1.3, 5.8 and
  1.7 as written — **merged** — against 1.1e3, 4.6e3 and 4.6e3 with both
  sides in one frame. Near 90° the difference is almost all E, which the
  reduction moves into the F slot, where Σ has no variance. At β 91.0 vs 91.5
  the written test gives 46.6 against 2.8e4: still split, but 600× weaker.
  *Superseded in part 2026-09-28:* the written χ² reproduce exactly, and the
  one-frame column does not. With σ_E = 1e-4·E as stated it is 4.5e5, 1.6e6,
  5.4e6 and 7.7e6; the verdicts are unchanged.
- **A false split.** One tetragonal lattice (6, 6, 4), refined twice with
  σ_A = 1e-6 (B tied) and σ_C = 1e-5, 2000 pairs drawn from that covariance:
  the written test splits **41.2 %** of them, the one-frame test 0.1 %.

**Why it matters.** `consensus.merge_engine_candidates` pools every engine's
candidates through `dedup_groups` and writes `found_by` from each group, and
`grade` floors a candidate with fewer than `MIN_AGREEMENT` finders at `low`
before a caveat is read; `high` needs every engine. A false merge fakes
agreement and drops the merged lattice from the list. A false split denies
agreement to a lattice two engines found. Inside one engine the effect is
small: sibling leaves refine onto the same cell bit for bit (WP-1509
measured 7000 raw candidates holding 761 distinct ones), and Δ = 0 passes in
any frame. Across engines, refinements of one lattice from different line
assignments differ slightly, which is exactly where the test decides.

**Not measured: whether any real harvest changes.** Task 1 answers that before
anything is built, and its answer re-rates this WP.

**The fix has its pieces already.** `reduce.reduce_cell` keeps the change of
basis (`ReducedCell.change_of_basis`, a gemmi triplet, from
`GruberVector(track_change_of_basis=True)`). A..F is linear in G\*
(`qspace.gstar_from_af`: columns h², k², l², kl, hl, hk), and a change of basis
acts on G\* as a congruence, so red = T·af for a 6×6 T read off the triplet and
cov_red = T·cov_af·Tᵀ. Two candidates can reduce through different T, so each
covariance is carried by its own. `_dedup_groups` already caches the reduction
once per distinct af (`reduced`, keyed on the af's bytes); the transformed
covariance belongs in the same cache.

**Traps.**
- **The no-covariance branch is already in one frame** (componentwise relative
  on the reduced A..F), and so are `same_lattice`'s callers in `priors.py` and
  `ambiguity.py`, which pass no covariance. Leave them alone.
- **Near a Niggli boundary two copies of one lattice can reduce to different
  equivalent forms**, and Δ is then not small in any frame. That is a
  pre-existing limit, separate from this defect; do not read its cases as this
  WP's.
- **This is not a bit-identity change.** Verdicts move by design, so WP-1509's
  replay digests (brucite hexagonal `c82630be`, trigonal `719d4e0b`; corundum
  hexagonal `6a060c83`, trigonal `e8466d7f`, tetragonal `f610fbdc`; synthetic
  monoclinic `fc4d2b0b`) move wherever a group changes. Say which moved and
  why. Corundum hexagonal and trigonal should not move (their frames are the
  identity). *Superseded 2026-09-28:* they moved, from pool rank 14-16, on
  wrong cells with c < a in the same pool; see the handover.
- `_dedup_groups(fast=False)` is the plain pass WP-1509's test holds equal to
  the fast one. Change both, and keep that test's three witnesses.

## Non-goals

Batching the χ² tests (WP-1519). The choice of `CELL_EQUALITY_CHI2` or of
`pinv`'s cutoff. Niggli-boundary handling. The no-covariance tolerance.

## Tasks

- [x] **Measure first.** On the harvests consensus pools for the acceptance
      corpus (`tests/test_acceptance_indexing.py`'s datasets) and bethanechol's
      ten sets, count candidate pairs the test compares whose reduction is not
      the identity, and the groups that change when Σ is carried into the
      reduced frame. Record every rank and grade that moves. Re-rate this WP
      from the result.
- [x] Carry each candidate's covariance through its own change of basis, once
      per distinct af. Unit tests: the false merge and the false split above,
      each asserted to come out right, and an identity-frame pair (c > a)
      whose verdict and χ² are unchanged to the bit.
- [x] `tests/test_acceptance_indexing.py` and `tests.bethanechol_benchmark`
      (manual mode, run alone) on the final tree, with every changed group
      named. Add a rule to `indexing/CLAUDE.md` if the measurement shows a
      stranger needs one; the candidate wording is "a χ² takes its difference
      and its covariance in one frame".
- [x] Skill: none unless a grade moves on the corpus; if one does, the
      agreement row in the indexing reference says what changed.

## Acceptance

No same-lattice test reads a covariance in a frame other than its difference's.
The corpus and benchmark changes are listed with their cause.

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py tests/test_indexing_consensus.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m tests.bethanechol_benchmark --modes manual
.venv/bin/python -m ruff check src tests examples
```

## References

WP-1020 (the χ² dedup on the reduced cell); WP-1024 (consensus agreement);
WP-1509 (the dedup caches, the replay harness and digests). Křivý & Gruber
(1976, *Acta Cryst.* A**32**, 297-298) and Grosse-Kunstleve, Sauter & Adams
(2004, *Acta Cryst.* A**60**, 1-6) — the Niggli reduction gemmi implements.

## Handover log

### 2026-09-28 (2nd session) — closed: dedup reads each covariance in its difference's frame

Indexing decides that two candidates are one lattice by weighing the difference
of their reduced metrics against their covariances. The covariances had been
left in each engine's own setting, and on real searches that mismatch was the
common case. It covered 77 % of the acceptance suite's comparisons and 98 % of
bethanechol's. Each covariance now goes through the same change of basis as its
metric. No grade moved anywhere, and nothing at rank 1 or 2 moved on the
acceptance suite. On the bethanechol benchmark one true cell drops to rank 2,
behind a wrong cell that two engines really did find, so manual mode scores −3
where it scored −2.

*Done.*
- `reduce.reduction(af)` returns the reduced A..F and the 6×6 map T that took
  `af` there. T comes from gemmi's triplet through `reduce._basis_change` (moved
  there from `ambiguity`, so one reader); its convention, R⁻¹ of gemmi's rot,
  was measured over 28 reductions. `reduce.reduced_covariance(cov, t)` carries
  a covariance. `same_lattice` and `engines._dedup_groups` carry each
  candidate's covariance through its own T, beside the reduction cached once
  per distinct af (f73f00b). T is `None` where red = af component for
  component, and those pairs keep their χ² to the bit (tested).
- Within the reduction's ε, gemmi flips the sign of a near-zero D, E or F and
  the triplet does not record it. `reduction` flips those rows of T (9b8d78f).
  909 of 2000 cells with an angle within 1e-3° of 90° disagreed with the
  triplet's map, every one by sign, and all close to ≤ 8e-16 after.
- Tests, 10 cases over 6 functions: the map as a hypothesis property, four
  snap-zone cells, the false merge, the false split, an identity-frame pair on
  two cells, and two engines' candidates through `dedup_groups` (both passes)
  and `merge_engine_candidates`. The false merge, the false split and the
  engine test fail with `reduce.reduced_covariance` patched to the identity.
- `INDEXING_THRESHOLDS_VERSION` 1.5 → 1.6, because two runs with identical spec
  notes now answer differently (1.3's precedent). The skill's api index is
  regenerated for it. One rule on `indexing/CLAUDE.md`'s reduction bullet (cap
  318 → 321, logged) and a 1.5.1 release-note section.
- Nothing to prune on arrival: no `### Inherited`, and nothing had touched
  `indexing/` since the filing's `d88f7ff`.

*Measured* (macOS arm64, Darwin 25.6, `[dev]` venv, py3.12, 10 cores; another
session held the load average near 6 through the runs):
- The probe wrapped `engines._dedup_groups` and ran the written test and a
  one-frame copy on the same candidates. The copy matched the source on all
  272 calls.
- **Acceptance corpus**, old behaviour returned: 173 dedup calls, 1 265 301 χ²
  tests, 973 683 (77 %) in a non-identity frame, groups changed in 45 calls. At
  the consensus merge: LaB6 200 → 139 groups, fluorite −56, hl2 −7, the
  three-phase mixture −3, corundum with its template −1, FAP +2, brucite +2.
  Mostly merges of c < a cells: a LaB6 hexagonal pair 0.075 % apart in c
  scored χ² 97 written and 5.8 in one frame.
- **End to end** (each run's final consensus input captured, then replayed
  through validation, ambiguity and the gate): 44 passed on the old tree and
  on the fixed one (12:00 and 14:13 wall). No grade multiset changed and
  nothing at rank 1 or 2 moved. Low-graded candidates at rank 3 and below
  reorder on LaB6 (8 rows), fluorite (5), the mixture (5), hl2 (9) and FAP
  (10). FAP's ranks 3-4 lose dichotomy as a finder: the written test had
  merged (9.3795, 6.9038) with a dichotomy cell 0.09 % away in c.
- **Bethanechol manual**, old run under the probe, new run on the fixed tree:
  99 dedup calls, 3 908 560 χ² tests, 98 % in a non-identity frame, groups
  changed in all 99, and the pooled 1800 lost 165 groups. Score −2 → −3: Db's
  truth goes from rank 1 to rank 2 (score 0). The same move appears on
  identical harvests, so the fix made it and the clock did not. The new
  rank-1 cell (15.106, 9.430, 6.639, β 119.47°) was found by svd, and by
  trial_error in an oblique setting (c 13.174 Å, β 154.07°). Their χ² were
  61.9 and 123.3 written, 6.9 and 10.6 in one frame. Agreed now, it joins the
  corroborated tier and wins the panel there. Every candidate is `low` and
  nothing is promoted in either run, and every set's search is cut by its
  budget in both. Top cells also change on Aa, Ba, Cb and Da, none a truth;
  only Ba's change appears on identical harvests.
- **Units**, WP-1509's harness rebuilt (registry recorders, `index_pattern`
  once, dichotomy replayed at 1e5 s on one BLAS thread), written against fixed
  on the same captured inputs: brucite hexagonal `2b9bc538` → `40752146`
  (first differing pool rank 9 of 60), trigonal `e2117cb2` → `867bb1f5` (4);
  corundum hexagonal `3190bee2` → `f6b582ba` (16), trigonal `2d3b0c80` →
  `3e5ac067` (14), tetragonal `8a5fd6cd` unchanged; synthetic monoclinic
  through `index_pattern` `a9f00c79` → `57a6a9e3`, and from `spec_for`
  directly `62582f65` → `30473892` (10 candidates → 5). Unit wall time was
  equal within 1 % either way (corundum hexagonal 264.1 and 262.0 s, run in
  parallel).
- **Sign snap**: 0 of 7959 candidates pooled across the four captured runs
  sit in the zone, so the consensus-level numbers above hold under the flip.
  The engines' raw harvests were not captured.
- **Fast selection**, final tree: 6712 passed, 152 skipped (6864), 4 more than
  the run before the snap-zone test, 10 added cases in all.
  `tests.added_test_times`, one run on this Mac: 0.13 s over the 6 added
  functions, 0.12 s of it the hypothesis test.
- **Final tree** (after the review and the sign flip; `main` had not moved, so
  this is the merged tree): acceptance 44 passed in 12:07 wall. Bethanechol
  manual, run alone, scores −3 with every set's rank as in the fixed-tree run
  above (Bb, E and F at rank 1, Db at 2), 75-93 s a set.

*Gotchas.*
- **A replay digest belongs to a platform.** It hashes the cells' bits, and
  not one of 1509's six Linux x86-64 digests reproduced on this Mac's unchanged
  path. Pushed to WP-1519 and WP-1520.
- Context's trap that corundum hexagonal and trigonal "should not move" was
  wrong. Their truths' frames are the identity, but their pools carry wrong
  cells with c < a, and those move from pool rank 14-16. Noted in place.
- Context's one-frame χ² for the false merge do not reproduce. With σ_E =
  1e-4·E as stated, the one-frame χ² equals the own-frame χ², 4.5e5 to 7.7e6.
  The same 1:4:4:25 ratios appear with σ_E ∝ √(AC), so the filing's scratch
  scaled E some other way. The written numbers reproduce exactly, and the
  verdicts stand. Noted in place.
- The written test, for any later comparison, is `reduce.reduced_covariance`
  patched to the identity.

*Review.* `/code-review high --fix` reported eight. It fixed four without
changing an answer (3000 random triclinic reductions give the same maps).
`reduced_af` builds no map again (24.0 µs, against 39.8 µs through
`reduction`), `same_lattice` builds none without covariances, the map cache
holds 4096 (840 distinct triplets in 3000 triclinic reductions), and the
triplet has one reader. Its correctness finding, the sign snap, is fixed
above with a test its property test could not reach. Declined two: a
frame-checking `equal_reduced` would change a public API beyond this WP, and
repeating the covariance product per copy costs under 1 % of a pass.

*Not generalised, deliberately.* No other χ² in `indexing/` reads a
covariance (`pinv` appears only in `equal_reduced`), and `cov_af`'s other
reader, σ(V), stays in one frame. The covariance-free callers of
`same_lattice` in `priors` and `ambiguity` are untouched, as the WP said.

*Next.* Nothing on this WP. WP-1519 batches the settled test and must stack
the carried covariances (its `### Inherited`). Db's move is the ranking's own
rule applied to correct input: a wrong cell two engines found outranks the
truth within the corroborated tier. It is recorded here and filed nowhere.

- **2026-09-28** — filed while scoping WP-1509's follow-ups: reading dedup's
  χ² path for the batching work showed the frame mismatch, and the two probes
  in Context measured both directions of it.
