"""#562 S2a: the direct-space engine — moves, tempering, clustering.

Synthetic and public structures only: a rigid fragment of acridine's shape
(ideal fused hexagons, 1.39 Å, 13 C + 1 N) on a general position of a
P 1 21/n 1 cell chosen here, with its Cu Kα pattern simulated; NAC
(``tests/data/11BM_NAC.fxye``, ``cod_1000236.cif``) from its own Pawley
intensities; and textbook groups for the normaliser.

The four acceptance bars of the S2a row, each run once against a deliberately
broken variant that made it fail (the S2a report records which and how):

1. **The fragment is recovered**: 4 seeds × 6 replicas × 2 000 sweeps
   (12 000 moves a seed) find it within 0.10 Å RMSD from ≥ 2 seeds, on the
   compiled path and on the numpy path.
2. **NAC's six sites are recovered** from its Pawley intensities by ≥ 2 of 4
   seeds at 20 000 sweeps (120 000 moves a seed).
3. **Clustering is the group's**: two symmetry-equivalent solutions are one
   cluster, an enantiomer pair is one, a genuinely different minimum is two;
   with the enantiomorph removed from the equivalences the enantiomer pair
   splits (the positive arm).
4. **Swap acceptance is reported per neighbour pair**, and the record can
   tell a ladder whose pairs always swap from one whose pairs rarely do.

The move sizes, the span and the exchange rate are the module constants'
measurements (``solve/tempering.py``); the slow tests read them, never a copy.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.fragments import Fragment
from rietx.crystallography.site_classes import site_assignments, site_classes
from rietx.crystallography.symmetry import resolve_group, site_orbit
from rietx.model import compiled
from rietx.model.forward import compile_model, d_spacings
from rietx.model.restraints import _metric_g
from rietx.params.vector import ParameterTable
from rietx.schemas.pattern import PatternData
from rietx.solve import cluster as cl
from rietx.solve import tempering as tp
from rietx.solve.chemistry import (
    ExcludedContact,
    PriorWeights,
    SolvePriors,
    clash_energy,
    site_clash,
)
from rietx.solve.cost import SolveCost
from rietx.solve.moves import (
    Clash,
    FragmentUnit,
    FreeSite,
    Radiation,
    Scattering,
    SearchRefused,
    SearchSpace,
)

sys.path.insert(0, str(Path(__file__).parent))
from test_acceptance_nac import build_nac_inputs  # noqa: E402

pytestmark = pytest.mark.xdist_group("solve-engine")

_KEYS = ("a", "b", "c", "alpha", "beta", "gamma")
RECOVERY_ANG = 0.10
ACR_CELL = (11.0, 6.1, 15.5, 90.0, 97.0, 90.0)
ACR_SWEEPS = 2000
NAC_SWEEPS = 20000
NAC_LIMITS = (2.0, 24.0)
SEEDS = (0, 1, 2, 3)
REPLICAS = 6


@pytest.fixture(autouse=True)
def _restore_switch():
    was = compiled.set_enabled(None)
    yield
    compiled.set_enabled(was)


def _p(v):
    return rx.Parameter(value=float(v))


def _has_solve_kernels() -> bool:
    try:
        import rietx_kernels as rk
    except ImportError:
        return False
    return all(callable(getattr(rk, n, None)) for n in compiled.SOLVE_NAMES)


PATHS = [pytest.param(True, id="compiled", marks=pytest.mark.skipif(
    not _has_solve_kernels(), reason="no rietx-kernels with the solve kernels (1.4.0)")),
    pytest.param(False, id="numpy")]


# -- the synthetic fragment case ---------------------------------------------------
def acridine() -> Fragment:
    """Three fused regular hexagons, 1.39 Å, N opposite C9 in the middle ring."""
    r, pts = 1.39, []
    for cx in (-r * math.sqrt(3), 0.0, r * math.sqrt(3)):
        for k in range(6):
            a = math.radians(30 + 60 * k)
            p = (cx + r * math.cos(a), r * math.sin(a), 0.0)
            if not any(abs(p[0] - q[0]) < 1e-3 and abs(p[1] - q[1]) < 1e-3 for q in pts):
                pts.append(p)
    pts = np.array(pts)
    species = ["N" if abs(x) < 1e-3 and y < 0 else "C" for x, y, _ in pts]
    return Fragment(tuple(species), pts)


def _acr_phase():
    return rx.Phase(name="acr", space_group="P 1 21/n 1",
                    cell=rx.Cell(**{k: _p(v) for k, v in zip(_KEYS, ACR_CELL)}),
                    atoms=[rx.Atom(label="X", species="C", x=_p(0.1), y=_p(0.2), z=_p(0.3))],
                    scale=_p(1.0))


def _acr_truth(space: SearchSpace) -> np.ndarray:
    """The first uniform start (generator seed 0) whose molecule keeps every
    intermolecular contact at 3.3 Å or more."""
    from rietx.solve.chemistry import contacts

    rng = np.random.default_rng(0)
    n = space.n_atoms
    for _ in range(5000):
        u = space.random(rng, 1)
        im = space.images(space.xyz(u))[0].reshape(n, -1, 3)
        pos = np.concatenate([im[:, k] for k in range(im.shape[1])])
        c = contacts(pos, space.g, 4.0, centres=np.arange(n))
        inter = (c.b >= n) | np.any(c.shift != 0, axis=1)
        if inter.any() and c.d[inter].min() >= 3.3:
            return u
    raise AssertionError("no packing found")      # pragma: no cover


def _simulate(phase, ins, tt=(4.0, 70.0, 0.02), counts=1e4, seed=0):
    st = rx.Structure(phases=[phase])
    t = np.arange(*tt)
    flat = PatternData(two_theta=list(t), intensity=list(np.ones_like(t)))
    tab = ParameterTable(st, ins)
    v = tab.decode(tab.x0())
    y = np.asarray(compile_model(st, ins, flat, mode="rietveld").evaluate(v))
    y = y / y.max() * counts + 0.03 * counts
    yo = np.random.default_rng(seed).poisson(y).astype(float)
    data = PatternData(two_theta=list(t), intensity=list(yo),
                       sigma=list(np.sqrt(np.maximum(yo, 1.0))))
    return compile_model(st, ins, data, mode="rietveld"), v


#: The clash σ (Å) and radius fraction these tests declare: SolvePriors has no
#: default for either since #1016's review round, so the values its first
#: revision carried (0.1 Å, 0.8) are declared here, measured on nothing.
CLASH_SIGMA_ANG = 0.1
CLASH_FRACTION = 0.8


def _priors(weights=None, **kw):
    return SolvePriors(weights=weights or PriorWeights(coordination=0.0),
                       sigma=CLASH_SIGMA_ANG, fraction=CLASH_FRACTION, **kw)


def _problem(space, cost, ins, priors=None):
    sc = Scattering(space, cost.hkl, cost.d, Radiation.from_instrument(ins, space.species))
    clash = Clash.build(space, priors or _priors(PriorWeights.control()))
    return tp.SearchProblem(space, sc, cost, clash)


def build_acr_problem(tt=(4.0, 70.0, 0.02)):
    """(problem, truth u, truth xyz): the fragment's Cu Kα₁,₂ pattern, 4-70° 2θ,
    a 10⁴-count strongest point over a 3 % flat background, one Poisson draw,
    and the cost built at the true profile.  A plain function, so the record
    script reruns this state rather than an imitation of it."""
    space = SearchSpace([FragmentUnit(acridine(), biso=3.0)], _acr_phase())
    u = _acr_truth(space)
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    ins.source.dispersion = None
    model, v = _simulate(space.search_phase(space.xyz(u)[0]), ins, tt=tt)
    cost = SolveCost.from_model(model, v)
    return _problem(space, cost, ins), u, space.xyz(u)[0]


@pytest.fixture(scope="module")
def acr():
    return build_acr_problem()


# -- NAC -----------------------------------------------------------------------------
NAC_COMPOSITION = {"Ca2+": 12, "Al3+": 8, "Na1+": 8, "F1-": 56}


def build_nac_problem():
    """(problem, truth xyz, the Pawley ``Refinement``): NAC's sites placed on the
    site-class assignment that is the deposited one, found among
    :func:`site_assignments`'s for the composition."""
    data, st, ins = build_nac_inputs()
    ref = rx.Refinement(st, ins, history=False)
    res = ref.fit(data, mode="pawley", two_theta_limits=NAC_LIMITS, telemetry=False)
    assert res.status == "converged"
    cost = SolveCost.from_pawley(ref, data)
    phase = ref.fitted_structure.phases[0]
    group = resolve_group(phase.space_group, phase.symmetry_operations)
    classes = site_classes(group)
    truth = {a.label: np.array([a.x.value, a.y.value, a.z.value]) for a in phase.atoms}
    want = sorted((a.species, next(i for i, c in enumerate(classes) if c.multiplicity
                                   == site_orbit(group, truth[a.label]).multiplicity))
                  for a in phase.atoms)
    found = [s for s in site_assignments(classes, NAC_COMPOSITION) if sorted(s.sites) == want]
    assert len(found) == 1
    units = [FreeSite(a.species, classes[next(ci for sp, ci in found[0].sites
                                               if sp == a.species and classes[ci].multiplicity
                                               == site_orbit(group, truth[a.label]).multiplicity)],
                      a.label, 1.0, 1.0)
             for a in phase.atoms]
    space = SearchSpace(units, phase)
    xt = np.array([truth[a.label] for a in phase.atoms])
    return _problem(space, cost, ref.fitted_instrument), xt, ref


