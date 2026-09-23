# WP-1312 — CW neutron follow-through: the seed, the resonant flag, the joint fit

Milestone: unscheduled · Status: ⬜ — tasks 1-2 and the #271 row landed from outside (PRs #280, #282, #427); tasks 3-4 and the #268/#276 rows open
Depends on: — (WP-1132 is the maintainer's and does not gate any task here)
Priority: P2 2026-09-23 — a resonant absorber's b is mis-tabulated in silence, on a path few fits run

## Goal

The three loose ends the CW-neutron landing left are closed: the
`constant_wavelength_neutron` seed matches its own docstring, a resonant
absorber in a structure is named instead of silently mis-tabulated, and a
combined X-ray + neutron joint refinement is exercised, verified and
documented rather than merely admissible.

## Context

From issues #124 (maintainer-filed, fix stated), #113 item (a) (the cheap
slice; the rest is fenced), and #194 (verify, don't build).

**1. The seed (issue #124).** `Instrument.constant_wavelength_neutron(...,
fwhm_deg=...)` seeds `w = (0.5·fwhm)²` *and* `x = fwhm`. `w` gives a constant
Γ_G = fwhm/2, which is right; `x` is the Lorentzian Scherrer term
Γ_L = X/cosθ, so the full-FWHM seed both double-counts the width and makes it
strongly angle-dependent. Measured at fwhm_deg = 0.3, the seeded TCHZ FWHM
is 0.369° at 2θ = 20 (1.23×), 0.405 at 60, 0.474 at 90, 0.637 at 120,
**1.179 at 150 (3.93×)** — over exactly the high-angle peaks a CW neutron
cell refinement leans on hardest. Not a correctness bug (the terms refine
afterwards; every #108 fit converged) but three things make it worth fixing:
the docstring promises the observed width; the frozen per-stage windows are
sized from the seed, so the over-width is paid at every stage compile; and
the shape is wrong as well as the size — a real CW neutron resolution
function is narrowest near the focusing angle (Caglioti, Paoletti & Ricci
1958), and a monotonically widening seed is not a coarse version of that.
**Fix: seed `w` alone**; test asserts the seeded FWHM stays near `fwhm_deg`
across 20–150°, not only at low angle; a line in WP-1134's record.

**2. The resonant flag (issue #113 item a).** `crystallography/neutron.py`'s
Sears table ships `RESONANT_ABSORBERS` (Cd, Sm, Eu, Gd). Natural Yb belongs
in it: σ_abs 34.80 barn (14× Ru's 2.56) with an isotopic spread of nearly
three orders (¹⁶⁸Yb 2230.40 vs ¹⁷⁶Yb 2.85 barn) — absorption that large and
that isotope-dependent *is* a nuclear resonance, and a resonance is
energy-dependent, which the thermal table cannot express (the module's own
fence says so). The cheap, honest slice: add Yb, and emit a diagnostic when a
resonant absorber sits in a refined structure — the neutron analogue of
"this wavelength straddles an absorption edge", needing only the species
list plus a cited resonance energy per nuclide. The energy-dependent
correction itself (σ_abs(λ), the S(Q)-level utility) **stays fenced** with
TOF; issue #113 holds that design.

**3. The joint fit is admissible and unexercised (issue #194).**
Multi-histogram refinement ships (`multi.py`, WP-0308) and is stacked per
Von Dreele (1997), *J. Appl. Cryst.* **30**, 517 — the combined
X-ray/neutron paper itself. Nothing in `params/multi.py` restricts radiation
kind, and CW neutron landed in WP-1134 — so a mixed fit is structurally
admissible **today**, and no test or example runs one. Three tasks the issue
lists: an acceptance/example of a genuine X-ray + neutron joint fit on one
shared structure (source a public dual dataset — search the maintainer-local
paper corpus before asking); an audit that per-histogram physics keys on the
histogram's **own** radiation across a mixed fit (anomalous dispersion — on
by default, X-ray-only — must no-op cleanly on the neutron histogram; b vs
f(Q); polarization vs none; the WP-1134 paths); and a check that the
shared-vs-per-histogram parameter split holds when the two histograms weight
structure factors differently. WP-1134's own log notes three defects found
only by *combining* parts on a single path — the same argument for
exercising this combination.

### Inherited

- **2026-09-23, from the issue triage (issue #276).** The reporter claimed
  #276's row on the thread and opened PR #429 the same day ("the neutron
  preset builds its profile in a coarse-instrument box; a bare wide width
  still refuses by name"). The PR covers #276 only; #268's row is unclaimed.
  Reviewing it is `/pr-review`'s.
- **2026-09-16, from [1118](1118-foreign-model-files.md): there is now a real
  CW-neutron instrument to start from.** `rx.read_gsas2_instprm` reads a
  GSAS-II `.instprm` into a frozen `Instrument`, and `tests/data/gsas2_hb2a.instprm`
  is HFIR's HB-2A at λ = 2.40627 Å with its refined Caglioti terms, its zero
  and its axial divergence. Task 3's joint fit needs a neutron histogram's
  instrument from somewhere; this is one nobody here invented, and its widths
  (U = 0.0799, V = -0.0444, W = 0.0242 deg²) are a real reactor
  diffractometer's rather than a seed.
- **2026-09-02, from the magnetic scattering track
  ([1327](1327-magnetic-structure.md)): the joint-fit audit gains a third row
  when the moment lands.** Task 3 here audits that per-histogram physics keys
  on the histogram's own radiation (dispersion no-ops on the neutron arm, b
  against f(Q), polarisation against none). 1327 adds a magnetic term that
  enters a `neutron_cw` histogram only and is identically zero on an X-ray
  one, so shape the audit as a table keyed on the source kind that a new
  term joins with one row, rather than three hand-written checks. Nothing to
  build here for it now.
- **2026-09-03, from the issue triage (issue #252): the joint fit has now
  been exercised from outside.** An outside campaign ran a converged
  two-histogram X-ray + neutron fit on one shared structure (41 free
  parameters, Rwp 0.088, GoF 1.47) — evidence for task 3's "admissible and
  unexercised", though not the audit it asks for. What that run found missing
  is reporting and telemetry (`summary`/`report`, `events=`,
  `max_shift_over_esd`), which is
  [1341](1341-a-joint-fit-has-no-report.md), not this WP.

- **2026-09-15, from the issue triage (issues #271, #268, #276): three
  neutron rows for the follow-through.**

  **#271 — `read_recipe` refuses `PNC` with a clause that is true only of
  TOF.** `io/recipe.py` (WP-1306) reads a PowderLine recipe whose instrument
  block is GSAS-II's, and refuses any `Type` other than `PXC`, saying `'PNC' neutron and every time-of-flight type put a different
  quantity on the x axis than PatternData holds`. False for `PNC`: a
  constant-wavelength neutron histogram's axis is 2θ in degrees, and the
  package has refined that radiation since WP-1134. `PNC` differs from `PXC`
  only in the source arm (`NeutronSource`, polarisation pinned at 1, no
  emission lines), and `Lam` from `Iparm1` is the neutron λ. Ask: a `PNC`
  recipe builds a `constant_wavelength_neutron` instrument and refines; the
  TOF types keep their refusal with a message naming only them. This is
  task 3's "admissible" contradicted at the recipe door, so it is this WP's
  row. The recipe reader is a build-wide feature and not a `PROJECT_FORMATS`
  row (`io/projects/registry.py`'s docstring), so nothing in 1118's registry
  moves with it.

  **#268 — `docs/manual/intensities.md` contradicts itself on b.** Line 73:
  "b is real for every nuclide this table covers". Line 94, same section:
  for the resonant absorbers "b is complex". Sears gives ¹⁵⁷Gd as
  b = −1.14 − 71.9i fm and `b_Sears.dat` stores the real part only, which is
  the fact the first sentence reaches for. One clause fixes it: every value
  the table *stores* is real; for the resonant absorbers b is complex and
  the table carries its real part, which `NEUTRON_RESONANT_ABSORBER` names
  since PR #282. Task 2's manual half. The reporter's audit of 30 stated
  values across the tree against Sears 1992 (via gemmi's `neutron92`) found
  only the Nd/Ru transposition of #254; this prose claim was the only other
  thing.

  **#276 — `constant_wavelength_neutron(fwhm_deg > 1.0)` raises on its own
  bound, and the 2026-09-11 ruling above already answers it.** Before PR
  #280 the seed `x = fwhm` tripped `profile.x`'s `max = 1.0`; after it,
  `w = fwhm²` trips `w`'s at the same threshold. The ruling stands: the
  bound stays, the constructor refuses by name with the per-`Parameter`
  escape. What #276 adds is the measured case the refusal must be shown to
  cover. The public APDW Co₃O₄ set (ILL D1B, λ = 2.52 Å) has a strongest
  line of 1.10° FWHM, Caglioti 2.26° at 124° 2θ, and its FullProf `.pcr`
  carries U = 1.576, V = −0.501, W = 0.475, outside `ProfileTCHZ.u`'s
  default `max = 1.0` too. With every width bound widened by hand (u ∈
  [−0.5, 8], v ∈ [−4, 4], w/x/y ≤ 8) it converges to U = 1.654 ± 0.051 at
  Rwp 0.0074. So the refusal's escape has to build *that* instrument (five
  bounds, not one), the neutron chapter states it, and a bare
  `ProfileTCHZ(u=1.576)` refusing is the ruling's cost, said out loud. Use
  the D1B numbers as the refusal test's fixture (its licence per
  `tests/data/README.md`); 1415 uses the same file.

## Non-goals

- **Not the neutron µR estimator** —
  [1132](1132-neutron-specimen-absorption.md), the maintainer's, checklist
  already written. Its absence does not gate any task here (declare no µR on
  the neutron histogram in the example, as every fit does today).
- **Not σ_abs(λ), S(Q) reduction, or anything TOF** — fenced; issue #113
  holds the design.
- **Not new physics.** Every task verifies, seeds, or names; none adds a
  correction.

## Tasks

- [x] Seed fix: `w` alone; the 20–150° FWHM assertion; the WP-1134 record
      line. Landed from outside as PR #280 (`9d8b7043`, 2026-09-16), with the
      `ProfileTCHZ.w` bound decided 2026-09-11 and the refusal built on it.
      See the 2026-09-16 entry.
- [ ] ~~Yb into `RESONANT_ABSORBERS`; the resonant-absorber diagnostic;
      skill row~~ — landed from outside, PR #282 (`8c39a02c`). **Left: a
      cited resonance energy per member**, which that PR deliberately
      declined for want of a citation (2026-09-11 entry).
- [ ] The mixed-fit acceptance/example (public dual dataset, provenance row)
      + the radiation-kind audit, any fix it forces landing as its own
      commit; obs/calc/diff PNGs for both histograms to `tests/output/`.
- [ ] Manual: the joint-refinement section states what is shared, what is
      per-histogram, and which corrections key on radiation kind.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_neutron_cw.py tests/test_multi_histogram.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: the seeded FWHM tracks `fwhm_deg` across the range; the diagnostic
fires for an Yb-bearing structure and is silent for Ru/O; the mixed fit
refines one structure against both histograms with dispersion active on the
X-ray one only, and the audit's findings (if any) each carry a test.

The shipping PR carries `Closes #124`, `Closes #194`, and a comment on
issue #113 saying its (a) slice landed — #113 stays open for the fenced
(b)/(c) halves.

