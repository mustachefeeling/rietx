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

from pxrdref import Instrument
from pxrdref.params.vector import AffineTie, ParameterTable
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
