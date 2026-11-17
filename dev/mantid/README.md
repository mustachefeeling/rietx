# dev/mantid/: raw TOF focusing with Mantid

Raw neutron TOF powder data → focused GSAS bank files (`.gss`), with Mantid 6.15.0, plus a per-era Si
calibration (DIFC, DIFA, TZERO per bank) written as GSAS `.iparm` / `.instprm`. Built and validated on ISIS HRPD
(2008–2020 runs) on 2026-11-06. Yue ruled on yue-here/rietx#1446 (2026-11-16) that raw TOF reduction is out of scope
for rietx: Mantid focuses, and rietx starts at the focused bank file. This directory keeps the
recipe we use, so it is not rebuilt from scratch. It lives on this development fork, not in rietx: nothing here is
part of the package. The scripts are the ones our runs used, changed only for `$HOME` paths, the UTC line and
pointers to this README. The working notes behind the numbers below are not public.

**Clean room.** Mantid is run as a black box. Algorithms and properties come from its user documentation
(docs.mantidproject.org) and the run-time property lists only. No Mantid source and no facility `treatall*.py` script
was opened, and none may be: the env holds Mantid's Python source (`site-packages/mantid*`, `plugins/`, `isis_powder`);
never open, grep or quote it. IDF XML, `.cal`, `.pref` and facility instrument-parameter files are instrument data and
may be read. Reports say "focused with Mantid 6.15.0 (black box), nothing read".

**Licence.** MIT, like the rest of this repository. The scripts import Mantid (GPL-3.0), which is not included and
is installed separately; no Mantid code is copied here. Anyone who distributes these scripts bundled with Mantid
does so under Mantid's licence.

## Files

| File | Runs in | Does |
|---|---|---|
| `focus_hrpd.py` | `mantid` env | Single-run reference recipe (the canary): sample, V, V-empty, optional sample-empty, optional `.cal`; writes `<label>.gss`, `_tof.xye`, `_d.xye`, `<label>_log.json` (every call). Its docstring lists every step. |
| `batch/hrpd_scan.py` | `mantid` env | Stage 1 header scan: `LoadRaw` of one spectrum per run → title, start, proton charge, TOF window from the axis; temperatures from the run's text logs. Appends to a `.jsonl`, resumable. |
| `batch/make_tasks.py` | plain python3, on the workstation | Assigns each run to a calibration row by (RB, TOF window), writes `specs/<task>.json`, `tasks.jsonl`, `calib_rows.json`, `runs.json`. The `ROWS` and `ASSIGN` tables are the HRPD 2008–2020 choices (our calibration-choice notes): rewrite them for another instrument or RB set. |
| `batch/focus_hrpd_batch.py` | `mantid` env | The batch task: one V per task, then every sample of the task (one RB folder × one calibration row, ≤ 60 runs). A failing run is logged and the task carries on. |
| `batch/read_batch.py` | rietx venv | Reads every `.gss` of a task with `rietx.read_pattern` (banks 1–3, TOF axis, σ > 0) and counts peaks on a pseudo-2θ axis. |
| `batch/build_manifest.py` | plain python3 | Per RB folder: `MANIFEST.tsv` and a README from the task summaries and reads. |
| `batch/calib_rows.json` | data | The 8 HRPD calibration rows (V, V-empty, rod radius, window) as `make_tasks.py` wrote them. |
| `batch/specs/*.json` | data | Two example task specs: R18-30 (V and V-empty from one cycle) and R13-10 (V-empty from 2018 on a 2013 V: the `RebinToWorkspace` case). |
| `si_calibration/focus_si.py` | `mantid` env | `focus_hrpd_batch.py` plus one addition: `save_nxs` keeps the focused TOF workspace (`<label>_tof.nxs`) for PDCalibration. |
| `si_calibration/pdcal_si.py` | `mantid` env | Mantid arm: `PDCalibration` per bank on the focused Si, `Gaussian` and `BackToBackExponential`, `DIFC+TZERO+DIFA`. Cross-check only. |
| `si_calibration/own_fit_si.py` | rietx venv (numpy/scipy) | Own clean-room arm: single-peak B2B⊗Gaussian fits in TOF, then weighted LSQ of TOF = DIFC·d + DIFA·d² + TZERO. `b2b_fac` (α, β held at the facility law) is the calibration that gets written. |
| `si_calibration/analyse_calibration.py` | rietx venv | Tabulates and compares both arms and the facility file → `calibration_table.json/.tsv`. Reads `<root>/mantid_pdcal/` and `<root>/own_fit/`. |
| `si_calibration/write_calibration_files.py` | plain python3 | Writes `HRPD_<era>_<window>.iparm` (GSAS-I, 3 banks, strict columns) and `_bank<b>.instprm` (GSAS-II) from the own `b2b_fac` arm. rietx main reads both. |
| `si_calibration/apply_check.py` | rietx venv | Applies a calibration to non-Si runs and compares bank 2 with bank 1 per reflection. Imports `own_fit_si.py`. |
| `si_calibration/specs/si18_10_*.json` | data | One spec per kind (focus, pdcal, own) for the 2018 Si run HRP70715. |

