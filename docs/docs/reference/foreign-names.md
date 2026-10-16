---
html_theme.sidebar_secondary.remove: true
---

# Names in other programs

This page gives the name each rietx parameter has in GSAS-II, GSAS, TOPAS and FullProf, and the unit conversions between them.

Each foreign name is one that rietx's own readers and writers for that format use, and a test checks every name in the table against that code.
An empty cell means rietx neither reads nor writes that quantity in that format.
The conversions below the table are the ones the code applies.

## The table

| rietx | GSAS-II | GSAS | TOPAS | FullProf |
| --- | --- | --- | --- | --- |
| `phases.*.cell.a`, `b`, `c` | `Cell` | `ABC` | `a`, `b`, `c` | `a`, `b`, `c` |
| `phases.*.cell.alpha`, `beta`, `gamma` | `Cell` | `ANGLES` | `al`, `be`, `ga` | `alpha`, `beta`, `gamma` |
| `phases.*.atoms.*.x`, `y`, `z` | atom row | atom record | `x`, `y`, `z` | `X`, `Y`, `Z` |
| `phases.*.atoms.*.occ` | atom row | atom record | `occ` | `Occ` |
| `phases.*.atoms.*.biso` | `Uiso` | atom record | `beq` | `Biso` |
| `phases.*.atoms.*.u11` to `u23` | | | `u11` to `u23` | |
| `phases.*.atoms.*.moment.crystalaxis_*` | | | `mlx`, `mly`, `mlz` | |
| `phases.*.scale` | `Scale` | | `scale` | `Scale` |
| `instrument.zero_shift` | `Zero` | | `th2_offset` | `Zero` |
| `instrument.source.lines.*.wavelength` | `Lam`, `Lam1`, `Lam2` | | `lo` | `Lambda1`, `Lambda2` |
| `instrument.source.lines.*.weight` | `I(L2)/I(L1)` | | `la` | `Ratio` |
| `instrument.polarization` | `Polariz.` | | `LP_Factor` | |
| `instrument.profile.u`, `v`, `w` | `U`, `V`, `W` | `GU`, `GV`, `GW` | | `U`, `V`, `W` |
| `instrument.profile.x` | `X` | `LX` | | `Y` |
| `instrument.profile.y` | `Y` | `LY` | | `X` |
| `instrument.geometry.axial_sl`, `axial_hl` | `SH/L` | `S/L`, `H/L` | `Finger_et_al` | |
| `instrument.background.c*` | | | `bkg` | |
| `phases.*.gauss_size` | | | | `GauSiz` |
| `instrument.source.difc`, `difa`, `difb` | `difC`, `difA`, `difB` | | | |
| `instrument.source.tzero` | `Zero` | | | |
| `instrument.source.profile_tof.alpha1` | `alpha` | | | |
| `instrument.source.profile_tof.beta0`, `beta1` | `beta-0`, `beta-1` | | | |
| `instrument.source.profile_tof.sig0`, `sig1`, `sig2` | `sig-0`, `sig-1`, `sig-2` | | | |

## What each reader builds

The GSAS-II `.gpx` reader and the TOPAS reader each build a `Structure` from the cell, the atoms and their displacement parameters.
GSAS-II's instrument names come from its `.instprm` file, which `rietx` reads and writes separately.
TOPAS's instrument and profile names, and FullProf's profile, zero and wavelength names, are written by rietx's exporters and not read back.
A TOPAS file's size and strain macros, its 2θ corrections and its preferred orientation are reported when the file is read, and not carried.

## Conversions

Caglioti U, V and W
: GSAS-II and GSAS state a Gaussian variance in centidegrees².
  rietx states the Gaussian FWHM² in degrees², so rietx's value is the GSAS-II value × 8 ln 2 × 10⁻⁴.
  FullProf's U, V and W are FWHM² in degrees², the same as rietx's.

Lorentzian X and Y
: GSAS-II and GSAS state X and Y in centidegrees, so rietx's value is theirs ÷ 100.
  FullProf swaps the letters.
  FullProf's X is the tan θ term and its Y the 1/cos θ term, the reverse of rietx and GSAS-II.
  FullProf also states widths per phase, so its X is rietx's `y` plus the phase's `lor_strain`, and its Y is `x` plus `lor_size`.

Displacement parameter
: GSAS-II and GSAS state Uiso, and B = 8π²·Uiso.
  TOPAS's `beq` and FullProf's `Biso` are B already.

Axial divergence
: GSAS-II states one `SH/L`, the sum of the specimen and detector terms.
  Reading one splits it evenly between `axial_sl` and `axial_hl`, and writing one sums them.
  GSAS states `S/L` and `H/L` separately.

Polarisation
: GSAS-II's `Polariz.` is rietx's K.
  TOPAS states an angle c in `LP_Factor(c)`, and K = 1/(1 + cos² c).

Magnetic moment
: TOPAS's `mlx`, `mly` and `mlz` are components along the fractional axes.
  rietx's crystal-axis component is each one times its own lattice parameter in Å.

Phase scale
: A GSAS-II or GSAS scale does not compare with rietx's, so rietx seeds its own on reading.
  TOPAS's `scale` is read as the file states it by default.
  `to_structure(scale="rietx")` converts it with the file's `LP_Factor` or its neutron flag.
