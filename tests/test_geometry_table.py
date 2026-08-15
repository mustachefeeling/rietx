"""Interatomic distances and angles, with esds from the full covariance (WP-1072).

McCusker *et al.* (1999) §11 makes the chemical sense of the structure one of
the two most important criteria for judging a Rietveld refinement, and §10 says
the e.s.d. of a derived quantity must use "the whole correlation matrix, not
just the diagonal elements".  What is checked here:

* the **distances themselves**, against three published structures whose
  geometry is known independently of this package;
* the **neighbour search is complete**, by orbit counting — |A_ij|·m_i =
  |A_ji|·m_j is a relation the search cannot satisfy by accident, and it caught
  a same-site deduplication that was silently dropping real neighbours;
* the **esd chain**, against a Monte Carlo through ``decode`` — which exercises
  the parameter transforms and the affine coordinate-DOF ties, neither of which
  a partials-only comparison would reach;
* the **symmetry-image pin** the WP asks for: three symmetry-equivalent bonds
  must agree in length *and* in esd, which they do only when each image's
  rotation enters the derivative on the correct side;
* that a **code round-trips** — applying the operation the row names to the
  published coordinates reproduces the distance the row quotes.
"""

from __future__ import annotations

import math
from pathlib import Path

import gemmi
import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.model import geometry as geom
from rietx.model.forward import compile_model
from rietx.model.geometry import geometry_table, symmetry_operations
from rietx.model.restraints import _metric_g
from rietx.params.vector import ParameterTable
from rietx.schemas.structure import Structure
from tests.test_acceptance_qpa_roundrobin import (
    corundum_phase,
    fluorite_phase,
    zincite_phase,
)
from tests.test_coordinates import RUTILE_OX, make_rutile, synthesize_rutile

OUT = Path(__file__).parent / "output"
LAB = Instrument.debye_scherrer(wavelength=1.5406)


def _blank(lo: float = 15.0, hi: float = 80.0, step: float = 0.05) -> PatternData:
    tt = np.arange(lo, hi, step)
    return PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())


def _table_for(phase, *, vary: list[str] | None = None):
    """``(GeometryTable, structure, ParameterTable, theta)`` for one phase."""
    structure = Structure(phases=[phase])
    model = compile_model(structure, LAB, _blank(), mode="rietveld")
    table = ParameterTable(structure, LAB)
    if vary is not None:
        table.set_vary(["*"], False)
        table.set_vary(vary, True)
    theta = table.x0()
    return geometry_table(model, table, theta, structure), structure, table, theta


def _distances(g, a: str, b: str) -> list[float]:
    """Sorted bonded distances between the named labels, rounded to 0.1 mÅ."""
    return sorted(round(d.distance, 4) for d in g.bonds
                  if (d.atom_1, d.atom_2) == (a, b))


# ----------------------------------------------------------------------
# the numbers
# ----------------------------------------------------------------------
def test_corundum_matches_the_published_geometry():
    """α-Al₂O₃ against Lewis, Schwarzenbach & Flack (1982) Acta Cryst. A38, 733.

    Al sits in a distorted octahedron: three short Al–O at 1.8551 Å and three
    long at 1.9709 Å, O–Al–O angles at 79.6/86.4/90.8/101.2/164.2°, and the
    shared octahedron edges as the short O···O contacts.  The input
    coordinates are the published ones rounded to five decimals, which is
    where the sub-milliångström difference comes from.
    """
    g, *_ = _table_for(corundum_phase())
    assert _distances(g, "Al", "O") == [1.8548] * 3 + [1.9712] * 3
    angles = sorted(round(a.angle, 2) for a in g.angles
                    if (a.atom_1, a.atom_2, a.atom_3) == ("O", "Al", "O"))
    assert angles == ([79.63] * 3 + [86.37] * 3 + [90.79] * 3
                      + [101.17] * 3 + [164.22] * 3)
    # the shared octahedron edges, McCusker §11's "nonbonding" half
    edges = sorted({round(d.distance, 3) for d in g.contacts
                    if (d.atom_1, d.atom_2) == ("O", "O")})
    assert edges == [2.524, 2.620, 2.725, 2.866]


