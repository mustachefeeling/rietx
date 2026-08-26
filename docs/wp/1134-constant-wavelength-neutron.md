# WP-1134 — constant-wavelength neutron: b, λ/n harmonics, and a refinable λ

Milestone: v1.1 · Status: ✅ 2026-08-25 — b, λ/n harmonics and a refinable λ shipped; PR #108 + #127 merged
Depends on: —

## Goal

Constant-wavelength neutron diffraction, as three changes that are one feature:
the bound coherent scattering length `b` where `f0` was, λ/n monochromator
harmonics as derived emission lines, and a wavelength that can refine where the
cell is held.  One `SCHEMA_VERSION` bump (0.6 → 0.7) because they reach a
consumer together.

**This file exists because the number did not.** The work was committed under
`WP-1128:`, which is the shipped v1.1 indexing WP
(`1128-prior-seed-before-the-gate.md`, cited from `indexing/svd.py:798`).  Two
meanings of one number costs more than a renumber, so the in-code citations
moved to 1134 — `optimize/least_squares.py`, `model/forward.py` ×2.  The commit
message prefixes are historical and were not rewritten.

## The three parts, and why each is not the obvious thing

**b, not f0.** `f0` has exactly one caller, so the amplitude is one seam rather
than a branch through the forward model.  What makes a neutron test a *neutron*
test is not that it converges: b(Al) < b(O) in fm while f(Al) > f(O) in
electrons, so a corundum pattern **peaks on a different reflection** under the
two radiations.  A test that would pass for an X-ray source is not testing the
radiation.  K = 1 and the absent dispersion channel are each a reason no new
correction code appears, and the Caglioti law *is* the neutron resolution
function (Caglioti, Paoletti & Ricci 1958) — the X-ray path is the borrower.

**Harmonics are emission lines, not a phase.** A λ/n component diffracts the
same hkl list with the same |F|², because |F|² is evaluated at sinθ/λ = 1/2d — a
property of the reflection, not of the wavelength reaching it.  A doubled-cell
phase reproduces the positions and carries the structure factors of a
fictitious cell, so its intensities are wrong.  Deriving λ/n in `lines` rather
than storing it is what keeps declaration and spectrum one fact.

**A free λ needs the cell pinned, not several histograms.** The flat direction
is λ → sλ with **a*** → s**a***, and pinning either end blocks it.  The first
implementation refused every single-histogram λ on the premise that it is
degenerate "whatever the data", which is false for a held cell — and a held
certified cell is exactly how a beamline's λ is calibrated.

## Findings

**Three defects were found by *combining* the parts, not by writing them.**

1. Folding harmonics and the refinable λ into one branch showed a derived λ/n
   does not follow a refining fundamental **in the residual**: `line_lambdas`
   read θ per line and a derived harmonic has no θ row, so it fell back to its
   frozen compile-time value.  Measured at +0.2 % on the fundamental: read
   (1.5404, 0.7702) where tracking gives (1.5434808, 0.7717404).  At the
   +258 ppm the acceptance suite finds on this instrument that misplaces the
   λ/2 peaks by up to 0.11° at 2θ = 150°, about a third of the assumed 0.30°
   FWHM — and nothing raised, because the Jacobian column agreed with the
   residual.  `HARMONIC_FRACTION` reported the same stale λ/n.
2. `Instrument.constant_wavelength_neutron` wrapped `mu_r` in a `Parameter`
   where `Geometry.mu_r` is a plain float, so **every** call passing a µR
   raised.  No test passed one.  Worse, `_resolve_specimen_absorption` runs
   automatically, so a neutron capillary was silently having an **X-ray** µR
   computed and written onto it — fenced, and WP-1132 / issue #117 specifies
   the neutron estimator.
3. The isotope convention was implemented and tested at the lookup and
   **discarded one line above it**: `compile_phase_sites` normalised species
   through the *X-ray* normaliser unconditionally, so `D`, `2H` and `7Li`
   raised "no Waasmaier-Kirfel coefficients" while the shipped Sears table has
   had b(²H) = +6.671 fm all along.  The headline neutron case.

**Validated against three codes on three datasets.** Cr₂WO₆ BT-1 c/a to
−3.4 ppm; Al₂O₃ BT-1 Rwp 0.1016 against 0.1115 at matched Rexp; Nd₂Ru₂O₇
x(O 48f) within 0.2σ of Kennedy & Vogt.  The harmonic fraction refines to
1.05 ± 0.19 % on the published Cu(311) histogram whose paper states a λ/2
contribution.  The refinable λ recovers XND 1.42's calibration on NIST SRM
640c Si to **1.26 ppm** — λ = 0.412375557 against 0.412376076(379), both about
41 ppm above the beamline's own stated 0.412359.

