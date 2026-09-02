"""The FullProf ``.pcr`` project reader.

Every fixture here is written inline, per ``io/CLAUDE.md``: a text format's lines
are self-describing, so a literal in the test says more than a writer that
shares constants with the parser could.

**The real files are not committed.** The corpus this reader was written against
is six ``.pcr`` files from the maintainer's own archive, which are the owner's
data and are not this repo's to vendor. So the fixtures below are *minimal
synthetic* files that exercise one grammar branch each, and the provenance is
carried as a **quotation in a comment**: every line, every codeword and every
count in them was copied out of a named real file at a named line, so a reader
can check where each came from without the file being here. The real-file
verification is a manual check, recorded in the session report; ``ATTRIBUTION.md``
§ Format specifications records what the format facts were read from.

The failure mode this reader exists to prevent is not a crash but a *wrong
number with nothing raised*, so the assertions are about the tri-state and the
counts, not only the values:

* a **codeword** carries which refined parameter drives a value *and the sign*,
  so ``11.00`` and ``-11.00`` on two sublattices are the antiferromagnetic
  constraint and a reader that recorded only "refined" would lose the physics;
* a **count** the file declares is asserted against the lines parsed, because a
  ``.pcr`` is positional and has no keyword to resynchronise on — a dropped
  atom or background point silently reinterprets everything after it;
* a **refusal** is asserted by its message, because the whole scope claim of
  this reader is "handles X, refuses Y *by name*".
"""

from pathlib import Path

import pytest

import rietx as rx
from rietx.io.projects.fullprof import (
    FullProfPcrError,
    _strip,
    atom_tie_recoverability,
    cell_parameter_ties,
    decode_codeword,
    normalize_space_group,
    normalize_species,
    nuclear_parameter_ties,
    occupancy_factor,
    read_fullprof_pcr,
    to_structure,
)
from rietx.schemas.instrument import NeutronSource

# --------------------------------------------------------------- the fixtures
#
# One header, three phase blocks and a trailing range line, assembled per test.
# Every line is quoted from `crwo6002_momcomp.pcr` (the Cr2WO6 + Cr2O3 + magnetic
# neutron CW refinement) unless the comment says otherwise, with the background
# cut from 51 points to 2 and the excluded regions from 2 to 1 so the fixture
# stays readable. The `!` header comments are kept verbatim *because they are
# what a real file has* — nothing here reads them, which is trap 2.

#: crwo6002_momcomp.pcr:1-14, :16-18 (two of 51 background points), :69-70 (one
#: of two excluded regions), :74 and :76-77.
_HEADER = """\
COMM 60 K
! Current global Chi2 (Bragg contrib.) =      5.144
! Files => DAT-file: CrWO6002.dat,  PCR-file: crwo6002_momcomp
!Job Npr Nph Nba Nex Nsc Nor Dum Iwg Ilo Ias Res Ste Nre Cry Uni Cor Opt Aut
   {job}   7   {nph}   2   1   0   0   0   0   0   0   0   0   0   0   0   0   0   0
!
!Ipr Ppl Ioc Mat Pcr Ls1 Ls2 Ls3 NLI Prf Ins Rpa Sym Hkl Fou Sho Ana
   0   0   1   2   2   0   4   0   0   1   0  -1   1   0   0   1   0
!
! Lambda1  Lambda2    Ratio    Bkpos    Wdt    Cthm     muR   AsyLim   Rpolarz  2nd-muR -> Patt# 1
 2.077100 2.077100  0.50000   70.000  4.0000  0.0000  0.2160  160.00    0.0000  0.2160
!
!NCY  Eps  R_at  R_an  R_pr  R_gl     Thmin       Step       Thmax    PSD    Sent0
 45  0.05  0.85  0.85  0.85  0.85      3.0000   0.050000   166.2000   0.000   0.000
!
!2Theta/TOF/E(Kev)   Background  for Pattern#  1
        12.9000       952.8345         91.00
        16.4000       977.2739        101.00
!
! Excluded regions (LowT  HighT) for Pattern#  1
        0.00        9.00
!
      61    !Number of refined parameters
!
!  Zero    Code    SyCos    Code   SySin    Code  Lambda     Code MORE ->Patt# 1
 -0.03994  601.0  0.00000    0.0  0.00000    0.0 2.370100    0.00   0
"""

#: crwo6002_momcomp.pcr:88-95 — the four trirutile sites, each a value line and
#: a codeword line, with the `#color cyan` annotation the real file carries.
_CR2WO6_SITES = """\
Cr     CR      0.00000  0.00000  0.33312  0.21358   0.50000   0   0   0    1  #color cyan
                  0.00     0.00     0.00     0.00      0.00
W      W       0.00000  0.00000  0.00000  0.22402   0.25000   0   0   0    1  #color cyan
                  0.00     0.00     0.00     0.00      0.00
O1     O       0.30156  0.30156  0.00000  0.24694   0.50000   0   0   0    1  #color cyan
                  0.00     0.00     0.00     0.00      0.00
O2     O       0.30294  0.30294  0.34087  0.18463   1.00000   0   0   0    1  #color cyan
                  0.00     0.00     0.00     0.00      0.00"""

#: crwo6002_momcomp.pcr:96-108. The cell codewords `51 51 61` are the tetragonal
#: tie: a and b are driven by parameter 5, c by parameter 6.
_PROFILE = """\
!-------> Profile Parameters for Pattern #  1
!  Scale        Shape1      Bov      Str1      Str2      Str3   Strain-Model
  {scale}       0.00000   0.00000   0.00000   0.00000   0.00000       0
    {scale_code}     0.000     0.000     0.000     0.000     0.000
!       U         V          W           X          Y        GauSiz   LorSiz Size-Model
   0.413324  -0.214088   0.112683   0.000000   0.000000   0.000000   0.000000    0
     21.000     31.000     41.000      0.000      0.000      0.000      0.000
!     a          b         c        alpha      beta       gamma      #Cell Info
{cell}
{cell_codes}
!  Pref1    Pref2      Asy1     Asy2     Asy3     Asy4      S_L      D_L
  0.00000  0.00000  0.02734  0.00000  0.00000  0.00000  0.03000  0.03000
     0.00     0.00    81.00     0.00     0.00     0.00     0.00     0.00"""

_CR2WO6_CELL = "   4.580088   4.580088   8.847341  90.000000  90.000000  90.000000"
_CR2WO6_CELL_CODES = "   51.00000   51.00000   61.00000    0.00000    0.00000    0.00000"

#: crwo6002_momcomp.pcr:78-84, :86-87.
_PHASE_TEMPLATE = """\
!-------------------------------------------------------------------------------
!  Data for PHASE number:   {labelled}  ==> Current R_Bragg for Pattern#  1:     {r_bragg}
!-------------------------------------------------------------------------------
{name}
!
!Nat Dis {third} Pr1 Pr2 Pr3 Jbt Irf Isy Str Furth       ATZ    Nvk Npr More
   {nat}   {dis}   {third_value} 0.0 0.0 1.0   {jbt}   {irf}  {isy}   {strn}   {furth}        963.500   {nvk}   7   {more}
!
{sg}               <--Space group symbol
{symmetry}{atom_header}
{atoms}
{profile}"""

_NUCLEAR_ATOM_HEADER = (
    "!Atom   Typ       X        Y        Z     Biso       Occ     In Fin N_t Spc /Codes")

#: crwo6002_momcomp.pcr:157-158 for `Isy = -1` (Rx/Ry/Rz then Ix/Iy/Iz) and
#: crwo6002_G5_nc.pcr:166-167 for `Isy = -2` (C1..C3 then C4..C9). Same columns,
#: different physical meaning — which is why nothing here reads the header.
_MAGNETIC_ATOM_HEADER = (
    "!Atom   Typ  Mag Vek    X      Y      Z       Biso    Occ      Rx      Ry      Rz\n"
    "!     Ix     Iy     Iz    beta11  beta22  beta33    MagPh")


def _phase(*, name="Cr2wO6", nat=4, jbt=0, isy=0, irf=0, dis=0, strn=0, furth=0,
           nvk=0, more=0, third_value=0, sg="P 42/m n m", symmetry="",
           atoms=_CR2WO6_SITES, atom_header=None, cell=_CR2WO6_CELL,
           cell_codes=_CR2WO6_CELL_CODES, scale="6.4296",
           scale_code="71.00000", labelled=1, r_bragg="1.79") -> str:
    """One phase block. ``third_value`` is the ``Ang``/``Mom`` column (trap 2)."""
    magnetic = jbt == 1
    return _PHASE_TEMPLATE.format(
        labelled=labelled, r_bragg=r_bragg, name=name, nat=nat, dis=dis,
        third="Mom" if magnetic else "Ang", third_value=third_value, jbt=jbt,
        irf=irf, isy=isy, strn=strn, furth=furth, nvk=nvk, more=more, sg=sg,
        symmetry=symmetry,
        atom_header=(_MAGNETIC_ATOM_HEADER if magnetic and atom_header is None
                     else _NUCLEAR_ATOM_HEADER if atom_header is None
                     else atom_header),
        atoms=atoms,
        profile=_PROFILE.format(scale=scale, scale_code=scale_code, cell=cell,
                                cell_codes=cell_codes))


#: crwo6002_momcomp.pcr:145-155, cut from four SYMM/MSYM pairs to two.
_ISY_MINUS_1_SYMMETRY = """\
!Nsym Cen Laue MagMat
   2   1   1   1
!
SYMM X, Y, Z
MSYM  u, v, w,0.000
SYMM Y, X, -Z+1
MSYM -u,-v, w,0.000
!
"""

#: crwo6002_momcomp.pcr:159-162 — one magnetic site, four lines. The `11.00`
#: codeword on Ry is parameter 1: the ordered moment.
_ISY_MINUS_1_ATOM = """\
CR     MCR3  1  0  0.00000 0.00000 0.33311 0.21358  1.00000   0.000   3.741   0.000
                      0.00    0.00    0.00    0.00     0.00    0.00   11.00    0.00
     0.000   0.000   0.000   0.000   0.000   0.000  0.00000
      0.00    0.00    0.00    0.00    0.00    0.00     0.00"""

#: crwo6002_G5_nc.pcr:145-164, cut from three SYMM blocks to two. Ireps = -2, so
#: each SYMM carries **two** BASR/BASI pairs, and N_Bas = 4 makes each of them
#: 3 x 4 = 12 numbers. Both counts are the invariant this fixture exists for.
_ISY_MINUS_2_SYMMETRY = """\
! Nsym   Cen  Laue Ireps N_Bas
     2     1      1    -2     4
! Real(0)-Imaginary(1) indicator for Ci
  0  0  0  0
!
SYMM X, Y, Z
BASR     2     0     0     0     2     0     0    -2     0    -2     0     0
BASI     0     0     0     0     0     0     0     0     0     0     0     0
BASR     2     0     0     0     2     0     0    -2     0    -2     0     0
BASI     0     0     0     0     0     0     0     0     0     0     0     0
SYMM -Y+1/2, X+1/2, Z+1/2
BASR     2     0     0     0    -2     0     0    -2     0     2     0     0
BASI     0     0     0     0     0     0     0     0     0     0     0     0
BASR     0     0     0     0     0     0     0     0     0     0     0     0
BASI     0     0     0     0     0     0     0     0     0     0     0     0
!
"""

#: crwo6002_G5_nc.pcr:168-175 — two Cr sublattices whose C2 coefficients carry
#: `11.00` and `-11.00`: one refined parameter, opposite signs, the
#: antiferromagnetic constraint. Note also the `.00000` spelling with no leading
#: zero, which is how that file writes every coordinate.
_ISY_MINUS_2_ATOMS = """\
1CR  MCR3  1   0    .00000  .00000  .33312 .21358 1.00000   0.000   0.800   0.000
                    0.00    0.00    0.00    0.00    0.00    0.00   11.00    0.00
   0.050   0.000   0.000   0.000   0.000   0.000   .00000
    0.00    0.00    0.00    0.00    0.00    0.00    0.00
2CR  MCR3  2   0    .00000  .00000  .66688 .21358 1.00000   0.000  -0.800   0.000
                    0.00    0.00    0.00    0.00    0.00    0.00  -11.00    0.00
   0.050   0.000   0.000   0.000   0.000   0.000   .00000
    0.00    0.00    0.00    0.00    0.00    0.00    0.00"""

