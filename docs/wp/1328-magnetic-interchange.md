# WP-1328 — magnetic interchange: magCIF in and out, and the readers stop refusing

Milestone: unscheduled · Status: ⬜
Depends on: 1327 (the model the files describe); 1118 soft (the coverage
registry the foreign readers report through)

## Goal

A magnetic structure enters the package from a magCIF (the operator list,
the moments, the propagation vector) and leaves as one from a refined
result, and the three foreign-file refusals that exist because "rietx has no
magnetic model" are lifted to *read* where the construct maps onto 1327's
model and stay *refused by name* where it does not.

## Context

Third rung of the magnetic scattering track (ROADMAP § Unscheduled). The
readers are where the package meets a user's existing work, and every one of
them currently refuses a magnetic phase with the same sentence: importing the
nuclear half alone "would look complete" (`io/projects/coverage.py`, the
`magnetic structure` feature at `Stance.REFUSED` over `mag_space_group`,
`mag_only`, `mag_only_for_mag_sites`, `mlx`, `mly`, `mlz`, `mg`,
`mag_atom_out`; the TOPAS reader's raise at ≈ line 1915; WP-1314's refusal
list for Jana `.m50`). Those sentences were right, and 1327 makes them wrong.

**magCIF is the interchange format, and it carries what 1327 stores.** The
COMCIFS `magnetic_dic` (`cif_mag.dic`, tags checked 2026-09-02) defines
`_space_group_symop_magn_operation.xyz` and
`_space_group_symop_magn_centering.xyz` (operators with the time-reversal
sign), `_atom_site_moment.crystalaxis_x/y/z` and their `_su`, the spherical
form `_atom_site_moment.spherical_modulus/polar/azimuthal`,
`_parent_propagation_vector.kxkykz`, and `_space_group_magn.name_BNS` /
`name_OG` / `transform_BNS_Pp_abc` for the symbol and the parent-to-magnetic
cell transform. MAGNDATA and ISODISTORT emit this form, so a reader that
takes it takes every published commensurate structure. `io/cif.py`'s
`structure_from_cif` is the reader to extend; it already carries the
diagnostics channel a repair must report through (species normalised, a cell
angle corrected), and a magnetic block reaches the same channel.

**Writing it is the exporter's job** (`io/exporters.py`,
`write_refinement_cif`): the refined moments with esds, the operator list
that was refined under, and the symbol carried through as metadata. WP-1319
guards the CIF writer with checkCIF, which has no magCIF arm; the guard here
is the dictionary itself, tags checked against `cif_mag.dic` the way the core
tags are checked against the core dictionary. Fetch both the way the standing
memory says (COMCIFS via `gh api`).

**The foreign readers, by construct.** TOPAS states a magnetic structure on
the same `str` as the nuclear one (`mag_space_group`, `mlx mly mlz` on the
site), which is 1327's shape: the site moments map, the symbol is metadata,
and the operators come from TOPAS's own `mag_space_group` number only if the
file also lists them; otherwise the phase is *reported*, not read, and the
message says which tag would have made it readable. `mag_only` is a phase
contributing no nuclear intensity, a shape 1327 does not have, and stays
refused by name. FullProf `.pcr` magnetic phases (Jbt = ±1, Fourier
components per k, a separate phase) map only when k is commensurate and the
phase is described in its magnetic cell; the Fourier-component form is
refused with the sentence naming the incommensurate fence. Jana `.m50`
magnetic phases: the refusal list in 1314 shortens by one entry once this
lands, and 1314's own file is where that edit goes.

**The rule the readers follow** is 1118's: report or refuse, never drop. A
nuclear-only structure that looks complete is the failure every one of these
refusals exists to prevent, so a magnetic construct the reader cannot carry
is still named in the result.

## Non-goals

- The model itself, its physics, its DOFs: 1327.
- The `.pcr` and `.m50` readers as such: 1118 and 1314 own them; this WP
  owns the magnetic rows in their coverage tables.
- checkCIF conformance for the nuclear CIF: 1319.
- Incommensurate structures in any format.

## Tasks

- [ ] magCIF reader in `structure_from_cif`: operators with ε, centrings,
      crystal-axis moments (spherical accepted and converted), the parent
      propagation vector, the BNS/OG symbol as metadata; a file describing
      modulation refused by name.
- [ ] magCIF writer in `write_refinement_cif`: moments with esds, operators,
      symbol; tags checked against `cif_mag.dic`; a round trip through the
      reader is bit-identical on every stored field.
- [ ] `coverage.py`: the `magnetic structure` feature split by keyword into
      *read* (`mag_space_group`, `mlx`, `mly`, `mlz`, `mag_atom_out`) and
      *refused* (`mag_only`, `mag_only_for_mag_sites`), each with its
      sentence; the TOPAS reader's raise becomes the registry's stance.
- [ ] The `.pcr` magnetic rows: Jbt = ±1 in the magnetic cell read,
      Fourier-component form refused by name; a fixture per stance.
- [ ] Manual Part 1 (`using/data.md` and the interchange chapter), skill
      routing row for "you were handed a magnetic structure", and 1314's
      refusal list amended.
- [ ] Tests: round trips, the coverage stances, perturbation fuzz in
      `test_readers_robust.py`'s arm.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_magcif.py tests/test_projects_topas.py -q
.venv/bin/python -m ruff check src tests examples
```

- A MAGNDATA entry for Cr₂WO₆ or LaMnO₃ (licence checked per file) reads
  into the structure 1327's acceptance refines, and the refined result
  writes back to a file the reader reads to bit-identical stored fields.
- A TOPAS `.inp` with `mag_space_group` and site moments reads with the
  moments in place; one with `mag_only` is refused by name.
- No reader drops a magnetic construct silently: every fixture with one
  either carries it or names it.

## References

- COMCIFS `magnetic_dic` — github.com/COMCIFS/magnetic_dic, `cif_mag.dic`.
- Gallego, S. V. et al. (2016). *J. Appl. Cryst.* **49**, 1750 — MAGNDATA.
  **Not in the corpus; ask.**
- [1327](1327-magnetic-structure.md) the model; [1118](1118-foreign-model-files.md)
  the coverage registry and the report-or-refuse rule;
  [1314](1314-mfile-reader.md) the Jana refusal list;
  [1319](1319-structure-interchange.md) the CIF writer's guard.

## Handover log

- **2026-09-02** — created, from the assessment of PR #221, which had the
  readers as one task inside a single WP. Split off because the readers meet
  a user's existing work and their refusals are today's most visible
  statement that the package has no magnetic model. No code touched. First
  task is the magCIF reader.
