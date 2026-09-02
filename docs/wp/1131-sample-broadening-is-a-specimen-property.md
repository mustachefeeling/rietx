# WP-1131 — Sample broadening is a specimen property, not an angular coefficient

Milestone: unscheduled · Status: ✅ 2026-09-02
Depends on: — (WP-0308 owns the sharing map this corrects; WP-1072 is the esd
precedent the reporting half copies)

## Goal

Two halves of one mistake. A joint fit of patterns at different wavelengths
shares the **specimen's** crystallite size rather than a deg-2θ coefficient that
only names that size at one wavelength — measured below at **+12.5 % / −34.5 %**
on the package's own two-wavelength fixture. And a converged fit reports
crystallite size and microstrain as **physical numbers with esds**, or says why
it cannot, instead of leaving a user to convert a broadening coefficient
off-tool with a constant the package never states.

And a third, moved here from [1130](1130-background-reference.md)'s
2026-08-27 review because it reads the same conversion: a width the fit
has driven past what a crystal can have is named as a finding, in those
physical units. It is the only check that tells a nanocrystalline specimen
from a phase that has become a pedestal, and 1130's background diagnostic
defers to it.

## Context

### Why this exists

2026-08-23, from reading Von Dreele's GSAS-II teaching presentation, not from a
failing test. One slide splits the profile as *"Instrument — fixed from
calibration"* against *"Sample — phase & histogram dependent. **Independent of
experiment (e.g. CW or TOF)**"*. GSAS-II can make that claim because it refines
a physical size (μm) and a physical microstrain; the angular broadening is
derived per histogram. rietx shares the angular coefficient, which is not
independent of the experiment. Checking the claim against the code found a
measured defect and a missing output, and they have one cause.

Everything else in that presentation was already here or already fenced. The
identifiability half of its SVD slide is WP-1056's `soft_modes` (which answers
the downside Von Dreele names, that `w_ii` is not 1:1 to parameters); Jacobi
equilibration is WP-1110 for the covariance and a measured null for the step
(`../solver-survey.md` §0.2); the esd-scaling disagreement is that survey's E7;
hkl-dependent width misfit is `report/strain.py`; difference Fourier is fenced
at v2+. This WP is what was left.

### The physics, restated because it is the whole WP

Scherrer size broadening, in radians of 2θ: Δ2θ = k·λ / (p·cosθ). rietx stores
the coefficient of 1/cosθ in **deg 2θ**, so

    lor_size  =  (180/π)·k·λ / p            ∝ λ

Microstrain broadening: Δ2θ = 2·(Δd/d)·tanθ, so the coefficient of tanθ is

    lor_strain  =  (360/π)·(Δd/d)           no λ

The Gaussian pair obeys the same two laws in *variance*, so `gauss_size` ∝ λ²
and `gauss_strain` is λ-free. Stephens is λ-free as well: Λ(hkl) enters the
same tanθ slot, and σ(M)·d²·tanθ carries no wavelength.

**So exactly two of the six sample-broadening quantities depend on the
wavelength, and they are exactly the two named "size".** Note what this does
*not* depend on: the Scherrer constant k cancels out of every ratio below, so
the finding stands whatever convention k follows. Which convention it should
follow is a task, not an input.

### Finding 1 — the default sharing map shares a wavelength-dependent number

`params/multi.py:40-62`, `SharingMap`, docstring and rule:

> Default rule: a path is **per-histogram** iff it starts with ``instrument.``
> or ends with ``.scale``; everything else (cell, coordinates, occupancies,
> ADPs, **size/strain**, extinction, preferred orientation) is **shared** — one
> specimen, one crystal.

```python
    def is_shared(self, path: str) -> bool:
        ...
        return not (path.startswith("instrument.") or path.endswith(".scale"))
```

`phases.*.lor_size` and `phases.*.gauss_size` match neither exclusion, so each
becomes **one column written identically into every histogram's structure copy**
(`params/multi.py:65-83`, `:130-196`). Meanwhile `multi.py:4` advertises the
exact case that breaks it: patterns "at once — different wavelengths, geometries
or temperatures". `docs/wp/0308-multi-histogram.md` never raises the wavelength
question; grepping it for λ returns only the *test* line "two synthetic patterns
of the same phase at different wavelengths".

The docstring's justification, "one specimen, one crystal", is right. The
implementation does not deliver it for size.

### Finding 2 — measured, with the control that isolates the cause

One LaB₆ specimen, one true crystallite size p = 400 Å, synthesized at the two
wavelengths the committed fixture already uses (`tests/test_multi_histogram.py:60-63`,
ratio **1.7171**), each pattern carrying the `lor_size` its own wavelength
requires. Instrument `profile.x` held at 0 so all size broadening is the
sample's. Plan: scale+background, then cell, then the one width.

