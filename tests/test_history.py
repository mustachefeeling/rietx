"""Refinement history DAG: recording, restore fidelity, branching, light mode."""

from __future__ import annotations

import copy
import math
from pathlib import Path

import pytest

import rietx as pr
from rietx.params.vector import ParameterTable
from rietx.refine import replay
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_refine_synthetic import perturbed_models, synthesize

OUT = Path(__file__).parent / "output"

# A short plan: enough stages to branch from, fast enough for a unit test.
SHORT = pr.RefinementPlan(stages=[
    pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=40),
    pr.Stage("cell", ["phases.*.cell.*"], max_iter=40),
])


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture(scope="module")
def fitted(pattern):
    """A completed Rietveld fit with history, reused across read-only tests."""
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    result = ref.fit(pattern, plan=SHORT)
    return ref, result


# ---------------------------------------------------------------- recording
def test_records_a_node_per_stage(fitted):
    ref, result = fitted
    tree = ref.history
    # root + one node per stage
    assert len(tree) == 1 + len(SHORT.stages)
    assert tree.root.action.kind == "root"
    assert [n.action.name for n in tree.nodes.values() if n.action.kind == "stage"] \
        == ["scale_bkg", "cell"]
    assert result.node_id == tree.order[-1]
    assert result.tree_id == tree.header.tree_id
    # every fitted node carries its own agreement indices
    for node in tree.nodes.values():
        if node.action.kind == "stage":
            assert node.metrics.statistics is not None
            assert node.metrics.status in {"converged", "max_iter", "diverged"}


def test_action_records_the_equivalent_api_call(fitted):
    ref, _ = fitted
    node = ref.history[ref.history.order[-1]]
    call = node.action.api_call()
    assert "run_stage" in call and "cell" in call


# ---------------------------------------------------------- restore fidelity
def test_checkout_restores_every_parameter_exactly(pattern):
    """The load-bearing invariant: a checkpoint loses no state.

    Checked on the parameter values themselves, bit for bit — an Rwp
    comparison would be a lossy proxy for this.
    """
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(pattern, plan=SHORT)
    tree = ref.history

    for node in tree.nodes.values():
        ref.checkout(node.id)
        table = ParameterTable(ref.fitted_structure, ref.fitted_instrument)
        recorded = ParameterTable(node.state.structure, node.state.instrument)
        assert {e.path: e.value for e in table.entries} \
            == {e.path: e.value for e in recorded.entries}
        # the free set is not stored on the models, so it rides alongside
        table.set_vary(["*"], False)
        for path in node.state.free_paths:
            table.set_vary([path], True)
        assert table.free_paths == node.state.free_paths


def test_replay_agrees_with_recorded_metrics(fitted, pattern):
    """Replay recompiles at the node's own values, so it can differ slightly
    from the as-optimised metrics (frozen at the values the stage started
    from).  The tolerance is wide enough for that refreeze and far too tight
    to survive any actual loss of state."""
    ref, _ = fitted
    tree = ref.history
    for node in tree.nodes.values():
        if node.metrics.statistics is None:
            continue
        again = replay(tree, node.id, pattern)
        assert again.statistics.rwp == pytest.approx(
            node.metrics.statistics.rwp, rel=1e-2)


def test_replay_is_deterministic(fitted, pattern):
    ref, _ = fitted
    a = replay(ref.history, ref.history.order[-1], pattern)
    b = replay(ref.history, ref.history.order[-1], pattern)
    assert a.statistics.rwp == b.statistics.rwp
    assert a.y_calc == b.y_calc


def test_a_node_whose_stage_moved_nothing_discrete_replays_exactly(fitted, pattern):
    """`scale_bkg` refines only scale and background, neither of which enters
    the frozen reflection list or windows, so its refreeze is a no-op."""
    ref, _ = fitted
    node = [n for n in ref.history.nodes.values() if n.action.name == "scale_bkg"][0]
    again = replay(ref.history, node.id, pattern)
    assert again.statistics.rwp == node.metrics.statistics.rwp


# --------------------------------------------------------------- Le Bail
def test_lebail_restore_keeps_extracted_intensities(pattern):
    """Le Bail intensities live outside θ and are path-dependent, so a node
    that loses them cannot reproduce itself."""
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(pattern, mode="lebail", plan=SHORT)
    tree = ref.history

    node = tree[tree.order[-1]]
    assert node.state.mode == "lebail"
    assert node.state.reflections, "no per-hkl state captured"
    assert len(node.state.reflections[0].intensity) == len(node.state.reflections[0].hkl)

    good = replay(tree, node.id, pattern)

    # Prove the stored intensities are load-bearing: strip them and the same
    # state fits far worse, because compile_model re-seeds them flat.
    stripped = copy.deepcopy(tree)
    stripped.nodes[node.id].state.reflections = []
    bad = replay(stripped, node.id, pattern)
    assert bad.statistics.rwp > good.statistics.rwp * 1.05, (
        f"clearing the hkl→I map barely changed Rwp "
        f"({good.statistics.rwp:.4f} → {bad.statistics.rwp:.4f}); "
        "the Le Bail restore path is not doing anything")


