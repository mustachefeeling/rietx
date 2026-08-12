# WP-0604 — Sphinx + MyST theory manual

Milestone: v0.6 · Status: ✅ 2026-07-29
Depends on: —

## Goal

A buildable Sphinx + MyST theory manual under `docs/manual/` that organises the
physics already derived in the code's docstrings into numbered, cross-referenced
equations with a sphinxcontrib-bibtex bibliography — and that structurally
*cannot* drift from the code: every threshold it quotes is injected from the
live package at build time, every equation names the source symbol whose
docstring it transcribes, and guard tests fail the suite when either link
breaks.

## Context

The raw material already exists by invariant: every physics function cites
author/year/journal in its docstring, and the heavyweight derivations
(absorption 145 lines, Stephens 54, dispersion 54, structure-factor Friedel
average 47, FCJ 43, LM sign-error correction 57, linalg64 precision policy 45,
March-Dollase 56, extinction 58 …) are already manual-quality prose *in the
modules*. The manual's job is organisation, typeset equations, and the
convention warnings — not re-derivation. The design rule, from the Brindley
incident below: **the manual transcribes from code and docstrings, never from
WP prose, and where it would restate a derivation it points at the docstring
instead.**

Design decisions (made at expansion, 2026-07-29):

- **Location**: `docs/manual/` (MyST `.md` sources + `conf.py` +
  `references.bib`), building to `docs/manual/_build` (gitignored). Planning
  docs in `docs/` are untouched.
- **Dependencies**: a new `[docs]` extra — `sphinx`, `myst-parser`,
  `sphinxcontrib-bibtex`, `furo` — included into `[dev]` by self-reference so
  the guard tests actually run in the standard suite rather than skipping.
- **Numbered equations**: MyST `{math}` directives with `:label:`; referenced
  with `{eq}` roles. Numbering is per-chapter and automatic.
- **Cross-reference direction is manual → docstring.** Each displayed equation
  carries a `*Source:* ``anatase.module.symbol``` line naming the docstring it
  was transcribed from. The reverse direction (editing 40 modules' docstrings
  to name manual equation numbers) was rejected: it couples every physics
  module to the manual's numbering and would go stale on every reorganisation.
  A guard test imports every named symbol, so a rename breaks the build's
  tests, not the reader's trust.
- **Thresholds and fenced constants are never typed into the manual.**
  `conf.py` imports the live package and exposes them as MyST substitutions
  (`{{ BRINDLEY_MU_R_FENCE }}`, `{{ CYLINDER_MU_R_MAX }}`, …); an undefined
  substitution is a warning and the build runs `-W`. This is the executable
  form of the Brindley lesson.
