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

import re
from pathlib import Path

import pytest

from rietx.io.projects.topas import (
    TopasInpError,
    _cell_search_text,
    _masked,
    normalize_space_group,
    normalize_species,
    read_topas_inp,
    refined,
    resolve_ifdefs,
    strip_comments,
    symbol_table,
    to_structure,
)


def _inp(directory: Path, name: str, text: str) -> Path:
    """Write a fixture .inp. One writer, so the encoding is named once."""
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


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
    inp = _inp(tmp_path, "s.inp", f'str\nphase_name "P"\nspace_group "P1"\na 5.0\n{line}\n')
    (site,) = read_topas_inp(inp).phases[0].sites
    assert (site.x, site.y, site.z) == pytest.approx(xyz)
    assert site.occupancy == pytest.approx(occ)
    assert site.beq == pytest.approx(beq)


def test_an_equation_referencing_another_parameter_resolves(tmp_path):
    """``y = ph1_O1_x;`` is how a tetragonal oxygen says y is tied to x.

    Refusing it cost 14 archive files, the tier-1 Cr2WO6 references among them.
    """
    inp = _inp(tmp_path, "s.inp", 'str\nphase_name "Cr2WO6"\nspace_group "P42/mnm"\na 4.58\n'
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
    inp = _inp(tmp_path, "s.inp", 'prm Fe1_x = 1/4 + Fe1_dx;:  0.25733\n'
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
    inp = _inp(tmp_path, "broken.inp", 'str\nphase_name "Unreadable"\nspace_group "P1"\na 5.0\n'
                   'site A1 x 0 y 0 z = 1-nothing_defined; occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "broken.inp" in str(exc.value)
    assert "Unreadable" in str(exc.value)
    assert "cannot read z" in str(exc.value)


def test_a_token_with_no_number_never_escapes_as_a_bare_valueerror(tmp_path):
    """Root CLAUDE.md: a reader raises naming the file, never its parser's
    exception. Three archive files reached ``ValueError('beq')`` this way."""
    inp = _inp(tmp_path, "s.inp", 'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
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
    inp = _inp(tmp_path, "s.inp", f'str\nphase_name "P"\nspace_group "P1"\na 5.0\n{line}\n')
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
    inp = _inp(tmp_path, "s.inp", f'str\nphase_name "P"\nspace_group "P1"\na 5.0\n{line}\n')
    assert read_topas_inp(inp).phases[0].scale == pytest.approx(expected)


def test_arithmetic_is_not_eval(tmp_path):
    """The charset gate that preceded the ``ast`` walk admitted ``**``, so a
    malformed file could put an unbounded computation inside a reader."""
    inp = _inp(tmp_path, "s.inp", 'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
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
    inp = _inp(tmp_path, "s.inp", 'str\nphase_name "P"\nspace_group "P1"\n'
                   'a lpa 6.2977` min 6.26 max 6.29\nc lpc 10.2458`\n'
                   'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell_limits["a"] == (6.26, 6.29)
    cell = to_structure(read_topas_inp(inp)).phases[0].cell
    assert cell.a.value == pytest.approx(6.2977)
    assert cell.a.min == pytest.approx(6.26)     # the bound that holds is kept
    assert cell.a.max == float("inf")            # the one it contradicts is not


def test_a_disabled_phase_is_not_in_the_model(tmp_path):
    inp = _inp(tmp_path, "s.inp", '#ifdef NEVER\nstr\nphase_name "ghost"\nspace_group "P1"\n'
                   'a 99.0\n#endif\n'
                   'str\nphase_name "real"\nspace_group "P1"\na 5.0\n'
                   'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    assert [p.name for p in read_topas_inp(inp).phases] == ["real"]


def test_the_emission_macro_is_reported_never_expanded(tmp_path):
    """ATTRIBUTION.md's fence: TOPAS is closed, so its macro library is not
    reproduced. Only the anode is reported; wavelengths come from rietx's own
    table."""
    inp = _inp(tmp_path, "s.inp", "CuKa5(0.0001)\nRadius(217.5)\n")
    model = read_topas_inp(inp)
    assert (model.anode, model.emission_macro) == ("CuKa", "CuKa5")
    assert model.wavelength is None
    assert model.goniometer_radius_mm == pytest.approx(217.5)


def test_to_structure_builds_a_refinable_structure(tmp_path):
    """``beq`` is TOPAS's B and ``biso`` is also B — no 8π² conversion."""
    inp = _inp(tmp_path, "s.inp", 'str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
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
    inp = _inp(tmp_path, "s.inp", 'r_wp 8.04733245 gof 1.52039055\n'
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


# ------------------------------------------------- the refine flags (WP-1118)

@pytest.mark.parametrize("line, expected", [
    ("a lp 4.15689`", True),      # backtick: TOPAS wrote it back after refining
    ("a @ 4.15689", True),        # explicitly refined
    ("a @, 4.15689", True),
    ("a !lp 4.15689", False),     # explicitly held
    ("a !lp 4.15689`", False),    # `!` outranks the backtick
    ("a 4.15689", None),          # the file says nothing either way
])
def test_the_refine_flag_is_read_as_a_tri_state(tmp_path, line, expected):
    """A control file's refine flags are the payload, not its numbers.

    They are the part a person cannot reconstruct from a CIF plus a pattern,
    and the part that decides whether a cross-code comparison means anything.
    ``None`` is a third state on purpose: a file that says nothing is not a
    file that said "held", and collapsing the two is what would let a reader
    hand back a confident wrong protocol.
    """
    inp = _inp(tmp_path, "s.inp", f'str\nphase_name "P"\nspace_group "P1"\n{line}\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    assert read_topas_inp(inp).phases[0].vary.get("a") == expected


def test_a_site_carries_its_own_flags():
    """One site, mixed: a refined coordinate, a held B, an untouched occupancy."""
    line = "site B1 x @, 0.19776` y 0.5 z 0.5 occ B 1. beq !bb 0.3076"
    assert refined("x", line) is True
    assert refined("beq", line) is False
    assert refined("y", line) is None


def test_the_certified_standards_protocol_survives_the_round_trip(tmp_path):
    """The NIST SRM 660b protocol: the certified cell is **held**, and that is
    the fact a transcription loses.

    This is the whole argument for reading the flags. Both phases' scales were
    refined and cBN's cell was refined; LaB6's was not, because 4.15689 Å is
    the certificate's number and holding it is what decorrelates zero and
    displacement from the cell. A reader that returned only the values would
    hand back a model that looks identical and refines to a different answer.
    """
    inp = _inp(tmp_path, "srm660b.inp",
               'r_wp 8.04733245 gof 1.52039055\n'
               'str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
               'scale ph1_scale  0.000225160497`\na 4.15689\n'
               'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n'
               'site B1  x @, 0.19895` y 0.5 z 0.5 occ B 1. beq @, 0.3076`\n'
               'str\nphase_name "cubic_BN"\nspace_group "F-43m"\n'
               'scale ph2_scale  0.00321777397`\na lp_bn  3.616466`\n'
               'site N1 x 0 y 0 z 0 occ N 1. beq @, 0.30441`\n')
    lab6, cbn = to_structure(read_topas_inp(inp)).phases

    assert lab6.cell.a.value == pytest.approx(4.15689)
    assert lab6.cell.a.vary is False          # certified, held
    assert cbn.cell.a.vary is True            # the internal standard, refined
    assert lab6.scale.vary is True and cbn.scale.vary is True
    assert lab6.atoms[0].biso.vary is False   # `!bla`
    assert lab6.atoms[1].x.vary is True       # `@, 0.19895``


# ------------------------------------------- report or refuse, never drop

def test_a_magnetic_phase_is_refused_by_name(tmp_path):
    """rietx has no magnetic structure model, so returning the nuclear half
    silently would hand back a model that looks complete.

    Found by compiling every structure the reader returns: `mag_space_group
    62.448` matched an unanchored `space_group` and arrived as the *symbol*
    "62.448", which gemmi then refused a long way from the cause.
    """
    inp = _inp(tmp_path, "mag.inp",
               'str\nphase_name "LaMnO3_mag"\nmag_space_group 62.448\na 5.7\n'
               'site Mn1 x 0 y 0 z 0 occ Mn+3 1 beq b 0.5\n')
    with pytest.raises(TopasInpError, match="magnetic space group"):
        read_topas_inp(inp)


def test_an_inp_with_no_structural_phase_refuses_naming_the_file(tmp_path):
    """A Pawley or indexing-only `.inp` legitimately has no cell to build from.

    It must still not reach the caller as a pydantic `ValidationError`: a
    reader raises naming the file, and pydantic's report names a field.
    """
    inp = _inp(tmp_path, "pawley.inp", 'r_wp 3.2\nxdd "sample.xy"\n')
    model = read_topas_inp(inp)
    assert model.phases == []
    with pytest.raises(TopasInpError, match="pawley.inp"):
        to_structure(model)


def test_a_phase_whose_sites_were_all_disabled_refuses_naming_the_phase(tmp_path):
    inp = _inp(tmp_path, "gated.inp",
               'str\nphase_name "p21n"\nspace_group "P21/n"\na 5.0\n'
               '#ifdef NEVER\nsite A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n#endif\n')
    with pytest.raises(TopasInpError) as exc:
        to_structure(read_topas_inp(inp))
    assert "gated.inp" in str(exc.value) and "p21n" in str(exc.value)


# ------------------------------------------- one grammar, on the cell too

#: The cell had its own regex once, and it admitted three of these six. The
#: numbers are `parametric_04.inp`'s monoclinic `p21n` lattice parameter, which
#: that file writes as an equation with TOPAS's evaluated tail — measured: the
#: three equation spellings left `a` out of `phase.cell`, so `to_structure`
#: dropped the phase, and across the archive that lost **320 phases in 15
#: files**, 107 patterns of `parametric_04.inp` among them.
CELL_SPELLINGS = [
    ("a 7.301139", 7.301139, None),
    ("a lpa 7.301139", 7.301139, None),
    ("a @ 7.301139", 7.301139, True),
    ("a !lpa 7.301139`", 7.301139, False),
    ("a =mlpa;:7.301139`", 7.301139, True),
    ("a = 7.3;", 7.3, None),
    ("a = mlpa;", 7.30114, None),
]


@pytest.mark.parametrize("line, expected, vary", CELL_SPELLINGS)
def test_a_cell_edge_reads_in_every_spelling_the_one_grammar_admits(
        tmp_path, line, expected, vary):
    """The cell is read through the same grammar as every other scalar.

    A second regex for the cell is the failure this PR is about one rank down:
    it disagreed with `_field` on the `= expr;: value` tail, and a phase whose
    `a` is missing is silently absent from the `Structure` while its
    `weight_percent` still reports.
    """
    inp = _inp(tmp_path, "cell.inp",
               f'prm mlpa 7.30114\nstr\nphase_name "p21n"\nspace_group "P121/n1"\n'
               f'{line}\nb 7.5\nc 7.7\nbe 99.1\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell["a"] == pytest.approx(expected)
    assert phase.vary.get("a") == vary
    (built,) = to_structure(read_topas_inp(inp)).phases
    assert built.cell.a.value == pytest.approx(expected)


def test_a_cell_min_max_still_reads_when_the_value_is_named(tmp_path):
    """Routing the cell through the one grammar must not lose the window that
    keeps a phase the data cannot see from running away."""
    inp = _inp(tmp_path, "cell.inp",
               'str\nphase_name "P"\nspace_group "P1"\n'
               'a lp_bn 3.616466` min 3.61 max 3.63\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell_limits["a"] == (3.61, 3.63)
    assert phase.vary["a"] is True


# --------------------------------------------------------- the lattice macros

#: Every spelling of a lattice macro that a real archive file contains, with
#: the file it came from. A macro is a *specification fact* (io/CLAUDE.md's
#: rule 2), so the argument order is read off these lines and never guessed.
LATTICE_MACROS = [
    # Cubic_ with a named argument — the one form that already worked.
    ("Cubic_(lpa 4.15689)", (4.15689,) * 3 + (90.0,) * 3, None),
    # nameless: `\w*` in front of the value ate the integer part and gave
    # a = 0.15689, the same class as `weight_percent 11.596` → 0.596.
    ("Cubic(10)", (10.0,) * 3 + (90.0,) * 3, None),              # rigidb.inp:37
    ("Cubic_( 4.15689)", (4.15689,) * 3 + (90.0,) * 3, None),
    # flag with no name: the whole cell came back empty, so the phase vanished.
    ("Cubic(@  4.15692`)", (4.15692,) * 3 + (90.0,) * 3, True),  # LaB6_Riet_TCHZ_01.inp:54
    ("Cubic_(!lpa 4.15689)", (4.15689,) * 3 + (90.0,) * 3, False),
    # TOPAS's own evaluated tail, inside the macro's parenthesis.
    ("Cubic(=a1;:  5.43416_0.00012)",                            # Si_in_cap_NOMAD_jue.inp:139
     (5.43416,) * 3 + (90.0,) * 3, None),
    ("Cubic(aLP  11.210591`)",                                   # i15-xpdf_…_pdfonly.inp:69
     (11.210591,) * 3 + (90.0,) * 3, True),
    # a = b, c, and γ = 90 — TOPAS writes the two independent lengths in order.
    ("Tetragonal(@  4.594290`, @  2.958587`)",                   # d5_05005_pawley_01.inp:38
     (4.594290, 4.594290, 2.958587, 90.0, 90.0, 90.0), True),
    # a = b, c, and γ = **120**.
    ("Hexagonal(@  3.613074`, @  12.037126`)",                   # BL104_B_1.inp:87
     (3.613074, 3.613074, 12.037126, 90.0, 90.0, 120.0), True),
    ("Trigonal(  12.695126,   37.972985)",                       # AT027-23_…:90
     (12.695126, 12.695126, 37.972985, 90.0, 90.0, 120.0), None),
    ("Trigonal(@  12.68790`_0.00010,  @  37.94996`_0.00056)",    # AT027-23_…_fin.inp:51
     (12.68790, 12.68790, 37.94996, 90.0, 90.0, 120.0), True),
]


@pytest.mark.parametrize("macro, cell, vary", LATTICE_MACROS)
def test_a_lattice_macro_fills_the_cell_it_states(tmp_path, macro, cell, vary):
    """A lattice macro is as much a statement of the cell as an ``a`` line.

    Before this, only ``Cubic_(<name> <value>)`` was read: every other macro
    left ``phase.cell`` empty and ``to_structure`` then *dropped the phase*
    while ``weight_percent`` went on reporting for it, so a QPA table looked
    complete with a phase missing from the `Structure`.
    """
    inp = _inp(tmp_path, "macro.inp",
               f'str\nphase_name "P"\nspace_group "P1"\n{macro}\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert tuple(phase.cell[k] for k in ("a", "b", "c", "al", "be", "ga")) == \
        pytest.approx(cell)
    assert phase.vary.get("a") == vary
    assert len(to_structure(read_topas_inp(inp)).phases) == 1


@pytest.mark.parametrize("macro", [
    "Rhombohedral(@ 5.4, @ 55.3)",
    "Orthorhombic(@ 5.4, @ 6.1, @ 7.2)",
    "Monoclinic(@ 5.4, @ 6.1, @ 7.2, @ 99.1)",
    "Triclinic(@ 5.4, @ 6.1, @ 7.2, @ 88, @ 99, @ 101)",
])
def test_a_lattice_macro_with_no_evidenced_argument_order_is_refused_by_name(
        tmp_path, macro):
    """Guessing a macro's argument order is worse than declining to read it.

    Each of these appears in the archive **only** inside a ``'`` comment, so no
    file states which argument is which — ``Rhombohedral(@ #, @ #)`` in
    `D20.inp`'s template is a length and an angle in an order no file here
    fixes. A wrong order is a wrong cell with nothing raised, which is the one
    outcome this reader exists to avoid, so the macro is refused by name.
    """
    inp = _inp(tmp_path, "unevidenced.inp",
               f'str\nphase_name "P"\nspace_group "P1"\n{macro}\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "unevidenced.inp" in str(exc.value)
    assert macro.split("(")[0] in str(exc.value)


def test_a_lattice_macro_beside_an_explicit_cell_is_not_needed(tmp_path):
    """An `hkl_Is` Pawley block's macro must not overwrite the `str` phase's own
    cell: the archive's `Hexagonal(` occurrences all sit in such a block, in the
    same chunk as a `str` phase that states a, b, c itself."""
    inp = _inp(tmp_path, "both.inp",
               'str\nphase_name "LiAlCl4"\nspace_group "P121/c1"\n'
               'a 7.018696\nb 6.520921\nc 13.019527\nal 90\nbe 93.32175\nga 90\n'
               'site Al1 x 0.70588 y 0.32198 z 0.89924 occ Al+3 1.\n'
               'hkl_Is\nphase_name "hexagonal from Dicvol"\n'
               'Hexagonal(@  3.613074`, @  12.037126`)\nspace_group "P-6m2"\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell["a"] == pytest.approx(7.018696)
    assert phase.cell["c"] == pytest.approx(13.019527)


def test_a_str_block_that_produced_no_cell_refuses_rather_than_dropping(tmp_path):
    """Report or refuse, never drop — and `weight_percent` is why.

    A phase whose cell could not be read used to be skipped by `to_structure`
    with nothing said, while `model.phases` still carried its weight fraction.
    The QPA numbers then look complete with a phase missing from the
    `Structure`, which is worse than the dropped-*site* case this reader
    already makes a hard error.
    """
    inp = _inp(tmp_path, "nocell.inp",
               'str\nphase_name "real"\nspace_group "P1"\na 5.0\n'
               'weight_percent ph1_wtpct 40.0`\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'str\nphase_name "cell_less"\nspace_group "P4/mmm"\n'
               'weight_percent ph2_wtpct 60.0`\n'
               'site Sr1 x 0 y 0 z 0 occ Sr+2 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert [p.weight_percent for p in model.phases] == pytest.approx([40.0, 60.0])
    with pytest.raises(TopasInpError) as exc:
        to_structure(model)
    assert "nocell.inp" in str(exc.value) and "cell_less" in str(exc.value)


# ------------------------------------------------------------ the encoding

#: One realistic file, written in five encodings. The three a byte-order mark
#: names are read; the two it does not are refused.
_ENCODED = ('r_wp 8.04733245 gof 1.52039055\n'
            'xdd "srm660b.xy"\nCuKa5(0.0001)\n'
            'str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
            'Cubic_(lpa 4.15689)\nscale ph1_scale 0.000225160497`\n'
            'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n')


@pytest.mark.parametrize("codec", ["utf-8", "utf-8-sig", "utf-16"])
def test_a_byte_order_mark_is_decoded_not_read_as_utf8(tmp_path, codec):
    """`read_text(encoding="utf-8")` on a UTF-16 file gives zero phases, and
    `to_structure` then says "a Pawley or indexing-only .inp is legal and has
    none" — a confident wrong diagnosis of a *decode* failure.

    `io.formats.base.decode` is the seam that already answers this, shared with
    `head()` rather than duplicated. All 606 archive files are BOM-free, so
    this is latent rather than measured.
    """
    inp = tmp_path / "enc.inp"
    inp.write_bytes(_ENCODED.encode(codec))
    model = read_topas_inp(inp)
    assert [p.name for p in model.phases] == ["LaB6"]
    assert model.r_wp == pytest.approx(8.04733245)
    assert model.data_files == ["srm660b.xy"]
    assert to_structure(model).phases[0].cell.a.value == pytest.approx(4.15689)


def test_a_bom_immediately_before_the_first_str_still_splits(tmp_path):
    """U+FEFF is category Cf, not `\\s`, so `^\\s*str\\s*$` misses a `str` the
    mark is glued to — the one place a UTF-8 BOM actually breaks this reader."""
    inp = tmp_path / "bomfirst.inp"
    inp.write_bytes(('str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
                     'Cubic_(lpa 4.15689)\n'
                     'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n')
                    .encode("utf-8-sig"))
    assert [p.name for p in read_topas_inp(inp).phases] == ["LaB6"]


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"])
def test_a_utf16_file_with_no_mark_is_refused_naming_the_file(tmp_path, codec):
    """`io/CLAUDE.md`'s `xy` row settles this: a NUL is refused by name *unless*
    behind a BOM, because ASCII-range UTF-16LE is valid UTF-8 with interleaved
    NULs and no byte-order mark says which of LE and BE it is. Guessing is a
    repair this reader cannot say it made, so it refuses instead."""
    inp = tmp_path / f"{codec}.inp"
    inp.write_bytes(_ENCODED.encode(codec))
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert f"{codec}.inp" in str(exc.value)


# ---------------------------------------- the flag grammar, off the one match

def test_the_coordinate_macros_own_flag_is_read(tmp_path):
    """`A1(@xO3, …)` carries its flag *inside* the parenthesis.

    The value grammar was unified and the flag grammar was not, so `refined`'s
    separate regex never looked inside the macro and returned None — which
    `rx.Parameter` then defaults to `vary=False`, i.e. **held**. The tri-state
    this reader argues for collapsed to "held" at the one boundary where the
    file was explicit.
    """
    line = ("site O3 A1(@xO3, 0.00143, 0.00143) A2(!yO3, 0.03550, 0.001) "
            "A3(@zO3, 0.21526, 0.001) occ O 1.0 beq !bval 0.5")
    assert refined("x", line) is True
    assert refined("y", line) is False
    assert refined("z", line) is True
    inp = _inp(tmp_path, "macroflags.inp",
               f'str\nphase_name "P"\nspace_group "P1"\na 5.0\n{line}\n')
    (atom,) = to_structure(read_topas_inp(inp)).phases[0].atoms
    assert (atom.x.vary, atom.y.vary, atom.z.vary) == (True, False, True)


def test_a_write_back_backtick_after_an_evaluated_tail_is_read_as_refined(tmp_path):
    """`scale =scph1*scb1;:  0.0844868572\\`` — the backtick sits after the `;:`
    tail, where the flag regex could not reach it. The value was read
    correctly and the flag was lost, which is the same tri-state error one
    field over."""
    inp = _inp(tmp_path, "tail.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'scale =scph1*scb1;:  0.0844868572`\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.scale == pytest.approx(0.0844868572)
    assert phase.vary["scale"] is True
    assert to_structure(read_topas_inp(inp)).phases[0].scale.vary is True


# ------------------------------------------------------ occ carries a species

@pytest.mark.parametrize("occ, expected", [
    ("occ Ca+2 @ 0.6", True),        # charged and flagged
    ("occ Ca @ 0.6", True),          # uncharged — the one that worked, by luck
    ("occ Ca+2 !n 0.6", False),
    ("occ Ca !n 0.6", False),        # uncharged but *named*: also lost
    ("occ Si !ph1_Si 0.8000", False),        # SiGe_LiCl-KCl_grey_PVII.inp
    ("occ La+3 !LSF_occ_La 0.6 vcocc", False),   # lasf_longruns_riet_07.inp
    ("occ Na+1 1", None),            # the file says nothing
])
def test_an_occupancys_flag_is_read_whatever_the_species(occ, expected):
    """The grammar has **one** name slot and on an `occ` line the species
    consumes it, so `occ Ca @ 0.6` worked by accident and everything else
    returned None. Widening `_NAME` to admit `+`/`-` is not the fix — it is
    load-bearing everywhere else — so `occ` reads past its species first.

    Incidence: 38 real site lines. `occ Si !ph1_Si 0.8000` is a Si/Ge solid
    solution deliberately **held** at 0.8/0.2, arriving as held-by-default
    rather than held-by-file — and a default cannot be told from a decision.
    """
    assert refined("occ", f"site A1 x 0 y 0 z 0 {occ} beq b 0.5") is expected


def test_a_held_occupancy_reaches_the_structure_as_held(tmp_path):
    inp = _inp(tmp_path, "sige.inp",
               'str\nphase_name "SiGe"\nspace_group "Fd-3m:2"\na 5.45\n'
               'site Si1_Si x 0. y 0. z 0. occ Si !ph1_Si 0.8000 beq b 0.5\n'
               'site Si1_Ge x 0. y 0. z 0. occ Ge @ph1_Ge 0.2000 beq b 0.5\n')
    si, ge = to_structure(read_topas_inp(inp)).phases[0].atoms
    assert (si.occ.value, si.occ.vary) == (pytest.approx(0.8), False)
    assert (ge.occ.value, ge.occ.vary) == (pytest.approx(0.2), True)


# -------------------------------------------------- a stated zero is a value

def test_a_stated_zero_scale_is_not_replaced_by_the_default(tmp_path):
    """`ph.scale or 1e-4` substitutes a made-up default for a measured zero.

    A phase refined to absent is a state this repo already recognises — the
    `weight_percent cBN_wtpct 0.000` case above — and 20 real phases across 9
    files state `scale 0`. `or` also destroys the difference between "the file
    stated zero" and "the file said nothing", which is the F3 error again.
    """
    inp = _inp(tmp_path, "off.inp",
               'str\nphase_name "cBN_refined_to_absent"\nspace_group "F-43m"\n'
               'a 3.616466\nscale !ph_off 0\n'
               'site N1 x 0 y 0 z 0 occ N 1. beq !bn 0.30441\n')
    model = read_topas_inp(inp)
    assert model.phases[0].scale == 0.0
    scale = to_structure(model).phases[0].scale
    assert scale.value == 0.0
    assert scale.vary is False


def test_a_phase_stating_no_scale_still_gets_the_seed(tmp_path):
    """The other half of the tri-state: absent is still the 1e-4 seed."""
    inp = _inp(tmp_path, "noscale.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert model.phases[0].scale is None
    assert to_structure(model).phases[0].scale.value == pytest.approx(1e-4)


# ------------------------------------------------- a keyword is not a symbol

#: A realistic file, whose only *declarations* are the two `prm`s and the named
#: values. Measured on the old sweep: 21 symbols bound from these 30 lines,
#: including `beq`, `bkg`, `gof`, `min`, `max`, `r_wp`, `x`, `y`, `z` and the
#: element symbols `B`, `La`, `N` — each bound to an occupancy of 1.0, so a
#: `prm B` would have silently got boron's occupancy.
_REALISTIC = '''r_wp 8.04733245 gof 1.52039055
xdd "srm660b.xy"
    CuKa5(0.0001)
    Radius(217.5)
    bkg @ 128.4 -33.9 12.6 -4.1 1.9
prm scph1 1.0
prm scb1 0.0844868572
str
    phase_name "LaB6"
    space_group "Pm-3m"
    Cubic_(lpa 4.15689)
    scale ph1_scale 0.000225160497`
    weight_percent ph1_wtpct 17.907`
    CS_L(csl1, 210.4)
    site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389
    site B1  x @, 0.19895` y 0.5 z 0.5 occ B 1. beq @, 0.3076`
str
    phase_name "cubic_BN"
    space_group "F-43m"
    a lp_bn 3.616466` min 3.61 max 3.63
    scale ph2_scale 0.00321777397`
    weight_percent cBN_wtpct 82.093`
    site N1 x 0 y 0 z 0 occ N 1. beq @, 0.30441`
'''


@pytest.mark.parametrize("keyword", [
    "a", "b", "c", "x", "y", "z", "beq", "occ", "scale", "weight_percent",
    "bkg", "min", "max", "r_wp", "gof", "site", "prm", "Radius",
])
def test_a_keyword_is_never_bound_as_a_symbol(keyword):
    """The sweep took any `<name> <number>` pair, so every keyword with a bare
    value became a named parameter. Nothing raises when one is then
    substituted into an equation: `_arith` returns a plausible number."""
    assert keyword not in symbol_table(strip_comments(_REALISTIC))


@pytest.mark.parametrize("species", ["La", "B", "N"])
def test_a_species_is_never_bound_as_a_symbol(species):
    """`occ La 1.` puts the species where the grammar's name slot is, so the
    old sweep bound `La` to 1.0 — and a `prm La` would then have lost to it."""
    assert species not in symbol_table(strip_comments(_REALISTIC))


@pytest.mark.parametrize("declared", [
    "scph1", "scb1", "lpa", "ph1_scale", "ph1_wtpct", "bla", "lp_bn",
    "ph2_scale", "cBN_wtpct", "csl1",
])
def test_every_real_declaration_is_still_bound(declared):
    """The narrowing must not cost a name an equation could reach: a `prm`, a
    `local`, the name slot of a keyword's value, and a macro's named argument
    are all declarations."""
    assert declared in symbol_table(strip_comments(_REALISTIC))


def test_a_prm_outranks_an_earlier_sites_coordinate(tmp_path):
    """`setdefault` means the first binding wins, so a real `prm x 0.9999` lost
    to whatever earlier line happened to write `x <number>` — silently, because
    `_resolve` substitutes and `_arith` returns a number."""
    inp = _inp(tmp_path, "collide.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0.1111 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'prm x 0.9999\n'
               'site A2 x = x; y 0 z 0 occ Na+1 1 beq b 0.5\n')
    a1, a2 = read_topas_inp(inp).phases[0].sites
    assert a1.x == pytest.approx(0.1111)
    assert a2.x == pytest.approx(0.9999)


def test_an_equation_reaching_a_keyword_refuses_rather_than_inventing(tmp_path):
    """`y = x;` names no parameter this file declares — `x` is a keyword, not a
    symbol — and the old sweep resolved it to the *first* site's x. Refusing is
    the only honest answer: inventing a coordinate is the one outcome worse
    than declining to read the file."""
    inp = _inp(tmp_path, "keyword_ref.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0.3333 y 0.6667 z 0 occ Na+1 1 beq b 0.5\n'
               'site A2 x 0.1 y = x; z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "keyword_ref.inp" in str(exc.value) and "cannot read y" in str(exc.value)


# ------------------------------------------------ a quote is not a comment

@pytest.mark.parametrize("line", [
    r'''xdd "C:\data\o'brien.xy"''',
    r'''phase_name "d'Alembert phase"''',
])
def test_an_apostrophe_inside_a_quoted_string_is_not_a_comment(line):
    """Cutting at the first `'` truncated the string it sat in: a data file
    became `C:\\data\\o` and a phase became `d`. A silently mislabelled phase
    is a wrong answer with nothing raised; incidence in the archive is 0, so
    this is latent."""
    assert strip_comments(line) == line


def test_a_truncated_string_does_not_reach_the_model(tmp_path):
    inp = _inp(tmp_path, "quoted.inp",
               'r_wp 3.2\nxdd "C:\\data\\o\'brien.xy"\n'
               'str\nphase_name "d\'Alembert"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert model.data_files == ["C:\\data\\o'brien.xy"]
    assert [p.name for p in model.phases] == ["d'Alembert"]


def test_a_real_trailing_comment_is_still_cut(tmp_path):
    """The other side of the same test: a `'` outside a string still opens a
    comment, which is what rule 1 exists for."""
    assert strip_comments('xdd "sample.xy" \' a real comment') == 'xdd "sample.xy" '
    assert strip_comments("str ' don't") == "str "


# ----------------------------------------------- the geometry is a declaration

@pytest.mark.parametrize("line, geometry", [
    # what actually declares a capillary, quoted from the archive
    ("capillary_u_cm_inv @, 36.0187505", "debye_scherrer"),
    ("capillary_diameter_mm 0.5", "debye_scherrer"),
    ("capillary_parallel_beam", "debye_scherrer"),
    ("Cylindrical_2Th_Correction(@, 0.91181`)", "debye_scherrer"),
    ("Cylindrical_I_Correction(2.64)", "debye_scherrer"),
    # and what does not: a name, a path and a parameter are not declarations
    ('phase_name "Debye_test_material"', "bragg_brentano"),
    ('xdd "C:/data/debye_run3.xy"', "bragg_brentano"),
    ("prm capillary_diam 0.7", "bragg_brentano"),
    ('phase_name "MgO_cylindrical_ref"', "bragg_brentano"),
])
def test_the_geometry_is_decided_by_a_declaration_not_by_a_name(
        tmp_path, line, geometry):
    """The sniff matched `Cylindrical_|capillary|Debye` case-insensitively over
    the whole file, so a phase called `Debye_test_material` flipped a file
    carrying `Radius(217.5)` and `LP_Factor(26.4)` — unambiguously
    Bragg-Brentano — to `debye_scherrer`.

    A geometry is declared by a *statement*, so the token has to open a line.
    Incidence in the archive is 0, so this is latent; what the archive does
    show is that `Debye` appears in **no** file, while the tokens above are how
    the 26 capillary files actually say it.
    """
    inp = _inp(tmp_path, "geom.inp",
               f'r_wp 4.1\nRadius(217.5)\nCuKa5(0.0001)\nLP_Factor(26.4)\n{line}\n'
               'str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
               'Cubic_(lpa 4.15689)\n'
               'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n')
    assert read_topas_inp(inp).geometry == geometry


# ------------------------------ a stated key that cannot be read refuses

@pytest.mark.parametrize("key, line", [
    ("a", "a = a*1.0;"),
    ("b", "b =Get(a);"),          # 7 real phases in 4 archive files
    ("c", "c = a*1.633;"),
    ("al", "al = nothing_defined;"),
    ("be", "be = 90+nothing_defined;"),
    ("ga", "ga =Get(al);"),
])
def test_a_stated_cell_key_that_cannot_be_read_refuses_naming_it(
        tmp_path, key, line):
    """Whether the cell is right must not turn on whether the author *named*
    the edge, which no caller can see.

    Measured: `a 3.000` + `c = a*1.633;` + `ga 120` built c = 3.0 for a stated
    4.899 — 63 % low — because `a` is a keyword and not a symbol, so the
    equation is unresolvable, the key was `continue`d and `to_structure`
    substituted `c["a"]`. The same substitution on an angle makes an
    unresolvable `be = …;` read 90.0, so a monoclinic phase arrives
    orthorhombic with nothing raised. `a` already refused (in `to_structure`,
    for want of a cell); the other five now refuse symmetrically, at read,
    where the line can be named.
    """
    base = "" if key == "a" else "a 3.0\n"
    inp = _inp(tmp_path, "silent.inp",
               f'str\nphase_name "P"\nspace_group "P1"\n{base}{line}\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "silent.inp" in str(exc.value)
    assert f"cannot read {key}" in str(exc.value)
    assert line.strip() in str(exc.value)


def test_naming_the_edge_is_what_made_the_difference(tmp_path):
    """The measured pair, side by side: the same cell, written twice.

    `c = lpa*1.633;` resolves because `a lpa 3.000` *declares* `lpa`, so this
    half always worked. Nothing about the file says which spelling the author
    would use, which is why the other half may not answer.
    """
    inp = _inp(tmp_path, "named.inp",
               'str\nphase_name "P"\nspace_group "P63/mmc"\n'
               'a lpa 3.000\nc = lpa*1.633;\nga 120\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell["c"] == pytest.approx(4.899)
    assert to_structure(read_topas_inp(inp)).phases[0].cell.c.value == \
        pytest.approx(4.899)


def test_a_cell_key_the_phase_never_states_still_keeps_its_default(tmp_path):
    """The other half of the rule, and it stays unchanged: an **absent** line is
    a different fact from an unreadable one. A cubic phase writes `a` alone."""
    inp = _inp(tmp_path, "cubic.inp",
               'str\nphase_name "W"\nspace_group "Im-3m"\na 3.158949\n'
               'site W1 x 0 y 0 z 0 occ W 1. beq 0.3\n')
    phase = read_topas_inp(inp).phases[0]
    assert list(phase.cell) == ["a"]
    cell = to_structure(read_topas_inp(inp)).phases[0].cell
    assert (cell.b.value, cell.c.value) == pytest.approx((3.158949, 3.158949))
    assert (cell.alpha.value, cell.gamma.value) == pytest.approx((90.0, 90.0))


# ---------------------------- a str chunk ends at the next block opener

def test_a_trailing_pawley_block_lends_the_phase_above_nothing(tmp_path):
    """`re.split(r"^\\s*str\\s*$")` ends a chunk only at the next `str`, so a
    trailing `hkl_Is` belonged to the phase above it and `_read`/`_field` swept
    the whole thing — three of the neighbour's numbers, silently.

    Measured on the real file: `W02_DR_11bmb_3858_pawley_Nb2O5.inp` gave
    tungsten b = 3.814 and c = 19.299 off the Nb2O5 block's
    `load hkl_m_d_th2 I` table, where 3.814 is a **d-spacing** column read as a
    cell edge. It is F1's failure mode moved from the cell regex to the block
    splitter, and it reaches the scale and the weight percent too.
    """
    inp = _inp(tmp_path, "bleed.inp",
               'str\n'
               '  phase_name "structural"\n  space_group "Fm-3m"\n  a 4.0\n'
               '  scale @ 0.001\n'
               '  site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'hkl_Is\n'
               '  a 3.1\n  c 19.3\n  scale @ 0.00987\n  weight_percent 61.4\n')
    (phase,) = read_topas_inp(inp).phases
    assert phase.cell == {"a": pytest.approx(4.0)}
    assert phase.scale == pytest.approx(0.001)
    assert phase.weight_percent is None
    cell = to_structure(read_topas_inp(inp)).phases[0].cell
    assert (cell.a.value, cell.c.value) == pytest.approx((4.0, 4.0))


@pytest.mark.parametrize("opener", [
    "hkl_Is",           # 139 line-initial occurrences in the archive
    "xo_Is",            # 277
    "xdd \"next.xye\"",  # 609 — a new dataset ends the phase too
    "fit_obj",          # 2
    "str",              # the one it already ended at
])
def test_every_block_opener_ends_the_phase_above_it(tmp_path, opener):
    """A `.inp` has no closing brace, so a phase's text runs to the next block
    opener — of *any* kind, not to the next `str`. The counts are the archive's,
    line-initial and after comment stripping. `macro` is deliberately **not**
    here: it is excised as a definition, not treated as an opener (see
    `test_a_macro_definition_inside_a_str_block_does_not_truncate_the_phase`)."""
    inp = _inp(tmp_path, "openers.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               f'{opener}\nweight_percent 61.4\nc 19.3\n')
    (phase,) = read_topas_inp(inp).phases
    assert phase.weight_percent is None
    assert "c" not in phase.cell


def test_a_phase_after_a_pawley_block_is_still_read(tmp_path):
    """The splitter must not lose a `str` that follows another block."""
    inp = _inp(tmp_path, "after.inp",
               'str\nphase_name "first"\nspace_group "P1"\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'hkl_Is\nphase_name "pawley"\na 3.1\n'
               'str\nphase_name "second"\nspace_group "P1"\na 5.0\n'
               'site B1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert [p.name for p in model.phases] == ["first", "second"]
    assert [p.cell["a"] for p in model.phases] == pytest.approx([4.0, 5.0])


def test_a_str_block_with_no_phase_name_is_recorded_not_passed_over(tmp_path):
    """Measured, on `simulate_Nb_Cu.inp`: a `str` block stating a cell and two
    sites and **no** `phase_name` used to arrive named "CaO" with scale 1.0 —
    both read off the `hkl_Is` block below it. That is finding 2 on a real file.

    Ending the chunk at the `hkl_Is` removes the wrong name, and then the
    reader must not go quiet about the block: answering "a Pawley or
    indexing-only .inp is legal and has none" about a file carrying a cell and
    two sites is the same confident wrong diagnosis a UTF-16 decode used to
    get. The block cannot be *named* — taking the neighbour's name is the bug —
    so it is recorded and the refusal quotes it.
    """
    inp = _inp(tmp_path, "unnamed.inp",
               'str\n  a 4.8152\n  space_group "Fm-3m"\n'
               '  site Ca1 x 0 y 0 z 0 occ Ca+2 1. beq 0.019\n'
               '  site O1 x 0.5 y 0.5 z 0.5 occ O-2 1. beq 0.016\n'
               '#ifdef phase_1_\nhkl_Is\n  phase_name "CaO"\n  scale nb_scale 1`\n'
               '  a 4.8152\n#endif\n')
    model = read_topas_inp(inp)
    assert model.phases == []
    (sb,) = model.skipped_blocks
    # It records what it lacked *and* what it carried (finding 4): the cell it
    # states is exactly what makes it a phase in all but its name.
    assert (sb.lacked, sb.n_sites, sb.cell) == ("phase_name", 2, {"a": 4.8152})
    assert str(sb) == ("a `str` block stating 2 site lines but no phase_name, "
                       "carrying a cell (a)")
    with pytest.raises(TopasInpError) as exc:
        to_structure(model)
    assert "2 site lines but no phase_name" in str(exc.value)
    assert "indexing-only" not in str(exc.value)


# ------------------------------------------- STR(...) is refused by name

def test_a_phase_opening_with_the_STR_macro_is_refused_by_name(tmp_path):
    """`STR(R-3)` expands to a whole `str` block from a macro library this
    reader does not have and may not reproduce.

    Such a file returned **zero** phases and `to_structure` then answered "A
    Pawley or indexing-only .inp is legal and has none" — a confident wrong
    diagnosis about a file that plainly contains `STR(`. Seven archive files
    are affected (`rigidb.inp`, `split_fum.inp`, `SPODI.inp`, `D20.inp` and
    three `AT027-23_*` variants), all of them returning no phase at all.
    Expanding the macro can wait; answering wrongly about it cannot.
    """
    inp = _inp(tmp_path, "strmacro.inp",
               'r_wp 3.2\nxdd "sample.xye"\n'
               'STR(R-3)\nphase_name "corundum"\n'
               'STR(Fm-3m)\nphase_name "silicon"\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "strmacro.inp" in str(exc.value)
    assert "STR(R-3)" in str(exc.value) and "2 phases" in str(exc.value)


# --------------------------------------- beq: refused, never moved or leaked

def test_a_negative_beq_is_refused_naming_the_site_never_clamped(tmp_path):
    """`max(s.beq, 0.0)` moved a stated −0.42 to 0.0 with nothing said.

    A slightly negative refined B is an ordinary outcome of a converged
    refinement — the column absorbs absorption and normalisation error, and 75
    sites across 11 archive files state one — so this is the reader repairing
    where it cannot say that it did, the rule its own tri-state argument rests
    on. Moving it changes every high-Q intensity, so it is a contradiction
    rather than a deviation a reader may repair, and the sibling `.pcr` reader
    refuses the same value: one story whichever code wrote the file. The number
    stays readable on `model.phases`.
    """
    inp = _inp(tmp_path, "negb.inp",
               'str\nphase_name "Co10Ge3O16"\nspace_group "P1"\na 8.3\n'
               'site GE1 x 0 y 0 z 0 occ Ge+4 1 beq bge -0.42`\n')
    model = read_topas_inp(inp)
    assert model.phases[0].sites[0].beq == pytest.approx(-0.42)
    with pytest.raises(TopasInpError) as exc:
        to_structure(model)
    assert "negb.inp" in str(exc.value) and "GE1" in str(exc.value)
    assert "-0.42" in str(exc.value)


def test_a_schema_refusal_from_the_cell_or_the_atoms_is_still_converted(tmp_path):
    """`rx.Cell(...)` and the `atoms` comprehension sat **outside** the try that
    exists to convert a schema report into a reader's refusal — one line above
    it — so only the `rx.Phase(...)` call was covered and `beq bA 26.0` reached
    the caller as a raw `pydantic_core.ValidationError`.

    The truncation pin cannot catch this class: a ragged cut rarely leaves a
    well-formed line carrying an out-of-range number, so it is tested directly.
    26 Å² is outside the [0, 25] window `Atom.biso` itself declares, which is
    where the bound comes from — the reader quotes it rather than inventing it.
    """
    inp = _inp(tmp_path, "outofrange.inp",
               'str\nphase_name "hot"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq bA 26.0\n')
    with pytest.raises(TopasInpError) as exc:
        to_structure(read_topas_inp(inp))
    assert "outofrange.inp" in str(exc.value) and "hot" in str(exc.value)


# ------------------------------------------------------------ the robustness pin

def test_a_truncated_inp_never_escapes_as_anything_but_a_topas_error(tmp_path):
    """`io/CLAUDE.md`'s refusal rule, pinned: a reader raises `TopasInpError`
    naming the file, never its parser's exception.

    This is the `test_readers_robust.py` arm one subtree over, and the reason
    it is written down is that the rule is easy to lose — a ragged cut through
    a site line or a macro argument is exactly where a bare `ValueError` or an
    `IndexError` gets out. Bounded to ~200 offsets on purpose: the same sweep
    at every byte offset of seven real archive files (~57 700 truncations) also
    passes, and it is not a test anyone should wait for.
    """
    raw = _REALISTIC.encode("utf-8")
    target = tmp_path / "cut.inp"
    offsets = sorted({round(i * len(raw) / 199) for i in range(200)})
    for n in offsets:
        target.write_bytes(raw[:n])
        try:
            to_structure(read_topas_inp(target))
        except TopasInpError:
            pass
        except Exception as exc:            # noqa: BLE001 — the point of the test
            raise AssertionError(
                f"truncation at {n} of {len(raw)} bytes escaped as "
                f"{type(exc).__name__}: {exc}") from exc


# ============================================================ round-three review
# The grammar is unified per keyword; the scan was still per line, and TOPAS is
# whitespace-insensitive — so a cell or a second site packed onto one line was
# read wrong or dropped. Each reproduction below is the reviewer's own.

# ---------------------------- finding 1: a cell packed onto one line

@pytest.mark.parametrize("cell_line, expected", [
    # `a 5.4 b 6.1 c 7.2` read only `a` and built a=b=c — orthorhombic arrived
    # cubic with nothing raised.
    ("a 5.4 b 6.1 c 7.2", {"a": 5.4, "b": 6.1, "c": 7.2}),
    # the same with parameter names, so `b` is not the line's first token.
    ("a lpa 5.4 b lpb 6.1 c lpc 7.2", {"a": 5.4, "b": 6.1, "c": 7.2}),
    # `al 90 be 90 ga 120` read only `al`, so `ga` defaulted to 90.
    ("a 5.4\nal 90 be 90 ga 120", {"a": 5.4, "al": 90.0, "be": 90.0, "ga": 120.0}),
])
def test_a_cell_packed_onto_one_line_reads_every_key(tmp_path, cell_line, expected):
    """The stated-key refusal was gated on `re.match(rf"\\s*{key}\\b", ln)`, a
    line anchor, so a cell key mid-line was invisible to both the read and the
    refusal. The scan is token-oriented now, after `_cell_search_text` blanks
    the macro parentheses the anchor existed to protect."""
    inp = _inp(tmp_path, "packed.inp",
               f'str\nphase_name "P"\nspace_group "P1"\n{cell_line}\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    for key, value in expected.items():
        assert phase.cell[key] == pytest.approx(value)


def test_an_orthorhombic_cell_on_one_line_does_not_arrive_cubic(tmp_path):
    """`a 5.4 b 6.1 c 7.2` built a=b=c=5.4 and an orthorhombic phase arrived
    cubic with nothing raised — the reviewer's first example, through the
    build."""
    inp = _inp(tmp_path, "ortho.inp",
               'str\nphase_name "ortho"\nspace_group "Pmmm"\n'
               'a 5.4 b 6.1 c 7.2\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    cell = to_structure(read_topas_inp(inp)).phases[0].cell
    assert (cell.a.value, cell.b.value, cell.c.value) == \
        pytest.approx((5.4, 6.1, 7.2))


def test_a_hexagonal_gamma_on_a_packed_angle_line_is_not_ninety(tmp_path):
    """`al 90 be 90 ga 120` read `ga` as 90, so a P6/mmm built with gamma 90 and
    the eventual refusal was ParameterTable's, naming the cell rather than the
    file. Read correctly, gamma is 120 and no refusal follows."""
    inp = _inp(tmp_path, "hex.inp",
               'str\nphase_name "hex"\nspace_group "P6/mmm"\n'
               'a 3.6 b 3.6 c 5.9\nal 90 be 90 ga 120\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    cell = to_structure(read_topas_inp(inp)).phases[0].cell
    assert cell.gamma.value == pytest.approx(120.0)


def test_a_named_macro_argument_is_not_read_as_a_cell_line(tmp_path):
    """The line anchor kept `lpa` inside `Cubic_(lpa …)` off the `a` scan; the
    token scan keeps that by blanking macro parentheses, so even a macro whose
    argument is *literally* `a` is the macro's, not an `a` line."""
    inp = _inp(tmp_path, "namedarg.inp",
               'str\nphase_name "P"\nspace_group "Pm-3m"\n'
               'Cubic_(a 4.15689)\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    cell = read_topas_inp(inp).phases[0].cell
    assert cell["a"] == pytest.approx(4.15689)   # from the macro, filling b, c
    assert cell["b"] == pytest.approx(4.15689)


# ---------------------------- finding 2: a second site on one line

def test_a_second_site_on_one_line_is_a_second_atom(tmp_path):
    """`site A1 … beq b 0.5 site B1 x 0.5 …` gave one atom, nothing raised — the
    per-line scan matched the line once, and the count guard `len(sites) !=
    len(site_lines)` counted lines, so the missing site was never a line.
    `_SITE_KEYWORDS` already lists `site` as an occupancy terminator, so the
    grammar half knew; the sites are split token-wise now (finding 2)."""
    inp = _inp(tmp_path, "twosite.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq bA 0.5 '
               'site B1 x 0.5 y 0.5 z 0.5 occ Cl-1 1 beq bB 0.8\n')
    sites = read_topas_inp(inp).phases[0].sites
    assert [s.label for s in sites] == ["A1", "B1"]
    assert (sites[1].x, sites[1].y, sites[1].z) == pytest.approx((0.5, 0.5, 0.5))
    assert sites[1].beq == pytest.approx(0.8)
    atoms = to_structure(read_topas_inp(inp)).phases[0].atoms
    assert [a.label for a in atoms] == ["A1", "B1"]


# ---------------------- finding 2: a mixed site keeps every species

def test_a_mixed_site_with_several_occ_tokens_builds_one_atom_per_species(tmp_path):
    """`occ Al+3 0.9 occ Cr+3 0.1` on one line is a mixed site — the two-`site`-
    line spelling already builds two atoms, and this maps to the same
    representation (round-five finding 2). The predecessor returned Al alone,
    silently, and the phase's Z·M was then that of the wrong composition. Three
    occ tokens, same."""
    inp = _inp(tmp_path, "mixed.inp",
               'str\nphase_name "M"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0.1 y 0.2 z 0.3 occ Al+3 0.9 occ Cr+3 0.1 beq b 0.5\n')
    sites = read_topas_inp(inp).phases[0].sites
    assert [(s.species, s.occupancy) for s in sites] == [("Al3+", 0.9), ("Cr3+", 0.1)]
    # the label, coordinates and B are shared, exactly as the two-line form
    assert all(s.label == "A1" for s in sites)
    assert all((s.x, s.y, s.z) == pytest.approx((0.1, 0.2, 0.3)) for s in sites)
    assert all(s.beq == pytest.approx(0.5) for s in sites)
    atoms = to_structure(read_topas_inp(inp)).phases[0].atoms
    assert [a.species for a in atoms] == ["Al3+", "Cr3+"]


def test_three_occ_tokens_on_one_site_build_three_atoms(tmp_path):
    inp = _inp(tmp_path, "tri.inp",
               'str\nphase_name "M"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Al+3 0.8 occ Cr+3 0.1 occ Fe+3 0.1 beq b 0.5\n')
    sites = read_topas_inp(inp).phases[0].sites
    assert [(s.species, s.occupancy) for s in sites] == \
        [("Al3+", 0.8), ("Cr3+", 0.1), ("Fe3+", 0.1)]


def test_a_dropped_second_species_is_a_wrong_cell_mass(tmp_path):
    """The QPA cost the reviewer measured, pinned as a Z·M (= cell_mass): the
    mixed site's second species carries mass, and dropping it changes the
    phase's Z·M and so its Hill-Howard weight fraction. On a constructed two-
    phase mixture the reviewer measured Z·M 147.986 (both species) against
    89.874 (the first alone), a 10.2 wt% error. The construction here is an
    Fm-3m 4a site half Al half Cr: Z·M 157.9553 with both species against
    53.9631 with Al alone."""
    from rietx.optimize.qpa import phase_zmv

    def _zm(line):
        st = to_structure(read_topas_inp(_inp(
            tmp_path, "zm.inp",
            'str\nphase_name "M"\nspace_group "Fm-3m"\na 4.2\n' + line + "\n")))
        ph = st.phases[0]
        return phase_zmv(ph.space_group, ph.cell.lengths_angles(),
                         [(a.species, a.x.value, a.y.value, a.z.value, a.occ.value)
                          for a in ph.atoms]).cell_mass

    both = _zm('site A1 x 0 y 0 z 0 occ Al+3 0.5 occ Cr+3 0.5 beq b 0.5')
    al_only = _zm('site A1 x 0 y 0 z 0 occ Al+3 0.5 beq b 0.5')
    assert both == pytest.approx(157.9553, abs=1e-3)
    assert al_only == pytest.approx(53.9631, abs=1e-3)
    assert both > al_only            # the dropped species was mass, not noise


# ------------------ finding 3: species and occupancy travel together

def test_a_species_takes_its_own_value_not_the_next_occs(tmp_path):
    """`occ Al+3 occ Cr+3 0.1` — the predecessor read the species off match one
    and the value off match two, so **Al** arrived at 0.1, Cr's value (round-
    five finding 3). Each occ token is read once now: Al states no value and
    keeps the format's own 1.0, Cr states 0.1 and keeps it."""
    inp = _inp(tmp_path, "pair.inp",
               'str\nphase_name "M"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Al+3 occ Cr+3 0.1 beq b 0.5\n')
    sites = read_topas_inp(inp).phases[0].sites
    assert [(s.species, s.occupancy) for s in sites] == [("Al3+", 1.0), ("Cr3+", 0.1)]


# ---------------------------- finding 3: the splitter's own guard is blind

def test_a_macro_definition_inside_a_str_block_does_not_truncate_the_phase(tmp_path):
    """A `macro dummy { 1 }` DEFINITION inside a `str` block truncated the phase
    (one atom, `weight_percent None`, silent) because `macro` was treated as a
    block opener, and the per-phase count guard was blind by construction — both
    its numbers came off the same truncated chunk. A macro is excised as a
    definition now, so the phase continues past it (finding 3)."""
    inp = _inp(tmp_path, "macrodef.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'macro dummy { 1 }\n'
               'weight_percent wp 42.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'site B1 x 0.5 y 0.5 z 0.5 occ Cl-1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert [s.label for s in phase.sites] == ["A1", "B1"]
    assert phase.weight_percent == pytest.approx(42.0)


def test_the_file_level_site_guard_counts_over_the_whole_file(tmp_path):
    """The per-phase guard is computed from the splitter's own output, so it
    cannot see a splitter error. The file-level guard counts `site` tokens over
    `active`, independent of the split (finding 3): a `site` the reader neither
    parsed into a phase nor recorded on a skipped block is refused, naming the
    file."""
    inp = _inp(tmp_path, "guard.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'hkl_Is\nphase_name "pawley"\n'
               'site STRAY x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "guard.inp" in str(exc.value) and "site` tokens" in str(exc.value)


# ---------------------------- finding 4: a skipped phase dropped while one builds

def test_a_nameless_phase_that_carries_a_cell_is_not_dropped_while_another_builds(
        tmp_path):
    """`to_structure` quoted `skipped_blocks` only in the zero-phase branch, so
    a nameless second phase (60 wt%) vanished when the first phase read and the
    totals no longer summed (finding 4). It refuses instead — the choice
    consistent with io/CLAUDE.md's "report or refuse, never drop" where there is
    no diagnostics channel — and the skipped block records the cell, scale and
    weight_percent it carried, not only its site count."""
    inp = _inp(tmp_path, "twophase.inp",
               'str\nphase_name "A"\nspace_group "P1"\na 5.0\n'
               'weight_percent wpA 40.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'str\nspace_group "Fm-3m"\na 4.2\n'
               'scale scB 0.01\nweight_percent 60.0\n'
               'site B1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert [p.name for p in model.phases] == ["A"]
    (sb,) = model.skipped_blocks
    assert sb.lacked == "phase_name"
    assert sb.cell["a"] == pytest.approx(4.2)
    assert sb.scale == pytest.approx(0.01)
    assert sb.weight_percent == pytest.approx(60.0)
    with pytest.raises(TopasInpError) as exc:
        to_structure(model)
    assert "twophase.inp" in str(exc.value)
    assert "no longer summing" in str(exc.value)


# ---------------------------- finding 5: beq's 0.5 seed is a builder's, not a fact

def test_a_site_that_states_no_beq_is_none_on_the_model_and_seeded_at_build(tmp_path):
    """`beq` substituted 0.5 where the site line stated none, and a caller could
    not tell it from a stated value though `TopasModel` is "what a .inp states"
    (finding 5). `beq` is `None` on the model now; the 0.5 seed moves to
    `to_structure`. `occ` defaulting to 1.0 is the format's own default and is
    left alone."""
    inp = _inp(tmp_path, "nobeq.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1\n')
    site = read_topas_inp(inp).phases[0].sites[0]
    assert site.beq is None
    assert site.occupancy == pytest.approx(1.0)
    biso = to_structure(read_topas_inp(inp)).phases[0].atoms[0].biso
    assert biso.value == pytest.approx(0.5)


def test_a_stated_beq_is_kept_verbatim_and_not_confused_with_the_seed(tmp_path):
    """The other half: a *stated* beq — including a stated 0.5 — is the file's,
    read as-is, and distinguishable from the absent case above only because the
    absent one is `None`."""
    inp = _inp(tmp_path, "yesbeq.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    assert read_topas_inp(inp).phases[0].sites[0].beq == pytest.approx(0.5)


# ------------- round-five finding 1: a stated tensor is carried, built on
# opt-in, and never silently replaced by the isotropic seed

ADP_TAIL = 'u11 0.013 u22 0.013 u33 0.013 u12 0 u13 0 u23 0'


@pytest.mark.parametrize("line", [
    'site Na1 x 0 y 0 z 0 occ Na+1 1 adps ' + ADP_TAIL,
    'site Na1 x 0 y 0 z 0 occ Na+1 1 ' + ADP_TAIL,   # bare u11…, no `adps`
])
def test_a_stated_adp_tensor_is_carried_on_the_model(tmp_path, line):
    """`u11 0.013 …` came back with no tensor and `beq` None, and `to_structure`
    then seeded biso 0.5 — for NaCl at U = 0.013 that is B_eq = 8π²·0.013 =
    1.026 read as 0.5, which the reviewer measured at max |ΔI|/I_max 3.6 % and
    +34.7 % on the strongest 90-140° peak, nothing raised (round-five finding
    1). The tensor is carried now, `adps` keyword or not. Convention: TOPAS's
    u_ij are U^ij in Å² — the CIF `_atom_site_aniso_U_ij` convention `AnisoU`
    holds — so the numbers transfer unchanged."""
    inp = _inp(tmp_path, "adp.inp",
               'str\nphase_name "NaCl"\nspace_group "Fm-3m"\na 5.64\n' + line + "\n")
    site = read_topas_inp(inp).phases[0].sites[0]
    assert site.adps == {"u11": 0.013, "u22": 0.013, "u33": 0.013,
                         "u12": 0.0, "u13": 0.0, "u23": 0.0}
    assert site.beq is None


def test_a_stated_tensor_the_caller_did_not_ask_for_is_refused_not_seeded(tmp_path):
    """The hard constraint: what the build may not do is seed 0.5 in silence.
    `to_structure` without `aniso=True` refuses a tensor-stating site by name,
    the same opt-in shape as `structure_from_cif(aniso=...)`."""
    inp = _inp(tmp_path, "adp.inp",
               'str\nphase_name "NaCl"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 ' + ADP_TAIL + "\n")
    with pytest.raises(TopasInpError) as exc:
        to_structure(read_topas_inp(inp))
    msg = str(exc.value)
    assert "'Na1'" in msg and "anisotropic" in msg and "aniso=True" in msg


def test_the_opt_in_builds_the_tensor_in_the_cif_u_convention(tmp_path):
    """`aniso=True` builds the `AnisoU` block; biso becomes the schema's inert
    record (vary False), valued at the file's beq where stated, else 8π²·U_eq
    from the trace — the CIF path's own fallback — never the 0.5 seed."""
    import math

    inp = _inp(tmp_path, "adp.inp",
               'str\nphase_name "NaCl"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 ' + ADP_TAIL + "\n")
    atom = to_structure(read_topas_inp(inp), aniso=True).phases[0].atoms[0]
    assert atom.aniso is not None
    assert atom.aniso.u11.value == pytest.approx(0.013)
    assert atom.aniso.u23.value == pytest.approx(0.0)
    assert atom.biso.value == pytest.approx(8 * math.pi ** 2 * 0.013)  # 1.026
    assert atom.biso.vary is False


def test_a_beq_beside_the_tensor_keeps_both_numbers(tmp_path):
    """`beq` beside the tensor used to keep B and silently drop the anisotropy.
    Both are the file's: the tensor builds, and the stated beq is the inert
    isotropic record."""
    inp = _inp(tmp_path, "adpbeq.inp",
               'str\nphase_name "NaCl"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 beq b 0.7 ' + ADP_TAIL + "\n")
    model = read_topas_inp(inp)
    assert model.phases[0].sites[0].beq == pytest.approx(0.7)
    assert model.phases[0].sites[0].adps["u11"] == pytest.approx(0.013)
    atom = to_structure(model, aniso=True).phases[0].atoms[0]
    assert atom.aniso.u11.value == pytest.approx(0.013)
    assert atom.biso.value == pytest.approx(0.7)


def test_a_tensor_free_site_is_untouched_by_the_opt_in(tmp_path):
    """A mixed file yields a mixed structure, exactly as the CIF path: the
    opt-in changes nothing for a site that states no tensor."""
    inp = _inp(tmp_path, "mixadp.inp",
               'str\nphase_name "P"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 ' + ADP_TAIL + "\n"
               'site Cl1 x 0.5 y 0.5 z 0.5 occ Cl-1 1 beq b 1.2\n')
    na, cl = to_structure(read_topas_inp(inp), aniso=True).phases[0].atoms
    assert na.aniso is not None
    assert cl.aniso is None and cl.biso.value == pytest.approx(1.2)


def test_an_adp_components_refine_flag_travels_with_its_value(tmp_path):
    inp = _inp(tmp_path, "adpflag.inp",
               'str\nphase_name "P"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 '
               'u11 @ 0.013 u22 0.013 u33 !u33f 0.013 u12 0 u13 0 u23 0\n')
    atom = to_structure(read_topas_inp(inp), aniso=True).phases[0].atoms[0]
    assert atom.aniso.u11.vary is True
    assert atom.aniso.u33.vary is False


def test_a_stated_tensor_component_the_reader_cannot_resolve_refuses(tmp_path):
    """Finding 4's rule reaches the tensor: a stated u_ij that cannot be read
    refuses naming the component and the line, rather than becoming a 0."""
    inp = _inp(tmp_path, "adpbad.inp",
               'str\nphase_name "P"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 u11 =mystery; u22 0.01 u33 0.01\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "cannot read u11" in str(exc.value)


def test_a_partial_tensor_with_a_missing_diagonal_is_refused(tmp_path):
    """An off-diagonal the file omits is 0 by the format's convention; a
    *diagonal* it omits has no default this reader may invent."""
    inp = _inp(tmp_path, "adppart.inp",
               'str\nphase_name "P"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 u11 0.013 u22 0.013\n')
    with pytest.raises(TopasInpError) as exc:
        to_structure(read_topas_inp(inp), aniso=True)
    assert "partial anisotropic tensor" in str(exc.value)


# ------------- round-five finding 4: a stated occ/beq that cannot be read refuses

@pytest.mark.parametrize("line, key", [
    ('site A1 x 0 y 0 z 0 occ Na+1 =mystery; beq b 0.5', "occ"),
    ('site A1 x 0 y 0 z 0 occ Na+1 1 beq =mystery;', "beq"),
])
def test_a_stated_occ_or_beq_the_reader_cannot_resolve_refuses(tmp_path, line, key):
    """`x =mystery;` already refuses, naming the line; `occ =mystery;` returned
    1.0 and `beq =mystery;` returned None → seeded 0.5, both silently (round-five
    finding 4). The established rule — a stated key that could not be read refuses
    naming the key and the line, an absent key keeps its default — now reaches
    occ and beq."""
    inp = _inp(tmp_path, "unresolvable.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n' + line + "\n")
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    msg = str(exc.value)
    assert "unresolvable.inp" in msg
    assert f"cannot read {key}" in msg
    assert line in msg                       # the offending line, named


def test_an_absent_occ_or_beq_still_keeps_its_default_not_a_refusal(tmp_path):
    """The other side of the same rule: a site that *omits* beq keeps the None
    that seeds 0.5, and an occupancy the file omits keeps 1.0 — an absent key is
    the file's own claim, not a value the reader could not read."""
    inp = _inp(tmp_path, "absent.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1\n')     # no beq, no occ value
    site = read_topas_inp(inp).phases[0].sites[0]
    assert site.beq is None and site.occupancy == pytest.approx(1.0)


# ---------------------------- finding 6: an absent writer is not a claim

def test_the_negative_beq_docstring_does_not_claim_a_pcr_reader_exists():
    """WP-1076: a declared name is a claim. The sibling `.pcr` reader lives on a
    *different* open PR (#111, `fullprof-pcr-reader`), not this tree, so
    `to_structure`'s docstring must state the rule a future/sibling reader keeps,
    not claim a file on this tree refuses the value (finding 6). The sentence
    becomes true when #111 merges."""
    doc = to_structure.__doc__
    assert "the sibling `.pcr` reader refuses the same value" not in doc
    assert "WP-1076" in doc


# ---------------------------- the `'/*` idiom (coordinator finding)

def test_strip_comments_apostrophe_delimiters_are_not_block_comments():
    """A `/*` or `*/` preceded on its line by an unquoted `'` is comment text,
    not a delimiter — the `'/*` idiom comments out the block-comment delimiter
    itself, so the text between `'/*` and `'*/` is live. Stripping `/* */` first
    deleted it; the one-pass scan sees the `'` first."""
    out = strip_comments("'/*\nkeepme\n'*/")
    assert "keepme" in out
    # a real /* */ block is still removed, and a real trailing ' still cuts
    assert "gone" not in strip_comments("/* gone */\nkeepme")
    assert strip_comments('"/*not a comment*/"') == '"/*not a comment*/"'


def test_the_apostrophe_block_comment_idiom_keeps_the_phase_active(tmp_path):
    """Built from a minimal reproduction of `TOF neutron input LSF.inp` (ORNL
    NOMAD), where `'/*` and `'*/` enable one of three refinements. `strip_comments`
    removed `/* */` first and deleted the active phase; the fix reads it."""
    inp = _inp(tmp_path, "idiom.inp",
               "' a header\n"
               "/* la 1 lo 0.7093 */\n"          # a real block comment: dead
               "'/*\n"
               'str\nphase_name "LSF rhombohedral"\nspace_group "R-3cH"\n'
               'a 5.537319`\nb 5.537319`\nc 13.561602`\nal 90 be 90 ga 120\n'
               'site La1 x 0 y 0 z 0.25 occ La+3 .6 beq bl 1.14\n'
               "'*/\n")
    model = read_topas_inp(inp)
    assert [p.name for p in model.phases] == ["LSF rhombohedral"]
    assert model.wavelength is None          # the real /* */ block was stripped
    assert model.phases[0].cell["c"] == pytest.approx(13.561602)


# ============================================================= round-four review
# The token scan put the whole safety of the scan onto the mask, and the mask was
# line-wise while the scan was token-wise — this round's own asymmetry one level
# down. One masked text is built once and every token scan reads it; the tests
# here pin what survives it, and the three regressions the hole let through.
# Each reproduction is the reviewer's own, measured against round two `2a69f76`.


# ---------------------------- the mask, pinned directly

def test_the_mask_blanks_the_space_group_value_so_a_letter_is_not_a_cell_key():
    """The invariant is the mask now, so it is pinned without a whole file: an
    unquoted Hermann-Mauguin symbol's value is blanked over the same span the
    reader's `space_group` regex reads, so `/c 1` is never a `c` token — while
    the real `a`/`b`/`c` lines and the `site` token survive for the scans that
    need them."""
    chunk = ('phase_name x\nspace_group P 1 21/c 1\n'
             'a 5.0\nb 6.0\nc 7.0\nsite A1 x 0 y 0 z 0 occ Na+1 1\n')
    base = _masked(chunk)
    assert "21/c" not in base                       # the symbol's value is gone
    assert "\na 5.0\n" in "\n" + base + "\n"         # real cell lines survive
    assert "b 6.0" in base and "c 7.0" in base
    assert "site A1" in base                         # the site token survives


def test_the_cell_mask_blanks_a_site_segment_not_a_site_line():
    """A site whose fields continue on the next line has the whole *segment*
    blanked for the cell scan — the `b` naming `beq`'s value is gone — but a real
    `b`/`c` line resuming below the site block is not, because the segment ends
    where the edges resume at a line start."""
    chunk = ('site A1 x 0 y 0 z 0 occ Na+1 1\n     beq b 0.5\n'
             'a 5.0\nb 6.0\nc 7.0\n')
    cell = _cell_search_text(chunk)
    assert "beq" not in cell                          # the continuation is gone
    assert "b 6.0" in cell and "c 7.0" in cell        # the cell resuming survives
    # but the base mask keeps the site token, for the split and the count
    assert "site A1" in _masked(chunk)


def test_the_mask_blanks_the_word_site_in_a_path_or_macro_but_keeps_a_real_one():
    """A `site` inside a quoted path or a macro argument is not a site token, so
    neither the file-level count nor the split may see it; a real one must."""
    base = _masked('xdd "C:\\data\\site\\run1.xy"\nOut_X_Ycalc("site.xy")\n'
                   'site A1 x 0 y 0 z 0 occ Na+1 1\n')
    assert len(re.findall(r"\bsite\b", base)) == 1    # only the real one


# ---------------------------- finding 1: an unquoted Hermann-Mauguin symbol

@pytest.mark.parametrize("sg, key, value", [
    # the full monoclinic spellings TOPAS and GSAS write out carry a lattice
    # letter immediately followed by a number, so `/c 1` read c = 1.0 and `/a 1`
    # read a = 1.0 — every d-spacing wrong, nothing raised.
    ("P 1 21/c 1", "c", 7.0),
    ("P 1 21/a 1", "a", 5.0),
])
def test_an_unquoted_hermann_mauguin_symbol_is_not_read_as_a_cell_key(
        tmp_path, sg, key, value):
    """`space_group P 1 21/c 1` read `/c 1` as c = 1.0: the symbol sits above the
    cell and the loop takes the first line that reads, so it won. The mask blanks
    the value over the span the reader's own regex consumes, so the real `c 7.0`
    line is the first `c` left (finding 1)."""
    inp = _inp(tmp_path, "hm.inp",
               f'str\nphase_name x\nspace_group {sg}\n'
               'a 5.0\nb 6.0\nc 7.0\nbe 99.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell[key] == pytest.approx(value)
    assert phase.space_group == sg                # the symbol itself is preserved


def test_a_quoted_hermann_mauguin_symbol_stays_safe(tmp_path):
    """Quoted symbols were already safe, because strings are blanked; keep it."""
    inp = _inp(tmp_path, "hmq.inp",
               'str\nphase_name x\nspace_group "P21/a"\n'
               'a 5.0\nb 6.0\nc 7.0\nbe 99.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert (phase.cell["a"], phase.cell["c"]) == pytest.approx((5.0, 7.0))


# ---------------------------- finding 2: a site declaration continues past the line

def test_a_beq_name_on_a_continuation_line_is_not_read_as_a_cell_edge(tmp_path):
    """`beq b 0.5` on its own line left the `b` naming the parameter exposed, and
    a cubic phase — which states no `b` line for the real value to win with —
    read b = 0.5 as a cell edge. Blanked as a site *segment*, `b` stays tied to
    `a` (finding 2)."""
    inp = _inp(tmp_path, "cont_b.inp",
               'str\nphase_name cubic\nspace_group Fm-3m\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1\n     beq b 0.5\n')
    model = read_topas_inp(inp)
    assert "b" not in model.phases[0].cell        # not stated; not leaked
    assert to_structure(model).phases[0].cell.b.value == pytest.approx(4.0)


def test_a_beq_name_ga_on_a_continuation_line_is_not_read_as_an_angle(tmp_path):
    """The same for `beq ga 0.5` on a gallium site: `ga` stayed 90°, not 0.5°."""
    inp = _inp(tmp_path, "cont_ga.inp",
               'str\nphase_name cubic\nspace_group Fm-3m\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Ga+3 1\n     beq ga 0.5\n')
    model = read_topas_inp(inp)
    assert "ga" not in model.phases[0].cell
    assert to_structure(model).phases[0].cell.gamma.value == pytest.approx(90.0)


def test_a_site_block_above_the_cell_lines_does_not_leak_into_the_cell(tmp_path):
    """The site block sits *above* the cell here, so `beq b 0.5` was read as
    b = 0.5 before the real `b 6.0` below it. The segment ends where the edges
    resume at a line start, so `b` is 6.0 — the one place "blank to block end"
    would have blanked the real cell and defaulted it (finding 2)."""
    inp = _inp(tmp_path, "above.inp",
               'str\nphase_name ortho\nspace_group Pmmm\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1\n     beq b 0.5\n'
               'a 5.0\nb 6.0\nc 7.0\n')
    phase = read_topas_inp(inp).phases[0]
    assert (phase.cell["a"], phase.cell["b"], phase.cell["c"]) == \
        pytest.approx((5.0, 6.0, 7.0))
    assert phase.sites[0].beq == pytest.approx(0.5)   # still read as the site's B


# ---------------------------- finding 3: the other scans must use the mask too

def test_a_path_containing_site_above_a_block_does_not_trigger_the_count(tmp_path):
    """`xdd "C:\\data\\site\\run1.xy"` above the block had the file-level guard
    count a `site` token the file never stated and refuse a file that dropped no
    site — the confident wrong diagnosis with its sign flipped. The count reads
    the mask now, so the word in the path is gone (finding 3)."""
    inp = _inp(tmp_path, "pathsite.inp",
               'xdd "C:\\data\\site\\run1.xy"\n'
               'str\nphase_name P\nspace_group P1\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    model = read_topas_inp(inp)                    # no refusal
    assert [s.label for s in model.phases[0].sites] == ["A1"]


def test_a_macro_string_containing_site_inside_a_block_is_not_split_as_a_site(
        tmp_path):
    """`Out_X_Ycalc("site.xy")` inside the block had the split cut a bogus segment
    and raise "no label/occ in site: 'site.xy\\")'". The split takes its
    boundaries off the mask, where the macro's string is blanked, so only the
    real site is a site (finding 3)."""
    inp = _inp(tmp_path, "macrostr.inp",
               'str\nphase_name P\nspace_group P1\na 5.0\n'
               'Out_X_Ycalc("site.xy")\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    model = read_topas_inp(inp)                    # no refusal
    assert [s.label for s in model.phases[0].sites] == ["A1"]


# ---------------------------- housekeeping: the refusal agrees with itself

@pytest.mark.parametrize("second_blocks, n_carrying, n_building, singular", [
    # one nameless block carrying a cell, one named phase building: both singular.
    ('str\nspace_group "Fm-3m"\na 4.2\nsite B1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n',
     1, 1, True),
    # two nameless blocks carrying a cell: the noun and the verb both pluralise.
    ('str\nspace_group "Fm-3m"\na 4.2\nsite B1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n'
     'str\nspace_group "Im-3m"\na 3.9\nsite C1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n',
     2, 1, False),
])
def test_the_dropped_block_refusal_agrees_in_number(
        tmp_path, second_blocks, n_carrying, n_building, singular):
    """The refusal pluralised its nouns but not its verbs — "1 `str` block here
    state a cell" and "1 other phase build". Both agree now, singular and
    plural."""
    inp = _inp(tmp_path, "agree.inp",
               'str\nphase_name "A"\nspace_group "P1"\na 5.0\n'
               'weight_percent wpA 40.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n' + second_blocks)
    with pytest.raises(TopasInpError) as exc:
        to_structure(read_topas_inp(inp))
    msg = str(exc.value)
    if singular:
        assert "block here states a cell" in msg
        assert "other phase builds would" in msg
    else:
        assert "blocks here state a cell" in msg
        assert "other phase builds would" in msg
