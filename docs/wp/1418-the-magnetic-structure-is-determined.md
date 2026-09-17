# WP-1418 — the magnetic structure is determined, not only stated

Milestone: unscheduled · Status: ⬜
Depends on: PR #290's `crystallography.magnetic` (landed 2026-09-10);
1326 (the k candidates) for the k-search rung; 1327 (the moment, the hold)
for the determination verb. The irrep and isotropy rungs depend on nothing
unlanded.

## Goal

A user with a neutron pattern whose nuclear model leaves intensity
unexplained gets, in order: the candidate propagation vectors, the candidate
magnetic space groups compatible with each, a trial refinement per candidate
under 1327's hold rules, and a ranked list grouped into the classes a powder
average cannot separate, each written out as a magCIF. The stored form stays
1327's operator list. The group theory is computed inside the package from
published algorithms, with spglib's database and spgrep as the oracles.

## Context

Issue #256 (2026-09-03), a design proposal for the rungs after 1326–1329,
with a 60-line check script; issue #257's amendments are folded into the
WPs they touch (1326, 1327, 1328) and not here.

**Why this is a candidate and not a fenced item.** 1327 § Non-goals reads
*"Determining a magnetic structure: representation analysis, k-SUBGROUPSMAG,
ISODISTORT's job. This WP refines a structure the user states."* #256 asks
for that to read as sequencing: the operator list 1327 refines is what the
determination rungs produce. Two facts moved since the fence was written.
`pyproject.toml` pins `spglib>=2.4`, and spglib carries the 1651 magnetic
space groups (UNI/BNS/OG numbers, operations with time reversals, and the
identification of a moment configuration's group; Shinohara, Togo & Tanaka
2023). And the first rung has **landed**: PR #290 (2026-09-10, from the
issue's author) added `crystallography.magnetic.operators`, with
`MagneticOperator`/`MagneticGroup`, `magnetic_group(spec)` and
`database_settings` over spglib's database, `identify()` from a bare
operator list, `MagneticGroup.transformed` via magCIF's
`transform_BNS_Pp_abc`, and `allowed_moment_basis`/`in_span` for the
per-site moment subspace. Its tests build all 1651 groups, round-trip
38 307 operations, identify 1648 of 1651 (three are a spglib database
defect), and assert twenty published moments lie in the *span* of the
derived subspace, never its dimension, with the Rᵀ control on three
hexagonal cases. That is root CLAUDE.md's rule for a symmetry action, kept.

So the maintainer has already accepted the layer. **The decision this WP
carries is whether 1327's non-goal becomes a sequencing statement.** The
triage's recommendation (2026-09-15) is yes, as a candidate the way 1325 is:
the shape is written, no milestone owns it, and it sits behind 1327 for the
verb while the irrep and isotropy rungs could land on their own with no
forward-model contact.

**What was measured.** With spglib 2.7.0 and spgrep 0.7.0 (BSD-3, numpy
only), for Pnma with Mn on 4b (0, 0, ½) at k = 0 the magnetic representation
decomposes into the four inversion-even one-dimensional irreps at
multiplicity 3 each and the four odd ones at 0, Σ n·dim = 12: Bertaut's
LaMnO₃ result, because a moment is axial and the 4b site symmetry contains
−1. A 4c orbit as control gives (1, 2, 2, 1, 1, 2, 2, 1). At k = (0, 0, ½)
the little group is all eight operations and returns two two-dimensional
irreps, each ×3. The group theory needed is about 60 lines over what the
tree depends on, plus tests.

**The rungs**, in the issue's letters (numbers are the maintainer's):

- **M-6 — little group, star, irreps, decomposition, projection.** Rᵀ on k;
  small irreps by induction with the factor system (the projective case at a
  zone-boundary k of a non-symmorphic group is why Kovalev tabulated them);
  CDML labels where k has one; Γ_perm ⊗ Γ_axial (and ⊗ Γ_V for displacements,
  which 1419 consumes) decomposed; basis vectors projected with every row of
  a multi-dimensional irrep and the lattice return-vector phase
  e^{−2πi k·a_g}, Gram–Schmidt reduced, real combinations where an irrep
  pairs with its conjugate. Shows it works: the Pnma check above on real
  data (LaMnO₃, `Magnetic-I`); agreement with spgrep up to a unitary
  intertwiner for all 230 groups at every special k; a published SARAh or
  BasIreps table reproduced; Σ n·dim = 3N.
