"""Read a FullProf ``.pcr`` refinement control file into a rietx model.

Format: FullProf Suite (Rodríguez-Carvajal) ``.pcr`` control files. FullProf is
closed source; **this reader is written from the file layout alone plus the
published format description**, as ``ATTRIBUTION.md``'s fence requires — no
FullProf code was read, no source file was consulted, and every layout fact
below is quoted in a comment from a named real file so that the evidence for it
is checkable. Where a real file is the *only* evidence for a block's position,
that is said, and where there is no evidence at all the construct is **refused
by name** rather than parsed on a guess.

Why the format is worth reading: a ``.pcr`` carries the whole solved model — the
phases, the sites, the cell, the instrument resolution function and, in the
header comments FullProf rewrites on every cycle, the converged χ² and per-phase
R_Bragg. That makes it the cheapest possible source of a *validated* refinement
to test against, exactly as a TOPAS ``.inp`` is (``projects/topas.py``).

Scope — what this reader claims
-------------------------------

**Handled completely: the single-pattern, constant-wavelength, nuclear case**
(``Job`` 0 or 1, one diffraction pattern, ``Jbt = 0`` phases). For those, every
value and every refinement codeword is read, the counts the file declares are
asserted against the lines actually parsed, and :func:`to_structure` builds a
:class:`~rietx.schemas.Structure`.

**Read but not modelled: magnetic phases** (``Jbt = 1``, both ``Isy = -1`` and
``Isy = -2`` sub-grammars). rietx has no magnetic scattering model, so a
magnetic phase cannot become a :class:`~rietx.schemas.Phase`. It is neither
dropped nor allowed to make the file unreadable: :func:`read_fullprof_pcr`
returns it in full on :attr:`FullProfModel.phases`, and
:func:`to_structure` **refuses**, naming every magnetic phase it would have
had to omit. See the design note below — four of the six real files this
reader was written against have a magnetic phase, so silently returning their
nuclear half is the single most damaging thing it could do.

**Refused by name, at read:** neutron time-of-flight (``Job = -1``), the
multi-pattern ``NPATT`` layout (a different grammar throughout, not merely a
different control-line header), a polynomial or Fourier background, single-
crystal/integrated-intensity jobs (``Cry``), restraint blocks, and every
control-line flag whose non-zero meaning would add lines this reader has no
file to establish the position of. Each refusal names the file, the field and
the value.

The three design decisions, and why
-----------------------------------

1. **A magnetic phase is carried, and the refusal is at build time.** Root
   CLAUDE.md's rule is *report or refuse, never drop*, and the choice here is
   between refusing the whole file at read and refusing only the build. Refusing
   at read throws away facts the reader read correctly — the nuclear phases, the
   wavelength, the agreement factors — because of a phase nobody asked it to
   build; and it would make 4 of the 6 real files simply unreadable, which is a
   reader nobody can use on the archive it was written for. Refusing at
   :func:`to_structure` puts the refusal exactly where the impossible thing is
   asked for, and :attr:`FullProfModel.magnetic_phases` is how the model
   *says* what it read. A caller who genuinely wants the nuclear subset passes
   ``nuclear_only=True``: the omission is then a caller's declared choice, named
   in the refusal message it replaces, rather than a reader's silence.

2. **TOF is refused at read, and so is every multi-bank file.** ``Job = -1``
   changes the meaning of the abscissa (TOF in µs, not degrees 2θ) and of the
   whole profile block (Sig-2/Sig-1/Sig-0, Gam-2/Gam-1/Gam-0, α₀/β₀/α₁ in place
   of Caglioti U/V/W and the asymmetry terms), and rietx has neither. The one
   real TOF file here is additionally ``NPATT 6``: **six patterns**, six
   independent control lines, six background blocks and six copies of every
   phase's profile block, sharing one set of atoms. That is a joint refinement
   over six detector banks — rietx's ``multi.py`` shape, not ``sequential.py``'s
   — and reading it would mean deciding *which* bank's resolution function to
   return, which is a question the file does not answer. Refused at the first
   line that says so (``NPATT``), before any of it is parsed.

3. **FullProf's ``Occ`` column is not rietx's ``occ``, and the difference is
   verified rather than assumed.** FullProf writes an occupancy already scaled
   by the site multiplicity over the general multiplicity, and the *absolute*
   normalisation of that column is degenerate with the phase scale factor —
   doubling every ``Occ`` and halving ``Scale`` is the same pattern. So the
   quantity a file states is a set of site occupancies *up to one arbitrary
   common factor*, and the corpus proves the factor is not conventional: the
   Cr₂WO₆ and Cr₂O₃ files carry a factor of 2 where the Co₃O₄ and YAG files
   carry 1. What is recoverable is the *ratio* between sites, so
   :func:`to_structure` divides each ``Occ`` by its site multiplicity, and
   **requires the result to be the same for every atom in the phase** — which
   is the statement "this phase is fully occupied", the only case where the
   arbitrary factor cancels. A phase where it is not constant is **refused**,
   naming the ratios, because a partially occupied site's chemical occupancy is
   not in the file. Handing the column straight through would be a silently
   wrong structure factor, which is the failure class this whole module exists
   to avoid.

Four traps, all verified against the real files
-----------------------------------------------

1. **The ``!  Data for PHASE number: N`` comments lie.** In
   ``crwo6002_G5_nc.pcr`` the *third* phase block is labelled ``PHASE number:
   1``. Phases are therefore parsed **positionally against ``Nph``** and the
   comment's index is recorded as :attr:`FullProfPhase.labelled_index` for
   provenance only. The parsed count is asserted against ``Nph``.

2. **Field names change with ``Jbt``.** The third column of a phase's control
   line is headed ``Ang`` when ``Jbt = 0`` and ``Mom`` when ``Jbt = 1``, in the
   same position — so a parser keyed on the header comment breaks on exactly
   the phase that matters. Nothing here reads a header comment: every block is
   located by walking the *data* lines in order, comments are dropped before the
   walk begins, and the column names are this module's own tables
   (:data:`_CELL_COLUMNS` and friends) zipped positionally.

3. **A stale λ sits in the refinable-λ slot.** ``crwo6002_momcomp.pcr`` has
   ``2.370100`` in the ``Zero Code SyCos Code SySin Code Lambda Code`` line
   while the refinement's real wavelength is the ``2.077100`` of the
   ``Lambda1 Lambda2`` line. Its codeword is ``0.00``, so it is inert and
   FullProf never used it. It is read into :attr:`FullProfModel.lambda_slot`,
   which is documented as *not* the wavelength; :attr:`FullProfModel.lambda1`
   is.

4. **The file's own refined-parameter count can be stale.**
   ``crwo6002_BV2andBV4.pcr`` declares 64 refined parameters and carries a
   codeword for parameter 65. Both numbers are reported —
   :attr:`FullProfModel.refined_parameter_count` is the declaration and
   :attr:`FullProfModel.parameter_numbers` the set actually referenced — and
   neither is silently corrected into the other, because which of the two is
   wrong is not something the file says.

One grammar for a refined value
-------------------------------

Every refinable scalar in a ``.pcr`` is a number paired with a **codeword**,
and the codeword carries two facts at once: ``10 × parameter_number +
multiplier``, signed. So it says *which* free parameter drives the value and
with what sign — which is how a ``.pcr`` writes a tie. ``crwo6002_G5_nc.pcr``'s
two Cr sublattices carry ``11.00`` and ``-11.00`` on the same basis-vector
coefficient: one parameter, opposite signs, i.e. the antiferromagnetic
constraint, and a reader that recorded only "refined" would lose the physics.
:class:`Code` is that decoding and :class:`Value` is the pair.

``0.00`` means fixed, and unlike a TOPAS ``.inp`` the slot is *always written* —
so the tri-state's third state is not "the file said nothing about this
parameter" but "the codeword column is not there at all", which happens only on
a ragged or truncated line. :attr:`Value.vary` is ``None`` exactly then, and
never collapses an absent column into ``False``.

Where the codeword sits is **not** uniform, and both spellings are real: the
atom, profile, cell and asymmetry blocks put it on the *following* line, while
the background points, the zero-shift line and the absorption line carry it
**inline** as the next column. Nothing here assumes one.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..formats.base import decode

# --------------------------------------------------------------------- errors


class FullProfPcrError(ValueError):
    """Raised naming the file and the offending line, never a bare parse miss.

    `io/CLAUDE.md`'s refusal rule: a reader raises naming the file, never its
    parser's exception. A ``.pcr`` is a positional format, so an unexpected
    field count desynchronises everything after it — which is why this is
    raised on the *first* line that does not fit rather than carried forward.
    """


# ------------------------------------------------------- the column-name tables
#
# These names are **this module's**, not the file's. A `.pcr` states its columns
# in a `!` comment line whose text changes with `Jbt` (trap 2), so reading them
# is how a parser comes to mis-key exactly the magnetic phase. Every block below
# is therefore a fixed tuple zipped positionally onto the numbers of one line,
# and the header comment is dropped before the walk starts.
#
# Each tuple was read off a real file, named in the comment above it.

#: ``!Job Npr Nph Nba Nex Nsc Nor Dum Iwg Ilo Ias Res Ste Nre Cry Uni Cor Opt Aut``
#: — crwo6002_momcomp.pcr:4, values on :5. Nineteen fields; the count is
#: asserted, because an eighteen-field (pre-``Aut``) form would shift every
#: field after it and nothing in the corpus establishes which one is missing.
_CONTROL_FIELDS = (
    "job", "npr", "nph", "nba", "nex", "nsc", "nor", "dum", "iwg", "ilo",
    "ias", "res", "ste", "nre", "cry", "uni", "cor", "opt", "aut")

#: The control-line flags whose only observed value is 0 and whose non-zero
#: meaning either adds lines this reader has no file to place, or changes what
#: the abscissa *is*. Refused by name rather than ignored: ignoring a flag that
#: adds a line desynchronises the whole positional walk, and ignoring ``Uni``
#: would read a non-2θ abscissa as 2θ, which `io/CLAUDE.md`'s "the axis is never
#: trusted" forbids outright.
#:
#: ``Iwg``, ``Ilo``, ``Ias``, ``Npr`` and ``Aut`` are deliberately *not* here:
#: they change weighting, the profile function or FullProf's own parameter
#: numbering, none of which moves a line. ``300q-1p5K_1.pcr`` has ``Aut 1``.
_MUST_BE_ZERO = {
    "nsc": "extra scattering-factor lines follow it",
    "nor": "its meaning is not established by any file here",
    "dum": "its meaning is not established by any file here",
    "res": "a resolution-function filename line follows it",
    "ste": "its meaning is not established by any file here",
    "nre": "restraint blocks follow it and their position is unevidenced",
    "cry": "it selects a single-crystal or integrated-intensity job, which is "
           "not a powder profile refinement",
    "uni": "it changes what the abscissa is, and reading a non-2θ axis as 2θ "
           "is the one repair a reader may never make",
    "cor": "its meaning is not established by any file here",
    "opt": "its meaning is not established by any file here",
}

#: ``!Ipr Ppl Ioc Mat Pcr Ls1 Ls2 Ls3 NLI Prf Ins Rpa Sym Hkl Fou Sho Ana`` —
#: crwo6002_momcomp.pcr:7, values on :8. Output-control switches only; recorded
#: for provenance and never acted on, because none of them moves a line.
_OUTPUT_FIELDS = (
    "ipr", "ppl", "ioc", "mat", "pcr", "ls1", "ls2", "ls3", "nli", "prf",
    "ins", "rpa", "sym", "hkl", "fou", "sho", "ana")

#: ``! Lambda1  Lambda2    Ratio    Bkpos    Wdt    Cthm     muR   AsyLim
#: Rpolarz  2nd-muR -> Patt# 1`` — crwo6002_momcomp.pcr:10, values on :11.
_PATTERN_FIELDS = (
    "lambda1", "lambda2", "ratio", "bkpos", "wdt", "cthm", "mur", "asylim",
    "rpolarz", "mur2")

#: ``!NCY  Eps  R_at  R_an  R_pr  R_gl     Thmin       Step       Thmax    PSD
#: Sent0`` — crwo6002_momcomp.pcr:13, values on :14.
_CYCLE_FIELDS = (
    "ncy", "eps", "r_at", "r_an", "r_pr", "r_gl", "thmin", "step", "thmax",
    "psd", "sent0")

#: ``!Nat Dis Ang Pr1 Pr2 Pr3 Jbt Irf Isy Str Furth       ATZ    Nvk Npr More``
#: — crwo6002_momcomp.pcr:83, values on :84; and the *same* fifteen positions
#: under the ``Mom`` spelling on :141/:142, which is trap 2. ``ang_or_mom`` is
#: deliberately one field: it is one column, and which of the two names it
#: carries is a function of ``Jbt``, not of the file's prose.
_PHASE_FIELDS = (
    "nat", "dis", "ang_or_mom", "pr1", "pr2", "pr3", "jbt", "irf", "isy",
    "str", "furth", "atz", "nvk", "npr", "more")

#: ``!  Zero    Code    SyCos    Code   SySin    Code  Lambda     Code MORE``
#: — crwo6002_momcomp.pcr:76, values on :77. The value/codeword pairs are
#: **inline** here, not on a following line. ``lambda_slot`` is trap 3: a stale
#: number with an inert codeword, and never the wavelength.
_ZERO_FIELDS = ("zero", "sycos", "sysin", "lambda_slot")

#: ``!  Scale        Shape1      Bov      Str1      Str2      Str3
#: Strain-Model`` — crwo6002_momcomp.pcr:97, values on :98, codewords on :99.
#: Six values plus a trailing integer model selector that has no codeword.
_SCALE_COLUMNS = ("scale", "shape1", "bov", "str1", "str2", "str3")

#: ``!       U         V          W           X          Y        GauSiz
#: LorSiz Size-Model`` — crwo6002_momcomp.pcr:100/:101/:102. Seven values plus
#: a trailing integer model selector. U/V/W are Caglioti in deg²(2θ); X/Y are
#: the Lorentzian pair, and note the root CLAUDE.md convention warning — GSAS
#: and FullProf swap the X/Y labels, so these are carried under FullProf's own
#: spelling and translated nowhere in this module.
_WIDTH_COLUMNS = ("u", "v", "w", "x", "y", "gausiz", "lorsiz")

#: ``!     a          b         c        alpha      beta       gamma`` —
#: crwo6002_momcomp.pcr:103/:104/:105. The codeword line is where a `.pcr`
#: writes a symmetry tie: ``51.00000 51.00000 61.00000`` ties a and b to
#: parameter 5 and c to parameter 6, which is the tetragonal constraint.
_CELL_COLUMNS = ("a", "b", "c", "alpha", "beta", "gamma")

#: ``!  Pref1    Pref2      Asy1     Asy2     Asy3     Asy4      S_L      D_L``
#: — crwo6002_momcomp.pcr:106/:107/:108. Eight values, eight codewords, no
#: trailing model selector.
_ASYM_COLUMNS = ("pref1", "pref2", "asy1", "asy2", "asy3", "asy4", "s_l", "d_l")

#: ``!Atom   Typ       X        Y        Z     Biso       Occ     In Fin N_t
#: Spc /Codes`` — crwo6002_momcomp.pcr:87, atom on :88, codewords on :89. The
#: label and the type consume the first two tokens; ``In``/``Fin``/``N_t``/
#: ``Spc`` are trailing integers with no codewords.
_ATOM_COLUMNS = ("x", "y", "z", "biso", "occ")

#: ``!Atom   Typ  Mag Vek    X      Y      Z       Biso    Occ      Rx  Ry  Rz``
#: then ``!     Ix     Iy     Iz    beta11  beta22  beta33    MagPh`` —
#: crwo6002_momcomp.pcr:157-162 (``Isy = -1``, real/imaginary moment
#: components) and crwo6002_G5_nc.pcr:166-171 (``Isy = -2``, where the same
#: two columns are basis-vector coefficients ``C1..C3`` and ``C4..C9``). Same
#: positions, different physical meaning, so the names are neutral: a magnetic
#: atom occupies **four** lines — values, codewords, continuation, codewords.
_MAGNETIC_COLUMNS = ("x", "y", "z", "biso", "occ", "m1", "m2", "m3")
_MAGNETIC_CONTINUATION = ("m4", "m5", "m6", "m7", "m8", "m9", "magph")

#: What a nuclear phase's ``N_t`` adds to each atom. ``0`` is the isotropic
#: form every single-pattern file here uses; ``2`` adds an anisotropic β line
#: and its codeword line, evidenced by yag_xpress_072_new.pcr:187-190. Any
#: other value is refused, because how many lines it occupies is then a guess
#: and a wrong guess desynchronises the rest of the file.
_N_T_EXTRA_LINES = {0: 0, 2: 2}

#: FullProf writes ``beta11 beta22 beta33 beta12 beta13 beta23`` in this order
#: (yag_xpress_072_new.pcr:186). Read, and refused at :func:`to_structure` —
#: the β → U^ij conversion needs a convention (whether the stored off-diagonal
#: already carries the factor 2 of the exponent) that no file here settles, and
#: a wrong factor is a silently wrong Debye-Waller factor at high Q.
_BETA_COLUMNS = ("beta11", "beta22", "beta33", "beta12", "beta13", "beta23")


# ------------------------------------------------------------ codeword grammar


@dataclass(frozen=True)
class Code:
    """A FullProf refinement codeword, decoded.

    The encoding is ``10 × number + multiplier``, signed, so one number carries
    both *which* free parameter drives this value and the linear coefficient
    (usually ±1) with which it does. That is how a ``.pcr`` writes a tie: the
    two Cr sublattices of ``crwo6002_G5_nc.pcr`` carry ``11.00`` and ``-11.00``
    on the same basis-vector coefficient — one parameter, opposite sign, the
    antiferromagnetic constraint — and the tetragonal cell of
    ``crwo6002_momcomp.pcr`` carries ``51.00000`` on both ``a`` and ``b``.

    A reader that recorded only "refined" would lose all of that, which is the
    same class of loss as the TOPAS reader's collapsed tri-state.
    """

    number: int
    multiplier: float
    #: The codeword exactly as the file wrote it, so a consumer can check the
    #: decoding rather than trust it.
    codeword: float


def decode_codeword(codeword: float) -> Code | None:
    """``601.0`` → parameter 60, multiplier +1; ``-11.00`` → parameter 1, −1.

    ``0.0`` is FullProf's spelling of *fixed* and returns None — the absence of
    a driving parameter, not parameter zero.

    A non-zero codeword that decodes to parameter **0** raises: that is a number
    no FullProf run writes — a truncated ``601.0`` reading as ``6`` is how one
    arises — and returning None for it would report a refined parameter as held,
    which is exactly the distinction a consumer of this function is making.
    """
    if codeword == 0.0:
        return None
    magnitude = abs(codeword)
    number = int(magnitude // 10)
    if number == 0:
        raise FullProfPcrError(
            f"codeword {codeword!r} decodes to parameter number 0, which no "
            f"FullProf refinement writes — the encoding is 10*number+multiplier")
    multiplier = round(magnitude - 10.0 * number, 6)
    return Code(number=number, multiplier=math.copysign(multiplier, codeword),
                codeword=codeword)


@dataclass(frozen=True)
class Value:
    """One scalar as the file states it, with its codeword.

    :attr:`vary` is a tri-state and the third state is narrower than a TOPAS
    ``.inp``'s. FullProf *always* writes the codeword slot, so "the file said
    nothing" is not reachable for a value whose line is intact; ``None`` means
    the codeword **column is absent** — a ragged or truncated line — and is
    never a stand-in for ``False``. Collapsing the two is how a reader comes to
    report a refined parameter as held.
    """

    value: float
    #: The codeword verbatim, or None where the codeword column is not there.
    codeword: float | None = None

    @property
    def vary(self) -> bool | None:
        """Was this value free in the refinement the file records?"""
        return None if self.codeword is None else self.codeword != 0.0

    @property
    def code(self) -> Code | None:
        """The decoded codeword: which parameter drives this, and with what sign."""
        return None if not self.codeword else decode_codeword(self.codeword)


# ------------------------------------------------------------------ the model


@dataclass
class FullProfAtom:
    """One site of a nuclear phase, or of a magnetic one.

    ``values`` is keyed by :data:`_ATOM_COLUMNS` for a nuclear site and by
    :data:`_MAGNETIC_COLUMNS` + :data:`_MAGNETIC_CONTINUATION` for a magnetic
    one — the *positions* named, never the header comment's words.
    """

    label: str
    #: The scattering-species token as the file wrote it (``CR``, ``MCR3``).
    species_raw: str
    #: The same token in IUCr spelling where it names an element (``Cr``); a
    #: magnetic form-factor label (``MCR3``) is left verbatim, since it names a
    #: table rietx has no counterpart for.
    species: str
    values: dict = field(default_factory=dict)
    #: ``In Fin N_t Spc`` — trailing integers with no codewords.
    flags: tuple = ()
    #: The anisotropic β block, where ``N_t = 2`` states one. Keyed by
    #: :data:`_BETA_COLUMNS`.
    betas: dict = field(default_factory=dict)

    @property
    def n_t(self) -> int:
        """FullProf's displacement-model selector for this site."""
        return int(self.flags[2]) if len(self.flags) > 2 else 0