#: crwo6002_momcomp.pcr:176-177.
_RANGE = """\
!  2Th1/TOF1    2Th2/TOF2  Pattern # 1
       9.000     157.000       1
"""


def _pcr(directory: Path, name: str, *phases: str, job: int = 1,
         nph: int | None = None, trailing: str = _RANGE) -> Path:
    """Write a fixture ``.pcr``. One writer, so the encoding is named once."""
    body = _HEADER.format(job=job, nph=len(phases) if nph is None else nph)
    text = body + "\n".join(phases) + "\n" + trailing
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def _magnetic_isy1(**kw) -> str:
    """The ``Isy = -1`` magnetic phase of ``crwo6002_momcomp.pcr``."""
    return _phase(**{"name": "Cr2wO6", "nat": 1, "jbt": 1, "isy": -1,
                     "sg": "P -1", "symmetry": _ISY_MINUS_1_SYMMETRY,
                     "atoms": _ISY_MINUS_1_ATOM, "labelled": 3,
                     "r_bragg": "9.46", **kw})


def _magnetic_isy2(**kw) -> str:
    """The ``Isy = -2`` magnetic phase of ``crwo6002_G5_nc.pcr``."""
    return _phase(**{"name": "Magnetic Phase", "nat": 2, "jbt": 1, "isy": -2,
                     "sg": "P -1", "symmetry": _ISY_MINUS_2_SYMMETRY,
                     "atoms": _ISY_MINUS_2_ATOMS, "labelled": 1,
                     "r_bragg": "1.00", **kw})


# ------------------------------------------------------------ the one grammar


@pytest.mark.parametrize("codeword, number, multiplier, provenance", [
    # Every row is a codeword copied out of a real file at the named line.
    (601.0, 60, 1.0, "crwo6002_momcomp.pcr:77 — the zero shift"),
    (71.00000, 7, 1.0, "crwo6002_momcomp.pcr:99 — a phase scale"),
    (51.00000, 5, 1.0, "crwo6002_momcomp.pcr:105 — the tetragonal a = b"),
    (61.00000, 6, 1.0, "crwo6002_momcomp.pcr:105 — the tetragonal c"),
    (11.00, 1, 1.0, "crwo6002_momcomp.pcr:160 — an ordered moment"),
    (-11.00, 1, -1.0, "crwo6002_G5_nc.pcr:173 — the *other* sublattice"),
    (611.00, 61, 1.0, "crwo6002_momcomp.pcr:175 — an asymmetry term"),
    (121.00, 12, 1.0, "yag_xpress_072_new.pcr:101 — a TOF Dtt2 shift"),
    (651.000, 65, 1.0, "crwo6002_BV2andBV4.pcr:102 — the stale-count case"),
])
def test_a_codeword_carries_the_parameter_and_the_sign(
        codeword, number, multiplier, provenance):
    """``10 x parameter + multiplier``, signed — two facts in one number.

    The sign is not decoration: ``11.00`` and ``-11.00`` on the two Cr
    sublattices of ``crwo6002_G5_nc.pcr`` are *one* refined moment entered with
    opposite signs, which is the antiferromagnetic constraint. A reader that
    recorded only "this was refined" would return two independent moments and
    lose the physics the file was written to express.
    """
    code = decode_codeword(codeword)
    assert code is not None, provenance
    assert (code.number, code.multiplier) == (number, multiplier)
    assert code.codeword == codeword          # verbatim, so the decode is checkable


def test_a_zero_codeword_is_fixed_not_parameter_zero():
    """``0.00`` is FullProf's spelling of *held*, and it is written for every
    parameter — which is why the tri-state's third state below is narrower than
    a TOPAS ``.inp``'s."""
    assert decode_codeword(0.0) is None


@pytest.mark.parametrize("codeword", [0.5, 1.0, -9.9])
def test_a_codeword_under_ten_is_refused_rather_than_read_as_fixed(codeword):
    """A codeword decoding to parameter 0 is a number no FullProf run writes —
    a truncated ``601.0`` reading as ``6`` is how one arises. Reading it as
    "fixed" would free-or-fix the wrong parameter with nothing raised."""
    with pytest.raises(FullProfPcrError, match="parameter number 0"):
        decode_codeword(codeword)


def test_the_refine_flag_is_a_tri_state(tmp_path):
    """Refined / fixed / *the codeword column is absent* — asserted as three
    states, not as two.

    FullProf writes the codeword slot for every refinable value, so unlike a
    TOPAS ``.inp`` "the file said nothing" is unreachable on an intact line.
    ``None`` therefore means the column is **not there** — a ragged or truncated
    line — and is never a stand-in for ``False``, because a lost tri-state reads
    as "held", which is a confident wrong protocol.
    """
    # crwo6002_momcomp.pcr:104-105: a and c refined (51/61), the angles held.
    # The codeword line here is cut short after three fields on purpose.
    pcr = _pcr(tmp_path, "tri.pcr",
               _phase(cell_codes="   51.00000   51.00000   61.00000"))
    cell = read_fullprof_pcr(pcr).phases[0].cell
    assert cell["a"].vary is True                 # codeword 51.00000
    assert cell["alpha"].vary is None             # the column is not there
    pcr = _pcr(tmp_path, "tri2.pcr", _phase())
    cell = read_fullprof_pcr(pcr).phases[0].cell
    assert cell["alpha"].vary is False            # codeword 0.00000, i.e. held


def test_a_shared_codeword_is_the_symmetry_tie(tmp_path):
    """``51.00000 51.00000 61.00000`` on a/b/c is how a ``.pcr`` writes
    a = b: one parameter number on two columns.

    Quoted from ``crwo6002_momcomp.pcr``:105. This is the fact a reader that
    stored only a bool would drop, and it is checkable against rietx's own
    derived tie — ``phases.0.cell.b`` is symmetry-tied to ``a`` for P 4₂/mnm, so
    the file and the package agree without either being told.
    """
    pcr = _pcr(tmp_path, "tie.pcr", _phase())
    cell = read_fullprof_pcr(pcr).phases[0].cell
    assert cell["a"].code.number == cell["b"].code.number == 5
    assert cell["c"].code.number == 6
    assert cell["a"].code.multiplier == 1.0


# -------------------------------------------------------------- normalisation


@pytest.mark.parametrize("written, expected, provenance", [
    ("CR", "Cr", "crwo6002_momcomp.pcr:88"),
    ("W", "W", "crwo6002_momcomp.pcr:90"),
    ("O", "O", "crwo6002_momcomp.pcr:92"),
    ("Co", "Co", "300q-1p5K_1.pcr:72 — already IUCr order, left alone"),
    ("AL", "Al", "yag_xpress_072_new.pcr:191"),
    ("Y", "Y", "yag_xpress_072_new.pcr:187"),
    # A magnetic form-factor label is a table name, not an element: rietx has
    # no counterpart, so it is returned verbatim rather than mangled into `Mc`.
    ("MCR3", "MCR3", "crwo6002_momcomp.pcr:159"),
    ("MCO3", "MCO3", "300q-1p5K_1.pcr:112"),
    # Charge, in either order, out in IUCr order — the same output convention
    # `projects/topas.py` uses, so the two readers hand back one spelling.
    ("CA+2", "Ca2+", "generalisation; no corpus file writes a charge"),
    ("O-2", "O2-", "generalisation"),
])
def test_species_are_normalised_to_iucr_order(written, expected, provenance):
    assert normalize_species(written) == expected, provenance


@pytest.mark.parametrize("written, expected, provenance", [
    ("P 42/m n m", "P 42/m n m", "crwo6002_momcomp.pcr:86 — already lower case"),
    ("R -3 c", "R -3 c", "crwo6002_momcomp.pcr:117"),
    ("P -1", "P -1", "crwo6002_momcomp.pcr:144"),
    # Upper case, and an origin choice gemmi resolves the *other* way from a
    # bare symbol: `F d -3 m` alone is choice 1, and the corpus's spinel is on
    # choice 2 (Co at 1/8,1/8,1/8 and 1/2,1/2,1/2).
    ("F D -3 M", "F d -3 m:2", "300q-1p5K_1.pcr:68"),
    ("I A -3 D", "I a -3 d", "yag_xpress_072_new.pcr:184 — one origin only"),
])
def test_the_symbol_is_case_normalised_and_the_origin_chosen(
        written, expected, provenance):
    """Only the lattice letter is upper case in a Hermann-Mauguin symbol, so
    lower-casing the tail is lossless; the origin choice is not, and dropping it
    selects the *other* origin with nothing raised.

    The choice is a convention, so it is not trusted:
    :func:`~rietx.io.projects.fullprof.occupancy_factor` re-derives every site
    multiplicity under whichever setting this returns, and a wrong origin makes
    the occupancy column stop reducing — see the occupancy tests below.
    """
    assert normalize_space_group(written) == expected, provenance


@pytest.mark.parametrize("raw, kept, provenance", [
    # A `!` opens a comment *inline* as well as at column 1, which is what makes
    # the refined-parameter count readable at all.
    ("      61    !Number of refined parameters", "61",
     "crwo6002_momcomp.pcr:74"),
    ("!Nat Dis Ang Pr1 Pr2 Pr3 Jbt Irf Isy Str Furth       ATZ    Nvk Npr More",
     "", "crwo6002_momcomp.pcr:83 — a header line is a comment"),
    ("P 42/m n m               <--Space group symbol", "P 42/m n m",
     "crwo6002_momcomp.pcr:86"),
    ("Cr     CR      0.00000  0.00000  0.33312  0.21358   0.50000   0   0   0    1  #color cyan",
     "Cr     CR      0.00000  0.00000  0.33312  0.21358   0.50000   0   0   0    1",
     "crwo6002_momcomp.pcr:88"),
])
def test_a_comment_is_cut_wherever_it_opens(raw, kept, provenance):
    assert _strip(raw) == kept, provenance


# ---------------------------------------------------------- count invariants


def test_the_declared_counts_are_asserted_against_the_lines_parsed(tmp_path):
    """Nba, Nex, Nph and Nat, all four.

    A ``.pcr`` is positional and offers no keyword to resynchronise on, so a
    dropped line does not raise — it silently reinterprets everything after it.
    A dropped background point moves the interpolated background under every
    peak it spans; a dropped atom is a wrong structure factor.
    """
    pcr = _pcr(tmp_path, "counts.pcr", _phase(), _magnetic_isy1())
    model = read_fullprof_pcr(pcr)
    assert len(model.background) == model.control["nba"] == 2
    assert len(model.excluded_regions) == model.control["nex"] == 1
    assert len(model.phases) == model.control["nph"] == 2
    for phase in model.phases:
        assert len(phase.atoms) == int(phase.control["nat"])


def test_a_declared_phase_count_the_file_cannot_satisfy_is_refused(tmp_path):
    """``Nph`` says three, the file holds one — refused naming the file, not
    read as "one phase and some trailing junk"."""
    pcr = _pcr(tmp_path, "shortnph.pcr", _phase(), nph=3)
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(pcr)
    assert "shortnph.pcr" in str(exc.value)


def test_a_declared_atom_count_the_phase_cannot_satisfy_is_refused(tmp_path):
    """``Nat = 5`` over four site pairs walks straight into the profile block."""
    pcr = _pcr(tmp_path, "shortnat.pcr", _phase(nat=5))
    with pytest.raises(FullProfPcrError, match="shortnat.pcr"):
        read_fullprof_pcr(pcr)


@pytest.mark.parametrize("corrupt, expected", [
    ("0.30294  0.30294  0.34087  0.18463   1.0x000", "'occ'"),
    ("0.30294  0.30294  0.34087  0.1x463   1.00000", "'biso'"),
    ("0.30294  0.3x294  0.34087  0.18463   1.00000", "'y'"),
])
def test_an_unreadable_stated_site_value_is_refused_naming_the_column(
        tmp_path, corrupt, expected):
    """Finding 4: a *stated* site value that cannot be read refuses naming
    **which** column it was, not merely the line.

    A ``.pcr`` is positional, so unlike a TOPAS ``.inp`` the reader can never
    silently default the value — the token is always refused — but naming the
    line alone left a reviewer counting tokens to see whether it was ``x``, the
    occupancy or a trailing flag. The rows corrupt O2's ``occ``, ``biso`` and
    ``y`` in turn; the refusal names each, and the absent case (a short codeword
    column, tri-state ``None``) is the pair tested separately above.
    """
    atoms = _CR2WO6_SITES.replace(
        "0.30294  0.30294  0.34087  0.18463   1.00000", corrupt, 1)
    pcr = _pcr(tmp_path, "badval.pcr", _phase(atoms=atoms))
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(pcr)
    message = str(exc.value)
    assert "badval.pcr" in message
    assert expected in message
    assert "is not a number for the" in message


