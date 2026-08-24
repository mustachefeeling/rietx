"""The TOPAS ``.inp`` project reader.

Every fixture here is written inline, per ``io/CLAUDE.md``: a text format's
lines are self-describing, so a literal in the test says more than a writer
that shares constants with the parser could.

The site-line forms are not invented. Each one below was taken from a real file
in a 606-``.inp`` archive, and the comment on each says what reading it wrong
cost — because the failure mode this reader exists to prevent is not a crash but
a *wrong number with nothing raised*. Two of them were measured: a phase
fraction read as 0.596 wt% when the file said 11.596, and one read as 0.931 when
the file said 60.931.
"""

import pytest

from rietx.io.projects.topas import (
    TopasInpError,
    normalize_space_group,
    normalize_species,
    read_topas_inp,
    resolve_ifdefs,
    strip_comments,
    symbol_table,
    to_structure,
)

# ----------------------------------------------------------------- rule 1, 2


def test_dead_text_outnumbers_live_text():
    """A wavelength read without stripping comments picks the disabled block.

    Real files carry several instrument blocks and disable all but one, so this
    is the difference between the refinement's own λ and a leftover.
    """
    text = strip_comments("""
        /* la 1 lo 0.7093 */
        ' la 1 lo 1.78897
        la 1 lo 0.41368
    """)
    assert "0.41368" in text
    assert "0.7093" not in text
    assert "1.78897" not in text


def test_ifdef_gates_content():
    live = resolve_ifdefs("#define A\n#ifdef A\nkeep\n#else\ndrop\n#endif\n"
                          "#ifdef B\ndrop2\n#else\nkeep2\n#endif")
    assert "keep" in live and "keep2" in live
    assert "drop" not in live and "drop2" not in live


def test_define_after_use_is_still_defined():
    """TOPAS permits it, so symbols are collected before the walk."""
    assert "keep" in resolve_ifdefs("#ifdef LATER\nkeep\n#endif\n#define LATER")


# -------------------------------------------------------------------- rule 4


@pytest.mark.parametrize("written, iucr", [
    ("Cu+1", "Cu1+"),   # TOPAS's sign-first spelling
    ("O-2", "O2-"),
    ("Y+3", "Y3+"),
    ("Cu1+", "Cu1+"),   # already IUCr order, left alone
    ("Co", "Co"),
])
def test_species_are_normalised_to_iucr_order(written, iucr):
    assert normalize_species(written) == iucr


@pytest.mark.parametrize("written, expected", [
    ("Pn-3mZ", "Pn-3m:2"),   # Z = Zentrum = origin choice 2
    ("P63mcZ", "P63mc:2"),
    ("R-3cH", "R-3c:H"),
    ("R-3cR", "R-3c:R"),
    ("Fm-3m", "Fm-3m"),      # a final letter that is part of the symbol
    ("Pnma", "Pnma"),
    ("P1", "P1"),
])
def test_origin_and_axis_suffixes_are_translated_not_dropped(written, expected):
    """Dropping the letter selects the *other* origin with nothing raised —
    for #224 a bare ``Pn-3m`` is choice 1, and Cu2O is conventionally choice 2.
    """
    assert normalize_space_group(written) == expected


# -------------------------------------------------------------------- rule 3