Spec paths are written `$HOME/...`. The scripts do not expand them: `make_tasks.py` writes absolute paths, and a
hand-made spec needs expanding first, e.g.
`python3 -c 'import os,sys; print(os.path.expandvars(open(sys.argv[1]).read()))' in.json > spec.json`.

## Environment (the workstation, Linux)

- User-space micromamba 2.10.0 at `~/opt/micromamba/bin/micromamba`, root `~/opt/micromamba/root`. Env `mantid`:
  Mantid **6.15.0**, Python 3.11, from conda-forge plus the `mantid` channel, 1.1 GB, no sudo.
- Run: `MAMBA_ROOT_PREFIX=$HOME/opt/micromamba/root ~/opt/micromamba/bin/micromamba run -n mantid python <script>`.
  Fitting and reads stay in the rietx venv (`~/venvs/rietx-py312`); the two exchange `.gss` and `.iparm`/`.instprm` files.
- Start-up network calls off: `usagereports.enabled=0`, `CheckMantidVersion.OnStartup=0`,
  `UpdateInstrumentDefinitions.OnStartup=0` in `~/.mantid/Mantid.user.properties` (set 2026-11-06T16:08Z). With them on,
  every start printed a version notice and `DownloadInstrument` wrote new IDFs into `~/.mantid/instrument/`.
- IDF pinned: every load is `LoadRaw` then `LoadInstrument(Filename=<IDF>, RewriteSpectraMap=False)`, so an
  auto-updated IDF never changes a focus.

## Per-run recipe

1. Load sample, V and V-empty (and a sample-empty if used): `LoadRaw(LoadMonitors=Exclude, LoadLogFiles=False)` →
   `LoadInstrument(IDF, RewriteSpectraMap=False)` → `NormaliseByCurrent`. Refuse a run with proton charge 0.
2. Take the TOF window from the data axis, never from the run title.
3. V-empty from another cycle: `RebinToWorkspace` onto the V's TOF bins first.
4. `Minus(V, V-empty)` → `ConvertUnits(Wavelength)` → `CylinderAbsorption` (V rod; values under Provenance) →
   `Divide(V, absorption)` → `ConvertUnits(TOF)`.
5. Pass 1: `AlignAndFocusPowder(CalFileName=<.cal>, Dspacing=True, DMin 0.2, DMax 25, DeltaRagged = −dt/t per bank)` of
   the V. It returns TOF: `ConvertUnits(dSpacing)`.
6. Crop per bank: the longest contiguous d range where the 51-bin running median of the focused V exceeds **10 %** of
   its bank median; d_min × 1.002, d_max / 1.002.
7. Pass 2: `AlignAndFocusPowder` of V and sample with those DMin/DMax, then `ConvertUnits(dSpacing)`.
8. V, bank by bank: `ExtractSingleSpectrum` → `StripVanadiumPeaks` (defaults) → `SmoothData(NPoints=51)`, copied back
   into a clone of the ragged focused V.
9. `Divide(sample, smoothed V)`; zero the non-finite bins (count them in the log).
10. `ConvertUnits(TOF)` → `SaveGSS(Format=RALF, DataFormat=FXYE, MultiplyByBinWidth=True, SplitFiles=False)`. Write
    the call log. The header carries the geometric focus DIFC only, not a Si calibration.

