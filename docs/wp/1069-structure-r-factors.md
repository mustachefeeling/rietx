# WP-1069 — Structure agreement indices: R_Bragg and R_F, and the stated esd method

Milestone: v1.0 · Status: ⬜
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

- [ ] Partition pass at fit close: per-phase R_B and R_F on the result
      (additive defaulted), Rietveld mode only, `None` absent-for-cause in
      Le Bail/Pawley, docstring stating the model bias and citing eqs 13/14.
- [ ] Emission-line aggregation into hkl orbits, pinned by a doublet test
      (Cu Kα1,2: R_B must not double-count the Kα2 windows).
- [ ] CIF export: structure-R tags verified against the pdCIF dictionary,
      plus the completed esd-method sentence.
- [ ] Surface where statistics already render (textdoc, report summary),
      and the `AGENT_PROTOCOL.md` row.
- [ ] Measured values on the three acceptance protocols in the handover;
      FAP compared against the `.EXP` if it quotes one.
- [ ] Tests (unit + the mode-semantics pins) + obs/calc/diff PNGs to
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

- **2026-08-15** — created from the McCusker audit (WP-1068); gaps 1 and 8.