| `lor_size` (deg 2θ) | λ = 0.41390 | λ = 0.71070 |
|---|---|---|
| true, for p = 400 Å | 0.053358 | 0.091620 |
| fitted alone | 0.053302 (**−0.1 %**) | 0.090623 (**−1.1 %**) |
| joint, one shared column | 0.060009 (**+12.5 %**) | 0.060009 (**−34.5 %**) |
| size implied by the shared column | **355.7 Å** | **610.7 Å** |
| Rwp alone | 0.0445 | 0.0850 |
| Rwp joint | 0.0826 | **0.2179** |

Each histogram alone recovers the true size to ≤ 1.1 %. Jointly, one column
serves both and is wrong in opposite directions; the two implied sizes differ by
**1.717×**, the wavelength ratio exactly, for one specimen.

**The control, same machinery, same wavelengths, `lor_strain` instead** — a
λ-free quantity, Δd/d = 1e-3:

| `lor_strain` (deg 2θ) | λ = 0.41390 | λ = 0.71070 |
|---|---|---|
| true | 0.114592 | 0.114592 |
| fitted alone | 0.114774 (+0.2 %) | 0.114726 (+0.1 %) |
| joint, one shared column | 0.114758 (**+0.1 %**) | 0.114758 (**+0.1 %**) |
| Rwp alone / joint | 0.0429 / 0.0429 | 0.0821 / 0.0821 |

Sharing is exactly right for strain and its Rwp does not move at all. **The
defect is the wavelength, not joint refinement**, and the control is what makes
that a measurement rather than an argument.

### Finding 3 — the cell survives, so the failure is loud in Rwp and mute in attribution

The shared cell comes back at **−0 ppm** in the size case and −1 ppm in the
strain control. A user's headline number is not corrupted, which narrows the
urgency without touching the correctness: what is wrong is the width, the size
derived from it, and Rwp.

And Rwp is loud — 0.0850 → 0.2179 on the second histogram is not a subtle
degradation. The fit nonetheless returns **`status="converged"`** and no
diagnostic names a cause. A user meeting this sees a joint fit that is much
worse than either pattern alone and has nothing pointing at the sharing map.
That is the shape WP-1076 named: not a wrong number, an unnamed one.

Exposure is bounded and should be stated plainly. No default plan frees these:
`mccusker_default` does not, which is why the committed two-wavelength test has
never fired this. `lab_sample_refine` frees all four in one stage
(`strategy/staged.py:318-319`), and any caller may. A size term sitting at its
default 0.0 is 0.0 at every wavelength, so the defect needs a *refined nonzero*
size term in a joint fit whose histograms differ in λ.

### Finding 4 — half of it landed in v1.2; the strain half did not

