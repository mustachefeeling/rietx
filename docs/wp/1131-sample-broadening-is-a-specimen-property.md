# WP-1131 — Sample broadening is a specimen property, not an angular coefficient

Milestone: unscheduled · Status: ⬜
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

### Finding 4 — no physical size or microstrain exists anywhere in the package

Verified by search across `src/`, `docs/manual/` and the exporters, not assumed:

- No Scherrer conversion, no `k`, no size in nm/μm/Å, no strain in ppm. Every
  "Scherrer" in `src/` is either the `debye_scherrer` geometry literal or prose
  naming the 1/cosθ law.
- The four coefficients are plain `Parameter`s with `unit="deg"` / `"deg^2"`
  (`schemas/structure.py:390-409`). Their comment states the θ-laws and the
  instrument ⊕ sample workflow, and states no conversion constant.
- `FitReport` carries no length and no dimensionless strain in any layer.
  `TrendAnalysis`'s `inv_cos_theta` / `tan_theta` templates are *attribution*
  amplitudes, and `StrainAnalysis.anisotropy` is a broadest/narrowest **ratio**.
- Derived-quantity esd propagation exists three times and none is this:
  `model/geometry.py` (bonds/angles), `optimize/qpa.py` (weight fractions),
  `indexing/qspace.py`. `params/vector.stderr_physical` propagates only through
  affine ties and transforms, so a `lor_size` esd is an esd on a FWHM in degrees.
- `docs/manual/microstructure.md` goes from the θ-laws straight to Stephens. The
  word "nm" does not appear in the manual.

The one physical microstructural length in the schema is an input whose
docstring rules out deriving it here, and rightly: `particle_radius_um` is
Brindley's absorption path, and "profile broadening measures the *coherent
domain* size, which is smaller than (and unrelated to) the particle"
(`schemas/structure.py:418-426`). Whatever this WP reports must be named a
**coherent domain size** and must never be confused with it.

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

- [ ] **The physics, as one authority.** A module (peer of `model/geometry.py`)
      holding the four conversions in both directions, each citing its source and
      stating its convention explicitly, with the wavelength as an argument
      rather than an ambient. This is what everything below imports; nothing else
      restates a constant.
- [ ] **Settle the constants before writing them.** Two conventions are
      genuinely open and must not be invented: the Scherrer constant `k` (shape
      dependent; GSAS-II's slide writes `k=1`), and whether the reported
      microstrain is Δd/d or 2Δd/d — Von Dreele's `M = 180·μ·tanΘ/π` against
      Δ2θ = 2(Δd/d)tanθ implies his μ is the doubled one. Read the source, ask
      the maintainer for Langford & Wilson (1978) if the corpus lacks it (a title
      search found no size/Scherrer paper), and record the choice beside the
      constant. Prior art decides this, per the root CLAUDE.md's fence on
      invented defaults.
- [ ] **Fix the sharing map.** `phases.*.lor_size` and `phases.*.gauss_size` may
      not be one column across histograms of different wavelength. Two candidate
      shapes, and the WP picks one on measurement: normalise the shared column
      (share the size, derive each histogram's coefficient from its own λ), or
      refuse — make them per-histogram by default and raise when a caller shares
      them across differing λ. Whichever lands, **equal wavelengths must stay
      bit-identical**, since that is every existing joint fit.
- [ ] **A diagnostic, because Finding 3 says the failure is unattributed.**
      Sharing a wavelength-dependent path across differing λ is a named finding
      with the paths and the two wavelengths in it, not a silent 2.6× Rwp. Add it
      through the `GuardFinding` constructor per the root CLAUDE.md rule, and its
      row in `AGENT_PROTOCOL.md`.
- [ ] **Report the size and the strain.** `FitReport` carries a per-phase
      microstructure block: coherent domain size and microstrain with esds
      through J·Cov·Jᵀ off the final Jacobian, `None` wherever the coefficient is
      at zero, unmeasured (`ParameterTable.unmeasured_rows`) or gradient-free.
      Name it a coherent domain size, and say beside it that it is not
      `particle_radius_um`.
- [ ] **State the separability caveat where the number is, not elsewhere.** Over
      a narrow 2θ range size and strain are collinear, which the package already
      knows (`report/schemas.py:733`'s `max_template_collinearity`, and the
      Layer 2 bullet at `../DESIGN.md` 322-328). A size reported without that
      caveat is the confident wrong
      singleton the FitReport exists to refuse. Reuse the existing statistic;
      do not compute a second opinion.
- [ ] **The Gaussian/Lorentzian consistency check.** Once the conversion exists,
      compare the size implied by `lor_size` against the one implied by
      `gauss_size` (and the two strains likewise) and report a disagreement.
      Finding 5 is why; one line once the authority exists.
- [ ] **Measure `gauss_size` the way Finding 2 measured `lor_size`.** The λ²
      dependence is derived here and not measured; the joint-fit error should be
      larger. Same fixture, same control.
- [ ] **Manual + protocol.** `docs/manual/microstructure.md` gains the extraction
      it currently omits (the chapter states the laws and gives no route to a
      number), the theory manual gains the equations per the root CLAUDE.md's
      rule that a WP adding physics adds its equation to Part 2, and Part 1 gains
      the new public names or the partition fails.
- [ ] **`rietx compare` row** — the standing rule, and the cumulative Δχ² panel
      is what would localise a width change to the regions it acts in.
- [ ] Tests (unit for the conversions against hand-computed values; the
      two-wavelength joint fixture from Finding 2 with its strain control, which
      must stay in the suite as the thing that fails if the sharing regresses) +
      obs/calc/diff PNGs to `tests/output/`.

## Acceptance

A joint fit of the two-wavelength fixture recovers one crystallite size within a
stated band at **both** wavelengths, where today it lands +12.5 % / −34.5 %; the
λ-free strain control stays bit-identical; a single-wavelength joint fit is
bit-identical to today; and a converged single-pattern fit reports a size with an
esd, or `None` with a reason.

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
  constant and its shape dependence. **Not read and not in the corpus** (a title
  search returned no size/Scherrer entry); request it before choosing `k`.
- **Stephens (1999)**, *J. Appl. Cryst.* **32**, 281 — already cited in
  `crystallography/stephens.py`; relevant here because Λ(hkl) is λ-free and so
  stays correctly shared.
- **Thompson, Cox & Hastings (1987)**, *J. Appl. Cryst.* **20**, 79 — already
  cited by `model/profiles/caglioti.py` for the Gaussian size term `P`.
- Licensing: GSAS-II is the source of the *parameterisation idea* only. Concepts
  and published equations, never code.

## Handover log

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