@dataclass
class MagneticSymmetry:
    """A magnetic phase's symmetry sub-block, in whichever spelling it uses.

    ``Isy`` switches the whole grammar and both branches are in the corpus:

    * ``Isy = -1`` — ``Nsym Cen Laue MagMat`` then ``Nsym`` × (``SYMM``,
      ``MagMat`` × ``MSYM``); the atoms then carry real moment components
      ``Rx Ry Rz`` and imaginary ``Ix Iy Iz``
      (``crwo6002_momcomp.pcr``:145-162).
    * ``Isy = -2`` — ``Nsym Cen Laue Ireps N_Bas``, a real/imaginary indicator
      line of ``N_Bas`` values, then ``Nsym`` × (``SYMM``, ``|Ireps|`` ×
      (``BASR``, ``BASI``)) with ``3 × N_Bas`` numbers per basis line; the
      atoms then carry basis-vector coefficients ``C1..C9``
      (``crwo6002_BV2andBV4.pcr``:145-161, ``crwo6002_G5_nc.pcr``:145-164,
      ``300q-1p5K_1.pcr``:98-108).

    Every count above is asserted, which is what makes the walk past an
    unmodelled block safe: this reader has to land on the next phase's first
    line exactly, and there is no keyword it could resynchronise on.
    """

    isy: int
    nsym: int
    cen: int
    laue: int
    #: ``MagMat`` under ``Isy = -1``; None under ``Isy = -2``.
    magmat: int | None = None
    #: ``Ireps`` and ``N_Bas`` under ``Isy = -2``; None under ``Isy = -1``.
    ireps: int | None = None
    n_bas: int | None = None
    #: The ``N_Bas`` real(0)/imaginary(1) indicators, ``Isy = -2`` only.
    real_imaginary: tuple = ()
    #: One entry per ``SYMM``: the operator text and the lines that follow it,
    #: verbatim. Verbatim because nothing here models them — carrying a parsed
    #: form would be a claim about a magnetic symmetry algebra this package does
    #: not have.
    operators: list = field(default_factory=list)


