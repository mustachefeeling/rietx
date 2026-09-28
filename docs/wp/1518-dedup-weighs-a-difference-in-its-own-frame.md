# WP-1518 — the dedup χ² test weighs a difference in the frame it was taken in

Milestone: unscheduled · Status: 🔄 2026-09-28 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: — (1020 built the test; 1509 built the caches it reads)
Priority: P2 2026-09-28 — a silent wrong answer on the path consensus builds agreement from, shown on synthetic covariances and not yet on a real harvest; P1 if task 1 finds a corpus grade that moves

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
  identity).
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

- **2026-09-28** — filed while scoping WP-1509's follow-ups: reading dedup's
  χ² path for the batching work showed the frame mismatch, and the two probes
  in Context measured both directions of it.
