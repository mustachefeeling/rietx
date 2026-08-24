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

from pathlib import Path

import pytest

from rietx.io.projects.topas import (
    TopasInpError,
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

