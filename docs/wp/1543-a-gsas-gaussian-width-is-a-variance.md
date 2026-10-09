# WP-1543 — a GSAS Gaussian width is a variance

Milestone: unscheduled · Status: 🔄 2026-10-10 — claimed by @yue-here; the one-constant, GSAS-II-oracle and `PRCF` tasks remain
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

### Inherited

- **2026-10-05, from the issue triage (issue #705): GSAS-II's `.instprm`
  is confirmed a variance against GSAS-II itself, and PR #708 fixes that
  pair alone.** The reporter ran GSAS-II 5.6 as a black box at zero cycles on
  `.instprm` + phase CIFs written from rietx fits (lab, synchrotron, CW
  neutron): every pattern with a Gaussian term was 2.35× too wide, ÷ 8 ln 2
  brought each to the known floors, and a Lorentzian-only profile agreed
  either way. That is task 1 for this path, though no GSAS-II output is in
  the tree. *Checked at `32ef5a6`* with the issue's script: GSAS-II's law on
  the written U, V, W draws 2.3548× rietx's FWHM at 30°, 60°, 120°; reading
  U = 100 gives a 0.100° FWHM at θ = 45° where GSAS-II draws 0.2355°.
  **PR #708, from a fork, open**: `gsas2.instprm_factor` (÷ 8 ln 2 on U V W)
  in the reader, writer and negative-width refusal, tests on GSAS-II's law
  rather than a round trip, `.gpx`'s `Gsas2Term.degrees` left a variance and
  documented so. Left here, by its "Not covered" and the maintainer's PR
  review: the `.prm` reader (`instrument_profile.py:710-712`) and writer
  (`:1079-1081`); the `.EXP` route, where `viz/compare.py:358-360` and
  `tests/test_acceptance_fap.py:164-166` hold `GsasProfileTerm.degrees` (a
  variance) as `profile.u/v/w`; and `:346`'s verification (3). GSAS-I needs
  no runner: `:1551` records GSAS-II importing a `.prm`'s GU/GV/GW
  unconverted, and the HB-2A cross (`test_gsas_prm.py:777`) shifts by √(8 ln 2).

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

- **2026-10-06 (2nd session)** — PR #739 (#735) merged as `226aafb5`.
  `read_gsas_prm` and `write_gsas_prm` convert `GU`, `GV` and `GW` as
  GSAS-I's Gaussian variance, and `rietx compare` seeds its GSAS-I protocol
  the same way. Gated together on a seven-PR stack replayed onto `main` at `7c8a0316` (stack `ee39adb9`, macOS arm64, `[dev,jax]`). The fast suite gave 8523 passed, 103 skipped and 2 failed. Both failures fail identically on bare `main`: the `toy_anomalous` golden (#760) and a hypothesis case in `test_indexing_reduce.py`. The whole slow tier gave 291 passed and 12 skipped. After the last merge, `main` at `0cbb1b70` is content-identical to the gated tree.
  - The FAP question from the last entry is answered. With axial divergence
    and the preset's instrument Lorentzian removed, so that the model is
    GSAS's CW function 2, `lor_size` lands 2.7 % from GSAS's LX under the
    variance reading and 48 % away under the old one.
    `test_fap_lorentzian_matches_gsas_lx_on_gsas_own_model` pins both arms,
    with rows in `tests/validation_matrix.py` and `docs/VALIDATION.md`. The
    old 5 % agreement was two errors cancelling. On the full protocol, which
    also refines S/L, the 0.30 band on LX stays, with its reason in the
    test. X = 0.001 is about 3 % of LX, so axial divergence carries nearly
    all of that gap.
  - Still open. `GAUSSIAN_VARIANCE_TO_FWHM_SQUARED` is defined in both
    `gsas.py` and `gsas2.py`. Both are `8 ln 2` today, so the one-constant
    task now has three spellings to fold, counting
    `recipe.GAUSS_CENTIDEG2_TO_DEG2`. The module docstring of
    `tests/test_acceptance_fap.py` (l. 43-49) quotes the new Lorentzian
    beside the old Rwp, Rp and cell figures. The head values are 9.25 %,
    7.12 % and +83/+82 ppm. The GSAS-II oracle task and the `PRCF` type-3
    refusal are untouched.

- **2026-10-06** — PR #708 (outside contributor, issue #705) merged as
  `b8f9b615`. The GSAS-II `.instprm` reader and writer now carry the
  8 ln 2 between a Gaussian variance and rietx's FWHM², through
  `gsas2.instprm_factor`. `Gsas2Term.degrees` stays the unit change alone,
  so a `.gpx` read is unchanged, and `files.md` now says so. The GSAS-II
  half of the first task stands on the measured row in `tests/data/README.md`.
  It was gated on a six-PR stack (macOS arm64, `[dev,jax]`, full suite 8724
  passed, 110 skipped, 1 failed on a golden that fails on bare `main` on that
  machine too). The GSAS-I half is PR #739 (#735), reviewed and not merged.
  It needs a rebase over #708, and an explanation of why the FAP acceptance
  moves away from GSAS's LX under the corrected Gaussian (about 5 % to about
  27 %, with the bar widened from 0.20 to 0.30). Until that is answered, the
  "one constant" and "tests pinned to GSAS-II's own numbers" tasks stay open.
  After #739, `GAUSSIAN_VARIANCE_TO_FWHM_SQUARED` lives in two modules beside
  `recipe.GAUSS_CENTIDEG2_TO_DEG2`.

- **2026-10-04** — Filed from WP-1327's handover. The LaMnO₃ acceptance
  seeds its widths from a GSAS-I file with the recipe's 8 ln 2 constant
  (`tests/test_acceptance_magnetic_lamno3.py`, `_instrument`), because
  `read_gsas_prm` refuses that file and its ÷1e4 seed refined 5–7× away. Nothing in the
  package was changed. Next: the first task, since it decides whether the
  rest is a fix or a docstring.