**Inert where it should be — the two negative controls beside the +0.2 %.**
The +0.2 % harmonic-tracking measurement in finding 1 shows the fix *acts*; two
equivalence measurements show it changes nothing where nothing should change,
which is the other half of the evidence a change inside the residual owes.
**No shipped preset frees a wavelength**: `fnmatch` of every stage's `turn_on`
glob across all seven `PLAN_PRESETS`, against
`instrument.source.lines.0.wavelength`, matches nothing — so no default plan's
behaviour moves, and a free λ is only ever a deliberate stage or a declared
`vary=True`.  **With λ held the harmonic tuple is bit-identical**:
`line_lambdas({})` `==` the compile-time `line_wavelengths` (checked with `==`,
not `approx`) for `harmonics=[2]` → (1.5, 0.75) and `[2, 3]` → (1.5, 0.75, 0.5),
so a fit that refines no fundamental reads exactly the frozen λ/n it always did.
That is the equivalence bar for a change inside the residual, and it belongs
here beside the +0.2 %: one shows the fix acts, the pair show it is silent where
it must be.

## Deliberately not in scope

- **TOF.** A bank spans a range of λ, so b(λ) would be needed near a resonance
  and µ varies inside one histogram.  Issue #113 scopes the resonant-absorption
  half at S(Q).
- **Magnetic scattering.** A discussion to raise, not a thing to implement.
- **A neutron µR estimator** — WP-1132.
- **The GUI's radiation blindness** and a `kind`-defaulting validator: named
  follow-ups rather than silent gaps.