@pytest.fixture(scope="module")
def nac():
    return build_nac_problem()


def _recovered(problem, run, eq, xt) -> tuple[float, float, tp.Visit]:
    """(RMSD after the polish, RMSD of the tempering's own lowest state before
    it, the polished state)."""
    sp = problem.space
    pol = min((tp.polish(problem, v) for v in run.best), key=lambda v: v.j)
    raw = min(run.best, key=lambda v: v.j)
    return (cl.align(eq, xt, sp.xyz(pol.u[None])[0], sp.species).rmsd,
            cl.align(eq, xt, sp.xyz(raw.u[None])[0], sp.species).rmsd, pol)


def _ladder(problem, n=REPLICAS):
    t_top, _median = tp.random_spread(problem, np.random.default_rng(12345))
    return tp.Ladder.planned(t_top, problem.space.n_par, n)


# ===================================================================================
# the structure factor
# ===================================================================================
@pytest.mark.parametrize("radiation", ["xray", "xray_dispersion", "neutron"])
def test_f2_is_the_forward_models(radiation):
    """|F|² over the frozen list equals ``CompiledModel._total_f2`` at the same
    coordinates, for each amplitude the source can choose."""
    space = SearchSpace([FragmentUnit(acridine(), biso=2.0)], _acr_phase())
    if radiation == "neutron":
        ins = rx.Instrument.constant_wavelength_neutron(1.594, fwhm_deg=0.3)
    else:
        ins = rx.Instrument.debye_scherrer(1.5406)
        if radiation == "xray":
            ins.source.dispersion = None
    rng = np.random.default_rng(3)
    u = space.random(rng, 3)
    tt = np.arange(5.0, 90.0, 0.05)
    flat = PatternData(two_theta=list(tt), intensity=list(np.ones_like(tt)))
    for r in range(3):
        st = rx.Structure(phases=[space.search_phase(space.xyz(u)[r])])
        model = compile_model(st, ins, flat, mode="rietveld")
        tab = ParameterTable(st, ins)
        v = tab.decode(tab.x0())
        cp = model.phases[0]
        cell = tuple(v[f"phases.0.cell.{k}"] for k in _KEYS)
        d = d_spacings(cp.reflections.index, *cell)
        want = np.asarray(model._total_f2(0, d, v, cell))
        sc = Scattering(space, cp.reflections.index, d,
                        Radiation.from_instrument(ins, space.species))
        assert (sc.amp_b is not None) == (radiation == "xray_dispersion")
        got = sc.f2(space.xyz(u[r:r + 1]))[0]
        assert np.max(np.abs(got - want)) <= 1e-13 * np.max(want)


