# WP-0501 — Capillary (cylindrical) absorption

Milestone: v0.5 · Status: 🔶 in progress
Depends on: —

## Goal

A Debye-Scherrer capillary specimen carries its cylindrical absorption factor
A(µR, θ) in the Rietveld intensity chain, with µR **computed** from composition,
packing fraction and capillary radius — never refined. The deliverable is
**unbiased ADPs**: omitting the correction biases Biso low by ≈0.09 Å² at µR = 1.

## Context

### The physics, and its one load-bearing consequence

Rouse, Cooper, York & Chakera (1970), *Acta Cryst.* **A26**, 682 give the
transmission factor for equatorial reflections from a cylinder as

```
A(µR, θ) = exp{ −(a₁ + b₁·sin²θ)·µR − (a₂ + b₂·sin²θ)·µR² }

cylinder:  a₁ = 1.7133   b₁ = −0.0368   a₂ = −0.0927   b₂ = −0.0375
           max error 0.0035 over 0 ≤ µR ≤ 1     (sphere, for reference and NOT
           implemented: 1.5108, −0.0315, −0.0951, −0.2898, max error 0.0024)
```

These coefficients were verified during planning against the paper's own
four-decimal Table 1: **max error 0.0015** (the paper claims ≤0.0035), and the
table's µR→0 slope is 1.6943 against the exact mean chord of a circle
16/(3π) = 1.6977. Do not re-derive this; do not substitute another
parameterisation without re-running that check.

**The consequence that shapes everything.** That expression factors *exactly*:

```
A = K(µR) · exp( +c(µR)·sin²θ ),    c(µR) = −(b₁·µR + b₂·µR²) > 0
```

a constant times a Debye-Waller-shaped term. Projecting `ln A` onto
{1, sin²θ} leaves a residual that is **identically zero to machine precision**,
and the paper certifies that form reproduces the true physics to 0.0035 over the
whole range a real capillary occupies. So cylindrical absorption is not
*approximately* degenerate with the phase scale and Biso — it is degenerate to
below the resolution of the best published tabulation.

Therefore:

- **µR is computed and fixed, never a refinable `Parameter`.** A free µR is a
  near-singular Jacobian column that always improves Rwp and never means
  anything. This is the WP-0310 transparency trap in a sharper form.
- **The deliverable is unbiased ADPs, not a better fit.** Omitting A forces the
  fit to reproduce a calc that rises with sin²θ, which it can only do by reducing
  the Debye-Waller damping. Neglecting capillary absorption therefore biases Biso
  **low** by

  ```
  ΔB = c(µR)·λ²/2   →   0.033 Å² at µR = 0.5,   0.088 Å² at µR = 1.0   (λ = 1.5406 Å)
  ```

  Against synthetic Biso esds of 0.01–0.02 Å² that is a 4–9σ systematic. **Do not
  assert that Rwp improves** — it is the wrong yardstick here.

### Convention, stated by physics not letters

ITC Vol. C (6.3.3.1)/(6.3.3.2): the **transmission coefficient A = (1/V)∫exp(−µT)dV
is ≤ 1** and is what the forward model *multiplies* into calc; the **absorption
correction A\* = 1/A ≥ 1** is what most tables print. Rouse Table 1 tabulates
A (transmission) directly — its µR = 0 row is 1.0000 — so no inversion is needed
against that fixture. Any comparison against an A\* table must invert one side,
and A(µR=0) = A\*(µR=0) = 1 makes an identity test blind to a swap; the direction
tests (A decreasing in µR, *increasing* with 2θ) are what catch it.

### Sources and their standing

| Rung | Source | Status |
|---|---|---|
| Implementation | Rouse et al. (1970) A26 682 eq. (2), cylinder | **Verified** against the paper's own Table 1 to 0.0015 |
| Ground truth | Rouse Table 1(a)/(b): A vs µR (0.00–1.00 step 0.01) × sin²θ, 4 dp | **Usable with care** — see the transcription trap below |
| Independent physics | ITC Vol. C eq. (6.3.3.4), the exact cylinder integral | Clean; a quadrature check is citable to ITC rather than home-rolled |
| Fence rationale | ITC Table 6.3.3.1(1a): thick flat plate A = 1/2µ | Clean |
| Cross-code only | Lobanov & Alte da Veiga, as used by GSAS-II `Absorb`/TOPAS `abs_lobanov` | Coefficients trace to a **conference abstract** (6th EPDIC, P12-16) that cannot be obtained; usable only as a *tolerance* comparison, never as a golden |
| Do not use | ITC Table 6.3.3.2 (cylinder A\*), Table 6.3.3.5 (Tibballs K_m) | The available scan of 6.3.3.2 is scrambled beyond recovery (the block that follows it is a mean-path-length table, not A\* — its µR = 0 row reads 1.5000); 6.3.3.5 is only referenced, not reproduced. Rouse supersedes both for µR ≤ 1 — do not spend a session re-extracting them |

