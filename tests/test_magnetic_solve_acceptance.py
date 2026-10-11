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
    """No class wins, none improves on the nuclear model, and none is supported.

    The few unexplained peaks match k = (0, ½, ½) at about chance, and two
    classes refine there.  Class 1's moments go to zero, where its child sites
    fold into a powder-degenerate pair whose quadrature sum is zero.  Class 3's
    moments stay near 0.14 and 0.58 μ_B with esds of 2.3 and 0.5 μ_B, which the
    data cannot measure, and its fit wanders that flat valley through every
    continuation of the stages' budget (``SOLVE_MAX_CONTINUATIONS``).  It stops
    short under TRF and LM alike (macOS arm64, WP-1938 D12).  The solution
    lists such a trial with a caveat and does not rank it, so the verdict does
    not rest on where it stopped.  Under the softplus coordinates it reported
    ``converged`` after 3-7 continuations, because a modulus near zero lost its
    column there.

    Which pair the fold finds, and its size, follows where each fit stopped.
    The rule behind the pair esd (one covariance for ρ and both σ's) is pinned
    on its own in ``test_magnetic_solve.py``.
    """
    s = solved_150k
    assert s.n_on_forbidden_lattice_points == 0
    assert s.verdict == "nothing to solve", s.reason
    assert s.best is None and s.margin is None
    refined = [t for t in s.trials if t.status == "refined"]
    assert refined and all(t.delta_bic <= 0.0 for t in refined)
    # a trial stopped short is listed with its caveat and left out of the ranking
    for t in refined:
        if t.fit_status != "converged":
            assert any(c.startswith(f"class {t.class_index}: the trial fit stopped")
                       and "not ranked" in c for c in s.caveats), (t.class_index,
                                                                    s.caveats)
    assert not any(t.supported for t in refined)
    paired = [m for t in refined for m in t.moments if m.paired_with]
    assert paired, "the degenerate pair was not folded"
    assert not any(m.pair_supported for m in paired)
    # each MOMENT_PAIR_DEGENERATE names its class, and that class's rows carry
    # the pair (#742): the pair's ``where`` is two paths every class shares
    # (moved here from test_pair_diagnostic_class in WP-1930)
    # A class index is unique only within one k.  The pairs span every k
    # tried and ``s.trials`` holds the chosen k's classes, so a pair is keyed
    # by its whole label and looked up only when it is the chosen k's (under
    # the LM driver a second k reaches a pair, WP-1938).
    pairs = [d for d in s.diagnostics if d.code == "MOMENT_PAIR_DEGENERATE"]
    assert pairs, [d.message for d in s.diagnostics]
    chosen = ("" if s.k is None or all(c == "0" for c in s.k)
              else " (k = (" + ", ".join(s.k) + "))")
    labels, classes = set(), set()
    for d in pairs:
        assert d.message.startswith("class "), d.message
        label = d.message.split(":")[0]
        labels.add(label)
        index = int(label.split()[1])
        if label != f"class {index}{chosen}":
            continue
        trial = next(t for t in s.trials if t.class_index == index)
        assert any(r.paired_with for r in trial.moments), (index, d.message)
        classes.add(index)
    assert classes, "no pair names a class of the chosen k"
    assert len(labels) == len(pairs)
    unpaired = {t.class_index for t in s.trials
                if not any(r.paired_with for r in t.moments)}
    assert not classes & unpaired
