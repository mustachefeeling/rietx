# Test data provenance

| File | Contents | Source | License/status |
|---|---|---|---|
| `11BM_NAC.fxye` | Na2Ca3Al2F14 (NAC) powder pattern, APS beamline 11-BM, λ = 0.4139090 Å (from the accompanying `.prm`), 54000 points, GSAS ESD (fxye) format | GSAS-II tutorials repo, `TOF-CW Joint Refinement/data/` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `11bm_gsas.prm` | GSAS instrument parameter file for the above (profile from SRM 660a LaB6 fit) | same | same |
| `cod_1000236.cif` | NAC structure, Courbion & Ferey (1988) J. Solid State Chem. 76, 426, space group I2₁3, a = 10.257 Å | Crystallography Open Database entry 1000236 | COD (public domain dedication) |
| `cod_1000055.cif` | LaB6 structure, Pm-3m, a = 4.157597 Å | COD entry 1000055 | COD (public domain dedication) |
| `nist_srm660c_100a.cif` | NIST SRM 660c LaB6 certification dataset incl. measured profile (5332 pts in 24 stitched scan regions, Cu Kα + graphite post-monochromator, NIST DBD, R = 217.5 mm) — v0.2 lab-instrument acceptance (`test_acceptance_srm660c.py`) | NIST Public Data Repository mds2-2315 (data.nist.gov) | NIST open data license (U.S. Government work) |
| `FAP.XRA` | Fluorapatite Ca₅(PO₄)₃F powder pattern, conventional lab Bragg-Brentano, Cu Kα doublet, 15-130.04° 2θ, 5753 pts, GSAS STD (counts-only) format — v0.2 cross-code acceptance (`test_acceptance_fap.py`) | GSAS-II tutorials repo, `LabData/data/` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `INST_XRY.PRM` | GSAS instrument parameter file for the above (λ = 1.5405/1.5443 Å, POLA 0.5, Kα2/Kα1 0.5, starting GU/GV/GW = 2/−2/5 centideg²) | same | same |
| `FAP.EXP` | GSAS's **converged** refinement of `FAP.XRA` — the source of every reference value and of the refinement protocol the acceptance test mirrors | same | same |

Reference values used in acceptance tests:

- NAC cell: a = 10.257(1) Å at RT per Courbion & Ferey (1988) (COD 1000236);
  high-accuracy powder determinations report a ≈ 10.2496-10.2506 Å depending on
  temperature/calibration — the acceptance test therefore checks internal
  consistency (Le Bail vs Rietveld) and agreement with the 11-BM wavelength
  calibration rather than a certificate-grade absolute value.
- LaB6 SRM 660c certified lattice parameter: a = 4.156826(8) Å **at 22.5 °C**
  (expanded uncertainty, k = 2; NIST certificate,
  tsapps.nist.gov/srmext/certificates/660c.pdf).  The `…_100a` data block was
  measured at 20.85 °C and its CIF records NIST's own recomputed cell for
  exactly this dataset, **a = 4.156780 Å** — the value the acceptance test
  compares against (consistent with the certificate via the Sirota et al. 1998
  thermal expansion used by NIST).  The certificate/CIF wavelength scale is
  λ(Cu Kα1) = 1.5405929 Å (Hölzer et al. 1997), which is what
  `Instrument.bragg_brentano(radiation="CuKa")` ships.
- SRM 660c auxiliary references: CIF-recorded specimen displacement
  −0.07877 mm (the v0.2 fit recovers −0.0801 mm with zero fixed);
  Hölzer integrated Kα2/Kα1 intensity ratio ≈ 0.52 (fit: 0.513).
- Fluorapatite (`FAP.EXP`, GSAS's own converged values — a **cross-code
  consistency** reference, not a certificate): cell a = 9.371724(36) Å,
  c = 6.885867(37) Å (`CRS1 ABC`/`ABCSIG`); Rwp = 0.1005, Rp = 0.0766 over
  5750 channels (`HST 1 RPOWD`); refined Lorentzian size LX = 3.35183 and
  strain LY = 2.48803 centideg, specimen shift `shft` = 4.90166, with
  GU/GV/GW held at 2/−2/5 and the zero point held at 0 (`HAP1 1PRCF` flags
  `NNNYYNNY…`, `HST 1 ICONS`).  Structure (7 sites in P 6₃/m, `CRS1 AT`
  records) is used as the starting model.  The v0.2 fit gives Rwp = 0.0973,
  Rp = 0.0776, LX-equivalent 0.0323°, and a cell +116/+113 ppm from GSAS's —
  a uniform d-scale offset, discussed in the test's module docstring.
