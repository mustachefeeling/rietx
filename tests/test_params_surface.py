"""The parameter surface: rows as data, the two edit verbs, plan metadata.

WP-1004.  Everything here is plain API — the GUI is a consumer, not a premise.
"""

from __future__ import annotations

import dataclasses

import pytest

import rietx as pr
from rietx.params.vector import Entry
from rietx.schemas.params import ParameterRow, TieSpec
from rietx.strategy.staged import PLAN_INFO, PLAN_PRESETS
from tests.test_refine_synthetic import perturbed_models, synthesize

SHORT = pr.RefinementPlan(stages=[
    pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=20),
    pr.Stage("cell", ["phases.*.cell.*"], max_iter=20),
])

#: Fields ``ParameterRow`` adds to ``Entry``'s, declared here so the anti-drift
#: test asserts the addition rather than silently tolerating any difference.
DELIBERATE_EXTRAS = {"esd", "mode_fixed"}


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture
def ref():
    structure, ins = perturbed_models()
    return pr.Refinement(structure, ins)


# ------------------------------------------------------------------ the schema
def test_parameter_row_mirrors_entry_plus_declared_extras():
    entry_fields = {f.name for f in dataclasses.fields(Entry)}
    row_fields = set(ParameterRow.model_fields)
    assert row_fields - entry_fields == DELIBERATE_EXTRAS
    assert entry_fields - row_fields == set(), "an Entry field is not exposed"


def test_tie_spec_describes_its_right_hand_side():
    tie = TieSpec(terms=[("phases.0.atoms.1.dof.0", 1.0)], const=0.1993)
    assert tie.sources == ["phases.0.atoms.1.dof.0"]
    assert tie.describe() == "0.1993 + 1·phases.0.atoms.1.dof.0"
    assert TieSpec(terms=[], const=0.0).describe() == "0"


# ------------------------------------------------------------------- listing
def test_parameters_lists_the_whole_table(ref):
    rows = {r.path: r for r in ref.parameters()}
    # free, tied, locked and merely-fixed all present — a caller deciding what
    # to free next has to see the parts it may not touch
    assert rows["phases.0.cell.a"].refinable
    assert rows["phases.0.cell.b"].tie is not None
    assert not rows["phases.0.cell.b"].refinable
    assert rows["phases.0.cell.alpha"].locked
    assert rows["phases.0.extinction"].refinable and not rows["phases.0.extinction"].vary
    # bounds and transforms come through, so a client can build an editor
    assert rows["phases.0.scale"].transform == "softplus"
    assert rows["phases.0.scale"].lo == 0.0


def test_parameters_reports_why_a_row_is_held(ref):
    rows = {r.path: r for r in ref.parameters()}
    assert "symmetry" in rows["phases.0.cell.alpha"].held_because
    assert rows["phases.0.cell.b"].held_because == "tied: = 1·phases.0.cell.a"
    assert rows["phases.0.cell.a"].held_because == ""


