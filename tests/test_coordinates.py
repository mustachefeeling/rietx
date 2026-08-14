"""Atomic-coordinate refinement under Wyckoff site-symmetry constraints.

Structures used here on purpose:
* LaB6 (Pm-3m) — La on the fully fixed 1a site, B on 6f (x, ½, ½): one DOF.
* Rutile TiO2 (P42/mnm) — Ti on fixed 2a, O on 4f (x, x, 0): one DOF that
  moves two coordinates through the [1, 1, 0] constraint row.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.crystallography.structure_factor import compile_phase_sites
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from tests.test_schemas import make_lab6

RUTILE_OX = 0.3053


def make_rutile(o_x: float = RUTILE_OX, *, vary_coords: bool = False) -> Structure:
    return Structure(phases=[Phase(
        name="rutile",
        space_group="P42/mnm",
        cell=Cell(
            a=Parameter(value=4.5937, vary=True, min=0.1),
            b=Parameter(value=4.5937, min=0.1),
            c=Parameter(value=2.9587, vary=True, min=0.1),
            alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
            gamma=Parameter(value=90.0),
        ),
        atoms=[
            Atom(label="Ti", species="Ti", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="O", species="O", x=Parameter(value=o_x, vary=vary_coords),
                 y=Parameter(value=o_x), z=Parameter(value=0.0)),
        ],
    )])


def synthesize_rutile(*, noise_seed: int = 11) -> PatternData:
    structure = make_rutile()
    structure.phases[0].scale.value = 8.0e-3
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    tt = np.arange(15.0, 80.0, 0.02)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0())) + 30.0  # flat background floor
    rng = np.random.default_rng(noise_seed)
    y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


# -- wiring ------------------------------------------------------------


def test_site_dofs_wired_from_symmetry():
    table = ParameterTable(make_lab6(), Instrument.debye_scherrer(wavelength=0.4139))
    paths = {e.path: e for e in table.entries}
    # La 1a: fully fixed, no DOFs, coordinates locked against globs
    assert paths["phases.0.atoms.0.x"].locked
    assert "phases.0.atoms.0.dof.0" not in paths
    # B 6f (x, ½, ½): exactly one DOF; x tied to it, y and z locked
    assert "phases.0.atoms.1.dof.0" in paths
    assert "phases.0.atoms.1.dof.1" not in paths
    assert paths["phases.0.atoms.1.x"].tie is not None
    assert paths["phases.0.atoms.1.y"].locked
    assert not table.set_vary(["phases.0.atoms.*.x"], True)  # tied/locked: no hits
    assert table.set_vary(["phases.0.atoms.*.dof.*"], True) == ["phases.0.atoms.1.dof.0"]


def test_rutile_o_site_shares_one_dof():
    table = ParameterTable(make_rutile(), Instrument.debye_scherrer(wavelength=1.5406))
    paths = {e.path: e for e in table.entries}
    assert "phases.0.atoms.1.dof.0" in paths
    assert "phases.0.atoms.1.dof.1" not in paths
    x, y = paths["phases.0.atoms.1.x"], paths["phases.0.atoms.1.y"]
    assert x.tie.terms == (("phases.0.atoms.1.dof.0", 1.0),)
    assert y.tie.terms == (("phases.0.atoms.1.dof.0", 1.0),)
    assert paths["phases.0.atoms.1.z"].locked


def test_vary_on_fixed_site_raises():
    structure = make_lab6()
    structure.phases[0].atoms[0].x.vary = True  # La 1a — symmetry-fixed
    with pytest.raises(ValueError, match="fully fixed special position"):
        ParameterTable(structure, Instrument.debye_scherrer(wavelength=0.4139))


def test_vary_flag_seeds_dof():
    structure = make_rutile(vary_coords=True)
    table = ParameterTable(structure, Instrument.debye_scherrer(wavelength=1.5406))
    assert "phases.0.atoms.1.dof.0" in table.free_paths


# -- stage-boundary write-back -----------------------------------------


def test_coordinate_write_back_survives_stage_boundary():
    """Refined coordinates must reach the pydantic models before recompile."""
    structure = make_rutile()
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.atoms.1.dof.0"], True)

    theta = table.x0()
    theta[0] = 0.007  # displace the O site along [1, 1, 0]
    table.commit(theta)
    table.apply_to_models(structure, ins)

    o = structure.phases[0].atoms[1]
    assert o.x.value == pytest.approx(RUTILE_OX + 0.007, abs=1e-12)
    assert o.y.value == pytest.approx(RUTILE_OX + 0.007, abs=1e-12)
    assert o.z.value == 0.0

    # the next stage's compile sees the moved site: same frozen orbit size,
    # images generated at the new position
    sites = compile_phase_sites(structure.phases[0])
    rot, tran = sites.ops[1]
    images = rot @ np.array([o.x.value, o.y.value, o.z.value]) + tran
    assert len(images) == 4  # 4f multiplicity survives the displacement
    target = np.array([RUTILE_OX + 0.007, RUTILE_OX + 0.007, 0.0])
    assert np.min(np.abs(images - target).sum(axis=1)) < 1e-9

    # a fresh table re-anchors at the committed position (θ = 0)
    table2 = ParameterTable(structure, ins)
    v = table2.decode(table2.x0())
    assert v["phases.0.atoms.1.x"] == pytest.approx(RUTILE_OX + 0.007, abs=1e-12)
    assert v["phases.0.atoms.1.dof.0"] == 0.0


# -- round trip --------------------------------------------------------


def test_round_trip_rutile_coordinate(tmp_path):
    """Perturbed O x is recovered within its esd by the structural plan."""
    pattern = synthesize_rutile()
    structure = make_rutile(RUTILE_OX + 0.012)  # ~0.05 Å off along [110]
    structure.phases[0].scale.value = 6.0e-3
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1.2e-2

    ref = Refinement(structure, ins)
    result = ref.fit(pattern, plan="mccusker_structural")
    assert result.status == "converged"
    # against Poisson noise Rwp is bounded by Rexp; GoF is the honest gauge
    assert result.statistics.gof < 1.3

    o = ref.fitted_structure.phases[0].atoms[1]
    x_par = result.parameter("phases.0.atoms.1.x")
    assert x_par.stderr is not None and x_par.stderr > 0
    assert o.x.value == pytest.approx(RUTILE_OX, abs=max(5 * x_par.stderr, 5e-4))
    assert o.y.value == o.x.value  # constraint held through the whole run

    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / "coordinates_rutile_fit.png"))


def test_lebail_never_frees_coordinate_dofs():
    pattern = synthesize_rutile()
    structure = make_rutile(vary_coords=True)
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1.2e-2
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(pattern, mode="lebail", plan="mccusker_structural")
    freed = {p for s in result.stages for p in s.freed}
    assert not any(".dof." in p for p in freed)
