"""Issue #278: a magnetic phase's reflections draw as their own tick row,
colour and vertical offset -- a second entry in ``result.ticks``
(``"<phase> (magnetic)"``), split from the nuclear row by the same purity
cut WP-1343 defines upstream (this branch's own copy, ``MAGNETIC_TICK_PURITY``
in ``refine.py`` -- see its docstring for why the branches disagree here).
"""

from __future__ import annotations

import re

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.supercell import magnetic_supercell
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase

LAMBDA_CW = 2.4
GRID = np.arange(8.0, 130.0, 0.05)


def _cell(a, b, c):
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))


def tetragonal() -> Phase:
    return Phase(
        name="tetragonal", space_group="P 4/m m m", cell=_cell(4.0, 4.0, 4.2),
        atoms=[Atom(label="Mn1", species="Mn", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0),
                    biso=Parameter(value=0.4)),
               Atom(label="O1", species="O", x=Parameter(value=0.5),
                    y=Parameter(value=0.5), z=Parameter(value=0.5),
                    biso=Parameter(value=0.6))])


def neutron():
    return rx.Instrument.constant_wavelength_neutron(LAMBDA_CW, fwhm_deg=0.35)


def simulate(phase, instrument, *, background=40.0, seed=20260909):
    ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
    y = np.asarray(ref.predict(GRID)) + background
    rng = np.random.default_rng(seed)
    y = y + rng.normal(scale=np.sqrt(np.maximum(y, 1.0)))
    return rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())


def _tick_trace_names(html: str) -> list[str]:
    return sorted(set(re.findall(r'"hkl: ([^"]*)"', html)))


@pytest.mark.slow
def test_a_magnetic_phase_draws_two_tick_rows(tmp_path):
    """A k=(0,0,1/2) magnetic tetragonal phase: two ``hkl:`` traces, one
    nuclear and one "(magnetic)"."""
    instrument = neutron()
    truth = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]
    statement = magnetic_supercell(tetragonal(), truth, magnetic_species=["Mn1"],
                                   ion={"Mn1": "Mn3+"}, magnitude=3.0)
    data = simulate(statement.phase, instrument)

    ref = rx.Refinement(rx.Structure(phases=[statement.phase]), instrument)
    ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("moment", ["phases.*.atoms.*.moment.dof*"])]))
    result = ref.result_

    names = {name for name in result.ticks}
    assert statement.phase.name in names
    assert f"{statement.phase.name} (magnetic)" in names
    assert result.ticks[f"{statement.phase.name} (magnetic)"], \
        "the magnetic row must not be empty on a phase that carries a moment"

    from rietx.viz.html import write_html
    out = tmp_path / "magnetic.html"
    write_html(result, str(out))
    html = out.read_text(encoding="utf-8")
    trace_names = _tick_trace_names(html)
    assert statement.phase.name in trace_names
    assert f"{statement.phase.name} (magnetic)" in trace_names


def test_a_non_magnetic_phase_draws_one_tick_row(tmp_path):
    """No ``magnetic_symmetry``: exactly one ``hkl:`` trace, as before #278."""
    instrument = neutron()
    data = simulate(tetragonal(), instrument)
    ref = rx.Refinement(rx.Structure(phases=[tetragonal()]), instrument)
    ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"])]))
    result = ref.result_

    assert list(result.ticks) == ["tetragonal"]

    from rietx.viz.html import write_html
    out = tmp_path / "nuclear.html"
    write_html(result, str(out))
    html = out.read_text(encoding="utf-8")
    assert _tick_trace_names(html) == ["tetragonal"]