def test_replay_does_not_mutate_le_bail_state(pattern):
    """``lebail_update`` mutates intensities in place; merely inspecting a
    checkpoint must never call it."""
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(pattern, mode="lebail", plan=SHORT)
    tree = ref.history
    node = tree[tree.head]

    before = list(node.state.reflections[0].intensity)
    first = replay(tree, node.id, pattern)
    second = replay(tree, node.id, pattern)
    after = list(node.state.reflections[0].intensity)

    assert before == after
    assert first.statistics.rwp == second.statistics.rwp


# --------------------------------------------------------------- branching
def test_branching_creates_independent_leaves(pattern):
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(pattern, plan=SHORT)
    tree = ref.history

    mid = [n for n in tree.nodes.values() if n.action.name == "scale_bkg"][0]
    frozen = mid.model_dump_json()

    ref.checkout(mid.id)
    alt = ref.run_stage(pattern, pr.Stage("profile_w", ["instrument.profile.w"],
                                          max_iter=40))

    leaves = tree.leaves()
    assert len(leaves) == 2, [n.id for n in leaves]
    assert {n.action.name for n in leaves} == {"cell", "profile_w"}
    assert tree.children(mid.id).__len__() == 2
    # recording a sibling must not disturb the node it branched from
    assert mid.model_dump_json() == frozen
    assert alt.statistics.rwp > 0


def test_branch_gives_a_second_working_tree(pattern):
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(pattern, plan=SHORT)
    tree = ref.history
    mid = [n for n in tree.nodes.values() if n.action.name == "scale_bkg"][0]

    other = ref.branch(mid.id)
    assert other.history is tree
    other.run_stage(pattern, pr.Stage("w", ["instrument.profile.w"], max_iter=30))
    assert len(tree.leaves()) == 2


def test_from_node_reopens_a_checkpoint(pattern):
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(pattern, plan=SHORT)
    tree = ref.history
    reopened = pr.Refinement.from_node(tree, tree.root.id)
    assert reopened.history is tree
    assert reopened.fitted_structure.phases[0].cell.a.value == pytest.approx(
        tree.root.state.structure.phases[0].cell.a.value)


# -------------------------------------------------------------- light mode
def test_history_disabled_is_inert_and_identical(pattern):
    structure, ins = perturbed_models()
    on = pr.Refinement(structure, ins, history=True).fit(pattern, plan=SHORT)
    off_ref = pr.Refinement(structure, ins, history=False)
    off = off_ref.fit(pattern, plan=SHORT)

    assert off_ref.history is None
    assert off.node_id is None and off.tree_id is None
    # the light path must not perturb the numbers in any way
    assert off.statistics.rwp == on.statistics.rwp
    assert off.statistics.chi2 == on.statistics.chi2

    with pytest.raises(RuntimeError, match="no history"):
        off_ref.checkout("n0000")


def test_refine_function_defaults_to_no_history(pattern):
    structure, ins = perturbed_models()
    result = pr.refine(pattern, structure, ins, plan=SHORT)
    assert result.node_id is None


def test_edit_refuses_a_model_with_no_parameter_table(pattern):
    """WP-1035: ``edit`` is the one write pydantic cannot check.

    A ``Structure`` validates against its schema knowing no crystallography;
    every symmetry refusal in this package is raised where a ``ParameterTable``
    is *constructed*, and the snapshot ``edit`` commits never constructs one. So
    an incompatible model used to be accepted, recorded as a node, and then raise
    from whatever next asked for the table — leaving the working state somewhere
    no fit and no listing can be built from. Measured through the GUI as a 500 on
    the following ``GET /api/params``, but the exposure was the library's.
    """
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(pattern, plan=SHORT)
    head, n_nodes = ref.history.head, len(ref.history)

    bad = copy.deepcopy(ref.structure)
    bad.phases[0].atoms[0].aniso = pr.AnisoU.isotropic(0.006, bad.phases[0].cell)
    bad.phases[0].atoms[0].aniso.u12.value = 0.004   # no cubic site allows shear
    with pytest.raises(ValueError, match="no parameter table"):
        ref.edit(structure=bad, label="should not land")

    # nothing moved: not the head, not the node count, not the working models
    assert (ref.history.head, len(ref.history)) == (head, n_nodes)
    assert ref.structure.phases[0].atoms[0].aniso is None
    assert ParameterTable(ref.structure, ref.instrument).entries

    # …and the gate reads the *proposed* pair, so an edit that repairs a broken
    # state is not refused by the damage it is undoing
    ref.structure.phases[0].atoms[0].aniso = bad.phases[0].atoms[0].aniso
    with pytest.raises(ValueError):
        ref.parameters()                              # the state of record
    fixed = copy.deepcopy(ref.structure)
    fixed.phases[0].atoms[0].aniso = None
    assert ref.edit(structure=fixed, label="repair") is not None
    assert ref.parameters()