- **M-7 — isotropy subgroups and the candidate models for (G, k).** Kernel
  and stabilisers of each irrep's order-parameter directions become 1327
  operator lists with irrep label and parent-cell transform; systematic
  absences per candidate (MAGNEXT) as a symmetry-only discriminator;
  **powder-equivalence classes**, candidates whose orbit-averaged |M⊥|²
  agree on every reflection (Shirane 1959 made mechanical). Shows it works:
  the published group of ≥ 10 MAGNDATA parents is in the list with its
  label; Pnma at Γ gives four maximal candidates; Shirane's cubic collinear
  degeneracy comes out as one class.
- **M-8 — the k-search beyond {0, ½}³.** 1326's arm with a pluggable
  candidate generator (issue #257 A1): every special point and line of the
  zone, labelled, then a general-k grid, an incommensurate k admitted as a
  *position* hypothesis and reported as such. Same files as 1326, so after
  it lands.
- **M-9 — the determination verb.** k candidates → M-7 candidates → one
  trial refinement per class under 1327's hold → ranking by ΔBIC at equal
  parameter count (with 1417's caveat on N) and a magnetic-only R over the
  magnetic intensities, plus the null test → a report listing the class, the
  members a powder cannot separate, the irrep, direction and symbol, and a
  magCIF per candidate (1328). Abstains with the reason when classes tie
  (1043's rule; never a confident singleton). Shows it works: LaMnO₃ 50 K
  ranks A-type first of four; Cr₂WO₆ prints the k = 0 sentence and holds at
  150 K.

M-10, mode amplitudes as degrees of freedom, is
[1419](1419-a-child-structure-refined-on-its-mode-amplitudes.md).

**Questions the issue leaves, with the triage's answers.** Irreps from
scratch with spgrep as a dev-only oracle (recommended by the issue and here:
a published algorithm, no runtime dependency, and the strongest test
available; BSD-3 makes either admissible). A UNI/BNS/OG number as an
alternative input: M-5 already does this, and a symbol *string* is refused
by name because spglib exposes numbers only. The internal moment basis: M-5
ships the conversions (`moment_to_cartesian` and back), with a MAGNDATA
round trip as the test (#257 A6). The non-goal reading: this WP.

**What it touches.** New `crystallography/magnetic/{irreps,isotropy}.py` and
tests; manual Part 2 sections with `*Source:*` lines; `ATTRIBUTION.md` rows
for spgrep if it becomes more than a test oracle (PR #290 already added
spglib's). M-8 and M-9 reach `refine.py`'s report arm and `strategy/`, and
the skill's `references/magnetic.md` (the file #287's ruling assigns to the
whole track).

**Datasets.** `Magnetic-I` (LaMnO₃, BT-1, 50 K) and `Magnetic-II` (Cr₂WO₆,
HB-2A, 4 K/150 K) as 1326/1327 name them; `Magnetic-III` (Ba₆Co₆-type
cobaltite, D1B) and `Magnetic-IV` (Pr₀.₅Sr₀.₅MnO₃, 3T2) are the first public
k ≠ 0 commensurate candidates, k to confirm from the tutorial pages before
either is named; `Magnetic-V` (Mn₃O₄, POWGEN) is TOF and stays fenced.
MAGNDATA magCIF entries serve the round-trip and span tests with no pattern.

### Inherited

- **2026-09-17, from [1436](1436-k-is-the-wavevector-everywhere-else.md):
  `k` is free for the propagation vector.** The earlier note here warned that
  `scattering.py`, `structure_factor.py` and `dispersion.py` all spent `k` on
  sinθ/λ, in the same subpackage `crystallography/magnetic/` lives in, and
  asked this WP to spell the propagation vector out rather than add a second
  bare `k`. 1436 has landed: that quantity is `stol` in python and `s` in
  equations throughout, following Waasmaier & Kirfel and the IUCr core
  dictionary, and a tree-wide sweep found no line left pairing a bare `k` with
  sinθ/λ in `src/`, `tests/`, `examples/` or the manual. **So name the
  propagation vector `k` and add no qualifier.** Root CLAUDE.md § Conventions
  carries the rule that keeps it free. The same note is in 1326, 1327, 1328 and 1329.

## Non-goals

- Modulated and incommensurate structures (superspace): issue #258 holds the
  shared design and the v2+ fence holds the item.
- Time-of-flight, polarised neutrons, magnetic X-rays (1327's fences).
- Mode amplitudes as refinable DOFs (1419).
- A magnetic phase as a second phase; 1327's site-attribute shape stands.

## Tasks

- [ ] M-6: irreps and decomposition, spgrep as oracle in the test suite
      only; the Pnma 4b/4c checks and the 230-group intertwiner test.
- [ ] M-7: isotropy subgroups → operator lists, absences, powder-equivalence
      classes; ≥ 10 MAGNDATA parents recover their published group.
- [ ] M-8: 1326's candidate generator made pluggable and the zone's special
      points and lines added, labelled.
- [ ] M-9: the verb, the ranking, the abstention, the magCIF per candidate;
      `capabilities()` feature flag; `help.py` entries.
- [ ] Manual Part 2: the projection operator, the return-vector phase, the
      powder-equivalence criterion, each with a *Source* line; Part 1 chapter
      under the magnetic one.
- [ ] Skill: the rows in `references/magnetic.md` (never the body); the
      1043-style abstention row.
- [ ] Tests, with obs/calc/diff PNGs to `tests/output/` for the M-9 fixtures.

## Acceptance

LaMnO₃ 50 K ranks A-type first of four with the class listed; Cr₂WO₆ 150 K
abstains with the k = 0 sentence; every shipped fixture is bit-identical with
no magnetic model declared.

```sh
.venv/bin/python -m pytest tests/test_magnetic_operators.py tests/test_magnetic_irreps.py tests/test_magnetic_isotropy.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issues #256, #257 (2026-09-03); PR #290 (M-5, landed 2026-09-10).
- Bertaut, E. F. (1968), *Acta Cryst.* A**24**, 217.
- Izyumov, Yu. A., Naish, V. E. & Ozerov, R. P. (1991), *Neutron Diffraction
  of Magnetic Materials*, Kluwer.
- Wills, A. S. (2000), *Physica B* **276–278**, 680 (SARAh).
- Bradley, C. J. & Cracknell, A. P. (1972), *The Mathematical Theory of
  Symmetry in Solids*, Oxford; Neto, N. (1973), *Acta Cryst.* A**29**, 464;
  Stokes, H. T., Campbell, B. J. & Cordes, R. (2013), *Acta Cryst.* A**69**,
  388 (ISO-IR).
- Stokes, H. T. & Hatch, D. M. (1988), *Isotropy Subgroups of the 230
  Crystallographic Space Groups*, World Scientific; Campbell, B. J., Stokes,
  H. T., Tanner, D. E. & Hatch, D. M. (2006), *J. Appl. Cryst.* **39**, 607
  (ISODISPLACE); Perez-Mato, J. M., Gallego, S. V., Tasci, E. S., Elcoro, L.,
  de la Flor, G. & Aroyo, M. I. (2015), *Annu. Rev. Mater. Res.* **45**, 217.
- Gallego, S. V. et al. (2012), *J. Appl. Cryst.* **45**, 1236 (MAGNEXT);
  Gallego, S. V. et al. (2016), *J. Appl. Cryst.* **49**, 1750 and 1941
  (MAGNDATA).
- Shirane, G. (1959), *Acta Cryst.* **12**, 282.
- Shinohara, K., Togo, A. & Tanaka, I. (2023), *Acta Cryst.* A**79**, 390;
  Shinohara, K. (2023), *JOSS* **8**, 5269 (spgrep, BSD-3).
- Hinuma, Y. et al. (2017), *Comput. Mater. Sci.* **128**, 140; Aroyo, M. I.
  et al. (2014), *Acta Cryst.* A**70**, 126 (k-point labels).
- The full register with DOIs is issue #256's comment of 2026-09-06.

## Handover log

- **2026-09-15** — created, from the 2026-09-15 issue triage (issue #256).
  Checked against the tree: M-5 is on `main` as PR #290 and nothing in
  `docs/` recorded it until this round; spglib 2.7.0 in the venv carries the
  magnetic database. The decision it carries, the non-goal as sequencing, is
  the maintainer's; the triage recommends yes as a candidate.
