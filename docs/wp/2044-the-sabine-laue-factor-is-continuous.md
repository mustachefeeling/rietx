# WP-2044 — The Sabine Laue factor is continuous at x = 1

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P1 2026-10-24 — a silent wrong answer in a shipped path: a fit parks extinction on a step in the model, and its esd collapses wherever the last Jacobian straddles the step; the 1.10 cut (2043) waits on it

## Goal

The Laue half of the Sabine extinction factor is one continuous function of
x, so no fit can park on a step at x = 1. The extinction column agrees with a
central difference at any step on the QPA guide's fit, and that fit's esds
agree between Linux and GitHub's macOS runner. The other programs' choices and
the paper are on record first, in `docs/practice.md`.

## Context

**The model.** `src/rietx/model/extinction.py` implements Sabine's
polycrystalline extinction, E = E_B·sin²θ + E_L·cos²θ, with
x = ext·|F|²·(λ/V)²·Xpol per reflection. It copies GSAS-II's `GetPwdrExt`
for E_L: the six-term series 1 + Σ cᵢxⁱ on 0 < x ≤ 1, and the two-term
asymptote √(2/πx)·(1 − 1/8x) above. Checked in GSAS-II 5.8.4 source
(`GSASII/GSASIIstrMath.py`, `GetPwdrExt`) on 2026-10-24. The two meet with
a step: E_L(1⁻) = 0.67420 and E_L(1⁺) = 0.69815, 3.6 %. The module docstring
keeps the step for the cross-code golden in `tests/test_extinction.py`, and
says real powder data keep x ≪ 1. GSAS-II differentiates its two branches
analytically (`GetPwdrExtDerv`). rietx takes the extinction column by a
forward difference in `optimize/least_squares._peak_chain_column`, at
h = 1e-6 relative.

**What WP-2043 measured, 2026-10-24.** The fit is `examples/guides/qpa.py`'s
first: 11-BM NAC with a CaF₂ impurity, plan `mccusker_structural`, 2-24°.
- At the answer CaF₂'s 11 reflections reach x = 6.49, five have x > 1, and the
  one at 2θ 19.004° has x = 1.0000. The solver parks extinction where a
  reflection touches the step: 1361.11 µm² in 1.9.0, 1361.15 on `main`.
- At the answer the column agrees with a central difference at 1e-6 (norm
  0.1957, cosine 1.0). A central difference at 1e-4 straddles the step: norm
  22.47, cosine −0.19. Earlier closing-stage iterates handed the solver a
  column of norm 4503.
- On GitHub's `macos-26-arm64` runner the last Jacobian straddled. CaF₂ came
  out 3.08 ± 0.21 wt% and extinction 1361 ± 0.007, against 3.08 ± 2.24 and
  1361 ± 2116 on Linux and on a local arm64 Mac. 1.9.0 gave 3.09 ± 2.32 on
  both. Run 40083266263 on branch `tmp/wp2043-macos-qpa`, whose workflow
  `.github/workflows/tmp-wp2043-qpa.yml` and probe re-run the check.

**The candidate.** e^(−x)·[I₀(x) + I₁(x)], with I₀ and I₁ the modified Bessel
functions, expands to Sabine's c₁…c₄, to c₅ = −7/640, and to his four-term
asymptote 1 − 1/8x − 3/128x² − 15/1024x³. That is WP-2043's own expansion, not
read from a paper. In code it is `i0e(x) + i1e(x)`, with
dE_L/dx = −i1e(x)/x, which is −1/2 at x = 0. Against GSAS-II's branches it
differs by 4e-8 at x = 0.25, 5.6e-6 at 0.5, 7.9e-4 at 1⁻, 3.6e-2 at 1⁺,
9.8e-3 at 2 and 1.1e-3 at 5. Patched into the QPA fit on numpy alone, it gave
extinction 1919 ± 4066 µm², CaF₂ 3.58 ± 3.53 wt% and Rwp 0.08163 against
0.08156. `HIGH_CORRELATION` scale ~ extinction at ρ = +0.998 fired where it had
not. The held fit stayed at 1.37 ± 0.07 wt%.

**The maintainer's ruling, 2026-10-24.** Option 1 of three (the continuous
function, before the 1.10 tag), filed as this stub, which checks the other
programs and the paper first. The two not taken: cut 1.10 now and owe 1.10.1;
or an analytic column on GSAS-II's form, which ends the esd lottery and leaves
the parking. The maintainer's standing rule is accuracy first, with a
program's convention served beside it where someone needs it.