@pytest.mark.skipif(not _has_solve_kernels(), reason="no rietx-kernels solve kernels")
def test_compiled_and_numpy_orbit_sums_agree_within_the_kernels_bound(nac, acr):
    """The engine's two paths, held to the kernels' stated bound: 1e-13 of
    each site's image count (``tests/test_solve_kernels.py``); and the
    compiled path is the one the engine took while it was on.  F d -3 m:2
    carries quarter translations, where a sign error in h·t shows (in
    I 2₁ 3 and P 2₁/n every h·t is a multiple of ½, so −h·t ≡ h·t)."""
    fd3m = rx.Phase(name="fd3m", space_group="F d -3 m:2", cell=rx.Cell.cubic(8.4),
                    atoms=[rx.Atom(label="X", species="O", x=_p(0.1), y=_p(0.2), z=_p(0.3))],
                    scale=_p(1.0))
    classes = site_classes(resolve_group("F d -3 m:2"))
    quarter = SearchSpace([FreeSite("Mg2+", [c for c in classes if c.dof == 1][0]),
                           FreeSite("O2-", classes[-1])], fd3m)
    hkl = np.random.default_rng(1).integers(-7, 8, (120, 3))
    hkl = hkl[np.abs(hkl).sum(axis=1) > 0]
    d = d_spacings(hkl, 8.4, 8.4, 8.4, 90.0, 90.0, 90.0)
    assert np.any((np.abs(quarter.tran * 4 - np.round(quarter.tran * 4)) < 1e-12)
                  & (np.abs(quarter.tran * 2 - np.round(quarter.tran * 2)) > 0.1))
    spaces = [(nac[0].space, nac[0].scattering), (acr[0].space, acr[0].scattering),
              (quarter, Scattering(quarter, hkl, d))]
    for sp, sc in spaces:
        xyz = sp.xyz(sp.random(np.random.default_rng(7), 4))
        atoms = np.arange(sp.n_atoms)
        compiled.set_enabled(True)       # declared, not inherited: RIETX_COMPILED=0 runs too
        before = dict(sc.compiled_used)
        s_c = sc.orbit_sums(xyz, atoms)
        one_c = sc.orbit_sums_one(xyz, np.arange(4) % sp.n_atoms)
        assert sc.compiled_used["orbit_sums"] == before["orbit_sums"] + 1
        assert sc.compiled_used["orbit_sums_one"] == before["orbit_sums_one"] + 1
        compiled.set_enabled(False)
        s_n = sc.orbit_sums(xyz, atoms)
        one_n = sc.orbit_sums_one(xyz, np.arange(4) % sp.n_atoms)
        assert sc.compiled_used["orbit_sums"] == before["orbit_sums"] + 1
        compiled.set_enabled(None)
        bound = 1e-13 * (sp.img_hi - sp.img_lo)
        assert np.all(np.abs(s_c - s_n).max(axis=2) <= bound[None, :])
        assert np.all(np.abs(one_c - one_n).max(axis=1) <= bound[np.arange(4) % sp.n_atoms])