def test_zincite_and_fluorite_coordination_numbers():
    """Wurtzite ZnO (3 + 1 tetrahedral) and fluorite CaF₂ (cubic 8 : 4).

    The count of rows naming an atom is its coordination number, which is the
    property this table exists to make readable.
    """
    g, *_ = _table_for(zincite_phase())
    assert _distances(g, "Zn", "O") == [1.9734] * 3 + [1.992]
    assert _distances(g, "O", "Zn") == [1.9734] * 3 + [1.992]

    g, *_ = _table_for(fluorite_phase())
    # a√3/4 with a = 5.4631 Å; Ca is 8-coordinate, F is 4-coordinate
    assert _distances(g, "Ca", "F") == [2.3656] * 8
    assert _distances(g, "F", "Ca") == [2.3656] * 4


def test_linear_angle_is_exactly_180_degrees():
    """Fluorite's F–Ca–F through the Ca site is linear, and must read 180.000.

    ``restraints`` clamps cos θ just inside [−1, 1] because a restraint row's
    derivative goes as 1/sin θ; reusing that for a *reported* angle gives
    179.997°.  The geometry table uses the half-angle form instead.
    """
    g, *_ = _table_for(fluorite_phase())
    straight = [a.angle for a in g.angles if a.angle > 179.0]
    assert straight, "fluorite has linear F–Ca–F angles"
    assert max(abs(a - 180.0) for a in straight) < 1e-9


def test_metal_metal_pairs_are_contacts_not_bonds():
    """A covalent-radius criterion is not evidence of an Al···Al bond.

    Corundum's face- and edge-sharing Al pairs are at 2.65 and 2.79 Å, inside
    the 2.82 Å the radii plus the slack allow.  Listed, but as contacts — and
    so they are not arms of any reported angle.
    """
    g, *_ = _table_for(corundum_phase())
    al_al = [d for d in g.distances if (d.atom_1, d.atom_2) == ("Al", "Al")]
    assert al_al and not any(d.bonded for d in al_al)
    assert min(d.distance for d in al_al) < 2.82   # inside the radius criterion
    assert not any("Al" in (a.atom_1, a.atom_3) for a in g.angles
                   if a.atom_2 == "Al")


# ----------------------------------------------------------------------
# the search is complete
# ----------------------------------------------------------------------
@pytest.mark.parametrize("builder", [corundum_phase, zincite_phase, fluorite_phase])
def test_orbit_counting_confirms_every_neighbour_was_found(builder):
    """|A_ij|·m_i = |A_ji|·m_j — the relation a partial search cannot satisfy.

    Counting the i→j neighbours of one atom against the j→i neighbours of the
    other, weighted by the site multiplicities, counts every i–j bond in the
    cell twice by two different routes.  A missing lattice shell, a dropped
    orbit op or an over-eager deduplication all break it; nothing else here
    would have noticed (the deduplication this caught was passing every
    distance-value test in this file).
    """
    phase = builder()
    structure = Structure(phases=[phase])
    model = compile_model(structure, LAB, _blank(), mode="rietveld")
    table = ParameterTable(structure, LAB)
    g = geometry_table(model, table, table.x0(), structure)
    mult = [len(ops[0]) for ops in model.phases[0].sites.ops]

    counts: dict[tuple[int, int, float], int] = {}
    for d in g.distances:
        key = (d.atom_index_1, d.atom_index_2, round(d.distance, 6))
        counts[key] = counts.get(key, 0) + 1
    for (i, j, dist), n_ij in counts.items():
        n_ji = counts.get((j, i, dist))
        assert n_ji is not None, f"{i}->{j} at {dist} has no reverse rows"
        assert n_ij * mult[i] == n_ji * mult[j]


