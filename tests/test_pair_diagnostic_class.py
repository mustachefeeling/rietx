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
def test_the_two_site_winner_reaches_one_minimum_and_pairs_nothing():
    """The two-site Pnma set of ``test_magnetic_solve``, which carried this
    file's end-to-end naming check until WP-1930 showed both its pairs were
    stopping points.

    Mn1 (4b) and Mn2 (4a) are related by c/2, so l-even and l-odd reflections
    measure m₁ + m₂ and m₁ − m₂ separately, and the true point is not a flat
    valley.  The winner, class 0, pairs or not by where the walk stops: issue
    #820 measured ρ(Mn1, Mn2) at −0.962 in one macOS venv and −0.498 on Linux,
    either side of ``MOMENT_PAIR_RHO_MIN`` = 0.95, at one χ².  With the floor
    seed the "all" stage starts ``lor_size`` and ``gauss_strain`` off their
    floor, class 0's moment stage converges where it hit ``max_iter`` before,
    and ρ is −0.114 with Linux's esds.  The naming check moved to the 150 K
    Cr₂WO₆ solution, whose pair is structural
    (``test_magnetic_solve_acceptance``).

    Class 2, the flat model, is still a stopping point, so only the winner is
    asserted to pair nothing.  On macOS arm64 and on Intel Xeon CI runners
    all three of its starts stop at m ≈ 0, where |F_m|² ∝ m² has no gradient
    and no column to correlate.  On AMD EPYC 7763 runners two of the three
    reach m₁ ≈ m₂ ≈ 0.097, χ² lower by 41, where ρ = −0.99997 and the pair is
    named (0.137 +/- 5.738 μ_B).  Same commit, same wheels: the runner's CPU
    decides (#865).
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

    pairs = [d.message for d in solution.diagnostics
             if d.code == "MOMENT_PAIR_DEGENERATE"]
    assert not [m for m in pairs if m.startswith("class 0")], pairs
    winner = next(t for t in solution.trials if t.class_index == 0)
    assert not any(r.paired_with for r in winner.moments)
    assert winner.n_minima == 1
    m1, m2 = winner.moments
    assert m1.magnitude == pytest.approx(3.5, abs=0.01)
    assert m2.magnitude == pytest.approx(0.7, abs=0.01)
    # Linux's esds before the seed were 0.002 and 0.004 μ_B
    assert m1.esd < 0.01 and m2.esd < 0.01