@pytest.mark.parametrize("on", PATHS)
def test_running_sums_stay_on_a_rebuild(acr, nac, on):
    """With no refresh inside the run, the running amplitudes after every move
    of a seed differ from a rebuild by rounding only (J units)."""
    compiled.set_enabled(on)
    for problem in (acr[0], nac[0]):
        run = tp.temper(problem, _ladder(problem), seed=5, sweeps=400, refresh_every=10 ** 9)
        assert run.drift <= 1e-10
        assert run.moves == 400 * REPLICAS


def test_a_seed_reruns_bit_for_bit(acr):
    problem = acr[0]
    lad = _ladder(problem)
    a = tp.temper(problem, lad, seed=11, sweeps=150)
    b = tp.temper(problem, lad, seed=11, sweeps=150)
    assert [v.j for v in a.best] == [v.j for v in b.best]
    assert np.array_equal(a.swap_accepts, b.swap_accepts)


def test_a_placed_fragment_keeps_its_shape():
    """The fragment map is an isometry of the template on an oblique cell:
    every interatomic distance of the placed atoms, through the metric,
    equals the template's, at any origin and orientation, and a torsion turns
    only its moving atoms about its axis."""
    frag = acridine()
    t = np.asarray(frag.xyz)
    want = np.linalg.norm(t[:, None] - t[None], axis=2)
    sp = SearchSpace([FragmentUnit(frag)], _acr_phase())
    for x in sp.xyz(sp.random(np.random.default_rng(4), 5)):
        d = x[:, None] - x[None]
        got = np.sqrt(np.einsum("abi,ij,abj->ab", d, sp.g, d))
        assert np.max(np.abs(got - want)) < 1e-12
    bent = SearchSpace([FragmentUnit(frag, torsions=((5, 4, (0, 1, 2, 3)),))], _acr_phase())
    u = bent.random(np.random.default_rng(5), 1)
    x0 = bent.xyz(u)[0]
    u[0, 6] += 40.0
    x1 = bent.xyz(u)[0]
    moved = np.flatnonzero(np.abs(x1 - x0).max(axis=1) > 1e-9)
    assert list(moved) == [0, 1, 2, 3]


