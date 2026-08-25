"""The parameter surface: rows as data, the two edit verbs, plan metadata.

WP-1004.  Everything here is plain API — the GUI is a consumer, not a premise.
"""

from __future__ import annotations

import dataclasses

import pytest

import rietx as rx
from rietx.params.vector import Entry
from rietx.schemas.params import ParameterRow, TieSpec
from rietx.strategy.staged import PLAN_INFO, PLAN_PRESETS
from tests.test_refine_synthetic import perturbed_models, synthesize

SHORT = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=20),
    rx.Stage("cell", ["phases.*.cell.*"], max_iter=20),
])

#: Fields ``ParameterRow`` adds to ``Entry``'s, declared here so the anti-drift
#: test asserts the addition rather than silently tolerating any difference.
#:
#: All three are held-reasons an ``Entry`` cannot carry, for the same reason:
#: they are not facts about the parameter.  ``esd`` comes from the last fit,
#: ``mode_fixed`` from the intensity mode, and ``needs_held_cell`` from whether
#: this histogram's *cell* is currently free — the only one that changes with
#: another parameter's state, which is why it cannot be an ``Entry.locked``
#: flag and has to be recomputed each time the surface is read.
DELIBERATE_EXTRAS = {"esd", "mode_fixed", "needs_held_cell"}


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture
def ref():
    structure, ins = perturbed_models()
    return rx.Refinement(structure, ins)


# ------------------------------------------------------------------ the schema
def test_parameter_row_mirrors_entry_plus_declared_extras():
    entry_fields = {f.name for f in dataclasses.fields(Entry)}
    row_fields = set(ParameterRow.model_fields)
    assert row_fields - entry_fields == DELIBERATE_EXTRAS
    assert entry_fields - row_fields == set(), "an Entry field is not exposed"


def test_a_wavelength_is_held_by_the_cell_and_says_so():
    """The fourth held-reason, and the only dynamic one.

    ``refinable`` promises "``set_vary`` could free this row".  With the cell
    free, ``set_vary`` skips a wavelength — so without this flag the promise
    would be false while ``held_because`` said nothing, which is exactly the
    defaulted-``False`` shape WP-1076 removes.  Both directions asserted: a
    held-because that never clears is the old hard lock in disguise.
    """
    import rietx as rx

    WL = "instrument.source.lines.0.wavelength"
    ins = rx.Instrument.debye_scherrer(wavelength=1.5406)

    def structure(cell_vary):
        st = rx.Structure(phases=[rx.Phase(
            name="LaB6", space_group="P m -3 m",
            cell=rx.Cell.cubic(4.15689, vary=cell_vary),
            atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                           y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))])])
        return st

    free = rx.Refinement(structure(True), ins, history=False)
    row = next(r for r in free.parameters() if r.path == WL)
    assert row.needs_held_cell and not row.refinable
    assert "cell held" in row.held_because
    assert not row.locked, "a dynamic reason must not masquerade as structural"

    held = rx.Refinement(structure(False), ins, history=False)
    row = next(r for r in held.parameters() if r.path == WL)
    assert not row.needs_held_cell and row.refinable and row.held_because == ""


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
    replayed = rx.Refinement(structure, ins)
    replayed.fit(pattern, plan=SHORT)
    for call in calls:
        eval(call, {"ref": replayed, "rx": rx, "data": pattern})  # noqa: S307
    assert replayed.structure.phases[0].cell.a.value == pytest.approx(
        ref.structure.phases[0].cell.a.value)
    assert replayed.instrument.profile.w.value == 0.02
    assert {r.path: r for r in replayed.parameters()}["instrument.profile.w"].vary


def test_set_vary_without_history_still_edits():
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    assert ref.set_vary(["phases.*.cell.*"]) == ["phases.0.cell.a"]
    ref.set_values({"phases.0.cell.a": 4.2})
    assert ref.history is None
    assert ref.structure.phases[0].cell.a.value == 4.2


