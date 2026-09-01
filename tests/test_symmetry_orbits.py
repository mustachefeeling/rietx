"""Site orbits are group-theoretic, and the two ways they used to go quiet.

An orbit length is |G| / |stabiliser| — a divisor of the group order — not a
count of how many images survived a pairwise comparison.  The greedy dedup this
replaced had no such invariant, and returned 22 and 30 under a group of order
36 (issue #215).  A bare origin-ambiguous H-M symbol picks a setting that
changes site multiplicities, and said nothing (issue #217).  Both are wrong
*compositions* rather than wrong fits: Rwp does not move, ZMV and every weight
fraction do.

The β-rhombohedral-boron case that issue #215 measured is reproduced by the
float that bit it, not by the ICSD file it came from — the coordinates are the
mechanism and the file is licensed data.  ``B11_SHAPE`` is a five-decimal x/y
pair of an 18h-type site whose ``y − 2x`` lands at ``1.0000000000000286e-04``,
just over a strict ``1e-4``, exactly as B11's does.
"""

from __future__ import annotations

import gemmi
import numpy as np
import pytest

from rietx.crystallography.symmetry import (
    SITE_TOL,
    expand_positions,
    get_spacegroup,
    setting_alternatives,
    site_orbit,
    snap_diagnostics,
)
from rietx.refine import _symmetry_silence_diagnostics
from rietx.schemas.common import Parameter as P
from rietx.schemas.structure import Atom, Cell, Phase, Structure

#: An 18h-type site of ``R -3 m:H``: y = 2x, |G| = 36, so 18 or 36 and nothing
#: else.  The z is arbitrary and free.
R3M_X, R3M_Z = 0.05620, 0.32670

#: x and y as a five-decimal file writes them, differing from y = 2x by the
#: same float ICSD 18318's B11 site does.
B11_SHAPE = (0.05620, 0.11250, 0.32670)


def test_b11_shape_is_the_float_that_bit() -> None:
    """The reproduction is pinned to the arithmetic, not to a data file."""
    x, y, _ = B11_SHAPE
    assert y - 2 * x == pytest.approx(1e-4, rel=1e-12)
    assert y - 2 * x > 1e-4          # a strict `<` tolerance excludes it


@pytest.mark.parametrize("offset", [-1.2e-4, -1.0e-4, -8e-5, 0.0,
                                    8e-5, 1.0e-4, 1.2e-4])
def test_orbit_is_always_a_divisor_of_the_group_order(offset: float) -> None:
    """Sweeping across the tolerance prints only 18 or 36 — never 22 or 30."""
    sg = get_spacegroup("R -3 m:H")
    n = len(expand_positions(sg, np.array([R3M_X, 2 * R3M_X + offset, R3M_Z])))
    assert n in (18, 36), f"orbit {n} is not a possible multiplicity under |G|=36"
    assert len(sg.operations()) % n == 0


def test_the_tolerance_boundary_is_inclusive() -> None:
    """A deviation *at* 1e-4 is within it; which side of `<` is fp, not physics."""
    sg = get_spacegroup("R -3 m:H")
    assert len(expand_positions(sg, np.array(B11_SHAPE))) == 18
    orbit = site_orbit(sg, np.array(B11_SHAPE))
    assert orbit.multiplicity == 18
    assert orbit.shift == pytest.approx(5e-5, rel=1e-6)
    # snapped exactly onto y = 2x, and only along the forbidden direction
    assert orbit.position[1] - 2 * orbit.position[0] == pytest.approx(0.0, abs=1e-15)
    assert orbit.position[2] == R3M_Z


def test_a_site_on_its_special_position_is_not_moved() -> None:
    """Bit-identical for a structure whose orbits were already right."""
    sg = get_spacegroup("R -3 m:H")
    xyz = np.array([R3M_X, 2 * R3M_X, R3M_Z])
    orbit = site_orbit(sg, xyz)
    assert orbit.shift == 0.0
    assert orbit.multiplicity == 18
    assert np.array_equal(orbit.position, xyz % 1.0)
    assert np.array_equal(orbit.images[0], xyz % 1.0)


def test_a_general_position_takes_the_whole_group_untouched() -> None:
    sg = get_spacegroup("R -3 m:H")
    xyz = np.array([0.1234, 0.5678, 0.9137])
    orbit = site_orbit(sg, xyz)
    assert orbit.multiplicity == len(sg.operations()) == 36
    assert orbit.shift == 0.0
    assert len(orbit.stabilizer) == 1
    assert np.array_equal(orbit.position, xyz)