# ===================================================================================
# the clash term
# ===================================================================================
def test_clash_paths_and_the_one_site_identity(nac):
    """The engine's per-site energy at w_same = ½ changes exactly as the total
    does under a one-site move, on the compiled path and on chemistry's numpy
    oracle, and the two paths agree."""
    problem = nac[0]
    sp = problem.space
    clash = Clash.build(sp, _priors())
    assert clash.active
    rng = np.random.default_rng(2)
    u = sp.random(rng, 3)
    xyz = sp.xyz(u)
    for on in ([True, False] if _has_solve_kernels() else [False]):
        compiled.set_enabled(on)
        tot = clash.total(xyz)
        want = [clash_energy(sp.images(xyz[r:r + 1])[0], sp.site_of_image, sp.g, clash.r0,
                             clash.sigma) for r in range(3)]
        assert np.allclose(tot, want, rtol=1e-12, atol=1e-12)
        k = int(sp.movable[3])
        u2, moved = sp.propose(u, np.full(3, k), np.full(3, 0.4), rng)
        xyz2 = sp.xyz(u2)
        atom = np.array([m[0] for m in moved])
        d_site = (clash.site(sp.images(xyz2), atom, 0.5) - clash.site(sp.images(xyz), atom, 0.5))
        assert np.allclose(d_site, clash.total(xyz2) - tot, rtol=1e-10, atol=1e-10)
    compiled.set_enabled(False)
    numpy_site = site_clash(sp.images(xyz), sp.site_of_image, np.zeros(3, dtype=int), sp.g,
                            clash.r0, clash.sigma, 0.5)
    compiled.set_enabled(None)
    assert np.allclose(clash.site(sp.images(xyz), np.zeros(3, dtype=int), 0.5), numpy_site,
                       rtol=1e-12, atol=1e-12)


# ===================================================================================
# refusals
# ===================================================================================
def test_a_seed_on_a_special_position_is_refused_by_name(nac):
    problem, xt, _ = nac
    sp = problem.space
    u = sp.random(np.random.default_rng(0), 1)
    # F1 is a general-position site; put it on the 3-fold axis at (0.2, 0.2, 0.2)
    f1 = sp.labels.index("F1")
    b = sp.blocks[f1]
    c = b.unit.site_class
    u[0, b.lo:b.hi] = np.linalg.solve(c.basis.T.astype(float), np.full(3, 0.2) - c.point)
    assert np.allclose(sp.xyz(u)[0, f1] % 1.0, 0.2)
    with pytest.raises(SearchRefused, match="F1") as err:
        sp.check_seed(u)
    assert err.value.reason == "special_position_seed"
    with pytest.raises(SearchRefused):
        tp.temper(problem, _ladder(problem), seed=0, sweeps=1, start=u[0])
    u[0, b.lo:b.hi] += (0.01, 0.03, 0.07)
    sp.check_seed(u)


def test_a_clash_radius_past_the_27_cells_is_refused_before_a_sweep(nac):
    sp = nac[0].space
    priors = _priors(exclude=(ExcludedContact("Ca", "F", 16.0),))
    with pytest.raises(SearchRefused, match="27 cells") as err:
        Clash.build(sp, priors)
    assert err.value.reason == "clash_reach"


def test_other_refusals():
    with pytest.raises(SearchRefused) as err:
        SearchSpace([], _acr_phase())
    assert err.value.reason == "no_units"
    with pytest.raises(SearchRefused) as err:
        SearchSpace([FragmentUnit(acridine(), torsions=((0, 1, (1, 2)),))], _acr_phase())
    assert err.value.reason == "torsion"


def test_a_fixed_class_scatters_and_does_not_move():
    """A site on a class with no free parameter has no slice of u."""
    phase = rx.Phase(name="nacl", space_group="F m -3 m", cell=rx.Cell.cubic(5.64),
                     atoms=[rx.Atom(label="X", species="Na", x=_p(0), y=_p(0), z=_p(0))],
                     scale=_p(1.0))
    classes = site_classes(resolve_group("F m -3 m"))
    fixed = [c for c in classes if c.dof == 0]
    sp = SearchSpace([FreeSite("Na1+", fixed[0]), FreeSite("Cl1-", fixed[1]),
                      FreeSite("O2-", [c for c in classes if c.dof == 1][0])], phase)
    assert sp.n_par == 1
    assert list(sp.movable) == [2]