# ------------------------------------------------------------- persistence
def test_jsonl_round_trip(tmp_path, pattern):
    structure, ins = perturbed_models()
    path = tmp_path / "run.jsonl"
    ref = pr.Refinement(structure, ins, history=str(path))
    ref.fit(pattern, plan=SHORT)
    ref.history.tag(ref.history.root.id, "start")

    loaded = pr.RefinementTree.load(path)
    assert loaded.order == ref.history.order
    for nid in ref.history.order:
        assert loaded.nodes[nid].model_dump_json() == ref.history.nodes[nid].model_dump_json()
    assert loaded.refs.get("start") == ref.history.root.id
    assert loaded.header.data_fingerprint == ref.history.header.data_fingerprint

    # ±inf parameter bounds must survive the state round-trip
    atom_x = loaded.root.state.structure.phases[0].atoms[0].x
    assert math.isinf(atom_x.max) and math.isinf(atom_x.min)


def test_save_rewrites_an_in_memory_tree(tmp_path, fitted):
    ref, _ = fitted
    path = tmp_path / "saved.jsonl"
    ref.history.save(path)
    loaded = pr.RefinementTree.load(path)
    assert len(loaded) == len(ref.history)


def test_head_survives_a_reload(tmp_path, pattern):
    """A reloaded tree stands where the session left it (WP-1005).

    Both halves were broken and each fails on its own: ``add`` advances HEAD in
    memory but appends no ref record, so a log written by a plain ``fit``
    reloaded with ``refs == {}`` — ``tree["head"]`` raised, and a project could
    not resume.  And ``load`` applied every node before every annotation, so a
    ``checkout`` earlier in the file overrode the nodes committed *after* it and
    HEAD came back stale.  File order is what distinguishes the two.
    """
    structure, ins = perturbed_models()
    plain = tmp_path / "plain.jsonl"
    ref = pr.Refinement(structure, ins, history=str(plain))
    ref.fit(pattern, plan=SHORT)
    assert pr.RefinementTree.load(plain).head == ref.history.head == ref.history.order[-1]

    # checkout (which annotates HEAD) then continue: the later node must win
    branched = tmp_path / "branched.jsonl"
    ref2 = pr.Refinement(*perturbed_models(), history=str(branched))
    ref2.fit(pattern, plan=SHORT)
    ref2.checkout(ref2.history.order[1])
    ref2.run_stage(pattern, pr.Stage("zero", ["instrument.zero_shift"], max_iter=5))
    loaded = pr.RefinementTree.load(branched)
    assert loaded.head == ref2.history.head == ref2.history.order[-1]

    # a tag names a node without moving HEAD, before or after a reload
    ref2.history.tag(ref2.history.order[1], "rival")
    reloaded = pr.RefinementTree.load(branched)
    assert reloaded.refs["rival"] == ref2.history.order[1]
    assert reloaded.head == ref2.history.order[-1]


def test_replay_rejects_a_different_pattern(fitted):
    ref, _ = fitted
    other = synthesize(noise_seed=99)
    with pytest.raises(ValueError, match="fingerprint"):
        replay(ref.history, ref.history.order[-1], other)


# ----------------------------------------------------------------- queries
def test_tree_queries(fitted):
    ref, _ = fitted
    tree = ref.history

    best = tree.best("rwp")
    assert best.metrics.statistics.rwp == min(
        n.metrics.statistics.rwp for n in tree.nodes.values()
        if n.metrics.statistics)

    # `tree.order[-1]`, not `tree.head`: other tests share this module-scoped
    # tree and HEAD follows whoever checked out last.
    lineage = tree.lineage(tree.order[-1])
    assert [n.id for n in lineage] == tree.order  # a single chain
    assert lineage[0].parents == []

    rows = tree.compare([n.id for n in tree.nodes.values() if n.metrics.statistics])
    assert all("rwp" in r for r in rows)

    changed = tree.diff(tree.root.id, tree.order[-1])
    assert any(p.endswith("cell.a") for p in changed)

    tree.tag(tree.root.id, "start")
    assert tree["start"].id == tree.root.id
    with pytest.raises(KeyError):
        tree["nope"]


def test_tag_cannot_shadow_head(fitted):
    ref, _ = fitted
    with pytest.raises(ValueError, match="reserved"):
        ref.history.tag(ref.history.root.id, "head")


