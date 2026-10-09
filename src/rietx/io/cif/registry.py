"""Every tag a CIF written by this build carries, and what the dictionary calls it.

**What a row states.**  The tag as written (the flat DDL1 alias for core and
powder items, the dotted DDLm name for magnetic ones, as
:mod:`~rietx.crystallography.magcif` explains), the DDLm ``_definition.id`` it
spells, the definition's ``_type.purpose`` and ``_type.contents``, and which
output kinds carry it.  Names, purposes and contents are facts about the
dictionaries; no definition text is copied here, and the dictionaries
themselves are vendored under ``tests/data`` and never shipped.

**What holds it true.**  ``tests/test_cif_registry.py`` runs every writer and
reads the dictionaries, and asserts three things: every written tag is a row
here, every row is written by some writer (so no row outlives its writer), and
every row's tag is defined and not deprecated, with its ``definition_id``,
``purpose`` and ``contents`` the dictionary's own.  Two tags break the last
rule today and sit on :data:`KNOWN_VIOLATIONS`, which the same test holds to
shrinking.  The writers read ``contents``: :func:`~rietx.io.cif.numbers.text`
refuses whitespace in a single-token tag by it.

**Output kinds** (issue #756 § 2).  ``structure`` is
:meth:`~rietx.schemas.structure.Structure.to_cif`, ``refinement``
:func:`~rietx.io.exporters.write_refinement_cif`, ``gsas2``
:func:`~rietx.io.projects.gsas2.write_gsas2_phase_cif`.  ``magnetic`` is the
magCIF block, which rides in a structure or refinement CIF of a phase carrying
``magnetic_symmetry``.  The structure-block tags a magnetic phase also carries
are counted under the kind of the file, not under ``magnetic``.

References
----------
- Hall, Allen & Brown (1991), *Acta Cryst.* **A47**, 655: the CIF format.
- COMCIFS ``cif_core.dic`` 3.3.0, doi:10.1107/cifdic_core_3.3.0;
  ``cif_pd.dic`` 2.5.0; ``cif_mag.dic`` 0.9.9 (github.com/COMCIFS): every
  ``definition_id``, ``purpose`` and ``contents`` below.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...crystallography.magcif import PRIVATE_TAGS as _MAGCIF_PRIVATE

#: The output kinds a row may name.
OUTPUT_KINDS: tuple[str, ...] = ("structure", "refinement", "gsas2", "magnetic")


@dataclass(frozen=True)
class Tag:
    """One written tag.

    ``definition_id`` and ``purpose`` are ``None`` only for a private tag or an
    undefined one on :data:`KNOWN_VIOLATIONS`.  ``contents`` is the
    dictionary's ``_type.contents``, and for those tags this module's own
    statement, since the writer quotes or refuses a value by it.
    """

    name: str
    definition_id: str | None
    purpose: str | None
    contents: str
    kinds: frozenset[str]


#: Tags no dictionary defines, written under this build's own prefix.  Exempt
#: from the dictionary check; the magCIF module says why each exists.
PRIVATE_TAGS: frozenset[str] = frozenset(_MAGCIF_PRIVATE)

#: The tags written today that the dictionaries reject.  A later chunk removes
#: each; the registry test fails if this set gains a member or keeps one that
#: no longer violates.
KNOWN_VIOLATIONS: frozenset[str] = frozenset({
    # undefined in cif_pd.dic 2.5.0; the pattern block of WP-1933 (C-d) replaces it
    "_pd_proc_intensity_total_su",
    # alias of _space_group.name_H-M_full deprecated 2003-10-04; the structure
    # block dropped it (C-c), and gsas2.py writes it on purpose for GSAS-II
    # until WP-1933's C-g declares that file's profile
    "_symmetry_space_group_name_H-M",
})

_STRUCTURE = frozenset({"structure", "refinement", "gsas2"})
_BLOCK = frozenset({"structure", "refinement"})
_REFINEMENT = frozenset({"refinement"})
_GSAS2 = frozenset({"gsas2"})
_MAGNETIC = frozenset({"magnetic"})


def _rows(kinds: frozenset[str],
          *rows: tuple[str, str | None, str | None, str]) -> tuple[Tag, ...]:
    return tuple(Tag(name, did, purpose, contents, kinds)
                 for name, did, purpose, contents in rows)


_TAGS: tuple[Tag, ...] = (
    # the structure block (io/cif/blocks.py), the parts the GSAS-II phase CIF
    # shares with it
    *_rows(
        _STRUCTURE,
        ("_cell_length_a", "_cell.length_a", "Measurand", "Real"),
        ("_cell_length_b", "_cell.length_b", "Measurand", "Real"),
        ("_cell_length_c", "_cell.length_c", "Measurand", "Real"),
        ("_cell_angle_alpha", "_cell.angle_alpha", "Measurand", "Real"),
        ("_cell_angle_beta", "_cell.angle_beta", "Measurand", "Real"),
        ("_cell_angle_gamma", "_cell.angle_gamma", "Measurand", "Real"),
        ("_space_group_name_H-M_alt", "_space_group.name_H-M_alt", "Encode", "Text"),
        ("_space_group_symop_operation_xyz", "_space_group_symop.operation_xyz",
         "Encode", "Text"),
        ("_atom_site_label", "_atom_site.label", "Encode", "Word"),
        ("_atom_site_type_symbol", "_atom_site.type_symbol", "Link", "Word"),
        ("_atom_site_fract_x", "_atom_site.fract_x", "Measurand", "Real"),
        ("_atom_site_fract_y", "_atom_site.fract_y", "Measurand", "Real"),
        ("_atom_site_fract_z", "_atom_site.fract_z", "Measurand", "Real"),
        ("_atom_site_occupancy", "_atom_site.occupancy", "Measurand", "Real"),
        ("_atom_site_adp_type", "_atom_site.ADP_type", "State", "Text"),
        ("_atom_site_disorder_assembly", "_atom_site.disorder_assembly", "Encode", "Word"),
        ("_atom_site_disorder_group", "_atom_site.disorder_group", "Encode", "Word"),
        ("_atom_site_aniso_label", "_atom_site_aniso.label", "Link", "Word"),
        ("_atom_site_aniso_U_11", "_atom_site_aniso.U_11", "Measurand", "Real"),
        ("_atom_site_aniso_U_22", "_atom_site_aniso.U_22", "Measurand", "Real"),
        ("_atom_site_aniso_U_33", "_atom_site_aniso.U_33", "Measurand", "Real"),
        ("_atom_site_aniso_U_12", "_atom_site_aniso.U_12", "Measurand", "Real"),
        ("_atom_site_aniso_U_13", "_atom_site_aniso.U_13", "Measurand", "Real"),
        ("_atom_site_aniso_U_23", "_atom_site_aniso.U_23", "Measurand", "Real"),
    ),
    # the rest of the structure block, which the GSAS-II phase CIF does not
    # write until its profile is declared (WP-1933 C-g); its operation loop
    # has no ids
    *_rows(
        _BLOCK,
        ("_audit_creation_date", "_audit.creation_date", "Encode", "DateTime"),
        ("_audit_creation_method", "_audit.creation_method", "Describe", "Text"),
        ("_audit_conform_dict_name", "_audit_conform.dict_name", "Encode", "Text"),
        ("_audit_conform_dict_version", "_audit_conform.dict_version", "Encode", "Word"),
        ("_chemical_formula_sum", "_chemical_formula.sum", "Encode", "Text"),
        ("_chemical_formula_weight", "_chemical_formula.weight", "Number", "Real"),
        ("_cell_volume", "_cell.volume", "Measurand", "Real"),
        ("_cell_formula_units_Z", "_cell.formula_units_Z", "Number", "Real"),
        ("_space_group_crystal_system", "_space_group.crystal_system", "State", "Text"),
        ("_space_group_IT_number", "_space_group.IT_number", "Number", "Integer"),
        ("_space_group_name_Hall", "_space_group.name_Hall", "Encode", "Text"),
        ("_space_group_symop_id", "_space_group_symop.id", "Number", "Integer"),
        ("_exptl_crystal_density_diffrn", "_exptl_crystal.density_diffrn",
         "Measurand", "Real"),
        ("_atom_type_symbol", "_atom_type.symbol", "Encode", "Word"),
        ("_atom_type_number_in_cell", "_atom_type.number_in_cell", "Number", "Real"),
        ("_atom_type_description", "_atom_type.description", "Describe", "Text"),
        ("_atom_type_scat_source", "_atom_type_scat.source", "Describe", "Text"),
        ("_atom_site_U_iso_or_equiv", "_atom_site.U_iso_or_equiv", "Measurand", "Real"),
        ("_atom_site_site_symmetry_multiplicity",
         "_atom_site.site_symmetry_multiplicity", "Number", "Integer"),
    ),
    # the refinement CIF (io/exporters.py)
    *_rows(
        _REFINEMENT,
        ("_diffrn_radiation_wavelength", "_diffrn_radiation_wavelength.value",
         "Measurand", "Real"),
        ("_pd_proc_ls_prof_wR_factor", "_pd_proc_ls.prof_wR_factor", "Number", "Real"),
        ("_pd_proc_ls_prof_R_factor", "_pd_proc_ls.prof_R_factor", "Number", "Real"),
        ("_pd_proc_ls_prof_wR_expected", "_pd_proc_ls.prof_wR_expected", "Number", "Real"),
        ("_refine_ls_goodness_of_fit_all", "_refine_ls.goodness_of_fit_all",
         "Measurand", "Real"),
        ("_refine_ls_number_parameters", "_refine_ls.number_parameters", "Number", "Integer"),
        ("_pd_proc_number_of_points", "_pd_proc.number_of_points", "Number", "Integer"),
        ("_pd_proc_ls_special_details", "_pd_proc_ls.special_details", "Describe", "Text"),
        ("_pd_proc_ls_profile_function", "_pd_proc_ls.profile_function", "Describe", "Text"),
        ("_pd_proc_ls_background_function", "_pd_proc_ls.background_function",
         "Describe", "Text"),
        ("_refine_ls_R_I_factor", "_refine_ls.R_I_factor", "Number", "Real"),
        ("_refine_ls_R_factor_all", "_refine_ls.R_factor_all", "Number", "Real"),
        ("_refine_ls_number_reflns", "_refine_ls.number_reflns", "Number", "Integer"),
        ("_geom_bond_atom_site_label_1", "_geom_bond.atom_site_label_1", "Link", "Word"),
        ("_geom_bond_atom_site_label_2", "_geom_bond.atom_site_label_2", "Link", "Word"),
        ("_geom_bond_distance", "_geom_bond.distance", "Measurand", "Real"),
        ("_geom_bond_site_symmetry_1", "_geom_bond.site_symmetry_1", "Composite", "Symop"),
        ("_geom_bond_site_symmetry_2", "_geom_bond.site_symmetry_2", "Composite", "Symop"),
        ("_geom_contact_atom_site_label_1", "_geom_contact.atom_site_label_1",
         "Link", "Word"),
        ("_geom_contact_atom_site_label_2", "_geom_contact.atom_site_label_2",
         "Link", "Word"),
        ("_geom_contact_distance", "_geom_contact.distance", "Measurand", "Real"),
        ("_geom_contact_site_symmetry_1", "_geom_contact.site_symmetry_1",
         "Composite", "Symop"),
        ("_geom_contact_site_symmetry_2", "_geom_contact.site_symmetry_2",
         "Composite", "Symop"),
        ("_geom_angle_atom_site_label_1", "_geom_angle.atom_site_label_1", "Link", "Word"),
        ("_geom_angle_atom_site_label_2", "_geom_angle.atom_site_label_2", "Link", "Word"),
        ("_geom_angle_atom_site_label_3", "_geom_angle.atom_site_label_3", "Link", "Word"),
        ("_geom_angle", "_geom_angle.value", "Measurand", "Real"),
        ("_geom_angle_site_symmetry_1", "_geom_angle.site_symmetry_1", "Composite", "Symop"),
        ("_geom_angle_site_symmetry_2", "_geom_angle.site_symmetry_2", "Composite", "Symop"),
        ("_geom_angle_site_symmetry_3", "_geom_angle.site_symmetry_3", "Composite", "Symop"),
        ("_pd_proc_2theta_corrected", "_pd_proc.2theta_corrected", "Measurand", "Real"),
        ("_pd_proc_intensity_total", "_pd_proc.intensity_total", "Measurand", "Real"),
        ("_pd_proc_intensity_total_su", None, None, "Real"),
        ("_pd_calc_intensity_total", "_pd_calc.intensity_total", "Number", "Real"),
        ("_pd_proc_intensity_bkg_calc", "_pd_proc.intensity_bkg_calc", "Measurand", "Real"),
    ),
    # the GSAS-II phase CIF (io/projects/gsas2.from_structure): the bare
    # symbol GSAS-II reads first, and the B its import was measured on
    *_rows(
        _GSAS2,
        ("_symmetry_space_group_name_H-M", "_space_group.name_H-M_full", "Describe", "Text"),
        ("_atom_site_B_iso_or_equiv", "_atom_site.B_iso_or_equiv", "Measurand", "Real"),
    ),
    # the magCIF block (crystallography/magcif.write_magnetic_block)
    *_rows(
        _MAGNETIC,
        ("_space_group_symop_magn_operation.id",
         "_space_group_symop_magn_operation.id", "Key", "Text"),
        ("_space_group_symop_magn_operation.xyz",
         "_space_group_symop_magn_operation.xyz", "Encode", "Text"),
        ("_space_group_symop_magn_centering.id",
         "_space_group_symop_magn_centering.id", "Key", "Word"),
        ("_space_group_symop_magn_centering.xyz",
         "_space_group_symop_magn_centering.xyz", "Encode", "Text"),
        ("_space_group_magn.number_BNS", "_space_group_magn.number_BNS", "Describe", "Text"),
        ("_space_group_magn.name_BNS", "_space_group_magn.name_BNS", "Describe", "Text"),
        ("_space_group_magn.number_OG", "_space_group_magn.number_OG", "Encode", "Word"),
        ("_space_group_magn.transform_BNS_Pp_abc",
         "_space_group_magn.transform_BNS_Pp_abc", "Encode", "Text"),
        ("_atom_site_moment.label", "_atom_site_moment.label", "Link", "Word"),
        ("_atom_site_moment.crystalaxis_x", "_atom_site_moment.crystalaxis_x",
         "Measurand", "Real"),
        ("_atom_site_moment.crystalaxis_y", "_atom_site_moment.crystalaxis_y",
         "Measurand", "Real"),
        ("_atom_site_moment.crystalaxis_z", "_atom_site_moment.crystalaxis_z",
         "Measurand", "Real"),
        ("_atom_site_moment.crystalaxis_x_su", "_atom_site_moment.crystalaxis_x_su",
         "SU", "Real"),
        ("_atom_site_moment.crystalaxis_y_su", "_atom_site_moment.crystalaxis_y_su",
         "SU", "Real"),
        ("_atom_site_moment.crystalaxis_z_su", "_atom_site_moment.crystalaxis_z_su",
         "SU", "Real"),
        ("_atom_site_moment.magnitude", "_atom_site_moment.magnitude", "Measurand", "Real"),
        ("_atom_site_moment.magnitude_su", "_atom_site_moment.magnitude_su", "SU", "Real"),
        # the label is a site label, the ion a species, the Landé g a number
        ("_rietx_atom_site_moment.g", None, None, "Real"),
        ("_rietx_atom_site_moment.ion", None, None, "Text"),
        ("_rietx_atom_site_moment.label", None, None, "Word"),
    ),
)

#: The registry, keyed by the tag as written.
TAGS: dict[str, Tag] = {tag.name: tag for tag in _TAGS}