def test_parameters_merges_the_last_fits_esds(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.cell.a"].esd is not None and rows["phases.0.cell.a"].esd > 0
    # a tied dependent reports the propagated esd, not None
    assert rows["phases.0.cell.b"].esd == pytest.approx(rows["phases.0.cell.a"].esd)
    # something never freed has no esd rather than a stale one
    assert rows["phases.0.extinction"].esd is None


def test_parameters_reflects_the_free_set_after_a_stage(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.cell.a"].vary and rows["phases.0.scale"].vary
    assert not rows["instrument.profile.w"].vary


def test_lebail_mode_marks_the_dummy_atom_not_editable(ref, pattern):
    """A Le Bail phase must carry an atom to exist; it must not look editable.

    ``Phase`` refuses an empty atom list, so a Le Bail-only phase (indexing
    constructs these routinely) carries a dummy atom that contributes nothing —
    ``_run_stage`` force-fixes every ``.atoms.`` path in that mode.  A row shown
    as editable would invite refining something the mode discards.
    """
    ref.fit(pattern, mode="lebail", plan="profile_only")
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.0.biso"].mode_fixed
    assert not rows["phases.0.atoms.0.biso"].refinable
    assert "mode" in rows["phases.0.atoms.0.biso"].held_because
    assert rows["phases.0.scale"].mode_fixed  # degenerate with the intensities
    # ...and it is not *locked*: switching back to rietveld frees it again
    assert not rows["phases.0.scale"].locked
    assert rows["phases.0.cell.a"].refinable


# --------------------------------------------------------------------- verbs
def test_set_vary_frees_by_glob_and_refuses_locked(ref):
    hits = ref.set_vary(["phases.*.cell.*"])
    assert hits == ["phases.0.cell.a"]  # b, c tied; the angles locked
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.cell.a"].vary
    assert not rows["phases.0.cell.alpha"].vary
    # a string is accepted as a single glob (the GUI passes one row's path)
    assert ref.set_vary("phases.0.extinction") == ["phases.0.extinction"]
    assert ref.set_vary(["phases.*.cell.*"], False) == ["phases.0.cell.a"]


def test_set_values_writes_through_to_the_models(ref):
    ref.set_values({"phases.0.cell.a": 4.2, "phases.0.extinction": 1e-4})
    assert ref.structure.phases[0].cell.a.value == 4.2
    # the tied dependents follow their source — otherwise the cubic symmetry the
    # tie exists to enforce would be silently broken
    assert ref.structure.phases[0].cell.b.value == 4.2
    assert ref.structure.phases[0].cell.c.value == 4.2
    assert {r.path: r.value for r in ref.parameters()}["phases.0.cell.b"] == 4.2


def test_set_values_refuses_with_an_actionable_message(ref):
    with pytest.raises(ValueError, match="unknown parameter path"):
        ref.set_values({"phases.0.cell.aa": 4.2})
    with pytest.raises(ValueError, match="structurally fixed"):
        ref.set_values({"phases.0.cell.alpha": 91.0})
    with pytest.raises(ValueError, match=r"follows 'phases\.0\.cell\.a'"):
        ref.set_values({"phases.0.cell.b": 4.2})
    with pytest.raises(ValueError, match="outside its bounds"):
        ref.set_values({"phases.0.scale": -1.0})
    # a refused call changes nothing
    assert ref.structure.phases[0].cell.alpha.value == 90.0


def test_set_values_invalidates_the_stale_result(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    assert ref.result_ is not None
    ref.set_values({"phases.0.cell.a": 4.2})
    assert ref.result_ is None  # the fitted curve described the old values


# ------------------------------------------------------- verbs ↔ history nodes
def test_verbs_record_the_reserved_node_kinds(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    n_before = len(ref.history)
    ref.set_vary(["instrument.profile.w"])
    ref.set_values({"instrument.profile.w": 0.02})
    kinds = [ref.history[i].action.kind for i in ref.history.order[n_before:]]
    assert kinds == ["set_vary", "set_value"]
    # the free set and the value are in the recorded state, so a checkout
    # restores an edit exactly like it restores a stage
    node = ref.history[ref.history.order[-1]]
    assert "instrument.profile.w" in node.state.free_paths
    assert node.state.instrument.profile.w.value == 0.02


def test_recorded_api_call_evaluates_back_to_the_same_call(ref, pattern):
    """A history log doubles as a session script, so the rendering must run.

    The plural/singular mismatch this pins was real: ``api_call`` rendered
    ``ref.set_values(...)`` for the singular ``"set_value"`` node kind, and no
    such method existed until WP-1004 (the verb is plural — a GUI edits a table,
    not a cell — and the NodeKind literal stays as persisted).
    """
    ref.fit(pattern, plan=SHORT)
    ref.set_vary(["instrument.profile.w"])
    ref.set_values({"instrument.profile.w": 0.02})
    ids = ref.history.order[-2:]
    calls = [ref.history[i].action.api_call() for i in ids]
    assert calls[0] == "ref.set_vary(['instrument.profile.w'], True)"
    assert calls[1] == "ref.set_values({'instrument.profile.w': 0.02})"

    # eval the rendered strings against a fresh refinement: same state out
    structure, ins = perturbed_models()
    replayed = pr.Refinement(structure, ins)
    replayed.fit(pattern, plan=SHORT)
    for call in calls:
        eval(call, {"ref": replayed, "pr": pr, "data": pattern})  # noqa: S307
    assert replayed.structure.phases[0].cell.a.value == pytest.approx(
        ref.structure.phases[0].cell.a.value)
    assert replayed.instrument.profile.w.value == 0.02
    assert {r.path: r for r in replayed.parameters()}["instrument.profile.w"].vary


def test_set_vary_without_history_still_edits():
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins, history=False)
    assert ref.set_vary(["phases.*.cell.*"]) == ["phases.0.cell.a"]
    ref.set_values({"phases.0.cell.a": 4.2})
    assert ref.history is None
    assert ref.structure.phases[0].cell.a.value == 4.2


# ----------------------------------------------------------------- PLAN_INFO
def test_plan_info_covers_every_preset_and_no_more():
    assert set(PLAN_INFO) == set(PLAN_PRESETS)


def test_plan_info_rows_are_filled_in():
    for name, info in PLAN_INFO.items():
        assert info.title and info.description and info.when_to_use, name
        assert info.modes, name
        assert set(info.modes) <= {"rietveld", "lebail", "pawley"}, name


def test_plan_info_modes_match_what_the_plan_can_free():
    """A plan claiming ``rietveld`` only must not be the one Le Bail needs.

    Weak by design — the strong statement is the presets' own turn-on lists —
    but it catches the copy-paste that would send a Le Bail caller to a plan
    that frees structural parameters the mode discards.
    """
    for name, info in PLAN_INFO.items():
        globs = {g for stage in PLAN_PRESETS[name]().stages for g in stage.turn_on}
        structural = any(".atoms." in g for g in globs)
        if structural:
            assert info.modes == ("rietveld",), name