@dataclass
class SoftMomentConstraint:
    """One soft moment restraint: a target moment and its σ, keyed to a site.

    Both spellings in the corpus are the *same* production — an atom label
    truncated to the field's width — which is why this resolves the key by
    **prefix** against the phase's labels rather than switching on a shape:

    * ``CR   2.900 0.02000`` (``crwo6002_momcomp_softconstrained.pcr``:177),
      whose phase's one atom is labelled ``CR``;
    * ``1C  2.90 0.02`` / ``2C  2.90 0.02`` (``crwo6002_G5_nc.pcr``:190-191),
      whose phase's two atoms are labelled ``1CR`` and ``2CR``.

    Reading the second as a *site index* also fits those two lines, and would
    then read ``CR`` as a label — two productions where one explains both. The
    prefix reading is recorded, the raw key is kept beside it, and an
    unresolvable key is reported as such rather than guessed at.
    """

    key: str
    moment: float
    sigma: float
    #: Index into the phase's ``atoms`` where the key resolves to exactly one
    #: label by prefix; None where it resolves to none or to several.
    atom_index: int | None = None


@dataclass
class FullProfPhase:
    """One phase block, nuclear or magnetic.

    ``index`` is **positional** — its ordinal among the ``Nph`` blocks — and
    ``labelled_index`` is what the ``!  Data for PHASE number: N`` comment
    claimed. They disagree in a real file (``crwo6002_G5_nc.pcr``'s third block
    says 1), which is why nothing keys on the comment.
    """

    index: int
    name: str
    control: dict = field(default_factory=dict)
    space_group: str = ""
    #: The symbol exactly as written, before case normalisation.
    space_group_raw: str = ""
    atoms: list = field(default_factory=list)
    magnetic: MagneticSymmetry | None = None
    #: :data:`_SCALE_COLUMNS` ∪ :data:`_WIDTH_COLUMNS` ∪ :data:`_ASYM_COLUMNS`.
    profile: dict = field(default_factory=dict)
    #: :data:`_CELL_COLUMNS`.
    cell: dict = field(default_factory=dict)
    strain_model: int | None = None
    size_model: int | None = None
    #: ``Nvk`` propagation vectors, each a ``(k, codewords)`` pair.
    propagation_vectors: list = field(default_factory=list)
    soft_moment_constraints: list = field(default_factory=list)
    labelled_index: int | None = None
    r_bragg: float | None = None

    @property
    def jbt(self) -> int:
        return int(self.control["jbt"])

    @property
    def is_magnetic(self) -> bool:
        """``Jbt = 1``. rietx has no magnetic scattering model, so this phase
        can be reported but not built — see the module docstring's decision 1."""
        return self.jbt == 1

    @property
    def isy(self) -> int:
        return int(self.control["isy"])

    @property
    def nvk(self) -> int:
        """How many propagation vectors this phase declares."""
        return int(self.control["nvk"])


@dataclass
class FullProfModel:
    """What a ``.pcr`` states.

    Deliberately not a :class:`~rietx.schemas.Structure`: the caller decides
    which phases to keep, and this object's whole job is to be able to *say*
    what it read — including the parts rietx cannot model, which is the only
    alternative to dropping them.
    """

    #: The file this was read from, so every refusal downstream can name it.
    path: str | None = None
    #: The ``COMM`` title line.
    title: str | None = None
    #: ``! Current global Chi2 (Bragg contrib.) =`` — FullProf rewrites this
    #: comment every cycle, so it is the converged value, and it is the reason
    #: the format is worth reading at all.
    chi2: float | None = None
    #: The data file the header comment names. **Reported, never chased**: the
    #: reference is routinely stale — ``300q-1p5K_1.pcr`` names
    #: ``RT-1_5K_1.dat`` while the pattern beside it is ``300q-1p5K_1.dat`` —
    #: and resolving it would be a reader inventing a filename.
    data_file: str | None = None
    #: The ``PCR-file:`` name from the same comment, which is likewise often
    #: another refinement's (``crwo6002_G5_nc.pcr`` says ``crwo6002_BV2andBV4``).
    pcr_name: str | None = None
    control: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    pattern: dict = field(default_factory=dict)
    cycles: dict = field(default_factory=dict)
    #: ``(2θ position, Value)`` per interpolated background point. The codeword
    #: is **inline** as the third column here, not on a following line.
    background: list = field(default_factory=list)
    #: ``(low, high)`` per excluded region, in file order.
    excluded_regions: list = field(default_factory=list)
    #: The count the file declares. Compare with :attr:`parameter_numbers`
    #: rather than trusting either: they disagree in a real file (trap 4).
    refined_parameter_count: int | None = None
    #: Zero shift, cos/sin sample displacement, and trap 3's stale λ slot.
    zero_shift: dict = field(default_factory=dict)
    phases: list = field(default_factory=list)
    #: ``(2θ_low, 2θ_high, pattern)`` — the range actually fitted, from the
    #: trailing ``!  2Th1/TOF1  2Th2/TOF2  Pattern #`` block.
    fitted_range: tuple | None = None

    @property
    def job(self) -> int:
        """0 = X-ray CW, 1 = neutron CW. −1 (neutron TOF) is refused at read."""
        return int(self.control["job"])

    @property
    def lambda1(self) -> float | None:
        """The refinement's wavelength — **not** :attr:`lambda_slot` (trap 3)."""
        return self.pattern.get("lambda1")

    @property
    def lambda2(self) -> float | None:
        return self.pattern.get("lambda2")

    @property
    def lambda_slot(self) -> Value | None:
        """The refinable-λ slot of the zero-shift line.

        Trap 3: ``crwo6002_momcomp.pcr`` has ``2.370100`` here against a real λ
        of 2.077100, with codeword ``0.00`` so FullProf never used it. Read for
        provenance; :attr:`lambda1` is the wavelength.
        """
        return self.zero_shift.get("lambda_slot")

    @property
    def nuclear_phases(self) -> list:
        return [ph for ph in self.phases if not ph.is_magnetic]

    @property
    def magnetic_phases(self) -> list:
        """The phases rietx has no model for. Reported, never dropped."""
        return [ph for ph in self.phases if ph.is_magnetic]

    @property
    def parameter_numbers(self) -> frozenset:
        """Every parameter number any codeword in the file references."""
        numbers: set[int] = set()

        def gather(values) -> None:
            for value in values:
                code = value.code
                if code is not None:
                    numbers.add(code.number)

        gather(self.zero_shift.values())
        gather(v for _, v in self.background)
        for ph in self.phases:
            gather(ph.profile.values())
            gather(ph.cell.values())
            for atom in ph.atoms:
                gather(atom.values.values())
                gather(atom.betas.values())
            for _, codes in ph.propagation_vectors:
                gather(codes)
        return frozenset(numbers)


