"""Synthetic models whose TOPAS export was run in TOPAS as a black box.

Each case is a model of ours, built here and nowhere else, so the oracle files
in ``tests/data/topas_export_<case>_ycalc.txt`` (TOPAS-64 v6's Y_calc at zero
cycles for the file :func:`rietx.write_topas_inp` writes for the case) and the
tests that read them build exactly the same thing. Nothing here is measured
data: every pattern is rietx's own ``predict()`` of the case, and TOPAS's
answer is compared with it point for point.
"""

from __future__ import annotations

import numpy as np

import rietx as rx
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, Phase


def _cell(a, b, c, alpha=90.0, beta=90.0, gamma=90.0) -> Cell:
    return Cell(a=P(value=a), b=P(value=b), c=P(value=c), alpha=P(value=alpha),
                beta=P(value=beta), gamma=P(value=gamma))


def _atom(label, species, xyz, biso=0.6) -> Atom:
    return Atom(label=label, species=species, x=P(value=xyz[0]), y=P(value=xyz[1]),
                z=P(value=xyz[2]), biso=P(value=biso, min=0.0, max=25.0, unit="A^2"))


def nacl(scale=1.0e-3, extinction=0.0) -> Phase:
    return Phase(name="NaCl", space_group="F m -3 m", cell=_cell(5.6402, 5.6402, 5.6402),
                 atoms=[_atom("Na", "Na", (0.0, 0.0, 0.0), 1.1),
                        _atom("Cl", "Cl", (0.5, 0.5, 0.5), 0.9)],
                 scale=P(value=scale, min=0.0, transform="softplus"),
                 extinction=P(value=extinction, min=0.0, transform="softplus"))


def _tchz(inst, u=0.02, v=-0.01, w=0.01, x=0.02, y=0.01):
    prof = inst.profile.model_copy(update={
        k: getattr(inst.profile, k).model_copy(update={"value": val})
        for k, val in dict(u=u, v=v, w=w, x=x, y=y).items()})
    return inst.model_copy(update={"profile": prof})


def _pattern(ref, tt):
    y = np.asarray(ref.predict(tt))
    return rx.PatternData(two_theta=list(tt), intensity=list(y),
                          sigma=list(np.sqrt(np.maximum(y, 1.0))))


def case_nacl_neutron():
    """NaCl, constant-wavelength neutrons, a Chebyshev background, a zero shift
    and Sabine extinction on: the scale convention and the extinction term."""
    inst = _tchz(rx.Instrument.constant_wavelength_neutron(1.594))
    inst = inst.model_copy(update={
        "zero_shift": inst.zero_shift.model_copy(update={"value": 0.02}),
        "background": BackgroundChebyshev(coefficients=[
            P(value=v) for v in (300.0, -40.0, 15.0, -5.0)])})
    structure = rx.Structure(phases=[nacl(scale=2.0e-3, extinction=40.0)])
    ref = rx.Refinement(structure, inst, history=False)
    return ref, _pattern(ref, np.arange(10.0, 150.0, 0.05))


CASES = {"nacl_neutron": case_nacl_neutron}
