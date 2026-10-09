# WP-1933 — the CIF module beyond the structure block: the pattern block, the multi-block layout, and the validation hook

Milestone: unscheduled · Status: 🔄 2026-10-09 — claimed by @yue-here
Track: Coming from another code
Depends on: 1319 (#756, #752)
Priority: P2 2026-10-09 — was P3 until 1319 landed the registry, number rule and structure block it builds on; #756's later chunks, a named user waiting

## Goal

The refinement CIF passes checkCIF with A = 0 and B = 0 or each one justified, as
#756 § 2.2 states. `structure_from_cif` reads each block of a multi-phase file and
the su it carries. A label the reader cannot turn into an element is refused at
read with the label named.

## Context

This WP is chunks C-d, C-e and C-g of issue #756, filed 2026-10-09 when the
maintainer gave [1319](1319-structure-interchange.md) C-a to C-c. The design is
#756's body (§ 2.2 the refinement CIF, § 2.5 checkCIF, § 4 the C-W2, C-W3 and C-W5
rows) and the reporter's comment of 2026-10-06, whose table carries each chunk's
acceptance. Each chunk builds on 1319's `rietx/io/cif/` registry, number rule and
structure block, so read 1319's Context for the decisions already taken
(dictionaries vendored whole, the deprecated H-M tag dropped, § 7's defaults).
C-f (magCIF parent record) is [1911](1911-the-foreign-writers-state-what-the-other-program-reads.md)'s.

- **C-d, the pdCIF pattern block** (C-W2). The raw `_pd_meas_*` loop of every
  measured point, su in parentheses, weights with 0 on excluded points, d-spacing,
  2θ ranges, a wavelength loop from `Source.lines`, the reflection loop, QPA, PO,
  extinction and absorption, restraint/constraint/shift counts, text fields with su,
  `_pd_calc_method`, `_pd_instr_geometry`, and σ(V) taken from the covariance at fit
  close (`refine.py`). `io/exporters.py:514` writes `_pd_proc_2theta_corrected` for
  an uncorrected grid and `:516` writes the undefined `_pd_proc_intensity_total_su`
  (both checked at `5d1f5f67`). The second empties 1319's registry allow-list.
  Acceptance: `read_pdcif` reads back 5753 FAP points with weight 0 on the two
  excluded.
- **C-e, the multi-block layout and the reader** (C-W3). Overall, phase and pattern
  blocks with the `_pd_block_id` trio beside `_audit_block_code`;
  `structure_from_cif(block=)`; su on read (today the reader drops all 22 su of
  `fap_refinement.cif`, reading through `gemmi.read_small_structure`). The NAC +
  CaF₂ file that `structure_from_cif` refuses on `main` reads block by block. Land
  it after #757's I-c, which edits the same reader lines.
- **C-g, the validation hook** (C-W5). The VRF template, the GSAS-II phase CIF as a
  declared profile over the registry, and the recorded checkCIF alert lists as
  fixtures. Before a magnetic block is written the hook calls #758's
  `validate_magnetic_phase`, and a phase carrying `MAGNETIC_P1_MISMATCH` is refused.

**The reader's setting** (from [1118](1118-foreign-model-files.md), 2026-09-16,
moved here from 1319). A CIF can state its setting in three places, and gemmi's
small-structure reader uses one. It prefers `_space_group_name_H-M_alt` over
`_symmetry_space_group_name_H-M`, ignores `_space_group_IT_coordinate_system_code`
(the core dictionary says that item "cannot be used to define the coordinate
system"), and ignores a `_space_group_symop_operation_xyz` loop. So a bare
`F d -3 m` over origin-2 operations reads here as choice 1, where GSAS-II reads it
correctly by checking the operations. `crystallography.symmetry.setting_from_operators`
already does that comparison for the `.gpx` reader and would close the gap in
`structure_from_cif` with no new authority. Separately, `structure_from_cif`'s two
paths resolve a bare multi-setting symbol two ways: the primary takes
`gemmi.read_small_structure`'s spacegroup (`F d -3 m:2`), the fallback calls
`find_spacegroup_by_name` on the raw string (`F d -3 m:1`). The 8a and 16d
multiplicities swap between them. Only the resolvers were measured; no file was
built that takes the fallback.

**A label read as a species** (issue #752, triage 2026-10-08, reproduced at
`5d1f5f67`). COD 9001547 (spangolite) has `_atom_site_label` and no
`_atom_site_type_symbol`, so `Structure.from_cif` takes the species from the label.
A plain label (`Cu1`, `O2`, `H3`) is rewritten to its element with a
`CIF_SPECIES_NORMALISED` note. A label with a separator or a suffix (`O-h3`,
`O-H7A`) is left as the species, and the refusal comes at the first evaluation
(`ValueError: phase '9001547' atom 7 ('O-h3'): cannot read an element symbol from
species 'O-h3'`), because the compile boundary has no diagnostics channel. The
class is every label `cif._SITE_LABEL` (`^[A-Za-z]{1,2}\d+$`) does not match:
`O1A`, `Cu1A`, `O-h3`, `Ow1`, `Fe(1)`, `C1_2`. A hydrate's `Ho1` (hydroxyl
hydrogen) already reads as holmium, so a wider rule needs `_chemical_formula_sum`
as a check on the elements it may produce. The decision is how far a label may be
read when the file states no type symbol. Whatever is chosen is a repair at read
with a `Diagnostic` (`io/CLAUDE.md`), and the unreadable remainder refuses at read
with the label named. No count of COD files in this class was measured.

