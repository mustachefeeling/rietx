"""``solve_magnetic(tie_to_parent=True)``: the opt-in of #724 (the default is unchanged).

A k ≠ 0 child is a supercell of the parent, so its trial fit frees more nuclear
parameters than the parent had; ``tie_to_parent`` holds the child cell at the
parent-derived cell and ties the child Biso of one parent atom to one another.
Synthetic tetragonal P 4/m m m parent, k = (0, 0, 1/2), the generator of
``test_magnetic_k_trials``; no archive data.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx


def _fixture():
    from tests.test_magnetic_k_trials import true_k_and_data
    return true_k_and_data.__wrapped__()


def test_a_statement_ties_the_child_biso_of_one_parent_atom():
    from rietx.crystallography.magnetic.isotropy import candidates
    from rietx.crystallography.magnetic.supercell import magnetic_supercell
    from rietx.strategy.magnetic import _parent_site_ties
    from tests.test_magnetic_k_trials import tetragonal

    truth = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]
    statement = magnetic_supercell(tetragonal(), truth, magnetic_species=["Mn1"],
                                   ion={"Mn1": "Mn3+"}, magnitude=3.0)
    ties = _parent_site_ties(statement)
    by_parent: dict[int, list[int]] = {}
    for i, (parent_atom, _c) in enumerate(statement.site_map):
        by_parent.setdefault(parent_atom, []).append(i)
    assert len(ties) == sum(len(v) - 1 for v in by_parent.values())
    assert len(ties) >= 1
    for target, source, scale, offset in ties:
        assert target.endswith(".biso") and source.endswith(".biso")
        assert (scale, offset) == (1.0, 0.0) and target != source


def test_the_cell_leaves_every_stage_and_nothing_else_does():
    from rietx.strategy.magnetic import _without_cell

    plan = rx.RefinementPlan(stages=[
        rx.Stage("moment", ["phases.*.atoms.*.moment.dof*", "phases.*.scale"]),
        rx.Stage("all", ["phases.*.scale", "phases.*.cell.*",
                         "phases.*.atoms.*.biso"], max_iter=7)])
    held = _without_cell(plan)
    assert [s.turn_on for s in held.stages] == [
        ["phases.*.atoms.*.moment.dof*", "phases.*.scale"],
        ["phases.*.scale", "phases.*.atoms.*.biso"]]
    assert held.stages[1].max_iter == 7 and held.stages[1].name == "all"


def test_a_tied_trial_holds_the_child_cell_and_the_per_parent_biso():
    ref, data, _truth = _fixture()
    parent = ref.fitted_structure.phases[0]
    a, c = parent.cell.a.value, parent.cell.c.value

    kw = dict(sites=["Mn1"], ion="Mn3+", k=(0, 0, "1/2"))
    free = rx.solve_magnetic(ref, data, **kw)
    tied = rx.solve_magnetic(ref, data, tie_to_parent=True, **kw)
    assert free.verdict == "solved" and tied.verdict == "solved", (
        free.reason, tied.reason)

    # the default is the old behaviour: no row, the child cell refined
    assert not any(d.code == "SOLVE_B_TIED_PER_PARENT_SITE"
                   for d in free.diagnostics)
    free_cell = free.best._structure.phases[0].cell
    assert free_cell.c.value != pytest.approx(2 * c, abs=1e-12)

    assert any(d.code == "SOLVE_B_TIED_PER_PARENT_SITE" for d in tied.diagnostics)
    phase = tied.best._structure.phases[0]
    assert phase.cell.a.value == pytest.approx(a, abs=1e-12)
    assert phase.cell.c.value == pytest.approx(2 * c, abs=1e-12)
    mn = [x.biso.value for x in phase.atoms if x.species == "Mn"]
    assert len(mn) >= 2 and np.ptp(mn) < 1e-12
    # fewer free parameters, and the nuclear reference was held the same way
    assert tied.best.n_free_parameters < free.best.n_free_parameters
