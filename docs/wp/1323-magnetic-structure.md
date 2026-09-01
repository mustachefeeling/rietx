# WP-1323 — a magnetic structure: stating one, refining it, and reporting what it cost

Milestone: unscheduled · Status: ⬜
Depends on: — (WP-1134 shipped the CW-neutron instrument this needs; WP-1312 is
its follow-through and does not gate any task here)

## Goal

A magnetic structure can be **stated** (moments on sites, under a magnetic
symmetry, with a propagation vector), **refined** against constant-wavelength
neutron powder data alongside the nuclear model, and **reported** with the
moment magnitudes and their esds. Today the package has no magnetic model at
all, and says so in three places rather than pretending otherwise — this WP is
the scoping of what it would take to say yes instead.

**This WP is deliberately a scoping document.** The design is *not* settled
here. What is settled is the evidence, the fences, the vocabulary, and the list
of decisions somebody has to take before writing code.

## Context

### What the package says today, in its own words

Three fences, all consistent, all pointing at the same hole:

1. **`io/projects/coverage.py`** declares magnetic structure `Stance.REFUSED`
   over the keywords `mag_space_group`, `mag_only`, `mag_only_for_mag_sites`,
   `mlx`, `mly`, `mlz`, `mg`, `mag_atom_out`, because *"rietx has no magnetic
   model, so the nuclear half is all that could be imported and it would look
   complete"*.
2. **`io/projects/topas.py`** (≈ line 1915) raises rather than dropping: a
   `mag_space_group` makes the reader refuse the phase, on WP-1118's rule
   *report or refuse, never drop*. The comment notes the trap that made it
   necessary — `mag_space_group 62.448` used to match an unanchored
   `space_group` and arrive as the symbol `"62.448"`.
3. **WP-1314** refuses magnetic space groups by the same rule, and **WP-1134**
   fenced magnetic scattering explicitly as *"a discussion to raise, not a thing
   to implement"*. This WP is that discussion.

And one place where the absence is already **user-visible as an unanswerable
question**: `refine.py` (≈ lines 3150 and 3239) reports intensity the model puts
nowhere and names, among the candidate causes, *"a magnetic contribution"*. The
package can therefore already tell a user their residual might be magnetic, and
offers no way whatever to test that hypothesis. That asymmetry is the argument
for this WP more than any feature request is.

### The physics that makes this not just "another phase"

Restated here because it drives every design decision below, and because a
session that gets it wrong will produce something that fits and is meaningless.

- **Magnetic neutron scattering is Q-dependent in a way nuclear scattering is
  not.** The nuclear scattering length *b* is a constant; the magnetic form
  factor *f*(Q) falls off with Q much like an X-ray form factor, because it is
  the Fourier transform of an extended spin density rather than of a point
  nucleus. Magnetic intensity therefore concentrates at **low Q**, and a model
  that treats it as another nuclear phase will get the angular dependence wrong
  in a way the profile terms can partly absorb — which is exactly how a wrong
  magnetic model hides.
- **Only the moment component perpendicular to Q scatters**: I_mag ∝ |M_⊥|²,
  M_⊥ = Q̂ × (M × Q̂). A powder average over domains and over the reflection
  multiplicity makes some moment directions **unmeasurable in powder data** —
  for a collinear structure on a cubic lattice, the direction within certain
  planes is not determined at all. Any honest implementation has to be able to
  say "this component is not measurable here", which is the same class of
  statement the identifiability machinery already makes for nuclear parameters.
- **The scale is fixed, not free.** The magnetic and nuclear contributions of
  one specimen share one scale factor; the conversion constant is
  **0.2695 × 10⁻¹² cm per μ_B** (γr₀/2). A separate free magnetic scale is the
  single easiest way to get a plausible fit and a wrong moment, and it is what
  makes a magnetic refinement worth trusting or not.
- **A propagation vector k puts magnetic intensity at Q = G ± k.** For k = 0 the
  magnetic reflections sit on the nuclear ones; for k ≠ 0 they appear at
  positions the nuclear cell does not index at all — which is what a user with
  unexplained low-angle intensity actually has.
- **X-rays are not the route.** Non-resonant magnetic X-ray scattering is weaker
  than charge scattering by order (ħω/mc²) and is not a powder technique;
  resonant magnetic X-ray scattering is a synchrotron speciality. **Neutron
  first, and possibly neutron only.**

### The trap that would corrupt QPA

FullProf and others commonly model the magnetic contribution as a **separate
"phase"** sharing the nuclear cell. If rietx adopted that shape naively, a
magnetic phase would enter `phase_zmv` / `compute_qpa` as **separate mass**, and
every `weight_percent` in a magnetic refinement would be wrong — the same
specimen counted twice. `weight_percent` normalises over active phases
(`optimize/qpa.py`), so this is not hypothetical.

**Whatever shape is chosen, a magnetic contribution must be excluded from the
mass balance, and there should be a test that fails if it is not.** State this
before the schema, not after.

### Prior art, and the licensing fence

Concepts only; `ATTRIBUTION.md`'s rules apply and should be re-read before any
of this is ported.

- **FullProf** — the reference implementation for magnetic powder refinement;
  magnetic structure via propagation vector plus basis vectors from
  representation analysis (BasIreps), or via magnetic space group.
- **Jana2006** — magnetic (super)space groups, including incommensurate.
- **GSAS-II** — magnetic structures on the Shubnikov-group route.
- **Bilbao Crystallographic Server** (MAXMAGN, MAGNDATA) and **ISODISTORT** —
  the symmetry machinery, and MAGNDATA is a corpus of published magnetic
  structures in a machine-readable form.
- **`.mcif`** — the magnetic CIF dialect, the natural interchange format and the
  thing WP-1319 (structure interchange) would eventually have to know about.