# ===================================================================================
# the normaliser and clustering (bar 3)
# ===================================================================================
@pytest.mark.parametrize("symbol, cell, index, proper, floating", [
    ("P 1 21/c 1", (7, 8, 9, 90, 101, 90), 8, 8, 0),
    ("P 21 21 21", (5, 6, 7, 90, 90, 90), 16, 8, 0),
    ("I 21 3", (10.25,) * 3 + (90,) * 3, 4, 2, 0),
    ("P 1 21 1", (5, 6, 7, 90, 100, 90), 8, 4, 1),
    ("P -1", (5.1, 6.3, 7.2, 81, 95, 103), 8, 8, 0),
    ("P 1", (5.1, 6.3, 7.2, 81, 95, 103), 2, 1, 3),
    ("P 63/m m c", (5.5, 5.5, 9.0, 90, 90, 120), 2, 2, 0),
])
def test_the_normaliser_index_is_international_tables(symbol, cell, index, proper, floating):
    """[N(G) : G] on a general metric of the system, against International
    Tables A Part 15's Euclidean normalisers: P 1 2/m 1, P m m m and P -1
    with halved translations (8, 16, 8), I a -3 d over I 2₁ 3 (4), P 6/m m m
    with c/2 over P 6₃/m m c (2), and P -1 over P 1 with continuous shifts
    (2); P 2₁ is P 1 2/m 1 with a/2, c/2 and a continuous b (8).  ``proper``
    drops the enantiomorph."""
    g = _metric_g(cell)
    eq = cl.equivalences(resolve_group(symbol), g)
    assert eq.index == index
    assert cl.equivalences(resolve_group(symbol), g, enantiomers=False).index == proper
    assert len(eq.floating) == floating


def test_equivalent_solutions_are_one_cluster_and_different_ones_two(acr, nac):
    """Bar 3.  Copies the data cannot tell apart (|F|² equal on the cost's list,
    checked here independently of the equivalence set) align at RMSD 0 and
    join one cluster: in P 1 21/n 1 the molecule's 2₁ image moved to each of
    the eight origins (0 or ½ on each axis) and a lattice vector; in I 2₁ 3
    NAC's enantiomer −x.  A genuinely different minimum (the molecule turned
    30°; NAC with Na and Al exchanged) starts a cluster of its own, and with
    the enantiomorph dropped from the equivalences the enantiomer pair
    splits (the positive arm)."""
    from rietx.crystallography import rotation

    problem, u, xt = acr
    sp, sc = problem.space, problem.scattering
    eq = cl.equivalences(sp.group, sp.g)
    f_true = sc.f2(xt[None])[0]
    copies = []
    for shift in np.array(list(np.ndindex(2, 2, 2))) / 2.0:
        y = xt @ eq.rot[1].T + eq.tran[1] + shift + np.array([1.0, -2.0, 0.0])
        assert np.max(np.abs(sc.f2(y[None])[0] - f_true)) <= 1e-10 * f_true.max()
        assert cl.align(eq, xt, y, sp.species).rmsd < 1e-9
        copies.append(y)
    turned = u.copy()
    turned[0, 3:6] = np.asarray(rotation.compose_vectors(
        np.array([0.0, 0.0, math.radians(30)]), u[0, 3:6]))
    xturn = sp.xyz(turned)[0]
    sols = [cl.Solution(xt, 1.0, 1.0, 0.0, seed=0),
            cl.Solution(copies[5], 1.0001, 1.0001, 0.0, seed=1),
            cl.Solution(xturn, 2.0, 2.0, 0.0, seed=2)]
    assert [c.seeds for c in cl.cluster(sols, eq, sp.species)] == [(0, 1), (2,)]

    problem, xn, _ = nac
    sp, sc = problem.space, problem.scattering
    eq = cl.equivalences(sp.group, sp.g)
    proper = cl.equivalences(sp.group, sp.g, enantiomers=False)
    enantiomer = -xn
    f_true = sc.f2(xn[None])[0]
    assert np.max(np.abs(sc.f2(enantiomer[None])[0] - f_true)) <= 1e-10 * f_true.max()
    assert cl.align(eq, xn, enantiomer, sp.species).rmsd < 1e-9
    assert cl.align(proper, xn, enantiomer, sp.species).rmsd > 0.5     # the positive arm
    swapped = xn.copy()
    ia, ina = sp.labels.index("Al1"), sp.labels.index("Na1")
    swapped[[ia, ina]] = swapped[[ina, ia]]
    sols = [cl.Solution(xn, 1.1, 1.1, 0.0, seed=0),
            cl.Solution(enantiomer, 1.1, 1.1, 0.0, seed=1),
            cl.Solution(swapped, 1.4, 1.4, 0.0, seed=2)]
    assert [c.seeds for c in cl.cluster(sols, eq, sp.species)] == [(0, 1), (2,)]
    assert [c.seeds for c in cl.cluster(sols, proper, sp.species)] == [(0,), (1,), (2,)]


