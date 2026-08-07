"""WP-1028 regressions: robustness on data and CIFs we did not author.

One section per WP item, and every test here failed before its fix.  The
defects were measured on external files (COD entries, ICSD exports, the
PyWPEM CASES data) and are reproduced as synthetic minimal cases so the
suite carries no third-party data; the measured stories live in the WP file.
"""

from __future__ import annotations

import numpy as np
import pytest

from pxrdref import Instrument, PatternData
from pxrdref.schemas.structure import Structure

# ----------------------------------------------------------------------
# (a) species syntaxes that reject valid CIFs — at two lookups, not one
# ----------------------------------------------------------------------

NACL_CIF = """\
data_nacl
_symmetry_space_group_name_H-M 'F m -3 m'
_cell_length_a 5.6402
_cell_length_b 5.6402
_cell_length_c 5.6402
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Na1 {na} 0 0 0 1
Cl1 {cl} 0.5 0.5 0.5 1
"""


def _nacl_cif(tmp_path, na="Na", cl="Cl"):
    path = tmp_path / "nacl.cif"
    path.write_text(NACL_CIF.format(na=na, cl=cl))
    return str(path)


def test_normalize_cif_species_covers_both_wild_forms_and_only_them():
    from pxrdref.crystallography.cif import normalize_cif_species

    label = "site label in the type-symbol column"
    sign = "sign-first charge"
    assert normalize_cif_species("O1") == ("O", label)
    assert normalize_cif_species("Cl1") == ("Cl", label)
    assert normalize_cif_species("CL1") == ("Cl", label)
    assert normalize_cif_species("O-2") == ("O2-", sign)
    assert normalize_cif_species("Ni+3") == ("Ni3+", sign)
    assert normalize_cif_species("Li+1") == ("Li1+", sign)
    # canonical forms are untouched — including the trailing-sign ion that
    # always read fine, and a bare element in any case the lookups handle
    assert normalize_cif_species("Cl1-") == ("Cl1-", None)
    assert normalize_cif_species("O2-") == ("O2-", None)
    assert normalize_cif_species("Na") == ("Na", None)
    # a symbol the table cannot help is never half-rewritten: it passes
    # through verbatim to fail with the lookup's own message
    assert normalize_cif_species("Wat") == ("Wat", None)
    assert normalize_cif_species("D1") == ("D1", None)
    assert normalize_cif_species("Xx1") == ("Xx1", None)


def test_site_label_type_symbols_normalise_at_read(tmp_path):
    diags = []
    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na1", cl="Cl1"),
                                   diagnostics=diags)
    assert [a.species for a in structure.phases[0].atoms] == ["Na", "Cl"]
    assert {d.code for d in diags} == {"CIF_SPECIES_NORMALISED"}
    assert all(d.level == "info" for d in diags)
    where = sorted(w for d in diags for w in d.where)
    assert where == ["phases.0.atoms.0.species", "phases.0.atoms.1.species"]


def test_sign_first_charges_normalise_keeping_the_ion(tmp_path):
    diags = []
    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na+1", cl="Cl-1"),
                                   diagnostics=diags)
    assert [a.species for a in structure.phases[0].atoms] == ["Na1+", "Cl1-"]
    assert len(diags) == 2
    assert all("sign-first charge" in d.message for d in diags)


def test_untouched_species_record_no_diagnostic(tmp_path):
    diags = []
    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na", cl="Cl1-"),
                                   diagnostics=diags)
    assert [a.species for a in structure.phases[0].atoms] == ["Na", "Cl1-"]
    assert diags == []


@pytest.mark.parametrize("dispersion_on", [True, False],
                         ids=["dispersion-on", "dispersion-none"])
def test_normalised_species_compile_under_both_dispersion_settings(
        tmp_path, dispersion_on):
    # the defect fired at the first stage compile, from *two* lookups —
    # resolve_dispersion with the block on, normalize_species either way —
    # so the fix is asserted at compile, under both settings
    from pxrdref.model.forward import compile_model

    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na+1", cl="Cl1"))
    structure.phases[0].scale.value = 5e-3
    ins = Instrument.bragg_brentano(radiation="CuKa")
    if not dispersion_on:
        ins.source.dispersion = None
    tt = np.arange(20.0, 60.0, 0.05)
    pattern = PatternData(two_theta=tt.tolist(),
                          intensity=np.zeros_like(tt).tolist())
    compile_model(structure, ins, pattern, mode="rietveld")
