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
def test_every_pair_on_a_solution_names_a_class_whose_rows_carry_it():
    """The two-site Pnma set of ``test_magnetic_solve``: every class's pair is
    reported under the same two paths, so only the class tells them apart.
    Each message names its own class, and that class's trial carries the pair.

    How many classes pair is not asserted, because it depends on the machine
    (#820). Class 2, the flat model, pairs at ρ = −1.0000 everywhere. The
    winner, class 0, reaches the same minimum everywhere (χ²_red 1.0574465,
    Mn1 3.498 and Mn2 0.700 μ_B, the stated moments). Its ρ(Mn1, Mn2) is
    −0.962 in one macOS arm64 venv and −0.498 on Linux x86-64, either side of
    ``MOMENT_PAIR_RHO_MIN`` = 0.95. That venv reports two pairs; Linux and
    another macOS venv report one. A count of two has failed on Linux since
    the commit that added it. Mn1 (4b)
    and Mn2 (4a) are related by c/2, so l-even and l-odd reflections can
    measure m₁ + m₂ and m₁ − m₂ separately. Linux's esds there, 0.002 and
    0.004 μ_B, say the true point is not a flat valley. Why the Mac's
    covariance differs at the same χ² is a separate question, left open in
    #820."""
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

    pairs = [d for d in solution.diagnostics
             if d.code == "MOMENT_PAIR_DEGENERATE"]
    assert pairs, [d.message for d in solution.diagnostics]
    assert len({tuple(d.where) for d in pairs}) == 1   # the shared paths
    classes = set()
    for d in pairs:
        assert d.message.startswith("class "), d.message
        index = int(d.message.split(":")[0].split()[1])
        trial = next(t for t in solution.trials if t.class_index == index)
        assert any(r.paired_with for r in trial.moments), (index, d.message)
        classes.add(index)
    assert len(classes) == len(pairs)
    # and a class whose rows are not paired is named by no message
    unpaired = {t.class_index for t in solution.trials
                if not any(r.paired_with for r in t.moments)}
    assert not classes & unpaired