#: One site line per real spelling found in the archive, with the value the
#: file states. The parametrisation is the point: a parser that handles four of
#: these and drops the fifth produces a structure that is wrong in one atom,
#: which is a wrong structure factor and a *better* Rwp than the right model.
SITE_LINES = [
    # plain literals
    ("site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5", (0.0, 0.0, 0.0), 1.0, 0.5),
    # equation for a special position
    ("site A1 x = 1/3; y = 2/3; z 0.25 occ Na+1 1 beq b 0.5",
     (1 / 3, 2 / 3, 0.25), 1.0, 0.5),
    # a *named* refined value, backtick marker
    ("site A1 x nx 0.4938` y ny 0.24625` z nz 0.25` occ Na+1 1 beq b 0.8`",
     (0.4938, 0.24625, 0.25), 1.0, 0.8),
    # `!` fix flag BEFORE the name, and an `_esd` suffix on the number
    ("site A1 x 0 y 0 z !ph1_cr1_z 0.33489_0.00003 occ Cr+3 1. beq !bcr 1",
     (0.0, 0.0, 0.33489), 1.0, 1.0),
    # `@,` — a refined value TOPAS did not name
    ("site A1 x @, 0.19776` y 0.5 z 0.5 occ B 1. beq @, 0.5884`",
     (0.19776, 0.5, 0.5), 1.0, 0.5884),
    # name then equation
    ("site A1 x Zr1_x =1/2; y Zr1_y =1/2; z Zr1_z =1/3; occ Zr 1.0 beq 1",
     (0.5, 0.5, 1 / 3), 1.0, 1.0),
    # the A1/A2/A3 coordinate macro, flag inside the parenthesis
    ("site A1 A1(!xO3, 0.00143 , 0.00143) A2(!yO3, 0.03550 , 0.03550) "
     "A3(!zO3, 0.21526 , 0.21526) occ O 1.0 beq !bval 0",
     (0.00143, 0.03550, 0.21526), 1.0, 0.0),
    # occupancy OMITTED — TOPAS defaults to full, and reading the token after
    # the species as a number picked up the word "beq" and raised ValueError
    ("site A1 x 0.5 y 0. z 0.5 occ Sr+2 beq 0.7650`",
     (0.5, 0.0, 0.5), 1.0, 0.7650),
    # a partial occupancy with a flag and a name
    ("site A1 x 0.5 y 0.5 z 0.5 occ La+3 !LSF_occ_La 0.6 vcocc beq bval1 2.02",
     (0.5, 0.5, 0.5), 0.6, 2.02),
]


@pytest.mark.parametrize("line, xyz, occ, beq", SITE_LINES)
def test_every_real_site_spelling_reads(tmp_path, line, xyz, occ, beq):
    inp = tmp_path / "s.inp"
    inp.write_text(f'str\nphase_name "P"\nspace_group "P1"\na 5.0\n{line}\n')
    (site,) = read_topas_inp(inp).phases[0].sites
    assert (site.x, site.y, site.z) == pytest.approx(xyz)
    assert site.occupancy == pytest.approx(occ)
    assert site.beq == pytest.approx(beq)


def test_an_equation_referencing_another_parameter_resolves(tmp_path):
    """``y = ph1_O1_x;`` is how a tetragonal oxygen says y is tied to x.

    Refusing it cost 14 archive files, the tier-1 Cr2WO6 references among them.
    """
    inp = tmp_path / "s.inp"
    inp.write_text('str\nphase_name "Cr2WO6"\nspace_group "P42/mnm"\na 4.58\n'
                   'site O1 x ph1_O1_x 0.29935` y = ph1_O1_x; z 0 occ O-2 1. '
                   'beq ph1_beq_o1 0.34174`\n')
    (site,) = read_topas_inp(inp).phases[0].sites
    assert site.x == pytest.approx(0.29935)
    assert site.y == pytest.approx(0.29935)