**Transcription trap, and it is not obvious.** In the available scan of Rouse
Table 1 each cell holds **five consecutive µR rows**, and the printed µR labels
are offset from the values they sit beside. Read the sin²θ = 0 column as one
continuous run and it recovers exactly 51 entries = µR 0.00…0.50 — that count is
the check that the reading is aligned. A naive read attributes each label to the
first value in its cell and shifts every µR by up to 4 steps; the symptom is that
eq. (2) then misses the table by 0.055 instead of 0.0015.

### Existing machinery to reuse, not rebuild

- `crystallography/attenuation.py` (WP-0305): `linear_attenuation(element_counts,
  volume, wavelength) -> cm⁻¹` per phase, backed by bundled
  `data/mu_McMaster.dat`. It interpolates log-log and **refuses** a wavelength
  whose grid interval contains an absorption edge, refuses outside 2–120 keV, and
  raises `KeyError` for elements absent from the compilation. Measured vs NIST
  Hubbell-Seltzer at 8 keV: ≤2.5 % for Z ≥ 9, but B −7 % and O −3.6 %
  (McMaster's low-Z weakness) — relevant if µR is ever asserted against a
  light-element standard.
- `optimize/qpa.py`: `phase_zmv(...) -> ZMV` supplies `element_counts`,
  `cell_volume` and `ZMV.density`; `_apply_microabsorption` (`qpa.py:374-414`) is
  the **catch-and-degrade-to-a-reason-string** pattern to copy verbatim for the
  estimator — it catches `(KeyError, ValueError)` from the attenuation module
  rather than letting an edge refusal abort a refinement.
- `model/extinction.py` and `model/preferred_orientation.py` are the module shape
  to follow (physics + `_and_d…` derivative twin + module docstring citing the
  reference); `tests/test_extinction.py` is the test-layering template.

### Invariants this WP must respect

- **`model/*` is xp-routed** (WP-0401): bind `xp = get_backend()` once as the
  first statement of each public function, all math via `xp.*`, `np` only as a
  dtype token. Bare `np.*` breaks the jax and torch backends silently.
- **Frozen-per-stage discreteness**: µR is resolved once at compile onto
  `CompiledModel` and never derived from θ. A itself is *not* frozen — it depends
  on `tt_bragg`, which moves with the cell — so it is evaluated per residual call.
- **µR = 0 must be bit-identical to today.** `exp(−0.0) == 1.0` and `a * 1.0 == a`
  bit-for-bit, which is what protects every existing
  `tests/data/backend_goldens/*.npz`. Never reach this by a `1 - something` form.

### Inherited

From **WP-0305** (Brindley, landed 2026-07-23): the per-phase µ machinery already
exists — reuse `crystallography/attenuation.py` rather than rebuilding, including
its edge-refusal guard and its low-Z accuracy caveat (both restated above).
Brindley acts on QPA *weight fractions*; this WP acts on the profile intensity vs
θ. They are distinct and both may be active.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24): specimen transparency was
measured on SRM 676a and deliberately **kept at 0** — freeing it is a wash
(Rwp 14.37 → 14.33 %) that merely re-apportions the correlated
{zero, displacement, t} triple. Judge new absorption terms by whether they buy
band-resolved residual structure or an unbiased physical quantity, **not by Rwp**,
and do not silently change the acceptance protocol that holds transparency at 0.
This WP's answer to that warning is to make µR non-refinable outright.

From **WP-0401** (op shim, landed 2026-07-24): `model/` is xp-routed (restated
above). A *new op* would have to land on every backend and in `_OP_NAMES`; this
WP needs only `exp`, `sin`, `radians`, `asarray`, so it adds none.

## Non-goals

- **Flat-plate absorption in any form** — fenced into WP-0508 with its formulas.
  Reflection off a thick specimen is *exactly* angle-independent (ITC Table
  6.3.3.1(1a): A = 1/2µ, no θ) and therefore identical to the phase scale, which
  is why GSAS-II returns `1.0` for its `'Bragg'` case. The finite-thickness case
  6.3.3.1(2), A = {1 − exp(−2µt·cosec θ)}/2µ, and the transmission plate
  6.3.3.1(3), A = t·sec θ·exp(−µt·sec θ) at φ = 0, do have θ-signatures but need a
  sample thickness and tilt that no schema carries.
- **A refinable µR.** See above; this is a design decision, not a deferral.
- **µR > 1.** Outside Rouse's validity; diagnosed, not extrapolated.
- **A real-data capillary acceptance.** There is no capillary dataset in
  `tests/data/` — every real pattern is flat-plate Bragg-Brentano, and 11-BM is
  fitted with the geometry-agnostic `debye_scherrer` preset, which carries no
  capillary metadata. Deferred to WP-0508; the milestone row must say
  *algorithm-level* consistency.
- Microabsorption (WP-0305, already landed) and surface roughness (WP-0502).

## Tasks

- [x] Expand this stub into a full WP before writing code
- [ ] Rouse Table 1 ground-truth fixture → `tests/data/absorption_cylinder_rouse.dat`
      + provenance row in `tests/data/README.md` (lands *before* the physics)
- [ ] `Geometry.capillary_radius_mm`, `packing_fraction`, `mu_r` — all plain
      floats, never `Parameter`; validator; `Instrument.debye_scherrer` passthrough