# --------------------------------------------------------------- normalisation


def normalize_species(token: str) -> str:
    """``CR`` → ``Cr``, ``CA+2`` → ``Ca2+``; a magnetic label is left alone.

    FullProf writes the scattering-species token in whatever case the author
    typed — ``CR``, ``AL``, ``Co``, ``W`` all appear in the corpus — and rietx's
    species are element symbols in IUCr spelling. Title-casing a one- or
    two-letter element token is unambiguous, and the charge is reordered
    digit-first exactly as ``projects/topas.py`` does, so the two readers hand
    back one spelling.

    A token that does not look like an element with an optional charge —
    ``MCR3``, a magnetic form-factor table name — is returned **verbatim**.
    rietx has no magnetic form factors, so inventing ``Mc`` + charge from it
    would be a species that means nothing, and the phase carrying it is refused
    at :func:`to_structure` anyway.
    """
    stripped = re.sub(r"[^A-Za-z0-9+-]", "", token)
    if m := re.fullmatch(r"([A-Za-z]{1,2})([+-])(\d*)", stripped):
        element, sign, magnitude = m.groups()
        return f"{element.capitalize()}{magnitude or ''}{sign}"
    if m := re.fullmatch(r"([A-Za-z]{1,2})(\d*)([+-])", stripped):
        element, magnitude, sign = m.groups()
        return f"{element.capitalize()}{magnitude}{sign}"
    if re.fullmatch(r"[A-Za-z]{1,2}", stripped):
        return stripped.capitalize()
    return token.strip()


def normalize_space_group(symbol: str) -> str:
    """``F D -3 M`` → ``F d -3 m:2``; ``P 42/m n m`` unchanged.

    Two repairs, and each is a *report* rather than a contradiction:

    **Case.** FullProf carries the Hermann-Mauguin symbol in whatever case the
    author typed: ``F D -3 M`` (``300q-1p5K_1.pcr``:68) and ``I A -3 D``
    (``yag_xpress_072_new.pcr``:184) against ``P 42/m n m`` and ``R -3 c`` in
    the same corpus. Only the lattice letter is upper case in a HM symbol —
    everything after it is drawn from ``m a b c d n`` plus digits, ``/`` and
    ``-`` — so lower-casing the tail is lossless.

    **Origin choice.** FullProf writes no origin suffix at all, which is the
    TOPAS ``Pn-3mZ`` trap in a worse form: gemmi resolves a bare ``F d -3 m`` to
    origin choice **1**, and the corpus's spinel is on choice 2 (Co at ⅛⅛⅛ and
    ½½½, O at x,x,x — the standard Co₃O₄ description). Choice 2 is therefore
    preferred wherever the bare symbol lands on choice 1.

    That preference is a *convention*, so it is not left to be trusted:
    :func:`to_structure` re-derives every site's multiplicity under whichever
    setting this returns and refuses the phase unless the occupancy column
    reduces consistently (module docstring, decision 3). A wrong origin gives
    wrong multiplicities and is refused, not returned.
    """
    text = " ".join(symbol.split())
    if not text:
        return text
    normalised = text[0].upper() + text[1:].lower()
    try:
        import gemmi
    except ImportError:  # pragma: no cover - gemmi is a hard dependency
        return normalised
    try:
        sg = gemmi.SpaceGroup(normalised)
    except Exception:
        return normalised
    if sg.ext == "1":
        try:
            gemmi.SpaceGroup(f"{normalised}:2")
        except Exception:
            return normalised
        return f"{normalised}:2"
    return normalised


# ---------------------------------------------------------------- the line walk


def _strip(raw: str) -> str:
    """One line with its comments removed.

    Three markers, all real and all needed:

    * ``!`` opens a comment, and does so **inline** as well as at column 1 —
      ``61    !Number of refined parameters`` is a data line with a comment on
      it (``crwo6002_momcomp.pcr``:74), so cutting at ``!`` is what makes the
      count readable *and* what makes the header lines disappear.
    * ``<--`` annotates the space-group line
      (``P 42/m n m               <--Space group symbol``).
    * ``#`` annotates an atom line (``#color cyan`` on every Cr₂WO₆ site).

    A line that is empty after the cut is a comment line and never reaches the
    walk. The risk this accepts is a phase *name* containing one of the three
    markers, which no file here does; the alternative — position-only comment
    detection — would lose the refined-parameter count.
    """
    for marker in ("!", "#", "<--"):
        index = raw.find(marker)
        if index >= 0:
            raw = raw[:index]
    return raw.strip()


@dataclass(frozen=True)
class _Line:
    number: int
    text: str


class _Cursor:
    """A walk over the file's **data** lines, in order.

    Positional by construction, which is the answer to trap 2: the column names
    live in this module's tables and the file's ``!`` header comments are gone
    before the first ``take``. Every exhaustion and every field-count surprise
    raises :class:`FullProfPcrError` naming the file and the line, because a
    ``.pcr`` has no keyword a reader could resynchronise on — one wrong field
    count silently reinterprets everything after it.
    """

    def __init__(self, path: Path, lines: list) -> None:
        self.path = path
        self.lines = lines
        self.at = 0

    def _fail(self, what: str, detail: str, line: _Line | None = None) -> FullProfPcrError:
        where = f" line {line.number}" if line is not None else ""
        return FullProfPcrError(f"{self.path}:{where} {what}: {detail}")

    @property
    def exhausted(self) -> bool:
        return self.at >= len(self.lines)

    def peek(self) -> _Line | None:
        return None if self.exhausted else self.lines[self.at]

    def take(self, what: str) -> _Line:
        if self.exhausted:
            raise FullProfPcrError(
                f"{self.path}: the file ends where {what} was expected — "
                f"{len(self.lines)} data lines read. A .pcr is positional, so a "
                f"truncated file cannot be partially interpreted.")
        line = self.lines[self.at]
        self.at += 1
        return line

    def remaining(self) -> list:
        rest = self.lines[self.at:]
        self.at = len(self.lines)
        return rest

    def floats(self, what: str, *, at_least: int, skip: int = 0,
               leading: bool = False) -> tuple[_Line, list]:
        """The numbers of the next data line, and the line itself.

        ``skip`` drops leading non-numeric tokens (an atom's label and species).
        ``leading`` parses only the leading numeric *run* and stops at the first
        token that is not a number, which one block genuinely needs: FullProf
        writes ``0.0000000 0.0000000 0.0000000          Propagation Vector  1``
        (``300q-1p5K_1.pcr``:130), where the trailing words carry no comment
        marker for :func:`_strip` to cut at.
        """
        line = self.take(what)
        tokens = line.text.split()[skip:]
        numbers: list[float] = []
        for token in tokens:
            try:
                numbers.append(float(token))
            except ValueError as exc:
                if leading:
                    break
                raise self._fail(
                    what, f"{token!r} is not a number in {line.text!r}", line) from exc
        if len(numbers) < at_least:
            raise self._fail(
                what, f"expected at least {at_least} numbers, found "
                      f"{len(numbers)} in {line.text!r}", line)
        return line, numbers

    def ints(self, what: str, *, expect: int) -> tuple[_Line, list]:
        """Exactly ``expect`` integers.

        Exact rather than "at least": these are the control lines, where an
        extra or a missing field shifts the meaning of every field after it, so
        a count surprise is refused instead of being read off the front.
        """
        # `at_least=0`, so a *narrow* line is reported by the exact-count
        # message below rather than by the generic one: the actionable fact is
        # which form the reader expects, not that it wanted more numbers.
        line, numbers = self.floats(what, at_least=0)
        if len(numbers) != expect:
            raise self._fail(
                what, f"expected {expect} fields, found {len(numbers)} in "
                      f"{line.text!r} — only the {expect}-field form is "
                      f"evidenced by any file this reader was written against",
                line)
        out = []
        for value in numbers:
            if not float(value).is_integer():
                raise self._fail(what, f"{value!r} is not an integer in "
                                       f"{line.text!r}", line)
            out.append(int(value))
        return line, out


def _row(names: tuple, values: list, codewords: list | None) -> dict:
    """Zip a value line and its codeword line onto positional names.

    A codeword column the line does not reach is ``None``, which
    :attr:`Value.vary` reports as "the column is absent" rather than as
    "held" — the tri-state kept honest at the one place it could collapse.
    """
    out: dict[str, Value] = {}
    for i, name in enumerate(names):
        if i >= len(values):
            break
        codeword = None
        if codewords is not None and i < len(codewords):
            codeword = codewords[i]
        out[name] = Value(value=values[i], codeword=codeword)
    return out


