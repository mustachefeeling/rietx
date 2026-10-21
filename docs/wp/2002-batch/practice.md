# What the seven programs do by default (2026-10-21)

Surveyed for the fifth round's questions and for tier 2's widened program list
(`docs/milestones/generality.md` § The rule). One agent per program read its manual or
source and, where cheap, ran it. The lead checked the load-bearing numbers against the
reports. Versions: GSAS-II 5.8.4 (source), FullProf 8.20 (manual and `fp2k` runs), TOPAS
Technical Reference Version 9 (no source or `Topas.inc` read), RIETAN-FP 3.12 (manual and
runs), BGMN 4.2.23 with Profex 5.7.2 (manual, Profex docs and templates, runs; no source,
GPL), MAUD 3.07 (BSD-3 source at the tag), EasyDiffraction 0.21.1 with cryspy 0.13.0
(source). The sources for the load-bearing rows are listed at the end; where each program
sits on disk is in the maintainer's memory (`foreign-code-sources-on-disk`). "Checked" means
read in the source or manual; "ran" means measured.

## How far a peak is computed

The Lorentzian column is the area a pure Lorentzian loses to the default cut.

| Program | Default cut | Lorentzian area lost | When the window is set |
|---|---|---|---|
| rietx | `WINDOW_AREA_TOL`, 2 % of each peak's own area | 2 % | once per stage, at the stage's start (checked) |
| TOPAS | `ymin_on_ymax` 0.001 of the strongest line's height | 2.0 % | peak buffer rebuilt when a width moves past `aberration_range_change_allowed`, and per derivative for width parameters (§7.4, §7.7, checked) |
| MAUD | ±30 HWHM (±15 FWHM) | 2.1 % | every evaluation, finite-difference columns included (checked) |
| RIETAN-FP | `PC` 0.002 of each peak's own height, in three of four shipped examples; no default | 2.8 % | every evaluation (ran) |
| FullProf | `Wdt` × FWHM each side; no default, floored at 3; examples 3-15, PbSO₄ 6 | 5.3 % at 6 (10.5 % at 3, 2.1 % at 15) | once per run, at the starting widths (`Ias = 0`, ran); `Ias = 1` lags one cycle |
| GSAS-II | 50 FWHM below, 75 above | 0.53 % | every evaluation (checked) |
| BGMN | no cut seen out to 22° from a peak | ~0 | not documented |
| EasyDiffraction | none (cryspy sums every reflection over every point); the crysfml calculator uses 30 FWHM | 0 (1.1 %) | every evaluation (checked) |

## Axial divergence quadrature

| Program | Method |
|---|---|
| rietx | FCJ, node count from `NODES_PER_FWHM` etc., frozen per stage |
| GSAS-II | FCJ, Gauss-Legendre per profile point, count from the angular gap over the width, rounded up to a table, capped at 400; single precision (checked) |
| RIETAN-FP | FCJ, Gauss-Legendre per reflection, 10 to 100 nodes; Howard's model by Simpson with 3 to 9 terms (checked) |
| TOPAS | `axial_conv` (Cheary & Coelho 1998) by `axial_n_beta` rays, no printed default |
| FullProf | FCJ under `Npr = 7`; quadrature not documented |
| MAUD, EasyDiffraction (cryspy) | no FCJ; an empirical or Bérar-Baldinozzi asymmetry |
| BGMN | ray-traced instrument function, computed once before the fit and held |

## Reflections past the fitted range

| Program | Margin |
|---|---|
| rietx | `REFLECTION_MARGIN_DEG` 0.5° each side |
| TOPAS | `extra_X_left`, `extra_X_right` 0.5° each side (checked) |
| GSAS-II | none: a reflection must lie strictly inside the limits (checked) |
| RIETAN-FP | none: a reflection centred outside is dropped with its tails (ran) |
| FullProf | 3 × `Wdt` × FWHM above the upper limit (1.8° on PbSO₄); none below the lower (ran) |
| MAUD | `cutoff` × 0.1°, 3° at the default (checked) |
| EasyDiffraction | 4° in 2θ each side of the included points (checked) |
| BGMN | about the Kα₁-Kα₂ split, 0.05° at 30° to 0.6° at 150° (ran) |

## Staging and what a stage holds