def test_topas_own_evaluated_value_is_preferred_over_the_expression(tmp_path):
    """``= expr;: value`` — the ``;:`` tail is what the converged fit used.

    Taking it means the expression's whole symbol chain never has to be walked,
    which is what made the WISH parametric files readable.
    """
    inp = tmp_path / "s.inp"
    inp.write_text('prm Fe1_x = 1/4 + Fe1_dx;:  0.25733\n'
                   'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
                   'scale =scph1*scb1;:  0.0844868572`\n'
                   'site Fe1 x = Fe1_x; y 0 z 0 occ Fe 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert model.phases[0].scale == pytest.approx(0.0844868572)
    assert model.phases[0].sites[0].x == pytest.approx(0.25733)


def test_symbol_table_binds_the_evaluated_value(tmp_path):
    assert symbol_table("prm Fe1_x = 1/4 + Fe1_dx;:  0.25733")["Fe1_x"] == \
        pytest.approx(0.25733)


def test_an_unresolvable_coordinate_raises_naming_file_phase_and_line(tmp_path):
    """A dropped site is a wrong structure factor, so this is a hard error.

    The measured cost of the alternative: an earlier parser demanded a bare
    number, silently dropped Y1 and Ba1 from YBaCo4O7 (5 of 7 sites) and
    produced a 98 wt% phase-fraction error with a *better* Rwp than the correct
    model — 0.02370 against 0.02353.
    """
    inp = tmp_path / "broken.inp"
    inp.write_text('str\nphase_name "Unreadable"\nspace_group "P1"\na 5.0\n'
                   'site A1 x 0 y 0 z = 1-nothing_defined; occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "broken.inp" in str(exc.value)
    assert "Unreadable" in str(exc.value)
    assert "cannot read z" in str(exc.value)


def test_a_token_with_no_number_never_escapes_as_a_bare_valueerror(tmp_path):
    """Root CLAUDE.md: a reader raises naming the file, never its parser's
    exception. Three archive files reached ``ValueError('beq')`` this way."""
    inp = tmp_path / "s.inp"
    inp.write_text('str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
                   'site A1 x 0 y 0 z 0 occ La+3 !LSF_cubic_occ_La beq b 0.5\n')
    model = read_topas_inp(inp)          # must not raise ValueError
    assert model.phases[0].sites[0].occupancy == pytest.approx(1.0)


# ------------------------------------------------ the nameless-value bug class


@pytest.mark.parametrize("line, expected", [
    # both nameless forms are real lines from one PbPdO2 file, and both were
    # read with their integer part eaten: 0.596 and 0.931
    ("weight_percent  11.596`", 11.596),
    ("weight_percent  60.931`", 60.931),
    ("weight_percent perc_PbPdO2  17.407`", 17.407),
    ("weight_percent !ph3_wtpct  100.000`", 100.0),
    ("weight_percent @  31.610`", 31.610),
    ("weight_percent cBN_wtpct  0.000`", 0.0),   # a phase refined to absent
])
def test_a_nameless_value_keeps_its_integer_part(tmp_path, line, expected):
    """``(?:\\w+\\s+)?`` in front of a value eats digits, because ``\\w``
    matches one. That is how ``weight_percent 97.9`` came back 0.9."""
    inp = tmp_path / "s.inp"
    inp.write_text(f'str\nphase_name "P"\nspace_group "P1"\na 5.0\n{line}\n')
    assert read_topas_inp(inp).phases[0].weight_percent == pytest.approx(expected)


@pytest.mark.parametrize("line, expected", [
    ("scale @, 0.00135564312`", 0.00135564312),
    ("scale !cBN_scale  1e-15", 1e-15),
    ("scale ph2_scale  5.17632205e-006_3.88e-006_LIMIT_MIN_1e-015", 5.17632205e-06),
    ("scale ph1_scale  8.3652308e-006", 8.3652308e-06),
])
def test_scale_is_read_not_silently_defaulted(tmp_path, line, expected):
    """A scale read as absent is replaced by ``to_structure``'s 1e-4 default,
    which is a made-up number standing where the file had a measured one."""
    inp = tmp_path / "s.inp"
    inp.write_text(f'str\nphase_name "P"\nspace_group "P1"\na 5.0\n{line}\n')
    assert read_topas_inp(inp).phases[0].scale == pytest.approx(expected)


def test_arithmetic_is_not_eval(tmp_path):
    """The charset gate that preceded the ``ast`` walk admitted ``**``, so a
    malformed file could put an unbounded computation inside a reader."""
    inp = tmp_path / "s.inp"
    inp.write_text('str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
                   'site A1 x = 9**9**9; y 0 z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError):
        read_topas_inp(inp)


# ------------------------------------------------------------------- the model


def test_cell_limits_are_read_and_a_contradicting_one_is_dropped(tmp_path):
    """The file's own ``min``/``max`` are part of the author's model — a phase
    the data cannot see is a flat direction without them. But TOPAS writes the
    converged value back, so value and bound can end up on opposite sides, and
    handing pydantic both raised a validation error out of a reader.
    """
    inp = tmp_path / "s.inp"
    inp.write_text('str\nphase_name "P"\nspace_group "P1"\n'
                   'a lpa 6.2977` min 6.26 max 6.29\nc lpc 10.2458`\n'
                   'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell_limits["a"] == (6.26, 6.29)
    cell = to_structure(read_topas_inp(inp)).phases[0].cell
    assert cell.a.value == pytest.approx(6.2977)
    assert cell.a.min == pytest.approx(6.26)     # the bound that holds is kept
    assert cell.a.max == float("inf")            # the one it contradicts is not


def test_a_disabled_phase_is_not_in_the_model(tmp_path):
    inp = tmp_path / "s.inp"
    inp.write_text('#ifdef NEVER\nstr\nphase_name "ghost"\nspace_group "P1"\n'
                   'a 99.0\n#endif\n'
                   'str\nphase_name "real"\nspace_group "P1"\na 5.0\n'
                   'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    assert [p.name for p in read_topas_inp(inp).phases] == ["real"]


def test_the_emission_macro_is_reported_never_expanded(tmp_path):
    """ATTRIBUTION.md's fence: TOPAS is closed, so its macro library is not
    reproduced. Only the anode is reported; wavelengths come from rietx's own
    table."""
    inp = tmp_path / "s.inp"
    inp.write_text("CuKa5(0.0001)\nRadius(217.5)\n")
    model = read_topas_inp(inp)
    assert (model.anode, model.emission_macro) == ("CuKa", "CuKa5")
    assert model.wavelength is None
    assert model.goniometer_radius_mm == pytest.approx(217.5)


def test_to_structure_builds_a_refinable_structure(tmp_path):
    """``beq`` is TOPAS's B and ``biso`` is also B — no 8π² conversion."""
    inp = tmp_path / "s.inp"
    inp.write_text('str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
                   'Cubic_(lpa 4.15689)\nscale ph_scale 0.000225160497\n'
                   'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n'
                   'site B1 x !bx 0.19895 y 0.5 z 0.5 occ B 1. beq !bb 0.3076\n')
    (phase,) = to_structure(read_topas_inp(inp)).phases
    assert phase.space_group == "Pm-3m"
    assert phase.cell.a.value == pytest.approx(4.15689)
    assert phase.cell.b.value == pytest.approx(4.15689)   # Cubic_ fills b and c
    assert [a.species for a in phase.atoms] == ["La", "B"]
    assert phase.atoms[1].x.value == pytest.approx(0.19895)
    assert phase.atoms[0].biso.value == pytest.approx(0.4389)
    assert phase.scale.value == pytest.approx(0.000225160497)


def test_the_converged_figures_of_merit_are_recovered(tmp_path):
    """The reason the format is worth reading: it carries a *validated* answer.

    The numbers are the NIST SRM 660b LaB6 + cBN reference refinement
    (APS 11-BM run 3095), whose certified cell is 4.15689 Å.
    """
    inp = tmp_path / "s.inp"
    inp.write_text('r_wp 8.04733245 gof 1.52039055\n'
                   'str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
                   'Cubic_(lpa 4.15689)\nweight_percent ph_lab6_wtpct 17.907\n'
                   'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n'
                   'str\nphase_name "cubic_BN"\nspace_group "F-43m"\n'
                   'Cubic_(cbn 3.616466)\nweight_percent cBN_wtpct 82.093\n'
                   'site N1 x 0 y 0 z 0 occ N 1. beq !bn 0.30441\n')
    model = read_topas_inp(inp)
    assert model.r_wp == pytest.approx(8.04733245)
    assert model.gof == pytest.approx(1.52039055)
    assert [p.weight_percent for p in model.phases] == pytest.approx([17.907, 82.093])
    assert model.phases[0].cell["a"] == pytest.approx(4.15689)


def test_a_missing_file_raises_naming_it(tmp_path):
    with pytest.raises(TopasInpError, match="absent.inp"):
        read_topas_inp(tmp_path / "absent.inp")