def test_summary_and_mermaid_render(fitted):
    ref, _ = fitted
    text = ref.history.summary()
    assert ref.history.header.tree_id in text
    assert "scale_bkg" in text
    mermaid = ref.history.to_mermaid()
    assert mermaid.startswith("graph TD")
    assert "-->" in mermaid


def test_restoring_dropped_paths_warns(pattern):
    """A path that no longer exists must not vanish silently."""
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(pattern, plan=SHORT)
    # shrink the background so the high-order coefficients disappear
    ref.instrument.background = BackgroundChebyshev.with_terms(2)
    with pytest.warns(UserWarning, match="no longer exist"):
        ref.run_stage(pattern, pr.Stage("zero", ["instrument.zero_shift"], max_iter=10))


# -------------------------------------------------------------------- plot
def test_branch_overlay_plot(tmp_path, pattern):
    """Write the two competing branches to tests/output/ for visual inspection."""
    plt = pytest.importorskip("matplotlib.pyplot")

    import numpy as np

    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(pattern, plan=SHORT)
    tree = ref.history
    fork = [n for n in tree.nodes.values() if n.action.name == "cell"][0]

    # two plausible continuations of the same checkpoint: widen only W, or
    # free the whole TCHZ profile
    rivals = [
        pr.Stage("profile_w", ["instrument.profile.w"], max_iter=40),
        pr.Stage("profile_all", ["instrument.profile.u", "instrument.profile.v",
                                 "instrument.profile.w", "instrument.profile.x",
                                 "instrument.profile.y"], max_iter=40),
    ]
    for stage in rivals:
        ref.checkout(fork.id)
        ref.run_stage(pattern, stage)

    leaves = tree.leaves()
    assert len(leaves) == 2

    OUT.mkdir(exist_ok=True)
    fig, axes = plt.subplots(len(leaves), 1, figsize=(10, 8), sharex=True, dpi=130)
    for ax, leaf in zip(axes, leaves, strict=True):
        res = replay(tree, leaf.id, pattern)
        tt = np.asarray(res.two_theta)
        y_obs, y_calc = np.asarray(res.y_obs), np.asarray(res.y_calc)
        span = float(y_obs.max() - min(y_obs.min(), 0.0))
        offset = -0.12 * span
        ax.plot(tt, y_obs, ".", ms=2.5, color="#1f5fa8", label="observed")
        ax.plot(tt, y_calc, "-", lw=1.0, color="#c23b22", label="calculated")
        ax.plot(tt, y_obs - y_calc + offset, "-", lw=0.7, color="#4a4a4a",
                label="difference")
        ax.axhline(offset, lw=0.4, color="#bbbbbb")
        ax.set_title(f"{leaf.id}  {leaf.action.name}  "
                     f"Rwp={res.statistics.rwp:.4f}  GoF={res.statistics.gof:.2f}",
                     fontsize=9)
        ax.legend(loc="upper right", fontsize=7, frameon=False)
        ax.set_ylabel("intensity")
    axes[-1].set_xlabel(r"2$\theta$ (deg)")
    fig.suptitle(f"Rival continuations of checkpoint {fork.id} "
                 f"(Rwp={fork.metrics.statistics.rwp:.4f})", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "history_branches.png")
    plt.close(fig)
    assert (OUT / "history_branches.png").exists()


# ----------------------------------------------- stage arguments survive a node
def test_stage_node_carries_its_seeds(pattern):
    """A recorded stage must replay as the stage that ran (WP-1004).

    ``cherry_pick`` rebuilds a ``Stage`` from ``NodeAction``, so any stage
    argument missing there is a stage that replays *differently* — the
    extinction stage would start on the softplus dead-gradient floor and a
    Stephens stage from the all-zero block its seed exists to avoid.  Pinned on
    the recorded action and on the rendered api_call, which is what a session
    log promises is equivalent.
    """
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    seeded = pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                      max_iter=10, seed=1e-3, strain_seed=1000.0)
    ref.run_stage(pattern, seeded)
    action = ref.history[ref.history.order[-1]].action
    assert (action.seed, action.strain_seed) == (1e-3, 1000.0)
    assert "seed=0.001" in action.api_call()
    assert "strain_seed=1000.0" in action.api_call()
    # and through JSON, the round trip a persisted tree takes
    reloaded = pr.NodeAction.model_validate_json(action.model_dump_json())
    assert (reloaded.seed, reloaded.strain_seed) == (1e-3, 1000.0)


def test_stage_node_without_seeds_renders_unchanged(fitted):
    """An unseeded stage's api_call keeps its pre-WP-1004 text exactly."""
    ref, _ = fitted
    node = ref.history[ref.history.order[-1]]
    assert node.action.api_call() == (
        "ref.run_stage(data, pr.Stage('cell', ['phases.*.cell.*'], max_iter=40))")
