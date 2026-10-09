"""Every tag a CIF written by this build carries, and what the dictionary calls it.

**What a row states.**  The tag as written (the flat DDL1 alias for core and
powder items, the dotted DDLm name for magnetic ones, as
:mod:`~rietx.crystallography.magcif` explains), the DDLm ``_definition.id`` it
spells, the definition's ``_type.purpose``, and which output kinds carry it.
Names and purposes are facts about the dictionaries; no definition text is
copied here, and the dictionaries themselves are vendored under ``tests/data``
and never shipped.

**What holds it true.**  ``tests/test_cif_registry.py`` runs every writer and
reads the dictionaries, and asserts three things: every written tag is a row
here, every row is written by some writer (so no row outlives its writer), and
every row's tag is defined and not deprecated, with its ``definition_id`` and
``purpose`` the dictionary's own.  Two tags break the last rule today and sit
on :data:`KNOWN_VIOLATIONS`, which the same test holds to shrinking.  The
writers do not read this table yet; the structure block of WP-1319's C-c is
its first consumer.

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
  ``definition_id`` and ``purpose`` below.
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
    undefined one on :data:`KNOWN_VIOLATIONS`.
    """

    name: str
    definition_id: str | None
    purpose: str | None
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
    # alias of _space_group.name_H-M_full deprecated 2003-10-04; C-c drops it
    # from the structure block, and gsas2.py writes it on purpose for GSAS-II
    "_symmetry_space_group_name_H-M",
})

_STRUCTURE = frozenset({"structure", "refinement", "gsas2"})
_LISTED = frozenset({"structure", "refinement"})
_REFINEMENT = frozenset({"refinement"})
_GSAS2 = frozenset({"gsas2"})
_MAGNETIC = frozenset({"magnetic"})


def _rows(kinds: frozenset[str], *rows: tuple[str, str | None, str | None]
          ) -> tuple[Tag, ...]:
    return tuple(Tag(name, did, purpose, kinds) for name, did, purpose in rows)