- **`fwhm_deg` runs the seeded width wide at high angle, deliberately.** The seed
  sets both `w = (½·fwhm)²` (constant Gaussian, Γ_G = ½·fwhm) *and* `x = fwhm`
  (Lorentzian size term, Γ_L = X/cosθ), so the total width follows 1/cosθ and
  overshoots the observed FWHM — measured on a 0.3° line:

  ```
  2θ= 20  Γ_G=0.150  Γ_L=0.305  FWHM=0.369  1.23× the stated width
  2θ= 90  Γ_G=0.150  Γ_L=0.424  FWHM=0.474  1.58×
  2θ=150  Γ_G=0.150  Γ_L=1.159  FWHM=1.179  3.93×
  ```

  This is a **seed**, not a fitted profile: its one job is to size the frozen
  per-stage windows generously enough that a real neutron line — which *does*
  broaden with 1/cosθ — is captured at every angle, and erring wide is the safe
  error direction (too narrow silently loses the peak, the failure the seed
  exists to prevent). Seeding `w` alone would leave Γ_L at its ~0 default and a
  flat 0.15° window that misses a broadened high-angle line. Removing the `x`
  seed is therefore **not** behaviour-safe here: it is pinned by
  `test_profile_seed_helper_sets_both_width_terms` and the `_seeded_width`
  X-ray-comparison helper, and it moves the window sizing every acceptance fit
  with `fwhm_deg` depends on. Left as a seed; a caller wanting a faithful
  angle-independent width sets `profile.w`/`profile.x` themselves after
  construction. (Yue's 24 Aug and 25 Aug reviews.)

## Handover log

- **2026-08-25** — In review as PR #108. Yue's 24 Aug review covered the
  amplitude half; the harmonics and wavelength halves were folded in eight
  minutes later at the owner's request to unstack #112/#114, which invalidated
  the scope of that review rather than its content. His 25 Aug follow-up found
  the stale harmonic λ, the deuterium path, a red in the slow tier
  (`EmissionLine.wavelength` type change reaching an un-migrated reader), the
  WP-number collision this file resolves, and an orphan 1.5 MB data file
  committed by an over-broad `git add`. All fixed.
- **2026-08-25** — Closed the before-merge item on his 25 Aug review:
  `WAVELENGTH_CALIBRATION` now fires for the **single-histogram** held-cell case,
  not only for joint fits.  `_wavelength_calibration_diagnostics` moved to
  `refine.py` (shared with `multi.py`, which already imports its diagnostics
  from there) and grew a `pinned_by` clause and an optional `h`, because the
  message's last clause is false across the two: a single histogram measures λ
  against the **held cell**, a joint fit against the cell a held wavelength
  pins.  `refine.py` snapshots the declared λ off the pre-fit instrument and
  emits in `_build_result` for both `fit` and `run_stage`; `replay` passes none
  and reuses the node's recorded diagnostics.  `AGENT_PROTOCOL.md`'s row lost
  its `(joint fits only)`.  Measured on the Si-protocol shape (a held cell, one
  histogram generated at the true λ with the instrument declared 400 ppm below
  it): exactly one diagnostic, +417 ppm at 32× its esd, addressed at the plain
  path; a fit that frees no λ emits none; the joint tests are unchanged.  The
  two negative controls he contributed are folded into Findings above.
- **Follow-up designed, not implemented — an internal standard calibrates λ.**
  He found while verifying the fence that with **two** phases — an internal
  standard's cell HELD and the specimen's cell FREE, single histogram — a free λ
  is currently refused (declined by `set_vary`, and `check_wavelength_against_cell`
  raises naming `phases.1.cell.a`).  But λ → sλ is **not** flat there: it would
  have to scale the held standard's reciprocal lattice too, and that is held, so
  λ is genuinely measurable from the standard's positions while the specimen's
  cell refines against it.  This is the same shape as the over-restriction
  `f8e213e` fixed, one rank up: the rule should be about **which** cell is free,
  not whether *any* is.  Mixing a certified standard into the specimen is one of
  the commonest ways a wavelength is calibrated at all.  It refuses rather than
  answering wrong, so it is not a blocker — but after the last two folds it
  should be **designed, not patched**: its own future WP, in which the refusal
  message grows a third option beside "hold the cell" and "hold λ" (hold the
  cell of one phase and let λ measure against it).  Not implemented here.
- **2026-08-25** — Two follow-ups from the post-merge review of #108, in a small
  PR off `main`. (1) **`declared` is now a construction fact.** `refine.py`
  snapshotted the declared λ *per verb*, so a second λ-freeing `fit`/`run_stage`
  reported the move against the first call's answer — a value nobody declared
  (his shape: #1 +417.05 ppm from 1.539984 Å, #2 −18.15 ppm from 1.540626 Å).
  `Refinement.__init__` now snapshots once into `self._declared_wavelengths`
  (re-snapshotted only on an instrument `edit`, which *is* a new instrument; a
  `checkout` deliberately does not reset it), and both verbs report against it,
  so the second call reports the **cumulative** ppm from the truly-declared
  value — matching the joint path, which snapshotted at construction all along.
  `multi.py` now calls the shared `_declared_wavelengths` helper it had
  open-coded. (2) **The `fwhm_deg` `x` seed is recorded above** in *Deliberately
  not in scope* rather than changed: removing it breaks
  `test_profile_seed_helper_sets_both_width_terms` and moves the frozen window
  sizing, and the generous high-angle width is the safe error direction for a
  seed.
- **2026-08-25** *(reconstructed post hoc)* — PR #127's round-1 review (Yue,
  on the merged tree with `a173cb84` in) found the `branch()` bug was still
  reachable — a `branch` re-declares from `self.instrument`, which by then
  carries the parent stage's *refined* λ, reproducing the exact per-verb bug
  the construction snapshot fixed one level up (his measured shape: parent
  +417.05 ppm from the declared 1.539984, a `branch()` off it −18.15 ppm from
  the refined 1.540626 rather than the parent's cumulative +398.89) — plus
  three follow-ups, one flagged non-blocking. All four landed as
  `61cbce11..feb86b20`, same day, before merge.
  (1) `branch()` now copies `self._declared_wavelengths` onto the child after
  construction, like `_free_paths` and the ties; an `edit` on the branch still
  re-snapshots, so a branch that swaps the anode genuinely re-declares.
  `test_a_branch_inherits_the_declared_reference_from_the_root` pins his shape.
  (2) The snapshot handed to `_build_result` at both call sites (`fit`,
  `run_stage`) is now `list(...)`'d rather than aliased — not a live bug,
  closed before it becomes one.
  (3) The same shape bit a **series**, found while verifying the branch fix
  and not merely suspected: `_carry_into` warm-starts pattern *n* from pattern
  *n-1*'s refined λ, so every per-pattern `Refinement` `_fit_one` builds
  declared that refined value and reported the pattern-to-pattern drift
  instead of the calibration error. Measured on a 3-pattern synthetic series
  declared 400 ppm low: +416.8, −18.3, +1.6 ppm before the fix; +416.8,
  +398.6, +400.2 ppm after. `sequential.py` now threads the series-root
  declaration (`_declared_wavelengths(self.instrument)`) onto each pattern's
  `Refinement`, guarded on the line count so a `prepare` hook that swaps the
  anode keeps its own snapshot. The carried λ itself is untouched — every
  fitted endpoint is bit-identical before and after — only the diagnostic's
  reference moves; `SEQUENTIAL_PERSISTENT_FINDING`'s per-pattern count is
  unaffected, since it counted every λ-free pattern regardless of the ppm the
  bug was corrupting the *values*, not the count.
  (4) `AGENT_PROTOCOL.md`'s `WAVELENGTH_CALIBRATION` row now names the
  reference point: cumulative from the wavelength declared at construction,
  inherited by a `branch`, surviving a `checkout`, reset only by an
  instrument `edit`.

  Measured after all four (`[dev]`, macOS arm64, `.venv-test`,
  `PYTHONPATH=src`, jax/torch absent): ruff clean; `test_wavelength_freedom.py`
  24 passed (was 22, +2 = the branch and series tests); fast selection
  (`-m "not slow" -n 2 --dist loadgroup`, once, final tree) 2765 passed / 117
  skipped / 0 failed against the round-0 branch baseline of 2763/115 — passed
  moved by exactly the two new tests, and the skip count was independently
  measured at 117 on the same machine outside this change (env-conditional,
  not from it). Merged as PR #127 on 2026-08-26 without further review
  comment.
- **2026-08-26** — Handover repair: the entry above (PR #127's round-1 fixes,
  `61cbce11..feb86b20`) landed 2026-08-25 with no handover entry recorded;
  reconstructed it from `git log --stat` and the PR thread, and flipped
  Status to closed.
