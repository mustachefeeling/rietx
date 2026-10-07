"""``determine_extinction_symbol(refine_cell=True)``: the opt-in of #726 (the default is unchanged).

SRM 676a corundum from the IUCr round robin (public, ``tests/data/qarr``), at the
certified cell and at the cell scaled by 1.0012: the held-cell screen refutes the
true class at the scaled one; refining the cell inside the shared fit does not.
"""

from __future__ import annotations

import pytest

from rietx.indexing.extinction import determine_extinction_symbol

SCALE = 1.0012


def _scaled(cell, factor):
    return tuple(v * factor for v in cell[:3]) + tuple(cell[3:])


@pytest.fixture(scope="module")
def inputs():
    from tests.test_extinction_symbol import (
        CORUNDUM_CELL,
        CORUNDUM_RANGE,
        _candidate,
        corundum_inputs,
    )

    data, _cand, instrument = corundum_inputs.__wrapped__()
    return (data, instrument, CORUNDUM_RANGE,
            _candidate(_scaled(CORUNDUM_CELL, SCALE), "trigonal", "R"),
            CORUNDUM_CELL)


def test_a_cell_off_by_a_tenth_of_a_percent_refutes_the_true_class_unless_refined(inputs):
    data, instrument, limits, candidate, certified = inputs

    held = determine_extinction_symbol(data, candidate, instrument,
                                       two_theta_limits=limits)
    best = held.best_or_none()
    assert best is None or "R -3 c:H" not in best.space_groups, (
        "the held cell no longer refutes the true class at this offset: the "
        "default behaviour #726 describes has changed")
    assert held.cell == pytest.approx(candidate.cell)

    refined = determine_extinction_symbol(data, candidate, instrument,
                                          two_theta_limits=limits,
                                          refine_cell=True)
    best = refined.best_or_none()
    assert best is not None, [(c.symbol, c.refuted_reason)
                              for c in refined.candidates]
    assert best.symbol == "R - c -"
    assert best.space_groups == ["R 3 c:H", "R -3 c:H"]
    # the screen says which cell it used, and it moved back toward the certified one
    assert refined.cell != pytest.approx(candidate.cell)
    assert abs(refined.cell[0] / certified[0] - 1) < abs(candidate.cell[0] / certified[0] - 1)
