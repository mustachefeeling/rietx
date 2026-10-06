"""The floating origin of a polar group, and ``Refinement.hold_floating_origin()`` (#727, opt-in)."""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.wyckoff import floating_origin_basis


@pytest.mark.parametrize("group, rows", [
    ("P 63 m c", [[0, 0, 1]]),
    ("P 4 m m", [[0, 0, 1]]),
    ("P n a 21", [[0, 0, 1]]),
    ("P 1 21 1", [[0, 1, 0]]),
    ("C 1 c 1", [[1, 0, 0], [0, 0, 1]]),
    ("P 1", [[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
    ("R 3 c:H", [[0, 0, 1]]),
])
def test_a_polar_group_floats_along_its_polar_directions(group, rows):
    basis = floating_origin_basis(group)
    assert sorted(map(tuple, basis.tolist())) == sorted(map(tuple, rows))


@pytest.mark.parametrize("group", [
    "P 21 21 21", "P n m a", "F d -3 m", "P 21/c", "P 6/m m m", "P -1"])
def test_a_non_polar_group_has_only_discrete_origin_choices(group):
    assert len(floating_origin_basis(group)) == 0


def _zno(z_zn: float = 0.0, z_o: float = 0.382):
    P = rx.Parameter

    def atom(label, species, x, y, z, b):
        return rx.Atom(label=label, species=species, x=P(value=x), y=P(value=y),
                       z=P(value=z), biso=P(value=b))

    return rx.Phase(
        name="zno", space_group="P 63 m c",
        cell=rx.Cell(a=P(value=3.2495), b=P(value=3.2495), c=P(value=5.2069),
                     alpha=P(value=90.0), beta=P(value=90.0),
                     gamma=P(value=120.0)),
        scale=P(value=0.01),
        atoms=[atom("Zn", "Zn", 1 / 3, 2 / 3, z_zn, 0.5),
               atom("O", "O", 1 / 3, 2 / 3, z_o, 0.6)])


def _pattern():
    grid = np.arange(15.0, 100.0, 0.02)
    truth = rx.Refinement(rx.Structure(phases=[_zno()]),
                          rx.Instrument.bragg_brentano(radiation="CuKa"),
                          history=False)
    y = np.asarray(truth.predict(grid)) + 50.0
    y = np.maximum(y + np.random.default_rng(3).normal(
        scale=np.sqrt(np.maximum(y, 1.0))), 0)
    return rx.PatternData(two_theta=grid.tolist(), intensity=y.tolist())


PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
    rx.Stage("xyz", ["phases.*.scale", "instrument.background.c*",
                     "phases.*.atoms.*.dof.*"])])


def test_a_hold_leaves_one_z_and_the_other_is_quoted_against_it():
    data = _pattern()
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    ins.background = rx.auto_background(data)
    # a start displaced along c: the pair's common shift changes no intensity
    free = rx.Refinement(rx.Structure(phases=[_zno(0.05, 0.432)]), ins,
                         history=False)
    held = rx.Refinement(rx.Structure(phases=[_zno(0.05, 0.432)]), ins,
                         history=False)
    diagnostics = held.hold_floating_origin()
    assert [d.code for d in diagnostics] == ["ORIGIN_FIXED_ON_POLAR_AXIS"]
    assert diagnostics[0].where == ["phases.0.atoms.0.dof.0"]

    r_free = free.fit(data, plan=PLAN, telemetry=False)
    r_held = held.fit(data, plan=PLAN, telemetry=False)
    z = lambda ref, i: ref.fitted_structure.phases[0].atoms[i].z.value  # noqa: E731
    # held: Zn stays at its start, and O moves to the right distance from it
    assert z(held, 0) == pytest.approx(0.05, abs=1e-12)
    assert z(held, 1) - z(held, 0) == pytest.approx(0.382, abs=5e-3)
    # not held: the pair is free to slide and the fit says so
    assert "FLAT_DIRECTION" in {d.code for d in r_free.diagnostics}
    assert "FLAT_DIRECTION" not in {d.code for d in r_held.diagnostics}
    # the same fit quality, so nothing was lost by holding
    assert r_held.statistics.rwp == pytest.approx(r_free.statistics.rwp, rel=1e-2)
    # the default does nothing: a refinement never asked holds nothing
    assert not rx.Refinement(rx.Structure(phases=[_zno()]), ins,
                             history=False)._user_holds


def test_a_non_polar_group_holds_nothing():
    P = rx.Parameter
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    polar = rx.Refinement(rx.Structure(phases=[_zno()]), ins, history=False)
    assert len(polar.hold_floating_origin()) == 1
    pnma = rx.Phase(
        name="p", space_group="P n m a",
        cell=rx.Cell(a=P(value=5.7), b=P(value=7.7), c=P(value=5.5),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        atoms=[rx.Atom(label="La", species="La", x=P(value=0.05), y=P(value=0.25),
                       z=P(value=0.99), biso=P(value=0.5))])
    ref = rx.Refinement(rx.Structure(phases=[pnma]), ins, history=False)
    assert ref.hold_floating_origin() == [] and not ref._user_holds
