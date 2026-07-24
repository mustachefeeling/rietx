"""WP-0401 backend-shim bit-identity goldens.

The op-shim routing and purity refactors (WP-0401) must not change a single
computed number on the numpy path.  This file freezes that claim: each state
below is compiled, evaluated and differentiated exactly as the solver does,
and compared **bit-for-bit** (``np.array_equal``) against golden arrays
captured from the pre-shim tree.

States (chosen to cover every refactored code path):

* ``srm660c`` — real lab data, Bragg-Brentano + Kα doublet + FCJ + Chebyshev
  background; displacement/transparency/extinction free *at their 0 off-values*
  (gates the unconditional-evaluation refactor's exact identities).
* ``nac`` — real synchrotron data, two phases, coordinate DOF columns.
* ``toy_lebail`` — Le Bail partitioning (3 cycles) + P-spline penalty rows.
* ``toy_pawley`` — Pawley intensity block: aux Jacobian columns + overlap
  restraint rows.
* ``toy_rich`` — aniso ADPs + March-Dollase + extinction + displacement/
  transparency/zero all *on* (nonzero), unequal axial S/L ≠ H/L.

Golden bit patterns are environment-pinned (they depend on the numpy/BLAS
build); they live in ``tests/data/backend_goldens/`` and are documented in
``tests/data/README.md``.  If the environment shifts, re-baseline **from a
tree that passes the full suite**, never from a mid-refactor tree:

    .venv/bin/python -m tests.test_backend_shim
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.model.forward import compile_model
from pxrdref.optimize.least_squares import _make_jacobian, _make_residual
from pxrdref.params.vector import ParameterTable
from pxrdref.schemas.instrument import (
    BackgroundChebyshev,
    BackgroundPSpline,
    Instrument,
)
from pxrdref.schemas.pattern import PatternData
from pxrdref.schemas.structure import PreferredOrientation

DATA = Path(__file__).parent / "data"
GOLDEN_DIR = DATA / "backend_goldens"


# ----------------------------------------------------------------------
# state builders — deterministic (model, table, extras) triples
# ----------------------------------------------------------------------
def _free(table: ParameterTable, patterns: list[str]) -> None:
    table.set_vary(["*"], False)
    for pat in patterns:
        assert table.set_vary([pat], True), f"nothing freed by {pat!r}"


def _state_srm660c():
    path = DATA / "nist_srm660c_100a.cif"
    if not path.exists():
        return None
    data = pr.read_pdcif(path, block="_meas")
    structure = pr.Structure(phases=[pr.Phase(
        name="LaB6", space_group="P m -3 m", cell=pr.Cell.cubic(4.1568),
        atoms=[
            pr.Atom(label="La", species="La", x=pr.Parameter(value=0.0),
                    y=pr.Parameter(value=0.0), z=pr.Parameter(value=0.0),
                    biso=pr.Parameter(value=0.355, min=0.0, max=25.0)),
            pr.Atom(label="B", species="B", x=pr.Parameter(value=0.198),
                    y=pr.Parameter(value=0.5), z=pr.Parameter(value=0.5),
                    biso=pr.Parameter(value=0.276, min=0.0, max=25.0)),
        ],
        scale=pr.Parameter(value=1e-4, min=0.0, transform="softplus"),
    )])
    instrument = pr.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    instrument.profile.w.value = 2e-3
    instrument.profile.x.value = 5e-3
    instrument.geometry.axial_sl.value = 0.025
    instrument.geometry.axial_hl.value = 0.025
    instrument.background = BackgroundChebyshev.with_terms(6)

    table = ParameterTable(structure, instrument)
    # displacement, transparency and extinction free at their 0.0 off-values:
    # the FD Jacobian steps them on, so the exact-identity claim is exercised
    _free(table, [
        "phases.0.scale", "instrument.background.*",
        "instrument.geometry.sample_displacement",
        "instrument.geometry.sample_transparency",
        "instrument.zero_shift", "phases.0.cell.a",
        "instrument.profile.u", "instrument.profile.v", "instrument.profile.w",
        "instrument.profile.x", "instrument.profile.y",
        "instrument.source.lines.1.weight",
        "instrument.geometry.axial_sl", "instrument.geometry.axial_hl",
        "phases.0.atoms.*.biso", "phases.0.extinction",
    ])
    model = compile_model(structure, instrument, data, mode="rietveld",
                          free_paths=set(table.free_paths))
    return model, table, {}


def _caf2_phase() -> pr.Phase:
    return pr.Phase(
        name="CaF2", space_group="F m -3 m", cell=pr.Cell.cubic(5.4631),
        atoms=[
            pr.Atom(label="Ca", species="Ca2+", x=pr.Parameter(value=0.0),
                    y=pr.Parameter(value=0.0), z=pr.Parameter(value=0.0),
                    biso=pr.Parameter(value=0.6, min=0.0, max=25.0)),
            pr.Atom(label="F", species="F1-", x=pr.Parameter(value=0.25),
                    y=pr.Parameter(value=0.25), z=pr.Parameter(value=0.25),
                    biso=pr.Parameter(value=0.9, min=0.0, max=25.0)),
        ],
        scale=pr.Parameter(value=1e-7, min=0.0, transform="softplus"),
    )


def _state_nac():
    if not (DATA / "11BM_NAC.fxye").exists():
        return None
    data = pr.read_pattern(DATA / "11BM_NAC.fxye")
    structure = pr.Structure.from_cif(str(DATA / "cod_1000236.cif"))
    structure.phases[0].scale.value = 1e-6
    structure.phases.append(_caf2_phase())
    instrument = Instrument.debye_scherrer(wavelength=0.4139090)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    instrument.background = BackgroundChebyshev.with_terms(6)

    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.*.scale", "instrument.background.*",
        "phases.0.cell.a", "phases.1.cell.a", "instrument.zero_shift",
        "instrument.profile.w", "instrument.profile.x",
        "phases.0.atoms.*.dof.*",
        "phases.0.atoms.0.biso", "phases.1.atoms.0.biso",
    ])
    model = compile_model(structure, instrument, data, mode="rietveld",
                          two_theta_limits=(2.0, 24.0),
                          free_paths=set(table.free_paths))
    return model, table, {}


def _toy_base(*, c_near_a: bool = False) -> tuple[pr.Structure, Instrument, PatternData]:
    """Deterministic rutile toy: y_obs from a perturbed copy of the model.

    ``c_near_a`` squeezes the tetragonal cell pseudo-cubic so (hkl)/(lkh)
    partners nearly coincide — that is what puts overlapped groups (and hence
    restraint rows) into the Pawley state.
    """
    from tests.test_coordinates import make_rutile

    structure = make_rutile()
    structure.phases[0].scale.value = 8.0e-3
    if c_near_a:
        structure.phases[0].cell.c.value = 4.5910
    instrument = Instrument.debye_scherrer(wavelength=1.5406)
    instrument.profile.w.value = 8e-3
    grid = np.arange(15.0, 80.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim_structure = structure.model_copy(deep=True)
    sim_structure.phases[0].cell.a.value += 0.005
    sim_structure.phases[0].cell.c.value -= 0.004
    sim_structure.phases[0].scale.value = 9.2e-3
    sim = compile_model(sim_structure, instrument, empty, mode="rietveld")
    sim_table = ParameterTable(sim_structure, instrument)
    y = sim.evaluate(sim_table.decode(sim_table.x0())) + 30.0
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())
    return structure, instrument, pattern


_TOY_WHOLE_PATTERN_FREE = [
    "phases.0.cell.a", "phases.0.cell.c", "instrument.zero_shift",
    "instrument.profile.w", "instrument.background.*",
]


def _state_toy_lebail():
    structure, instrument, pattern = _toy_base()
    instrument.background = BackgroundPSpline.for_range(15.0, 80.0)
    table = ParameterTable(structure, instrument)
    _free(table, _TOY_WHOLE_PATTERN_FREE)
    model = compile_model(structure, instrument, pattern, mode="lebail",
                          free_paths=set(table.free_paths))
    model.lebail_update(table.decode(table.x0()), n_cycles=3)
    intens = np.concatenate([cp.hkl_intensity for cp in model.phases])
    return model, table, {"lebail_intensity": intens}


def _state_toy_pawley():
    structure, instrument, pattern = _toy_base(c_near_a=True)
    instrument.background = BackgroundChebyshev.with_terms(4)
    table = ParameterTable(structure, instrument)
    _free(table, _TOY_WHOLE_PATTERN_FREE)
    model = compile_model(structure, instrument, pattern, mode="pawley",
                          free_paths=set(table.free_paths))
    # mirror the staged runner's seeding: one Le Bail partition, then the
    # equal-split restraint on the seeded scale
    model.lebail_update(table.decode(table.x0()), n_cycles=3)
    model.build_pawley_restraint()
    return model, table, {"pawley_x0": model.pawley_x0()}


def _state_toy_rich():
    """Every optional intensity physics ON and nonzero at the expansion point."""
    from tests.test_aniso_adp import make_aniso_rutile

    structure = make_aniso_rutile()
    phase = structure.phases[0]
    phase.scale.value = 8.0e-3
    phase.extinction.value = 3e-4
    phase.preferred_orientation = PreferredOrientation(axis=(0, 0, 1))
    phase.preferred_orientation.r.value = 0.85
    instrument = Instrument.bragg_brentano(monochromator_two_theta=26.6)
    instrument.profile.w.value = 8e-3
    instrument.profile.x.value = 5e-3
    instrument.zero_shift.value = 0.01
    instrument.geometry.sample_displacement.value = -0.08
    instrument.geometry.sample_transparency.value = 0.005
    instrument.geometry.axial_sl.value = 0.03
    instrument.geometry.axial_hl.value = 0.02

    grid = np.arange(15.0, 80.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim_structure = structure.model_copy(deep=True)
    sim_structure.phases[0].cell.a.value = 4.5987
    sim_structure.phases[0].preferred_orientation.r.value = 0.9
    sim = compile_model(sim_structure, instrument, empty, mode="rietveld")
    sim_table = ParameterTable(sim_structure, instrument)
    y = sim.evaluate(sim_table.decode(sim_table.x0())) + 20.0
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())

    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.0.scale", "phases.0.cell.a", "phases.0.cell.c",
        "phases.0.atoms.*.dof.*", "phases.0.atoms.*.adp.*",
        "phases.0.preferred_orientation.r", "phases.0.extinction",
        "instrument.zero_shift",
        "instrument.geometry.sample_displacement",
        "instrument.geometry.sample_transparency",
        "instrument.profile.u", "instrument.profile.v", "instrument.profile.w",
        "instrument.profile.x", "instrument.profile.y",
        "instrument.geometry.axial_sl", "instrument.geometry.axial_hl",
        "instrument.source.lines.1.weight", "instrument.background.*",
    ])
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    return model, table, {}


STATES = {
    "srm660c": _state_srm660c,
    "nac": _state_nac,
    "toy_lebail": _state_toy_lebail,
    "toy_pawley": _state_toy_pawley,
    "toy_rich": _state_toy_rich,
}


def _capture(name: str) -> dict[str, np.ndarray] | None:
    """Evaluate + residual + Jacobian arrays at the state's expansion point."""
    built = STATES[name]()
    if built is None:
        return None
    model, table, extras = built
    theta = table.x0()
    if model.pawley is not None:
        theta = np.concatenate([theta, model.pawley_x0()])
    values = table.decode(theta[:len(table.free_paths)])
    out = dict(extras)
    out["free_paths"] = np.array(table.free_paths, dtype="U")
    out["theta"] = theta
    out["y_calc"] = model.evaluate(values)
    out["residual"] = _make_residual(model, table)(theta)
    out["jacobian"] = _make_jacobian(model, table)(theta)
    return out


