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
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Moment, Phase

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


def mnf2() -> Phase:
    """MnF₂, P 4₂/mnm under BNS 136.499, Mn moment 4.6 μ_B along c.

    Erickson (1953), *Phys. Rev.* **90**, 779.  Its strongest magnetic line,
    (1 0 0), is a screw absence of the nuclear group, so it is a
    magnetic-only row of the k = 0 reflection list.
    """
    return Phase(
        name="MnF2", space_group="P 42/m n m", cell=_cell(4.8734, 4.8734, 3.3099),
        atoms=[Atom(label="Mn1", species="Mn", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0),
                    biso=Parameter(value=0.4),
                    moment=Moment.from_values((0.0, 0.0, 4.6), "Mn2+")),
               Atom(label="F1", species="F", x=Parameter(value=0.305),
                    y=Parameter(value=0.305), z=Parameter(value=0.0),
                    biso=Parameter(value=0.6))],
        magnetic_symmetry="136.499")


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
    """A k = 0 magnetic phase: two ``hkl:`` traces, one nuclear and one
    "(magnetic)", and the screw-absent (1 0 0) on the magnetic one."""
    instrument = neutron()
    phase = mnf2()
    data = simulate(phase, instrument)

    ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
    ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("moment", ["phases.*.atoms.*.moment.dof*"])]))
    result = ref.result_

    names = {name for name in result.ticks}
    assert phase.name in names
    assert f"{phase.name} (magnetic)" in names
    assert result.ticks[f"{phase.name} (magnetic)"], \
        "the magnetic row must not be empty on a phase that carries a moment"
    assert [1, 0, 0] in result.tick_hkl[f"{phase.name} (magnetic)"]
    assert [1, 0, 0] not in result.tick_hkl[phase.name]

    from rietx.viz.html import write_html
    out = tmp_path / "magnetic.html"
    write_html(result, str(out))
    html = out.read_text(encoding="utf-8")
    trace_names = _tick_trace_names(html)
    assert phase.name in trace_names
    assert f"{phase.name} (magnetic)" in trace_names


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
