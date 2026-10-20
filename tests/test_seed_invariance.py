"""The roughness stage's seed does not change the answer (WP-2002, batch item B3).

``strategy.staged._ROUGHNESS_STAGE`` starts Suortti's b at 0.3.  On its floor
of 0 the correction is the identity, and GSAS-II starts there.  b is bimodal
(``RoughnessSuortti``'s docstring): one low-angle depression is reached by two
values of b, one on each side of a sensitivity peak.  So the start could pick
the branch, and through roughness's trade with Biso it could pick the Biso.

Measured on 2026-10-20 (macOS arm64, worktree venv ``[dev]``) on five lab
Bragg-Brentano patterns from three laboratories (NIST, the GSAS-II lab data,
the CPD round robin's CSIRO instrument), so three families.  Each ran its own acceptance protocol with a Suortti
block declared and the roughness stage appended last, once from b = 0.3 and
once from b = 0.  Every Biso, every scale and b agreed between the two starts
to within 2.7e-3 of the smaller of their two esds.  χ² agreed to 1.4e-4
relative or better.

=========================  ====================  ====================  ==========
family                     b from 0.3            b from 0              max Δ/esd
=========================  ====================  ====================  ==========
FAP (this file)            0.8126(3185), high    0.8127(3185), high    9.4e-5
SRM 660c LaB6              0, off                0, off                2.7e-3
CPD corundum               0, off                0, off                3.8e-5
CPD fluorite               0.024(5.6), low       0.012(5.6), low       2.1e-3
CPD zincite                0.33 with a = 1, off  0, off                7.2e-6
=========================  ====================  ====================  ==========

"high" and "low" are the side of the sensitivity peak, computed at the fitted
a for each pattern's lowest angle (0.369 for FAP from 15°).  "off" means
R ≡ 1, either from b = 0 or from a = 1.  Biso sat the same distance from each
reference under both starts: NIST's CIF Uiso for LaB6 (+2.7 and +3.8 esd),
GSAS's converged FAP.EXP for FAP (+1.8 to +2.3 esd).  So neither start is
closer to a reference, and the ruled switch to GSAS-II's 0 does not apply.

FAP is the family this test fits, because only there does the data support a
roughness off its floor in both starts.  From b = 0 the fit must cross the
sensitivity peak to reach the high branch, which is the hazard the brief named.
The start costs iterations, never the answer: 20 from 0.3 against 91 from 0.

The margin is the width of the basin both starts sit in.  A stored start of
b = 1.5 reaches the same answer.  Starts of 2.5, 3.5 and 4.9 stall on the dead
branch, with the depression at 15° under 0.1, and the branch assertion below
fails on them.  That failure is how this test was shown to be able to fail.
So the basin's upper edge lies between 1.5 and 2.5, five to eight times the
seed.

Two things the table does not claim.  The *esds* of Biso and the scale differ
between starts on corundum (×1.3 to ×2.3) and zincite (×1.1 to ×4.4).  Both
are fits where roughness ends switched off, and the two starts stop at
different points of the off state (b = 0 with a free, or a = 1).  At a = 1 the
b column is identically zero, so b leaves the covariance and the neighbours'
esds are conditional; at b = 0 with a < 1 the floored b row stays in it and
theirs are marginal (WP-1929).  And Pitschke's ``c`` shares the 0.3 literal but
is *not* start-invariant: from c = 0 on zincite it lands in its turned-over
regime (R ≈ 0.5 at every peak, scale ×2.1, χ² 4.8 % lower,
``ROUGHNESS_OUTSIDE_REGIME``), and on corundum Biso moves by 0.26 of the
smaller esd.  This file asserts neither.

Dispersion is **declined**, inherited from ``build_fap_inputs`` and restated
below, because the FAP protocol is the cross-code row against GSAS.
"""

import dataclasses
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.corrections import surface_roughness_suortti
from rietx.schemas import RoughnessSuortti
from rietx.strategy.staged import _ROUGHNESS_STAGE
from tests.test_acceptance_fap import _gsas_protocol_plan, build_fap_inputs

OUT = Path(__file__).parent / "output"
B = "instrument.geometry.surface_roughness.b"
A = "instrument.geometry.surface_roughness.a"
#: agreement bar between the two starts, as a fraction of the larger esd.
#: Measured 9.4e-5 at most on this protocol, so the bar has ~100× margin.
ESD_FRACTION = 0.01
#: χ² agreement, relative.  Measured 1.1e-10.
CHI2_RELATIVE = 1e-6

pytestmark = pytest.mark.slow


def _fit(stage: rx.Stage, tag: str):
    data, structure, instrument = build_fap_inputs()
    instrument.source.dispersion = None
    instrument.geometry.surface_roughness = RoughnessSuortti()
    plan = _gsas_protocol_plan()
    plan.stages.append(stage)
    ref = rx.Refinement(structure, instrument, history=False)
    result = ref.fit(data, plan=plan)
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"seed_invariance_fap_{tag}.png"))
    result.plot(path=str(OUT / f"seed_invariance_fap_{tag}_lowangle.png"),
                two_theta_range=(15.0, 55.0))
    import matplotlib.pyplot as plt

    plt.close("all")
    return ref, result


def _sensitivity_peak(a: float, two_theta_min: float) -> float:
    """The b at which the depression at the lowest fitted angle is largest."""
    grid = np.linspace(0.005, 3.0, 3000)
    depth = 1.0 - surface_roughness_suortti(np.full(grid.size, two_theta_min),
                                            a, grid)
    return float(grid[int(np.argmax(depth))])


def test_the_roughness_seed_does_not_change_the_answer():
    shipped = _ROUGHNESS_STAGE[0]
    assert shipped.seed > 0.0, (
        "the shipped roughness stage no longer seeds b, so this comparison of "
        "its seed against a start at 0 compares 0 with 0; rethink the test")
    runs = {"seeded": _fit(shipped, "seeded"),
            "zero": _fit(dataclasses.replace(shipped, seed=0.0), "zero")}

    # the two arms really started apart, and both finished
    assert runs["seeded"][1].stages[-1].seeded == {B: shipped.seed}
    assert runs["zero"][1].stages[-1].seeded == {}
    for _, result in runs.values():
        assert result.stages[-1].name == "roughness"
        assert result.stages[-1].status == "converged"

    # the data support a roughness off its floor (depression 0.27 at 15°),
    # and both starts reach the branch above the sensitivity peak
    two_theta_min = 15.0
    for _, result in runs.values():
        values = {p.path: p.value for p in result.parameters}
        a, b = values[A], values[B]
        depression = 1.0 - float(surface_roughness_suortti(
            np.array([two_theta_min]), a, b)[0])
        assert depression > 0.1
        assert b > _sensitivity_peak(a, two_theta_min)

    # every Biso, the scale, a and b agree to a hundredth of their esds
    seeded = {p.path: p for p in runs["seeded"][1].parameters}
    zero = {p.path: p for p in runs["zero"][1].parameters}
    compared = [p for p in seeded
                if p.endswith(".biso") or p.endswith(".scale") or p in (A, B)]
    assert len(compared) == 7 + 1 + 2
    for path in compared:
        p, q = seeded[path], zero[path]
        assert p.stderr and q.stderr, f"{path} carries no esd"
        assert abs(p.value - q.value) <= ESD_FRACTION * max(p.stderr, q.stderr), path

    chi2 = [result.statistics.chi2 for _, result in runs.values()]
    assert abs(chi2[0] - chi2[1]) <= CHI2_RELATIVE * chi2[0]