def test_the_magnetic_symmetry_counts_are_asserted(tmp_path):
    """``Nsym``, ``|Ireps|`` and ``3 x N_Bas`` — the three counts that make the
    walk *past* an unmodelled block safe.

    This is the one block the reader has to skip without modelling, and it must
    land on the next phase's first line exactly. ``Isy = -1`` gives Nsym x
    (SYMM + MagMat x MSYM); ``Isy = -2`` gives Nsym x (SYMM + |Ireps| x
    (BASR, BASI)) with 3 x N_Bas numbers on each basis line — two shapes from
    two real files, which is what makes it a rule rather than one file's
    coincidence.
    """
    pcr = _pcr(tmp_path, "magsym.pcr", _phase(), _magnetic_isy1(),
               _magnetic_isy2())
    one, two = read_fullprof_pcr(pcr).magnetic_phases
    assert (one.magnetic.isy, one.magnetic.nsym, one.magnetic.magmat) == (-1, 2, 1)
    assert len(one.magnetic.operators) == 2
    assert one.magnetic.operators[0] == ("SYMM X, Y, Z", ("MSYM  u, v, w,0.000",))
    assert (two.magnetic.isy, two.magnetic.nsym, two.magnetic.ireps,
            two.magnetic.n_bas) == (-2, 2, -2, 4)
    assert two.magnetic.real_imaginary == (0, 0, 0, 0)
    assert len(two.magnetic.operators) == 2
    _, basis = two.magnetic.operators[0]
    assert len(basis) == abs(two.magnetic.ireps)     # |Ireps| BASR/BASI pairs
    for real, imaginary in basis:
        assert len(real) == len(imaginary) == 3 * two.magnetic.n_bas


def test_a_basis_line_shorter_than_three_times_n_bas_is_refused(tmp_path):
    """``N_Bas`` declares four basis vectors and the line states three
    components — the declared count and the written vectors disagree, and
    reading the short line would shift every line after it."""
    short = _ISY_MINUS_2_SYMMETRY.replace(
        "BASR     2     0     0     0     2     0     0    -2     0    -2     0     0",
        "BASR     2     0     0", 1)
    pcr = _pcr(tmp_path, "shortbasr.pcr", _phase(),
               _magnetic_isy2(symmetry=short))
    with pytest.raises(FullProfPcrError, match="3 x N_Bas"):
        read_fullprof_pcr(pcr)


def test_a_basis_line_whose_keyword_is_wrong_is_refused(tmp_path):
    """The ``BASR``/``BASI`` label is the only thing that says which of the real
    and the imaginary part this line is, so it is checked rather than skipped —
    a file with the pair the other way round would otherwise arrive silently
    transposed."""
    swapped = _ISY_MINUS_2_SYMMETRY.replace("BASR     2", "BASX     2", 1)
    pcr = _pcr(tmp_path, "badkw.pcr", _phase(), _magnetic_isy2(symmetry=swapped))
    with pytest.raises(FullProfPcrError, match="expected a BASR line"):
        read_fullprof_pcr(pcr)


# ------------------------------------------------------------------ the traps


def test_the_phase_number_comment_is_not_the_phase_index(tmp_path):
    """Trap 1: ``crwo6002_G5_nc.pcr``'s **third** phase block is labelled
    ``!  Data for PHASE number:   1``.

    So phases are parsed positionally against ``Nph`` and the comment's index is
    kept beside them for provenance only. Keying on it would put a magnetic
    phase's profile parameters onto the nuclear phase of the same number.
    """
    pcr = _pcr(tmp_path, "mislabelled.pcr", _phase(labelled=1),
               _phase(name="Cr2O3", labelled=2), _magnetic_isy2(labelled=1))
    model = read_fullprof_pcr(pcr)
    assert [p.index for p in model.phases] == [1, 2, 3]
    assert [p.labelled_index for p in model.phases] == [1, 2, 1]   # the file lies
    assert model.phases[2].is_magnetic          # and position, not the comment,
    assert not model.phases[0].is_magnetic      # is what got it right


def test_the_ang_mom_column_does_not_move_with_its_name(tmp_path):
    """Trap 2: the third column of a phase's control line is headed ``Ang`` at
    ``Jbt = 0`` and ``Mom`` at ``Jbt = 1``, in the same position.

    A parser keyed on the header text breaks on exactly the phase that matters,
    so nothing here reads a header: the names are this module's own tuple zipped
    positionally. Asserted by giving the *magnetic* phase a non-zero value in
    that column — which is a soft-moment-constraint count, not an angle
    restraint, and must not be refused as one.
    """
    pcr = _pcr(tmp_path, "angmom.pcr", _phase(third_value=0),
               _magnetic_isy1(third_value=1))
    nuclear, magnetic = read_fullprof_pcr(pcr).phases
    assert nuclear.control["ang_or_mom"] == 0.0
    assert magnetic.control["ang_or_mom"] == 1.0
    # The header words in the fixture really do differ, so this is not vacuous.
    written = pcr.read_text(encoding="utf-8")
    assert "!Nat Dis Ang" in written and "!Nat Dis Mom" in written


def test_a_nuclear_phases_angle_restraints_are_refused(tmp_path):
    """The other side of trap 2: the *same* column at ``Jbt = 0`` opens an
    angle-restraint block, whose position no file here establishes."""
    pcr = _pcr(tmp_path, "angles.pcr", _phase(third_value=2))
    with pytest.raises(FullProfPcrError, match="Ang = 2"):
        read_fullprof_pcr(pcr)


def test_the_stale_lambda_slot_is_not_the_wavelength(tmp_path):
    """Trap 3: ``crwo6002_momcomp.pcr`` carries ``2.370100`` in the refinable-λ
    slot while the refinement's λ is the ``2.077100`` of the Lambda1 line.

    Its codeword is ``0.00``, so FullProf never used it — but a reader that took
    λ from the slot because it is the one *labelled* ``Lambda`` would refine
    every cell 14 % out and report a plausible Rwp.
    """
    model = read_fullprof_pcr(_pcr(tmp_path, "lambda.pcr", _phase()))
    assert model.lambda1 == pytest.approx(2.077100)
    assert model.lambda2 == pytest.approx(2.077100)
    assert model.lambda_slot.value == pytest.approx(2.370100)
    assert model.lambda_slot.vary is False       # inert, and said to be


def test_the_declared_refined_parameter_count_is_reported_not_trusted(tmp_path):
    """Trap 4: ``crwo6002_BV2andBV4.pcr`` declares 64 refined parameters and
    carries a codeword for parameter 65.

    Both numbers are reported and neither is corrected into the other, because
    which of the two is wrong is not something the file says. The fixture
    reproduces the disagreement with the real file's own ``651.000`` codeword.
    """
    stale = _phase(cell_codes="  601.00000  601.00000  651.00000    0.00000    0.00000    0.00000")
    model = read_fullprof_pcr(_pcr(tmp_path, "stale.pcr", stale))
    assert model.refined_parameter_count == 61          # what the file declares
    assert max(model.parameter_numbers) == 65           # what it references
    assert {60, 65}.issubset(model.parameter_numbers)


# ------------------------------------ report or refuse, never drop (magnetic)


def test_a_magnetic_phase_is_read_in_full_not_dropped(tmp_path):
    """Four of the six real files have one, so dropping it silently is the
    single most damaging thing this reader could do.

    Both sub-grammars are read: the ``Isy = -1`` moment components and the
    ``Isy = -2`` basis-vector coefficients, under the same positional names
    because they are the same columns.
    """
    pcr = _pcr(tmp_path, "mag.pcr", _phase(), _magnetic_isy1(), _magnetic_isy2())
    model = read_fullprof_pcr(pcr)
    assert [p.name for p in model.nuclear_phases] == ["Cr2wO6"]
    assert [p.name for p in model.magnetic_phases] == ["Cr2wO6", "Magnetic Phase"]
    (moment,) = model.magnetic_phases[0].atoms
    assert moment.species_raw == "MCR3"
    assert moment.values["m2"].value == pytest.approx(3.741)      # Ry
    assert moment.values["m2"].vary is True                       # codeword 11.00
    assert moment.values["m1"].vary is False                      # codeword 0.00
    assert moment.values["magph"].value == pytest.approx(0.0)


def test_two_sublattices_share_one_parameter_with_opposite_signs(tmp_path):
    """``11.00`` and ``-11.00`` on the two Cr sites of
    ``crwo6002_G5_nc.pcr``:169/:173.

    This is the whole argument for decoding the codeword rather than reducing it
    to a bool: the file states *one* refined moment applied with opposite sign to
    the two sublattices, and "both were refined" is a different — and wrong —
    model with two free parameters.
    """
    pcr = _pcr(tmp_path, "afm.pcr", _phase(), _magnetic_isy2())
    up, down = read_fullprof_pcr(pcr).magnetic_phases[0].atoms
    assert (up.label, down.label) == ("1CR", "2CR")
    assert up.values["m2"].code.number == down.values["m2"].code.number == 1
    assert up.values["m2"].code.multiplier == 1.0
    assert down.values["m2"].code.multiplier == -1.0
    assert up.values["m2"].value == pytest.approx(0.800)
    assert down.values["m2"].value == pytest.approx(-0.800)


def test_to_structure_refuses_a_magnetic_phase_naming_it(tmp_path):
    """rietx has no magnetic scattering model, so returning the nuclear phases
    alone would hand back a structure that looks complete while the file's
    magnetic contribution went unmentioned — the TOPAS reader's
    ``mag_space_group`` case, one format over.

    The refusal is at *build* time, not at read: refusing to read would throw
    away the nuclear phases, the wavelength and the agreement factors this
    reader got right, and make four of six real files unreadable.
    """
    pcr = _pcr(tmp_path, "refuse.pcr", _phase(), _magnetic_isy1())
    model = read_fullprof_pcr(pcr)
    with pytest.raises(FullProfPcrError) as exc:
        to_structure(model)
    message = str(exc.value)
    assert "refuse.pcr" in message
    assert "1 of 2 phases are magnetic" in message
    assert "Cr2wO6" in message and "Isy -1" in message
    assert "nuclear_only=True" in message       # the refusal names the way out


def test_nuclear_only_makes_the_omission_the_callers(tmp_path):
    """The third state of the "report or refuse, never drop" rule: a drop the
    *caller* declared. The magnetic phase is still on the model, so the omission
    stays inspectable rather than becoming invisible."""
    pcr = _pcr(tmp_path, "nuclearonly.pcr", _phase(), _magnetic_isy1())
    model = read_fullprof_pcr(pcr)
    structure = to_structure(model, nuclear_only=True)
    assert [p.name for p in structure.phases] == ["Cr2wO6"]
    assert len(model.magnetic_phases) == 1      # not lost, just not built


def test_a_file_of_nothing_but_magnetic_phases_refuses_either_way(tmp_path):
    """``nuclear_only=True`` on a file with no nuclear phase must not return an
    empty structure or a pydantic error — a reader raises naming the file."""
    pcr = _pcr(tmp_path, "allmag.pcr", _magnetic_isy1())
    model = read_fullprof_pcr(pcr)
    with pytest.raises(FullProfPcrError, match="no nuclear phase to build"):
        to_structure(model, nuclear_only=True)