## Non-goals

Fences, so the WP does not become "implement magnetism".

- **Determining a magnetic structure.** Representation analysis, symmetry-mode
  enumeration, candidate generation — the BasIreps/ISODISTORT job. **This WP
  refines a structure the user states**, in the same way the package refines a
  nuclear structure the user states rather than solving it.
- **Incommensurate and modulated structures.** WP-1314 already fences these; a
  k-vector that is not a simple rational fraction of a reciprocal lattice vector
  is a superspace problem and belongs with modulation, not here.
- **Time-of-flight.** WP-1134's fence stands: a bank spans a range of λ.
- **Polarised neutrons**, spherical neutron polarimetry, and single-crystal
  magnetic data.
- **Resonant or non-resonant magnetic X-ray scattering.**
- **Anything beyond the dipole approximation** for the magnetic form factor
  (no orbital/quadrupole terms), at least in the first landing — and the
  approximation must be *named in the output*, not assumed.

## Tasks

Ordered so that the decisions come before the code. Each is roughly one commit;
the first three produce documents, not features.

- [ ] **Decide how a magnetic structure is stated**, and write the decision down
      with its rejected alternatives. The two candidate routes are (a) a
      Shubnikov/magnetic space group plus moments on sites, and (b) a parent
      space group plus a propagation vector plus basis-vector coefficients.
      They differ in what a user must know and in what the package must
      implement; (b) is what representation analysis produces and (a) is what
      `.mcif` and MAGNDATA distribute.
- [ ] **Decide where the moment lives in the schema** — an attribute of `Atom`,
      a parallel magnetic site list, or a separate object — and how it composes
      with `Wyckoff` constraints, since a moment's allowed direction is
      constrained by site symmetry exactly as a positional DOF is.
- [ ] **Settle the QPA exclusion** and write the test that fails if a magnetic
      contribution enters the mass balance. Before anything else lands.
- [ ] Magnetic form factors: the ⟨j₀⟩ coefficient tables (International
      Tables C), their provenance, and the `SPECIES_FALLBACK_NEUTRAL` question
      in a magnetic setting — a magnetic ion absent from the table must not
      silently become something else, which is issue #202's lesson applied to a
      new table.
- [ ] The structure factor: |M_⊥|², the 0.2695 μ_B constant, the shared scale,
      and reflection generation for Q = G ± k.
- [ ] Identifiability: report the moment components the powder average cannot
      determine, rather than refining them to a confident number. The existing
      `identifiability` machinery is the right home and the right vocabulary.
- [ ] Readers: lift the `coverage.py` refusal to *reported* or *read* for the
      TOPAS magnetic keywords, and decide whether `.mcif` belongs here or in
      WP-1319.
- [ ] Diagnostics: connect to the existing unexplained-intensity report, so the
      package that says "this might be magnetic" can then say "and here is what
      happens if you model it".
- [ ] Manual chapter, `capabilities()` entry, and a row in `AGENT_PROTOCOL.md`
      if a diagnostic code lands.
- [ ] Tests, including the acceptance below, with obs/calc/diff PNGs to
      `tests/output/`.

## Acceptance

A published magnetic structure, refined from a public constant-wavelength
neutron powder dataset, reproducing the published moment magnitude **within the
published esd**, with the nuclear and magnetic contributions sharing one scale.

```sh
.venv/bin/python -m pytest tests/test_magnetic.py -q
.venv/bin/python -m ruff check src tests examples
```

Plus, and equally binding:

- A magnetic contribution **does not appear in the mass balance**; a test
  asserts a magnetic refinement's `weight_percent` matches the same specimen's
  nuclear-only refinement.
- A moment component the powder average cannot determine is **reported as such**
  rather than returned with a small esd.
- The form-factor approximation in force is named in the output.
- A k ≠ 0 structure places intensity at Q = G ± k, verified against generated
  positions rather than by eye.

## References

- Shirane, G. (1959), *Acta Cryst.* **12**, 282 — magnetic structure factors for
  powder work.
- Brown, P. J., *International Tables for Crystallography* Vol. C, § 4.4.5 —
  magnetic form factors and the ⟨j₀⟩ coefficients.
- Rodríguez-Carvajal, J. (1993), *Physica B* **192**, 55 — FullProf, and the
  propagation-vector formalism as implemented.
- Perez-Mato, J. M. *et al.* (2015), *Annu. Rev. Mater. Res.* **45**, 217 —
  magnetic symmetry and the Shubnikov-group route.
- Gallego, S. V. *et al.* (2016), *J. Appl. Cryst.* **49**, 1750 — MAGNDATA, the
  published-structure corpus.
- [1134](1134-constant-wavelength-neutron.md) — the CW-neutron instrument, and
  the fence this WP opens. [1312](1312-neutron-followthrough.md) — the seed and
  the resonant-absorber flag. [1319](1319-structure-interchange.md) — where
  `.mcif` may belong. [1118](1118-foreign-model-files.md) — the refuse-don't-drop
  rule the readers follow.

## Handover log

- **2026-09-02** — created, as a scoping document rather than a plan to execute.
  A reader now knows what the package's three existing magnetic refusals have in
  common, why a magnetic contribution is not simply another phase (Q-dependent
  form factor, |M_⊥|² geometry, one shared scale, Q = G ± k), and the one trap
  that must be settled before any schema is written: a magnetic contribution
  entering `phase_zmv` would double-count the specimen's mass and silently
  corrupt every `weight_percent` in the refinement. The design is deliberately
  open — in particular the Shubnikov-group versus propagation-vector question,
  which decides most of what follows. Next action: take that decision, and write
  the QPA-exclusion test before the schema it constrains.