**What 1319's structure block left** (C-c, 2026-10-09). Five items, each placed
in a chunk:

- **C-d.** checkCIF's PLAT981/PLAT986 (G) ask for f′ and f″. A refinement CIF
  knows them at its wavelength (`_atom_type_scat_dispersion_real`/`_imag`). A Le
  Bail or Pawley CIF states no formula, Z, Mr, density or `_atom_type` loop
  (`blocks.write_structure_block(composition=)`), and its dummy site is still
  written without #756 § 2.1's `_atom_site_calc_flag dum`.
- **C-e.** `structure_from_cif` reads a stated multiplicity only under the
  deprecated `_atom_site_symmetry_multiplicity` (`cif.py` `_site_statements`), so
  the `_atom_site_site_symmetry_multiplicity` the writer now emits goes unread.
- **C-g.** The GSAS-II phase CIF still writes B and the deprecated
  `_symmetry_space_group_name_H-M` by calling the block's parts. That tag stays on
  `registry.KNOWN_VIOLATIONS` until the profile is declared.
- **Kept as is.** A mass number stays in `_atom_type_symbol` (`57Fe`) so the round
  trip holds, though the dictionary's grammar puts digits only before a charge
  (`blocks._types`).

A long `_atom_type_scat_source` (113 characters) made PLATON skip every test while
the report still said "No syntax errors" (`blocks.SCAT_SOURCE_MAX` holds it at
40). A report whose value table comes back empty is a silent PLATON. Run settings
and alert lists are in 1319's Context.

## Non-goals

- **Not C-a, C-b or C-c**: [1319](1319-structure-interchange.md). **Not C-f**:
  [1911](1911-the-foreign-writers-state-what-the-other-program-reads.md).
- **Not CIF 2.0** (#756 § 3), msCIF (#678), torsions or the ionic bond criterion
  (#759).

## Tasks

- [ ] C-d, the pdCIF pattern block, f′/f″ in the `_atom_type` loop and the dummy
      site's `calc_flag`, with its checkCIF re-run.
- [ ] C-e, the multi-block layout, `structure_from_cif(block=)`, su and the current
      multiplicity tag on read; the
      reader's setting from the operator loop through `setting_from_operators`, and
      one resolver for a bare symbol.
- [ ] #752: decide how far a label is read without a type symbol, repair at read
      with a `Diagnostic`, refuse the remainder at read by label.
- [ ] C-g, the validation hook, the VRF template, the GSAS-II profile, the recorded
      reports as fixtures.
- [ ] Tests for each, with the COD 9001547 file as a fixture if its licence allows
      (COD is CC0), else a synthetic one.
- [ ] Skill: a reference row for any new diagnostic code, or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_exporters.py tests/test_magcif.py tests/test_projects_gsas2.py tests/test_cif_registry.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: the recorded checkCIF report on the FAP and NAC + CaF₂ refinement CIFs
shows A = 0, and B = 0 or each one justified in a `_vrf_` record; every block of
the NAC + CaF₂ file reads back with its su.

## References

- Issue #756 and its comment of 2026-10-06; issues #752, #757, #758.
- Toby, B. H. (2006), ITC Vol. G ch. 3.3 and 4.2 — the pdCIF block layout and items.

## Handover log

- **2026-10-09** — created by 1319's session, from #756's C-d, C-e and C-g and
  1319's inherited reader entries (#752, and the two 1118 setting findings). No open
  WP owned them: 1911 owns writers for other programs, and this is the package's own
  format.