def _block(cur: _Cursor, names: tuple, what: str, *, trailing: int = 0
           ) -> tuple[dict, int | None]:
    """A value line, its codeword line, and an optional trailing model selector.

    ``trailing`` is the integer model code that ends the scale and width lines
    (``Strain-Model``, ``Size-Model``) and carries **no** codeword, which is why
    it is taken off the value line rather than being a column.
    """
    _, values = cur.floats(what, at_least=len(names) + trailing)
    _, codewords = cur.floats(f"{what} codewords", at_least=1)
    model = None
    if trailing and len(values) > len(names):
        model = int(values[len(names)])
    return _row(names, values, codewords), model


# ------------------------------------------------------------------- the reader


#: ``! Current global Chi2 (Bragg contrib.) =      5.144`` — the converged χ²,
#: rewritten by FullProf on every cycle, so it is the answer and not a seed.
_CHI2 = re.compile(r"Current\s+global\s+Chi2[^=]*=\s*([-+0-9.eE]+)")

#: ``! Files => DAT-file: CrWO6002.dat,  PCR-file: crwo6002_momcomp``
_FILES = re.compile(r"DAT-file:\s*([^,]+?)\s*,\s*PCR-file:\s*(\S+)")

#: ``!  Data for PHASE number:   1  ==> Current R_Bragg for Pattern#  1: 1.79``
#: The phase number here is trap 1 and is recorded for provenance only.
_PHASE_COMMENT = re.compile(
    r"Data\s+for\s+PHASE\s+number:\s*(\d+).*?R_Bragg[^:]*:\s*([-+0-9.eE]+)")


def read_fullprof_pcr(path: str | Path) -> FullProfModel:
    """Parse a ``.pcr``. Raises :class:`FullProfPcrError` naming file and line.

    Handles the single-pattern constant-wavelength layout completely and refuses
    everything else by name — see the module docstring for the exact boundary.
    """
    path = Path(path)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise FullProfPcrError(f"{path}: cannot read: {exc}") from exc
    # `base.decode` is the seam `head()` already goes through, shared rather
    # than duplicated — the same reasoning as `projects/topas.py`'s.
    raw, codec, _bom = decode(raw_bytes)
    if "\x00" in raw:
        # `io/CLAUDE.md`'s `xy` row: ASCII-range UTF-16 is valid UTF-8 with
        # interleaved NULs, so a surviving NUL means no byte-order mark said
        # which of LE and BE this is, and guessing is a repair a reader cannot
        # say it made.
        raise FullProfPcrError(
            f"{path}: not text this reader can decode — NUL bytes survive a "
            f"{codec} decode, which is what an ASCII-range UTF-16 export with "
            f"no byte-order mark looks like. Re-save it as UTF-8.")

    raw_lines = raw.split("\n")
    model = FullProfModel(path=str(path))

    # The comments are read *first* and separately, for provenance only: the
    # agreement factors and the file references live nowhere else, and the phase
    # index one of them states is trap 1. Nothing structural comes from here.
    r_braggs: list[tuple[int, float]] = []
    for text in raw_lines:
        if m := _CHI2.search(text):
            model.chi2 = float(m.group(1))
        if m := _FILES.search(text):
            model.data_file, model.pcr_name = m.group(1), m.group(2)
        if m := _PHASE_COMMENT.search(text):
            r_braggs.append((int(m.group(1)), float(m.group(2))))

    data = [_Line(number=i + 1, text=stripped)
            for i, stripped in ((i, _strip(text)) for i, text in enumerate(raw_lines))
            if stripped]
    cur = _Cursor(path, data)

    first = cur.take("the COMM title line")
    if not first.text.upper().startswith("COMM"):
        raise FullProfPcrError(
            f"{path}: line {first.number} is {first.text!r}, and a .pcr opens "
            f"with a COMM title line — this is not a FullProf control file, or "
            f"its header was edited away")
    model.title = first.text[4:].strip() or None

    # The multi-pattern layout announces itself on the line after COMM, and it
    # is a different grammar from here down: per-pattern control lines that shed
    # `Nph` (it moves to a line of its own), per-pattern background and excluded
    # regions, and one copy of every phase's whole profile block per pattern.
    # Refused before any of it is parsed — see the module docstring's decision 2.
    if (nxt := cur.peek()) is not None and nxt.text.upper().startswith("NPATT"):
        count = nxt.text.split()[1] if len(nxt.text.split()) > 1 else "?"
        raise FullProfPcrError(
            f"{path}: line {nxt.number} declares NPATT {count} — a joint "
            f"refinement over {count} patterns. That is a different layout "
            f"throughout (per-pattern control lines, backgrounds, excluded "
            f"regions and profile blocks, one set of atoms), and choosing which "
            f"bank's resolution function to return is a question the file does "
            f"not answer. Single-pattern .pcr files only.")

    _, control = cur.ints("the Job/Npr/Nph control line",
                          expect=len(_CONTROL_FIELDS))
    model.control = dict(zip(_CONTROL_FIELDS, control, strict=True))

    job = model.control["job"]
    if job not in (0, 1):
        kind = {-1: "neutron time-of-flight", -2: "energy-dispersive X-ray",
                2: "energy-dispersive X-ray", 3: "neutron time-of-flight"}
        named = kind.get(job, "a job this reader does not know")
        raise FullProfPcrError(
            f"{path}: Job = {job} ({named}). rietx models "
            f"constant-wavelength diffraction only: a TOF pattern's abscissa is "
            f"microseconds, and its whole profile block is Sig-2/Sig-1/Sig-0 and "
            f"alpha0/beta0/alpha1 in place of Caglioti U/V/W. Job 0 (X-ray) and "
            f"Job 1 (neutron CW) are read.")
    for name, why in _MUST_BE_ZERO.items():
        if model.control[name] != 0:
            raise FullProfPcrError(
                f"{path}: control-line field {name.capitalize()} = "
                f"{model.control[name]}, and this reader only handles 0, because "
                f"{why}. No file it was written against states a non-zero value, "
                f"so reading on would be a guess at the layout.")
    # A negative count is not "none of them": `range(-1)` is empty, so an
    # excluded-region block declared negative would leave its lines to be
    # reinterpreted by whatever reads next. Refused rather than clamped.
    if model.control["nex"] < 0:
        raise FullProfPcrError(
            f"{path}: Nex = {model.control['nex']} — an excluded-region count "
            f"cannot be negative")
    if model.control["nph"] < 1:
        raise FullProfPcrError(
            f"{path}: Nph = {model.control['nph']} — a .pcr with no phase states "
            f"no model to read")
    nba = model.control["nba"]
    if nba < 2:
        raise FullProfPcrError(
            f"{path}: Nba = {nba}. Only an interpolated background of two or "
            f"more points is evidenced here (51 points in crwo6002_momcomp, 32 "
            f"in 300q-1p5K_1); Nba 0 or 1 selects a polynomial or a debye/"
            f"Fourier background whose coefficient line's *position* in the "
            f"single-pattern layout no file establishes, and a negative Nba "
            f"selects a background model this reader does not know.")

    _, output = cur.ints("the Ipr/Ppl output-control line",
                         expect=len(_OUTPUT_FIELDS))
    model.output = dict(zip(_OUTPUT_FIELDS, output, strict=True))

    _, pattern = cur.floats("the Lambda1/Lambda2 line",
                            at_least=len(_PATTERN_FIELDS))
    model.pattern = dict(zip(_PATTERN_FIELDS, pattern[:len(_PATTERN_FIELDS)],
                             strict=True))
    _, cycles = cur.floats("the NCY/Eps/Thmin line", at_least=len(_CYCLE_FIELDS))
    model.cycles = dict(zip(_CYCLE_FIELDS, cycles[:len(_CYCLE_FIELDS)],
                            strict=True))

    # The background points carry their codeword *inline* as the third column,
    # unlike the atom and profile blocks. Read as `Nba` lines exactly, and the
    # count is the invariant rather than something the loop is trusted for: a
    # dropped point moves the interpolated background under every peak it spans.
    for i in range(nba):
        _, numbers = cur.floats(f"background point {i + 1} of {nba}", at_least=2)
        codeword = numbers[2] if len(numbers) > 2 else None
        model.background.append(
            (numbers[0], Value(value=numbers[1], codeword=codeword)))
    if len(model.background) != nba:  # pragma: no cover - the loop is exact
        raise FullProfPcrError(
            f"{path}: parsed {len(model.background)} background points from a "
            f"declared Nba = {nba}")

    for i in range(model.control["nex"]):
        _, numbers = cur.floats(
            f"excluded region {i + 1} of {model.control['nex']}", at_least=2)
        model.excluded_regions.append((numbers[0], numbers[1]))

    count_line, counts = cur.floats("the refined-parameter count", at_least=1)
    if not float(counts[0]).is_integer():
        raise FullProfPcrError(
            f"{path}: line {count_line.number}: refined-parameter count "
            f"{counts[0]!r} is not an integer")
    model.refined_parameter_count = int(counts[0])

    # Value and codeword interleaved on one line: zero, SyCos, SySin, Lambda.
    zero_line, zero = cur.floats("the Zero/SyCos/SySin/Lambda line", at_least=8)
    model.zero_shift = {
        name: Value(value=zero[2 * i], codeword=zero[2 * i + 1])
        for i, name in enumerate(_ZERO_FIELDS)}
    if len(zero) > 8 and zero[8] != 0:
        raise FullProfPcrError(
            f"{path}: line {zero_line.number}: MORE = {zero[8]!r} on the "
            f"zero-shift line, which adds instrument lines whose position no "
            f"file here establishes")

    for index in range(1, model.control["nph"] + 1):
        model.phases.append(_read_phase(cur, path, index))
    if len(model.phases) != model.control["nph"]:  # pragma: no cover
        raise FullProfPcrError(
            f"{path}: parsed {len(model.phases)} phases from a declared "
            f"Nph = {model.control['nph']}")

    # Trap 1, recorded rather than trusted: the R_Bragg comments are attached in
    # *file order*, and the index each one claims is kept beside it so a consumer
    # can see the disagreement instead of inheriting it.
    for phase, (labelled, r_bragg) in zip(model.phases, r_braggs, strict=False):
        phase.labelled_index, phase.r_bragg = labelled, r_bragg

    _read_trailing(cur, path, model)
    # Decode every codeword now rather than lazily. A garbled one — a truncated
    # `601.0` reading as `6` — decodes to parameter 0, which is not a number any
    # FullProf run writes; refusing it here means the refusal names the *file*,
    # which `io/CLAUDE.md` requires, instead of surfacing from whatever consumer
    # first touched `Value.code`.
    try:
        model.parameter_numbers  # noqa: B018 - the decode is the point
    except FullProfPcrError as exc:
        raise FullProfPcrError(f"{path}: {exc}") from exc
    return model