def test_symmetry_code_regenerates_the_image_it_names():
    """Applying the coded operation to the published coordinates gives the row.

    A code is an index into the operation order
    :func:`symmetry_operations` lists (and the exported CIF carries), plus a
    ``klm`` lattice shift offset by 5.  Re-deriving the distance that way uses
    none of the machinery that produced it.
    """
    phase = corundum_phase()
    g, structure, table, theta = _table_for(phase)
    values = table.decode(theta)
    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    metric = _metric_g(cell)
    triplets = symmetry_operations(phase.space_group)
    xyz = [np.array([values[f"phases.0.atoms.{j}.{c}"] for c in "xyz"])
           for j in range(len(phase.atoms))]

    checked = 0
    for row in g.distances:
        code = row.symmetry_2
        assert code is not None, "corundum needs no shift outside the code"
        if code == ".":
            image = xyz[row.atom_index_2]
        else:
            n, klm = code.split("_")
            op = gemmi.Op(triplets[int(n) - 1])
            shift = np.array([int(c) - 5 for c in klm], dtype=float)
            rot = np.array(op.rot, dtype=float) / gemmi.Op.DEN
            tran = np.array(op.tran, dtype=float) / gemmi.Op.DEN
            image = rot @ xyz[row.atom_index_2] + tran + shift
        dx = image - xyz[row.atom_index_1]
        assert math.sqrt(dx @ metric @ dx) == pytest.approx(row.distance, abs=1e-9)
        checked += 1
    assert checked > 20


# ----------------------------------------------------------------------
# the esds (McCusker §10)
# ----------------------------------------------------------------------
def _rutile_with_covariance(rho: float = 0.6):
    """Rutile with a planted correlated covariance on (a, c, O-DOF).

    A planted covariance rather than a fitted one, so the propagation is
    checked against an exactly known input.  ``a`` carries a softplus
    transform so the internal→physical chain rule is exercised too, and the
    tetragonal ``b ← a`` tie plus the 4f site's single DOF (x and y move
    together) make the affine block non-trivial.
    """
    structure = make_rutile(vary_coords=True)
    structure.phases[0].cell.a.transform = "softplus"
    table = ParameterTable(structure, LAB)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.cell.a", "phases.0.cell.c",
                    "phases.0.atoms.1.dof.0"], True)
    free = list(table.free_paths)
    assert len(free) == 3
    theta = table.x0()
    stderr_internal = np.array([4e-4, 3e-4, 2e-4])
    correlation = np.array([[1.0, rho, -rho],
                            [rho, 1.0, rho / 2],
                            [-rho, rho / 2, 1.0]])
    model = compile_model(structure, LAB, _blank(), mode="rietveld")
    return model, structure, table, theta, stderr_internal, correlation


def test_esd_matches_a_monte_carlo_through_decode():
    """σ from J·Cov·Jᵀ against sampling the same covariance through ``decode``.

    The Monte Carlo perturbs the *internal* vector and decodes, so it goes
    through the softplus on ``a``, the ``b ← a`` crystal-system tie and the
    4f site's x = y = DOF constraint exactly as a refinement does.  Agreement
    to a few percent at 20 000 samples is the linearisation plus the sampling
    error, and the propagated numbers are ~1e-3 Å against a ~2 Å distance.
    """
    model, structure, table, theta, sd, corr = _rutile_with_covariance()
    g = geometry_table(model, table, theta, structure,
                       stderr_internal=sd, correlation=corr)
    rows = [d for d in g.distances if d.atom_index_1 == 0][:4]
    assert rows and all(d.stderr is not None for d in rows)

    cov_int = corr * np.outer(sd, sd)
    rng = np.random.default_rng(20260815)
    draws = rng.multivariate_normal(theta, cov_int, size=20000)
    samples = np.array([
        [_distance_at(table.decode(t), d) for d in rows] for t in draws])
    mc = samples.std(axis=0, ddof=1)
    for row, sigma in zip(rows, mc, strict=True):
        assert row.stderr == pytest.approx(sigma, rel=0.05)


