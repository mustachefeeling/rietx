"""The affine constraint block p_phys = C·p_free + d in ParameterTable.

Covers the WP-0301 refactor: crystal-system cell ties must behave exactly as
the old identity-tie code (the acceptance suites depend on it), the general
affine machinery (multi-term rows, constants, chains) must decode and
propagate esds by σ² = diag(C·Cov·Cᵀ), and the locked protections must
survive glob-based vary control.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument
from rietx.params.vector import AffineTie, ParameterTable, cell_window
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from tests.test_schemas import make_lab6


def make_table() -> ParameterTable:
    return ParameterTable(make_lab6(), Instrument.debye_scherrer(wavelength=0.4139))


# -- regression: identity cell ties bit-identical ----------------------


def test_cubic_cell_ties_track_a_exactly():
    table = make_table()
    table.set_vary(["phases.0.cell.a"], True)
    theta = table.x0() + 0.01
    values = table.decode(theta)
    assert values["phases.0.cell.b"] == values["phases.0.cell.a"]  # bitwise
    assert values["phases.0.cell.c"] == values["phases.0.cell.a"]


def test_fixed_angles_and_locked_entries_never_freed_by_globs():
    table = make_table()
    hits = table.set_vary(["phases.*.cell.*"], True)
    assert "phases.0.cell.a" in hits
    for path in ("phases.0.cell.b", "phases.0.cell.c", "phases.0.cell.alpha",
                 "phases.0.cell.beta", "phases.0.cell.gamma"):
        assert path not in hits
    assert not table.set_vary(["instrument.source.lines.0.weight"], True)


def test_tied_cell_edges_inherit_source_esd_exactly():
    table = make_table()
    table.set_vary(["phases.0.cell.a", "instrument.zero_shift"], True)
    theta = table.x0()
    s = np.array([3.2e-5, 1.1e-4])
    out = table.stderr_physical(theta, s)
    assert out["phases.0.cell.b"] == out["phases.0.cell.a"]
    assert out["phases.0.cell.c"] == out["phases.0.cell.a"]
    # a is identity-transformed, so its physical esd is the internal one
    assert out["phases.0.cell.a"] == pytest.approx(3.2e-5, rel=1e-12)
    # held parameters are not reported
    assert "phases.0.cell.alpha" not in out
    # and a full correlation matrix must not change an identity tie
    corr = np.array([[1.0, -0.7], [-0.7, 1.0]])
    out_c = table.stderr_physical(theta, s, corr)
    assert out_c["phases.0.cell.b"] == pytest.approx(out_c["phases.0.cell.a"], rel=1e-14)


def test_commit_then_decode_round_trip():
    table = make_table()
    table.set_vary(["phases.0.cell.a"], True)
    theta = table.x0() + 0.02
    table.commit(theta)
    values = table.decode(table.x0())
    assert values["phases.0.cell.a"] == pytest.approx(4.1766, abs=1e-12)
    assert values["phases.0.cell.b"] == values["phases.0.cell.a"]


# -- the general affine form -------------------------------------------


def test_multi_term_tie_wyckoff_style():
    """An x,x,0-style pattern: two parameters riding one synthetic DOF."""
    table = make_table()
    x0 = 0.1993
    table.add_parameter("synthetic.dof.0", 0.0, vary=True)
    table.add_parameter("synthetic.px", x0)
    table.add_parameter("synthetic.py", 0.5)
    table.set_tie("synthetic.px",
                  AffineTie(terms=(("synthetic.dof.0", 1.0),), const=x0))
    table.set_tie("synthetic.py",
                  AffineTie(terms=(("synthetic.dof.0", 1.0),), const=0.5))
    assert "synthetic.dof.0" in table.free_paths
    theta = table.x0()
    k = table.free_paths.index("synthetic.dof.0")
    theta[k] = 0.004
    values = table.decode(theta)
    assert values["synthetic.px"] == pytest.approx(x0 + 0.004, abs=1e-15)
    assert values["synthetic.py"] == pytest.approx(0.5 + 0.004, abs=1e-15)

    # esd: both tied parameters inherit the DOF esd (|coeff| = 1)
    s = np.zeros(len(theta))
    s[k] = 7e-4
    out = table.stderr_physical(theta, s)
    assert out["synthetic.px"] == pytest.approx(7e-4, rel=1e-12)
    assert out["synthetic.py"] == pytest.approx(7e-4, rel=1e-12)


def test_covariance_propagation_with_cross_terms():
    """σ² of p = a + b includes 2·cov(a, b), not just the diagonal."""
    table = make_table()
    table.set_vary(["phases.0.cell.a", "instrument.zero_shift"], True)
    table.add_parameter("synthetic.sum", 0.0)
    table.set_tie("synthetic.sum",
                  AffineTie(terms=(("phases.0.cell.a", 1.0),
                                   ("instrument.zero_shift", 1.0))))
    theta = table.x0()
    s = np.array([2e-4, 3e-4])
    rho = -0.6
    corr = np.array([[1.0, rho], [rho, 1.0]])
    out = table.stderr_physical(theta, s, corr)
    expected = np.sqrt(s[0] ** 2 + s[1] ** 2 + 2 * rho * s[0] * s[1])
    assert out["synthetic.sum"] == pytest.approx(expected, rel=1e-12)
    # without the correlation matrix the cross term is absent
    out_d = table.stderr_physical(theta, s)
    assert out_d["synthetic.sum"] == pytest.approx(np.hypot(s[0], s[1]), rel=1e-12)


def test_scaled_tie_scales_value_and_esd():
    table = make_table()
    table.set_vary(["phases.0.cell.a"], True)
    table.add_parameter("synthetic.half_a", 0.0)
    table.set_tie("synthetic.half_a",
                  AffineTie(terms=(("phases.0.cell.a", 0.5),), const=1.0))
    theta = table.x0()
    values = table.decode(theta)
    assert values["synthetic.half_a"] == pytest.approx(
        0.5 * values["phases.0.cell.a"] + 1.0, rel=1e-15)
    out = table.stderr_physical(theta, np.array([4e-4]))
    assert out["synthetic.half_a"] == pytest.approx(2e-4, rel=1e-12)


def test_chained_ties_flatten_onto_free_sources():
    table = make_table()
    table.set_vary(["instrument.zero_shift"], True)
    table.add_parameter("synthetic.mid", 0.0)
    table.add_parameter("synthetic.end", 0.0)
    table.set_tie("synthetic.mid",
                  AffineTie(terms=(("instrument.zero_shift", 2.0),), const=0.1))
    table.set_tie("synthetic.end",
                  AffineTie(terms=(("synthetic.mid", 3.0),), const=0.01))
    theta = table.x0()
    values = table.decode(theta)
    z = values["instrument.zero_shift"]
    assert values["synthetic.end"] == pytest.approx(6.0 * z + 0.31, rel=1e-12)
    C, _ = table.constraint_block()
    row = C[table._paths["synthetic.end"], :].toarray().ravel()
    k = table.free_paths.index("instrument.zero_shift")
    assert row[k] == pytest.approx(6.0)


def test_tie_to_held_source_lands_in_offset_and_follows_commit():
    table = make_table()  # zero_shift held
    table.add_parameter("synthetic.z2", 0.0)
    table.set_tie("synthetic.z2",
                  AffineTie(terms=(("instrument.zero_shift", 2.0),)))
    z = table.decode(table.x0())["instrument.zero_shift"]
    assert table.decode(table.x0())["synthetic.z2"] == pytest.approx(2 * z, rel=1e-15)
    # held sources give the tied entry no esd
    table.set_vary(["phases.0.cell.a"], True)
    out = table.stderr_physical(table.x0(), np.array([1e-4]))
    assert "synthetic.z2" not in out
    # free the source, refine it, commit: d must follow the new value
    table.set_vary(["instrument.zero_shift"], True)
    theta = table.x0()
    theta[table.free_paths.index("instrument.zero_shift")] = 0.02
    table.commit(theta)
    table.set_vary(["instrument.zero_shift"], False)
    assert table.decode(table.x0())["synthetic.z2"] == pytest.approx(0.04, rel=1e-12)


# -- guard rails -------------------------------------------------------


def test_cyclic_tie_raises():
    table = make_table()
    table.add_parameter("synthetic.p", 0.0)
    table.add_parameter("synthetic.q", 0.0)
    table.set_tie("synthetic.p", AffineTie(terms=(("synthetic.q", 1.0),)))
    with pytest.raises(ValueError, match="cyclic"):
        table.set_tie("synthetic.q", AffineTie(terms=(("synthetic.p", 1.0),)))


def test_unknown_source_raises():
    table = make_table()
    table.add_parameter("synthetic.p", 0.0)
    with pytest.raises(ValueError, match="unknown parameter"):
        table.set_tie("synthetic.p", AffineTie(terms=(("no.such.path", 1.0),)))


def test_duplicate_synthetic_path_raises():
    table = make_table()
    with pytest.raises(ValueError, match="already exists"):
        table.add_parameter("phases.0.cell.a", 1.0)


def test_locked_entry_cannot_be_retied():
    table = make_table()
    with pytest.raises(ValueError, match="locked"):
        table.set_tie("instrument.source.lines.0.weight",
                      AffineTie(terms=(("phases.0.scale", 1.0),)))


def test_tying_removes_from_free_set_and_globs_skip_it():
    table = make_table()
    table.set_vary(["phases.0.scale"], True)
    assert "phases.0.scale" in table.free_paths
    table.set_tie("phases.0.scale", AffineTie(terms=(("phases.0.cell.a", 1.0),)))
    assert "phases.0.scale" not in table.free_paths
    assert "phases.0.scale" not in table.set_vary(["phases.0.scale"], True)


# -- WP-1036: the setting a symbol names, not the crystal system alone -----
#
# Three defects, each a *different* subspace of the same dimension as the one
# the tables used to produce — so every assertion below names the angle held
# and the length tied, never how many of each there are (WP-1020's lesson).


def _cell(a, b, c, alpha, beta, gamma) -> Cell:
    return Cell(a=Parameter(value=a, min=0.1), b=Parameter(value=b, min=0.1),
                c=Parameter(value=c, min=0.1), alpha=Parameter(value=alpha),
                beta=Parameter(value=beta), gamma=Parameter(value=gamma))


def _phase(symbol: str, cell: Cell) -> Structure:
    return Structure(phases=[Phase(
        name="probe", space_group=symbol, cell=cell,
        atoms=[Atom(label="X", species="Si", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0))])])


def _cell_layout(symbol: str, cell: Cell) -> dict[str, tuple[bool, str | None]]:
    """(locked, tie-source) per cell parameter, as the table decides it."""
    table = ParameterTable(_phase(symbol, cell), Instrument.debye_scherrer(1.5406))
    out = {}
    for e in table.entries:
        if e.path.startswith("phases.0.cell."):
            name = e.path.rsplit(".", 1)[-1]
            src = e.tie.terms[0][0].rsplit(".", 1)[-1] if e.tie else None
            out[name] = (e.locked, src)
    return out


@pytest.mark.parametrize("symbol,unique,free_angle,held", [
    ("P 1 2/m 1", "b", "beta", ("alpha", "gamma")),
    ("P 1 1 2/m", "c", "gamma", ("alpha", "beta")),
    ("P 2/m 1 1", "a", "alpha", ("beta", "gamma")),
    ("P 1 1 21/b", "c", "gamma", ("alpha", "beta")),
])
def test_monoclinic_holds_the_angle_its_unique_axis_names(symbol, unique, free_angle, held):
    """The unique axis comes from the symbol, not from an assumption of b.

    Red before WP-1036 for every row but the b-unique one: the table locked
    alpha and gamma unconditionally, so a c-unique symbol had its free angle
    (gamma) held and its symmetry-fixed one (beta) left refinable — inverted,
    and invisible to a degrees-of-freedom count, which is 4 either way.
    """
    import gemmi
    assert gemmi.find_spacegroup_by_name(symbol).monoclinic_unique_axis() == unique
    angles = {"alpha": 90.0, "beta": 90.0, "gamma": 90.0} | {free_angle: 98.3}
    layout = _cell_layout(symbol, _cell(5.0, 6.0, 7.0, **angles))
    assert layout[free_angle] == (False, None), f"{symbol}: {free_angle} must refine"
    for name in held:
        assert layout[name] == (True, None), f"{symbol}: {name} must be held"
    for name in ("a", "b", "c"):
        assert layout[name] == (False, None), f"{symbol}: {name} must be free"


def test_rhombohedral_axes_tie_all_three_lengths_and_all_three_angles():
    """R -3 c:R needs a=b=c and alpha=beta=gamma, with one free angle.

    Red before WP-1036: the trigonal row assumed hexagonal axes, so c was left
    free (breaking a=b=c) and all three angles were locked at 55.28 (removing
    the one angular degree of freedom the setting has).  Free-parameter count
    is 2 either way — {a, c} then, {a, alpha} now.
    """
    layout = _cell_layout("R -3 c:R", _cell(5.128, 5.128, 5.128, 55.28, 55.28, 55.28))
    assert layout["a"] == (False, None)
    assert layout["b"] == (False, "a")
    assert layout["c"] == (False, "a")
    assert layout["alpha"] == (False, None)
    assert layout["beta"] == (False, "alpha")
    assert layout["gamma"] == (False, "alpha")


def test_hexagonal_axes_r_setting_is_unchanged():
    """The :H sibling keeps exactly the behaviour every existing fixture uses."""
    layout = _cell_layout("R -3 c:H", _cell(4.7602, 4.7602, 12.9933, 90.0, 90.0, 120.0))
    assert layout["b"] == (False, "a")
    assert layout["c"] == (False, None)
    assert all(layout[k] == (True, None) for k in ("alpha", "beta", "gamma"))


def test_rhombohedral_cell_ties_track_alpha_bitwise():
    """The angle tie is the identity, so beta and gamma follow alpha exactly."""
    table = ParameterTable(_phase("R -3 c:R", _cell(5.128, 5.128, 5.128, 55.28, 55.28, 55.28)),
                           Instrument.debye_scherrer(1.5406))
    table.set_vary(["phases.0.cell.a", "phases.0.cell.alpha"], True)
    values = table.decode(table.x0() + 0.01)
    assert values["phases.0.cell.b"] == values["phases.0.cell.a"]
    assert values["phases.0.cell.c"] == values["phases.0.cell.a"]
    assert values["phases.0.cell.beta"] == values["phases.0.cell.alpha"]
    assert values["phases.0.cell.gamma"] == values["phases.0.cell.alpha"]


@pytest.mark.parametrize("symbol,angles,offender", [
    ("P m m m", (90.0, 93.2, 90.0), "beta"),
    ("P m -3 m", (90.0, 90.0, 120.0), "gamma"),
    ("P 6/m m m", (90.0, 90.0, 90.0), "gamma"),
    ("P 1 1 2/m", (90.0, 93.2, 98.3), "beta"),
])
def test_a_fixed_angle_disagreeing_with_its_symmetry_is_refused(symbol, angles, offender):
    """Silence is not an option: the old table locked the *stored* value.

    Red before WP-1036 — a monoclinic beta = 93.2 survived, locked, under an
    orthorhombic symbol, and every d-spacing was computed from it (8.3 ppm of
    bias per 1e-3 deg).  The raise names the symbol, the angle, the value it
    holds and the value the symmetry demands.
    """
    with pytest.raises(ValueError, match="symmetry") as exc:
        _cell_layout(symbol, _cell(5.0, 6.0, 7.0, *angles))
    message = str(exc.value)
    assert symbol in message and offender in message


def test_a_fixed_angle_within_tolerance_is_accepted_and_still_held():
    """Float noise from an A..F metric solve must not refuse to build a table."""
    from rietx.crystallography.symmetry import SYMMETRY_ANGLE_TOL_DEG

    layout = _cell_layout("P 6/m m m",
                          _cell(4.76, 4.76, 12.99, 90.0, 90.0,
                                120.0 - 0.5 * SYMMETRY_ANGLE_TOL_DEG))
    assert layout["gamma"] == (True, None)


# -- a tie bounds its source, not only itself (WP-1119) -----------------
#
# The dependent's ``min``/``max`` are schema physics that go on existing after
# it is tied, but the solver's box covers only the *free* column — so before
# these, a coefficient other than 1 carried a dependent straight past its own
# ceiling and the first thing that noticed was pydantic, inside
# ``apply_to_models``, after the solve.


def test_a_dependents_own_ceiling_becomes_its_sources_ceiling():
    table = make_table()
    table.set_vary(["phases.0.atoms.0.biso"], True)          # Atom.biso is [0, 25]
    table.set_tie("phases.0.atoms.1.biso",
                  AffineTie(terms=(("phases.0.atoms.0.biso", 2.0),)))
    lo, hi = table.bounds()
    k = table.free_paths.index("phases.0.atoms.0.biso")
    assert (lo[k], hi[k]) == (0.0, 12.5)                     # bitwise: 25 / 2


def test_a_negative_coefficient_swaps_the_ends():
    table = make_table()
    table.set_vary(["phases.0.atoms.0.biso"], True)
    table.set_tie("phases.0.atoms.1.biso",
                  AffineTie(terms=(("phases.0.atoms.0.biso", -1.0),), const=20.0))
    lo, hi = table.bounds()
    k = table.free_paths.index("phases.0.atoms.0.biso")
    # 0 ≤ 20 − s ≤ 25  ⇒  −5 ≤ s ≤ 20, intersected with biso's own [0, 25]
    assert (lo[k], hi[k]) == (0.0, 20.0)


def test_windows_intersect_over_every_dependent_of_one_source():
    table = make_table()
    table.set_vary(["phases.0.atoms.0.biso"], True)
    table.set_tie("phases.0.atoms.1.biso",
                  AffineTie(terms=(("phases.0.atoms.0.biso", 2.0),)))
    table.add_parameter("synthetic.dep", 0.0, lo=0.0, hi=2.5)
    table.set_tie("synthetic.dep",
                  AffineTie(terms=(("phases.0.atoms.0.biso", 0.5),)))
    lo, hi = table.bounds()
    k = table.free_paths.index("phases.0.atoms.0.biso")
    assert (lo[k], hi[k]) == (0.0, 5.0)     # the tighter of 12.5 and 5, not the last


def test_an_unbounded_dependent_claims_nothing():
    """Every tie the package *derives* is this case — measured, not assumed.

    Cell lengths, cell angles and fractional coordinates all carry
    :class:`~rietx.schemas.common.Parameter`'s default ±inf, so the 52 ties
    ``ParameterTable`` builds across the repository's real structures (68 with
    anisotropic ADPs) narrow nothing.  That is what let the window apply
    unconditionally rather than behind a freeze, so it is asserted rather than
    left to the acceptance suites to notice.
    """
    table = make_table()                      # cubic: b, c ← a, all unbounded
    table.set_vary(["phases.0.cell.a"], True)
    assert table._tie_windows == {}
    lo, hi = table.bounds()
    k = table.free_paths.index("phases.0.cell.a")
    assert (lo[k], hi[k]) == (-np.inf, np.inf)


def test_a_second_source_widens_the_window_to_an_outer_box():
    """Two sources make a half-space, and the projection of one is what lands.

    ``d = s + u`` with ``d`` in [0, 25] does not bound ``s`` at 25 unless ``u``
    is pinned at 0 — the honest box is the one that admits every feasible
    ``s``, so a bounded co-source narrows and an unbounded one does not.
    """
    def window(u_lo: float, u_hi: float) -> tuple[float, float]:
        table = make_table()
        table.add_parameter("synthetic.u", 1.0, vary=True, lo=u_lo, hi=u_hi)
        table.set_vary(["phases.0.atoms.0.biso"], True)
        table.set_tie("phases.0.atoms.1.biso",
                      AffineTie(terms=(("phases.0.atoms.0.biso", 1.0),
                                       ("synthetic.u", 1.0))))
        lo, hi = table.bounds()
        k = table.free_paths.index("phases.0.atoms.0.biso")
        return lo[k], hi[k]

    assert window(-np.inf, np.inf) == (0.0, 25.0)   # nothing known: biso's own
    assert window(10.0, 20.0) == (0.0, 15.0)        # 25 − 10, the outer box
    assert window(0.0, 0.0) == (0.0, 25.0)          # pinned: the single-source answer


def test_two_bounds_that_cannot_both_hold_are_refused_not_clipped():
    table = make_table()
    table.add_parameter("synthetic.big", 30.0, vary=True, lo=30.0, hi=40.0)
    # and it names the *dependent*, which is where the fix usually is: the
    # window is on the source, and widening the source is the wrong move.
    with pytest.raises(ValueError, match=r"'phases\.0\.atoms\.1\.biso' follows "
                                         r"'synthetic\.big'.*\[0, 12\.5\].*"
                                         r"\[30, 40\]"):
        table.set_tie("phases.0.atoms.1.biso",
                      AffineTie(terms=(("synthetic.big", 2.0),)))


def test_a_bound_broken_on_write_back_names_the_path_and_the_tie():
    """The multi-source corner the outer box cannot close, made attributable.

    Before this it arrived as a bare pydantic ``ValidationError`` naming no
    path, no phase and no tie, from inside ``apply_to_models`` after the solve.
    """
    table = make_table()
    table.set_vary(["phases.0.atoms.0.biso"], True)
    table.set_tie("phases.0.atoms.1.biso",
                  AffineTie(terms=(("phases.0.atoms.0.biso", 2.0),)))
    table.entries[table._paths["phases.0.atoms.1.biso"]].value = 40.0
    structure, instrument = make_lab6(), Instrument.debye_scherrer(wavelength=0.4139)
    with pytest.raises(ValueError, match=r"phases\.0\.atoms\.1\.biso=40.*"
                                         r"\[0, 25\].*2·phases\.0\.atoms\.0\.biso"):
        table.apply_to_models(structure, instrument)


def test_the_tie_window_narrows_after_the_cell_window_not_before_it():
    """Order between the four derived bounds, and it is load-bearing.

    ``cell_window`` treats a **finite** stored side as a claim the caller made
    and leaves it alone, applying its runaway default only where the side is
    infinite.  A tie window handed to it first would look exactly like such a
    claim — a finite bound nobody wrote — and would switch off the guard that
    keeps an unsupported phase's cell from wandering.  Applied last it cannot:
    the three defaults each read the stored bounds, and the intersection is
    tighter than any of them.
    """
    table = make_table()
    table.set_vary(["phases.0.cell.a"], True)
    table.add_parameter("synthetic.dep", 0.0, lo=0.0, hi=100.0)
    table.set_tie("synthetic.dep",
                  AffineTie(terms=(("phases.0.cell.a", 1.0),)))
    table.freeze_cell_windows({0})              # the phase the data cannot see
    lo, hi = table.bounds()
    k = table.free_paths.index("phases.0.cell.a")
    a = table.entries[table._paths["phases.0.cell.a"]].value
    # the cell window's own answer, not the tie's [0, 100] passed through
    assert (lo[k], hi[k]) == cell_window("a", a, -np.inf, np.inf,
                                         path="phases.0.cell.a")
    assert (lo[k], hi[k]) != (0.0, 100.0)