**Superseded in part, 2026-09-02.** Finding 4 as written ("no physical size or
microstrain exists anywhere in the package") was true on 2026-08-23 and is half
false now: `b5918f43`…`817cfdb3` (2026-08-24, v1.2) put the **size** conversion
in `model/profiles/caglioti.py` — `apparent_size`, `delta_q_fwhm`,
`apparent_size_from_size_coefficient` and its inverse `size_coefficient_for_size`,
with `SCHERRER_K = 0.9` carrying the convention argument and Langford & Wilson
(1978) cited for the shape spread. `params.vector.size_cap`,
`refine._size_flag_diagnostics` and `report/layer2._size_clause` are its three
consumers.

What that leaves for this WP:

- **The conversion authority exists and this WP extends it rather than founding
  a peer module.** The original task asked for a new module beside
  `model/geometry.py`; there is now one authority in `caglioti.py` and a second
  spelling would be the mistake the root CLAUDE.md names.
- **There is still no strain conversion.** Nothing in `src/` reads a
  `lor_strain`/`gauss_strain` coefficient as a Δd/d, so a strain is still a
  number of degrees a user cannot check.
- **Nothing reports either as a result field.** `FitReport` carries no length
  and no dimensionless strain; both flags (below) compute a size or a width
  inside a diagnostic message and throw it away.
- **No esd anywhere.** Neither flag propagates, so the reporting half of this
  WP — J·Cov·Jᵀ off the final Jacobian, `None` where the coefficient is at
  zero, unmeasured or gradient-free — is untouched.

The one physical microstructural length in the schema is still an input whose
docstring rules out deriving it here, and rightly: `particle_radius_um` is
Brindley's absorption path, and "profile broadening measures the *coherent
domain* size, which is smaller than (and unrelated to) the particle"
(`schemas/structure.py:418-426`). Whatever this WP reports must be named a
**coherent domain size** and must never be confused with it.

### Finding 7 — re-measured on this tree, before and after, including `gauss_size`

2026-09-02, one script (`tests/output/wp1131_fixture.py`, session-local, and
`WP1131_NO_SCALE=1` disables the normalisation on the same build so the pair is
one measurement rather than two trees). LaB₆, p = 400 Å or Δd/d = 1e-3,
`profile.x` held at 0, λ 0.41390 over 3-24° and 0.71070 over 5-42°, three
stages: scale+background / cell / the one width.

| term | fitted alone | joint **before** | joint **after** |
|---|---|---|---|
| `lor_size` | −2.1 % / −2.2 % | +10.1 % / −35.9 % | −2.2 % / −2.2 % |
| implied size (Å) | — | **363.3 and 623.9** | **408.8 and 408.8** |
| Rwp | 0.1024 / 0.1372 | 0.1236 / **0.2450** | 0.1024 / 0.1374 |
| `gauss_size` | −0.1 % / −0.2 % | +11.9 % / **−62.1 %** | −0.1 % / −0.1 % |
| implied size (Å) | — | **378.2 and 649.3** | **400.2 and 400.2** |
| Rwp | 0.0412 / 0.0817 | 0.0809 / **0.3807** | 0.0412 / 0.0817 |
| `lor_strain` (control) | −0.8 % / −0.4 % | −0.7 % / −0.7 % | −0.7 % / −0.7 % |
| Rwp | 0.0538 / 0.0890 | 0.0538 / 0.0890 | 0.0538 / 0.0890 |

Three things this settles that Finding 2 could not. **The λ² derivation is
right and costs more than λ**: `gauss_size`'s joint Rwp on the long-wavelength
histogram was 4.7× its single-pattern value against `lor_size`'s 1.8×, because
the error in a width is squared into a variance. **The fix is exact, not
approximate**: after it the two implied sizes agree to floating point (the
coefficients are one number times two wavelengths), and both Rwp are what each
pattern gives alone to the fourth decimal. **The control is untouched to every
digit printed**, which is what makes the size result a measurement rather than
an argument — the same machinery, the same wavelengths, one λ-free quantity.

The percentages differ from Finding 2's (+12.5 % / −34.5 %) because the ranges,
seeds and starting values are this session's, rebuilt from Finding 2's recipe
rather than restored; the story, the implied-size ratio (1.7171, the wavelength
ratio exactly) and the cell's indifference (±2 ppm) are identical.

### Finding 5 — four independent coefficients can disagree about one specimen

GSAS-II parameterises one physical magnitude per mechanism plus a mixing
coefficient that splits it between the Gaussian and Lorentzian parts:

    S_γ = m_s·S + m_μ·M ,   S_Γ = [(1−m_s)²S² + (1−m_μ)²M²] / (8 ln 2)

so there is exactly **one** size, and `m_s ∈ [0,1]` describes the shape of the
size distribution rather than a second size. rietx registers `lor_size` and
`gauss_size` as fully independent columns (`params/vector.py:280-287`), and
`lab_sample_refine` frees both in the same stage. Nothing checks that they imply
the same size, and nothing reports it if they do not.

This does not by itself argue for adopting the parameterisation — independent
coefficients are the more general model and the constraint may cost fit quality
that means something. It argues that the **consistency is currently unmeasured**,
and it is one line to measure once Finding 4's conversion exists.

### Finding 6 — refine the coefficient, derive the size; the package already says why

GSAS-II refines the physical magnitude, which makes its esd fall straight out of
the covariance with no propagation. Copying that here walks into a trap this
repo has already paid for once. `size = (180/π)·k·λ / lor_size` has a **pole at
`lor_size = 0`**, and `lor_size` is a `softplus` parameter with `min=0.0`, which
the root CLAUDE.md records as underflowing to exactly 0.0 — the
`PreferredOrientation.r` failure, which fed the solver NaNs for a whole budget
without raising.

So the design is settled by rules already written down: keep refining the
coefficient, derive the size afterwards through J·Cov·Jᵀ the way
`model/geometry.py` does, and return **`None`** rather than a number when the
coefficient is at zero, unmeasured, or gradient-free. That is WP-1072's rule —
a quantity that cannot be measured is absent rather than zero — and
`ParameterTable.unmeasured_rows` already marks the inputs.

## Non-goals

- **Not the missing instrument `Z` term.** GSAS-II's Lorentzian is
  X/cosθ + Y·tanθ + **Z** and rietx has no constant Lorentzian
  (`schemas/instrument.py:507-543`). Von Dreele's own slide says X, Y, Z = 0 is
  normal and 11-BM has them zero, so the physics case is weak; the real case is
  that a GSAS-II `.instprm` carrying a nonzero Z has no field to land in, which
  makes it [1118](1118-foreign-model-files.md)'s, not this WP's.
- **Not anisotropic size.** Stephens gives hkl-dependent *strain* only; an
  anisotropic size model is a new physics seam and belongs with FPA at v2+.
- **Not the Le Bail / Pawley export claim.** `profile_only` and `pawley_default`
  both advertise "extracted intensities for structure solution"
  (`strategy/staged.py:539,551`) while the reflection table writes
  `f_squared=None` in those modes and an `intensity` column with Lp and
  multiplicity absorbed and no note saying so (`io/exporters.py:127-131`,
  `model/forward.py:1082`). Real, WP-1076-shaped, and unowned by any WP —
  recorded here because it was found in the same sweep, to be picked up
  separately rather than folded in.
- **Not TOF.** Von Dreele's "independent of experiment" claim spans CW and TOF;
  `Source.kind` is `Literal["xray_cw"]` and TOF is v2-fenced. The rule this WP
  installs is what a TOF histogram would later need, which is a reason to get it
  right and not a reason to build TOF.
- **Not a new estimator for the size distribution.** Reporting a coherent domain
  size is not a claim about the distribution behind it.

## Tasks

- [x] **The physics, as one authority — `caglioti.py`, extended not duplicated.** ✔
      The size half landed in v1.2 (Finding 4); this WP adds the **strain** half
      beside it, in both directions, citing its source and stating its convention,
      with no wavelength argument because strain has none. Everything below
      imports from there; nothing restates a constant.
- [x] **Settle the constants before writing them.** Settled from prior art, not
      invented, and recorded beside each constant. Size: `SCHERRER_K = 0.9`
      already in the tree — the **FWHM** convention for roughly isotropic
      crystallites, K an argument everywhere so a known morphology can say so
      (Langford & Wilson 1978 tabulate 0.89 for a sphere's FWHM against 1.0747
      for its integral breadth; the paper itself is still not in the corpus, and
      the numbers quoted here come from the in-tree citation and FullProf's
      manual). Strain: the coefficient is the **FWHM** of the Δd/d distribution,
      matching the size convention, so `lor_strain = (360/π)·(Δd/d)` inverts with
      no second constant. What the neighbours do, recorded because they disagree
      with each other and one of them is quoted at the user: GSAS-II reads its
      size off the FWHM with k = 1 and reports `mustrain` μ = 2·Δd/d in 10⁻⁶
      (Von Dreele's `S = 180kλ/(πp cosΘ)`, `M = 180μ tanΘ/π`); FullProf reads
      both off the **integral breadth** — apparent size `D = (360λ/π²)·(η+(1−η)√(π ln2))/Z_s`
      and apparent strain `ε = ½·β*·d` in 10⁻⁴ — which for a pure Lorentzian is
      π/2 = 1.571× rietx's size and half rietx's strain. Neither is adopted:
      rietx's four coefficients are FWHM coefficients, so the FWHM convention is
      the one that inverts them without a peak-shape assumption, and the two
      spreads are what make the reported number an order-of-magnitude statement.
- [x] **Fix the sharing map.** ✔ *normalise*, per the measurement below.
      `ParameterTable.apply_value_scale` declares a fixed factor between a
      path's physical value and its free column (folded into C, so `decode`
      multiplies, `x0`/`bounds` divide, an esd comes back multiplied and the
      analytic Jacobian inherits it for free because `_peak_chain_column`
      finite-differences θ *through* `decode`); `params.multi.size_value_scales`
      hands each histogram λ_h/λ_ref for `lor_size` and its square for
      `gauss_size`, and the structure copies are pre-scaled so the shared
      internal coordinate is the coefficient at λ_ref. Shared bounds are now
      **intersected** rather than last-write-wins, because the histograms can
      genuinely disagree about a size cap once it is divided per histogram.
      Measured on the fixture: two implied sizes 408.8 Å and 702.0 Å become one
      408.8 Å, histogram 1's Rwp 0.2450 → 0.1374 against 0.1372 for that pattern
      alone, and the λ-free strain control is unmoved to every digit printed
      (0.113840, Rwp 0.0538/0.0890 before and after). Old task text: **Fix the
      sharing map.** `phases.*.lor_size` and `phases.*.gauss_size` may
      not be one column across histograms of different wavelength. Two candidate
      shapes, and the WP picks one on measurement: normalise the shared column
      (share the size, derive each histogram's coefficient from its own λ), or
      refuse — make them per-histogram by default and raise when a caller shares
      them across differing λ. Whichever lands, **equal wavelengths must stay
      bit-identical**, since that is every existing joint fit.
- [x] **A diagnostic, because Finding 3 says the failure is unattributed.** ✔
      `SIZE_NORMALISED_ACROSS_WAVELENGTHS`, level **info** — with the fix there
      is no defect to warn about, so the row *states what was done*, the shape
      `PHASE_UNCONSTRAINED` took in WP-1301. Carries the path, both wavelengths,
      every histogram's factor and its resulting coefficient, and the
      `SharingMap(per_histogram=…)` escape. Silent when nothing was scaled or
      when every scaled term is still at zero. Old task text: **A diagnostic,
      because Finding 3 says the failure is unattributed.**
      Sharing a wavelength-dependent path across differing λ is a named finding
      with the paths and the two wavelengths in it, not a silent 2.6× Rwp. Add it
      through the `GuardFinding` constructor per the root CLAUDE.md rule, and its
      row in `AGENT_PROTOCOL.md`.
- [x] **Report the size and the strain.** ✔ `RefinementResult.microstructure` /
      `FitReport.microstructure`, one `PhaseMicrostructure` per phase, four
      `MicrostructureTerm`s each. Built in `model/microstructure.py` (the peer of
      `model/geometry.py`), called from `refine.py` beside `geometry_table` off
      the same final Jacobian, through the same λ selector the size bound and
      the size flag use. Each reading is a function of exactly **one**
      coefficient, so J·Cov·Jᵀ is one variance with no cross-term to drop —
      which is *why* a combined Gaussian+Lorentzian size is not reported.
      Four absences, each named: `at_zero`, `no_wavelength`, `not_measured`,
      and `None` for nothing missing. Named a coherent domain size, with
      `particle_radius_um` disclaimed in the schema and in the manual. Old task
      text: **Report the size and the strain.** `FitReport` carries a per-phase
      microstructure block: coherent domain size and microstrain with esds
      through J·Cov·Jᵀ off the final Jacobian, `None` wherever the coefficient is
      at zero, unmeasured (`ParameterTable.unmeasured_rows`) or gradient-free.
      Name it a coherent domain size, and say beside it that it is not
      `particle_radius_um`.
- [x] **The width check** — **landed in v1.2, not by this WP**:
      `SIZE_UNUSUALLY_SMALL` (below `refine.SIZE_FLAG_SIZE_A` = 50 Å apparent
      crystallite, via Scherrer at the pattern's longest line) and
      `STRAIN_UNUSUALLY_LARGE` (above `refine.STRAIN_FLAG_WIDTH` = 1.5 deg),
      each with a bound twin in `params.vector` (`size_cap` with its 2 nm physics
      floor, `strain_cap` off the fitted range) that arms only on a term already
      at the floor, and rows in `docs/skill/rietx/references/{diagnostics,abstention}.md`
      and `docs/manual/profiles.md`. Both thresholds are calibrated on the
      606-refinement TOPAS archive rather than invented, and both say the number
      is one to check rather than a refusal. 1130's dependency is discharged.
- [x] **State the separability caveat where the number is, not elsewhere.** ✔
      `PhaseMicrostructure.separable` + `size_strain_collinearity`, copied from
      the width `TrendAnalysis`'s own verdict in `build_report` and **never**
      recomputed. `None` — no claim made — on the result and on an abstained
      report. Old task text: **State the separability caveat where the number
      is, not elsewhere.** Over
      a narrow 2θ range size and strain are collinear, which the package already
      knows (`report/schemas.py:733`'s `max_template_collinearity`, and the
      Layer 2 bullet at `../DESIGN.md` 322-328). A size reported without that
      caveat is the confident wrong
      singleton the FitReport exists to refuse. Reuse the existing statistic;
      do not compute a second opinion.
- [x] **The Gaussian/Lorentzian consistency check.** ✔
      `PhaseMicrostructure.size_agreement` / `.strain_agreement`, the Gaussian
      reading over the Lorentzian one, `None` when either is absent. One line
      once the authority existed, exactly as Finding 5 predicted. Old task text:
      **The Gaussian/Lorentzian consistency check.** Once the conversion exists,
      compare the size implied by `lor_size` against the one implied by
      `gauss_size` (and the two strains likewise) and report a disagreement.
      Finding 5 is why; one line once the authority exists.
- [x] **Measure `gauss_size` the way Finding 2 measured `lor_size`.** ✔ Done,
      and the derivation held: the damage is larger. Same fixture, same control,
      the normalisation switched off on the same build (§ Finding 7).
- [x] **Manual + protocol.** ✔ Part 2's `microstructure.md` gains
      § *Reading a width as a strain* with {eq}`ms-strain-law` and
      {eq}`ms-strain-coefficient`, both `*Source:*`-attributed, and Stokes &
      Wilson (1944) joins the bibliography; the λ asymmetry is stated there
      because that is where the two equations sit side by side. Part 1's
      `using/results.md` gains § *The size and the strain, in physical units* —
      the field table, the four absences, the separability caveat and the
      joint-fit note — which is what the API partition demanded (20 new public
      names). The skill's deliverable table gains a **Microstructure** row and
      `references/judging.md` its worked measurement; `references/diagnostics.md`
      gains the `SIZE_NORMALISED_ACROSS_WAVELENGTHS` row. `SKILL_MAX_BYTES` went
      32 000 → 33 000 in the commit that needed it, argued there: the derivation
      ("half the ~66 kB Read cap") is unchanged, and the alternative was a
      deliverable whose row lived outside the table its four peers are in.
- [x] **`rietx compare` row** — ✔ **none, and the reason is the rule itself.**
      The standing rule is "add a row whenever a new *correction* lands", and
      this WP lands none: on a single-histogram standard — which every one of
      `compare`'s standards is — the sharing change is bit-identical by
      construction, and the report block changes no residual, so a variant
      toggling it would draw a flat Δχ² panel and assert nothing. The width
      comparison the task imagined already exists: every standard's baseline
      plan frees all four sample terms in its `sample_broadening` stage
      (`viz/compare.py:171`), so `result.microstructure` is populated on every
      run already, and the `stephens` variant is the width change the Δχ² panel
      localises.
- [x] Tests ✔ — `tests/test_microstructure.py` (the conversions against hand
      computations and against the law evaluated at six angles; the block's
      value, esd, four absences and the G/L agreement; an end-to-end fit whose
      size and strain each cover their truth; a JSON round trip) and four new
      rows in `tests/test_multi_histogram.py` (the two-wavelength size fixture,
      the `gauss_size` λ² twin, the λ-free strain control, the two selectors'
      agreement, the empty-scale cases and the `apply_value_scale` refusals).
      PNGs to `tests/output/`: `wp1131_size_joint_h{0,1}`,
      `wp1131_gauss_size_joint_h{0,1}`, `wp1131_microstructure_fit`, all
      inspected.

## Acceptance

A joint fit of the two-wavelength fixture recovers one crystallite size within a
stated band at **both** wavelengths, where today it lands +12.5 % / −34.5 %; the
λ-free strain control stays bit-identical; a single-wavelength joint fit is
bit-identical to today; a converged single-pattern fit reports a size with an
esd, or `None` with a reason; and a fit driven to 1130's trigger widths
fires the width finding while every bundled pattern's converged fit stays
silent.

**Met, 2026-09-02**, clause by clause. The fixture recovers **408.8 Å at both
wavelengths** (`lor_size`) and **400.2 Å at both** (`gauss_size`) against a true
400 Å, where the shared column landed 363.3/623.9 and 378.2/649.3 before; the
agreement between the two histograms is asserted at `rel=1e-9`, because after
the fix it is structural rather than statistical. The strain control is unmoved
to every digit printed. A single-wavelength joint fit declares **no scaling at
all** — an empty map, not a map of 1.0s — so `ParameterTable` takes the branch
it always took and the arithmetic is untouched. A converged single-pattern fit
reports 399.9(26) Å and Δd/d 0.00084(27), and every absent number names its
cause. The width finding is v1.2's and was already calibrated silent on the
bundled patterns.

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_microstructure.py -q
.venv/bin/python -m pytest tests/test_fitreport_layers.py tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

Quote the fast counts with venv and platform per the root CLAUDE.md § Numbers,
and put them in this file's handover entry.

## References

- **Von Dreele, R. B.**, *The Rietveld Refinement Method in GSAS-II*, teaching
  presentation (ANL) — the trigger. The load-bearing slides are the
  instrument/sample split ("Sample — phase & histogram dependent; independent of
  experiment"), the CW profile coefficients (`Γ_g² = 8ln2(U tan²Θ + V tanΘ + W +
  S_Γ)`, `γ = X/cosΘ + Y tanΘ + Z + S_γ`), and the mixing pair
  `S_γ = m_s S + m_μ M`, `S_Γ = [(1−m_s)²S² + (1−m_μ)²M²]/8ln2` with
  `S = 180kλ/(πp cosΘ)` and `M = 180μ tanΘ/π`. Maintainer-local, outside this
  repo.
- **Von Dreele (1997)**, *J. Appl. Cryst.* **30**, 517 — already the citation
  behind WP-0308's sharing map, which is what this WP corrects.
- **Scherrer (1918)**, *Nachr. Ges. Wiss. Göttingen* **26**, 98 — the size law.
- **Langford & Wilson (1978)**, *J. Appl. Cryst.* **11**, 102 — the Scherrer
  constant and its shape dependence. **Still not in the corpus** (a title search
  returns no size/Scherrer entry) and still not read; `SCHERRER_K`'s in-tree
  citation quotes its 0.89/1.0747 pair, which is what the convention note rests
  on. Worth requesting before anyone quotes a two-figure size.
- **Rodríguez-Carvajal**, *FullProf manual* — in the corpus, and the prior art
  that settles the convention question the other way: apparent size and apparent
  strain from the **integral breadth** of the size-only pseudo-Voigt, with the
  TCH mixing rule spelled out. Read for this WP, adopted as the *record of what
  the neighbours do*, not as the convention.
- **Stephens (1999)**, *J. Appl. Cryst.* **32**, 281 — already cited in
  `crystallography/stephens.py`; relevant here because Λ(hkl) is λ-free and so
  stays correctly shared.
- **Thompson, Cox & Hastings (1987)**, *J. Appl. Cryst.* **20**, 79 — already
  cited by `model/profiles/caglioti.py` for the Gaussian size term `P`.
- Licensing: GSAS-II is the source of the *parameterisation idea* only. Concepts
  and published equations, never code.

## Handover log

### 2026-09-02 — both halves landed, and a third of the WP was already done

**What this means.** A joint fit of one specimen at two wavelengths now shares
the *crystallite size* rather than the number of degrees, and every converged
fit reports a coherent domain size and a Δd/d with esds or a named reason it
has neither. The two halves needed one thing that did not exist — a conversion
authority — and half of that had landed in v1.2 while this WP sat queued, which
is the first thing this session found and the reason the checklist shrank
before it grew.

*Pruned on arrival* — Finding 4 said "no physical size or microstrain exists
anywhere in the package". Half false since `b5918f43`…`817cfdb3` (2026-08-24):
`caglioti.py` holds the size conversion in both directions with `SCHERRER_K`
carrying the convention and Langford & Wilson cited. The **width check**
inherited from 1130 had also shipped entire, as `SIZE_UNUSUALLY_SMALL` /
`STRAIN_UNUSUALLY_LARGE` with their `params.vector` bound twins, calibrated on
the 606-refinement TOPAS archive and rowed in the skill tree — so 1130's
dependency on this WP is **discharged** and § Inherited is gone. What that
left: the strain conversion, the sharing map, and the whole reporting half.

*Settled, not invented* — both open conventions, from prior art, recorded beside
the constants. rietx's four coefficients are **FWHM** coefficients, so the FWHM
convention inverts them with no peak-shape assumption and no second constant:
`Δd/d = (π/360)·lor_strain`. GSAS-II reads size off the FWHM with K = 1 and
publishes `mustrain` = 2Δd/d; FullProf reads both off the **integral breadth**,
which for a pure Lorentzian is 1.571× rietx's size and half its strain. Both
recorded in the manual and the skill, because a microstrain is not comparable
between codes without its convention. Langford & Wilson (1978) is **still not
in the corpus** and still unread — worth requesting before anyone quotes a
two-figure size.

*Measured* — the before/after table is § Finding 7. The headline: `lor_size`
joint went 363.3 Å / 623.9 Å (one specimen, two crystallites, exactly the
wavelength ratio apart) to **408.8 Å / 408.8 Å** against a true 400; `gauss_size`,
the λ² twin nobody had measured, went 378.2 / 649.3 to **400.2 / 400.2** and its
long-wavelength Rwp 0.3807 → 0.0817, which is what each pattern gives alone.
The λ-free strain control is unmoved to every digit printed, before and after,
which is what makes the size result a measurement rather than an argument. The
`WP1131_NO_SCALE=1` switch in the session-local fixture script disables the
normalisation on the same build, so the pair is one measurement and not two
trees.

*The seam* — `ParameterTable.apply_value_scale`, a fixed factor between a path's
physical value and the number its free column carries, folded into **C**. Chosen
over the alternatives because of where the derivative chain already is:
`_peak_chain_column` finite-differences θ *through* `decode`, so the analytic
column picks the factor up exactly where the whole-model FD column does and no
derivative branch is touched. Measured rather than argued — every column of the
stacked multi Jacobian against a central difference of the stacked residual,
worst relative error 2.7e-6 against the unscaled cell column's 9.8e-7.

*Two things the seam dragged in, both of which would have failed silently.*
Shared bounds are now **intersected** rather than last-write-wins, since a size
cap is a physical limit on each histogram's own coefficient and the scale
divides it differently per histogram. And `seed_softplus` seeds in **column**
units: seeding the physical value gives the histograms different internal
coordinates for one shared column, nothing raises, and the last write wins.

*Gotchas for whoever touches this next.* (1) Sharing happens in **internal**
coordinates — two histograms share a column by being given the same θ — so
anything that writes an entry's value per histogram has to think about the
scale; `commit`, `x0`, `bounds` and `seed_softplus` all do now, and a fifth
writer would not inherit it. (2) `SIZE_LAMBDA_POWER` is the whole list of
λ-dependent quantities, as data: a new size term is one line there, and a new
*strain* term is nothing. (3) The reference is histogram **0**, so its factor is
exactly 1.0 and `RefinementResult.parameters` reports its numbers unchanged —
which is also why equal wavelengths produce an *empty* map rather than a map of
1.0s, and why the pre-change arithmetic is untouched rather than merely equal.
(4) `SKILL_MAX_BYTES` went 32 000 → 33 000; the body was 32 B from its ceiling
before this WP, so the next addition to it will need the same decision.

*Not done, and why.* **No `rietx compare` row**: the standing rule adds one when
a *correction* lands, and this WP lands none — every compare standard is
single-histogram, where the change is bit-identical by construction, so a
variant would draw a flat Δχ² panel. Every standard's baseline already frees all
four sample terms, so the microstructure block is populated on every run as it
stands. **No combined Gaussian+Lorentzian size**: that one is a function of two
correlated columns and would need a covariance this module is not given, so the
two readings are compared through `size_agreement` instead — which is Finding 5's
unmeasured consistency, now measured.

*Counts* — fast selection `-m "not slow"`, this worktree's own `[dev]` venv
(no jax, no torch — the cross-backend rows self-skip), darwin/arm64, python
3.12.12, **alone on the machine**: **3977 passed, 122 skipped** in 3:01. The
suite was started twice before this and both runs were discarded rather than
quoted — one raced an edit of its own tree, the other started within three
seconds of another session's suite in the `wp1324` worktree, which rung 3's
exclusivity rule says is not quotable. **+54 tests**, all passes: 45 in the new
`tests/test_microstructure.py` and 9 in `tests/test_multi_histogram.py`
(5 → 14). No new skips — 122 in every run this session. **Full suite**, same venv and platform, once on the final tree: **4140 passed, 131 skipped** in 33:52 — above the ~15-30 min the commands section quotes, and wall clock is a range not a figure, so read the green rather than the minutes.

*Next* — nothing in this WP. It is closed. Two threads lead out of it: 1130 can
proceed (its dependency is discharged), and a **λ-free `gauss_strain`** joint
fixture was never run — derived and believed, like `gauss_size` was until this
session, and cheap to add to the same script if anyone wants the fourth cell of
the table.

- **2026-08-27** — 1130's review moved the width check here (Tasks, *The width check*) and made 1130 depend on this WP; the trigger numbers and the dataset pointer are in § Inherited. No code touched. *Next* is unchanged: the conversion authority first, since the check reads it, then the sharing fix.

### 2026-08-23 — opened from a presentation, and the bug is measured

**What this means.** rietx stores sample broadening as an angle and shares it
between histograms as though it were a property of the specimen. For microstrain
that is exactly right. For crystallite size it is wrong, because the same
specimen broadens by a different number of degrees at a different wavelength, and
a joint fit of the package's own two-wavelength fixture therefore serves one
column to two histograms that need values 1.717× apart. Measured, it lands
+12.5 % and −34.5 % from truth and takes the second histogram's Rwp from 0.0850
to 0.2179 while reporting `converged`. Underneath that is a plainer gap: the
package has never converted any of these coefficients into a crystallite size or
a microstrain, so a user cannot check the answer even in principle. Fixing the
sharing and shipping the physical number are the same piece of work, because
both need one authority for the conversion that does not exist yet.

*Done* — nothing landed in the tree; this session read the presentation, checked
each of its ideas against the code, and measured the one that turned out to be a
defect. This file is the record. The two measurement scripts are session-local
and not committed; Finding 2 has everything needed to rebuild them (one LaB₆
phase from `tests.test_schemas.make_lab6`, `profile.x` held at 0, a three-stage
plan of scale+background / cell / the one width, λ 0.41390 and 0.71070 over
3-24° and 5-42°).

*Measured* — Finding 2 and its control. The numbers that decide the design:
+12.5 % / −34.5 % (shared `lor_size` against each histogram's truth), 355.7 Å
and 610.7 Å (one specimen, two implied sizes), 1.717× (their ratio, the
wavelength ratio exactly), 0.0850 → 0.2179 (Rwp, second histogram), and the
control at +0.1 % / +0.1 % with Rwp unmoved to four decimals. Cell −0 ppm, so
the cell is not the victim.

*Not measured, deliberately* — `gauss_size`'s λ² dependence is derived from the
same law and is a task above; the Rwp damage there should be larger, and nobody
should quote a figure for it until it is run.

*Gotchas for the next session* — the finding does **not** depend on the Scherrer
constant, since k cancels from every ratio, so do not let the open convention
question block the sharing fix; a size term at its default 0.0 is 0.0 at every
wavelength, which is why the committed two-wavelength test has never caught this
and why the fixture must free the width explicitly; and equal-wavelength joint
fits are every joint fit that exists today, so bit-identity there is the bar, not
a nicety.

*Next* — the conversion authority, because both halves import it: the sharing
fix needs it to normalise a shared size, and the report needs it to state one.
Then the sharing fix, since that is the correctness half and it carries the
fixture that stops the regression.