_TAGS: tuple[Tag, ...] = (
    # the structure block (crystallography/cif.write_structure_block)
    *_rows(
        _STRUCTURE,
        ("_cell_length_a", "_cell.length_a", "Measurand"),
        ("_cell_length_b", "_cell.length_b", "Measurand"),
        ("_cell_length_c", "_cell.length_c", "Measurand"),
        ("_cell_angle_alpha", "_cell.angle_alpha", "Measurand"),
        ("_cell_angle_beta", "_cell.angle_beta", "Measurand"),
        ("_cell_angle_gamma", "_cell.angle_gamma", "Measurand"),
        ("_symmetry_space_group_name_H-M", "_space_group.name_H-M_full", "Describe"),
        ("_space_group_symop_operation_xyz", "_space_group_symop.operation_xyz",
         "Encode"),
        ("_atom_site_label", "_atom_site.label", "Encode"),
        ("_atom_site_type_symbol", "_atom_site.type_symbol", "Link"),
        ("_atom_site_fract_x", "_atom_site.fract_x", "Measurand"),
        ("_atom_site_fract_y", "_atom_site.fract_y", "Measurand"),
        ("_atom_site_fract_z", "_atom_site.fract_z", "Measurand"),
        ("_atom_site_occupancy", "_atom_site.occupancy", "Measurand"),
        ("_atom_site_B_iso_or_equiv", "_atom_site.B_iso_or_equiv", "Measurand"),
        ("_atom_site_adp_type", "_atom_site.ADP_type", "State"),
        ("_atom_site_disorder_assembly", "_atom_site.disorder_assembly", "Encode"),
        ("_atom_site_disorder_group", "_atom_site.disorder_group", "Encode"),
        ("_atom_site_aniso_label", "_atom_site_aniso.label", "Link"),
        ("_atom_site_aniso_U_11", "_atom_site_aniso.U_11", "Measurand"),
        ("_atom_site_aniso_U_22", "_atom_site_aniso.U_22", "Measurand"),
        ("_atom_site_aniso_U_33", "_atom_site_aniso.U_33", "Measurand"),
        ("_atom_site_aniso_U_12", "_atom_site_aniso.U_12", "Measurand"),
        ("_atom_site_aniso_U_13", "_atom_site_aniso.U_13", "Measurand"),
        ("_atom_site_aniso_U_23", "_atom_site_aniso.U_23", "Measurand"),
    ),
    # the operation ids: GSAS-II's loop has none
    *_rows(_LISTED, ("_space_group_symop_id", "_space_group_symop.id", "Number")),
    # the refinement CIF (io/exporters.py)
    *_rows(
        _REFINEMENT,
        ("_diffrn_radiation_wavelength", "_diffrn_radiation_wavelength.value",
         "Measurand"),
        ("_pd_proc_ls_prof_wR_factor", "_pd_proc_ls.prof_wR_factor", "Number"),
        ("_pd_proc_ls_prof_R_factor", "_pd_proc_ls.prof_R_factor", "Number"),
        ("_pd_proc_ls_prof_wR_expected", "_pd_proc_ls.prof_wR_expected", "Number"),
        ("_refine_ls_goodness_of_fit_all", "_refine_ls.goodness_of_fit_all",
         "Measurand"),
        ("_refine_ls_number_parameters", "_refine_ls.number_parameters", "Number"),
        ("_pd_proc_number_of_points", "_pd_proc.number_of_points", "Number"),
        ("_pd_proc_ls_special_details", "_pd_proc_ls.special_details", "Describe"),
        ("_pd_proc_ls_profile_function", "_pd_proc_ls.profile_function", "Describe"),
        ("_pd_proc_ls_background_function", "_pd_proc_ls.background_function",
         "Describe"),
        ("_refine_ls_R_I_factor", "_refine_ls.R_I_factor", "Number"),
        ("_refine_ls_R_factor_all", "_refine_ls.R_factor_all", "Number"),
        ("_refine_ls_number_reflns", "_refine_ls.number_reflns", "Number"),
        ("_geom_bond_atom_site_label_1", "_geom_bond.atom_site_label_1", "Link"),
        ("_geom_bond_atom_site_label_2", "_geom_bond.atom_site_label_2", "Link"),
        ("_geom_bond_distance", "_geom_bond.distance", "Measurand"),
        ("_geom_bond_site_symmetry_1", "_geom_bond.site_symmetry_1", "Composite"),
        ("_geom_bond_site_symmetry_2", "_geom_bond.site_symmetry_2", "Composite"),
        ("_geom_contact_atom_site_label_1", "_geom_contact.atom_site_label_1",
         "Link"),
        ("_geom_contact_atom_site_label_2", "_geom_contact.atom_site_label_2",
         "Link"),
        ("_geom_contact_distance", "_geom_contact.distance", "Measurand"),
        ("_geom_contact_site_symmetry_1", "_geom_contact.site_symmetry_1",
         "Composite"),
        ("_geom_contact_site_symmetry_2", "_geom_contact.site_symmetry_2",
         "Composite"),
        ("_geom_angle_atom_site_label_1", "_geom_angle.atom_site_label_1", "Link"),
        ("_geom_angle_atom_site_label_2", "_geom_angle.atom_site_label_2", "Link"),
        ("_geom_angle_atom_site_label_3", "_geom_angle.atom_site_label_3", "Link"),
        ("_geom_angle", "_geom_angle.value", "Measurand"),
        ("_geom_angle_site_symmetry_1", "_geom_angle.site_symmetry_1", "Composite"),
        ("_geom_angle_site_symmetry_2", "_geom_angle.site_symmetry_2", "Composite"),
        ("_geom_angle_site_symmetry_3", "_geom_angle.site_symmetry_3", "Composite"),
        ("_pd_proc_2theta_corrected", "_pd_proc.2theta_corrected", "Measurand"),
        ("_pd_proc_intensity_total", "_pd_proc.intensity_total", "Measurand"),
        ("_pd_proc_intensity_total_su", None, None),
        ("_pd_calc_intensity_total", "_pd_calc.intensity_total", "Number"),
        ("_pd_proc_intensity_bkg_calc", "_pd_proc.intensity_bkg_calc", "Measurand"),
    ),
    # the GSAS-II phase CIF (io/projects/gsas2.from_structure)
    *_rows(_GSAS2,
           ("_space_group_name_H-M_alt", "_space_group.name_H-M_alt", "Encode")),
    # the magCIF block (crystallography/magcif.write_magnetic_block)
    *_rows(
        _MAGNETIC,
        ("_space_group_symop_magn_operation.id",
         "_space_group_symop_magn_operation.id", "Key"),
        ("_space_group_symop_magn_operation.xyz",
         "_space_group_symop_magn_operation.xyz", "Encode"),
        ("_space_group_symop_magn_centering.id",
         "_space_group_symop_magn_centering.id", "Key"),
        ("_space_group_symop_magn_centering.xyz",
         "_space_group_symop_magn_centering.xyz", "Encode"),
        ("_space_group_magn.number_BNS", "_space_group_magn.number_BNS", "Describe"),
        ("_space_group_magn.name_BNS", "_space_group_magn.name_BNS", "Describe"),
        ("_space_group_magn.number_OG", "_space_group_magn.number_OG", "Encode"),
        ("_space_group_magn.transform_BNS_Pp_abc",
         "_space_group_magn.transform_BNS_Pp_abc", "Encode"),
        ("_atom_site_moment.label", "_atom_site_moment.label", "Link"),
        ("_atom_site_moment.crystalaxis_x", "_atom_site_moment.crystalaxis_x",
         "Measurand"),
        ("_atom_site_moment.crystalaxis_y", "_atom_site_moment.crystalaxis_y",
         "Measurand"),
        ("_atom_site_moment.crystalaxis_z", "_atom_site_moment.crystalaxis_z",
         "Measurand"),
        ("_atom_site_moment.crystalaxis_x_su", "_atom_site_moment.crystalaxis_x_su",
         "SU"),
        ("_atom_site_moment.crystalaxis_y_su", "_atom_site_moment.crystalaxis_y_su",
         "SU"),
        ("_atom_site_moment.crystalaxis_z_su", "_atom_site_moment.crystalaxis_z_su",
         "SU"),
        ("_atom_site_moment.magnitude", "_atom_site_moment.magnitude", "Measurand"),
        ("_atom_site_moment.magnitude_su", "_atom_site_moment.magnitude_su", "SU"),
        *((name, None, None) for name in sorted(_MAGCIF_PRIVATE)),
    ),
)

#: The registry, keyed by the tag as written.
TAGS: dict[str, Tag] = {tag.name: tag for tag in _TAGS}