def _read_phase(cur: _Cursor, path: Path, index: int) -> FullProfPhase:
    """One phase block, walked positionally.

    The order is the file's and every count is asserted: name, control line,
    space group, the magnetic symmetry sub-block where ``Isy < 0``, ``Nat``
    atoms, four profile blocks, then ``Nvk`` propagation vectors. There is no
    keyword to resynchronise on, so a surprise anywhere here is a refusal.
    """
    name_line = cur.take(f"the name of phase {index}")
    phase = FullProfPhase(index=index, name=name_line.text)

    _, control = cur.floats(f"phase {index} ({phase.name}) control line",
                            at_least=len(_PHASE_FIELDS))
    phase.control = dict(zip(_PHASE_FIELDS, control[:len(_PHASE_FIELDS)],
                             strict=True))
    where = f"{path}: phase {index} ({phase.name!r})"

    jbt = phase.jbt
    if jbt not in (0, 1):
        raise FullProfPcrError(
            f"{where}: Jbt = {jbt}. Only Jbt 0 (nuclear) and Jbt 1 (magnetic) "
            f"are evidenced here; the others select Le Bail intensity "
            f"extraction, a combined nuclear+magnetic phase or a form-factor "
            f"phase, each of which changes the atom block's own layout.")
    # `Ang` when Jbt = 0, `Mom` when Jbt = 1 — one column, two header words
    # (trap 2). A nuclear phase's non-zero `Ang` opens an angle-restraint block
    # whose position nothing here establishes; a magnetic phase's `Mom` is the
    # declared soft-moment-constraint count and adds no line to *this* block.
    ang_or_mom = int(phase.control["ang_or_mom"])
    for name, why in (
            ("dis", "distance-restraint lines follow it"),
            ("str", "a strain-model block follows it"),
            ("furth", "further-parameter lines follow it"),
            ("more", "additional per-phase lines follow it")):
        if int(phase.control[name]) != 0:
            raise FullProfPcrError(
                f"{where}: {name.capitalize()} = {int(phase.control[name])} and "
                f"{why}, at a position no file this reader was written against "
                f"establishes")
    if jbt == 0 and ang_or_mom != 0:
        raise FullProfPcrError(
            f"{where}: Ang = {ang_or_mom} and angle-restraint lines follow it, "
            f"at a position no file here establishes")
    if int(phase.control["irf"]) not in (0, -1):
        raise FullProfPcrError(
            f"{where}: Irf = {int(phase.control['irf'])}, which reads the "
            f"reflection list from a companion file rather than generating it "
            f"from the atoms — so the model this reader would return is not the "
            f"model that was refined")

    sg_line = cur.take(f"phase {index} space-group symbol")
    phase.space_group_raw = sg_line.text
    phase.space_group = normalize_space_group(sg_line.text)

    isy = phase.isy
    if jbt == 1 and isy not in (-1, -2):
        raise FullProfPcrError(
            f"{where}: a magnetic phase (Jbt 1) with Isy = {isy}. The magnetic "
            f"sub-grammar is selected by Isy and only -1 (SYMM/MSYM pairs) and "
            f"-2 (SYMM/BASR/BASI triples) are evidenced here")
    if jbt == 0 and isy != 0:
        raise FullProfPcrError(
            f"{where}: a nuclear phase (Jbt 0) with Isy = {isy}, which supplies "
            f"the symmetry operators explicitly instead of deriving them from "
            f"the space-group symbol — a block no file here states the shape of")
    if isy != 0:
        phase.magnetic = _read_magnetic_symmetry(cur, where, isy)

    nat = int(phase.control["nat"])
    if nat < 0 or phase.nvk < 0:
        # `range(-1)` is empty, so a negative count reads as "none" and leaves
        # the block's lines to be reinterpreted by whatever comes next.
        raise FullProfPcrError(
            f"{where}: Nat = {nat}, Nvk = {phase.nvk} — neither count can be "
            f"negative")
    for i in range(nat):
        phase.atoms.append(
            _read_magnetic_atom(cur, where, i + 1, nat) if jbt == 1
            else _read_nuclear_atom(cur, where, i + 1, nat))
    # A dropped site is a silently wrong structure factor, so the count is an
    # invariant rather than something the walk is trusted to get right — the
    # TOPAS reader's rule, and it costs nothing to restate here.
    if len(phase.atoms) != nat:  # pragma: no cover - the loop is exact
        raise FullProfPcrError(
            f"{where}: parsed {len(phase.atoms)} atoms from a declared Nat = {nat}")

    scale, phase.strain_model = _block(
        cur, _SCALE_COLUMNS, f"phase {index} scale/shape line", trailing=1)
    width, phase.size_model = _block(
        cur, _WIDTH_COLUMNS, f"phase {index} U/V/W width line", trailing=1)
    phase.cell, _ = _block(cur, _CELL_COLUMNS, f"phase {index} cell line")
    asym, _ = _block(cur, _ASYM_COLUMNS, f"phase {index} Pref/Asy line")
    phase.profile = {**scale, **width, **asym}

    # Nvk propagation vectors, one value line and one codeword line each,
    # positioned after the Pref/Asy block. Evidenced by exactly one file
    # (`300q-1p5K_1.pcr`:129-131, Nvk = 1) whose phase happens to be the last,
    # so the *position* rests on one observation and is said to.
    for i in range(phase.nvk):
        _, k = cur.floats(f"phase {index} propagation vector {i + 1}",
                          at_least=3, leading=True)
        _, codes = cur.floats(
            f"phase {index} propagation vector {i + 1} codewords", at_least=3,
            leading=True)
        phase.propagation_vectors.append(
            (tuple(k[:3]), tuple(Value(value=k[j], codeword=codes[j])
                                 for j in range(3))))
    return phase


def _labelled(cur: _Cursor, keyword: str, what: str, where: str) -> str:
    """A ``SYMM``/``MSYM`` line, verbatim, with its label checked.

    Verbatim because nothing here models a magnetic symmetry operator: carrying
    a parsed form would be a claim about an algebra this package does not have.
    The label is still checked, because it is the only thing that says the walk
    is still where it thinks it is — a `.pcr` has no other landmark.
    """
    line = cur.take(what)
    if not line.text.upper().startswith(keyword):
        raise FullProfPcrError(
            f"{where}: line {line.number}: expected a {keyword} line, found "
            f"{line.text!r}")
    return line.text


def _keyworded(cur: _Cursor, keyword: str, what: str, where: str,
               count: int) -> list:
    """A ``BASR``/``BASI`` line: the keyword, then exactly ``count`` numbers.

    The keyword is **checked**, not skipped. It is the one place a ``.pcr``
    labels a line, and the label is what says whether the numbers are the real
    or the imaginary part of the basis vector; reading past it on trust would
    let a file with the pair in the other order arrive silently transposed.
    """
    line = cur.take(what)
    tokens = line.text.split()
    if not tokens or tokens[0].upper() != keyword:
        raise FullProfPcrError(
            f"{where}: line {line.number}: expected a {keyword} line, found "
            f"{line.text!r}")
    numbers: list[float] = []
    for token in tokens[1:]:
        try:
            numbers.append(float(token))
        except ValueError as exc:
            raise FullProfPcrError(
                f"{where}: line {line.number}: {token!r} is not a number in "
                f"{line.text!r}") from exc
    if len(numbers) < count:
        # 3 * N_Bas is the invariant: three components per basis vector, so a
        # short line means the declared N_Bas and the written vectors disagree.
        raise FullProfPcrError(
            f"{where}: line {line.number}: {keyword} states {len(numbers)} "
            f"numbers where 3 x N_Bas = {count} are declared")
    return numbers[:count]


