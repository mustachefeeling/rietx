# Test data provenance

| File | Contents | Source | License/status |
|---|---|---|---|
| `11BM_NAC.fxye` | Na2Ca3Al2F14 (NAC) powder pattern, APS beamline 11-BM, λ = 0.4139090 Å (from the accompanying `.prm`), 54000 points, GSAS ESD (fxye) format | GSAS-II tutorials repo, `TOF-CW Joint Refinement/data/` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `11bm_gsas.prm` | GSAS instrument parameter file for the above (profile from SRM 660a LaB6 fit) | same | same |
| `cod_1000236.cif` | NAC structure, Courbion & Ferey (1988) J. Solid State Chem. 76, 426, space group I2₁3, a = 10.257 Å | Crystallography Open Database entry 1000236 | COD (public domain dedication) |
| `cod_1000055.cif` | LaB6 structure, Pm-3m, a = 4.157597 Å | COD entry 1000055 | COD (public domain dedication) |
| `nist_srm660c_100a.cif` | NIST SRM 660c LaB6 certification dataset incl. measured profile (5332 pts, Cu Kα + graphite analyzer) — reserved for v0.2 lab-instrument acceptance | NIST Public Data Repository mds2-2315 (data.nist.gov) | NIST open data license (U.S. Government work) |

Reference values used in acceptance tests:

- NAC cell: a = 10.257(1) Å at RT per Courbion & Ferey (1988) (COD 1000236);
  high-accuracy powder determinations report a ≈ 10.2496-10.2506 Å depending on
  temperature/calibration — the acceptance test therefore checks internal
  consistency (Le Bail vs Rietveld) and agreement with the 11-BM wavelength
  calibration rather than a certificate-grade absolute value.
- LaB6 SRM 660c certified lattice parameter: a = 4.156826(?) Å (see NIST
  certificate, tsapps.nist.gov/srmext/certificates/660c.pdf) — used in v0.2.