| Program | Staging | Held during a fit |
|---|---|---|
| rietx | plans of cumulative stages; the last frees everything the plan freed | reflection list, windows, FCJ nodes: per stage |
| RIETAN-FP | `NAUTO = 2`: early cycles refine subsets (background and scale; widths; asymmetry; widths and asymmetry; cell; atoms), then everything together to convergence. `NAUTO = 1`: the user lists the early cycles | windows follow every evaluation; Le Bail intensities per cycle |
| BGMN | automatic: isotropic models first, anisotropic ones added, then a closing run with everything free restarted from the answer; a weak anisotropic term is switched off | the ray-traced instrument function for the whole fit |
| MAUD | the refinement wizard: cumulative stages (scales and background; cell, zero, B; size and strain; atoms), no final all-free cycle | windows follow every evaluation; texture, strain, Le Bail intensities and structure factors per iteration |
| FullProf | none; the user runs successive files in the manual's advised order | windows and point assignment for the whole run (`Ias = 0`) |
| GSAS-II | none; scripting takes a user list | the reflection list per `Refine` call; windows every evaluation |
| TOPAS | none; `_rem` and `quick_refine` drop parameters for an iteration | the peak buffer up to its tolerances |
| EasyDiffraction | none | nothing: reflection list and windows rebuilt every evaluation |

None of the seven tests whether its answer depends on the path or the start, and none of
their manuals discusses it.

## Surface roughness starting values

| Program | Pitschke | Suortti | Default start |
|---|---|---|---|
| rietx | `RoughnessPitschke` | `RoughnessSuortti` | c and b seeded at 0.3 by the roughness stage |
| RIETAN-FP | yes | yes (and Sparks, Sidey) | none given |
| FullProf | the P₀, Cp, τ form | no | none; shipped examples start Cp 1.23-1.50, τ 0.134-0.145 |
| TOPAS | `Surface_Roughness_Pitschke_et_al` | `Surface_Roughness_Suortti` | not in the reference (in `Topas.inc`, not read) |
| GSAS-II | no | `SurfaceRough` | SRA = SRB = 0, not refined |
| BGMN, MAUD, EasyDiffraction | no | no | |

## Peak-width limits

| Program | U, V, W, X, Y limits | Negative width | Sample-broadening limits |
|---|---|---|---|
| rietx | floors only since 2026-10-21 | Γ_G² clamped at 1e-8 deg² | `lor_size` etc. by their own schema |
| GSAS-II | none | Gaussian variance and Lorentzian width floored per reflection | none |
| FullProf | none | Γ_G set to 1e-10 with a message; peaks vanish (ran) | none |
| RIETAN-FP | none | refused at the start; a step to one is rejected | none |
| TOPAS | no u-y rows in Table 2-1; opt-in `force_positive_fwhm` | undocumented | `CS_L` 0.3 nm to min(2·Val + 0.3, 10 000) |
| MAUD | ±0.5, ±0.3, ±0.1 on U, V, W, not enforced by its least squares | floored at 1e-7° | size 50-5000 Å, strain ≤ 0.005, not enforced |
| EasyDiffraction | none | H_G² floored at machine ε; a negative H_L passes | none |
| BGMN | no Caglioti widths | fatal error | Profex writes B1 ≤ 0.01 and k2 ≤ 1e-4 into the files it creates |

## The tier-2 rows resting on a program default

| Row | Programs that agree | Dissent |
|---|---|---|
| `Source:dispersion` (f′, f″ on for X-rays) | all seven (BGMN through the `.ano` table its default `LAMBDA=CU` names; other line files drop it silently) | none |
| `mode` rows (Rietveld) | GSAS-II, MAUD, EasyDiffraction, BGMN (Le Bail only with no atoms); FullProf, RIETAN-FP and TOPAS make the user state it | none |
| `two_theta_limits` rows (the full range) | GSAS-II, FullProf, RIETAN-FP, MAUD, EasyDiffraction; BGMN takes the instrument function's range; TOPAS's default is not stated (its `start_X`, `finish_X` are optional) | none |
| `refine:solver` (Marquardt-damped) | GSAS-II, TOPAS, RIETAN-FP, MAUD, EasyDiffraction, BGMN (regularised Gauss-Newton) | FullProf: Gauss-Newton with relaxation factors, undamped |
| `_TCH_ETA`, `_TCH_GAMMA` | GSAS-II, FullProf, RIETAN-FP, EasyDiffraction, TOPAS (whose §7.2 prints the cubic η term as 0.1116, likely a misprint of 0.11116) | none; MAUD and BGMN do not use TCH |
| `CELL_MIN_LENGTH_A` (1.5 Å) | TOPAS | none floor a cell length; the floor binds on no real cell |
| `auto_background:seed` (not from the data) | all seven start from zero, a constant or the user's numbers | none |
| `BRINDLEY_MU_R_FENCE` | the citation; FullProf prints the same classes as text | not asked of the others |