def _read_magnetic_symmetry(cur: _Cursor, where: str, isy: int) -> MagneticSymmetry:
    """The ``Isy < 0`` sub-block, in whichever of the two spellings it uses.

    Every count is asserted because this is the one block the reader has to walk
    *past* without modelling: it must land on the next phase's first line
    exactly, and a `.pcr` offers nothing to resynchronise on. The two shapes and
    their evidence are in :class:`MagneticSymmetry`'s docstring.
    """
    if isy == -1:
        _, header = cur.ints("the Nsym/Cen/Laue/MagMat line", expect=4)
        nsym, cen, laue, magmat = header
        block = MagneticSymmetry(isy=isy, nsym=nsym, cen=cen, laue=laue,
                                 magmat=magmat)
        for i in range(nsym):
            symm = _labelled(cur, "SYMM", f"SYMM {i + 1} of {nsym}", where)
            msyms = [_labelled(cur, "MSYM", f"MSYM {j + 1} of SYMM {i + 1}", where)
                     for j in range(max(magmat, 1))]
            block.operators.append((symm, tuple(msyms)))
        return block

    _, header = cur.ints("the Nsym/Cen/Laue/Ireps/N_Bas line", expect=5)
    nsym, cen, laue, ireps, n_bas = header
    if ireps >= 0:
        raise FullProfPcrError(
            f"{where}: Ireps = {ireps}. Only a negative Ireps — basis vectors "
            f"given explicitly — is evidenced here; a positive one names an "
            f"irreducible representation from FullProf's own tables, which this "
            f"reader has no copy of and may not reproduce.")
    block = MagneticSymmetry(isy=isy, nsym=nsym, cen=cen, laue=laue,
                             ireps=ireps, n_bas=n_bas)
    # The indicator line carries one flag per basis vector: `0 0 0 0` for
    # N_Bas = 4 (crwo6002_BV2andBV4.pcr:148), a single `0` for N_Bas = 1
    # (300q-1p5K_1.pcr:101). The count is what pins the reading.
    _, indicators = cur.ints("the Real(0)/Imaginary(1) indicator line",
                             expect=n_bas)
    block.real_imaginary = tuple(indicators)
    # Each BASR/BASI line holds 3 * N_Bas numbers — three components per basis
    # vector — and there are |Ireps| pairs per SYMM. Both counts are asserted:
    # `crwo6002_G5_nc.pcr` has Nsym 3, Ireps -2, N_Bas 4 (3 x 5 = 15 lines,
    # 12 numbers each) and `300q-1p5K_1.pcr` has Nsym 2, Ireps -1, N_Bas 1
    # (2 x 3 = 6 lines, 3 numbers each), which is what makes the rule a rule
    # rather than one file's coincidence.
    for i in range(nsym):
        symm = _labelled(cur, "SYMM", f"SYMM {i + 1} of {nsym}", where)
        basis: list = []
        for j in range(abs(ireps)):
            real = _keyworded(cur, "BASR", f"BASR {j + 1} of SYMM {i + 1}",
                              where, 3 * n_bas)
            imaginary = _keyworded(cur, "BASI", f"BASI {j + 1} of SYMM {i + 1}",
                                   where, 3 * n_bas)
            basis.append((tuple(real), tuple(imaginary)))
        block.operators.append((symm, tuple(basis)))
    return block


def _atom_floats(tokens: list, value_names: tuple, where: str,
                 line: _Line) -> list:
    """Parse an atom line's numeric tokens, naming the column a bad one sits in.

    Finding 4, the TOPAS reader's rigor: a *stated* site value that cannot be
    read is refused naming **which** column it was, not merely that some token on
    the line is not a number. A positional format cannot silently default a value
    the way a TOPAS ``.inp`` fell back on ``c["a"]`` — the token is always
    refused — so what naming the column buys is a reviewer being able to see
    whether it was ``x``, the ``occ`` or a trailing flag, rather than counting
    tokens by hand. Positions past the named columns are the trailing integer
    flags (``In Fin N_t Spc``), named generically.
    """
    numbers: list[float] = []
    for j, token in enumerate(tokens):
        try:
            numbers.append(float(token))
        except ValueError as exc:
            col = (f"{value_names[j]!r}" if j < len(value_names)
                   else f"trailing integer {j - len(value_names) + 1}")
            raise FullProfPcrError(
                f"{where}: line {line.number}: {token!r} is not a number for the "
                f"{col} column in {line.text!r} — a stated site value that "
                f"cannot be read is refused, never defaulted") from exc
    return numbers


def _read_nuclear_atom(cur: _Cursor, where: str, i: int, nat: int) -> FullProfAtom:
    """One nuclear site: a value line, a codeword line, and ``N_t``'s extras."""
    line = cur.take(f"atom {i} of {nat}")
    tokens = line.text.split()
    if len(tokens) < 2 + len(_ATOM_COLUMNS):
        raise FullProfPcrError(
            f"{where}: line {line.number}: an atom line needs a label, a "
            f"species and {len(_ATOM_COLUMNS)} numbers; found {len(tokens)} "
            f"tokens in {line.text!r}")
    numbers = _atom_floats(tokens[2:], _ATOM_COLUMNS, where, line)
    _, codewords = cur.floats(f"atom {i} codewords", at_least=1)
    atom = FullProfAtom(
        label=tokens[0], species_raw=tokens[1],
        species=normalize_species(tokens[1]),
        values=_row(_ATOM_COLUMNS, numbers, codewords),
        flags=tuple(numbers[len(_ATOM_COLUMNS):]))
    extra = _N_T_EXTRA_LINES.get(atom.n_t)
    if extra is None:
        raise FullProfPcrError(
            f"{where}: atom {atom.label!r} declares N_t = {atom.n_t}, and how "
            f"many lines that adds to the site is not established by any file "
            f"this reader was written against. Guessing it would desynchronise "
            f"every line after this one (N_t 0 and 2 are read).")
    if extra:
        _, betas = cur.floats(f"atom {i} anisotropic betas",
                              at_least=len(_BETA_COLUMNS))
        _, beta_codes = cur.floats(f"atom {i} beta codewords", at_least=1)
        atom.betas = _row(_BETA_COLUMNS, betas, beta_codes)
    return atom


def _read_magnetic_atom(cur: _Cursor, where: str, i: int, nat: int) -> FullProfAtom:
    """One magnetic site: **four** lines, values and codewords twice over.

    The moment columns are ``Rx Ry Rz`` / ``Ix Iy Iz`` under ``Isy = -1`` and
    basis-vector coefficients ``C1..C9`` under ``Isy = -2`` — the same
    positions, so they are read under the neutral names of
    :data:`_MAGNETIC_COLUMNS`. Nothing here models them; the point of reading
    them is that :attr:`FullProfModel.magnetic_phases` can *say* what it read,
    which is the alternative to dropping the phase.
    """
    line = cur.take(f"magnetic atom {i} of {nat}")
    tokens = line.text.split()
    # label, species, Mag, Vek, then the eight columns. `Mag` and `Vek` are
    # integer selectors (which magnetic form factor, which propagation vector)
    # and carry no codeword, so they sit with the label rather than in the row.
    if len(tokens) < 4 + len(_MAGNETIC_COLUMNS):
        raise FullProfPcrError(
            f"{where}: line {line.number}: a magnetic atom line needs a label, "
            f"a species, Mag, Vek and {len(_MAGNETIC_COLUMNS)} numbers; found "
            f"{len(tokens)} tokens in {line.text!r}")
    numbers = _atom_floats(tokens[2:], ("Mag", "Vek") + _MAGNETIC_COLUMNS,
                           where, line)
    _, codewords = cur.floats(f"magnetic atom {i} codewords", at_least=1)
    _, continuation = cur.floats(f"magnetic atom {i} continuation",
                                 at_least=len(_MAGNETIC_CONTINUATION))
    _, continuation_codes = cur.floats(
        f"magnetic atom {i} continuation codewords", at_least=1)
    values = _row(_MAGNETIC_COLUMNS, numbers[2:], codewords)
    values.update(_row(_MAGNETIC_CONTINUATION, continuation, continuation_codes))
    return FullProfAtom(label=tokens[0], species_raw=tokens[1],
                        species=normalize_species(tokens[1]), values=values,
                        flags=tuple(numbers[:2]))


def _read_trailing(cur: _Cursor, path: Path, model: FullProfModel) -> None:
    """The lines after the last phase: soft moment constraints and the 2θ range.

    Two productions share this region and they are told apart by whether the
    line **opens with a number**, which is a structural difference rather than a
    sniff: the fitted-range line is three numbers
    (``9.000 157.000 1``, ``crwo6002_momcomp.pcr``:177) and a soft moment
    constraint opens with a site key that is not one (``CR``, ``1C``).

    The constraints are attached to the last phase, which is where every real
    file puts them; a *non-final* phase declaring ``Mom > 0`` is refused above,
    because nothing here establishes where its block would sit. The declared
    ``Mom`` and the number of lines found are both recorded and neither is
    corrected into the other — they disagree in ``crwo6002_G5_nc.pcr``, which
    declares ``Mom = 1`` and writes two constraints.
    """
    last = model.phases[-1]
    ranges: list[tuple] = []
    for line in cur.remaining():
        tokens = line.text.split()
        try:
            float(tokens[0])
        except ValueError:
            if len(tokens) < 3:
                raise FullProfPcrError(
                    f"{path}: line {line.number}: {line.text!r} follows the "
                    f"last phase and is neither a fitted-range line (three "
                    f"numbers) nor a soft moment constraint (a site key, a "
                    f"moment and a sigma)") from None
            try:
                moment, sigma = float(tokens[1]), float(tokens[2])
            except ValueError as exc:
                raise FullProfPcrError(
                    f"{path}: line {line.number}: {line.text!r} looks like a "
                    f"soft moment constraint but its moment/sigma do not "
                    f"parse") from exc
            # One production, not two: both real spellings are an atom label
            # truncated to the field's width, so the key is resolved by prefix
            # and an unresolvable one is *reported* as unresolved rather than
            # guessed at. See SoftMomentConstraint's docstring.
            matches = [j for j, atom in enumerate(last.atoms)
                       if atom.label.startswith(tokens[0])]
            last.soft_moment_constraints.append(SoftMomentConstraint(
                key=tokens[0], moment=moment, sigma=sigma,
                atom_index=matches[0] if len(matches) == 1 else None))
            continue
        numbers = []
        for token in tokens:
            try:
                numbers.append(float(token))
            except ValueError:
                break
        if len(numbers) < 2:
            raise FullProfPcrError(
                f"{path}: line {line.number}: {line.text!r} follows the last "
                f"phase and states fewer than two numbers, so it is neither a "
                f"fitted 2theta range nor anything else this reader knows")
        ranges.append(tuple(numbers[:3]))
    if len(ranges) > 1:
        raise FullProfPcrError(
            f"{path}: {len(ranges)} fitted-range lines follow the last phase, "
            f"and a single-pattern .pcr states one")
    model.fitted_range = ranges[0] if ranges else None