def test_orbit_does_not_depend_on_operation_order() -> None:
    """The old failure mode: a partition that followed gemmi's ordering.

    Feeding the *images* of one site back in must give the same multiplicity —
    every member of an orbit has a conjugate stabiliser, hence the same order.
    """
    sg = get_spacegroup("R -3 m:H")
    orbit = site_orbit(sg, np.array(B11_SHAPE))
    for image in orbit.images:
        assert site_orbit(sg, image).multiplicity == orbit.multiplicity


def test_the_invariant_holds_across_every_setting_gemmi_knows() -> None:
    """|G| / |stabiliser| over all 564 settings, at and across the tolerance.

    Positions chosen to sit on, near and off the special positions that broke
    the greedy version: the cubic ¼¼¼ and ⅛⅛⅛ sites, where a jitter admits
    some members of the site symmetry and misses others.
    """
    rng = np.random.default_rng(0)
    bases = [np.array(p) for p in ((0.1234, 0.5678, 0.9137), (0.0, 0.0, 0.0),
                                   (0.25, 0.25, 0.25), (0.5, 0.0, 0.25),
                                   (1 / 3, 2 / 3, 0.1), (0.125, 0.125, 0.125))]
    checked = 0
    for sg in gemmi.spacegroup_table():
        order = len(sg.operations())
        for base in bases:
            for scale in (0.0, 3e-5, 9.9e-5, 1.01e-4, 5e-4):
                orbit = site_orbit(sg, base + scale * rng.standard_normal(3))
                assert order % orbit.multiplicity == 0
                assert orbit.multiplicity * len(orbit.stabilizer) == order
                assert orbit.shift <= SITE_TOL * (1 + 1e-9)
                checked += 1
    assert checked == 16_920


def test_the_guard_message_names_the_invariant() -> None:
    """``ORBIT_NOT_A_MULTIPLICITY`` is unreachable, so it is provoked by hand."""
    from rietx.crystallography import symmetry

    sg = get_spacegroup("R -3 m:H")
    # a stabiliser that is not the snapped point's own: the only way the count
    # and |G|/|stabiliser| can disagree
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(symmetry, "_COINCIDENCE_TOL", 0.4)   # merges distinct images
        with pytest.raises(ValueError, match="ORBIT_NOT_A_MULTIPLICITY"):
            symmetry.site_orbit(sg, np.array([0.1234, 0.5678, 0.9137]))


# --- the multiplicity reaches the model, the constraints and QPA -------------


def test_one_authority_serves_the_forward_model_and_the_constraints() -> None:
    """``select_orbit_ops`` and ``stabilizer_rotations`` read the same orbit."""
    from rietx.crystallography.structure_factor import select_orbit_ops
    from rietx.crystallography.wyckoff import stabilizer_rotations

    sg = get_spacegroup("R -3 m:H")
    orbit = site_orbit(sg, np.array(B11_SHAPE))
    rot, tran = select_orbit_ops(sg, np.array(B11_SHAPE))
    assert len(rot) == len(tran) == orbit.multiplicity == 18
    assert np.array_equal(rot, orbit.rot)
    assert len(stabilizer_rotations(sg, np.array(B11_SHAPE))) == 2
    # the two answer the same question: |G| = multiplicity × |stabiliser|
    assert len(rot) * len(stabilizer_rotations(sg, np.array(B11_SHAPE))) == 36


def test_wyckoff_multiplicity_follows() -> None:
    from rietx.crystallography.wyckoff import site_constraints

    sc = site_constraints("R -3 m:H", B11_SHAPE)
    assert sc.multiplicity == 18
    assert sc.wyckoff.startswith("18")


# --- SITE_SNAPPED_TO_SPECIAL_POSITION ----------------------------------------


def test_snap_is_reported_with_site_shift_and_multiplicity() -> None:
    sg = get_spacegroup("R -3 m:H")
    found = snap_diagnostics(sg, [("B11", B11_SHAPE)],
                             source="phase 'boron'", prefix="phases.0")
    assert len(found) == 1
    d = found[0]
    assert d.code == "SITE_SNAPPED_TO_SPECIAL_POSITION"
    assert d.level == "warning"
    assert d.where == ["phases.0.atoms.0"]
    assert "B11" in d.message
    assert "5.0e-05" in d.message          # the shift
    assert "multiplicity 18" in d.message  # what it bought


def test_a_structure_already_on_its_positions_says_nothing() -> None:
    sg = get_spacegroup("R -3 m:H")
    assert snap_diagnostics(sg, [("B", (R3M_X, 2 * R3M_X, R3M_Z))],
                            source="x", prefix="phases.0") == []