@pytest.mark.parametrize("magnetic, block, expected, declared", [
    # crwo6002_momcomp_softconstrained.pcr:176-177 — keyed by `CR`, and that
    # file's magnetic phase (Isy -1) has exactly one atom, labelled `CR`.
    (_magnetic_isy1, "! Soft moment constraints:\nCR   2.900 0.02000\n",
     [("CR", 2.900, 0.02)], 1),
    # crwo6002_G5_nc.pcr:189-191 — keyed by `1C`/`2C`, and that file's magnetic
    # phase (Isy -2) has two atoms, labelled `1CR` and `2CR`. One production,
    # not two: both keys are the label truncated to the field's width.
    (_magnetic_isy2, "! Soft moment constraints\n1C  2.90 0.02\n2C  2.90 0.02\n",
     [("1C", 2.90, 0.02), ("2C", 2.90, 0.02)], 1),
])
def test_soft_moment_constraints_read_in_both_spellings(
        tmp_path, magnetic, block, expected, declared):
    """Both real spellings, and the key resolved to a site by **prefix**.

    Reading the second as a *site index* also fits those two lines and would
    then read ``CR`` as a label — two productions where one explains both. The
    prefix reading is recorded, the raw key kept beside it, and the declared
    ``Mom`` is reported rather than enforced: ``crwo6002_G5_nc.pcr`` declares
    ``Mom = 1`` and writes **two** constraints, and which of the two numbers is
    wrong is not something the file says.
    """
    pcr = _pcr(tmp_path, "soft.pcr", _phase(),
               magnetic(third_value=declared), trailing=block + _RANGE)
    phase = read_fullprof_pcr(pcr).phases[-1]
    got = [(c.key, c.moment, c.sigma) for c in phase.soft_moment_constraints]
    assert got == pytest.approx(expected)
    labels = [phase.atoms[c.atom_index].label if c.atom_index is not None else None
              for c in phase.soft_moment_constraints]
    assert all(label is not None for label in labels)
    assert all(label.startswith(c.key)
               for label, c in zip(labels, phase.soft_moment_constraints))
    # Reported, not corrected: the declaration and the count are both readable.
    assert int(phase.control["ang_or_mom"]) == declared
    assert len(phase.soft_moment_constraints) == len(expected)


def test_the_propagation_vectors_are_read(tmp_path):
    """``Nvk`` k-vectors, each a value line and a codeword line, after the
    phase's Pref/Asy block.

    Quoted from ``300q-1p5K_1.pcr``:129-131, which is the **only** file that
    evidences the position — and whose phase happens to be the last, so the
    position rests on one observation and the reader's docstring says so. Note
    the trailing words: FullProf writes ``Propagation Vector  1`` after the
    numbers with no comment marker, so the line is read as a leading numeric run.
    """
    block = ("! Propagation vectors: \n"
             "   0.5000000   0.0000000   0.5000000          Propagation Vector  1\n"
             "    0.000000    0.000000    0.000000")
    pcr = _pcr(tmp_path, "kvec.pcr", _phase(),
               _magnetic_isy1(nvk=1) + "\n" + block)
    (k, codes), = read_fullprof_pcr(pcr).phases[-1].propagation_vectors
    assert k == pytest.approx((0.5, 0.0, 0.5))
    assert [c.vary for c in codes] == [False, False, False]


# --------------------------------------------------------- refused, by name


def test_a_tof_job_is_refused_naming_the_job_and_why(tmp_path):
    """``Job = -1``: the abscissa is microseconds and the whole profile block is
    Sig-2/Sig-1/Sig-0 and alpha0/beta0/alpha1 in place of Caglioti U/V/W.

    rietx models constant-wavelength diffraction only, so this is refused where
    it is declared rather than read into a model whose numbers mean something
    else. (``yag_xpress_072_new.pcr`` is the real one; it is additionally
    NPATT 6 and is refused a line earlier.)
    """
    pcr = _pcr(tmp_path, "tof.pcr", _phase(), job=-1)
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(pcr)
    assert "tof.pcr" in str(exc.value)
    assert "Job = -1" in str(exc.value)
    assert "time-of-flight" in str(exc.value)


def test_a_multi_pattern_file_is_refused_naming_the_pattern_count(tmp_path):
    """``yag_xpress_072_new.pcr``:3 — ``NPATT 6``, six GEM detector banks.

    A different layout throughout: per-pattern control lines (which shed ``Nph``,
    it moving to a line of its own — the ``!Job Npr Nba Nex`` header variant),
    per-pattern backgrounds, excluded regions and profile blocks, one shared set
    of atoms. Six patterns is a *joint* refinement over six banks, and which
    bank's resolution function a single ``Instrument`` should carry is a question
    the file does not answer. Refused before any of it is parsed.
    """
    path = tmp_path / "npatt.pcr"
    path.write_text(
        "COMM  YAG express cycle 072\n"
        "! Current global Chi2 (Bragg contrib.) =      11.28\n"
        "NPATT      6       1 1 1 1 1 1 <- Flags for patterns (1:refined, 0: excluded)\n"
        "W_PAT   0.167 0.167 0.167 0.167 0.167 0.167\n"
        "!Nph Dum Ias Nre Cry Opt Aut\n   1   1   1   0   0   0   1\n"
        "!Job Npr Nba Nex Nsc Nor Iwg Ilo Res Ste Uni Cor Anm\n"
        "  -1  13   0   2   0   1   0   0   5   0   1   0   0\n", encoding="utf-8")
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(path)
    assert "npatt.pcr" in str(exc.value)
    assert "NPATT 6" in str(exc.value)
    assert "6 patterns" in str(exc.value)


@pytest.mark.parametrize("nba, why", [
    # yag_xpress_072_new.pcr has Nba 0 and writes six polynomial coefficients
    # per pattern — but only in the multi-pattern layout, so where the
    # coefficient line sits in a *single*-pattern file is unevidenced.
    (0, "a polynomial background"),
    (1, "one interpolated point"),
    (-3, "a background model with no description here"),
])
def test_a_background_this_reader_cannot_place_is_refused(tmp_path, nba, why):
    pcr = _pcr(tmp_path, "bkg.pcr", _phase())
    text = pcr.read_text(encoding="utf-8").replace("   1   7   1   2   1",
                                   f"   1   7   1   {nba}   1")
    pcr.write_text(text, encoding="utf-8")
    with pytest.raises(FullProfPcrError, match=f"Nba = {nba}"):
        read_fullprof_pcr(pcr), why


@pytest.mark.parametrize("field, position", [
    # The control line's 19 fields, by position:
    # Job Npr Nph Nba Nex Nsc Nor Dum Iwg Ilo Ias Res Ste Nre Cry Uni Cor Opt Aut
    ("Nsc", 5), ("Nor", 6), ("Dum", 7), ("Res", 11), ("Ste", 12), ("Nre", 13),
    ("Cry", 14), ("Uni", 15), ("Cor", 16), ("Opt", 17),
])
def test_a_layout_changing_control_flag_is_refused_by_name(
        tmp_path, field, position):
    """Every control-line flag whose non-zero meaning adds lines this reader has
    no file to place — or, for ``Uni``, changes what the abscissa *is*.

    Ignoring such a flag is not the safe option: a flag that adds a line
    desynchronises the whole positional walk, and ``Uni`` non-zero would read a
    non-2θ abscissa as 2θ, which `io/CLAUDE.md`'s "the axis is never trusted"
    forbids outright. ``Iwg``, ``Ilo``, ``Ias``, ``Npr`` and ``Aut`` are
    deliberately *not* in this list — they change weighting, the profile function
    or FullProf's own parameter numbering, and move no line.
    ``300q-1p5K_1.pcr`` has ``Aut 1`` and must still read.
    """
    pcr = _pcr(tmp_path, "flag.pcr", _phase())
    lines = pcr.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if line.startswith("   1   7   1   2   1"):
            fields = line.split()
            fields[position] = "3"
            lines[i] = "   " + "   ".join(fields)
            break
    pcr.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(pcr)
    assert f"{field} = 3" in str(exc.value)
    assert "flag.pcr" in str(exc.value)


def test_a_control_line_of_the_wrong_width_is_refused(tmp_path):
    """An eighteen-field (pre-``Aut``) control line would shift every field
    after whichever one is missing, and nothing in the corpus says which."""
    pcr = _pcr(tmp_path, "narrow.pcr", _phase())
    text = pcr.read_text(encoding="utf-8").replace(
        "   1   7   1   2   1   0   0   0   0   0   0   0   0   0   0   0   0   0   0",
        "   1   7   1   2   1   0   0   0   0   0   0   0   0   0   0   0   0   0")
    pcr.write_text(text, encoding="utf-8")
    with pytest.raises(FullProfPcrError, match="expected 19 fields"):
        read_fullprof_pcr(pcr)


@pytest.mark.parametrize("jbt", [2, 10, -1, -3])
def test_an_unknown_jbt_is_refused_naming_it(tmp_path, jbt):
    """Only ``Jbt`` 0 (nuclear) and 1 (magnetic) are evidenced. The others select
    Le Bail intensity extraction, a combined nuclear+magnetic phase or a
    form-factor phase, each of which changes the *atom block's* own layout."""
    pcr = _pcr(tmp_path, "jbt.pcr", _phase(jbt=jbt))
    with pytest.raises(FullProfPcrError, match=f"Jbt = {jbt}"):
        read_fullprof_pcr(pcr)


def test_a_nuclear_phase_with_explicit_symmetry_is_refused(tmp_path):
    """``Isy != 0`` at ``Jbt = 0`` supplies the operators instead of deriving
    them from the symbol — a block no file here states the shape of."""
    pcr = _pcr(tmp_path, "isy.pcr", _phase(isy=1))
    with pytest.raises(FullProfPcrError, match="Isy = 1"):
        read_fullprof_pcr(pcr)


def test_a_magnetic_phase_with_an_unknown_isy_is_refused(tmp_path):
    """``Isy`` selects the whole magnetic sub-grammar, so an unrecognised value
    means the reader does not know how many lines the block occupies."""
    pcr = _pcr(tmp_path, "isy3.pcr", _phase(),
               _magnetic_isy1(isy=-3))
    with pytest.raises(FullProfPcrError, match="Isy = -3"):
        read_fullprof_pcr(pcr)


def test_a_positive_ireps_is_refused(tmp_path):
    """A positive ``Ireps`` names an irreducible representation from FullProf's
    own tables, which this reader has no copy of and — per ATTRIBUTION.md's
    fence, FullProf being closed — may not reproduce."""
    tabulated = _ISY_MINUS_2_SYMMETRY.replace("    -2     4", "     2     4", 1)
    pcr = _pcr(tmp_path, "ireps.pcr", _phase(),
               _magnetic_isy2(symmetry=tabulated))
    with pytest.raises(FullProfPcrError, match="Ireps = 2"):
        read_fullprof_pcr(pcr)


@pytest.mark.parametrize("field, value", [
    ("Dis", 2), ("Str", 1), ("Furth", 3), ("More", 1),
])
def test_a_phase_flag_that_adds_unevidenced_lines_is_refused(
        tmp_path, field, value):
    """Distance restraints, a strain-model block, further parameters, additional
    per-phase lines. Every one is zero in every corpus file, so where its block
    sits is a guess — and a wrong guess desynchronises the rest of the file."""
    pcr = _pcr(tmp_path, "phaseflag.pcr",
               _phase(**{{"Dis": "dis", "Str": "strn", "Furth": "furth",
                          "More": "more"}[field]: value}))
    with pytest.raises(FullProfPcrError, match=f"{field} = {value}"):
        read_fullprof_pcr(pcr)


def test_a_phase_reading_its_reflections_from_a_file_is_refused(tmp_path):
    """``Irf`` 1 or 2 reads the hkl list from a companion file, so the model this
    reader would return is not the model that was refined. ``Irf`` 0 and -1 are
    both in the corpus and both read."""
    pcr = _pcr(tmp_path, "irf.pcr", _phase(irf=2))
    with pytest.raises(FullProfPcrError, match="Irf = 2"):
        read_fullprof_pcr(pcr)


def test_an_unknown_n_t_is_refused_naming_the_atom(tmp_path):
    """``N_t`` decides how many lines a site occupies — 0 adds none, 2 adds an
    anisotropic β line and its codewords (``yag_xpress_072_new.pcr``:187-190).
    Anything else and the reader does not know where the next atom starts."""
    odd = _CR2WO6_SITES.replace("   0   0   0    1  #color cyan",
                                "   0   0   5    1  #color cyan", 1)
    pcr = _pcr(tmp_path, "nt.pcr", _phase(atoms=odd))
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(pcr)
    assert "N_t = 5" in str(exc.value) and "'Cr'" in str(exc.value)


def test_a_missing_file_raises_naming_it(tmp_path):
    with pytest.raises(FullProfPcrError, match="absent.pcr"):
        read_fullprof_pcr(tmp_path / "absent.pcr")


