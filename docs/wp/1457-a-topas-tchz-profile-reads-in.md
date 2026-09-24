# WP-1457 — a TOPAS TCHZ profile reads in

Milestone: unscheduled · Status: ⬜
Depends on: — (1433 soft: the `.inp` grammar the reader still refuses)
Priority: P3 2026-09-24 — a hand translation works; it cost an agent six source reads, and nothing checks the letters

## Goal

An instrument profile stated in TOPAS's `TCHZ_Peak_Type` form becomes an
`Instrument` without a hand translation, `Z` term included. Each profile
parameter's help entry names its TOPAS equivalent.

## Context

**The evidence.** The session WP-1453 describes was given a synchrotron
instrument file in TOPAS form: `prm` lines for U, V, W, Z, X and Y, a zero
shift, an axial term and two radii. rietx has no reader for it. The agent
spent six tool calls grepping the source for the width convention and the
clamp on a negative variance. `help_for` gave Γ_G² = U·tan²θ + V·tanθ + W,
but neither the fold for Z nor the clamp. The file's own W + Z is negative,
so Γ_G² < 0 at low angle, and `RESOLUTION_NOT_POSITIVE` fired on every fit.
That finding was correct. The agent believed TOPAS clamps the same variance
silently, and nobody has checked that.

**The translation.** Take TOPAS's TCHZ Gaussian FWHM² as
U·tan²θ + V·tanθ + W + Z/cos²θ. Then Z/cos²θ = Z + Z·tan²θ, so Z folds
exactly into U + Z and W + Z, and rietx needs no new parameter. rietx's own
1/cos²θ Gaussian term is the per-phase sample size `P` (`gauss_size`,
`docs/manual/profiles.md` eq `prof-caglioti-g`), which is λ-scaled across
histograms (WP-1131). It is the wrong home for an instrument term. For the
Lorentzian, rietx's X is the 1/cosθ term and Y the tanθ term
(`help_for("instrument.profile.x")`). The agent mapped TOPAS's letters the
other way round. **Every letter and unit here is to be measured against
TOPAS's own reference output, never adopted from its prose** (root
CLAUDE.md, comparing against another code).

**The seams.** `src/rietx/io/instrument_profile.py` holds the instrument-file
readers: GSAS-I `.prm` (`read_gsas_prm`) and GSAS-II `.instprm`. The TOPAS
`.inp` reader (`src/rietx/io/projects/topas.py`, `read_topas_inp`) builds a
`Structure` only. Its docstring says `to_structure` never builds an
`Instrument`, and the emission profile and geometry stay on `TopasModel`.
How to add a format, and what a reader may repair:
`src/rietx/io/CLAUDE.md`.

**Scope question.** A TOPAS profile arrives two ways. One is a
`TCHZ_Peak_Type(…)` macro call in an `.inp`. The other is a bare fragment of
named `prm` lines, which is what this session had. The fragment has no fixed
grammar, since the names are the user's. So the first cut is probably the
macro, with the fragment left to the caller and the help entries.

## Non-goals

- Fundamental parameters (`Rp`, `Rs`, `axial`). FPA is fenced to v2.
- Writing TOPAS profiles out.

## Tasks

- [ ] Measure the letters and units against TOPAS reference output (the
      private archive may hold a TCHZ `.inp` with its `.out`; cite it by
      number, WP-1450).
- [ ] Help entries: each `instrument.profile.*` entry names its TOPAS and
      GSAS-II equivalent, and U and W say how a Z term folds into them.
      `tests/test_help.py` crosses the vocabulary both ways.
- [ ] Read `TCHZ_Peak_Type(…)` from an `.inp` into an `Instrument`, beside
      the GSAS readers, or through `read_topas_inp`. Decide which and write
      it here.
- [ ] Tests: a synthetic `.inp` with a nonzero Z round-trips to the same
      Γ_G(θ) to 1e-12 across 5-150°.
- [ ] Skill: one line in `references/api.md`'s reader list, generated.

## Acceptance

A TCHZ `.inp` reads to an `Instrument` whose Γ_G and Γ_L match TOPAS's
reference output at every tabulated angle.

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_projects_topas.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Thompson, P., Cox, D. E. & Hastings, J. B. (1987). *J. Appl. Cryst.*
  **20**, 79.
- Coelho, A. A. TOPAS-Academic Technical Reference, `TCHZ_Peak_Type`.
- WP-1118 (the TOPAS reader), WP-1437 (the help formulas' audit).

## Handover log

- **2026-09-24** — created from the review of an agent session on a private
  series. The readers and the absent TCHZ handling were checked against the
  tree at `2d42303a`. The fold for Z is algebra, and the TOPAS letters are
  unverified. Next: measure the letters.
