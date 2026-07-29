# WP-1025 — Extinction symbol / space-group determination

Milestone: v1.0 · Status: ⬜ not started
Depends on: 1024

## Goal

`determine_extinction_symbol(data, candidate, instrument) -> ExtinctionScreen`
ranks the extinction classes compatible with an indexed lattice, **listing**
the space groups inside each class rather than choosing between them, and
closes the `index → space group → Le Bail → Rietveld` workflow.

## Context

- **The observable is the extinction symbol, not the space group.** Only
  systematic absences are visible in a powder pattern, so space groups sharing
  an extinction class (centrosymmetric/non-centrosymmetric pairs,
  enantiomorphs) produce **identical** diffraction patterns — by construction,
  not for want of data. Therefore `ExtinctionCandidate.space_groups` is a
  `list`, and `EXTINCTION_GROUPS_NOT_SEPARABLE` (info) fires **whenever
  `len > 1`**, not only when the data are weak. That is a statement about the
  physics, and it is the cleanest instance in the package of "never a confident
  wrong singleton".
- **Derive the classes; do not transcribe IT A Table 3.2.** Enumerate every
  gemmi space group whose crystal system and centring match the candidate
  lattice, compute `ops.systematic_absences(hkl)` over the enumerated hkl set
  in range, and **group by identical absence set**. Same "derive from the
  operators, no case table" discipline as `wyckoff._compatible_lattice` and
  `stephens.strain_basis`, and it is automatically correct in non-standard
  settings, which a transcribed table is not.
- **Screen per class**: `generate_reflections(representative_sg, cell, λ, …)`
  (which already does absence filtering and Laue merging) →
  `structure_from_candidate(candidate, space_group=representative_sg)` →
  `refine(data, structure, instrument, mode="lebail", plan="profile_only",
  history=False)`. **Pass `history=False` explicitly**: `refine()` defaults it
  off but `Refinement()` defaults it on, and a 12-class screen must not build
  12 trees.
- **Score by nested model comparison, not by lowest Rwp.** A class with fewer
  absences has more reflections and always fits at least as well, so Rwp alone
  ranks the least-constrained class first, every time. Use
  `report.layer2.delta_bic(chi2_restricted, chi2_full, n_points, n_added)` and
  `hamilton_justified(...)` — **imported, not reimplemented** — with `n_added`
  the difference in reflection count and the *more*-absent class as the
  restricted model. This is the same statistical device WP-1024's FoM panel
  needs for the same reason, and the same one Layer 2 uses before adding
  parameters.
- **Direct absence evidence refutes, where a fit only ranks.** For each
  reflection a class forbids but a lower-symmetry class allows, read the
  intensity at that position from (a) the peak list and (b) the Le Bail
  intensity extracted under the permissive class. A class is **refuted** when a
  forbidden position carries I > 3σ that is *not* explained by overlap with an
  allowed reflection — and the overlap test reuses `_overlap_groups`' FWHM
  criterion, so "overlapped" still means one thing. Report the refuting hkl
  explicitly; a refutation the user cannot check is not evidence.
- Markvardsen, David, Johnson & Shankland (2001) is the Bayesian version of
  this logic and is cited as the method's reference; its full posterior is a
  **v2 fence**, ΔBIC/Hamilton is the v1.0 form. **Verify that citation from the
  journal before it enters a docstring or ATTRIBUTION.md** — it is the one
  reference in this milestone not confirmed by a supplied source.
- **Test file naming**: use `tests/test_extinction_symbol.py`.
  `tests/test_extinction.py` already exists and is *secondary extinction*
  (WP-0506) — an unrelated physical effect that happens to share the word.

### Inherited

From **WP-1024**: `structure_from_candidate` and its two footguns (dummy atom
required by `Phase._nonempty`; `space_group=None` means the absence-free
lattice group). This WP is where a *real* space group finally replaces that
default, so it is also where the docstring should point next.

From **WP-1020**: `CellCandidate.lattice_group` is the absence-free group used
for validation — the screen's starting point, and the "no extinction
conditions" reference model in the nested comparison.

## Non-goals

- No structure solution, no |F| extraction for phasing — the screen ends at a
  ranked list of classes.
- No Bayesian posterior (v2 fence, see Context).
- No choice *within* a class. If a caller needs one group, that is their
  chemistry knowledge, not this data — and the diagnostic says so.

## Tasks

- [ ] `indexing/extinction.py`: enumerate compatible groups from gemmi, compute
      absence sets, group into classes by identical absences, pick a
      representative and a class label from the shared conditions.
- [ ] Per-class Le Bail screen (`history=False`), ΔBIC/Hamilton scoring
      imported from `report.layer2`.
- [ ] Forbidden-position intensity evidence with the `_overlap_groups` overlap
      check; `refuted` / `refuted_reason` with the refuting hkl.
- [ ] `ExtinctionCandidate`, `ExtinctionScreen` in `schemas/indexing.py`;
      `determine_extinction_symbol` public entry + `pxrdref/__init__.py`
      export.
- [ ] Diagnostics: `EXTINCTION_GROUPS_NOT_SEPARABLE` (always, when >1 group),
      `EXTINCTION_SYMBOL_AMBIGUOUS`, `EXTINCTION_FORBIDDEN_INTENSITY`; rows in
      `docs/AGENT_PROTOCOL.md` §6/§7.
- [ ] `tests/test_extinction_symbol.py`: fluorapatite (`FAP.XRA`) returns the
      `P6₃--` class with its compatible groups **listed, not chosen**; NAC
      (`11BM_NAC.fxye`) returns an I-centred class; a synthetic screw-axis
      pattern is separated from its screw-free partner; and a class whose
      forbidden position carries injected intensity comes back `refuted` with
      the hkl named.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extinction_symbol.py -q
.venv/bin/python -m ruff check src tests examples
```

Criterion: on FAP the correct extinction class ranks first and
`EXTINCTION_GROUPS_NOT_SEPARABLE` names every group it contains; on the
synthetic screw-axis pattern the screw-free class is refuted with its
forbidden hkl reported; and no test asserts a single space group where the
powder data cannot support one.

## References

- Altomare, A. *et al.* (2004). *J. Appl. Cryst.* **37**, 957-966; (2005)
  **38**, 760-767 — probabilistic space-group determination from powder data.
- Markvardsen, A. J., David, W. I. F., Johnson, J. C. & Shankland, K. (2001).
  *Acta Cryst.* **A57**, 47 — the Bayesian formulation. **Confirm before
  citing in code.**
- *International Tables for Crystallography* Vol. A, Table 3.2 — the
  extinction-symbol list this WP derives rather than transcribes.
- `report/layer2.py` — `delta_bic`, `hamilton_justified`.

## Handover log

- **2026-07-29** — created from the indexing plan.
