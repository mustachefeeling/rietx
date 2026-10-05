# WP-1543 — a GSAS Gaussian width is a variance

Milestone: unscheduled · Status: ⬜ 2026-10-04 — filed from WP-1327's LaMnO₃ lane; the conversion is unconfirmed against GSAS-II itself
Track: Coming from another code
Depends on: —
Priority: P1 2026-10-04 — if confirmed, every GSAS-I `.prm` and GSAS-II `.instprm`/`.gpx` instrument reads its Gaussian widths 2.35× too narrow, frozen, and a sample fit puts the rest into size and strain silently

## Goal

A GSAS or GSAS-II Gaussian coefficient read into rietx, or written out of it,
describes the same peak width in both programs. One conversion constant
serves every reader and writer, and a test pins it against the other
program's own output rather than against rietx's round trip.

## Context

**Two conversions of one quantity disagree by 8 ln 2 = 5.545.**

- rietx's `ProfileTCHZ.u, v, w` are a Gaussian **FWHM²** in deg²:
  `model/profiles/caglioti.py:271`, Γ_G² = u tan²θ + v tanθ + w.
- GSAS-II's `U, V, W` are a Gaussian **variance** σ² in centideg². The
  recipe reader measured this against GSAS-II's own output: its peak list's
  `sigma_squared` column reproduces U tan²θ + V tanθ + W on all 49 LaB6
  reflections, and the drawn FWHM of its `y_calc − y_bkg` matches
  √(8 ln 2)·√σ²/100 to 0.1–0.9 % (`io/recipe.py:35-41`). So
  `io/recipe.py:147` converts with `GAUSS_CENTIDEG2_TO_DEG2 = 8 ln 2 × 1e-4`.
- **Three other paths divide by 1e4 alone**, reading a variance as a FWHM²:
  - `read_gsas_prm`, `io/instrument_profile.py:710-712` (GSAS-I `GU GV GW`,
    profile type 3, whose manual defines them as σ² too);
  - `read_gsas2_instprm`, `io/instrument_profile.py:1268-1290` via
    `projects/gsas2.centidegree_factor` (`gsas2.py:358`);
  - the writers the same factor serves: `write_gsas2_instprm`
    (`instrument_profile.py:1668`) and the `.prm` writer
    (`instrument_profile.py:1079`, `_PRM_CENTIDEG_SQUARED`).
  Each reader's own round trip passes, because writer and reader share the
  factor. That is why no test saw it (WP-1527's pattern).
- **Measured once, on real data** (WP-1327's lane, 2026-10-04, LaMnO₃ on
  BT-1): seeded from `BT1_Cu311.inst`'s type-3 `GU GV GW` by ÷1e4, a free
  refinement moved u, v, w by 5–7×; seeded with the 8 ln 2 conversion, they
  refined to within ~25 %. One dataset, starting values from a tutorial file,
  so this is direction and not proof.
- **A docstring claims the opposite.** `read_gsas_prm`'s verification (3)
  (`instrument_profile.py:346`) says an independent rietx fit of 11-BM gave
  W = 6.58e-6 deg² against the ÷1e4 conversion's 6.30e-6. If 8 ln 2 is right,
  that agreement is a coincidence of a fit that split width between the
  Gaussian, the Lorentzian and the axial terms. Re-examine it before deciding.

**What it costs if confirmed.** These readers return a **frozen** instrument
(every parameter `vary=False`), the calibrate → freeze → refine-sample
workflow. A Gaussian FWHM 2.35× too narrow, held, leaves the rest of each
peak to the sample: `gauss_size`/`gauss_strain`, or the Lorentzian terms. The
fit can still converge well, and the microstructure it reports is wrong.

## Non-goals

- FullProf's and TOPAS's widths: FullProf's U, V, W are a FWHM² already.
  Check them in the audit task, but change them only on evidence.
- The `.EXP` project reader's coefficient table (`projects/gsas.py:135`)
  reports each coefficient in degrees as the variance it is; change it only
  if it feeds `ProfileTCHZ`.

## Tasks

- [ ] Confirm against GSAS-II itself, not rietx: a committed GSAS-II
      project or recipe output with both an instrument's U, V, W and a
      computed pattern (the recipe reader's LaB6 is one), read through
      `read_gsas2_instprm` and drawn by rietx, peak FWHM against GSAS-II's.
- [ ] Audit every reader and writer of a GSAS or GSAS-II width
      (`git grep -n 'centidegree_factor\|_PRM_CENTIDEG\|/ 1e4\|1e-4'` under
      `src/rietx/io/`) and list each with its convention.
- [ ] One constant for the conversion, used by every path, and the
      `read_gsas_prm` docstring's three-way verification rewritten.
- [ ] Tests pinned to GSAS-II's own numbers, not to a round trip.
- [ ] The 1.7.0 notes: a frozen GSAS instrument's widths move, and so does
      every sample-broadening number fitted on one.
- [ ] `read_gsas_prm` refuses a bank whose first `PRCF` record is not type
      3, even when the bank also states a type-3 record, as `BT1_Cu311.inst`
      does (functions 1, 2 and 3). Decide whether to read the type-3 one, or
      at least name it in the refusal, once the conversion is settled. From
      WP-1327's review.
- [ ] Re-check `tests/test_gsas_prm.py`'s cross of `gsas2_hb2a.instprm`
      against `gsas2_hb2a_cr2wo6.prm`, which says U V W "differ, the two
      being different calibrations".

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gsas_prm.py tests/test_gsas2_instprm.py tests/test_recipe.py -n auto --dist loadgroup
```

Plus a figure: one GSAS-II-computed line drawn over rietx's from the same
`.instprm`, FWHM agreeing to the recipe's 1 %.

## References

- Larson & Von Dreele (2004), *GSAS*, LAUR 86-748: profile function 3,
  σ² = GU tan²θ + GV tanθ + GW + GP/cos²θ in centideg².
- `io/recipe.py`'s module docstring: the measurement against GSAS-II.
- [1327](1327-magnetic-structure.md), whose LaMnO₃ lane found it.

## Handover log

- **2026-10-04** — Filed from WP-1327's handover. The LaMnO₃ acceptance
  seeds its widths from a GSAS-I file with the recipe's 8 ln 2 constant
  (`tests/test_acceptance_magnetic_lamno3.py`, `_instrument`), because
  `read_gsas_prm` refuses that file and its ÷1e4 seed refined 5–7× away. Nothing in the
  package was changed. Next: the first task, since it decides whether the
  rest is a fix or a docstring.