def test_a_file_that_does_not_open_with_comm_is_refused(tmp_path):
    """A ``.pcr`` opens with ``COMM``. Anything else is either not a FullProf
    control file or has had its header edited away, and reading on would
    interpret whatever line happened to be first as the control line."""
    path = tmp_path / "notpcr.pcr"
    path.write_text("data_something\n_cell_length_a 4.58\n", encoding="utf-8")
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(path)
    assert "notpcr.pcr" in str(exc.value) and "COMM" in str(exc.value)


@pytest.mark.parametrize("codec", ["utf-8", "utf-8-sig", "utf-16"])
def test_a_byte_order_mark_is_decoded_not_read_as_utf8(tmp_path, codec):
    """`io.formats.base.decode` is the seam `head()` already answers this with,
    shared rather than duplicated — the same choice ``projects/topas.py`` made.
    A UTF-16 export read as UTF-8 gives a first line that is not ``COMM`` and
    would be diagnosed as "not a FullProf file", a confident wrong diagnosis of
    a *decode* failure."""
    source = _pcr(tmp_path, "src.pcr", _phase()).read_text(encoding="utf-8")
    path = tmp_path / f"enc-{codec}.pcr"
    path.write_bytes(source.encode(codec))
    model = read_fullprof_pcr(path)
    assert model.title == "60 K"
    assert model.chi2 == pytest.approx(5.144)
    assert model.phases[0].cell["a"].value == pytest.approx(4.580088)


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"])
def test_a_utf16_file_with_no_mark_is_refused_naming_the_file(tmp_path, codec):
    """`io/CLAUDE.md`'s `xy` row: ASCII-range UTF-16LE is valid UTF-8 with
    interleaved NULs and no byte-order mark says which of LE and BE it is, so
    guessing is a repair a reader cannot say it made."""
    source = _pcr(tmp_path, "src2.pcr", _phase()).read_text(encoding="utf-8")
    path = tmp_path / f"{codec}.pcr"
    path.write_bytes(source.encode(codec))
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(path)
    assert f"{codec}.pcr" in str(exc.value)


def test_a_trailing_line_that_is_neither_production_is_refused(tmp_path):
    """After the last phase come soft moment constraints and the fitted 2θ
    range, told apart by whether the line opens with a number. Something that is
    neither is refused rather than absorbed into whichever it resembles."""
    pcr = _pcr(tmp_path, "junk.pcr", _phase(),
               trailing="SOMETHING ELSE\n" + _RANGE)
    with pytest.raises(FullProfPcrError, match="junk.pcr"):
        read_fullprof_pcr(pcr)


# ------------------------------------------------- to_structure


def test_to_structure_builds_and_carries_the_refine_flags(tmp_path):
    """``Biso`` is FullProf's B and rietx's ``biso`` is also B — no 8π².

    The refine flags are the payload: a control file says which parameters were
    free and which were held, and that is the part a person cannot reconstruct
    from a CIF plus a pattern. Here the cell's a and c were refined (codewords
    51/61) and every coordinate and displacement parameter held (0.00) — which
    is what the ``crwo6002_momcomp.pcr`` refinement actually did.
    """
    pcr = _pcr(tmp_path, "build.pcr", _phase())
    (phase,) = to_structure(read_fullprof_pcr(pcr)).phases
    assert phase.name == "Cr2wO6"
    assert phase.space_group == "P 42/m n m"
    assert phase.cell.a.value == pytest.approx(4.580088)
    assert phase.cell.c.value == pytest.approx(8.847341)
    assert phase.cell.a.vary is True and phase.cell.c.vary is True
    assert phase.cell.alpha.vary is False
    assert [a.label for a in phase.atoms] == ["Cr", "W", "O1", "O2"]
    assert [a.species for a in phase.atoms] == ["Cr", "W", "O", "O"]
    assert phase.atoms[3].z.value == pytest.approx(0.34087)
    assert phase.atoms[0].biso.value == pytest.approx(0.21358)
    assert phase.atoms[0].biso.vary is False
    assert phase.scale.value == pytest.approx(6.4296)
    assert phase.scale.vary is True                    # codeword 71.00000


def test_to_structure_reports_a_species_rewrite_through_diagnostics(
        tmp_path):
    """The one repair that reaches the ``Structure`` is the species spelling.

    ``read_fullprof_pcr`` reports it *structurally* — ``species_raw`` (``CR``)
    sits beside ``species`` (``Cr``) on the atom — but the ``Structure`` carries
    only the one spelling, so the raw token is dropped at the build. io/CLAUDE.md
    (a reader repairs only where it can say it did) is honoured by the same
    channel ``structure_from_cif`` uses: pass ``diagnostics=`` a list and the
    rewrite is recorded, one ``FULLPROF_SPECIES_NORMALISED`` per distinct token,
    with the affected atom path — and a clean spelling records nothing, which is
    why W/O₁/O₂ leave no diagnostic though they too pass through the normaliser.
    """
    model = read_fullprof_pcr(_pcr(tmp_path, "diag.pcr", _phase()))
    diagnostics = []
    structure = to_structure(model, diagnostics=diagnostics)
    assert [d.code for d in diagnostics] == ["FULLPROF_SPECIES_NORMALISED"]
    (recorded,) = diagnostics
    assert recorded.level == "info"
    assert recorded.where == ["phases.0.atoms.0.species"]
    assert "'CR'" in recorded.message and "'Cr'" in recorded.message
    assert structure.phases[0].atoms[0].species == "Cr"
    # No list is the same build, and it is silent — the repair is opt-in to see,
    # never suppressed for correctness.
    assert to_structure(model).phases[0].atoms[0].species == "Cr"


def test_a_refined_coordinate_reaches_the_structure_as_refined(tmp_path):
    """``crwo6002_BV2andBV4.pcr``:88-95 refines Cr's z, O1's x/y and O2's x/y/z
    (codewords 551, 561, 571, 581) and holds W's — which is what makes this a
    tri-state test rather than a value test."""
    refined = (
        "Cr     CR      0.00000  0.00000  0.33449  0.08537   0.50000   0   0   0    1\n"
        "                  0.00     0.00   551.00   591.00      0.00\n"
        "W      W       0.00000  0.00000  0.00000  0.22402   0.25000   0   0   0    1\n"
        "                  0.00     0.00     0.00     0.00      0.00\n"
        "O1     O       0.29771  0.29771  0.00000  0.24694   0.50000   0   0   0    1\n"
        "                561.00   561.00     0.00     0.00      0.00\n"
        "O2     O       0.30498  0.30498  0.33853  0.23070   1.00000   0   0   0    1\n"
        "                571.00   571.00   581.00   621.00      0.00")
    pcr = _pcr(tmp_path, "flags.pcr", _phase(atoms=refined))
    cr, w, o1, o2 = to_structure(read_fullprof_pcr(pcr)).phases[0].atoms
    assert (cr.z.vary, cr.biso.vary) == (True, True)
    assert (w.z.vary, w.biso.vary) == (False, False)
    assert (o1.x.vary, o1.y.vary, o1.z.vary) == (True, True, False)
    assert (o2.x.vary, o2.z.vary, o2.biso.vary) == (True, True, True)


def test_the_built_structure_compiles_a_parameter_table(tmp_path):
    """Not just "pydantic accepted it": the structure has to reach a
    :class:`~rietx.params.vector.ParameterTable`, which is where every
    crystallography refusal lives (species, cell ties, site-symmetry DOFs).

    This is the "compile every structure returned" half of the TOPAS reader's
    review, and it is what checks that the ``.pcr``'s own codeword tie and
    rietx's *derived* symmetry tie agree: ``a`` and ``c`` come back free and
    ``b`` does not, because ``b`` is tied to ``a`` for P 4₂/mnm — the file said
    the same thing with ``51.00000`` twice, and neither was told the other.
    """
    import rietx as rx
    from rietx.params.vector import ParameterTable

    model = read_fullprof_pcr(_pcr(tmp_path, "table.pcr", _phase()))
    structure = to_structure(model)
    table = ParameterTable(
        structure, rx.Instrument.constant_wavelength_neutron(model.lambda1))
    free = {p for p in table.free_paths if p.startswith("phases")}
    assert free == {"phases.0.cell.a", "phases.0.cell.c", "phases.0.scale"}


def test_the_occupancy_column_reduces_to_a_common_factor(tmp_path):
    """FullProf's ``Occ`` is multiplicity-scaled and its absolute normalisation
    is degenerate with the phase scale, so what is recoverable is the *ratio*
    between sites.

    Measured on the real files: ``Occ x M_general / M_site`` is **2.0** for every
    site of both Cr₂WO₆ files' phases and **1.0** for Co₃O₄ and YAG. Two files,
    two factors, same convention — which is the evidence that the factor is
    arbitrary and that constancy is the only thing a reader may conclude from it.
    """
    model = read_fullprof_pcr(_pcr(tmp_path, "occ.pcr", _phase()))
    assert occupancy_factor(model.phases[0]) == pytest.approx(2.0, rel=1e-4)
    # Fully occupied, so every rietx occ is 1.0 — the arbitrary factor cancels
    # and none of it leaks into the structure factor.
    atoms = to_structure(model).phases[0].atoms
    assert [a.occ.value for a in atoms] == pytest.approx([1.0] * 4)


def test_an_occupancy_that_does_not_reduce_is_refused_naming_the_ratios(tmp_path):
    """A partially occupied site's chemical occupancy is **not in the file** —
    it is inseparable from the arbitrary common factor — so it is refused.

    Handing FullProf's ``Occ`` straight into rietx's ``occ`` would be a silently
    wrong structure factor, which is the failure class this module exists to
    avoid. The same check is what verifies the origin choice
    :func:`normalize_space_group` picks: a wrong origin gives wrong
    multiplicities, the ratios stop agreeing, and the phase is refused rather
    than returned.
    """
    partial = _CR2WO6_SITES.replace("0.33312  0.21358   0.50000",
                                    "0.33312  0.21358   0.35000", 1)
    model = read_fullprof_pcr(_pcr(tmp_path, "partial.pcr",
                                   _phase(atoms=partial)))
    with pytest.raises(FullProfPcrError) as exc:
        to_structure(model)
    message = str(exc.value)
    assert "partial.pcr" in message
    assert "does not reduce" in message
    assert "Cr=1.4000" in message and "W=2.0000" in message


def test_a_phase_with_no_sites_is_refused_rather_than_dropped(tmp_path):
    """``Nat = 0`` is legal in a ``.pcr`` — a phase whose reflections come from a
    companion file, or one being set up — and it has no structure factor.

    Refused rather than skipped, because ``model.phases`` would go on carrying
    its R_Bragg: the TOPAS reader's "report or refuse, never drop" case, where
    the QPA numbers looked complete with a phase missing from the ``Structure``.
    """
    model = read_fullprof_pcr(_pcr(tmp_path, "empty.pcr",
                                   _phase(nat=0, atoms="")))
    assert model.phases[0].atoms == []
    with pytest.raises(FullProfPcrError, match="Nat = 0"):
        to_structure(model)


def test_a_negative_biso_is_refused_naming_the_atom(tmp_path):
    """``300q-1p5K_1.pcr``:70 refined O1 to Biso = −0.67266 Å², a real FullProf
    outcome — the column absorbs absorption and normalisation error.

    rietx bounds ``biso`` at zero, and clamping −0.67 to 0 changes every high-Q
    intensity: a *contradiction* between the file and the model, not the kind of
    small deviation root CLAUDE.md licenses a reader to repair silently. So it is
    refused, and the file's own number stays readable on the model.
    """
    negative = _CR2WO6_SITES.replace("0.33312  0.21358", "0.33312 -0.67266", 1)
    model = read_fullprof_pcr(_pcr(tmp_path, "negb.pcr",
                                   _phase(atoms=negative)))
    assert model.phases[0].atoms[0].values["biso"].value == pytest.approx(-0.67266)
    with pytest.raises(FullProfPcrError) as exc:
        to_structure(model)
    assert "negb.pcr" in str(exc.value)
    assert "'Cr'" in str(exc.value) and "-0.67266" in str(exc.value)