**A second copy of the formula.** The TOPAS writer
(`io/projects/topas_input.py`, the extinction builder near line 405) spells
the same two branches into a `scale_pks` expression, from its own
`_SABINE_LAUE` and `_SABINE_XPOL` (audit rows at `_audit.py` 1495-1496). Its
docstring measured TOPAS 6 against rietx at extinction 20 (`case_nacl_xray`,
Y_calc to 2.6e-3). Whether TOPAS's expression language has I₀ and I₁ is
unchecked.

**The neighbour.** WP-1944 (issue #877) owns *which* phases
`mccusker_structural` frees extinction on: every phase today, which is why
CaF₂'s is free to walk here. It does not own the function, and neither fix
replaces the other.

**Tier.** Physics: the function is Sabine's own, written exactly rather than as
two truncated expansions. No threshold or automatic action is added.

## Non-goals

- Secondary extinction, or an extinction model other than Sabine's.
- The 1.10 cut's own work. That is WP-2043, which waits on this one.

## Tasks

- [ ] The paper: Sabine, Von Dreele & Jørgensen (1988), *Acta Cryst.* A44,
      374, at `/Users/yue/Zotero yue-here/storage/HXSZ3X8N/Sabine et al. - 1988
      - Extinction in time-of-flight neutron powder diffractometry.pdf`. What
      it gives for E_L: the series, the asymptote, a closed form, a switch
      point. Whether e^(−x)·[I₀ + I₁] is stated or implied. Sabine (1988),
      *Acta Cryst.* A44, 368, eqs 6 and 16, is not in the corpus: ask the
      maintainer for it if the first paper does not settle the form
- [ ] The other programs, each marked checked or inferred: TOPAS (the
      technical reference, topas-academic.com/technical_reference), FullProf,
      RIETAN-FP, BGMN, MAUD and EasyDiffraction (sources and manuals under
      `~/Code/rietx-bench/tools/`), GSAS-II (checked above). For each, the
      extinction model, whether E_L is continuous at x = 1, and how its
      derivative is taken. Into `docs/practice.md` as a new § Extinction
- [ ] Checkpoint: if the survey changes the case, such as a program using an
      exact form or every program keeping the step for a stated reason, bring
      it to the maintainer before any code
- [ ] `model/extinction.py`: E_L = e^(−x)·[I₀ + I₁] and its derivative, on
      numpy, jax and torch. `i0e` and `i1e` join `_OP_NAMES` and every
      backend, or `tests/test_backend_conformance.py` fails. The docstring's
      "out of reach for real powder data" goes, replaced by the QPA fit's
      numbers
- [ ] The TOPAS writer follows the model, or states where it cannot: an
      exact form if TOPAS's expression language has the functions, otherwise
      the closest it can spell, with the difference measured and reported at
      write. Its round-trip test re-run
- [ ] The column: a test that the extinction column on the QPA guide's fit
      agrees with a central difference at 1e-4 and at 1e-6. Whether an
      analytic column (`sabine_extinction_and_dx` exists) should replace the
      forward difference is decided on that test's numbers
- [ ] `tests/test_extinction.py`: the GSAS-II transcription becomes a
      comparison within the band above, and a test asserts E_L is continuous
      at x = 1. `tests/test_cross_backend.py` rows for extinction; the
      bit-identity goldens that carry extinction recaptured, with the move
      quoted
- [ ] The QPA guide re-pinned (`examples/guides/qpa.py`, its page), and its
      first fit re-run on the macOS runner by re-pushing
      `tmp/wp2043-macos-qpa`. The branch is deleted after
- [ ] Manual: the Theory tab's extinction equation with its `*Source:*` line.
      Notes: a "Numbers that move" entry in `docs/releases/1.10.0.md` naming
      who moves (a fit where some reflection's x passes about 0.5)
- [ ] Skill: none expected. The new `HIGH_CORRELATION` firing is the existing
      code's row

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extinction.py tests/test_cross_backend.py \
  tests/test_backend_conformance.py tests/test_examples.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

And on the macOS runner, the QPA guide's first fit gives the same CaF₂ esd as
Linux to two significant figures.

## References

- Sabine, T. M., Von Dreele, R. B. & Jørgensen, J.-E. (1988). *Acta Cryst.*
  A44, 374-379.
- Sabine, T. M. (1988). *Acta Cryst.* A44, 368-373.
- GSAS-II 5.8.4, `GSASIIstrMath.GetPwdrExt` and `GetPwdrExtDerv`.
- `docs/wp/2043-cut-1-10-0.md` § Context, for the runner measurements.

## Handover log

- **2026-10-24** — created by WP-2043's session at the maintainer's ask: a
  stub for option 1 that checks the other programs and the paper first. No
  open WP owns the function: of the open WPs naming Sabine or the Laue
  factor, 1944 owns which phases a plan frees, 1911 the foreign writers'
  coverage and 1327 the magnetic Laue orbit. Filed against `origin/main`
  at `377c5724`. Next: the paper, then the survey.
