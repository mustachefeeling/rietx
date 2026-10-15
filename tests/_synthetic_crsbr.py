"""Forward-modelled CrSBr, k = (0, 0, 1/2): the WP-1343 synthetic k != 0 fixture.

Offered on yue-here/rietx#277 and accepted there.  The patterns come from
rietx's own forward model, with a planted ``magnetic_lor_size``, a planted
moment and Poisson counting noise from a fixed seed.  Nothing here is measured
data; no data file is committed (in-process generation from a seed, the
``_synthetic_silicon.py`` precedent), so the fixture cannot go stale against
the forward model it tests.

**The structure is a named published one.**  A. López-Paz, Z. Guguchia,
V. Y. Pomjakushin, C. Witteveen, A. Cervellino, H. Luetkens, N. Casati,
A. F. Morpurgo and F. O. von Rohr, "Dynamic magnetic crossover at the origin of
the hidden-order in van der Waals antiferromagnet CrSBr", *Nature
Communications* **13**, 4745 (2022), doi:10.1038/s41467-022-32290-4 (CC BY 4.0).
Neutron powder diffraction on HRPT (PSI), λ = 2.449 Å, refined in FullProf.
Only the published numbers below enter this file; the structure was first
reported by Göser, Paul & Kahle, *J. Magn. Magn. Mater.* **92**, 129 (1990).

* **Cell and coordinates:** Supplementary Information, **Supplementary Table 1**
  (PDF page 2 of 7), the T = 1.8 K column: a = 3.5127(1), b = 4.7458(1),
  c = 7.9131(2) Å; Cr 2b (0.25, 0.75, z) z = -0.1269(6), Biso 0.22(6) Å²;
  S 2a (0.75, 0.75, z) z = 0.0739(9), Biso 0.21(9); Br 2a (0.75, 0.75, z)
  z = -0.3535(6), Biso 0.40(3).  *Supplementary Table 2* of the SI holds the
  irreducible representation (BASR 0 1 0: a moment along b), not coordinates;
  the 1.8 K coordinates are in Table 1.
* **Setting.**  The paper writes the group "Pmnm".  Expanded in that symbol the
  published coordinates do not give Cr₂S₂Br₂ per cell (gemmi ``P m n m:2``
  gives Z = 4, ``:1`` gives 8 atoms per site).  Expanded in ``P m m n:2``
  (origin choice 2, the setting of the printed site labels, layers ⊥ c) they do:
  Z = 2, and the Cr octahedron is [CrS₄Br₂] with Cr-S 2.37 and 2.41 Å, Cr-Br
  2.51 Å (checked in ``test_magnetic_width_k_half.py``).  The paper's symbol is
  taken as a permutation slip; the paper's axes are kept (c is the stacking
  direction, the moment is along b).
* **Magnetic structure** (main text, p. 3): k = (0 0 1/2), "a doubling of the
  cell along the c-axis"; ferromagnetic layers, moments along b, antiferromagnetic
  between layers (A-type); M(1.8 K) = 3.09(1) μ_B per Cr (S = 3/2).  rietx
  identifies the child as BNS 62.450, transform ``a,b,2c``.

**Synthetic by design (§ what is left out):** the instrument (u = 0.05,
w = 0.03, as the MnF₂ round trip; **not** HRPT's resolution), the background
(flat, 50 counts), the counts, the planted width, the noise.  No preferred
orientation (the paper refined a March correction), no axial asymmetry, no
absorption, no second phase, no thermal story (1.8 K values only).
"""

from __future__ import annotations

from typing import Literal

import numpy as np

import rietx as rx
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.supercell import (
    anti_translation_ties,
    magnetic_supercell,
)
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase

DOI = "10.1038/s41467-022-32290-4"

#: Supplementary Table 1, T = 1.8 K column (a, b, c in Å)
CELL = (3.5127, 4.7458, 7.9131)
#: the setting that reproduces Z = 2 and sensible bond lengths (module docstring)
SPACE_GROUP = "P m m n:2"
#: (x, y, z, Biso) per atom, Supplementary Table 1, 1.8 K
SITES = {
    "Cr": (0.25, 0.75, -0.1269, 0.22),
    "S": (0.75, 0.75, 0.0739, 0.21),
    "Br": (0.75, 0.75, -0.3535, 0.40),
}
K = ("0", "0", "1/2")
#: M(1.8 K) = 3.09(1) μ_B, main text
MOMENT = 3.09
LAMBDA = 2.449
#: the planted magnetic Lorentzian width, degrees 2θ (synthetic)
SIZE = 0.20
BACKGROUND = 50.0
#: strongest magnetic line = 5 000 counts above background for the *sharp*
#: pattern: 5000 / 1.567e6 (the unit-scale height of the child (0 0 1) line at
#: the planted moment, from one ``predict``), to three significant figures.
#: At this level esd(size) is about 1.3 %, above the window-truncation floor of
#: the width term (PR #524 measured ~1.2 % low; at 1e5 counts that floor would
#: be several esd and the 2σ bar would test the floor, not the term).
SCALE = 3.19e-3
SEEDS = {"broad": 1343, "sharp": 1344, "paramagnetic": 1345}
TWO_THETA = np.arange(5.0, 130.0, 0.05)


def parent() -> Phase:
    """CrSBr in ``P m m n:2``, the 1.8 K published coordinates."""
    atoms = [Atom(label=el, species=el,
                  x=Parameter(value=x), y=Parameter(value=y),
                  z=Parameter(value=z), biso=Parameter(value=b))
             for el, (x, y, z, b) in SITES.items()]
    cell = Cell(**{n: Parameter(value=v) for n, v in
                   zip(("a", "b", "c", "alpha", "beta", "gamma"),
                       (*CELL, 90.0, 90.0, 90.0), strict=True)})
    return Phase(name="CrSBr", space_group=SPACE_GROUP, cell=cell, atoms=atoms)