def test_the_cif_reader_reports_on_its_own_channel() -> None:
    """The reader's channel, the same message — bundled standards stay silent."""
    from rietx.crystallography.cif import structure_from_cif

    for path in ("tests/data/cod_1000055.cif", "tests/data/cod_1000236.cif"):
        found: list = []
        structure_from_cif(path, diagnostics=found)
        assert [d for d in found
                if d.code == "SITE_SNAPPED_TO_SPECIAL_POSITION"] == []


# --- SPACE_GROUP_SETTING_ASSUMED ---------------------------------------------


def _spinel(symbol: str) -> Structure:
    """Origin-choice-2 coordinates, which is how papers print spinel."""
    return Structure(phases=[Phase(
        name="spinel", space_group=symbol,
        cell=Cell(a=P(value=8.0806), b=P(value=8.0806), c=P(value=8.0806),
                  alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        atoms=[
            Atom(label="Mg", species="Mg",
                 x=P(value=0.125), y=P(value=0.125), z=P(value=0.125)),
            Atom(label="Al", species="Al",
                 x=P(value=0.5), y=P(value=0.5), z=P(value=0.5)),
            Atom(label="O", species="O",
                 x=P(value=0.2624), y=P(value=0.2624), z=P(value=0.2624)),
        ])])


def test_the_spinel_multiplicities_swap_between_settings() -> None:
    """The measured table from issue #217, which is why the choice must be said."""
    sites = [(0.125, 0.125, 0.125), (0.5, 0.5, 0.5), (0.2624, 0.2624, 0.2624)]
    counts = {s: [len(expand_positions(get_spacegroup(s), np.array(p)))
                  for p in sites]
              for s in ("F d -3 m:1", "F d -3 m:2")}
    assert counts["F d -3 m:1"] == [16, 8, 32]
    assert counts["F d -3 m:2"] == [8, 16, 32]


@pytest.mark.parametrize("symbol,taken,others", [
    ("F d -3 m", "F d -3 m:1", ("F d -3 m:2",)),
    ("227", "F d -3 m:1", ("F d -3 m:2",)),          # a number names no setting
    ("R -3 m", "R -3 m:H", ("R -3 m:R",)),           # axes, not origin
])
def test_a_bare_ambiguous_symbol_names_what_it_took(symbol, taken, others) -> None:
    assert setting_alternatives(symbol) == (taken, others)


@pytest.mark.parametrize("symbol", ["F d -3 m:1", "F d -3 m:2", "P b c a",
                                    "R -3 m:H", "P m -3 m"])
def test_a_symbol_that_names_its_setting_is_silent(symbol: str) -> None:
    assert setting_alternatives(symbol) == ("", ())


def test_the_ambiguous_set_is_read_off_the_tables() -> None:
    from rietx.crystallography.symmetry import _settings_by_hm

    assert len(_settings_by_hm()) == 40
    assert all(len(v) > 1 for v in _settings_by_hm().values())


def test_the_setting_diagnostic_quotes_the_composition_each_implies() -> None:
    """The discriminator is the composition, not the symbol (issue #217)."""
    found = [d for d in _symmetry_silence_diagnostics(_spinel("F d -3 m"))
             if d.code == "SPACE_GROUP_SETTING_ASSUMED"]
    assert len(found) == 1
    d = found[0]
    assert d.level == "warning"
    assert d.where == ["phases.0.space_group"]
    assert "F d -3 m:1 → Al8 Mg16 O32" in d.message    # the inverted spinel
    assert "F d -3 m:2 → Al16 Mg8 O32" in d.message    # the one that was meant


def test_naming_the_setting_silences_it() -> None:
    assert [d for d in _symmetry_silence_diagnostics(_spinel("F d -3 m:2"))
            if d.code == "SPACE_GROUP_SETTING_ASSUMED"] == []


def test_a_scaffold_is_not_asked_for_a_composition() -> None:
    """Outside rietveld the atoms are a placeholder, so the composition is a
    fiction — but ``:H`` against ``:R`` changes the operators, so the setting
    is still reported."""
    from rietx.schemas.structure import lebail_scaffold

    scaffold = lebail_scaffold("F d -3 m", [8.08, 8.08, 8.08, 90.0, 90.0, 90.0])
    found = _symmetry_silence_diagnostics(scaffold, "lebail")
    assert [d.code for d in found] == ["SPACE_GROUP_SETTING_ASSUMED"]
    assert "→" not in found[0].message          # no dummy-carbon formula
    assert "F d -3 m:2" in found[0].message
    # and the snap is not reported about a dummy atom
    assert [d for d in _symmetry_silence_diagnostics(scaffold, "pawley")
            if d.code == "SITE_SNAPPED_TO_SPECIAL_POSITION"] == []