## Batch

Tasks were run by our own batch runner (not in this repository): one task per spec, run 1–2 canary tasks with the
exact command and check them before the batch. What the HRPD batch used (34 tasks, 1183 runs):

- `hrpd_scan.py` over the run list (one co-tenant task; 1309 runs in 88 s) → `make_tasks.py scan.jsonl <jobdir>`
  (edit its `JOB`, `CAL`, `IDF` constants first; the task's output folder is `<RB folder>/mantid_focus_20261106`) →
  copy `focus_hrpd_batch.py`, `read_batch.py`, `specs/`, `tasks.jsonl` to `~/wsjobs/<job>/`.
- Per task: `cwd` the job dir, env `MAMBA_ROOT_PREFIX=$HOME/opt/micromamba/root`, command
  `$HOME/opt/micromamba/bin/micromamba run -n mantid python focus_hrpd_batch.py specs/<task>.json; rc=$?; $HOME/venvs/rietx-py312/bin/python read_batch.py specs/<task>.json out/rietx/<task>.json; exit $rc`.
- Sizing: **threads = cpus = 4, spec `maxcores` 4** (Mantid `MultiThreaded.MaxCores`); `mem_gb` 3.0 (4.0 for the
  10–210 ms window); ≤ 60 runs per task; `est_s` = 10 + 3 N; `timeout_s` 1800.
- Parallelism: 6 workers at nice 10 on a 32-core machine.
- Si calibration tasks chain the three steps:
  `$HOME/opt/micromamba/bin/micromamba run -n mantid python focus_si.py specs/<t>_focus.json && $HOME/opt/micromamba/bin/micromamba run -n mantid python pdcal_si.py specs/<t>_pdcal.json && $HOME/venvs/rietx-py312/bin/python -I own_fit_si.py specs/<t>_own.json`,
  threads 4, cpus 4, `mem_gb` 3.5, `timeout_s` 600. Then, on the returns: `analyse_calibration.py <root> <out>` →
  `write_calibration_files.py <calibration_table.json> <out>` → `apply_check.py`.

## Pitfalls (measured, 2026-11-06)

- **`CylinderAbsorption` segfaults** (rc 139) with `MaxCores=4` when `OMP_NUM_THREADS` is 1 or 2, pinned or not; it runs
  at 4. Set the thread variables to the task's cores, so a Mantid task declares threads = cpus = MaxCores.
- **Mantid takes every core by default** (`MaxCores=0`): 640–730 % CPU per focus. Cap it to the task's cpus.
- **Memory:** the declared 1.5 GB was too low. Canary maxrss 1768 and 2623 MB per 60-run task; batch peak 2907 MB
  (10–210 ms) and 2198 MB (30–130 ms). rietx's read alone peaks at 150 MB.
- **Time:** focus median 0.14–0.25 s per run, the V 0.8–1.0 s per task, about 0.6–0.9 s per run with the rietx read.
  1183 runs: 333 s wall on 6 workers. A single-run start-up costs 2.6–3.7 s.
- **No `.cal` = no HRPD resolution.** IDF geometry with bank-name grouping gave DIFC −0.017 / −0.53 / +1.17 % off, peak
  shifts Δd/d −1.6e-3 to −1.15e-2 and bank-1 peaks 1.6–3.0× broader. Always focus with the facility `.cal`.
- **Crop:** 2 % leaves partly covered edge bins (bank-3 ramp, edge spikes). 30 % cuts the V's own decline inside the
  frame (bank 1 at 113 ms for 30–130 ms, at 149 ms for 10–210 ms). 10 % reproduces the facility's 2018 crop to about
  1 ms (bank 1 31.5–125.4 ms against 31.4–125.0 ms). The contiguity rule drops frame-edge spikes at 100–101 and
  208–212 ms. The facility's "5–95 %" crop is defined only in its fenced scripts, so it is not used.
- **Top of bank 2:** the last 1–2 bins drop below half the local level (33 of 33 spot checks): exclude d > 0.995 d_max.
- **Failures:** 5 of 1183. Four runs with zero proton charge (the script refuses them) and one single-crystal run on a
  128-spectrum table, which `AlignAndFocusPowder` refuses.
- **The run title lies:** HRP71604 says 30–130 ms, its TOF axis is 100–200 ms.
- **A distant vanadium costs shape:** ±6 % at 4.5 years, up to 20 % at 10 years. Choose V and V-empty per RB first.
- **`StripVanadiumPeaks` and `ConjoinWorkspaces` refuse a ragged workspace:** strip and smooth bank by bank.
- **`AlignAndFocusPowder(Dspacing=True)` returns TOF:** convert to d before cropping or dividing.
- **Sample-environment empty:** subtracting the empty furnace made the shape worse (ratio 0.51–1.20, bank 3 negative),
  and the facility did not subtract one (`S-Empty 0`). The batch subtracts none.
- **Bank 3 is low value** (4–6 usable Si peaks; noise above about 13 Å at 100–200 and 10–210 ms).
- **No calibration in the `.gss`:** positions in d are about +0.1 % off in banks 1–2 until a Si calibration is
  attached (the facility's sits +0.08 % on the geometric DIFC in banks 1–2, −0.34 % in bank 3).
- **Sample position is not calibrated:** HRP72335 (LT furnace) has bank 2 at −1.65e-3 in d against bank 1.
- **PDCalibration 6.15 does not hold B2B A and B fixed** (no `RespectFixedPeakParameters`; the 7.0 page adds it): read
  back from `_fitparam`, they leave the declared law by factors 0.3–30. It returns no uncertainty, and may return a
  model without DIFA. The written files come from the own arm.
- **A TOF calibration is only defined with its peak convention:** a Gaussian centre sits 200–700 ppm above the B2B
  location T0. The files are in the T0 convention with the facility's α/β; a symmetric-profile d-space fit converted
  with them reads cells about 3e-4 high in bank 1.

## Provenance of the fixed values

- **V rod:** radius 0.3 cm, height 2.0 cm, `AttenuationXSection` 5.1 b, `ScatteringXSection` 5.08 b,
  `SampleNumberDensity` 0.072, from the facility pref file `mtd-30-130ms.pref` (read as configuration data in the
  canary). The 2008 rows use radius 0.4 cm, from the rod named in the run titles ("8mm V rod").
  `NumberOfSlices` 10, `NumberOfAnnuli` 10, `NumberOfWavelengthPoints` 100, `ExpMethod Normal` are our choice.
- **Log binning dt/t** 0.0003 / 0.0007 / 0.0012 (banks 1/2/3): the pref file's `Bining` values.
- **`.cal`:** the facility's `hrpd_new_072_01_corr.cal` (header date 2007-11-24), from the CC BY 4.0 LaTaO4 thesis
  dataset; the pref file names it for offsets and grouping. Checked valid 2008–2020: on Si in 2008, 2013 and 2018, and
  bank 1 against bank 2 for 2019–2020. With it our DIFC, 2θ and L match the facility's own focus exactly.
- **IDF:** `HRPD_Definition_pre20210301.xml` (Mantid's own pick for these dates, same positions), loaded explicitly.
  Bank components `bank_bsk`, `bank_90degnew`, `bank_la`.
- **Smoothing and peak strip:** `SmoothData` 51 points, `StripVanadiumPeaks` defaults (FWHM 7, Tolerance 4, Linear):
  our choice. The facility used a 70-coefficient spline.
- **Si profile laws:** α = alp/d, β = bet0 + bet1/d⁴ with alp 0.174216, bet0 0.0247928, bet1 0.00694837, from the
  facility's `Cyc_182_mantid3.hrpd` (PRCF set 1); the facility DIFC/DIFA/ZERO compared against are its ICONS records.
  The certified Si cells (`a_cert` in the specs) come from the NIST SRM certificates.

## Absorption convention

**`CylinderAbsorption` is applied to the vanadium rod only. The sample is NOT absorption-corrected.** Sample
absorption is left for the fitting program (rietx's TOF work, yue-here/rietx#1548, models µ(λ); see #1446). Never correct it in both places. A run
focused here and then fitted with an absorption term counts it once; adding a Mantid sample absorption step would
count it twice.
