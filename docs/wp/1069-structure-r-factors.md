# WP-1069 — Structure agreement indices: R_Bragg and R_F, and the stated esd method

Milestone: v1.0 · Status: ✅ 2026-08-15 — R_Bragg/R_F per phase from an
evaluate-only structure-model partition, the two core-dictionary CIF tags on
each phase's own block, and the esd method stated in full
Depends on: — (recommended **before 1003**: adds public statistics fields and
CIF tags the freeze should cover; the grounds are in 1003's Inherited)

## Goal

A converged Rietveld result carries the structure-sensitive agreement indices
R_Bragg (eq 14) and R_F (eq 13) per phase, computed by observed-intensity
partitioning; the CIF export writes them under the dictionary tags and states
the esd method completely. Gaps 1 and 8 of the McCusker audit
(`../milestones/v1.0.md` § Appendix — the McCusker 1999 compliance audit).

## Context

- **The gap.** Every published Rietveld refinement quotes at least one
  structure R; Young, Prince & Sparks (1982) require them; the pdCIF export
  has no structure-R tag at all. Nothing in the package computes one —
  `grep -ri r_bragg src` is empty.
- **The definitions** (McCusker et al. 1999, §11; the paper is at
  `~/zotero-linker/derived/YWSBLSIS/`):
  - eq (13): R_F = Σ|F(obs) − F(calc)| / Σ|F(obs)| over hkl;
  - eq (14): R_B = Σ|I(obs) − I(calc)| / Σ|I(obs)|, I = m·F² (m the
    multiplicity). A weighted equivalent exists (Cox & Papoular 1996) —
    docstring note, not scope.
- **"obs" is a partition, not a measurement.** §6: the intensities of
  overlapped reflections are distributed in proportion to the calculated ones
  — "the same procedure is used to calculate the R_F values". That procedure
  already exists: `CompiledModel.lebail_update` (`model/forward.py:871`) is
  observed-intensity partitioning. One evaluate-only partition pass at the
  converged values yields I(obs) per reflection; nothing enters the residual,
  so frozen-per-stage discreteness is untouched.
- **Both indices are model-biased and the docstring says so** — the paper
  does ("this is, of course, biased towards the structural model, but it
  gives an indication of the reliability of the structure").
- **Mode semantics.** In Le Bail mode the partition *is* the fit, so R_B is
  circular and must be absent-for-cause (`None`), the `lebail_gap` precedent
  (Rietveld-only, `report/schemas.py`). Pawley: the intensities are refined
  θ, same circularity, same `None`.
- **Emission lines.** The partition is per (line, reflection); the paper's
  sums are over hkl. Aggregate every line's window contribution into its hkl
  orbit before summing — the `RefinementResult.ticks` lesson (all lines, not
  just the primary) one rank down.
- **Where it lands.** Compute at fit close in `refine.py` (the
  identifiability precedent — it needs the compiled model and the converged
  values); store as additive defaulted fields, per phase (other codes quote
  per-phase R_B, and QPA users read it that way). `Statistics`
  (`schemas/results.py:22`) is per-fit, so the per-phase list needs its own
  carrier field on the result or on the per-phase results — pick one and say
  why. Additive defaulted fields, no `SCHEMA_VERSION` bump (the events
  precedent); the freeze ratifies.
- **The esd method statement (gap 8).** §10: "In any publication, the method
  used to calculate the e.s.d.'s should be stated."
  `_pd_proc_ls_special_details` (`io/exporters.py:282-286`) names the
  Bérar-Lelann inflation factor but not the base estimator. Add the sentence:
  esds are √diag(χ²_red·(JᵀJ)⁻¹), then multiplied by the stated factor.
- **CIF tags are looked up, never remembered.** The profile-R tags are at
  `io/exporters.py:276-281`; verify the structure-R tag names against the
  pdCIF dictionary before writing them (candidates `_refine_ls_R_I_factor`,
  `_refine_ls_R_Fsqd_factor`, `_refine_ls_R_factor_all` — check, do not
  trust this list).
- Invariant to honour: a new number ships with a *measured* record, never an
  Rwp comparison as its evidence. Here the evidence is the acceptance
  protocols: quote R_B/R_F on 11-BM NAC, SRM 660c and FAP in the handover;
  the FAP `.EXP` is GSAS's converged fit — if it quotes an R_B, compare
  within the WP-1001 tolerance discipline (cross-code consistency, not
  truth).

## Non-goals

- Difference Fourier maps (v2+ fence — ROADMAP § v2+).
- Any gate or threshold on the values: they are reported, not judged.
- The Cox-Papoular weighted variant: docstring pointer only.
- Reworking `lebail_update` itself; the pass reuses it evaluate-only.

## Tasks

- [x] Partition pass at fit close: per-phase R_B and R_F on the result
      (additive defaulted), Rietveld mode only, `None` absent-for-cause in
      Le Bail/Pawley, docstring stating the model bias and citing eqs 13/14.
- [x] Emission-line aggregation into hkl orbits, pinned by a doublet test
      (Cu Kα1,2: R_B must not double-count the Kα2 windows).
- [x] CIF export: structure-R tags verified against the pdCIF dictionary,
      plus the completed esd-method sentence.
- [x] Surface where statistics already render (textdoc, report summary),
      and the `AGENT_PROTOCOL.md` row.
- [x] Measured values on the three acceptance protocols in the handover;
      FAP compared against the `.EXP` if it quotes one.
- [x] Tests (unit + the mode-semantics pins) + obs/calc/diff PNGs to
      `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_structure_r_factors.py tests/test_exporters.py -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- McCusker, Von Dreele, Cox, Louër & Scardi (1999), *J. Appl. Cryst.* **32**,
  36–50, §6, §10, §11 eqs (13)/(14). Local copy above.
- Cox & Papoular (1996), *Mater. Sci. Forum* **228-231**, 233 (weighted R_B).
- Young, Prince & Sparks (1982), *J. Appl. Cryst.* **15**, 357.
- Toby (2006), *Powder Diffraction* **21**, 67 (the naming conventions the
  statistics already follow).

## Handover log

- **2026-08-15** — **closed ✅.** No `### Inherited` on arrival, so nothing to
  prune. All six tasks landed; ten commits.

  **Done.** `CompiledModel.structure_intensity_partition` (evaluate-only, at
  fit close), `optimize.statistics.structure_r_factors` (eqs 13/14),
  `RefinementResult.phase_agreement: list[PhaseAgreement]` and the same field
  on `HistogramResult` (a joint fit's partition is of *one* pattern's counts,
  so per histogram, like its QPA and absorption record — additive defaulted,
  no `SCHEMA_VERSION` bump, the events precedent). CIF export, the manual's
  statistics chapter, `AGENT_PROTOCOL.md` § 4 step 9, one root CLAUDE.md
  clause. `agent.refine_json` needed no change: `AgentSuccess.result` *is* the
  `RefinementResult`, so the rows serialize already.

  **Task 4 named two surfaces that turned out not to exist, and went to three
  others instead.** `gui/textdoc.py` renders no statistics at all — it is the
  `.rxt` parameter/plan editor, and its whole vocabulary is rows, globs, peaks
  and stages. The FitReport's `summary` is a *judging* surface, and this WP's
  own non-goal forbids a gate or threshold on these values, so a passive number
  there would have been the first sentence in that string that decided nothing.
  What the item was really asking for — that a reader meet the numbers where
  they read the others — went to the manual's § Fit statistics (beside the
  `Statistics` table), `AGENT_PROTOCOL.md` § 4 as step 9 of the judging order,
  and the CIF. If a later WP gives the FitReport a structure-R statement, it
  should arrive with a threshold and a measured reason for it, not as a field.

  **The design decision, and why.** Writing the calculated counts of
  reflection k as W_k = Σ_l Σ_i I_lk·Ω_lk,i and its observed share as
  O_k = Σ_l Σ_i [I_lk·Ω_lk,i / y_bragg,i]·net_i, the two differ **only** by the
  obs/calc ratio, so I(obs) = m·|F|²·O_k/W_k. That is not an optimisation of
  the obvious form (reconstruct the correction product per (line, reflection)
  and divide it out): the obvious form divides by |F|² = 0 on a systematically
  absent reflection, and it re-derives factors `phase_peaks` already applied.
  Scale, preferred orientation, Lp, extinction, absorption, roughness and the
  line weights are in both W and O and cancel, which is what makes the returned
  pair the paper's I_hkl = m·F² rather than a count. **A new correction
  therefore costs the R factors nothing** — but a change to
  `structure_factors_squared` changes their units.

  **CIF tags, looked up not remembered.** IUCr's HTML dictionary browser 403s
  to both curl and WebFetch; `gh api repos/COMCIFS/cif_core/contents/cif_core.dic`
  works. `_refine_ls_R_I_factor` — its own definition says "most often
  calculated in Rietveld refinements of powder data, where it is referred to as
  R~B~ or R~Bragg~". `_refine_ls_R_factor_all` — "the conventional R factor",
  Σ|F(meas)−F(calc)|/Σ|F(meas)|, which is eq (13) exactly; `_all` not `_gt`
  because there is no intensity threshold to point a
  `_reflns_threshold_expression` at. Both are core-dictionary `_refine_ls`
  items scoped to the *structure*, so they go on each phase's own block, not on
  block 0 beside the profile R factors. `_refine_ls_number_reflns` carries n.
  The powder dictionary has no Bragg-R tag at all (`save_pd_proc_ls.*` is
  background/diffractogram/peak-cutoff/pref-orient/prof-R/prof-wR/profile/
  special-details, and nothing else).

  **Measured, `[dev]` venv, macOS arm64** (Rwp, then per phase R_B / R_F / n):

  | protocol | Rwp | phase | R_B | R_F | n |
  |---|---|---|---|---|---|
  | SRM 660c, NIST protocol | 0.0866 | LaB6 | 0.0336 | 0.0165 | 30 |
  | FAP, GSAS-II tutorial protocol | 0.0973 | fluorapatite | 0.0516 | 0.0326 | 329 |
  | 11-BM NAC, Le Bail pass | 0.1457 | — | *absent for cause* | | |
  | 11-BM NAC + CaF₂, two-phase Rietveld | 0.0931 | 1000236 | 0.0518 | 0.0308 | 129 |
  | | | CaF2 | 0.3845 | 0.1793 | 11 |

  R_F ≈ R_B/2 throughout, which is what taking the root of a relative
  intensity error does; SRM 660c's `a` = 4.156895 Å is unmoved (the partition
  writes nothing — pinned by a test).

  **The FAP `.EXP` comparison could not be made, and the reason is the point.**
  It carries `HST 1 R-FAC 654 0.06830 7.393183E+06` beside
  `HST 1 NREF 660 0.8499` and `HST 1 RPOWD 0.1005 0.0766 5750`. **654 counts
  (emission line, reflection) pairs, not hkl.** Measured three ways: our
  compiled model has 329 hkl orbits and 658 (line, reflection) rows, within
  0.6 % of GSAS's 654/660; generating to GSAS's own quoted d_min of 0.8499 Å
  gives **326** for one line, a factor 2.0 out; and summing both lines over
  GSAS's 15–129.98° range gives 646. So GSAS sums over a doubled list in which
  each hkl appears twice at different weights, while eqs 13/14 sum over hkl.
  On top of that the file does not say whether 0.06830 is an R(F), an R(F²) or
  an R_B — `BIGFO 0.137403E+06` against the record's own `7.393183E+06`
  suggests the third field is Σ|Fo| rather than ΣFo², but that is an inference
  and no GSAS manual is in the local corpus. Under the WP-1001 discipline
  (adopting a protocol, not just its numbers) this is a comparison that cannot
  be made rather than one that failed, so nothing is asserted against it.

  **One finding worth carrying: R_B is unweighted, and a trace phase's value is
  not comparable with the major phase's.** CaF₂ at 1.35 wt % reads 0.385
  against NAC's 0.052, and the *whole* of it is four reflections at
  I(obs)/I(calc) ≈ 2.2 — (311), (331), (422), (511)/(333) — each under a strong
  NAC peak with a large positive Δ/σ. Two mechanisms, neither separable here:
  eq (14) has no w, so a reflection the weighted fit barely constrains counts
  as much as one that dominates it; and the partition hands out the counts the
  *major* phase failed to describe. Σ I(obs)/Σ I(calc) is 1.5707 for CaF₂ and
  0.9924 for NAC, while CaF₂'s *median* per-reflection ratio is 1.0017 — a
  four-reflection tail, not a uniform offset. That is what the Cox-Papoular
  weighted variant answers; it stays a docstring pointer (non-goal). The rule
  is in the manual and in `structure_r_factors`' docstring; the numbers are
  here.

  **Counts.** `-m "not slow"`, `[dev]` venv, macOS: **2285 passed, 108
  skipped**, against **2272 passed, 108 skipped** with
  `--ignore=tests/test_structure_r_factors.py` — +13 passed, +0 skipped,
  exactly the thirteen new tests, and no other module's count moved. Full
  suite on the same venv and platform: **2392 passed, 117 skipped**, ~23 min.
  The partition costs **1.2× a forward
  evaluate** (23 ms against 19 ms on FAP's 329 reflections × 2 lines), 0.47 %
  of that fit — it runs once per `_build_result`, which is once per `fit`,
  per `run_stage`, per `replay`, and per stage boundary under
  `stage_reports=True`, where the `lebail_gap` beside it already costs more.

  **Gotchas for whoever is next.** (a) `lebail_gap` flips the model to Le Bail
  mode and seeds *flat*; this partition must **not** — its shares come from the
  structural model, which is the whole difference between "how well does the
  structure explain the intensities" and "what is the best profile-only fit".
  Two neighbouring methods, opposite seeds. (b) The tests quote no remembered
  number: the fixed point (model's own noiseless pattern → I(obs) = I(calc) to
  fp) and the uniform-scale closed form (R_B = 0.2, R_F = √1.2 − 1 at a 1.2×
  scale) are exact. Mutation-checked: making the Kα2 window contribute to O but
  not W moves the doublet fixed point to R_B = 0.318 while every single-line
  row stays green. (c) The March-Dollase row of the fixed-point test is not
  decoration — P is folded into the intensity *before* every other correction,
  and only an r ≠ 1 run would see it reaching one side of the ratio and not the
  other. (d) `tests/output/wp1069_nac_two_phase.png` is not written by the
  suite; the committed test PNG is `structure_r_lab6.png`.

- **2026-08-15** — created from the McCusker audit (WP-1068); gaps 1 and 8.
