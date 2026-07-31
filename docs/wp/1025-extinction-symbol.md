# WP-1025 — Extinction symbol / space-group determination

Milestone: v1.0 · Status: ✅ 2026-07-30
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

**From WP-1024 (landed 2026-07-30) — the extinction evidence already exists and is
already being counted, but against a different question.** Three things land in
your lap:

- **`LeBailValidation.predicted_but_absent_two_theta` is an extinction list in all
  but name.** `workflow.absent_reflections` integrates `y_obs − y_background` over
  ±½ FWHM at every predicted position and reports the ones below 3σ — measured, 0
  of 28 for a certified cubic cell and 117 of 153 for a doubled one. That is the
  *lattice*-level version of your question, computed against the **fitted**
  background (which is why it beats asking the peak list). Reuse the function
  rather than writing a second absence test: two absence detectors that disagree
  would be worse than either.
- **Its documented failure mode is exactly your subject matter**, so read
  `ABSENT_SIGMA`'s docstring before trusting a count. A reflection can be absent
  because the space group forbids it (yours), because the lattice is wrong
  (WP-1024's), or because it is too weak to see (nobody's) — and the detector
  cannot tell them apart. WP-1024 gates on "any absent reflection refutes the
  candidate", which is only sound *because* it validates the absence-free lattice
  group: once you supply a group with reflection conditions, that gate would
  excuse a phantom as an extinction, which is precisely how an oversized cell
  passes. **If you make `structure_from_candidate`'s default a real space group,
  `INDEX_PREDICTED_BUT_ABSENT` stops meaning what it means** — keep the
  lattice-group validation as the gate's input and add yours beside it.
- **A candidate's `INDEX_BRAVAIS_AMBIGUOUS` is a live warning for your screen.**
  `BravaisOpinion.methods_disagree` fires on genuine pseudosymmetry, and the
  reported system is the *conservative* one. The nested comparison should start
  from `bravais.system`, not `bravais.system_loosest`.

From **WP-1020**: `CellCandidate.lattice_group` is the absence-free group used
for validation — the screen's starting point, and the "no extinction
conditions" reference model in the nested comparison.

From **WP-1019** (2026-07-30): `quality.volume_envelope(d_n, n, system, *,
centring_multiplicity=None)` defaults to the **worst case** centring each system
allows, because centring is part of the answer this WP produces. Once an
extinction symbol is determined, pass the real multiplicity (F 4, R 3, I/A/B/C 2,
P 1) to tighten the volume bound — that is a concrete, already-wired use for this
WP's output, and it is why the parameter exists. The default was not a guess: with
no centring factor the envelope *excluded* corundum's true volume, 125 Å³ against
255, because R-centring extinguishes two thirds of hkl.

## Non-goals

- No structure solution, no |F| extraction for phasing — the screen ends at a
  ranked list of classes.
- No Bayesian posterior (v2 fence, see Context).
- No choice *within* a class. If a caller needs one group, that is their
  chemistry knowledge, not this data — and the diagnostic says so.

## Tasks

- [x] `indexing/extinction.py`: enumerate compatible groups from gemmi, compute
      absence sets, group into classes by identical absences, pick a
      representative and a class label from the shared conditions.
- [x] Per-class Le Bail screen (`history=False`), ΔBIC/Hamilton scoring
      imported from `report.layer2`.
- [x] Forbidden-position intensity evidence with the `_overlap_groups` overlap
      check; `refuted` / `refuted_reason` with the refuting hkl. **The overlap
      check answers a different question from the one the plan gave it** — see
      the handover log.
- [x] `ExtinctionCandidate`, `ExtinctionScreen` in `schemas/indexing.py`;
      `determine_extinction_symbol` public entry + `pxrdref/__init__.py`
      export.
- [x] Diagnostics: `EXTINCTION_GROUPS_NOT_SEPARABLE` (always, when >1 group),
      `EXTINCTION_SYMBOL_AMBIGUOUS`, `EXTINCTION_FORBIDDEN_INTENSITY` (plus
      `EXTINCTION_CONDITIONS_PARTIAL`); rows in `docs/AGENT_PROTOCOL.md`
      §6/§7e.
- [x] `tests/test_extinction_symbol.py`: fluorapatite (`FAP.XRA`) returns the
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
- Markvardsen, A. J., David, W. I. F., **Johnston**, J. C. & Shankland, K.
  (2001). *Acta Cryst.* **A57**, 47–54, doi:10.1107/S0108767300012174 — the
  Bayesian formulation. **Confirmed 2026-07-30** against the IUCr record before
  it entered a docstring, and the check earned its place: the third author is
  Johnston, not Johnson as this WP had it. The paper's own unit of answer is the
  *extinction symbol*, which is the corroboration that mattered.
- *International Tables for Crystallography* Vol. A, Table 3.2 — the
  extinction-symbol list this WP derives rather than transcribes.
- `report/layer2.py` — `delta_bic`, `hamilton_justified`.

## Measured acceptance (2026-07-30)

```
.venv/bin/python -m pytest tests/test_extinction_symbol.py -q   →  27 passed, 8.6 s
.venv/bin/python -m ruff check src tests examples               →  clean
```