# ===================================================================================
# grades (provisional)
# ===================================================================================
def _sol(x, chi2, seed, shift=0.0):
    return cl.Solution(np.asarray(x) + shift, chi2, chi2, 0.0, seed=seed)


def test_provisional_grades(acr):
    problem, _u, xt = acr
    sp = problem.space
    eq = cl.equivalences(sp.group, sp.g)
    far = sp.xyz(sp.random(np.random.default_rng(9), 1))[0]
    kw = dict(floor=1.0, labels=sp.labels, species=sp.species)
    # one seed: low
    one = cl.rank(cl.cluster([_sol(xt, 1.0, 0)], eq, sp.species), **kw)
    assert one[0].grade == "low" and "single_seed" in one[0].caveats
    # two seeds, the next cluster far worse: high; that one low
    two = cl.rank(cl.cluster([_sol(xt, 1.0, 0), _sol(xt, 1.0, 1), _sol(far, 3.0, 2),
                              _sol(far, 3.0, 3)], eq, sp.species), **kw)
    assert [r.grade for r in two] == ["high", "low"]
    assert two[0].thresholds_version == cl.THRESHOLDS_VERSION
    assert two[0].margin_to_next == pytest.approx(2.0)
    assert not hasattr(two[0], "structure")
    # a rival within the margin: medium
    riv = cl.rank(cl.cluster([_sol(xt, 1.0, 0), _sol(xt, 1.0, 1), _sol(far, 1.03, 2),
                              _sol(far, 1.03, 3)], eq, sp.species), **kw)
    assert riv[0].grade == "medium" and "rival" in riv[0].caveats
    # the control arm finds a different structure 20 % better: the leader is capped
    lead = cl.cluster([_sol(xt, 1.0, 0), _sol(xt, 1.0, 1)], eq, sp.species)
    ctrl = cl.cluster([_sol(far, 0.8, 4, ), _sol(far, 0.8, 5)], eq, sp.species)
    capped = cl.rank(lead, control=ctrl, eq=eq, **kw)
    assert capped[0].grade == "low" and "prior_excludes_better_fit" in capped[0].caveats
    # ... and not when the control's leader is the same structure, or only 5 % better
    same = cl.cluster([_sol(xt, 0.8, 4), _sol(xt, 0.8, 5)], eq, sp.species)
    assert cl.rank(lead, control=same, eq=eq, **kw)[0].grade == "high"
    close = cl.cluster([_sol(far, 0.95, 4), _sol(far, 0.95, 5)], eq, sp.species)
    assert cl.rank(lead, control=close, eq=eq, **kw)[0].grade == "high"


# ===================================================================================
# the ladder and the swap record (bar 4)
# ===================================================================================
def test_the_planned_ladder():
    lad = tp.Ladder.planned(2.0, 10, 6)
    assert lad.temperatures[-1] == pytest.approx(2.0)
    assert lad.temperatures[-1] / lad.temperatures[0] == pytest.approx(tp.LADDER_SPAN)
    ratios = lad.temperatures[1:] / lad.temperatures[:-1]
    assert np.allclose(ratios, ratios[0])
    assert lad.steps[0] == pytest.approx(tp.STEP_ANG[0])
    assert lad.steps[-1] == pytest.approx(tp.STEP_ANG[1])
    pred = lad.predicted_swap()
    assert pred.shape == (5,) and np.allclose(pred, pred[0]) and 0.0 < pred[0] < 1.0
    with pytest.raises(ValueError):
        tp.Ladder.planned(2.0, 10, 1)