# ------------------------------------------------------------- to_structure


#: How far the per-site occupancy ratios may spread and still be called
#: constant. The corpus states ``Occ`` to five decimals — ``0.16667`` for 1/6 —
#: so the ratios carry ~2e-5 of rounding; the origin-choice error this gate
#: exists to catch is a **factor of two**. Anything between is a real partial
#: occupancy, and a real partial occupancy is refused rather than rounded off.
_OCCUPANCY_RTOL = 5e-3


def occupancy_factor(phase: FullProfPhase, where: str | None = None) -> float:
    """The common factor FullProf's ``Occ`` column carries, or a refusal.

    FullProf's ``Occ`` is the chemical occupancy times the site multiplicity
    over the general multiplicity, and the *absolute* normalisation of the
    column is degenerate with the phase scale — doubling every ``Occ`` and
    halving ``Scale`` is the same pattern, which is why the corpus carries a
    factor of 2 on the Cr₂WO₆ files and 1 on the Co₃O₄ and YAG ones.

    So ``Occ_i × M_general / M_i`` is the site occupancy up to one unknown
    common factor. Where it is the *same* for every site the phase is fully
    occupied, the factor cancels, and every rietx ``occ`` is 1.0 — which is the
    only case a chemical occupancy is recoverable in. Where it is not, the
    factor and the partial occupancies are not separable and the phase is
    refused, naming the ratios: handing the column through would be a silently
    wrong structure factor.

    Returns the common factor, for the record.
    """
    import gemmi
    import numpy as np

    from ...crystallography.symmetry import expand_positions

    where = where or f"phase {phase.index} ({phase.name!r})"
    try:
        sg = gemmi.SpaceGroup(phase.space_group)
    except Exception as exc:
        raise FullProfPcrError(
            f"{where}: space group {phase.space_group_raw!r} (read as "
            f"{phase.space_group!r}) is not one gemmi resolves: {exc}") from exc
    if not phase.atoms:
        raise FullProfPcrError(
            f"{where}: the phase states Nat = 0, so it has no sites to build a "
            f"structure factor from — and dropping it would leave its R_Bragg "
            f"reporting for a phase the Structure lacks")
    general = len(list(sg.operations()))
    ratios: list[float] = []
    for atom in phase.atoms:
        xyz = np.array([atom.values[k].value for k in ("x", "y", "z")], float)
        multiplicity = len(expand_positions(sg, xyz))
        ratios.append(atom.values["occ"].value * general / multiplicity)
    reference = max(ratios, key=abs)
    if reference == 0.0 or any(
            abs(r - reference) > _OCCUPANCY_RTOL * abs(reference) for r in ratios):
        stated = ", ".join(f"{a.label}={r:.4f}"
                           for a, r in zip(phase.atoms, ratios, strict=True))
        raise FullProfPcrError(
            f"{where}: FullProf's Occ column does not reduce to one chemical "
            f"occupancy. Occ x M_general/M_site is [{stated}] under "
            f"{phase.space_group!r}, and those must agree for the arbitrary "
            f"common factor to cancel — FullProf's Occ normalisation is "
            f"degenerate with the phase scale, so a partial occupancy is not "
            f"separable from it. Unequal ratios mean either a genuinely "
            f"partially occupied phase, whose chemical occupancies are not in "
            f"the file, or the wrong origin choice for this symbol. Read "
            f"`phase.atoms[i].values['occ']` for what the file does state.")
    return reference


def to_structure(model: FullProfModel, *, nuclear_only: bool = False):
    """Build a :class:`~rietx.schemas.Structure` from a parsed ``.pcr``.

    ``Biso`` is FullProf's B and rietx's ``biso`` is also B — no 8π²
    conversion. The cell, the coordinates, the displacement parameters and the
    scale all carry the file's own refine flags, decoded from the codewords.

    Four refusals, each naming what it would otherwise have dropped:

    * **A magnetic phase.** rietx has no magnetic scattering model, so returning
      the nuclear phases alone would hand back a structure that looks complete
      while the file's magnetic contribution — and its R_Bragg — went
      unmentioned. ``nuclear_only=True`` is how a caller *declares* it wants the
      nuclear subset; the omission is then the caller's, and named in the
      message this refusal replaces.
    * **A negative ``Biso``.** ``300q-1p5K_1.pcr``'s O1 refined to −0.67266 Å²,
      which is a real FullProf outcome (the column absorbs absorption and
      normalisation error). rietx bounds ``biso`` at zero, and clamping −0.67 to
      0 changes every high-Q intensity — a *contradiction*, not the kind of
      small deviation root CLAUDE.md licenses a reader to repair silently.
    * **An anisotropic β block.** The β → U^ij conversion needs a convention no
      file here settles (whether the stored off-diagonal already carries the
      exponent's factor of 2), and a wrong factor is a silently wrong
      Debye-Waller factor.
    * **An occupancy column that does not reduce** — see
      :func:`occupancy_factor`.

    ``Scale`` is carried through **verbatim** as a starting value and a refine
    flag, and is *not* comparable with a rietx scale: FullProf's folds ``ATZ``,
    the occupancy normalisation above and its own profile normalisation into one
    number.
    """
    import rietx as rx

    magnetic = model.magnetic_phases
    if magnetic and not nuclear_only:
        named = ", ".join(f"{ph.index}:{ph.name!r} (Jbt {ph.jbt}, Isy {ph.isy}, "
                          f"{len(ph.atoms)} sites)" for ph in magnetic)
        raise FullProfPcrError(
            f"{model.path or '<model>'}: {len(magnetic)} of {len(model.phases)} "
            f"phases are magnetic and rietx has no magnetic scattering model: "
            f"{named}. Returning only the nuclear phases would hand back a "
            f"structure that looks complete while those phases' contribution "
            f"went unmentioned. Read `model.magnetic_phases` for what the file "
            f"states about them, or pass nuclear_only=True to declare that the "
            f"nuclear subset is what you want.")

    phases = []
    for ph in model.nuclear_phases:
        where = f"{model.path or '<model>'}: phase {ph.index} ({ph.name!r})"
        missing = [k for k in _CELL_COLUMNS if k not in ph.cell]
        if missing:
            raise FullProfPcrError(
                f"{where}: the cell line states no {', '.join(missing)}, so this "
                f"phase cannot be built — and dropping it would leave its "
                f"R_Bragg reporting for a phase the Structure lacks")
        for atom in ph.atoms:
            if atom.betas:
                raise FullProfPcrError(
                    f"{where}: atom {atom.label!r} carries an anisotropic beta "
                    f"block (N_t = {atom.n_t}). Converting FullProf's beta_ij "
                    f"to rietx's U^ij needs a convention no file here settles — "
                    f"whether the stored off-diagonal already carries the "
                    f"exponent's factor of 2 — and a wrong factor is a silently "
                    f"wrong Debye-Waller factor at high Q. Read "
                    f"`atom.betas` for what the file states.")
            biso = atom.values["biso"].value
            if biso < 0.0:
                raise FullProfPcrError(
                    f"{where}: atom {atom.label!r} has Biso = {biso}, and rietx "
                    f"bounds biso at zero. A negative B is a real FullProf "
                    f"outcome — the column absorbs absorption and normalisation "
                    f"error — but clamping it to zero changes every high-Q "
                    f"intensity, so it is a contradiction rather than a "
                    f"deviation a reader may repair. Read "
                    f"`atom.values['biso'].value` for the file's own number.")
        # The occupancy check is also what verifies `normalize_space_group`'s
        # origin choice: a wrong origin gives wrong multiplicities, so the
        # ratios stop agreeing and the phase is refused rather than returned.
        occupancy_factor(ph, where)

        def _p(value: Value, **kw):
            """One rietx Parameter carrying the file's own refine flag."""
            if (free := value.vary) is not None:
                kw["vary"] = free
            return rx.Parameter(value=value.value, **kw)

        cell = rx.Cell(**{
            name: _p(ph.cell[key])
            for name, key in zip(("a", "b", "c", "alpha", "beta", "gamma"),
                                 _CELL_COLUMNS, strict=True)})
        atoms = [
            rx.Atom(label=atom.label, species=atom.species,
                    x=_p(atom.values["x"]), y=_p(atom.values["y"]),
                    z=_p(atom.values["z"]),
                    # Fully occupied, verified above; the file's own Occ is a
                    # multiplicity-scaled quantity and stays on the model.
                    occ=rx.Parameter(value=1.0, min=0.0, max=1.5),
                    biso=_p(atom.values["biso"], min=0.0, max=25.0))
            for atom in ph.atoms]
        scale = ph.profile.get("scale")
        try:
            phases.append(rx.Phase(
                name=ph.name, space_group=ph.space_group, cell=cell, atoms=atoms,
                scale=rx.Parameter(
                    value=1e-4 if scale is None else scale.value, min=0.0,
                    transform="softplus",
                    **({} if scale is None or scale.vary is None
                       else {"vary": scale.vary}))))
        except FullProfPcrError:
            raise
        except Exception as exc:
            # Every schema refusal is converted at this boundary: a reader raises
            # naming the file, and pydantic's report names a field.
            raise FullProfPcrError(f"{where}: {exc}") from exc
    if not phases:
        raise FullProfPcrError(
            f"{model.path or '<model>'}: no nuclear phase to build. The file "
            f"states {len(model.phases)} phase(s), all magnetic — read "
            f"`model.magnetic_phases` for what it does say about them.")
    try:
        return rx.Structure(phases=phases)
    except Exception as exc:
        raise FullProfPcrError(f"{model.path or '<model>'}: {exc}") from exc