## Sources

Line numbers are at the versions above. RIETAN-FP's and FullProf's manuals are cited by
section, TOPAS's Technical Reference by section and keyword as printed.

| Program | Window | Staging and freezing | Roughness, widths, limits |
|---|---|---|---|
| GSAS-II 5.8.4 | `GSASIIpwd.getWidthsCW` (`GSASIIpwd.py:811-832`); used at `GSASIIstrMath.py:4071-4077`; FCJ in `sources/powsubs/psvfcjo.for:176-188`; reflections strictly inside the limits, `GSASIIstrIO.py:3175-3177` | hkl list once per `Refine`, `GSASIIstrIO.py:3131`; `DefaultControls`, `GSASIIobj.py:18-20`; `HessianLSQ`, `GSASIImath.py:164-432` | `SurfaceRough`, `GSASIIpwd.py:129-140`, SRA = SRB = 0 at `GSASIIdataGUI.py:2078`; width floors `GSASIIstrMath.py:3901, 3903`; no default limits (`parmMinDict` empty, `GSASIIscriptable.py:2983`); `dropOOBvars`, `GSASIIstrMain.py:1198-1230` |
| FullProf 8.20 | `Wdt`, Appendix LINE 8; floored at 3 (ran); `Ias`, LINE 4 ("reordering ... only at the first cycle") | the manual's advised order, Rietveld section; solver, Mathematical section eqs 3.5-3.7 | P₀, Cp, τ roughness, LINE 15; negative Γ_G² message in `fp2k.inf` (Sep 2002); TCH coefficients eqs 3.16-3.17 |
| TOPAS (Tech. Ref. v9) | `ymin_on_ymax`, §7.1 and the `lam` entry, default 0.001; `peak_buffer_step` and `aberration_range_change_allowed`, §7.4, Table 7-3; per-derivative rebuilds, §7.7; `extra_X_left`/`_right`, default 0.5 | §2.1 (only named parameters refine); §5 (Newton-Raphson with Marquardt, BCCG §5.1); §5.15-5.17 cycles | roughness macros §22.1.8 (signatures only); Table 2-1 in §2.17 (no u-y rows; cell, occupancy, `CS_L` rows); η's printed 0.1116 in §7.2 |
| RIETAN-FP 3.12 | `PC`, per-peak height fraction (listing text "Cut-off = PC*(PEAK INTENSITY)"); recomputed each evaluation (ran) | `NAUTO`, §17.3.17; Le Bail intensities per cycle, §10.1-10.3; stall handling, §17.8.2 | roughness models, §3.2; FCJ by Gauss-Legendre 10-100 nodes, §3.10.3; negative width refused (ran); TCH, eqs 3.66-3.67 |
| BGMN 4.2.23 | no cut seen to 22° from a peak (ran) | automatic ladder and closing run, manual §A.4 and Doebelin & Kleeberg (2015) J. Appl. Cryst. 48, 1573, §2; instrument function held, manual §2.1 | no roughness model, §6.4; B1, k1, k2, §5.5-5.6; limits by RG-CD active set, §5.1; no esd at a limit, §A.4; Profex's default limits, its UI reference §3.4.7 |
| MAUD 3.07 | `_pd_proc_ls_peak_cutoff` default 30 HWHM, `R/diffr/PseudoVoigtPeak.java:267-268` | wizard stages, `R/comp/launchRefineWizard.java` and `FilePar.prepareWizard`; per-iteration holds, `COMP_STATUS` in `FilePar` | Caglioti bounds `InstrumentBroadeningPVCaglioti.initializeAsNew`; bounds not enforced, `FilePar.checkBound`, `LeastSquareFit` |
| EasyDiffraction 0.21.1 | `cutoff_fwhm` default 0 (none), `cryspy/A_functions_base/powder_diffraction_const_wavelength.py:207`; crysfml `WDT 30`, `easydiffraction/analysis/calculators/crysfml.py:125` | everything per evaluation, `easydiffraction/analysis/calculators/cryspy.py:201, 349`; hkl margin `cryspy/procedure_rhochi/rhochi_pd.py:141-148` | widths unbounded, `variable.py:397-400`; H_G² floor, `powder_diffraction_const_wavelength.py:123` |

Found beside the questions, for rietx-bench rather than rietx: its BGMN case names
`LAMBDA=cu_hoelzer97`, which has no `.ano` table, so that run has no anomalous dispersion
(12 % of |F| on Pb (101)), while its `engine.toml` says it uses `cu.ano`.
