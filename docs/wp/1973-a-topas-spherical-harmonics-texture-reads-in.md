# WP-1973 — a TOPAS spherical-harmonics texture reads in

Milestone: unscheduled · Status: ⬜
Track: Coming from another code
Depends on: 1960 (the model and its conversion to GSAS-II); #131
Priority: P3 2026-10-15 — a workaround covers it: declare `Phase.texture` and refine it from zero; blocked on TOPAS's own output

## Goal

`to_structure` carries a TOPAS `PO_Spherical_Harmonics` block onto
`Phase.texture`, through a conversion measured against TOPAS's own value of
the series at stated coefficients.

## Context

### What exists

WP-1960 landed the model. `Phase.texture` declares an even order and a
name → `Parameter` map of coefficients, and P is Von Dreele's (1997) eq. 2-3:

    P_h = 1 + Σ_l (4π/(2l+1)) · Σ_n C_l^n · k_l(ψ) · K_l^n(h)

K are Bunge's real harmonics, orthonormal over the sphere, with no
Condon-Shortley phase, in a frame with z on the principal axis and x on the
next cell edge (`crystallography/spherical_harmonics.py`'s docstring).
k_l(ψ) = √((2l+1)/4π)·P_l(cos ψ), and ψ is 0° under `bragg_brentano`
(`model/preferred_orientation.TEXTURE_SAMPLE_PSI_DEG`). Names are GSAS-II's
C(l, n) as `c4_0`, `c4_neg4`. The GSAS-II `.gpx` reader carries a texture
through C·‖K_GSAS‖·P_l(0), measured against GSAS-II's `SHPOcal`
(`io/projects/gsas2._gsas2_texture`).

The TOPAS reader reports the macro and drops it: `io/projects/coverage.py`'s
"preferred orientation" row lists `PO_Spherical_Harmonics` as REPORTED. A bare
`spherical_harmonics_hkl` has its own "spherical-harmonics series" row,
because an equation may use the series for broadening instead (clay.inp,
§ 20.17.1). That row stays reported.

### What the Technical Reference says (Version 9, read 2026-10-15)

Public at `https://topas-academic.com/technical_reference`, one HTML page whose
text is the `TECH_REF_HTML_PLAIN` JSON string inside it.

- `spherical_harmonics_hkl` "Defines a hkl dependent symmetrized spherical
  harmonics series". Only the coefficients the point group's selection rules
  allow are generated (Järvinen, 1993). Without user coefficients, TOPAS
  generates them and appends them to the `.out` at the end of the run.
- `PO_Spherical_Harmonics(sh, order)` is `spherical_harmonics_hkl sh sh_order
  order scale_pks = sh;`. So TOPAS's P is the series' value.
- Coefficients are `sh_Cij_prm` rows, `y00 !sh_c00 1` first, then `y20`,
  `y40`, …; cubic ones are `k41`, `k61`, `k62`, `k81`.
- `sh_alpha` is "the angle in degrees between the polar axis and the
  scattering vector". It defaults to 0°, "required for symmetric reflection as
  is the case for Bragg-Brentano geometry". That agrees with rietx's ψ.
- `sh_order` runs from 2 to 8, or to 10 in a cubic class.

It states neither the normalisation nor the crystal frame. Järvinen (1993)
normalises each function to max|Y| = 1, drops the 4π/(2l+1) and uses
P_l(cos α) for the sample term. If TOPAS does the same in rietx's frame, then
at α = 0, C = c_TOPAS / (√(4π/(2l+1))·max|K|). That is a hypothesis from
prose. Root CLAUDE.md requires a foreign unit to be measured against the
format's own output. Whitfield (2009) reports 13 refined terms at order 4 for
P-1 wollastonite, where 14 exist, and says nothing of why. The non-zero-n
names (Whitfield's `p`/`m` letters) and the term list per class are unknown
too.

### What unblocks it

TOPAS's value of `sh` at known hkl and coefficients, one phase per Laue class.
TOPAS writes a record per reflection through `phase_out`:

    phase_out sh.txt load out_record out_fmt out_eqn {
       " %4.0f" = H; " %4.0f" = K; " %4.0f" = L; " %14.10f\n" = sh; }

A first run with no `sh_Cij_prm` gives the generated names. A second run with
each coefficient set to a stated value gives the numbers. Rietx's functions
then fit each term's factor by least squares over the reflections, and a frame
mismatch shows as a poor fit. Two routes: the maintainer runs it, or #131's
contributor does. #131's SRM 1976a plate refinement compares coefficients only
after a fit, which is weaker.

### Licensing

TOPAS is closed: its Technical Reference and its output only, never code.

## Non-goals

- `spherical_harmonics_hkl` in a width equation. It stays reported.
- A non-zero `sh_alpha`, unless the probe measures how it enters. Until then
  it is reported.
- Writing the block to TOPAS. `TOPAS_FIELD_NOT_WRITTEN` names it today
  (WP-1960). Writing it is the inverse of this conversion and can follow it.

## Tasks

- [ ] The probe: the input and its output committed under `tests/data/` with a
      README provenance row, generator beside the numbers as WP-1960's golden is.
- [ ] The conversion, measured per class: names, normalisation and frame,
      written into this file. Whitfield's missing P-1 term answered.
- [ ] The import: `to_structure` carries the macro onto `Phase.texture`, its
      coverage row moves, and a diagnostic states the conversion. A block whose
      coefficients the file does not state, or a non-zero `sh_alpha`, is reported.
- [ ] Tests: the carried texture gives TOPAS's `sh` at every probe reflection.
- [ ] Manual: the TOPAS section of `using/files.md`.
- [ ] Skill: the new code's row in `references/diagnostics-projects.md`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_projects_topas.py
.venv/bin/python -m ruff check src tests examples
```

The bar: under `bragg_brentano`, P from the carried texture equals TOPAS's `sh`
at every probe reflection, to the precision the probe printed.

## References

- Coelho, A. A., TOPAS / TOPAS-Academic Technical Reference, Version 9:
  `spherical_harmonics_hkl`, `PO_Spherical_Harmonics`, `phase_out`, § 20.17.1.
- Järvinen, M. (1993). *J. Appl. Cryst.* 26, 525-531.
  doi:10.1107/S0021889893001219.
- Whitfield, P. S. (2009). *J. Appl. Cryst.* 42, 134-136.
  doi:10.1107/S0021889808041149.
- Von Dreele, R. B. (1997). *J. Appl. Cryst.* 30, 517-525.
  doi:10.1107/S0021889897005918.
- WP-1960 § Pinned by Task 1, the convention and the GSAS-II conversion.

## Handover log

- **2026-10-15** — filed from WP-1960, whose Task 9 read the Technical
  Reference and found no normalisation in it. No open WP owns it: 1455 reads a
  TCHZ profile and 1530 the reader's silences. Next: run the probe, which needs
  TOPAS.