def _p1_moments(phase: Phase):
    """Every Cr of the child's P1 expansion: ``(frac_z, moment_vector)``."""
    group = phase.magnetic_symmetry.group()
    out = set()
    for a in phase.atoms:
        if a.moment is None:
            continue
        pos = np.array([a.x.value, a.y.value, a.z.value])
        m = np.array(a.moment.values(), dtype=float)
        for op in group.all_operations():
            r = np.asarray(op.act_on_site(pos), dtype=float) % 1.0
            out.add((tuple(np.round(r % 1.0, 4) % 1.0),
                     tuple(np.round(np.asarray(op.act_on_moment(m)), 6))))
    return sorted(out)


def is_a_type_along_b(phase: Phase) -> bool:
    """P1 expansion test: all moments along b, same-layer Cr parallel, adjacent
    layers antiparallel.  A layer is a set of Cr within 3 Å along c."""
    c = phase.cell.c.value
    sites = _p1_moments(phase)
    if len(sites) != 4:
        return False
    if any(abs(m[0]) > 1e-6 or abs(m[2]) > 1e-6 or abs(m[1]) < 1e-6
           for _r, m in sites):
        return False
    for i, (ri, mi) in enumerate(sites):
        for rj, mj in sites[i + 1:]:
            dz = abs(ri[2] - rj[2])
            dz = min(dz, 1.0 - dz) * c
            same_layer = dz < 3.0
            parallel = mi[1] * mj[1] > 0
            if same_layer != parallel:
                return False
    return True


def child(magnitude: float = MOMENT):
    """The a,b,2c child (BNS 62.450), the A-type candidate chosen by its P1
    expansion and not by its index.  Returns the ``SupercellStatement``."""
    cs = candidates(SPACE_GROUP, SITES["Cr"][:3], K)
    for cand in cs.candidates:
        try:
            st = magnetic_supercell(parent(), cand, magnetic_species="Cr",
                                    ion="Cr3+", magnitude=magnitude)
        except Exception:  # noqa: BLE001 - a candidate the builder refuses is skipped
            continue
        if cand.bns_number == "62.450" and is_a_type_along_b(st.phase):
            return st
    raise AssertionError("no A-type candidate with moments along b")


def child_phase(magnitude: float = MOMENT, *, size: float = 0.0,
                scale: float = SCALE) -> Phase:
    """The child phase at ``scale``, optionally with the planted width."""
    ph = child(magnitude).phase
    ph.scale.value = scale
    if size:
        ph.magnetic_lor_size = Parameter(value=size, min=0.0, unit="deg",
                                         transform="softplus")
        ph.magnetic_lor_strain = Parameter(value=0.0, min=0.0, unit="deg",
                                           transform="softplus")
    return ph


def nuclear_phase(scale: float = SCALE) -> Phase:
    """The child cell with no moment block at all (the "above T_N" state)."""
    ph = child().phase
    for a in ph.atoms:
        a.moment = None
    ph.magnetic_symmetry = None
    ph.scale.value = scale
    return ph


def instrument() -> rx.Instrument:
    """Synthetic constant-wavelength neutron instrument (not HRPT's)."""
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA)
    ins.profile.u.value, ins.profile.w.value = 0.05, 0.03
    ins.background = rx.BackgroundChebyshev.with_terms(2)
    ins.background.coefficients[0].value = BACKGROUND
    return ins


def blank() -> rx.PatternData:
    return rx.PatternData(two_theta=TWO_THETA.tolist(),
                          intensity=np.zeros_like(TWO_THETA).tolist())


def mean_counts(phase: Phase) -> np.ndarray:
    ref = rx.Refinement(rx.Structure(phases=[phase]), instrument())
    return np.asarray(ref.predict(blank()), dtype=float)


def pattern(kind: Literal["broad", "sharp", "paramagnetic"], *,
            count_factor: float = 1.0) -> rx.PatternData:
    """One Poisson draw, seeded per kind (1343 / 1344 / 1345).

    ``broad``: moment 3.09, ``magnetic_lor_size`` 0.20°.  ``sharp``: the same
    moment and counts, no width.  ``paramagnetic``: the nuclear child, no
    moment block (Michael's "above T_N" arm).  ``count_factor`` multiplies the
    scale (the 4x arm of the A2 diagnostic; the background is not scaled)."""
    sc = SCALE * count_factor
    if kind == "broad":
        ph = child_phase(size=SIZE, scale=sc)
    elif kind == "sharp":
        ph = child_phase(scale=sc)
    elif kind == "paramagnetic":
        ph = nuclear_phase(sc)
    else:
        raise ValueError(kind)
    mean = mean_counts(ph)
    rng = np.random.default_rng(SEEDS[kind])
    counts = rng.poisson(mean).astype(float)
    return rx.PatternData(two_theta=TWO_THETA.tolist(), intensity=counts.tolist(),
                          sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())


def start_structure(moment: float = 2.0, *,
                    count_factor: float = 1.0) -> rx.Structure:
    """The fit start: moment seeded off the truth, both widths at their off state."""
    return rx.Structure(phases=[child_phase(moment, scale=SCALE * count_factor)])


def apply_ties(ref: rx.Refinement) -> None:
    """The anti-centring as a constraint, on every Refinement."""
    for target, source, scale, offset in anti_translation_ties(
            ref.structure.phases[0]):
        ref.tie(target, source, scale=scale, offset=offset)
