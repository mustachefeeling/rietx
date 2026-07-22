# Attribution

pxrd-refine is an independent implementation, but its design and mathematics
draw on published literature and on existing open-source software. This file
records every source of inspiration or data, its license, and exactly what was
used. Sources under GPL were **studied only**; no GPL code has been ported.

## Algorithms and equations (literature — cited in docstrings and docs)

- Rietveld, H. M. (1969). *J. Appl. Cryst.* 2, 65–71 — the profile refinement method.
- Caglioti, Paoletti & Ricci (1958). *Nucl. Instrum.* 3, 223–228 — U,V,W width law.
- Thompson, Cox & Hastings (1987). *J. Appl. Cryst.* 20, 79–83 — TCH pseudo-Voigt.
- Finger, Cox & Jephcoat (1994). *J. Appl. Cryst.* 27, 892–900 — axial-divergence asymmetry.
- Waasmaier & Kirfel (1995). *Acta Cryst.* A51, 416–431 — 5-Gaussian form factors.
- McCusker et al. (1999). *J. Appl. Cryst.* 32, 36–50 — Rietveld refinement guidelines.
- Toby, B. H. (2006). *Powder Diffraction* 21, 67–70 — agreement indices.
- Bérar & Lelann (1991). *J. Appl. Cryst.* 24, 1–5 — serial-correlation esd correction.
- Hill & Howard (1987). *J. Appl. Cryst.* 20, 467–474 — QPA scale-factor relation.
- Le Bail, Duroy & Fourquet (1988). *Mater. Res. Bull.* 23, 447–452 — Le Bail intensity extraction.
- Coelho, A. A. (2005). *J. Appl. Cryst.* 38, 455–461; (2018) 51, 210–218 & 428–435 —
  minimizer design ideas (bound-constrained solves, adaptive Marquardt). Algorithms
  reimplemented from the papers; TOPAS itself is proprietary and was not consulted as code.
- Eilers, P. H. C. (2003). *Anal. Chem.* 75, 3631 — Whittaker smoother.
- Baek et al. (2015). *Analyst* 140, 250 — arPLS baseline estimation.
- Ryan et al. (1988). *Nucl. Instrum. Meth.* B34, 396 — SNIP background clipping.
- David, W. I. F. (2004). *J. Res. NIST* 109 — cumulative-χ² diagnostics.

## Open-source software studied or used

| Project | License | Relationship |
|---|---|---|
| lmfit | BSD-3 | **API inspiration**: the Parameter model (value/vary/min/max/expr). No code ported. |
| GSAS-II | BSD-style (Argonne) | **Behavioral reference** for conventions and validation goldens. No code ported. |
| CrysPy | MIT | Reference for pure-Python Rietveld mathematics. No code ported. |
| Dans_Diffraction | Apache-2.0 | Reference for scattering computations. No code ported. |
| pymatgen | MIT | Cross-check for structure factors/multiplicities in tests. |
| cctbx | BSD-style | Cross-check for symmetry constraints in tests. |
| EasyDiffraction | BSD-3 | Architecture reference (schema-driven design). No code ported. |
| pybaselines (derb12) | BSD-3 | **Algorithm reference** for arPLS/SNIP implementations (reimplemented from the papers with the pybaselines documentation as a guide); optional dependency for extended baseline algorithms. |
| gemmi | MPL-2.0 | **Dependency** — CIF parsing, space-group operations, hkl utilities. |
| BGMN / Profex | GPL | Studied (papers/docs only). **No code ported.** |
| xrayutilities | GPL-2.0 | Studied (papers/docs only). **No code ported.** |

## Data tables

- `src/pxrdref/data/f0_WaasKirf.dat` — Waasmaier & Kirfel (1995) 5-Gaussian f0
  coefficients, obtained from the ESRF DABAX collection (public scientific data,
  redistributed by silx (MIT) among others). Cite Waasmaier & Kirfel (1995).
- Test patterns under `tests/data/` — see `tests/data/README.md` for per-file
  provenance (NIST / APS 11-BM public data are works of the U.S. Government).