def test_swap_acceptance_is_reported_per_neighbour_pair(acr):
    """Bar 4.  Attempts and acceptances per pair, each in [0, 1]; the planned
    ladder's record shows a pair below 1, and a ladder of equal temperatures,
    where every exchange is accepted, records exactly 1 on every pair."""
    problem = acr[0]
    run = tp.temper(problem, _ladder(problem), seed=1, sweeps=400)
    acc = run.swap_acceptance
    assert acc.shape == (REPLICAS - 1,)
    assert np.all(run.swap_attempts == 20) and np.all((acc >= 0.0) & (acc <= 1.0))
    assert np.any(acc < 1.0)
    flat = tp.Ladder(np.full(REPLICAS, 1.0), np.full(REPLICAS, 0.2), problem.space.n_par)
    assert np.all(tp.temper(problem, flat, seed=1, sweeps=200).swap_acceptance == 1.0)


def test_polish_never_worsens(acr):
    problem = acr[0]
    run = tp.temper(problem, _ladder(problem), seed=2, sweeps=50)
    for v in run.best:
        assert tp.polish(problem, v).j <= v.j + 1e-12


# ===================================================================================
# the acceptance runs (bars 1 and 2)
# ===================================================================================
@pytest.mark.slow
@pytest.mark.parametrize("on", PATHS)
def test_the_rigid_fragment_is_recovered_from_two_seeds(acr, on):
    """Bar 1: 4 seeds × 6 replicas × :data:`ACR_SWEEPS`; ≥ 2 seeds within
    0.10 Å RMSD; the ranked list's leader is that structure and two seeds
    found it.  Also ≥ 2 seeds' own lowest state, **before** the polish, within
    0.10 Å: measured over 16 seeds, an accept-every-move walk followed by the
    same polish recovers this rigid 6-DOF case 14 times in 16 and is never
    within 0.10 Å before it (0.51-1.10 Å), so without this clause the bar
    could not tell tempering from a random walk."""
    compiled.set_enabled(on)
    problem, _u, xt = acr
    sp = problem.space
    eq = cl.equivalences(sp.group, sp.g)
    lad = _ladder(problem)
    hits, raw_hits, sols = 0, 0, []
    for seed in SEEDS:
        run = tp.temper(problem, lad, seed=seed, sweeps=ACR_SWEEPS, wall_seconds=3600.0)
        assert run.stopped is None and run.moves == ACR_SWEEPS * REPLICAS
        assert (run.compiled["orbit_sums"] > 0) == on
        rmsd, raw, pol = _recovered(problem, run, eq, xt)
        hits += rmsd <= RECOVERY_ANG
        raw_hits += raw <= RECOVERY_ANG
        sols.append(cl.Solution(sp.xyz(pol.u[None])[0], pol.j, pol.chi2, pol.clash, seed))
    assert hits >= 2
    assert raw_hits >= 2
    ranked = cl.rank(cl.cluster(sols, eq, sp.species), floor=problem.floor,
                     labels=sp.labels, species=sp.species)
    assert cl.align(eq, xt, ranked[0].xyz, sp.species).rmsd <= RECOVERY_ANG
    assert len(ranked[0].seeds) >= 2


@pytest.mark.slow
def test_nac_is_recovered_from_its_pawley_intensities(nac):
    """Bar 2: NAC's six sites, on the deposited assignment, from ≥ 2 of 4
    seeds at :data:`NAC_SWEEPS`, within 0.10 Å RMSD of the deposited
    coordinates after alignment, after the polish and before it (an
    accept-every-move walk: 1 of 8 after it, 0 of 8 before)."""
    problem, xt, _ = nac
    eq = cl.equivalences(problem.space.group, problem.space.g)
    lad = _ladder(problem)
    hits = raw_hits = 0
    for seed in SEEDS:
        run = tp.temper(problem, lad, seed=seed, sweeps=NAC_SWEEPS, wall_seconds=3600.0)
        assert run.stopped is None
        rmsd, raw, _pol = _recovered(problem, run, eq, xt)
        hits += rmsd <= RECOVERY_ANG
        raw_hits += raw <= RECOVERY_ANG
    assert hits >= 2
    assert raw_hits >= 2