def test_an_anisotropic_beta_block_is_read_and_refused(tmp_path):
    """``N_t = 2`` adds a β line and its codewords
    (``yag_xpress_072_new.pcr``:187-190), which is read — so the line accounting
    stays exact — and refused at build.

    Converting FullProf's β_ij to rietx's U^ij needs a convention no file here
    settles: whether the stored off-diagonal already carries the exponent's
    factor of 2. A wrong factor is a silently wrong Debye-Waller factor at high
    Q, so the numbers are reported and the phase is not built.
    """
    aniso = (
        "Y    Y       0.12500  0.00000  0.25000  0.00000   0.25000   0   0   2    0\n"
        "                0.00     0.00     0.00     0.00      0.00\n"
        "    0.00024  0.00048  0.00048  0.00000  0.00000   0.00016\n"
        "     411.00   421.00   421.00     0.00     0.00    431.00")
    model = read_fullprof_pcr(_pcr(tmp_path, "aniso.pcr",
                                   _phase(nat=1, sg="I A -3 D", atoms=aniso)))
    atom = model.phases[0].atoms[0]
    assert atom.n_t == 2
    assert atom.betas["beta11"].value == pytest.approx(0.00024)
    assert atom.betas["beta23"].vary is True             # codeword 431.00
    assert atom.betas["beta12"].vary is False
    with pytest.raises(FullProfPcrError) as exc:
        to_structure(model)
    assert "aniso.pcr" in str(exc.value) and "beta" in str(exc.value)


def test_the_converged_agreement_factors_are_recovered(tmp_path):
    """The reason the format is worth reading: it carries a *validated* answer.

    FullProf rewrites the χ² and per-phase R_Bragg comments on every cycle, so
    they are the converged numbers and not a seed. The values are
    ``crwo6002_momcomp.pcr``'s own: χ² 5.144, R_Bragg 1.79 / 41.28 / 9.46 — and
    the 41.28 is worth keeping visible, because a reader that reported only χ²
    would make that phase look fitted.
    """
    pcr = _pcr(tmp_path, "fom.pcr", _phase(labelled=1, r_bragg="1.79"),
               _phase(name="Cr2O3", nat=2, labelled=2, r_bragg="41.28",
                      sg="R -3 c",
                      atoms="Cr     CR      0.00000  0.00000  0.29899  0.21358   0.66667   0   0   0    1\n"
                            "                  0.00     0.00     0.00     0.00      0.00\n"
                            "O1     O       0.27011  0.00000  0.25000  0.25592   1.00000   0   0   0    1\n"
                            "                  0.00     0.00     0.00     0.00      0.00",
                      cell="   4.954182   4.954182  13.421314  90.000000  90.000000 120.000000",
                      cell_codes="    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000",
                      scale=" 0.13355E-01", scale_code="  0.00000"),
               _magnetic_isy1(labelled=3, r_bragg="9.46"))
    model = read_fullprof_pcr(pcr)
    assert model.chi2 == pytest.approx(5.144)
    assert [p.r_bragg for p in model.phases] == pytest.approx([1.79, 41.28, 9.46])
    # `0.13355E-01` — Fortran exponent notation, on a real scale line.
    assert model.phases[1].profile["scale"].value == pytest.approx(0.013355)
    assert model.phases[1].cell["gamma"].value == pytest.approx(120.0)


def test_the_data_file_reference_is_reported_not_chased(tmp_path):
    """``300q-1p5K_1.pcr``:3 names ``RT-1_5K_1.dat`` while the pattern beside it
    on disk is ``300q-1p5K_1.dat``, and ``crwo6002_G5_nc.pcr``:3 names another
    refinement's ``.pcr``.

    So the reference is recorded and never resolved: a reader that went looking
    would either fail on a file that is not missing or find the wrong one, and
    inventing a filename is not a repair it could say it made.
    """
    pcr = _pcr(tmp_path, "ref.pcr", _phase())
    model = read_fullprof_pcr(pcr)
    assert model.data_file == "CrWO6002.dat"
    assert model.pcr_name == "crwo6002_momcomp"
    assert not (tmp_path / "CrWO6002.dat").exists()   # and nothing went looking


def test_the_excluded_regions_and_fitted_range_are_read(tmp_path):
    """Protocol, not data: root CLAUDE.md's rule is that excluded regions live in
    the document because they are in neither the pattern file nor the model
    state. A ``.pcr`` is where a FullProf refinement records them, so mirroring
    its protocol means reading both the excluded list and the range that was
    actually fitted (``crwo6002_momcomp.pcr``:70-71 and :177)."""
    model = read_fullprof_pcr(_pcr(tmp_path, "excl.pcr", _phase()))
    assert model.excluded_regions == [(0.0, 9.0)]
    assert model.fitted_range == (9.0, 157.0, 1.0)


def test_the_background_points_carry_their_codewords_inline(tmp_path):
    """Where the codeword sits is not uniform, and both spellings are real: the
    atom, profile and cell blocks put it on the *following* line, the background
    points and the zero-shift line carry it as the next column."""
    model = read_fullprof_pcr(_pcr(tmp_path, "bkgin.pcr", _phase()))
    assert [pos for pos, _ in model.background] == pytest.approx([12.9, 16.4])
    assert [v.value for _, v in model.background] == pytest.approx(
        [952.8345, 977.2739])
    assert [v.code.number for _, v in model.background] == [9, 10]
    assert model.zero_shift["zero"].value == pytest.approx(-0.03994)
    assert model.zero_shift["zero"].code.number == 60
    assert model.zero_shift["sycos"].vary is False


# ---------------------------------------------------------- the robustness pin


def test_a_truncated_pcr_never_escapes_as_anything_but_a_fullprof_error(tmp_path):
    """`io/CLAUDE.md`'s refusal rule, pinned: a reader raises
    :class:`FullProfPcrError` naming the file, never its parser's exception.

    A positional format makes this the *likeliest* place to lose the rule: a cut
    through a codeword line, a basis-vector line or an atom's trailing integers
    is exactly where a bare ``ValueError`` or an ``IndexError`` gets out, and a
    ragged cut through a number leaves a token like ``0.3`` that parses fine and
    a count that does not. Bounded to ~200 offsets on purpose — the same sweep at
    every byte offset also passes, and it is not a test anyone should wait for.
    """
    raw = _pcr(tmp_path, "whole.pcr", _phase(), _magnetic_isy1(),
               _magnetic_isy2()).read_bytes()
    target = tmp_path / "cut.pcr"
    offsets = sorted({round(i * len(raw) / 199) for i in range(200)})
    for n in offsets:
        target.write_bytes(raw[:n])
        try:
            model = read_fullprof_pcr(target)
            to_structure(model, nuclear_only=True)
        except FullProfPcrError:
            pass
        except Exception as exc:            # noqa: BLE001 — the point of the test
            raise AssertionError(
                f"truncation at {n} of {len(raw)} bytes escaped as "
                f"{type(exc).__name__}: {exc}") from exc


# ----------------------------------------------- the review round: six findings
#
# One section per finding of the PR #111 review, each pinning a divergence
# between what this module's own docstring claims and what its code did. The
# fixtures reuse the quoted lines above; where a finding needs a shape no corpus
# file has, the comment says so rather than implying a real file was seen.


def _rewrite_trailing_selector(text: str, header: str, value: str) -> str:
    """Rewrite the trailing model selector on the data line after ``header``.

    Edits a *quoted* line rather than inventing one: the Strain-Model and
    Size-Model selectors are the last token of ``crwo6002_momcomp.pcr``:98 and
    :101, and only that token is replaced.
    """
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if header in line:
            tokens = lines[i + 1].split()
            tokens[-1] = value
            lines[i + 1] = "  " + "  ".join(tokens)
            return "\n".join(lines)
    raise AssertionError(f"no {header!r} line in the fixture")


# Finding 1 — the tri-state must not collapse into False.
#
# `crwo6002_momcomp.pcr`:88-89 with its codeword line cut from five columns to
# three. FullProf always writes the slot, so this shape is a *damaged* file, not
# one that says "held" — which is the whole distinction `Value.vary is None`
# exists to keep, and the module docstring's "never collapses an absent column
# into False".
_RAGGED_CODEWORD_SITES = """\
Cr     CR      0.00000  0.00000  0.33312  0.21358   0.50000   0   0   0    1
                  0.00     0.00     0.00
W      W       0.00000  0.00000  0.00000  0.22402   0.25000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00
O1     O       0.30156  0.30156  0.00000  0.24694   0.50000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00
O2     O       0.30294  0.30294  0.34087  0.18463   1.00000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00"""


def test_an_absent_codeword_column_is_refused_not_read_as_held(tmp_path):
    """A ragged codeword line is refused at build, never defaulted to vary=False.

    The reader's own tri-state says ``None`` means "the codeword column is not
    there at all". ``to_structure`` cannot know the protocol for such a value,
    and skipping the ``vary`` kwarg let ``rx.Parameter``'s schema default supply
    ``False`` — making a parameter the file said nothing about indistinguishable
    from one it genuinely fixed. That is WP-1076's collapse one file over.
    """
    pcr = _pcr(tmp_path, "ragged.pcr", _phase(atoms=_RAGGED_CODEWORD_SITES))
    model = read_fullprof_pcr(pcr)
    # The *reader* still reports the absence faithfully — it is only the build
    # that cannot proceed on it.
    assert model.phases[0].atoms[0].values["biso"].vary is None
    assert model.phases[0].atoms[1].values["biso"].vary is False
    with pytest.raises(FullProfPcrError) as excinfo:
        to_structure(model)
    message = str(excinfo.value)
    assert "'Cr'" in message and "Biso" in message
    assert "ragged or truncated" in message
    assert "vary=False" in message


def test_an_absent_cell_codeword_column_is_refused_naming_the_column(tmp_path):
    """The same refusal on the cell line, which names *which* of the six."""
    pcr = _pcr(tmp_path, "ragged_cell.pcr",
               _phase(cell_codes="   51.00000   51.00000   61.00000"))
    with pytest.raises(FullProfPcrError, match=r"cell's alpha"):
        to_structure(read_fullprof_pcr(pcr))


# Finding 2 — a schema refusal must be converted at the same boundary.


def test_a_schema_refusal_on_an_atom_is_converted_naming_the_file(tmp_path):
    """``rx.Cell`` and the atoms are built *inside* the conversion ``try``.

    They were built above it, so a pydantic ``ValidationError`` escaped raw —
    naming a field but not the file — contradicting the adjacent comment "every
    schema refusal is converted at this boundary" and reaching any caller that
    catches only the documented error type.

    ``biso`` is the reachable case: ``to_structure`` bounds it at ``max=25.0``,
    so a Biso above that is refused by ``rx.Parameter`` itself. A *negative*
    Biso does not exercise this — it has its own explicit refusal further up.
    """
    sites = _CR2WO6_SITES.replace("0.21358", "31.00000")
    pcr = _pcr(tmp_path, "hot.pcr", _phase(atoms=sites))
    with pytest.raises(FullProfPcrError) as excinfo:
        to_structure(read_fullprof_pcr(pcr))
    assert "hot.pcr" in str(excinfo.value)


# Finding 3 — a tie rietx cannot express is refused, not silently loosened.
#
# Built, not quoted: **no corpus file ties two nuclear atoms**. All five readable
# real files tie only one site's own coordinates (`300q-1p5K_1.pcr`'s O1 x=y=z on
# parameter 41; `crwo6002_BV2andBV4.pcr`'s O1 and O2 x=y on 56 and 57), and rietx
# reproduces every one of those through its site-symmetry DOFs — verified against
# the real files, which is why they must *not* refuse. The codeword `81.00` below
# is quoted from crwo6002_momcomp.pcr:108 (an Asy1 codeword); putting it on two
# atoms' Biso is this test's construction.
_SHARED_BISO_SITES = """\
Cr     CR      0.00000  0.00000  0.33312  0.21358   0.50000   0   0   0    1
                  0.00     0.00     0.00    81.00      0.00
W      W       0.00000  0.00000  0.00000  0.21358   0.25000   0   0   0    1
                  0.00     0.00     0.00    81.00      0.00
O1     O       0.30156  0.30156  0.00000  0.24694   0.50000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00
O2     O       0.30294  0.30294  0.34087  0.18463   1.00000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00"""