- **No autodoc.** The docstrings use unicode math and prose conventions that
  reST rendering would mangle under `-W`; the manual points at symbols, and
  the reader opens the module. An API reference is a different document with
  different failure modes (WP-1003's problem, not this one).
- **Build must be `-W` clean** (warnings are errors), and `sphinx-build` runs
  in the fast test suite via subprocess (build is seconds for ~12 pages;
  `pytest.importorskip("sphinx")` keeps environments without the extra green).

Chapter plan (bibliography keys from the docstring citations; the inventory
that produced this plan is reproducible by grepping `src/` for years/journals):

0. Front matter — how to read this manual; code-is-authoritative rule.
1. The forward model — Rietveld sum, Le Bail fixed point, Pawley block;
   residual row layout (`model/forward.py`, `model/rows.py`).
2. Peak positions — G\*, Bragg's law, zero/displacement/transparency
   (`crystallography/lattice.py`, `model/corrections.py`).
3. Peak profiles — Caglioti split with the variance-vs-FWHM addition rules,
   TCH pseudo-Voigt, true Voigt via Weideman Faddeeva, FCJ axial divergence
   incl. the ξ substitution and the S/L = H/L corner
   (`model/profiles/*.py`).
4. Intensities — Waasmaier-Kirfel f₀, Cromer-Liberman f′/f″ with the Kissel-
   Pratt correction, Debye-Waller in the three ADP representations, the exact
   Friedel-average ⟨|F|²⟩ = |A|² + |B|², multiplicity by Laue-orbit counting
   (`crystallography/{scattering,dispersion,adp,structure_factor,symmetry}.py`).
5. Intensity corrections — Lp, capillary and flat-plate absorption (with the
   A vs A\* = 1/A convention paragraph and the two different "off" states),
   surface roughness (Suortti, Pitschke), secondary extinction (Sabine),
   March-Dollase with the geometry-dependent sense of r, Brindley
   microabsorption and Hill-Howard QPA
   (`model/{corrections,absorption,extinction,preferred_orientation}.py`,
   `optimize/qpa.py`).
6. Microstructure — size/strain θ-laws documented by physics not letters;
   Stephens anisotropic strain with all three labelling conventions stated
   (FWHM not σ; 10⁻¹² Å⁻⁴ units; literal monomials)
   (`model/profiles/caglioti.py`, `crystallography/stephens.py`).
7. Background — additive models, P-spline penalty rows, arPLS/SNIP estimators,
   masked-BIC + Durbin-Watson selection (`background/*.py`).
8. Estimation — weighted objective, weights policy, agreement indices,
   Bérar-Lelann inflation, solvers (TRF / bounded LM / BCCG) with the Stephens
   cone as the reason `lm` exists, and the fp64 floor (cond(JᵀJ) = cond(J)²)
   (`optimize/*.py`, `backend/linalg64.py`).
9. Parameterisation & constraints — transforms, crystal-system ties, Wyckoff
   coordinate/ADP bases as exact rational nullspaces, restraint rows
   (`params/*.py`, `crystallography/wyckoff.py`, `model/restraints.py`).
10. Reading a paper against its own numbers — the method chapter: Rouse b₂
    (validate against the integral, not a transcription), the two Coelho
    in-print inconsistencies, the FCJ corner as "the parameterisation, not the
    solver, stalls", and µR vs µt (exact vs approximate degeneracy; not one of
    the v0.5 corrections is well judged by Δ Rwp).

### Inherited

From **WP-0602** (agent JSON surface, landed 2026-07-29) — three facts for
any chapter that touches the agent-facing surface:

- **`anatase.agent` exists** (`refine_json`, `tool_definition`,
  `request_schema`/`response_schema`); its module docstring is the contract
  prose (envelope, the three closed error codes, the two deliberate history
  asymmetries) — lift it rather than re-describing.
- **The Layer-2 vocabulary gained `refine_preferred_orientation`**
  (THRESHOLDS_VERSION 0.2 → 0.3): the WP-0307 texture orphan is claimed, so a
  manual section on the FitReport should not repeat the "no action consumes
  the texture diagnostic" caveat that older notes carry.