# ------------------------------------------------- user constraints (WP-1070)
BISOS = ["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"]


def test_tie_equal_makes_one_parameter_of_a_group(ref):
    """The verb §7 asks for: the first match carries the freedom, rest follow."""
    assert ref.tie_equal(BISOS) == ["phases.0.atoms.1.biso"]
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.1.biso"].tie.sources == ["phases.0.atoms.0.biso"]
    assert not rows["phases.0.atoms.1.biso"].refinable
    assert rows["phases.0.atoms.0.biso"].refinable, "the source keeps the freedom"
    # the dependent takes the source's value at once, so nothing is left
    # describing the pre-tie state
    ref.set_values({"phases.0.atoms.0.biso": 0.71})
    assert ref.structure.phases[0].atoms[1].biso.value == 0.71
    # ...and the constraint is a *reduction*: one fewer column in θ
    assert ref.set_vary(["phases.0.atoms.*.biso"]) == ["phases.0.atoms.0.biso"]


def test_tie_is_the_general_affine_form(ref):
    """Complementary occupancies: occ₁ = 1 − occ₀, the other case §7 names."""
    ref.set_values({"phases.0.atoms.0.occ": 0.6})
    ref.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ", scale=-1.0, offset=1.0)
    assert ref.structure.phases[0].atoms[1].occ.value == pytest.approx(0.4)
    ref.set_values({"phases.0.atoms.0.occ": 0.75})
    assert ref.structure.phases[0].atoms[1].occ.value == pytest.approx(0.25)
    row = {r.path: r for r in ref.parameters()}["phases.0.atoms.1.occ"]
    assert row.held_because == "tied: = 1 + -1·phases.0.atoms.0.occ"


def test_a_tied_row_says_whose_tie_holds_it(ref):
    """``user`` is what separates a row a caller may release from one it may not.

    Both populations hold a row the same way and read the same in
    ``held_because``, so without the flag a client has to *try* an untie to
    find out — and the answer differs for two rows that look identical.
    """
    ref.tie_equal(BISOS)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.1.biso"].tie.user
    assert not rows["phases.0.cell.b"].tie.user, "a cell tie is the space group's"


def test_a_tie_refuses_and_names_the_holder(ref):
    with pytest.raises(ValueError, match="unknown parameter path"):
        ref.tie("phases.0.atoms.9.biso", "phases.0.atoms.0.biso")
    with pytest.raises(ValueError, match="structurally fixed"):
        ref.tie("phases.0.cell.alpha", "phases.0.cell.a")
    with pytest.raises(ValueError, match="symmetry outranks a user tie"):
        ref.tie("phases.0.cell.b", "phases.0.cell.a")
    with pytest.raises(ValueError, match="carries no freedom of its own"):
        ref.tie("phases.0.atoms.0.biso", "phases.0.cell.b")
    with pytest.raises(ValueError, match="cannot be tied to itself"):
        ref.tie("phases.0.atoms.0.biso", "phases.0.atoms.0.biso")
    with pytest.raises(ValueError, match="that is set_values"):
        ref.tie(*BISOS, scale=0.0)
    with pytest.raises(ValueError, match="outside its bounds"):
        ref.tie(*BISOS, scale=-1.0)
    # a refused call changes nothing — not the table, not the models
    assert {r.path: r for r in ref.parameters()}["phases.0.atoms.0.biso"].refinable
    assert ref.history is None or len(ref.history) == 0


def test_a_tie_refuses_a_chain_naming_what_to_tie_to_instead(ref):
    ref.tie_equal(BISOS)
    with pytest.raises(ValueError, match=r"follows 'phases\.0\.atoms\.0\.biso' "
                                         r"\(a user tie\)"):
        ref.tie("phases.0.atoms.0.occ", "phases.0.atoms.1.biso")
    with pytest.raises(ValueError, match="untie it first"):
        ref.tie("phases.0.atoms.1.biso", "phases.0.atoms.0.occ")