| specimen | leading class | its space groups | evidence |
|---|---|---|---|
| FAP (`FAP.XRA`, real lab, truth P 6₃/m) | `P 63 - -` | P 6₃, P 6₃/m, P 6₃22 | ΔBIC −21.8; the six rival classes all refuted by named hkl; 2.2 s over 7 classes |
| NAC (`11BM_NAC.fxye`, real synchrotron, truth I 2₁3) | `I - - -` | 6 groups incl. I 2₁3 | the screws are invisible *in principle* (I-centring already extinguishes h00, h odd); 4 rivals refuted; 2.0 s |
| synthetic P 2₁/c | `P 1 21/c 1` | P 2₁/c alone | ΔBIC 24 clear of its screw-free partner `P 1 c 1`, while **Rwp differs by 1e-5** |
| the same, with a peak injected at 030 | `P 1 c 1` | P c, P 2/c | `P 1 21/c 1` refuted, naming (0,3,0) |

## Handover log

- **2026-07-29** — created from the indexing plan.
- **2026-07-30** — **landed.** `determine_extinction_symbol(data, candidate,
  instrument) → ExtinctionScreen` is exported from `pxrdref`, tested in
  `tests/test_extinction_symbol.py` (27 tests, 8.6 s, 4 of them `slow`), and
  documented in AGENT_PROTOCOL §7e. Done / in flight / next / gotchas:

  **Done.** Everything on the checklist. The shape is `IndexingResult`'s one rank
  down — no `.symbol` on the screen, `best_or_none()` returns a *class*, and the
  class carries a `space_groups` **list** — so a single space group is unspellable
  in this API, which is the point: it is the one place in the package where the
  singleton is not merely unsupported but *unmeasurable*.

  **Three things the plan got wrong, all found by measurement.**

  1. **The absence test's null model.** The plan (and WP-1024's inherited note)
     said to reuse `absent_reflections` against the fitted background. That
     refutes the *true* class on real data: FAP's forbidden 003 sits **0.89
     FWHM** from the allowed (3,-1,2), ten times stronger, whose tail fills the
     ±½ FWHM window to **+27.6 σ**. Against the class's own `y_calc` —
     background *plus every reflection the class still allows* — the same window
     reads **−3.9 σ**. The function is still reused, called with `y_calc` in the
     `y_background` slot, so there is one detector with one window and one
     threshold; where nothing is predicted nearby the two are identical. The
     general form: **a detector's null model has to contain the competing
     hypothesis's own predictions**, and WP-1024's did because a phantom
     reflection sits in a gap.
  2. **`_overlap_groups` answers a different question from the one the plan gave
     it.** Its criterion (½ the mean FWHM) is "can least squares apportion this
     intensity", which is right for `n_added` — a forbidden line coinciding with
     an allowed one never was an independently determined intensity — and far too
     tight for "is this window contaminated". Both questions are now asked, each
     by the thing that answers it.
  3. **Refute-before-fitting was the wrong order** and had to go: with the null
     model above, refutation needs the class's own fit. It costs nothing —
     ~0.1 s per class after a ~2 s shared profile fit, so seven classes are 2.2 s
     and an orthorhombic-P screen's 71 would be ~10 s.

  **The acceptance criterion above needed re-reading, and the reason is worth
  keeping.** It asks for "the screw-free class refuted with its forbidden hkl
  reported" on the synthetic pattern. That cannot happen and should not:
  **refutation is one-sided by construction.** An extinction symbol asserts
  absences and nothing else, so intensity at a position it forbids contradicts
  it, while a class claiming *too few* absences asserts nothing the data can
  falsify — `P 1 c 1` is a perfectly true statement about a P 2₁/c pattern,
  merely not the most specific true one. Preferring the specific answer is what
  the nested comparison is for, and the criterion is met from the other side
  instead: inject one peak at 030 and `P 1 21/c 1` comes back refuted **naming
  (0,3,0)** while `P 1 c 1`, which predicts a line there, is untouched and takes
  first place. Both directions are tested.

  **Two design decisions worth not re-litigating.** `n_added` counts only
  *testable* forbidden lines (covered by data, separable from allowed ones);
  without that a class whose absences all hide under neighbours wins on parsimony
  alone, at ΔBIC = −n·ln N with no measurement behind it. And the enumeration is
  by **lattice**, not crystal system: a hexagonal metric carries the trigonal-P
  groups, which own classes (`P 3 c 1`, `P 3 1 c`) no hexagonal group reproduces.

  **Gotchas for anyone touching this.** The class representative is chosen by
  largest *Laue* group so the reflection lists are nested — and computing that
  needs the inversion gemmi keeps out of `sym_ops`, or `P 4 3 2` outranks
  `P m -3 m` and the reference model silently stops being the lattice group. The
  absence of a *line* is asked of the whole orbit, not its representative
  (`P a -3` extinguishes 012 but not 021, and they share one m-3m orbit at one
  2θ). And the derived reflection conditions are a *convenience*: the screen runs
  on the absence set, and `conditions_complete` is False for 1 of gemmi's 550
  settings.

  **Next.** Nothing here is blocking. The two open questions are for other WPs
  and have been written into their `### Inherited` sections: whether the FAP/NAC
  extinction claims should become rows in `docs/VALIDATION.md` (1026 — they are
  real-data assertions that live outside `test_acceptance_*.py`, so the matrix
  guard does not see them), and whether the agent JSON surface grows a fifth task
  arm for the screen (1003, before the freeze).
