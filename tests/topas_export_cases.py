"""Synthetic models whose TOPAS export was run in TOPAS as a black box.

Each case is a model of ours, built here and nowhere else, so the oracle files
in ``tests/data/topas_export_<case>_ycalc.txt`` (TOPAS-64 v6's Y_calc at zero
cycles for a whole TOPAS input written from the case: the ``str`` block, the
background, the zero shift and any extinction term, which
:func:`rietx.write_topas_inp` does not write whole) and the tests that read
them build exactly the same thing. Nothing here is measured
data: every pattern is rietx's own ``predict()`` of the case, and TOPAS's
answer is compared with it point for point.
"""

from __future__ import annotations

import numpy as np

import rietx as rx
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import BackgroundChebyshev, BackgroundPSpline
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


def case_nacl_xray():
    """NaCl, a Cu Kα₁/Kα₂ laboratory pattern (K = 0.5) and a specimen
    displacement: ``LP_Factor``, the X-ray scale constant K and the
    displacement's sign and unit."""
    inst = _tchz(rx.Instrument.bragg_brentano(radiation="CuKa"),
                 u=0.004, v=-0.002, w=0.003, x=0.01, y=0.005)
    geom = inst.geometry.model_copy(update={
        "sample_displacement": inst.geometry.sample_displacement.model_copy(
            update={"value": 0.05})})
    inst = inst.model_copy(update={
        "geometry": geom,
        "background": BackgroundChebyshev(coefficients=[
            P(value=v) for v in (50.0, -10.0, 4.0)])})
    structure = rx.Structure(phases=[nacl(scale=1.0e-4)])
    ref = rx.Refinement(structure, inst, history=False)
    return ref, _pattern(ref, np.arange(20.0, 120.0, 0.01))


def case_nacl_pspline():
    """NaCl, constant-wavelength neutrons, a smoothed P-spline background and FCJ
    axial divergence, the background and B free: rietx's own background model
    and asymmetry, as TOPAS ``fit_obj`` pieces, ``penalty`` terms and
    ``Finger_et_al``."""
    inst = _tchz(rx.Instrument.constant_wavelength_neutron(2.4),
                 u=0.3, v=-0.2, w=0.1, x=0.05, y=0.02)
    tt = np.arange(10.0, 130.0, 0.1)
    geom = inst.geometry.model_copy(update={
        "axial_sl": inst.geometry.axial_sl.model_copy(update={"value": 0.01}),
        "axial_hl": inst.geometry.axial_hl.model_copy(update={"value": 0.02})})
    inst = inst.model_copy(update={
        "geometry": geom,
        "background": BackgroundPSpline(
            breakpoints=list(np.linspace(tt[0], tt[-1], 12)),
            coefficients=[P(value=200.0 + 30.0 * np.cos(k / 3.0)) for k in range(14)],
            lambda_smooth=1.0)})
    ref = rx.Refinement(rx.Structure(phases=[nacl(scale=2.0e-3)]), inst, history=False)
    ref.set_vary(["instrument.background.*", "phases.0.atoms.*.biso", "phases.0.scale",
                  "instrument.geometry.axial_hl"], True)
    return ref, _pattern(ref, tt)


CASES = {"nacl_neutron": case_nacl_neutron, "nacl_xray": case_nacl_xray,
         "nacl_pspline": case_nacl_pspline}


def write_case(name, path):
    """The case's ``.inp`` as the tests and the oracle kit both write it."""
    ref, pattern = CASES[name]()
    rx.write_topas_inp(ref.fitted_structure, path, free=ref,
                       instrument=ref.fitted_instrument, pattern=pattern,
                       scale="topas")
    return ref, pattern