- [ ] `model/absorption.py`: `cylinder_absorption`,
      `cylinder_absorption_and_dmur`, `equivalent_delta_biso`, `CYLINDER_MU_R_MAX`
      + the evidence-ladder tests (Rouse fixture, ITC quadrature, 16/(3π) limit,
      µR = 0 identity, dA/dµR vs FD, direction/convention guard, **degeneracy
      pinned as a test**)
- [ ] µR estimator: `packed_mu_r` (attenuation.py), `estimate_capillary_mu_r`
      (qpa.py, catch-and-degrade), `estimate_mu_r` (refine.py, re-exported)
- [ ] Wire A into `phase_peaks` **and both** `_structural_intensity_grad` and
      `po_intensity_grad`; hidden-Jacobian guard test with its discriminating
      pre-assert
- [ ] `ABSORPTION_MU_R_OUT_OF_RANGE` / `ABSORPTION_ESTIMATE_UNAVAILABLE`
      diagnostics; report the applied µR and equivalent ΔB
- [ ] `toy_capillary` cross-backend state (new state, never edit `toy_rich`);
      capture the golden **last**, from a green tree
- [ ] ADP-bias test: µR = 1.0 injected, Biso biased low by 0.088 Å² without the
      correction and unbiased with it; PNGs to `tests/output/`
- [ ] Docs: DESIGN.md subsection, ATTRIBUTION.md rows, WP-0508 stub,
      `### Inherited` notes into WP-0502/0503, handover log, ROADMAP sync

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_absorption.py -q          # evidence ladder + ADP bias
.venv/bin/python -m pytest tests/test_backend_shim.py -q        # µR=0 is bit-identical
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_backend_conformance.py -q
.venv/bin/python -m pytest -m "not slow" -q
.venv/bin/python -m pytest -m slow -q                           # acceptance numbers UNMOVED
.venv/bin/python -m ruff check src tests examples
```

Criteria:

1. `cylinder_absorption` matches the Rouse fixture to ≤0.0035 (measured 0.0015)
   and an ITC (6.3.3.4) quadrature independently.
2. Injecting µR = 1.0 and refining **without** the correction returns Biso low by
   0.088 ± esd Å²; refining **with** it returns Biso unbiased. Rwp is not asserted
   to improve.
3. Every backend agrees per-column on `toy_capillary` inside the standing
   5e-3 rel-L2 / 0.99999 cosine bars.
4. The slow suite reports **identical** NAC / SRM 660c / FAP numbers — none of
   them sets a capillary radius, so µR stays 0 and the correction is exactly the
   identity. If any moves, it is firing where it should not.

## References

- Rouse, K. D., Cooper, M. J., York, E. J. & Chakera, A. (1970). *Absorption
  corrections for neutron diffraction.* **Acta Cryst. A26**, 682-691. — eq. (2)
  and Table 1; the implementation and its ground truth.
- *International Tables for Crystallography*, Vol. C, §6.3.3 — (6.3.3.1) A,
  (6.3.3.2) A\* = 1/A, (6.3.3.4) the exact cylinder integral, Table 6.3.3.1 the
  analytic special cases (flat-plate fence).
- Dwiggins, C. W. Jr (1975a). *Acta Cryst.* **A31**, 146-148 — cylinder A\* to
  0.1 %; the source of ITC Table 6.3.3.2. Not obtained; noted for WP-0508.
- Lobanov & Alte da Veiga (1998), 6th EPDIC abstract P12-16 — GSAS-II/TOPAS's
  fit, valid to µR ≤ 3. Cross-code reference only; coefficients unverifiable.
- Hewat, A. W. (1979). *Acta Cryst.* **A35**, 248 — states the scale × Debye-Waller
  factorisation for µr < 1 that this WP measures exactly.

## Handover log

- **2026-07-27** — expanded from a stub into a full WP and started.
  *Done:* the physics is settled and verified (Rouse eq. (2) checked against the
  paper's own table to 0.0015; µR→0 slope 1.6943 vs 16/(3π) = 1.6977), and the
  degeneracy is proved rather than assumed — `ln A` has *identically zero*
  residual after projecting out {1, sin²θ}, so ΔB = c·λ²/2 = 0.088 Å² at µR = 1
  is the entire physical content of the correction.
  *Decisions, taken with the user and not to be re-opened:* cylindrical only
  (flat-plate → WP-0508); Rouse rather than Lobanov, because Lobanov's
  coefficients trace only to an unobtainable conference abstract and carry a
  θ-dependent ~2.7 % branch step at µR = 3; **µR computed-and-fixed, not
  refinable** — this reverses an earlier working assumption once the degeneracy
  was measured, and reversing it back would reintroduce a near-singular column.
  *Gotchas:* the Rouse-table offset-label trap (above) — a naive read misses by
  0.055 rather than 0.0015; and the hidden-Jacobian hazard, since A multiplies
  the same product that `_structural_intensity_grad` and `po_intensity_grad`
  rebuild by hand.
  *Next:* the ground-truth fixture, then the schema.
- **2026-07-22** — created as a stub from the ROADMAP split.
