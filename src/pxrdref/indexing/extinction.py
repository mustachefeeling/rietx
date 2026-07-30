"""Extinction-symbol determination: which systematic absences the pattern shows.

:func:`determine_extinction_symbol` takes an indexed lattice and the pattern it
came from and returns a **ranked list of extinction classes**, each listing the
space groups it contains.  It closes the ``index → space group → Le Bail →
Rietveld`` workflow, and its founding rule is the FitReport's one rank up, in its
sharpest form:

**The observable is the extinction symbol, not the space group.**  Only
systematic absences reach a powder pattern, so every space group sharing an
absence set produces an *identical* pattern — centrosymmetric/non-centro\
symmetric pairs, enantiomorphs, and the mirror that separates ``P 63`` from
``P 63/m`` are all invisible here **by construction, not for want of counting
time**.  So :class:`~pxrdref.schemas.indexing.ExtinctionCandidate` carries a
``space_groups`` *list*, ``EXTINCTION_GROUPS_NOT_SEPARABLE`` fires whenever it
holds more than one, and nothing in this module can return one space group.

**The classes are derived, never transcribed.**  Every gemmi setting whose
lattice matches the candidate is enumerated, its absence set is computed over the
hkl in range with ``ops.systematic_absences``, and the settings are grouped by
*identical* absence sets — the same discipline as ``wyckoff._compatible_lattice``
and ``stephens.strain_basis``.  It is therefore automatically right in
non-standard settings, which a transcription of *International Tables* A Table
3.2 is not: with the axes fixed by indexing, ``P n m a`` and ``P m n b`` are
different hypotheses about *this* cell, and both are enumerated.

**Three measured decisions shape the rest.**

1. *Count lines, not orbits.*  Two orbits routinely land at one 2θ (WP-1020's
   ``predicted_lines`` fix), and two reflections at one position are one
   observation and one Le Bail intensity.  Every count here — ``n_lines``,
   ``n_absent``, and the ``n_added`` of the nested comparison — is over distinct
   *positions*, which also makes the comparison immune to a class representative
   whose Laue group splits orbits more finely than the holohedry does.
2. *An absence you cannot see is not evidence.*  ``n_added`` counts only the
   **testable** forbidden lines: inside the fitted range, and separated from
   every line the class still allows by ``model.forward._overlap_groups``' own
   FWHM criterion.  Without this, a class whose extra absences all hide under
   allowed neighbours wins on parsimony alone — ΔBIC = −n·ln N with no
   measurement behind it — which is exactly the confident wrong singleton this
   milestone exists to prevent.
3. *Direct absence evidence refutes; the fit only ranks.*  A forbidden position
   carrying net intensity above the fitted background refutes its class outright,
   and no fit can rescue it, so a refuted class is **not** fitted at all.  That
   is both the epistemics and the cost control: an orthorhombic P screen
   enumerates 71 classes and refutes most of them from one reference fit.

**Scoring is a nested model comparison, not lowest Rwp.**  A class with fewer
absences has more reflections and always fits at least as well, so Rwp ranks the
least-constrained class first every time.  ``report.layer2.delta_bic`` and
``hamilton_justified`` are imported (not reimplemented — they are the same device
Layer 2 uses before adding a parameter) with the *more*-absent class as the
restricted model, and the reported ``delta_bic`` is BIC(class) − BIC(absence-free
lattice): negative favours the class, and the difference between two classes'
values is itself a ΔBIC because both share the reference.

Markvardsen, David, Johnson & Shankland (2001), *Acta Cryst.* **A57**, 47-54 is
the Bayesian formulation of this problem — a full posterior over extinction
symbols from the extracted intensities.  ΔBIC plus direct absence evidence is the
v1.0 form of the same logic; the posterior is a v2 fence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import gemmi
import numpy as np

from ..schemas.indexing import CellCandidate
from .fom import lattice_group

#: ΔBIC below which two classes are **not** separated.  Kass & Raftery (1995),
#: *J. Am. Stat. Assoc.* **90**, 773, call a difference above 10 "very strong"
#: evidence; anything less is reported as an ambiguity rather than resolved,
#: which is the same posture ``ShiftScreen.separable`` takes one module over.
DECISIVE_DELTA_BIC = 10.0

#: Crystal systems that share one *lattice*, keyed by the candidate's system.
#: The powder determines a lattice, not a crystal system: a hexagonal metric
#: carries both the trigonal-P and the hexagonal groups, and the trigonal ones
#: own absence classes (``P 3 c 1``, ``P 31 c``) that the hexagonal ones do not.
#: Excluding them would silently remove real hypotheses.  Every other row is
#: itself — a monoclinic *group* in an orthorhombic cell is pseudosymmetry, which
#: is the Bravais screen's question and not this one's.
_LATTICE_SYSTEMS: dict[str, tuple[str, ...]] = {
    "triclinic": ("triclinic",),
    "monoclinic": ("monoclinic",),
    "orthorhombic": ("orthorhombic",),
    "tetragonal": ("tetragonal",),
    "trigonal": ("trigonal", "hexagonal"),
    "hexagonal": ("hexagonal", "trigonal"),
    "cubic": ("cubic",),
}

_GLIDES = frozenset("abcnde")
_SCREW = re.compile(r"^[2346][1-5]$")
_ROTATION = re.compile(r"^-?[12346]$")


def _is_axis(token: str) -> bool:
    return bool(_ROTATION.match(token) or _SCREW.match(token))


def _is_plane(token: str) -> bool:
    return token == "m" or token in _GLIDES


def _is_position(token: str) -> bool:
    """Is this a readable H-M position — an axis, a plane, or ``axis/plane``?"""
    parts = token.split("/")
    if len(parts) == 2:
        return _is_axis(parts[0]) and _is_plane(parts[1])
    return _is_axis(token) or _is_plane(token)


# ----------------------------------------------------------------------
# enumerating the compatible groups
# ----------------------------------------------------------------------
def _well_formed(sg: gemmi.SpaceGroup) -> bool:
    """Is this a standard H-M setting whose positions can be read?

    gemmi's table carries a handful of CCP4 origin-shifted entries whose symbols
    are not H-M at all — ``P 21212(a)``, ``C 2 2 21a)``, ``I 2 3a``.  They are
    dropped, and dropping them loses nothing: each has the same absence set as
    its standard counterpart (measured over gemmi 0.7.5's whole table), so it
    joins the same class and would only add an unreadable string to
    ``space_groups`` and defeat the symbol derivation, which reads positions.
    """
    tokens = sg.xhm().split(":")[0].split()[1:]
    return bool(tokens) and all(_is_position(t) for t in tokens)


def _unique_axis(cell: tuple[float, ...]) -> str:
    """The monoclinic unique axis, read off the cell rather than assumed.

    The package's conventional monoclinic setting is b-unique (see
    ``fom.lattice_group``), but the setting is a property of the *cell* that
    reaches this function, and enumerating the wrong unique axis would compare a
    ``P 1 21/c 1`` hypothesis against axes it does not refer to.
    """
    devs = [abs(cell[3] - 90.0), abs(cell[4] - 90.0), abs(cell[5] - 90.0)]
    return "abc"[int(np.argmax(devs))] if max(devs) > 1e-6 else "b"


def compatible_groups(system: str, centring: str,
                      cell: tuple[float, ...]) -> list[gemmi.SpaceGroup]:
    """Every gemmi setting whose lattice is this candidate's.

    Filtered by crystal system (through :data:`_LATTICE_SYSTEMS`), by centring,
    and — for monoclinic — by the unique axis the cell itself declares.  The
    rhombohedral-axes settings (``R 3:R``) are excluded because an R lattice
    reaches this package in hexagonal axes; applying one to a hexagonal cell
    describes a different lattice, which is the same class of error as handing a
    Niggli-reduced cell's input centring to a symmetry finder (WP-1024).
    """
    systems = _LATTICE_SYSTEMS.get(system)
    if systems is None:
        raise ValueError(f"unknown crystal system {system!r}")
    axis = _unique_axis(cell)
    out = []
    for sg in gemmi.spacegroup_table():
        if sg.crystal_system_str() not in systems or sg.ext == "R":
            continue
        if sg.centring_type() != (centring or "P"):
            continue
        if sg.crystal_system_str() == "monoclinic" and \
                sg.monoclinic_unique_axis() != axis:
            continue
        if not _well_formed(sg):
            continue
        out.append(sg)
    return out


def _laue_order(sg: gemmi.SpaceGroup) -> int:
    """Order of the Laue group — the point group with inversion added.

    It is what decides how finely reflections split into orbits, so the class
    representative is chosen to maximise it: the reflection list then differs
    from the absence-free lattice's *only* by the absences, which is what makes
    the comparison nested.
    """
    rots = {tuple(map(tuple, op.rot)) for op in sg.operations()}
    return len(rots | {tuple(tuple(-v for v in row) for row in r) for r in rots})


def _order(sg: gemmi.SpaceGroup) -> int:
    """Order of the space group's point group, inversion included.

    gemmi keeps the inversion out of ``sym_ops`` and in ``is_centrosymmetric``,
    so multiplying it back in is what keeps ``P m -3 m`` (48) above ``P 4 3 2``
    (24) — without it the absence-free class's representative comes out as a
    lower-symmetry member, and the reference model would stop being the lattice
    group every other part of the indexer compares against.
    """
    ops = sg.operations()
    return len(ops.sym_ops) * (2 if ops.is_centrosymmetric() else 1)


# ----------------------------------------------------------------------
# the class label
# ----------------------------------------------------------------------
def _absence_token(token: str) -> str:
    """The absence-generating part of one H-M position, or ``"-"``.

    A screw axis and a glide plane extinguish; a rotation, a rotoinversion and a
    mirror do not.  ``63/m`` therefore reduces to ``63`` and ``21/c`` stays whole.
    """
    parts = token.split("/")
    axis = parts[0] if _SCREW.match(parts[0]) else ""
    plane = parts[1] if len(parts) > 1 and parts[1] in _GLIDES else ""
    if not plane and token in _GLIDES:
        plane = token
    if axis and plane:
        return f"{axis}/{plane}"
    return axis or plane or "-"


def extinction_symbol(groups: list[gemmi.SpaceGroup], system: str,
                      centring: str) -> str:
    """An IT-style extinction symbol for a class, **derived** from its members.

    Built from the member carrying the fewest absence-generating elements — the
    one whose symbol is already the extinction symbol, which is IT's own
    convention read backwards — with every non-extinguishing position replaced by
    ``-``.  ``{P 63, P 63/m, P 63 2 2}`` → ``P 63 - -``; ``{P m 21 b, P 2 m b,
    P m m b}`` → ``P - - b``, because the 2₁'s condition is subsumed by the b
    glide's and only the glide is an independent element.  Monoclinic keeps its
    ``1`` placeholders (``P 1 21/c 1``), as IT writes them.

    **A label, not a key.**  It is derived rather than transcribed, so for an
    enantiomorphic pair — ``{P 41 3 2, P 43 3 2}`` — the choice between the two
    screw letters is arbitrary and is made by sorting the derived string;
    ``space_groups`` is the answer, and ``representative`` identifies the class.
    """
    def key(sg: gemmi.SpaceGroup):
        toks = [_absence_token(t) for t in sg.xhm().split(":")[0].split()[1:]]
        return (sum(t != "-" for t in toks), _order(sg), " ".join(toks), sg.number)

    src = min(groups, key=key)
    raw = src.xhm().split(":")[0].split()[1:]
    toks = [t if (system == "monoclinic" and t == "1") else _absence_token(t)
            for t in raw]
    n = 1 if system == "triclinic" else 3
    toks = (toks + ["-"] * n)[:n]
    return " ".join([centring or "P", *toks])


# ----------------------------------------------------------------------
# the reflection conditions
# ----------------------------------------------------------------------
#: Zones (planes through the origin) and axes the conditions are stated on, with
#: the two free indices each is parameterised by.  The list is the *derivation's*
#: vocabulary, not a table of answers: every condition is fitted to the absence
#: set and kept only if it reproduces it exactly.  The unusual-looking entries
#: are the symmetry images a fixed-axis cell makes distinct — ``h-2hl`` is the
#: hexagonal image of ``hhl`` under the threefold, ``hk-k`` a cubic image — and
#: without them a c-glide in ``P 63/m m c`` or an n-glide in ``P m -3 n`` is
#: reported half-explained.
_ZONES = (
    ("0kl", 0, ("k", "l"), (1, 2)),
    ("h0l", 1, ("h", "l"), (0, 2)),
    ("hk0", 2, ("h", "k"), (0, 1)),
    ("hhl", -1, ("h", "l"), (0, 2)),
    ("h-hl", -2, ("h", "l"), (0, 2)),
    ("hkk", -3, ("h", "k"), (0, 1)),
    ("hkh", -4, ("h", "k"), (0, 1)),
    ("hk-k", -5, ("h", "k"), (0, 1)),
    ("hk-h", -6, ("h", "k"), (0, 1)),
    ("h-2hl", -7, ("h", "l"), (0, 2)),
    ("-2hhl", -8, ("k", "l"), (1, 2)),
)
_AXES = (
    ("h00", 3, ("h",), (0,)),
    ("0k0", 4, ("k",), (1,)),
    ("00l", 5, ("l",), (2,)),
    ("hh0", 6, ("h",), (0,)),
    ("hhh", 7, ("h",), (0,)),
)
#: Linear forms tried, simplest first, against moduli 2, 3, 4 and 6.
_FORMS2 = (((1, 0), "{0}"), ((0, 1), "{1}"), ((1, 1), "{0}+{1}"),
           ((1, -1), "{0}-{1}"), ((2, 1), "2{0}+{1}"), ((1, 2), "{0}+2{1}"),
           ((2, -1), "2{0}-{1}"), ((3, 1), "3{0}+{1}"))
_FORMS1 = (((1,), "{0}"),)
_MODULI = (2, 3, 4, 6)


def _zone_mask(hkl: np.ndarray, code: int) -> np.ndarray:
    """Membership of one zone or axis, by the code in :data:`_ZONES`/:data:`_AXES`."""
    h, k, ell = hkl[:, 0], hkl[:, 1], hkl[:, 2]
    return {
        0: h == 0, 1: k == 0, 2: ell == 0,
        -1: h == k, -2: k == -h, -3: k == ell, -4: h == ell,
        -5: k == -ell, -6: h == -ell, -7: k == -2 * h, -8: h == -2 * k,
        3: (k == 0) & (ell == 0), 4: (h == 0) & (ell == 0),
        5: (h == 0) & (k == 0), 6: (h == k) & (ell == 0),
        7: (h == k) & (k == ell),
    }[code]


def _fit_condition(hkl, absent, labels, cols, forms) -> str | None:
    values = [hkl[:, c] for c in cols]
    for coefs, template in forms:
        combo = sum(c * v for c, v in zip(coefs, values))
        for m in _MODULI:
            if np.array_equal(absent, (combo % m) != 0):
                return f"{template.format(*labels)} = {m}n"
    return None


def reflection_conditions(hkl: np.ndarray, absent: np.ndarray
                          ) -> tuple[list[str], bool]:
    """Human-readable conditions for an absence set, and whether they cover it.

    Returns ``(["0kl: k = 2n", …], complete)``.  Every string is *fitted*: the
    modulus rule must reproduce the absences on its zone exactly, or it is not
    reported.  Zones are fitted off-axis (an axis inside a zone carries its own,
    stronger condition — Pbca's ``00l: l = 2n`` is not implied by ``0kl: k = 2n``)
    and a zone equivalent to one already reported is skipped, so the list reads
    like IT's rather than repeating each cubic permutation.

    ``complete`` is False when some absence no fitted rule explains remains.
    Measured over gemmi 0.7.5's whole table, that happens for **1 of 550**
    settings (``C 4 2 21``, a non-standard tetragonal C setting) — but the flag
    travels rather than being assumed away, because the absence set, not this
    prose, is what the screen actually uses.
    """
    absent = np.asarray(absent, dtype=bool)
    on_axis = np.count_nonzero(hkl == 0, axis=1) >= 2
    out: list[str] = []
    explained = np.zeros(len(hkl), dtype=bool)
    for group, forms, is_zone in ((_ZONES, _FORMS2, True),
                                  (_AXES, _FORMS1, False)):
        for name, code, labels, cols in group:
            in_zone = _zone_mask(hkl, code)
            mask = in_zone & ~on_axis if is_zone else in_zone
            if not mask.any() or not absent[mask].any():
                continue
            if not (absent[mask] & ~explained[mask]).any():
                continue                      # a symmetry image of a stated zone
            cond = _fit_condition(hkl[mask], absent[mask], labels, cols, forms)
            if cond is None:
                continue
            out.append(f"{name}: {cond}")
            explained |= mask & absent
            # the rule holds on the zone's own axes too whenever it predicts them
            # correctly — that is what makes an axial condition *implied* rather
            # than independent, and keeps ``P 1 21/c 1`` from reporting
            # ``00l: l = 2n`` beside ``h0l: l = 2n``
            axial = in_zone & on_axis
            if is_zone and axial.any() and _fit_condition(
                    hkl[axial], absent[axial], labels, cols, forms) is not None:
                explained |= axial & absent
    return out, not bool((absent & ~explained).any())


# ----------------------------------------------------------------------
# classes
# ----------------------------------------------------------------------
@dataclass
class AbsenceClass:
    """One extinction class before any fit: its groups, symbol and conditions."""

    symbol: str
    representative: str
    space_groups: list[str]
    conditions: list[str] = field(default_factory=list)
    conditions_complete: bool = True


def absence_classes(candidate: CellCandidate, wavelength: float,
                    two_theta_max: float, two_theta_min: float = 0.0,
                    ) -> list[AbsenceClass]:
    """Group every compatible space group by its absence set over the hkl in range.

    Two classes that differ only outside the measured range are **one class**
    here, and that is the honest statement: the data cannot separate them.  It is
    also why :attr:`ExtinctionScreen.two_theta_range` is part of the answer.

    The representative is the member with the largest Laue group (see
    :func:`_laue_order`); the absence-free class's representative is therefore the
    lattice group itself, which is what makes it the reference model.
    """
    groups = compatible_groups(candidate.system, candidate.centring,
                               candidate.cell)
    if not groups:
        return []
    hkl = _hkl_in_range(candidate.cell, wavelength, two_theta_max, two_theta_min)
    lattice = gemmi.find_spacegroup_by_name(
        candidate.lattice_group or lattice_group(candidate.system,
                                                 candidate.centring))
    allowed = ~np.asarray(lattice.operations().systematic_absences(hkl), dtype=bool)
    hkl_lattice = hkl[allowed]

    buckets: dict[bytes, list[gemmi.SpaceGroup]] = {}
    for sg in groups:
        key = np.asarray(sg.operations().systematic_absences(hkl_lattice),
                         dtype=bool).tobytes()
        buckets.setdefault(key, []).append(sg)

    out = []
    for key, members in buckets.items():
        rep = max(members, key=lambda s: (_laue_order(s), _order(s),
                                          s.is_reference_setting(), -s.number))
        conds, complete = reflection_conditions(
            hkl_lattice, np.frombuffer(key, dtype=bool))
        out.append(AbsenceClass(
            symbol=extinction_symbol(members, candidate.system,
                                     candidate.centring),
            representative=rep.xhm(),
            space_groups=[s.xhm() for s in sorted(members,
                                                  key=lambda s: (s.number,
                                                                 s.xhm()))],
            conditions=conds, conditions_complete=complete))
    return out


def _hkl_in_range(cell, wavelength: float, two_theta_max: float,
                  two_theta_min: float = 0.0) -> np.ndarray:
    """Every integer hkl whose d falls in range — the same box and the same 0.1 %
    boundary slack ``generate_reflections`` uses, so the two enumerations agree."""
    from ..crystallography.lattice import d_spacings

    d_min = wavelength / (2.0 * np.sin(np.radians(max(two_theta_max, 1e-6) / 2.0)))
    ranges = [np.arange(-int(np.floor(x / d_min)) - 1,
                        int(np.floor(x / d_min)) + 2) for x in cell[:3]]
    grid = np.meshgrid(*ranges, indexing="ij")
    hkl = np.column_stack([g.ravel() for g in grid]).astype(np.int64)
    hkl = hkl[~np.all(hkl == 0, axis=1)]
    d = d_spacings(hkl, *cell)
    keep = d >= d_min * 0.999
    if two_theta_min > 0.0:
        d_max = wavelength / (2.0 * np.sin(np.radians(max(two_theta_min, 1e-3)
                                                      / 2.0)))
        keep &= d <= d_max * 1.001
    return hkl[keep]


__all__ = ["DECISIVE_DELTA_BIC", "AbsenceClass", "absence_classes",
           "compatible_groups", "extinction_symbol", "reflection_conditions"]
