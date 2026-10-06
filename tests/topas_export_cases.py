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

from fractions import Fraction

import numpy as np

import rietx as rx
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import BackgroundChebyshev, BackgroundPSpline, Dispersion
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
    # declared, not inherited: TOPAS 6's Y_calc carries the anomalous term, and
    # rietx matches it with dispersion on (2.4e-3), not off (4.4e-2)
    source = inst.source.model_copy(update={"dispersion": Dispersion()})
    inst = inst.model_copy(update={
        "source": source,
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


def pbcm_child() -> Phase:
    """A k = (½, 0, 0) child of a synthetic Pbcm parent (``magnetic_supercell``):
    TOPAS has no ``mag_space_group`` for it, so the writer restates it in P1."""
    from rietx.crystallography.magnetic.isotropy import candidates
    from rietx.crystallography.magnetic.supercell import magnetic_supercell

    parent = Phase(name="synthetic Pbcm", space_group="P b c m",
                   cell=_cell(5.0, 9.0, 9.5),
                   atoms=[_atom("Fe", "Fe", (0.25, 0.125, 0.25), 0.5),
                          _atom("O", "O", (0.0, 0.375, 0.25), 0.8)])
    cand = candidates(parent.space_group, (0.25, 0.125, 0.25),
                      (Fraction(1, 2), 0, 0)).candidates[0]
    return magnetic_supercell(parent, cand, magnetic_species="Fe", ion="Fe3+",
                              magnitude=3.0).phase


def case_child_magnetic():
    """The Pbcm child with a magnetic-only Lorentzian width, a P-spline
    background and FCJ axial divergence, refined as a plan would leave it: the
    moment, the scale, the B and the magnetic width free, the anti-translation
    partners tied and one B per parent site."""
    from rietx.crystallography.magnetic.supercell import anti_translation_ties

    child = pbcm_child()
    child = child.model_copy(update={
        "scale": P(value=5.0e-3, min=0.0, transform="softplus"),
        "magnetic_lor_strain": P(value=0.3, min=0.0, transform="softplus")})
    inst = _tchz(rx.Instrument.constant_wavelength_neutron(2.4),
                 u=0.3, v=-0.2, w=0.1, x=0.05, y=0.02)
    tt = np.arange(8.0, 120.0, 0.1)
    knots = list(np.linspace(tt[0], tt[-1], 12))
    geom = inst.geometry.model_copy(update={
        "axial_sl": inst.geometry.axial_sl.model_copy(update={"value": 0.01}),
        "axial_hl": inst.geometry.axial_hl.model_copy(update={"value": 0.02})})
    inst = inst.model_copy(update={
        "geometry": geom,
        "background": BackgroundPSpline(
            breakpoints=knots,
            coefficients=[P(value=200.0 + 30.0 * np.cos(k / 3.0)) for k in range(14)],
            lambda_smooth=1.0)})
    ref = rx.Refinement(rx.Structure(phases=[child]), inst, history=False)
    for t, so, sc, off in anti_translation_ties(child):
        ref.tie(t, so, scale=sc, offset=off)
    groups: dict[str, list[int]] = {}
    for j, a in enumerate(child.atoms):
        groups.setdefault(a.label.rsplit("_", 1)[0], []).append(j)
    for js in groups.values():
        if len(js) > 1:
            ref.tie_equal([f"phases.0.atoms.{j}.biso" for j in js])
    rows = {r.path: r for r in ref.parameters()}
    free = ["phases.0.scale", "phases.0.magnetic_lor_strain"] + [
        p for p, r in rows.items()
        if r.tie is None and not r.locked and (p.endswith(".biso") or ".moment.dof" in p)]
    ref.set_vary(free, True)
    return ref, _pattern(ref, tt)


CASES = {"nacl_neutron": case_nacl_neutron, "nacl_xray": case_nacl_xray,
         "nacl_pspline": case_nacl_pspline, "child_magnetic": case_child_magnetic}


def write_case(name, path):
    """The case's ``.inp`` as the tests and the oracle kit both write it."""
    ref, pattern = CASES[name]()
    rx.write_topas_inp(ref.fitted_structure, path, free=ref,
                       instrument=ref.fitted_instrument, pattern=pattern,
                       scale="topas", p1_expand="auto")
    return ref, pattern