def test_tie_equal_is_all_or_nothing(ref):
    """A glob that sweeps in a row it cannot tie is a glob to narrow.

    Silently omitting it would leave a constraint the caller asked for and did
    not get — indistinguishable, from the outside, from one that landed.
    """
    with pytest.raises(ValueError, match="symmetry outranks a user tie"):
        ref.tie_equal("phases.0.cell.*")
    assert {r.path: r.tie for r in ref.parameters()}["phases.0.cell.c"].user is False
    with pytest.raises(ValueError, match="an equality group needs at least two"):
        ref.tie_equal("phases.0.atoms.0.biso")


def test_untie_releases_only_this_refinements_ties(ref):
    ref.tie_equal(BISOS)
    assert ref.untie("phases.0.atoms.*.biso") == ["phases.0.atoms.1.biso"]
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.1.biso"].tie is None
    # released, not freed: that decision belongs to set_vary
    assert not rows["phases.0.atoms.1.biso"].vary
    assert rows["phases.0.atoms.1.biso"].refinable
    # a glob sweeping symmetry ties leaves them alone...
    assert ref.untie("phases.0.cell.*") == []
    # ...but naming one is a request that has to be refused, not a no-op
    with pytest.raises(ValueError, match="tied by symmetry"):
        ref.untie("phases.0.cell.b")
    with pytest.raises(ValueError, match="is not tied"):
        ref.untie("phases.0.atoms.0.biso")


def test_a_tie_refuses_a_mode_fixed_target(ref, pattern):
    ref.fit(pattern, mode="lebail", plan="profile_only")
    with pytest.raises(ValueError, match="force-fixed by the 'lebail'"):
        ref.tie_equal(BISOS)


def test_the_esd_of_a_tied_row_is_its_sources(ref, pattern):
    """Identical to what a cell tie already reports, and by the same route.

    ``stderr_physical`` propagates through C, so an identity tie reports the
    source esd exactly and an affine one scales it.  Pinned against the derived
    tie beside it so the two can never drift into separate policies.
    """
    ref.tie("phases.0.atoms.1.biso", "phases.0.atoms.0.biso", scale=2.0)
    ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("biso", ["phases.*.scale", "phases.*.cell.*",
                          "phases.*.atoms.*.biso"], max_iter=20)]))
    rows = {r.path: r for r in ref.parameters()}
    source = rows["phases.0.atoms.0.biso"].esd
    assert source is not None and source > 0
    assert rows["phases.0.atoms.1.biso"].esd == pytest.approx(2.0 * source)
    # the derived tie beside it, on the same fit, with the same rule
    assert rows["phases.0.cell.b"].esd == pytest.approx(rows["phases.0.cell.a"].esd)