# ----------------------------------------------------------------------
# the gate
# ----------------------------------------------------------------------
@pytest.mark.parametrize("name", [
    pytest.param("srm660c", marks=pytest.mark.slow),
    pytest.param("nac", marks=pytest.mark.slow),
    "toy_lebail",
    "toy_pawley",
    "toy_rich",
])
def test_numpy_path_bit_identical_to_golden(name):
    path = GOLDEN_DIR / f"{name}.npz"
    if not path.exists():
        pytest.skip(f"golden {path.name} not present")
    got = _capture(name)
    if got is None:
        pytest.skip(f"dataset for state {name!r} not present")
    with np.load(path) as ref:
        assert set(ref.files) == set(got), (
            f"{name}: golden keys {sorted(ref.files)} != captured {sorted(got)}")
        for key in ref.files:
            a, b = ref[key], got[key]
            assert a.shape == b.shape, f"{name}:{key} shape {a.shape} != {b.shape}"
            assert np.array_equal(a, b), (
                f"{name}:{key} diverged from the pre-shim golden "
                f"(max |Δ| = {np.max(np.abs(a - b)) if a.dtype.kind == 'f' else '?'})")


if __name__ == "__main__":
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name in STATES:
        got = _capture(name)
        if got is None:
            print(f"{name}: dataset missing, skipped")
            continue
        out = GOLDEN_DIR / f"{name}.npz"
        np.savez_compressed(out, **got)
        sizes = {k: v.shape for k, v in got.items()}
        print(f"{name}: wrote {out} ({out.stat().st_size / 1e6:.2f} MB) {sizes}")
