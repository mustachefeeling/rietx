"""``MOMENT_PAIR_DEGENERATE`` on a ``solve_magnetic`` solution names its class (#742).

The solution lists the pairs of every class of every k tried, and a pair's
``where`` is two parameter paths that two classes share, so without the class a
pair found for a rival is indistinguishable from the winner's.
"""

from __future__ import annotations

import pytest

import rietx as rx
from rietx.schemas.common import Diagnostic
from rietx.schemas.structure import MagneticSymmetry, Moment


def _pair() -> Diagnostic:
    return Diagnostic(level="info", code="MOMENT_PAIR_DEGENERATE",
                      message="a and b are a powder-degenerate moment pair",
                      where=["phases.0.atoms.0.moment.dof0",
                             "phases.0.atoms.1.moment.dof0"], value=3.5)


def test_the_message_opens_with_the_class_and_nothing_else_moves():
    from rietx.strategy.magnetic import _named_for_class

    (named,) = _named_for_class([_pair()], 2, (0, 0, 0))
    assert named.message.startswith("class 2: a and b are")
    assert named.where == _pair().where and named.value == 3.5
    assert named.code == "MOMENT_PAIR_DEGENERATE"


def test_a_propagation_vector_off_gamma_is_named_too():
    from rietx.strategy.magnetic import _named_for_class

    (named,) = _named_for_class([_pair()], 0, (0.5, 0, 0.5))
    assert named.message.startswith("class 0 (k = (0.5, 0, 0.5)): ")


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-two-site")
def test_the_two_site_winner_finds_each_site_its_own_moment():
    """The two-site Pnma set of ``test_magnetic_solve``, which carried this
    file's end-to-end naming check until WP-1930 showed both its pairs were
    stopping points.

    Mn1 (4b) and Mn2 (4a) are related by c/2, so l-even and l-odd reflections
    measure m₁ + m₂ and m₁ − m₂ separately.  Swapping the two moduli leaves
    the size of each combination unchanged.  The swapped point is a second
    minimum, χ² higher by only 0.66 (2556.51 against 2555.85, macOS arm64).  The flat start lands on it
    under both drivers since the floor seed went (WP-1938 D4), so the sweep
    reports two minima and the released start that reaches the truth wins.
    Under LM the released starts reach it only because the moduli climb before
    the angles turn (D12): freed together, they stopped at χ² 454 660.

    Whether the winner's moduli are named a pair is left out.  Both moments lie
    along **a**, where the azimuth is stationary, and how far from it the
    solver stops decides the moduli esds and ρ (WP-1929 task 4).  Issue #820
    measured ρ at −0.962 on one macOS venv and −0.498 on Linux, either side of
    ``MOMENT_PAIR_RHO_MIN``; under LM on macOS arm64 the esds are 0.031 and
    0.159 μ_B and the pair is named.  A named pair still has to quote the
    quadrature sum the data measure, so that is asserted.

    Class 2, the flat model, is still a stopping point, so nothing is asserted
    about it.  On macOS arm64 and on Intel Xeon CI runners all three of its
    starts stopped at m ≈ 0 under TRF.  On AMD EPYC 7763 runners two of the
    three reached m₁ ≈ m₂ ≈ 0.097 and named the pair: the runner's CPU decided
    (#865).
    """
    from tests import test_magnetic_solve as T

    instrument = T.neutron()
    truth = T.candidate_named("P n m a", T.MN_SITE, (0, 0, 0), T.A_TYPE_BNS)
    ops, cent = truth.group.xyz_strings()
    data = T.simulate(T.two_site(
        m1=Moment.from_values((3.5, 0.0, 0.0), "Mn3+"),
        m2=Moment.from_values((0.7, 0.0, 0.0), "Mn3+"),
        magnetic=MagneticSymmetry(operations=list(ops),
                                  centerings=list(cent))), instrument)
    ref = T.nuclear_fit(T.two_site(), data, instrument)
    solution = rx.solve_magnetic(ref, data, sites=["Mn1", "Mn2"], ion="Mn3+")

    winner = next(t for t in solution.trials if t.class_index == 0)
    assert solution.best is not None and solution.best.class_index == 0
    m1, m2 = winner.moments
    assert m1.magnitude == pytest.approx(3.5, abs=0.01)
    assert m2.magnitude == pytest.approx(0.7, abs=0.01)
    for row in winner.moments:
        if row.paired_with:
            assert row.paired_magnitude == pytest.approx(
                (3.5 ** 2 + 0.7 ** 2) ** 0.5, abs=0.01)