- **`Provenance.solver` and `CONSTRAINT_ACTIVE` exist**: which driver ran is
  on every result, and a bounded-LM answer that pressed the Stephens cone
  says so (`StageResult.n_constraint_truncations` per stage; the diagnostic
  fires only for the answer-producing stage). A solver chapter should present
  the cone as the reason `lm` exists — the tie in speed was expected
  (WP-0601's Amdahl bound), the constraint vocabulary is the deliverable.

From **WP-0508** (flat-plate absorption, landed 2026-07-28) — a section that
is already written, and a worked example of the house rule.

- **The three specimen-absorption geometries are derived in full in
  `model/absorption.py`'s module docstring**, each in three lines from the ITC
  eq. (6.3.3.1) volume average, including the sin θ cancellation that makes a
  *thick* Bragg-Brentano specimen angle-independent. That is manual prose
  already; lift it rather than re-deriving, and keep the convention paragraph
  (A ≤ 1 transmission vs the A\* = 1/A most tables print — an identity test
  cannot tell them apart, only the direction of the θ-dependence can).
- **It is also the cleanest illustration of "validate against the integral, not
  a transcription".** WP-0501's b₂ was printed with two digits transposed in
  the available scan of Rouse (1970); the error is invisible against a
  constant-θ slice of the paper's own table and 0.08 wrong at µR = 1. The
  flat-plate cases are closed-form integrals rather than fits, so
  `tests/test_flat_plate.py` checks them against an adaptive quadrature of the
  defining path-length integral, sharing no constant with the implementation.

From **WP-0305** (Brindley, landed 2026-07-23) — a concrete instance of the
"second, divergent source" risk this stub already names, and a warning about
*which* source to trust. 0305's own WP body wrote the microabsorption fence as
"µR ≲ 0.01–0.1", which **conflated two conventions**: the shipped fence is
`BRINDLEY_MU_R_FENCE = 0.05` in µ·R, derived from µ·D ≤ 0.1 (D = diameter,
R = radius). The handover log corrected it; the WP body was never rewritten.

The general rule that follows: **transcribe formulas and thresholds from the
code and its docstrings, never from WP prose.** WP bodies record what was
planned, handover logs record what shipped, and where they disagree the code is
authoritative. Every physics function cites author/year/journal in its
docstring by invariant, which is what makes the code the better source.

From **WP-0503** (Stephens anisotropic strain, landed 2026-07-27) — the manual
must state *conventions*, not just equations, and this is the worst offender so
far. Three independent labelling choices sit behind the S_HKL of
`crystallography/stephens.py`, and getting any one wrong rescales every
published number:

1. `√(Σ S·monomial)·d²·10⁻⁶` is the **FWHM** of the ΔM/M distribution here, not
   its standard deviation — no √(8 ln 2) appears anywhere;
2. the coefficients are carried in **10⁻¹² Å⁻⁴**, not physical Å⁻⁴ (and that is
   load-bearing numerically, not cosmetic — see the module docstring);
3. they multiply the **literal monomials** h^H k^K l^L, whereas other codes fold
   symmetry multiplicities into their templates (writing the cubic S220 term as
   `3·(h²k² + h²l² + k²l²)`, say), so their printed values differ by small
   integer factors as well.

A manual that reproduces Stephens (1999) equation (1) without all three is
worse than no manual: a reader would transfer literature S values straight in
and get a wrong width law that still refines. The same applies to the
size↔1/cosθ, strain↔tanθ letter conventions already in `profiles/caglioti.py`
(GSAS and FullProf swap X/Y).

From **WP-0601** (bounded LM solver, landed 2026-07-28) — three things worth a
paragraph each, all measured on real data rather than argued.

- **The FCJ profile has a genuine corner at S/L = H/L, and the default
  instrument starts both apertures equal.** `fcj_offsets_weights` builds its
  quadrature around `|S/L − H/L|` and `min(S/L, H/L)`, both non-differentiable
  where the two are equal, and the docstring already says the split "keeps the
  response C¹ everywhere except the inherent FCJ kink at s = h itself".
  Measured consequence on SRM 660c: the analytic S/L and H/L Jacobian columns
  agree with a residual-vector finite difference to only ~2 % (every other
  column is ≤ 1e-5), because the analytic derivative is one-sided while the
  central difference straddles the corner. Their columns are then *identical*,
  so a Gauss-Newton step moves the pair along the diagonal forever — the
  correlation guard reports ρ = +1.000, and the bounded LM converges with
  `axial_sl == axial_hl` bit-identically while TRF escapes onto an asymmetric
  solution by way of its own internal scaling. Neither escape is principled.
  This belongs in the manual as a worked example of "the parameterisation, not
  the solver, is what stalls".
- **Two Coelho papers disagree with themselves in print**, and both cases are
  resolved in `optimize/bccg.py` and `optimize/lm.py` with the reasoning and
  the measurement. Coelho (2005) eq. (1) prints `Max[(k+1)/N_k, 1]` while its
  text describes a reduction (`Min`); measured, neither reading helps and the
  shipped factor is 1. Coelho (2018) eq. (9) defines `ΔS_t = Δpᵀb`, which is
  positive for a descent step while ΔS < 0 and would report `r_u < 0` always;
  the self-consistent reading is `ΔS_t = −Δθᵀb`, pinned by the identity
  `r_u ≡ 1` on an exactly linear model. Good material for a manual section on
  reading a method paper against its own numbers.
- **Why the normal equations are the fp64 floor** is now demonstrated twice
  over: cond(JᵀJ) = cond(J)² is the reason `backend/linalg64.py` exists, and
  the bounded LM forms JᵀJ explicitly rather than implicitly as TRF does, so it
  is the more direct illustration for the manual's precision chapter.

## Non-goals

- **No API reference / autodoc** — pointing at symbols is deliberate (above);
  a rendered API reference belongs with the WP-1003 freeze, if anywhere.
- **No hosting / CI / readthedocs** — WP-1002 owns CI; this WP delivers a
  local `-W`-clean build plus the guard tests.
- **No docstring rewrites to cite manual equation numbers** — rejected
  direction, see design decisions.
- **No new physics prose in docstrings** — gaps found while transcribing are
  noted in the handover log, not silently patched in either place.
- **No v2-fence chapters** (FPA, TOF/neutron, spherical-harmonics texture) —
  named as out of scope in the front matter, not drafted.

## Tasks

- [x] Expand this stub into a full WP before writing code
- [x] Docs infra: `[docs]` extra (self-referenced into `[dev]`),
      `docs/manual/` skeleton, `conf.py` importing live constants as MyST
      substitutions, `_build/` gitignored, empty manual builds `-W`-clean
- [x] `references.bib`: every literature reference cited in `src/` docstrings,
      keyed `author-year` (deduplicated; ITC volumes as `@book`s)
- [x] Chapters 1–3: forward model, peak positions, peak profiles
- [x] Chapters 4–6: intensities, intensity corrections, microstructure
- [x] Chapters 7–9: background, estimation, parameterisation & constraints
- [x] Chapter 10 + front matter: method case studies; how-to-read rules
- [x] Guard tests (`tests/test_manual.py`): `-W` build via subprocess; every
      bib entry cited somewhere; every `*Source:*` symbol imports; ruff clean

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual.py -q
.venv/bin/python -m ruff check src tests examples
```

Plus the two structural claims the tests encode: no bibliography entry is
uncited, and every equation's `*Source:*` symbol resolves by import.

## References

The bibliography *is* the deliverable — see `docs/manual/references.bib`.
Tooling: Sphinx, MyST-Parser, sphinxcontrib-bibtex, furo (all BSD-licensed).

## Handover log

- **2026-07-29 (post-ship)** — the two held-out bibliography entries are
  closed: the user supplied both papers, so `andreev1994` (J. Appl. Cryst.
  27, 288 — title verified from the paper itself) and `deslattes1985`
  (ch. 5 of *Atomic Inner-Shell Physics*, Plenum 1985, p. 181) are now in
  `references.bib` and cited where their docstrings live (the Bérar-Lelann
  upper-bound paragraph in `estimation.md`; the Mo/Ag wavelength provenance
  in `peak-positions.md`). Only the *first* pages are recorded — the copies
  supplied don't show the end pages, and the house rule applies to page
  ranges too. The bibliography now covers every physics docstring citation
  in scope.
- **2026-07-29 (ship)** — all eight tasks landed in eight commits; WP shipped
  and it closes v0.6 (milestone record `../milestones/v0.6.md`). Done: ten
  chapters + front matter under `docs/manual/` (MyST, numbered equations,
  ~50 labelled), `references.bib` with 62 verified entries, `conf.py`
  injecting ten live constants as substitutions, five guard tests in
  `tests/test_manual.py` (build `-W` via subprocess ≈4 s in the fast suite,
  bib coverage both directions, every `*Source:*` symbol imports, labelled
  pages carry source lines). Fast suite 940 passed / 4 skipped in 57 s.
  Gotchas for whoever extends the manual:
  - **Two docstring citations are deliberately absent from the bib** because
    their full records couldn't be verified against the papers and titles
    are never fabricated (house rule + memory "ask for papers"): Andreev
    (1994), J. Appl. Cryst. 27, 288 (serial-correlation esds,
    `optimize/statistics.py`) and Deslattes & Kessler (1985, Plenum,
    `schemas/instrument.py`). Ask the user for the PDFs and add them.
  - `test_every_bib_entry_is_cited` means **adding a bib entry without citing
    it fails the suite** — add the citation first.
  - The `{{ constant }}` substitutions come from `docs/manual/conf.py`
    imports; a new fenced constant needs a line there *and* use in a chapter
    (unused substitutions don't warn; undefined ones fail `-W`).
  - Exporter/pdCIF papers (Hall 1991, Toby 2003) and the compare-UI structure
    provenance papers were left out on scope grounds (theory manual, not
    formats), not by oversight.
- **2026-07-29** — expanded the stub into a full WP: chapter plan derived from
  a sweep of every citation-bearing docstring in `src/`; anti-divergence
  design fixed (substitutions for constants, manual→docstring source lines,
  guard tests, no autodoc). Starting infra next.
- **2026-07-22** — created as a stub from the ROADMAP split.
