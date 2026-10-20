# Exported files

This page gives the three export writers and the items a refinement CIF holds, including the structure block that opens every CIF from rietx.

[How to export the refined structure as a CIF and the reflection list as a table](../guides/export.md) gives the procedure and reads both files back.
[Files written for other programs](foreign-writers.md) gives the TOPAS, FullProf, GSAS and GSAS-II files.

## Writers

| Call | Writes |
|---|---|
| `write_refinement_cif` | the refined structure, the fit and the pattern, as a CIF |
| `write_reflection_table` | one row per emission line and reflection: hkl, d, 2θ, \|F\|² and intensity |
| `write_qpa_table` | the quantitative phase analysis |

`Refinement.write_cif`, `Refinement.write_reflection_table` and `Refinement.write_qpa_table` write the same files from the last fit.
`Refinement.write_cif` also writes the reflection loop, which only a fit's compiled model can build.
`write_refinement_cif` takes the result, the structure and the instrument, so take `structure` from `Refinement.fitted_structure`, which holds the refined values and their esds.
A table's suffix `.tsv` or `.tab` makes it tab-separated.

`rietx.viz.html.write_html` writes the interactive page, and `RefinementResult.plot` writes the static figure.
Both work on a base install.

## The refinement CIF

The CIF is the one a journal asks for, so it carries more than the coordinates.
Per phase it writes the agreement indices of [The refinement result](result.md): `_refine_ls_R_I_factor` (R<sub>B</sub>), `_refine_ls_R_factor_all` (R<sub>F</sub>) and `_refine_ls_number_reflns`.
It writes the bond distances, contacts and angles as `_geom_bond_`, `_geom_contact_` and `_geom_angle_` loops, with esds in value(esd) form.
The loops list each bond once, where `GeometryTable` lists it from each end so that the rows naming an atom count its neighbours ([Derived quantities](derived.md#bonding-geometry)).

Each `_geom_*_site_symmetry_*` code indexes the `_space_group_symop_` loop written into the same block.
A code that pointed at whatever order the reader's own library generated would name a different atom.

With `pattern=` the profile loop holds every measured point, and a weight of 0 marks each point the fit did not use.
Without it the loop holds only the fitted points.
A single-phase file reads back through `Structure.from_cif` and `read_pdcif`.
A multi-phase file has one block per phase, each of which reads back as a structure, while the pattern loop and the refinement items are in the first block only.

## The structure block

Every CIF this package writes, `Structure.to_cif` included, opens each phase with the same structure block.

It names the setting three ways.
The resolved Hermann-Mauguin symbol goes under `_space_group_name_H-M_alt`, beside the Hall symbol, the IT number and the crystal system.
The full `_space_group_symop_` loop follows, which is the loop the geometry codes index.
An H-M symbol cannot fix the origin, and the Hall symbol and the operations can, so a bare `F d -3 m` never reaches the file.
The deprecated `_symmetry_space_group_name_H-M` is not written.
The GSAS-II phase CIF is the one exception, since GSAS-II reads that tag first ([Files written for other programs](foreign-writers.md#gsas-ii-phase-cif)).

Displacements are U (`_atom_site_U_iso_or_equiv`, with `_atom_site_adp_type` `Uiso` or `Uani`), with each site's multiplicity beside it.
The block also states the formula in Hill order, Z, M<sub>r</sub>, the calculated density and the cell volume, an `_atom_type` loop, and the dictionaries it conforms to: `cif_core.dic` 3.3.0, plus `cif_pd.dic` 2.5.0 in a refinement CIF and `cif_mag.dic` 0.9.9 for a magnetic phase.
A type symbol is the species rietx computes, so `Cu+` is written `Cu1+`, and an ion rietx's table lacks is written as the neutral atom with `_atom_type_description` saying so.

A value with an esd is written in value(esd) form.
A value without one is written as the shortest text that reads back as the same number, so a β of 90.00004 survives a round trip.
Two phases whose names collapse to one block name, such as `ph 1` and `ph-1`, get distinct blocks.
A label with whitespace and a non-finite number are refused by name before the file is written.

Run through IUCr checkCIF, a structure-only file reports the same volume, symmetry, formula, M<sub>r</sub>, density and Z that checkCIF computes.
Its remaining alerts ask for single-crystal and instrument items a powder structure does not have.