def test_a_recoverable_cross_atom_tie_reports_rather_than_refusing(tmp_path):
    """A shared Biso across two sites is dropped, reported, and restorable.

    Two sites sharing a Biso codeword is one FullProf parameter, not two, so the
    built ``Structure`` does carry more free parameters than the fit. But that
    is a **stated, recoverable loss** rather than a reading we would have to
    choose between, and root ``CLAUDE.md``'s rule is to report those and refuse
    only the ambiguous ones. ``biso`` is a direct parameter path, so the
    restoring call is unambiguous — and this test proves the message's promise
    by making the call, rather than asserting the sentence exists.
    """
    pcr = _pcr(tmp_path, "tied.pcr", _phase(atoms=_SHARED_BISO_SITES))
    model = read_fullprof_pcr(pcr)
    carried, dropped = nuclear_parameter_ties(model.phases[0])
    assert carried == []
    assert dropped == ["parameter 8: Cr.biso(x+1), W.biso(x+1)"]
    assert atom_tie_recoverability(model.phases[0]) == {
        "parameter 8: Cr.biso(x+1), W.biso(x+1)": True}

    # No refusal, and no flag needed to get past one.
    diagnostics: list = []
    structure = to_structure(model, diagnostics=diagnostics)
    assert len(structure.phases[0].atoms) == 4
    reported = [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"]
    assert len(reported) == 1
    assert reported[0].level == "warning"
    assert "Cr.biso" in reported[0].message and "W.biso" in reported[0].message
    assert reported[0].where == ["phases.0"]
    # It does not claim the caller declared anything — that prefix belongs to
    # the arm that still refuses.
    assert "drop_parameter_ties=True:" not in reported[0].message

    # The remedy the message names actually works on the structure handed back.
    refinement = rx.Refinement(
        structure, rx.Instrument(source=NeutronSource(wavelength=1.5406)))
    assert refinement.tie_equal(
        ["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"]) == [
            "phases.0.atoms.1.biso"]


def test_an_ambiguous_cross_atom_tie_still_refuses(tmp_path):
    """Tying two sites' *coordinates* is the case that has to refuse.

    Coordinates refine through site-symmetry directions (``dof.k``), and two
    different sites' ``dof`` bases are not the same direction — so restoring the
    tie would mean choosing which index on each site stands for it. Here both
    sites sit at DOF-0 special positions, so there is no path to tie at all.
    That is a reading we would have to pick, not a loss we can state, so it
    refuses and names the escape.
    """
    sites = _SHARED_BISO_SITES.replace(
        "                  0.00     0.00     0.00    81.00      0.00\n"
        "W      W       0.00000  0.00000  0.00000  0.21358   0.25000   0   0   0    1\n"
        "                  0.00     0.00     0.00    81.00      0.00",
        "                 81.00     0.00     0.00     0.00      0.00\n"
        "W      W       0.00000  0.00000  0.00000  0.21358   0.25000   0   0   0    1\n"
        "                 81.00     0.00     0.00     0.00      0.00")
    assert sites != _SHARED_BISO_SITES, "the codeword lines were not rewritten"
    pcr = _pcr(tmp_path, "tiedxy.pcr", _phase(atoms=sites))
    model = read_fullprof_pcr(pcr)
    carried, dropped = nuclear_parameter_ties(model.phases[0])
    assert dropped == ["parameter 8: Cr.x(x+1), W.x(x+1)"]
    assert atom_tie_recoverability(model.phases[0]) == {
        "parameter 8: Cr.x(x+1), W.x(x+1)": False}
    with pytest.raises(FullProfPcrError) as excinfo:
        to_structure(model)
    message = str(excinfo.value)
    assert "Cr.x" in message and "W.x" in message
    assert "tie_equal" in message
    assert "drop_parameter_ties=True" in message


def test_dropping_an_ambiguous_tie_is_the_callers_declared_choice(tmp_path):
    """``drop_parameter_ties=True`` builds the refusing arm, and says so."""
    sites = _SHARED_BISO_SITES.replace(
        "                  0.00     0.00     0.00    81.00      0.00\n"
        "W      W       0.00000  0.00000  0.00000  0.21358   0.25000   0   0   0    1\n"
        "                  0.00     0.00     0.00    81.00      0.00",
        "                 81.00     0.00     0.00     0.00      0.00\n"
        "W      W       0.00000  0.00000  0.00000  0.21358   0.25000   0   0   0    1\n"
        "                 81.00     0.00     0.00     0.00      0.00")
    pcr = _pcr(tmp_path, "tiedxy.pcr", _phase(atoms=sites))
    diagnostics: list = []
    structure = to_structure(read_fullprof_pcr(pcr), drop_parameter_ties=True,
                             diagnostics=diagnostics)
    assert len(structure.phases[0].atoms) == 4
    dropped = [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"]
    assert len(dropped) == 1
    assert dropped[0].message.startswith("drop_parameter_ties=True:")
    assert "Cr.x" in dropped[0].message and "W.x" in dropped[0].message
    assert dropped[0].where == ["phases.0"]


def test_the_six_real_files_contain_no_cross_atom_tie(tmp_path):
    """Why the recoverability rule is written from principle, not from corpus.

    Every shared-number group in the archive's six ``.pcr`` files is a
    *single-atom* coordinate tie, which is carried. So the corpus reaches
    neither arm of the recoverable/ambiguous split, and a rule inferred from it
    would have been an accident — the same argument that moved the cell ties
    onto ``cell_constraints``. Recorded here as the fixture-level statement of
    that fact: a phase built from single-atom ties alone has an empty
    recoverability map, because nothing was dropped.
    """
    pcr = _pcr(tmp_path, "single.pcr", _phase(atoms=_CR2WO6_SITES.replace(
        "O1     O       0.30156  0.30156  0.00000  0.24694   0.50000   0   0   0    1  #color cyan\n"
        "                  0.00     0.00     0.00     0.00      0.00",
        "O1     O       0.30156  0.30156  0.00000  0.24694   0.50000   0   0   0    1  #color cyan\n"
        "                561.00   561.00     0.00     0.00      0.00")))
    model = read_fullprof_pcr(pcr)
    carried, dropped = nuclear_parameter_ties(model.phases[0])
    assert dropped == []
    assert carried == ["parameter 56: O1.x(x+1), O1.y(x+1)"]
    assert atom_tie_recoverability(model.phases[0]) == {
        "parameter 56: O1.x(x+1), O1.y(x+1)": False}, (
        "a carried group's recoverability is never consulted, but it must not "
        "claim to be restorable — the map answers only 'if this were dropped'")


def test_a_sites_own_coordinate_tie_is_carried_by_symmetry_not_refused(tmp_path):
    """The corpus's real ties must **not** refuse — rietx already reproduces them.

    ``crwo6002_BV2andBV4.pcr`` ties O1's x to its y with parameter 56, on
    ``P 42/m n m``'s 4f site. ``ParameterTable._collect_atom_coords`` gives that
    site one ``dof.0`` and writes x and y as affine rows onto it, so the
    constraint is already one free parameter. Refusing it would be a false alarm
    on a real file, which is why the check re-derives the site's DOF count
    instead of refusing every shared codeword.
    """
    sites = _CR2WO6_SITES.replace(
        "O1     O       0.30156  0.30156  0.00000  0.24694   0.50000   0   0   0    1  #color cyan\n"
        "                  0.00     0.00     0.00     0.00      0.00",
        "O1     O       0.30156  0.30156  0.00000  0.24694   0.50000   0   0   0    1  #color cyan\n"
        "                561.00   561.00     0.00     0.00      0.00")
    assert "561.00" in sites, "the O1 codeword line was not rewritten"
    pcr = _pcr(tmp_path, "wyckoff.pcr", _phase(atoms=sites))
    model = read_fullprof_pcr(pcr)
    carried, dropped = nuclear_parameter_ties(model.phases[0])
    assert dropped == []
    assert carried == ["parameter 56: O1.x(x+1), O1.y(x+1)"]
    # and it builds without the caller having to declare anything
    assert len(to_structure(model).phases[0].atoms) == 4


# Round-three finding — a *cell* codeword tie is the one tie the atom analysis
# above does not reach. Whether rietx reproduces it turns on the space group,
# not on a site's DOFs, so the same `51 51 61` codewords are carried under a
# tetragonal symbol and dropped under an orthorhombic or triclinic one. The
# corpus has only the tetragonal (`crwo6002_*`, param 5) and cubic
# (`300q-1p5K_1`, param 40) cases, both carried, so the dropped case is driven
# synthetically the way the reviewer drove it.


def test_a_tetragonal_cell_tie_is_carried_by_symmetry_not_reported(tmp_path):
    """`51 51 61` under `P 42/m n m` is `a = b`, which the setting ties itself.

    This is the corpus's own case (`crwo6002_momcomp.pcr`:105) and it must stay
    silent: rietx's metric already holds `b = a` under a tetragonal setting, so
    the built cell has exactly the two free lengths the file refined and there is
    nothing dropped. The default fixture carries these codewords, so this pins
    that the new cell analysis does not raise a false alarm on the real file.
    """
    model = read_fullprof_pcr(_pcr(tmp_path, "tetra.pcr", _phase()))
    carried, dropped = cell_parameter_ties(model.phases[0])
    assert carried == ["parameter 5: a(x+1), b(x+1)"]
    assert dropped == []
    diagnostics: list = []
    to_structure(model, diagnostics=diagnostics)
    assert [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"] == []


@pytest.mark.parametrize("sg", ["P m m m", "P 1"])
def test_a_cell_tie_symmetry_does_not_hold_is_reported_not_dropped(tmp_path, sg):
    """The same `a = b` codewords under a symbol that leaves `a` and `b` free.

    Orthorhombic and triclinic do not tie the two edges, so `51 51 61` builds a
    cell with three free lengths where FullProf refined two — the function's own
    definition of a dropped tie, reached by the one path the atom analysis never
    consulted. It is *reported* through `FULLPROF_TIE_DROPPED` (the sibling
    reader's `TOPAS_CELL_COUPLING_DROPPED` shape) rather than refused: the cell
    is built either way, so no `drop_parameter_ties=True` is needed to see it.

    A one-site phase, as the reviewer drove it: the occupancy-ratio check is
    trivially self-consistent there, so what is under test is the cell tie and
    not the multiplicities.
    """
    site = ("Cr     CR      0.00000  0.00000  0.33312  0.21358   0.50000"
            "   0   0   0    1\n"
            "                  0.00     0.00     0.00     0.00      0.00")
    model = read_fullprof_pcr(
        _pcr(tmp_path, "loose.pcr", _phase(sg=sg, nat=1, atoms=site)))
    carried, dropped = cell_parameter_ties(model.phases[0])
    assert carried == []
    assert dropped == ["parameter 5: a(x+1), b(x+1)"]
    diagnostics: list = []
    # No flag passed, and it still builds — this reports, it does not refuse.
    structure = to_structure(model, diagnostics=diagnostics)
    assert len(structure.phases[0].atoms) == 1
    tie = [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"]
    assert len(tie) == 1
    assert tie[0].level == "warning"
    assert "a(x+1), b(x+1)" in tie[0].message
    assert "drop_parameter_ties=True" not in tie[0].message
    assert tie[0].where == ["phases.0.cell"]


def test_a_scaled_cell_relation_is_dropped_even_under_a_symbol_that_ties(
        tmp_path):
    """`b = 2a` is a multiplier, and symmetry only ever *equates* two edges.

    `51.00000` on `a` and `52.00000` on `b` share parameter 5 but with
    multipliers 1 and 2, so the file states `b = 2a`, not `b = a`. Even under
    `P 42/m n m`, whose symmetry ties `b = a`, rietx reproduces the equality and
    not the scaled relation, so the file's actual tie is dropped. The check must
    read the multiplier, not just the shared number — otherwise it would wave
    this through as the tetragonal `a = b` it is not.
    """
    scaled = "   51.00000   52.00000   61.00000    0.00000    0.00000    0.00000"
    model = read_fullprof_pcr(
        _pcr(tmp_path, "scaled.pcr", _phase(sg="P 42/m n m", cell_codes=scaled)))
    carried, dropped = cell_parameter_ties(model.phases[0])
    assert carried == []
    assert dropped == ["parameter 5: a(x+1), b(x+2)"]
    diagnostics: list = []
    to_structure(model, diagnostics=diagnostics)
    tie = [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"]
    assert len(tie) == 1
    assert "a(x+1), b(x+2)" in tie[0].message


def test_a_cubic_cell_tie_is_carried_including_the_edge_named_only_transitively(
        tmp_path):
    """`a = b = c` (parameter 40) under a cubic setting, the corpus's other case.

    `300q-1p5K_1.pcr` ties all three lengths to one parameter on `F d -3 m:2`.
    The cubic constraint table names `b -> a` and `c -> a` but not `c -> b`, so
    the check must follow ties to their root to see that `c` shares `a`'s root.
    All three land carried, and nothing is reported.
    """
    cubic = "  401.00000  401.00000  401.00000    0.00000    0.00000    0.00000"
    sites = ("Co1    CO      0.12500  0.12500  0.12500  0.35000   0.12500"
             "   0   0   0    1\n"
             "                  0.00     0.00     0.00     0.00      0.00")
    cell = "   8.068200   8.068200   8.068200  90.000000  90.000000  90.000000"
    model = read_fullprof_pcr(_pcr(tmp_path, "cubic.pcr",
                                   _phase(nat=1, sg="F D -3 M", atoms=sites,
                                          cell=cell, cell_codes=cubic)))
    carried, dropped = cell_parameter_ties(model.phases[0])
    assert carried == ["parameter 40: a(x+1), b(x+1), c(x+1)"]
    assert dropped == []
    diagnostics: list = []
    to_structure(model, diagnostics=diagnostics)
    assert [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"] == []


# Finding 4 — the R_Bragg count is asserted, not truncated into agreement.


def test_more_r_bragg_comments_than_phases_is_refused_not_truncated(tmp_path):
    """``strict=False`` here would attach an agreement factor to the wrong phase.

    The comments are matched by *file order* — their own phase number is trap 1
    and cannot re-key them — so an unequal count is a refusal, exactly as the
    ``Nph``/parsed-phase count two lines above already is.
    """
    stray = ("!  Data for PHASE number:   3  ==> Current R_Bragg for "
             "Pattern#  1:     5.00\n")
    pcr = _pcr(tmp_path, "extra.pcr", _phase(), trailing=stray + _RANGE)
    with pytest.raises(FullProfPcrError) as excinfo:
        read_fullprof_pcr(pcr)
    message = str(excinfo.value)
    assert "2" in message and "1 phases" in message


def test_a_pcr_with_no_r_bragg_comments_still_reads(tmp_path):
    """Zero comments is not a mismatch — a never-run .pcr carries none."""
    pcr = _pcr(tmp_path, "unrun.pcr", _phase())
    text = "\n".join(line for line in pcr.read_text(encoding="utf-8").split("\n")
                     if "R_Bragg" not in line)
    pcr.write_text(text, encoding="utf-8")
    model = read_fullprof_pcr(pcr)
    assert model.phases[0].r_bragg is None


# Finding 5 — integer fields go through an is_integer() guard, never bare int().


def test_a_non_integer_phase_control_field_is_refused_not_truncated(tmp_path):
    """``int(3.5) == 3`` would read a three-atom phase from a four-atom one.

    The line as a whole cannot go through ``_Cursor.ints``: ``Pr1 Pr2 Pr3`` are
    ``0.0 0.0 1.0`` and ``ATZ`` is ``963.500`` on this very line
    (crwo6002_momcomp.pcr:84) and ``154213.406`` in 300q-1p5K_1.pcr:66, so
    requiring the whole line to be integral would refuse every real file. The
    eleven counts and selectors get the guard field by field instead.
    """
    pcr = _pcr(tmp_path, "fractional.pcr", _phase(nat="3.5"))
    with pytest.raises(FullProfPcrError) as excinfo:
        read_fullprof_pcr(pcr)
    message = str(excinfo.value)
    assert "Nat = 3.5" in message
    assert "desynchronises" in message


def test_a_real_phase_control_line_keeps_its_float_atz(tmp_path):
    """The guard must not reject ATZ, which is a genuine float in every file."""
    model = read_fullprof_pcr(_pcr(tmp_path, "atz.pcr", _phase()))
    assert model.phases[0].control["atz"] == 963.500
    assert model.phases[0].control["pr3"] == 1.0


@pytest.mark.parametrize("header, what", [
    ("Strain-Model", "strain"),
    ("Size-Model", "size"),
])
def test_a_non_integer_model_selector_is_refused(tmp_path, header, what):
    """A model selector names a discrete broadening model, so ``1.5`` is not a 1.

    Truncating it would select a *different* model without saying so — the one
    place left in this module that cast a float through a bare ``int()``.
    """
    phase = _rewrite_trailing_selector(_phase(), header, "1.5")
    pcr = _pcr(tmp_path, f"{what}.pcr", phase)
    with pytest.raises(FullProfPcrError, match=r"model selector"):
        read_fullprof_pcr(pcr)


def test_an_integer_model_selector_still_reads(tmp_path):
    """The guard admits the integers the real files write."""
    phase = _rewrite_trailing_selector(_phase(), "Size-Model", "1")
    model = read_fullprof_pcr(_pcr(tmp_path, "size1.pcr", phase))
    assert model.phases[0].size_model == 1
    assert model.phases[0].strain_model == 0


# Finding 6 — an R lattice on rhombohedral axes.
#
# Synthetic, and it has to be: **every R phase in the corpus is on hexagonal
# axes** (`crwo6002_momcomp.pcr`:104's Cr2O3 cell, 4.95420 4.95420 13.42130
# 90 90 120). The cell below is that same real cell transformed to the
# rhombohedral setting of the same lattice —
# a_rh = sqrt(a^2/3 + c^2/9) = 5.30999 and
# sin(alpha/2) = 3 / (2*sqrt(3 + (c/a)^2)) => alpha = 55.61448 — so it describes
# a real Cr2O3, arrived at by arithmetic on a quoted line rather than invented.
# This closes a gap; it is not a wrong answer any file here produced.
_CR2O3_RHOMBOHEDRAL_CELL = (
    "   5.309990   5.309990   5.309990  55.614480  55.614480  55.614480")
_CR2O3_HEXAGONAL_CELL = (
    "   4.954200   4.954200  13.421300  90.000000  90.000000 120.000000")


@pytest.mark.parametrize("cell, expected, why", [
    ({"a": 5.30999, "b": 5.30999, "c": 5.30999,
      "alpha": 55.61448, "beta": 55.61448, "gamma": 55.61448},
     "R -3 c:R", "a = b = c with alpha = beta = gamma is rhombohedral axes"),
    ({"a": 4.95420, "b": 4.95420, "c": 13.42130,
      "alpha": 90.0, "beta": 90.0, "gamma": 120.0},
     "R -3 c", "the corpus's own Cr2O3 is hexagonal and must stay bare"),
])
def test_the_r_setting_is_picked_from_the_cell(cell, expected, why):
    """Root CLAUDE.md's invariant: ``read_small_structure`` picks R from the cell.

    gemmi resolves a bare ``R -3 c`` to the **hexagonal** setting (36
    operations); the rhombohedral one has 12. That factor of three is the
    general multiplicity :func:`occupancy_factor` divides by, so reading a
    rhombohedral cell under ``:H`` is a wrong multiplicity on every site.
    """
    assert normalize_space_group("R -3 c", cell) == expected, why


def test_without_a_cell_the_bare_r_symbol_is_unchanged():
    """No cell, no claim: the R case cannot be decided and is not guessed at."""
    assert normalize_space_group("R -3 c") == "R -3 c"


def test_a_rhombohedral_cell_selects_the_r_setting_end_to_end(tmp_path):
    """The cell line sits *after* the atoms, so the symbol is re-derived there."""
    pcr = _pcr(tmp_path, "rhombo.pcr",
               _phase(sg="R -3 c", cell=_CR2O3_RHOMBOHEDRAL_CELL,
                      cell_codes=_CR2WO6_CELL_CODES))
    phase = read_fullprof_pcr(pcr).phases[0]
    assert phase.space_group_raw == "R -3 c"
    assert phase.space_group == "R -3 c:R"


def test_a_hexagonal_r_cell_is_left_on_the_default_setting(tmp_path):
    """The corpus's real R phase, pinned: it must keep reading as before."""
    pcr = _pcr(tmp_path, "hex.pcr",
               _phase(sg="R -3 c", cell=_CR2O3_HEXAGONAL_CELL,
                      cell_codes=_CR2WO6_CELL_CODES))
    assert read_fullprof_pcr(pcr).phases[0].space_group == "R -3 c"


# The two lower-confidence items the review raised, both surfaced rather than
# left silent.


def test_the_origin_choice_repair_is_reported_as_a_diagnostic(tmp_path):
    """FullProf writes no origin suffix, so choosing one is a repair — and a
    repair on a value that reaches the ``Structure`` is reported the way the
    species rewrite is, on the same channel.

    ``F D -3 M`` is quoted from ``300q-1p5K_1.pcr``:68.
    """
    # A one-site cubic phase: Co3O4's 8a site alone, so the symbol resolves and
    # the occupancy ratio is trivially self-consistent.
    sites = ("Co1    CO      0.12500  0.12500  0.12500  0.35000   0.12500"
             "   0   0   0    1\n"
             "                  0.00     0.00     0.00     0.00      0.00")
    cell = "   8.068200   8.068200   8.068200  90.000000  90.000000  90.000000"
    pcr = _pcr(tmp_path, "spinel.pcr",
               _phase(nat=1, sg="F D -3 M", atoms=sites, cell=cell,
                      cell_codes=_CR2WO6_CELL_CODES))
    model = read_fullprof_pcr(pcr)
    assert model.phases[0].space_group == "F d -3 m:2"
    diagnostics: list = []
    to_structure(model, diagnostics=diagnostics)
    origin = [d for d in diagnostics if d.code == "FULLPROF_ORIGIN_CHOICE"]
    assert len(origin) == 1
    assert "'F D -3 M'" in origin[0].message
    assert "'F d -3 m:2'" in origin[0].message
    assert origin[0].where == ["phases.0.space_group"]


def test_a_case_only_repair_is_not_reported_as_an_origin_choice(tmp_path):
    """Lower-casing a HM symbol's tail is lossless, so it is not a convention
    the caller has to see — only the *setting* suffix is."""
    pcr = _pcr(tmp_path, "case.pcr", _phase(sg="P 42/M N M"))
    model = read_fullprof_pcr(pcr)
    assert model.phases[0].space_group == "P 42/m n m"
    diagnostics: list = []
    to_structure(model, diagnostics=diagnostics)
    assert [d for d in diagnostics if d.code == "FULLPROF_ORIGIN_CHOICE"] == []


def test_a_single_site_phase_says_its_occupancy_check_did_not_discriminate(
        tmp_path):
    """The occupancy-ratio test is structurally blind for a one-site phase.

    One ratio always agrees with itself, so the test passes for *every* setting
    and the licence it grants the origin choice is vacuous exactly there. That
    cannot be repaired by a better test — FullProf's Occ carries one arbitrary
    common factor per phase, so one site is one equation in two unknowns — so it
    is reported instead of being left silent.
    """
    sites = ("Co1    CO      0.12500  0.12500  0.12500  0.35000   0.12500"
             "   0   0   0    1\n"
             "                  0.00     0.00     0.00     0.00      0.00")
    cell = "   8.068200   8.068200   8.068200  90.000000  90.000000  90.000000"
    pcr = _pcr(tmp_path, "one_site.pcr",
               _phase(nat=1, sg="F D -3 M", atoms=sites, cell=cell,
                      cell_codes=_CR2WO6_CELL_CODES))
    diagnostics: list = []
    to_structure(read_fullprof_pcr(pcr), diagnostics=diagnostics)
    blind = [d for d in diagnostics if d.code == "FULLPROF_OCCUPANCY_UNCHECKED"]
    assert len(blind) == 1
    assert blind[0].level == "warning"
    assert "single site" in blind[0].message
    assert blind[0].where == ["phases.0.atoms.0.occ"]


def test_a_multi_site_phase_makes_no_such_claim(tmp_path):
    """Four sites do discriminate, so nothing is reported."""
    diagnostics: list = []
    to_structure(read_fullprof_pcr(_pcr(tmp_path, "four.pcr", _phase())),
                 diagnostics=diagnostics)
    assert [d for d in diagnostics
            if d.code == "FULLPROF_OCCUPANCY_UNCHECKED"] == []