def _distance_at(values: dict[str, float], row) -> float:
    """The row's distance recomputed from a decoded value dict.

    Deliberately re-derived here from the *symmetry code* rather than from the
    frozen image, so the Monte Carlo shares no code path with the propagation
    it checks.
    """
    cell = tuple(values[f"phases.{row.phase_index}.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    metric = _metric_g(cell)
    base = f"phases.{row.phase_index}.atoms"
    x1 = np.array([values[f"{base}.{row.atom_index_1}.{c}"] for c in "xyz"])
    x2 = np.array([values[f"{base}.{row.atom_index_2}.{c}"] for c in "xyz"])
    code = row.symmetry_2
    if code == ".":
        image = x2
    else:
        n, klm = code.split("_")
        triplets = symmetry_operations("P42/mnm")
        op = gemmi.Op(triplets[int(n) - 1])
        rot = np.array(op.rot, dtype=float) / gemmi.Op.DEN
        tran = np.array(op.tran, dtype=float) / gemmi.Op.DEN
        image = rot @ x2 + tran + np.array([int(c) - 5 for c in klm], dtype=float)
    dx = image - x1
    return math.sqrt(dx @ metric @ dx)


def test_full_covariance_and_diagonal_only_disagree():
    """§10's point, measured: ignoring the correlations changes the answer."""
    model, structure, table, theta, sd, corr = _rutile_with_covariance()
    g = geometry_table(model, table, theta, structure,
                       stderr_internal=sd, correlation=corr)
    ratios = [d.stderr / d.stderr_diagonal for d in g.distances
              if d.stderr and d.stderr_diagonal]
    assert ratios
    assert max(abs(r - 1.0) for r in ratios) > 0.05

    # and with an identity correlation the two constructions coincide exactly
    g0 = geometry_table(model, table, theta, structure, stderr_internal=sd,
                        correlation=np.eye(3))
    for d in g0.distances:
        if d.stderr:
            assert d.stderr == pytest.approx(d.stderr_diagonal, rel=1e-12)


def test_symmetry_equivalent_bonds_agree_in_length_and_in_esd():
    """The image pin: an equivalent bond's esd must equal its parent's.

    Length agreement alone is weak — it holds for any consistent placement of
    the image.  The esd additionally requires each image's rotation to enter
    the derivative chain on the correct side (``Rᵀ`` acting on the metric
    gradient, ``R`` on the position), which is the trap the ADP and indexing
    work both fell into with a passing degrees-of-freedom count.
    """
    model, structure, table, theta, sd, corr = _rutile_with_covariance()
    g = geometry_table(model, table, theta, structure,
                       stderr_internal=sd, correlation=corr)
    groups: dict[tuple, list] = {}
    for d in g.distances:
        groups.setdefault((d.atom_index_1, d.atom_index_2,
                           round(d.distance, 9)), []).append(d)
    equivalent = [rows for rows in groups.values() if len(rows) > 1]
    assert equivalent, "rutile has symmetry-equivalent Ti–O bonds"
    for rows in equivalent:
        esds = [r.stderr for r in rows]
        assert all(e is not None for e in esds)
        assert max(esds) == pytest.approx(min(esds), rel=1e-12)


def test_a_symmetry_fixed_angle_carries_no_esd():
    """Rutile's 90° and 180° O–Ti–O angles report no esd; its 99° one does.

    Two different failures, one answer.  At 90° symmetry holds the angle while
    its partials against the individual x, y, z entries do not vanish, so
    gᵀ·Cov·g reaches zero by cancelling and lands on roundoff —
    ``90.00000000000(43)``.  At 180° the geometry is at a stationary point,
    where the linearisation J·Cov·Jᵀ rests on does not hold at all and the
    partials that come back are the cos-clamp's.  Both are absence of
    information, so both report ``None``.
    """
    model, structure, table, theta, sd, corr = _rutile_with_covariance()
    g = geometry_table(model, table, theta, structure,
                       stderr_internal=sd, correlation=corr)
    fixed = [a for a in g.angles
             if min(abs(a.angle - 90.0), abs(a.angle - 180.0)) < 1e-6]
    free = [a for a in g.angles
            if min(abs(a.angle - 90.0), abs(a.angle - 180.0)) > 1.0]
    assert fixed and free
    assert all(a.stderr is None and a.stderr_diagonal is None for a in fixed)
    assert all(a.stderr is not None and a.stderr > 1e-4 for a in free)


def test_no_covariance_gives_no_esd_rather_than_a_diagonal_one():
    """An evaluate-only pass reports the geometry and withholds every esd."""
    g, *_ = _table_for(corundum_phase())
    assert g.distances and g.angles
    assert all(d.stderr is None and d.stderr_diagonal is None
               for d in g.distances)
    assert all(a.stderr is None for a in g.angles)


def test_a_fully_fixed_row_reports_none_not_zero():
    """Every coordinate symmetry-fixed and the cell held: absence, not σ = 0.

    ``weight_fractions``' rule one rank over — an all-zero covariance block is
    absence of information.  In fluorite both sites are fully fixed by
    symmetry, so with only the scale free no Ca–F row has a source of
    variance at all.
    """
    structure = Structure(phases=[fluorite_phase()])
    table = ParameterTable(structure, LAB)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.scale"], True)
    model = compile_model(structure, LAB, _blank(), mode="rietveld")
    theta = table.x0()
    g = geometry_table(model, table, theta, structure,
                       stderr_internal=np.array([1e-4]),
                       correlation=np.eye(1))
    assert g.distances
    assert all(d.stderr is None for d in g.distances)


# ----------------------------------------------------------------------
# carrier semantics and bounds
# ----------------------------------------------------------------------
@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_no_geometry_outside_rietveld(mode):
    """The dummy atom those modes require is not a structure to measure."""
    structure = Structure(phases=[corundum_phase()])
    model = compile_model(structure, LAB, _blank(), mode=mode)
    table = ParameterTable(structure, LAB)
    assert geometry_table(model, table, table.x0(), structure) is None


def test_the_contact_cap_is_recorded_not_silent(monkeypatch):
    """A bounded table says it was bounded (CLAUDE.md: no silent caps)."""
    monkeypatch.setattr(geom, "MAX_CONTACTS_PER_ATOM", 2)
    g, *_ = _table_for(corundum_phase())
    assert g.notes and "not listed" in g.notes[0]
    assert all(len([d for d in g.contacts if d.atom_index_1 == i]) <= 2
               for i in (0, 1))


def test_a_phase_too_large_to_search_says_so(monkeypatch):
    monkeypatch.setattr(geom, "MAX_ASYM_ATOMS", 1)
    g, *_ = _table_for(corundum_phase())
    assert g.distances == [] and g.angles == []
    assert g.notes and "search limit" in g.notes[0]


def test_the_criteria_travel_with_the_table():
    g, *_ = _table_for(corundum_phase())
    assert g.bond_slack == geom.BOND_SLACK_ANG
    assert g.contact_max == geom.CONTACT_MAX_ANG
    assert all(d.distance <= g.contact_max + 1e-9 for d in g.distances)
    assert len(g.bonds) + len(g.contacts) == len(g.distances)


# ----------------------------------------------------------------------
# end to end
# ----------------------------------------------------------------------
def test_a_real_fit_recovers_the_synthesised_geometry():
    """Rutile refined from a synthetic pattern, against the structure that made it.

    TiO₂ has four equatorial Ti–O and two apical.  The truth here is the
    structure the pattern was synthesised from, not a remembered literature
    figure, so the assertion is about this refinement and not about how well
    the fixture matches a paper — and the tolerance is the *propagated* esd,
    which is the quantity this WP adds.
    """
    truth, *_ = _table_for(make_rutile().phases[0])
    reference = sorted(round(d.distance, 4) for d in truth.bonds
                       if (d.atom_1, d.atom_2) == ("Ti", "O"))
    assert len(reference) == 6 and len(set(reference)) == 2  # 4 + 2

    pattern = synthesize_rutile()
    structure = make_rutile(RUTILE_OX + 0.012)
    structure.phases[0].scale.value = 6.0e-3
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1.2e-2
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(pattern, plan="mccusker_structural")
    assert result.status == "converged"

    g = result.geometry
    assert g is not None
    rows = [d for d in g.bonds if (d.atom_1, d.atom_2) == ("Ti", "O")]
    assert len(rows) == 6
    assert all(d.stderr is not None and d.stderr > 0 for d in rows)
    for row, want in zip(sorted(rows, key=lambda d: d.distance), reference,
                         strict=True):
        assert row.distance == pytest.approx(want, abs=4 * row.stderr)
    # a Ti–O esd of a hundredth of an ångström or worse would mean the
    # propagation is picking up something other than this fit
    assert max(d.stderr for d in rows) < 0.01

    OUT.mkdir(exist_ok=True)
    pytest.importorskip("matplotlib")
    from rietx.viz.plots import plot_result

    plot_result(result, path=str(OUT / "geometry_rutile_fit.png"))
