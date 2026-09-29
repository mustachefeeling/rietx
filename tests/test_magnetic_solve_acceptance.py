"""`solve_magnetic` on real data: Cr₂WO₆ at 4 K and 150 K (WP-1418, M-9).

The GSAS-II Magnetic-II tutorial patterns (HFIR HB-2A, λ 2.4067 Å, P4₂/mnm;
provenance in ``tests/data/README.md``), refined from the ideal trirutile start
by the session fixture ``conftest.cr2wo6_nuclear`` that WP-1326's and WP-1327's
acceptance suites already share, so the nuclear models here are exactly theirs.

Two arms, one per temperature, and each is the other's control:

* **4 K**: intensity sits on reciprocal-lattice points the nuclear structure
  factor forbids, so the k step takes the k = 0 route without consulting the
  candidate-k ranking, and 58.395, the group the tutorial refines and
  ``test_acceptance_magnetic.py`` states by hand, is ranked first with its
  class's powder-inseparable members named.
* **150 K**: above the ordering temperature there is nothing on a forbidden
  point, a handful of unexplained peaks match a zone-boundary k at about
  chance, and no class refined there improves on the nuclear model, so the
  answer is that there is nothing to solve rather than a winner.

obs/calc/diff PNGs of the 4 K winner go to ``tests/output/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("magnetic-cr2wo6")]

OUT = Path(__file__).parent / "output"


@pytest.fixture(scope="module")
def solved_4k(cr2wo6_nuclear):
    return rx.solve_magnetic(cr2wo6_nuclear["ref4"], cr2wo6_nuclear["d4"],
                             sites=["Cr1"], ion="Cr3+")


@pytest.fixture(scope="module")
def solved_150k(cr2wo6_nuclear):
    return rx.solve_magnetic(cr2wo6_nuclear["ref150"], cr2wo6_nuclear["d150"],
                             sites=["Cr1"], ion="Cr3+")


def test_the_4k_pattern_takes_the_k_zero_route_and_ranks_58_395_first(solved_4k):
    s = solved_4k
    assert s.k_route == "forbidden lattice points", s.k_reason
    assert tuple(str(c) for c in s.k) == ("0", "0", "0")
    assert s.n_on_forbidden_lattice_points > 0
    assert s.verdict == "solved", s.reason
    assert s.best.bns_number == "58.395"
    assert s.best.supported
    assert s.margin is not None and s.margin > s.tie_width
    # the class names what the powder cannot separate from the published group
    members = {m.split()[0] for m in s.best.members}
    assert {"58.395", "65.483", "10.44"} <= members
    # a moment of the size the tutorial reports, measured well clear of zero
    m = s.best.moments[0]
    assert 1.7 < m.magnitude < 2.4 and m.esd < 0.2

    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result

    plot_result(s.best._result, path=str(OUT / "magnetic_solve_cr2wo6_4K.png"))


def test_the_150k_pattern_has_nothing_to_solve(solved_150k):
    """No class wins, and none improves on the nuclear model.

    Not "no class is supported": that half of eligibility does not hold
    steadily here.  One class's powder-degenerate pair of child sites comes
    back with a quadrature sum near 0.60 μ_B while each row alone is
    unsupported, and whether the pair clears the null test the gate reads
    (``MomentRow.pair_supported``) has turned on its linearised esd: 0.09 μ_B
    (6.7σ, cleared) before WP-1321 passed declared ranges to the moment's
    ``Parameter`` (#527), 0.25 μ_B (2.4σ, not cleared) after, with the sum
    unchanged.  What keeps the class from winning either way is its ΔBIC,
    below zero, the other half of eligibility, so the assertion is on that
    half, since it is what this pattern establishes.
    """
    s = solved_150k
    assert s.n_on_forbidden_lattice_points == 0
    assert s.verdict == "nothing to solve", s.reason
    assert s.best is None and s.margin is None
    refined = [t for t in s.trials if t.status == "refined"]
    assert refined and all(t.delta_bic <= 0.0 for t in refined)