## References

- Issues #124, #113, #194; PR #108 / WP-1134 — where the seed and the fence
  landed.
- Caglioti, G., Paoletti, A. & Ricci, F. P. (1958), *Nucl. Instrum.* **3**,
  223 — the CW neutron resolution function.
- Von Dreele, R. B. (1997), *J. Appl. Cryst.* **30**, 517 — combined X-ray +
  neutron Rietveld refinement.
- Sears, V. F. (1992), *Neutron News* **3**(3), 26 — the shipped table.

## Handover log

### 2026-09-23 — the #271 row landed from outside; a `PNC` recipe now builds

`read_recipe` now reads a GSAS-II `PNC` instrument block rather than refusing
it. That is the #271 row of the 2026-09-15 inheritance, live since PR #427
merged (`90d4663e`, closing #271). Like tasks 1 and 2 it arrived from an
outside contributor with no `WP-NNNN:` prefix and no touch of this file. The
WP stays `⬜`: tasks 3 and 4 are untouched, the #268 and #276 rows are open,
and no session owns it.

**What the merge makes possible.** A `PNC` recipe builds
`NeutronSource(wavelength=Lam)` and refines. The λ-flag refusal runs before
the source is built, so a flagged neutron wavelength is refused as an X-ray
one is. `NeutronSource.dispersion` is `None`, so the recipe's
`_decline_dispersion` returns before any Cromer-Liberman lookup. A stated
`Polariz.` is reported as `RECIPE_FIELD_DROPPED`, and a refine flag on it is
refused. The ground is GSAS-II's `GetIntensityCorr`, which applies the
factor only to an X-ray type, and `io/instrument_profile.py` already reads a
`PNC` `.instprm` bank on it. Each other type now has its own refusal:
`PNT`/`PXE` for the axis, `PXB`/`PNB` for the profile function, and an
unknown code as unknown. The list lives in `RECIPE_TYPES` and
`_REFUSED_TYPES`, outside `__all__`.

**What it deliberately does not do.** The test recipe is the LaB6 X-ray
fixture relabelled `PNC`, so it pins the source arm and that the fit runs,
and its Rwp means nothing. No real neutron recipe is in the tree. Task 3's
mixed-fit example would be the first place one could be exercised.

**Two loose ends, posted as non-blocking follow-ups on the PR.** The
diagnostic's `where` always names `initialization[0].Polariz.`, even when
only `parameterization.polarization` carried the value. The module
docstring's `RECIPE_FIELD_DROPPED` paragraph lists `Z = 0` and the hump γ,
and omits this case. It is a dropped value that is not at the model's
identity, justified because it is inert in GSAS-II too.

**Measured on the merged tree** (darwin/arm64, python 3.12, `[dev,jax]`,
nothing else running): fast suite 5925 passed, 84 skipped; full `-m slow`
191 passed, 7 skipped, 1 xfailed; `ruff` and the `-W` manual build clean.

### 2026-09-16 — task 1 landed from outside; the seed is the width you asked for

`Instrument.constant_wavelength_neutron(fwhm_deg=...)` now seeds `w` alone, at
`fwhm_deg ** 2`, and leaves `x` at its default. That is task 1, live in the
package since PR #280 merged (`9d8b7043`), and like task 2 it arrived from an
outside contributor with no `WP-NNNN:` prefix and no touch of any file under
`docs/wp/`. This entry exists because nothing in the tooling would have asked
for one. The WP stays `⬜`: tasks 3 and 4 are untouched and no session owns it.

**What the fix buys.** With U = V = 0 the Caglioti law gives Γ_G = √W, so
`W = fwhm²` reproduces the stated width at every angle. Measured on the merged
tree at `fwhm_deg = 0.30`, the Gaussian width reads 0.30000 at 2θ = 20, 60,
100, 140 and 150, against the old seed's 1.179° at 150 (3.93×). The Lorentzian
stays at its default 0.001, worth 0.3 to 0.7 % of the line. The frozen
per-stage windows are sized from the seed, so the over-width is no longer paid
at every stage compile.

**What it deliberately does not do.** The `ProfileTCHZ.w` bound stays at
`max = 1.0` deg², which caps `fwhm_deg` at 1.0° where the old seed accepted
2.0°. The 2026-09-11 decision declined widening it, because `min`/`max` are
serialised fields and refinement bounds both, so raising the schema default
would move the search box of every newly built instrument. Instead
`constant_wavelength_neutron` raises before assigning, naming `fwhm_deg`, its
value, the `w` it would have seeded, the bound and the escape hatch. It reads
the bound off `inst.profile.w.max` rather than restating `1.0`, so the message
follows the field. The fence is inclusive: `fwhm_deg = 1.0` builds. A genuinely
coarser instrument is declared by setting `instrument.profile.w` explicitly
with its own bounds, which round-trips through JSON with that bound intact.

**The gotcha the review turned up, and it is still open.**
`indexing.workflow.seed_widths` does `out.profile.w.value = float(measured **
2)`, the same seed and the correct idiom, with no fence in front of it. Built a
peak list whose median FWHM is 1.4° and called it:

```
pydantic ValidationError: value 1.9599999999999997 lies outside bounds [0.0, 1.0]
```

That is issue #124's defect in pydantic's own words, one module over, and it
fires during an indexing run rather than at a constructor argument the caller
typed. It is reached from `index_pattern` (`workflow.py:423`) and from
`extinction.py:714`, so a coarse enough pattern takes the whole search down
with a message about a Caglioti coefficient. This is on `main` today, and
PR #280 neither causes it nor worsens it. Whoever picks up this WP should close
it as one class with the constructor, since the fence and its message already
exist next door. Smaller: `docs/manual/using/data.md` describes the seed well
and does not mention the 1.0° ceiling, which only the docstring carries.

**Measured** (bench worktree, `[dev,jax]`, macOS arm64, `-n auto --dist
loadgroup`, nothing else in the suite), on PR #280 merged onto `origin/main`
`ad6085c9`:

| | measured |
|---|---|
| fast selection | 5122 passed, 82 skipped, ~2m41s |
| fast selection, main alone | 5115 passed, 82 skipped, ~3m18s |
| `-m slow` on the merged tree | 176 passed, 7 skipped, ~32 min |

+7 passed and no new skip, which is exactly the seven test cases the diff adds
(three parametrised width cases, the Lorentzian check, and three around the new
ceiling). The bench venv reads `1.4.0`; the contributor's reported
`test_skill.py` metadata failure is a stale editable install on their bench and
does not reproduce here.

**Next** for this WP is unchanged from the 2026-09-11 entry, minus the #280
line: comment on #113(a), then task 3, whose first open item is still sourcing
the public X-ray + neutron dual dataset.

### 2026-09-11 — two of the three tasks landed from outside, and this WP never opened

A CW neutron refinement now tells you when the structure contains an element
whose tabulated scattering length cannot describe it. That is task 2, live in
the package since PR #282 merged (`8c39a02c`), and it arrived from an outside
contributor rather than from a session on this WP — which is why this entry
exists at all: nothing in the tooling would have asked for one, because the
merged commits carry no `WP-NNNN:` prefix and the merge touched no file under
`docs/wp/`. Task 1, the seed fix, is PR #280, reviewed and held on one
decision that is recorded below. The WP itself stays `⬜`: no session owns it,
and the two remaining halves are real work rather than paperwork.

**Done — task 2, in part.** `RESONANT_ABSORBERS` gains natural `Yb` and
`168Yb`, and `refine._resonant_absorber_diagnostics` emits
`NEUTRON_RESONANT_ABSORBER` when such a species sits in a structure being
refined against a non-X-ray source. It reports and never refuses, because one
constant wavelength away from the resonance the thermal value is the right
number. Severity splits on `RESONANT_ABSORBER_SEVERE_BARN = 1000.0`: `warning`
for the four classic black absorbers (Cd 2520, Eu 4530, Sm 5923, Gd 49700),
`info` for Yb, whose element absorbs 34.80 and whose resonance lives in the
0.13 % minority `168Yb` at 2230.40. The skill row landed in all three
committed copies.

**Deliberately not done, and this is what keeps the task open.** The checklist
asks for "a cited resonance-energy entry per member" and the PR ships none.
The reason given is the right one: the energies need a citation this package
does not carry (Mughabghab, *Atlas of Neutron Resonances*, is the usual
source) and transcribing them from memory is a failure this campaign has
already met once. So the flag says *that* a species is resonant and cannot yet
say *where*. Whoever picks this up needs the Atlas or an equivalent, and the
maintainer-local paper corpus is the first place to look.

**Measured** (bench worktree, `[dev,jax]`, macOS arm64, `-n auto --dist
loadgroup`, nothing else in the suite), on PR #282 merged onto `origin/main`
`ff69ec34`:

| | measured |
|---|---|
| fast selection | 4534 passed, 78 skipped, ~2m14s |
| fast selection, main alone | 4529 passed, 78 skipped, ~2m31s |
| full suite including `-m slow` | 4703 passed, 83 skipped, ~23 min |

+5 passed, no new skip — exactly the five new test functions. The full run is
the one that carries: `ci.yml` runs `-m "not slow"` and `nightly.yml` has no
`pull_request` trigger, so no acceptance suite ever sees a PR.

**Decided — task 1's held item (2026-09-11).** PR #280 seeds `w = fwhm_deg²`,
which is right, and in doing so narrows the widths the constructor accepts:
`ProfileTCHZ.w` declares `max = 1.0` deg², so the old `(0.5·fwhm)²` accepted
`fwhm_deg` up to 2.0° and the correct seed accepts 1.0°. **The bound stays at
1.0 and the constructor refuses by name.** Three reasons, in the order they
decided it:

1. *The narrowing is nominal.* The old upper range never produced a correct
   profile — at `fwhm_deg = 2.0` the old seed gave Γ_G = 1.0°, half the width
   asked for, plus a Lorentzian `X = 2.0` climbing as 1/cosθ. Nothing correct
   is being taken away.
2. *Widening is not local.* `min`/`max` are serialised fields and refinement
   bounds both, so raising the schema default changes the search box of every
   newly built instrument, laboratory X-ray included, where `help.py` puts the
   typical `w` at 0.001-0.02 — 1.0 is already 50× the top of that range. It is
   also an observable change to a serialised default, which under the
   bump-per-observable-change rule owes a `SCHEMA_VERSION` bump. That is a
   broad cost for a rare case.
3. *The rare case is already expressible.* The bound is per-`Parameter`, not
   global: `inst.profile.w = Parameter(value=1.44, min=0.0, max=4.0,
   unit="deg^2", transform="softplus")` works today and round-trips through
   `model_dump`/`Instrument(**d)` with `max = 4.0` intact (verified on
   `8c39a02c`). A genuinely coarse instrument states itself explicitly, which
   is the right place for that claim to live.

What is actually defective is the message. `fwhm_deg = 1.2` currently dies in
pydantic naming `w` and the number 1.44, neither of which the caller typed.
The fix asked for on #280 is a refusal in the constructor naming `fwhm_deg`,
its seeded `w`, the declared bound read off the field rather than restated,
and the one-line escape above.

**Gotcha for task 3, found while reviewing #282 and worth more than the PR
that found it.** `_dispersion_diagnostics` is called only from `Refinement`
and never from `multi.py`, so a joint fit loses `DISPERSION_NEGLECTED`
entirely — and the new `_resonant_absorber_diagnostics` is wired in beside it
and inherits exactly that gap. This is task 3's "audit that per-histogram
physics keys on the histogram's own radiation" arriving as a concrete defect
rather than a hypothesis. It is **not** being fixed here: WP-1344, open in
PR #297, owns how `multi.py` decides which diagnostics a histogram is
entitled to. No `### Inherited` note has been pushed there because that WP's
file does not exist on `main` yet and a live session holds it.

**Gotcha — the closing protocol no longer fits.** This WP's Acceptance
section assumes one shipping PR carrying `Closes #124`, `Closes #194` and a
comment on #113. The work is arriving piecemeal from outside instead: PR #282
covers #113(a)'s species half, #280 covers #124, and #194 is untouched.
Issue #113 still needs its comment saying the (a) slice landed, and it has
not been posted.

**Next**, in order: settle #280 with the named refusal and merge it, which
closes task 1 and issue #124; comment on #113(a); then task 3, whose first
open item is still sourcing the public X-ray + neutron dual dataset, now with
the `multi.py` diagnostics gap above as a known finding waiting for WP-1344.

- **2026-09-01** — created, from issues #124/#113(a)/#194 (2026-09-01
  triage). Settled: three verbs — fix the seed, name the absorber, exercise
  the joint fit; first open item is sourcing the public X-ray + neutron
  dual dataset.
