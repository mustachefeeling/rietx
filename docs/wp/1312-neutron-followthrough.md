# WP-1312 — CW neutron follow-through: the seed, the resonant flag, the joint fit

Milestone: unscheduled · Status: ✅ 2026-10-02 — tasks 1-4 and the #268, #271, #276 and #437 rows landed from outside (PRs #280, #282, #427, #429, #452, #526, #530); the resonance energies landed 2026-10-02 (ENDF/B-VIII.0); the #113 comment posted
Track: The specimen is not an angle, and the neutron follow-through
Depends on: — (WP-1132, claimed by @mustachefeeling in PR #541, does not gate any task here)

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
- [x] Yb into `RESONANT_ABSORBERS`; the resonant-absorber diagnostic;
      skill row — landed from outside, PR #282 (`8c39a02c`). The cited
      resonance energy per member landed 2026-10-02: lowest positive
      resonance of each nuclide from ENDF/B-VIII.0 (the supplied Atlas PDF
      stops before its per-nuclide tables), `RESONANCE_ENERGY_EV` /
      `resonance_wavelengths`, quoted in the diagnostic's message.
- [x] The mixed-fit acceptance/example (public dual dataset, provenance row)
      + the radiation-kind audit, any fix it forces landing as its own
      commit; obs/calc/diff PNGs for both histograms to `tests/output/`.
      Landed from outside as PR #530 (`406667ed`, 2026-09-29); see that
      day's second entry.
- [x] Manual: the joint-refinement section states what is shared, what is
      per-histogram, and which corrections key on radiation kind. Same PR.

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

### 2026-10-02 — the resonant-absorber flag now says where the resonance is

A neutron refinement of a structure holding Cd, Sm, Eu, Gd or Yb used to be
told only that the scattering length is incomplete near a resonance. It is now
told where the lowest resonance sits, as an energy and as a neutron
wavelength, beside the instrument's own wavelength. For Gd the two resonances
are at 1.75 Å and 1.61 Å, close to the 1.798 Å thermal wavelength. That is why
the flag matters most on a reactor instrument near 1.5-2.5 Å. The package
still does not judge whether a given wavelength is too near, because that needs
the resonance width, which it does not carry.

- *Done*: `RESONANCE_ENERGY_EV`, `resonance_wavelengths()` and
  `NEUTRON_LAMBDA_EV_ANGSTROM` in `crystallography/neutron.py`; the
  `NEUTRON_RESONANT_ABSORBER` message quotes them (`refine.py`). Two tests in
  `tests/test_neutron_cw.py`, one crossing every `RESONANT_ABSORBERS` member
  against the energy table. Two stale sentences in the manual
  (`corrections.md`, `using/data.md`) and one in the `total_cross_section_neutron`
  refusal message now say what is true. The Inherited section was pruned on
  arrival: every row (#271, #268, #276, #437, the joint-fit audit) had landed.
- *Source, and why it is not the Atlas.* The values are the lowest
  positive-energy resonance of ¹¹³Cd 0.1787, ¹⁴⁹Sm 0.0973, ¹⁵¹Eu 0.321,
  ¹⁵⁵Gd 0.0268, ¹⁵⁷Gd 0.0314 and ¹⁶⁸Yb 0.597 eV, read from the MF2/MT151
  records of the ENDF/B-VIII.0 files (IAEA-NDS download, 2018 retrieval). The
  Atlas PDF in the Zotero library (`XIHREUPV`, 153 pages) ends at the
  bibliography on printed page 136, so its per-nuclide tables are absent. The
  full volume then turned up (`~/Downloads`, 1008 pages). It matches ¹¹³Cd
  (0.178 eV), ¹⁴⁹Sm (0.0973) and ¹⁶⁸Yb (0.597). It lacks the ¹⁵⁵Gd pages and
  ¹⁵⁷Gd's first ones (printed 64-5 to 64-12 are not in the scan), and ¹⁵¹Eu
  was not found by text search. Those three rest on ENDF alone, and the code
  comment and `ATTRIBUTION.md` say so. Pages 64-5 to 64-12 from another copy
  would close it.
- *Deliberately not done*: the refusal in `total_cross_section_neutron` stays
  at every wavelength for every listed absorber. Loosening it needs a width and
  a measured departure from 1/v, and nothing here measures either.
- *Measured* (macOS arm64, `[dev]` without jax or torch, `-n auto --dist
  loadgroup`): fast selection 7922 passed, 159 skipped, ~5 min on the first
  run, which was alone; the re-run after review, with another session's suite
  running beside it, took ~8.7 min and so is not a timing. Two tests added,
  each ~0.00 s in the junit file, so neither joins the slow tail. The full
  selection did not run: nothing here moves a measured number, because the
  only change is message text and a data table. One test failed on the
  re-run, `test_skill.py`'s budget, because I had added a sentence to the
  skill row. The row's file was already over budget, so I reverted it. The
  package's own message carries the fact, which the placement rule ranks first.
- *Review (`/code-review high --fix`)*: no correctness bug. Applied: a comment
  that overclaimed an Atlas cross-check (now states what was and was not
  checked), an `ATTRIBUTION.md` entry for the ENDF values, and the `sits`
  list ordered like `named` in the message. Taken afterwards: the carriers
  table is now crossed against `RESONANT_ABSORBERS` in the test. Declined: the
  skill-row edit (above), deriving `NEUTRON_LAMBDA_EV_ANGSTROM` from
  `scipy.constants` (the test pins it to the 1.798 Å already shipped), a manual
  line wrap, and rewording the refusal message.
- *Gotchas*: a nuclide with a bound level (¹⁴⁹Sm at -1.127 eV, ¹⁵¹Eu at
  -0.0609 eV) is not given a second entry. The file's resonance range may end
  well above the lowest level, so the lowest *positive* one is the right pick.
- *Next*: none; the WP is closed. The #113 comment was approved and posted
  (issue comment 5962375054) and #113 stays open for the fenced (b) and (c)
  halves. The Priority line is gone and the narrative moved to the v1.6
  record. Pages 64-5 to 64-12 of another Atlas copy would let the ¹⁵⁵Gd and
  ¹⁵⁷Gd energies be checked against it.

### 2026-09-29 (2nd session) — tasks 3 and 4 landed from outside; #194 closes

A joint fit of an X-ray and a neutron histogram now has an audit that says
which corrections key on each histogram's own radiation, and the manual says
what such a fit shares. It arrived as the contributor's PR #530, reviewed over
two rounds and merged as `406667ed` in a `/pr-review` run, closing #194. It was
gated in one stack with #536, which shares no file with it.

- *Done*:
  - **The audit is a table keyed on the source kind.** It is
    `RADIATION_KEYED` in `tests/test_joint_xray_neutron.py`, with five rows:
    b against f₀(s), dispersion, polarisation K, the magnetic structure
    factor, and the capillary µR estimate. Each row reads the joint fit's own
    compiled models. A new member of `Instrument.source`'s union fails
    `test_every_row_answers_for_every_source_kind` until every row answers for
    it.
  - **The fix the audit forced landed in its own commit.**
    `MultiParameterTable.set_vary` and `seed_softplus` had returned a shared
    path once per histogram, so `StageResult.freed` listed each shared column
    twice. No number moved, because the vary flags were always right.
  - **The weighting split.** One corundum structure against a synthetic
    X-ray and a synthetic neutron pattern. Neutron sharpens x(O) (joint esd
    ×0.66 of X-ray alone) and adds almost nothing on z(Al) (×0.955).
  - **Task 4.** `using/series.md` § "Two radiations in one fit", and the
    agent skill's `surprises.md` §8.30.
  - **The real-data mixed fit was already here.** It is
    `test_acceptance_wavelength.py::_joint` (Nd₂Ru₂O₇, 11-BM + BT-1, the
    `mg090.*` files, with its PNGs). The PR adds no data.
- *Review round 1* asked for one change. The pinned bars inherited
  `Source.dispersion`'s default, so `_xray()` now declares `Dispersion()`
  explicitly. The Linux x86_64 numbers now sit beside the macOS seed spread in
  both docstrings, and `joint_al > 0.9` is the bar with the least margin,
  about 0.05.
- *Measured* (review, Linux x86_64, 4 cores, Python 3.12.3, `[dev,jax]`
  bench venv, run as root, on `origin/main` `5ac3fc0` + #536 + #530): fast
  6842 passed, 111 skipped. The fast run was on `a332029b`; #542 then moved
  main by four markdown files, and the docs, skill and hook tests were re-run
  on the rebuilt tree, 275 passed. `-m slow`: 229 passed, 14 skipped, and 1
  failed, `test_held_phase.py`'s ramp runaway guard (137.9 s against 60 s;
  it passes alone in 18.6 s; WP-1420's). `-W` build clean.
- *Not done*: the diagnostics gap is only pinned, not wired.
  `DISPERSION_NEGLECTED`, `NEUTRON_RESONANT_ABSORBER` and
  `SPECIES_FALLBACK_NEUTRAL` are never raised on a joint fit. That wiring is
  WP-1344's, and the manual section and §8.30 say so. `HistogramResult`
  names no radiation (#252, WP-1341). No neutron µR is built: WP-1132, now
  claimed by @mustachefeeling in #541.
- *Next*: task 2's cited resonance energy per `RESONANT_ABSORBERS` member.
  The comment on #113 saying its (a) slice landed is still unposted.

### 2026-09-29 — the #268 row landed from outside

The manual no longer contradicts itself about whether a neutron scattering
length can be complex. `intensities.md` now says what is true of the stored
table, that every value in it is real. It then says that for the resonant
absorbers b is complex and the table carries its real part, which is what
the thermal-table bullet below it already said. A reader who looks up
whether b can be complex gets one answer instead of two. It arrived as the
contributor's PR #526, reviewed and merged as `677fbb13` in the
`/pr-review all` run of 2026-09-29. It closed #268, and it is the manual
half of task 2 as the 2026-09-15 triage placed it.

- *Done*: one clause under the b = b_coh equation, #268's suggested text in
  two sentences. It is prose only: no fenced constant, substitution or
  *Source* line moves.
- *Measured* (review, Linux x86_64, 4 cores, Python 3.12.3, `[dev,jax]`
  bench venv, run as root, on the merged tree): `test_docs_consistency`,
  `test_manual` and `test_manual_api` gave 63 passed. The `-W` Sphinx build
  exits 0 and the built `intensities.html` carries the clause. `-m slow`
  gave 226 passed, 15 skipped and 1 failed in 52:30. The one failure was
  `test_held_phase.py`'s wall-clock runaway guard (138.3 s against 60 s on
  a loaded 4-core box). It failed on the base tree too and passes alone in
  18.85 s.
- *Not done*: the triage note's suggestion to point the clause at
  `NEUTRON_RESONANT_ABSORBER`. The manual names that code nowhere, and the
  PR followed the issue's text. Optional. Task 2's other half, a cited
  resonance energy per member, is unchanged.
- *Next*: tasks 3 and 4, the mixed-fit acceptance and the joint-refinement
  manual section, both still unclaimed.

### 2026-09-24 — the #437 row landed from outside; a type-3 PNCR `.prm` reads

`rx.read_gsas_prm` now reads a constant-wavelength neutron `.prm` whose
profile is type 3. It builds `Instrument.constant_wavelength_neutron` at
`LAM1` and maps the eight `PRCF` coefficients exactly as it does for `PXCR`.
That is the #437 row of the 2026-09-24 inheritance, live since PR #452 merged
(`28ed67af`, closing #437). It arrived from an outside contributor with a
`WP-1312:` commit and no touch of this file. The WP stays `⬜`: tasks 3 and 4
are untouched, the #268 row is open, and no session owns it.

**What the merge makes possible.** The `PRCF` type decides what reads, under
either `HTYPE`, and it is checked before `ICONS`. A type-1 file is refused for
its own type. The message names the file, its `HTYPE` and its coefficient
count, and it no longer describes `mg090.Cu311.inst`. The fixture is
`tests/data/gsas2_hb2a_cr2wo6.prm`, the Magnetic-II tutorial's HB-2A
instrument. A test crosses it against `gsas2_hb2a.instprm` on the same
diffractometer. Source kind, geometry, λ (to 1.8e-4) and X = Y = 0 agree.
U V W, the zero and the axial terms differ, because the two files are two
calibrations.

**What it deliberately does not do.** `write_gsas_prm` still refuses a
neutron source. The one real `PNCR` file writes `POLA 0.990` and
`KRATIO 0.500` for a source with neither, and one file is a reading, too thin
to write a convention from. A non-zero `LAM2` on a `PNCR` file is refused.
`POLA` and `KRATIO` are read and named in `GSAS_PRM_FIELD_DROPPED`'s `ICONS`
row, and neither is applied.

**Gotchas.** `tests/test_acceptance_magnetic.py:45` still says `read_gsas_prm`
refuses this file, and the acceptance seeds its width by hand. The comment is
now false. Reading the instrument from the `.prm` instead would move a slow
acceptance's numbers, so that is WP-1327's call, and the review left it as a
follow-up. The 2026-09-23 two-routes gotcha gains a third route: the `.prm`
reader goes through the preset and so gets the coarse box, while
`read_gsas2_instprm` widens the default box only as far as the file needs.

**Measured on the merged tree** (darwin arm64, python 3.12, `[dev,jax]`, a
suite from another repository sharing the machine):

- Fast suite: 6087 passed, 89 skipped (#452 alone on `14239188`).
- The slow tests around the reader (`test_acceptance_wavelength.py`,
  `test_multi_histogram.py`, `test_acceptance_magnetic.py`,
  `test_neutron_cw.py`): 10 passed.
- The whole `-m slow` suite once, on `14239188` + #452 + #456, whose tree is
  the one main reached at `dab23473`: 197 passed, 7 skipped, 1 xfailed.

### 2026-09-23 (2nd session) — the #276 row landed from outside; the neutron preset builds a coarse box

A constant-wavelength neutron instrument whose lines are wider than 1° can
now be built from the preset. `Instrument.constant_wavelength_neutron` builds
its profile with `ProfileTCHZ.coarse`, in `TCHZ_BOUNDS_COARSE` (u ∈ [−0.5, 8],
v ∈ [−4, 4], w, x and y up to 8). So `fwhm_deg` reaches √8 ≈ 2.83° before the
preset's own fence refuses it by name. That is the #276 row of the 2026-09-15
inheritance, live since PR #429 merged (`2d42303a`, closing #276). Like the
rows before it, it arrived from an outside contributor with no `WP-NNNN:`
prefix and no touch of this file. The WP stays `⬜`: tasks 3 and 4 are
untouched, the #268 row is open, and no session owns it.

**Decided (2026-09-23, the maintainer, on the PR).** The #276 row said
"the constructor refuses by name", quoting the 2026-09-11 ruling. The PR
instead read the ruling's escape as the neutron preset's job, and asked. The
maintainer took that reading. Calling `constant_wavelength_neutron` is the
explicit instrument statement that reason 3 asked a coarse instrument to
make. Reason 2's cost, every new instrument's search box moving, is avoided,
because the X-ray presets keep their box literal for literal. The schema
default is unchanged, so no `SCHEMA_VERSION` bump was owed.

**What the merge makes possible.** The APDW D1B Co₃O₄ model (U = 1.576,
V = −0.501, W = 0.475) constructs through `ProfileTCHZ.coarse(...)`. A bare
number for any width is refused by name, on construction and on assignment,
where on main it was pydantic's type error. The message names the width, the
value, the default box and both escapes: `ProfileTCHZ.coarse` and an explicit
`Parameter(value, min, max)`. `TCHZ_DEFAULTS`, `TCHZ_BOUNDS` and
`TCHZ_BOUNDS_COARSE` in `schemas/instrument.py` are the one statement of the
seeds and the two boxes.

**What it deliberately does not do.** A bare wide width still refuses:
`ProfileTCHZ(u=1.576)` raises. That is the ruling's cost, and `using/data.md`
says so. No X-ray preset's box moves, and
`test_the_x_ray_profile_box_is_unchanged` pins all three literal for literal.
`indexing.workflow.seed_widths` still seeds `w` unfenced, so the 2026-09-16
gotcha stands.

**Gotcha.** Two neutron routes now give two boxes. The preset builds the
coarse box, while `read_gsas2_instprm` starts from the default box and
widens each width only as far as the file's value needs. That is not wrong,
since a file is the caller's claim, but it is worth a look when #268's row
is picked up.

**Measured on the merged tree** (Linux x86_64, 4 cores, python 3.12,
`[dev,jax]`):

- Fast suite: 1 failed, 5920 passed, 96 skipped. The failure is
  `test_telemetry.py`'s unwritable-directory case, which fails on main alone
  because the bench runs as root.
- Fast collect: 6007 → 6015, +8.
- Full `-m slow`: 2 failed, 188 passed, 9 skipped. Neither failure is #429's.
  The brucite XPASS(strict) is red on main's own nightly (run 51), and the
  held-phase ramp guard is an X-ray path, over its 60 s guard under load and
  green in isolation on the same tree.
- `ruff`: clean.

**Next** is unchanged: task 3, whose first open item is still sourcing the
public X-ray + neutron dual dataset. The #268 row is unclaimed.

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