def test_tie_verbs_record_a_set_tie_node(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    n_before = len(ref.history)
    ref.tie_equal(BISOS)
    ref.untie("phases.0.atoms.1.biso")
    kinds = [ref.history[i].action.kind for i in ref.history.order[n_before:]]
    assert kinds == ["set_tie", "set_tie"]
    declared, released = (ref.history[i] for i in ref.history.order[n_before:])
    assert declared.action.ties["phases.0.atoms.1.biso"].sources == [BISOS[0]]
    assert released.action.untied == ["phases.0.atoms.1.biso"]
    # the *state* carries the register, which is what a checkout restores
    assert declared.state.ties["phases.0.atoms.1.biso"].const == 0.0
    assert released.state.ties == {}


def test_a_tie_node_renders_an_api_call_that_runs(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    ref.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ", scale=-1.0, offset=1.0)
    ref.untie("phases.0.atoms.1.occ")
    calls = [ref.history[i].action.api_call() for i in ref.history.order[-2:]]
    assert calls == [
        "ref.tie('phases.0.atoms.1.occ', 'phases.0.atoms.0.occ', scale=-1.0, "
        "offset=1.0)",
        "ref.untie(['phases.0.atoms.1.occ'])"]
    structure, ins = perturbed_models()
    replayed = rx.Refinement(structure, ins)
    for call in calls:
        eval(call, {"ref": replayed, "rx": rx})  # noqa: S307
    assert {r.path: r for r in replayed.parameters()}["phases.0.atoms.1.occ"].tie is None


def test_a_checkout_restores_the_parameter_count_the_node_had(ref, pattern):
    """A tie is not a property of the models, so only the node can carry it.

    ``ParameterTable`` rederives the symmetry ties from the space group on
    every build and knows nothing about a user's — a checkout that restored
    only structure and instrument would come back with the constraint silently
    gone, and the free count one higher than the node it claims to be at.
    """
    ref.fit(pattern, plan=SHORT)
    before = ref.history.head
    ref.tie_equal(BISOS)
    ref.set_vary(["phases.0.atoms.*.biso"])
    tied_node = ref.history.head
    assert "phases.0.atoms.1.biso" not in ref.history[tied_node].state.free_paths

    ref.checkout(before)
    assert ref._ties == {}
    assert {r.path: r for r in ref.parameters()}["phases.0.atoms.1.biso"].tie is None

    ref.checkout(tied_node)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.1.biso"].tie.user
    assert rows["phases.0.atoms.0.biso"].vary and not rows["phases.0.atoms.1.biso"].vary


def test_ties_survive_a_history_file_round_trip(ref, pattern, tmp_path):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=tmp_path / "h.jsonl")
    ref.fit(pattern, plan=SHORT)
    ref.tie_equal(BISOS)
    reopened = rx.Refinement.from_node(
        rx.RefinementTree.load(tmp_path / "h.jsonl"), "head")
    row = {r.path: r for r in reopened.parameters()}["phases.0.atoms.1.biso"]
    assert row.tie is not None and row.tie.user


def test_symmetry_outranks_a_user_tie_when_an_edit_creates_one(ref):
    """The one place the rule can actually be violated (``_apply_ties``).

    The verbs refuse a target that is already tied, but a tie declared while a
    path was free stays declared through an ``edit`` that makes the same path
    symmetry-tied.  Overwriting would break the symmetry the derived tie exists
    to enforce, so the user's is dropped — loudly, and at the edit that ended
    it, since a constraint that stopped applying is exactly what a caller must
    not have to guess at.
    """
    structure, ins = perturbed_models()
    structure.phases[0].space_group = "P 1"  # nothing tied, nothing locked
    ref = rx.Refinement(structure, ins, history=False)
    ref.tie("phases.0.cell.b", "phases.0.cell.a")
    assert {r.path: r for r in ref.parameters()}["phases.0.cell.b"].tie.user

    cubic = ref.structure.model_copy(deep=True)
    cubic.phases[0].space_group = "P m -3 m"
    with pytest.warns(UserWarning, match="now tied by symmetry"):
        ref.edit(structure=cubic)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.cell.b"].tie is not None
    assert not rows["phases.0.cell.b"].tie.user, "the space group's tie, not the user's"
    # said once, at the edit: the register is reconciled with the model it left
    assert ref._ties == {}
    # and the refusals read the table too, so the message names the real holder
    with pytest.raises(ValueError, match="symmetry outranks a user tie"):
        ref.tie("phases.0.cell.b", "phases.0.cell.a")
    with pytest.raises(ValueError, match="tied by symmetry"):
        ref.untie("phases.0.cell.b")


def test_tie_without_history_still_edits():
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    assert ref.tie_equal(BISOS) == ["phases.0.atoms.1.biso"]
    assert ref.history is None
    assert ref.structure.phases[0].atoms[1].biso.value == pytest.approx(
        ref.structure.phases[0].atoms[0].biso.value)


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
