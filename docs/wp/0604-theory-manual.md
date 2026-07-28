# WP-0604 — Sphinx + MyST theory manual

Milestone: v0.6 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Sphinx + MyST theory manual: numbered equations cross-referenced from
  docstrings (sphinxcontrib-bibtex)

## Context pointers

- The raw material already exists by invariant: every physics function cites
  author/year/journal in its docstring. The manual organises those citations
  into numbered equations; it must not become a second, divergent source of
  the formulas.

## Inherited

From **WP-0602** (agent JSON surface, landed 2026-07-29) — three facts for
any chapter that touches the agent-facing surface:

- **`pxrdref.agent` exists** (`refine_json`, `tool_definition`,
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

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
