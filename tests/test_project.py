"""WP-1005 — the project container: create, open, save, and what may not drift.

Most of these are cheap (no refinement): what a project has to get right is the
*bindings* — bytes, parsed numbers, reader call, history tree — and every one of
them is checkable without solving anything.  One module-scoped fit exists to
prove the interesting half, that reopening resumes mid-history at the head.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.project import PROJECT_JSON
from tests.test_refine_synthetic import perturbed_models, synthesize

OUT = Path(__file__).parent / "output"

pytestmark = pytest.mark.xdist_group("project")

#: The real preset rather than a two-stage stub, because the fixture's PNG is the
#: visual gate this suite's numbers cannot be (CLAUDE.md, Tests).  A partial plan
#: converges to a *bad* fit by design — dropping the zero-shift stage alone leaves
#: a derivative-shaped residual on every peak — and a picture that always looks
#: wrong cannot show that something is.  It costs well under a second here.
SHORT = rx.PLAN_PRESETS["mccusker_default"]()

DATA = Path(__file__).parent / "data"


def _write_xye(path: Path, data: rx.PatternData, *, with_sigma: bool = True) -> Path:
    """The synthetic pattern as a file, since a project copies bytes not objects.

    ``repr`` of a float round-trips exactly, so the parsed arrays are
    bit-identical to ``data`` and the fingerprints must agree.

    The esd column is deliberately **not** √max(y,1): an esd equal to the Poisson
    fallback would make "the file's weights survived the copy" untestable, since
    losing the column entirely would produce the same numbers.  1.3× stands for
    any of the ordinary reasons a measured esd is not raw counting statistics
    (monitor normalisation, merged frames, a detector gain).
    """
    sig = 1.3 * np.sqrt(np.maximum(np.asarray(data.intensity), 1.0))
    rows = (f"{float(t)!r} {float(y)!r} {float(s)!r}" if with_sigma
            else f"{float(t)!r} {float(y)!r}"
            for t, y, s in zip(data.two_theta, data.intensity, sig))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture(scope="module")
def pattern_file(tmp_path_factory, pattern):
    return _write_xye(tmp_path_factory.mktemp("data") / "synth.xye", pattern)


def _create(root: Path, pattern_file: Path, **kw) -> rx.Project:
    structure, ins = perturbed_models()
    return rx.Project.create(root, pattern=pattern_file, structure=structure,
                             instrument=ins, **kw)


@pytest.fixture(scope="module")
def fitted_project(tmp_path_factory, pattern_file):
    """One real refinement inside a project, shared by the resume tests."""
    project = _create(tmp_path_factory.mktemp("fitted") / "sample.rex", pattern_file)
    result = project.fit(plan=SHORT)
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / "project_container.png"))
    return project, result


# ------------------------------------------------------------------ layout
def test_create_writes_the_documented_layout(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file, ui={"disclosure": "simple"})

    assert sorted(p.name for p in project.path.iterdir()) == [
        "exports", "history.jsonl", "live", "project.json", "synth.xye"]
    assert project.live_dir.is_dir() and project.exports_dir.is_dir()
    # the pattern is a byte-for-byte copy, not a re-serialisation
    assert (project.path / "synth.xye").read_bytes() == pattern_file.read_bytes()
    # the root node is the as-created model, so "undo everything" has a target
    assert len(project.history) == 1
    assert project.history.root.action.kind == "root"
    assert project.refinement._head_id == project.history.head


def test_create_refuses_to_write_over_a_project(tmp_path, pattern_file):
    _create(tmp_path / "s.rex", pattern_file)
    with pytest.raises(FileExistsError, match="open it instead"):
        _create(tmp_path / "s.rex", pattern_file)


def test_missing_pattern_file_is_named(tmp_path):
    structure, ins = perturbed_models()
    with pytest.raises(FileNotFoundError, match="pattern file not found"):
        rx.Project.create(tmp_path / "s.rex", pattern=tmp_path / "nope.xy",
                          structure=structure, instrument=ins)


# --------------------------------------------------------------- round trip
def test_document_round_trip_including_infinite_bounds(tmp_path, pattern_file):
    """±inf bounds must survive JSON, and the project's own document too.

    The bounds live in the history node here, not in ``project.json`` — which is
    the point of the split — so this exercises both files in one open.
    """
    project = _create(tmp_path / "s.rex", pattern_file, plan="mccusker_default",
                      mode="rietveld", two_theta_limits=(4.0, 22.0),
                      excluded_regions=[(7.5, 8.0)], ui={"panels": ["plot", "params"]})
    project.save()

    raw = json.loads((project.path / PROJECT_JSON).read_text(encoding="utf-8"))
    assert raw["format_version"] == "1.2"   # WP-1123: the plan grew a schedule
    assert raw["patterns"][0]["reader"] == "xy"

    reopened = rx.Project.open(project.path)
    assert reopened.doc.model_dump() == project.doc.model_dump()
    assert reopened.doc.ui == {"panels": ["plot", "params"]}
    assert reopened.doc.two_theta_limits == (4.0, 22.0)
    assert reopened.doc.excluded_regions == [(7.5, 8.0)]
    # the exclusion reaches the data, not just the document
    assert reopened.data.excluded_regions == [(7.5, 8.0)]
    assert reopened.data.in_range_mask().sum() < len(reopened.data.two_theta)
    # the plan is a PlanSpec and rebuilds the preset it names
    assert [s.name for s in reopened.doc.plan.to_plan().stages] == \
           [s.name for s in rx.PLAN_PRESETS["mccusker_default"]().stages]

    x = reopened.refinement.parameters()
    unbounded = [r for r in x if math.isinf(r.hi)]
    assert unbounded, "some parameters are genuinely unbounded above"
    assert all(math.isinf(r.hi) for r in unbounded)


def test_a_user_tie_survives_the_round_trip_without_a_save(tmp_path, pattern_file):
    """The constraint is model state, so the log carries it and ``save`` is idle.

    One authority per fact: ``history.jsonl`` holds the model state and its head
    *is* the working state, so a tie is on disk the moment it is declared —
    exactly as ``set_vary`` is.  Reopening must come back with the same
    parameter count, not merely the same values: a project that dropped the
    constraint would refine one parameter more than the protocol it recorded,
    and every esd it quoted afterwards would be the wrong one.
    """
    project = _create(tmp_path / "tied.rex", pattern_file)
    bisos = ["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"]
    project.refinement.tie_equal(bisos)
    project.refinement.set_vary(["phases.0.atoms.*.biso"])

    reopened = rx.Project.open(project.path)
    rows = {r.path: r for r in reopened.parameters()}
    assert rows[bisos[1]].tie is not None and rows[bisos[1]].tie.user
    assert rows[bisos[1]].tie.sources == [bisos[0]]
    assert rows[bisos[0]].vary and not rows[bisos[1]].vary
    # and it is still the user's to release after the round trip
    assert reopened.refinement.untie(bisos[1]) == [bisos[1]]


def test_open_accepts_the_document_path(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    assert rx.Project.open(project.path / PROJECT_JSON).path == project.path


def test_save_never_rewrites_the_pattern_or_the_log(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    before = {p.name: p.read_bytes() for p in project.path.iterdir() if p.is_file()}
    project.doc.ui["zoom"] = [10.0, 20.0]
    project.save()
    after = {p.name: p.read_bytes() for p in project.path.iterdir() if p.is_file()}

    assert after["synth.xye"] == before["synth.xye"]
    assert after["history.jsonl"] == before["history.jsonl"]
    assert after[PROJECT_JSON] != before[PROJECT_JSON]
    assert not list(project.path.glob("*.tmp")), "the atomic write left no debris"


# ------------------------------------------------------------- the bindings
def test_esd_column_survives_the_copy(tmp_path, pattern, pattern_file):
    """The file's esds are the weights; the Poisson fallback is *not* equivalent.

    Read the copy the project made and compare the weights it yields against the
    original file's — the reason the pattern is copied verbatim rather than
    re-serialised (CLAUDE.md, Weights).
    """
    project = _create(tmp_path / "s.rex", pattern_file)
    original = rx.read_pattern(pattern_file)
    copied = project.data

    assert project.data_ref.has_sigma is True
    assert copied.sigma is not None
    np.testing.assert_array_equal(copied.sig(), original.sig())
    # and they are not the Poisson fallback in disguise
    poisson = rx.PatternData(two_theta=copied.two_theta, intensity=copied.intensity)
    assert not np.allclose(copied.sig(), poisson.sig())


def test_a_pattern_without_esds_says_so(tmp_path, tmp_path_factory, pattern):
    plain = _write_xye(tmp_path_factory.mktemp("plain") / "noesd.xy", pattern,
                       with_sigma=False)
    project = _create(tmp_path / "s.rex", plain)
    assert project.data_ref.has_sigma is False
    assert project.data.sigma is None


def test_edited_pattern_file_is_refused(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    copied = project.path / project.data_ref.filename
    copied.write_text(copied.read_text(encoding="utf-8") + "99.0 1.0 1.0\n",
                      encoding="utf-8")
    with pytest.raises(ValueError, match="file has changed"):
        rx.Project.open(project.path)


def test_same_bytes_parsed_differently_is_reported_as_a_reader_change(
        tmp_path, pattern_file):
    """The two digests answer different questions, and the message says which.

    Editing the recorded fingerprint while leaving the sha256 alone is exactly
    the state a reader change would produce: the bytes are what they always
    were, the numbers are not.
    """
    project = _create(tmp_path / "s.rex", pattern_file)
    doc_path = project.path / PROJECT_JSON
    raw = json.loads(doc_path.read_text(encoding="utf-8"))
    raw["patterns"][0]["fingerprint"] = "0" * 32
    doc_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="parses them differently"):
        rx.Project.open(project.path)


def test_history_recorded_against_another_pattern_is_refused(
        tmp_path, tmp_path_factory, pattern):
    """A container may not silently rebind a tree to different data.

    ``refine.replay`` enforces this per node; a project that opened anyway would
    be the same failure one level up, and permanent rather than per call.
    """
    mine = _write_xye(tmp_path_factory.mktemp("mine") / "a.xye", pattern)
    other = _write_xye(tmp_path_factory.mktemp("other") / "b.xye",
                       synthesize(noise_seed=99))
    project = _create(tmp_path / "s.rex", mine)
    stranger = _create(tmp_path / "t.rex", other)

    (project.path / "history.jsonl").write_bytes(
        (stranger.path / "history.jsonl").read_bytes())
    with pytest.raises(ValueError, match="recorded against a different pattern"):
        rx.Project.open(project.path)


def test_missing_history_log_is_refused(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    (project.path / "history.jsonl").unlink()
    with pytest.raises(FileNotFoundError, match="holds the model state"):
        rx.Project.open(project.path)


def test_a_future_format_version_is_refused_by_name(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    doc_path = project.path / PROJECT_JSON
    raw = json.loads(doc_path.read_text(encoding="utf-8"))
    raw["format_version"] = "2"
    doc_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="another version of rietx"):
        rx.Project.open(project.path)


def test_multi_pattern_projects_are_refused_not_truncated(tmp_path, pattern_file):
    """The ``patterns`` list is the multi-histogram seam, not a feature yet."""
    project = _create(tmp_path / "s.rex", pattern_file)
    doc_path = project.path / PROJECT_JSON
    raw = json.loads(doc_path.read_text(encoding="utf-8"))
    raw["patterns"].append(dict(raw["patterns"][0]))
    doc_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="single-pattern projects only"):
        rx.Project.open(project.path)


# ------------------------------------------------------- the reader *call*
def test_the_pdcif_block_is_recorded_and_replayed(tmp_path):
    """Re-opening must reproduce the reader call, not merely the file.

    The NIST SRM 660c certification file carries both a measured and a
    calculated block with identical tags, and the default read takes the first
    that parses — so a project that recorded only the path would come back with
    a different pattern, and (because the fingerprint would then disagree) as a
    hard error rather than a wrong answer.  Recording ``block`` is what makes it
    open at all.
    """
    cif = DATA / "nist_srm660c_100a.cif"
    structure, ins = perturbed_models()
    project = rx.Project.create(tmp_path / "cert.rex", pattern=cif,
                                structure=structure, instrument=ins,
                                reader_options={"block": "_calc"})

    assert project.data_ref.reader == "pdcif"
    assert project.data_ref.options == {"block": "_calc"}
    assert "calc" in project.data.metadata["block"]

    reopened = rx.Project.open(project.path)
    assert reopened.data.metadata["block"] == project.data.metadata["block"]
    # …and the default read really does pick a different block, so this matters
    assert rx.read_pattern(cif).metadata["block"] != project.data.metadata["block"]


# --------------------------------------------------------------- the session
def test_settings_drive_the_convenience_verbs(tmp_path, pattern_file):
    """``project.fit()`` runs the project's own plan, mode and limits."""
    one = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                 max_iter=5)])
    project = _create(tmp_path / "s.rex", pattern_file, plan=one,
                      two_theta_limits=(4.0, 20.0))
    result = project.fit()

    assert [s.name for s in result.stages] == ["scale_bkg"]
    assert project.refinement._two_theta_limits == (4.0, 20.0)


def test_run_stage_uses_the_documents_mode_before_any_fit(tmp_path, pattern_file):
    """A Le Bail project driven one stage at a time must not start in Rietveld.

    ``Refinement.run_stage`` defaults ``mode`` to the value it carries, which
    before the first run is the ``"rietveld"`` default — so the mode a project
    selected has to be passed explicitly, and this is the test that says so.
    """
    project = _create(tmp_path / "s.rex", pattern_file, mode="lebail")
    result = project.run_stage(
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                 max_iter=5))
    assert result.mode == "lebail"
    assert project.history[project.history.head].state.mode == "lebail"


def test_set_excluded_regions_updates_document_and_data(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    project.set_excluded_regions([(6.0, 6.5)])
    assert project.doc.excluded_regions == [(6.0, 6.5)]
    assert project.data.excluded_regions == [(6.0, 6.5)]
    project.save()
    assert rx.Project.open(project.path).data.excluded_regions == [(6.0, 6.5)]


def test_an_unrun_edit_is_in_the_log_before_any_save(tmp_path, pattern_file):
    """Nothing has to be saved for work to be durable.

    The tree exists from ``create``, so ``set_vary``/``set_values`` commit a node
    immediately — which is what settles the WP-1004 question of whether a project
    edited without running anything has state no history node describes.
    """
    project = _create(tmp_path / "s.rex", pattern_file)
    project.refinement.set_vary("instrument.zero_shift", True)
    project.refinement.set_values({"phases.0.cell.a": 4.16})

    reopened = rx.Project.open(project.path)  # no save() in between
    assert [n.action.kind for n in reopened.history.nodes.values()] == \
           ["root", "set_vary", "set_value"]
    assert reopened.refinement.fitted_structure.phases[0].cell.a.value == 4.16
    assert "instrument.zero_shift" in reopened.refinement._free_paths


def test_reopen_mid_history_resumes_at_head(fitted_project, pattern):
    project, result = fitted_project
    assert result.node_id == project.history.head

    reopened = rx.Project.open(project.path)
    assert len(reopened.history) == 1 + len(SHORT.stages)
    assert reopened.refinement._head_id == project.history.head
    # the working state is the fitted one, not the as-created one
    fitted_a = project.refinement.fitted_structure.phases[0].cell.a.value
    assert reopened.refinement.fitted_structure.phases[0].cell.a.value == fitted_a
    assert reopened.refinement._free_paths == project.refinement._free_paths
    # and it can be continued: a new stage lands as a child of the head
    reopened.run_stage(rx.Stage("zero", ["instrument.zero_shift"], max_iter=5))
    assert reopened.history[reopened.history.head].parents == [result.node_id]


def test_a_reopened_project_can_replay_its_head(fitted_project):
    """The reopened tree and the reopened data are compatible in both directions.

    ``replay`` is the strictest check available: it refuses a pattern whose
    fingerprint does not match the tree, then recompiles the node's state from
    scratch.  Agreement with the node's cached metrics is close but not exact —
    those are *as-optimised*, measured on a model frozen at the values the stage
    started from (see ``NodeMetrics``).
    """
    project, _ = fitted_project
    reopened = rx.Project.open(project.path)

    replayed = rx.replay(reopened.history, "head", reopened.data)
    cached = reopened.history[reopened.history.head].metrics.statistics.rwp
    assert replayed.statistics.rwp == pytest.approx(cached, rel=1e-3)
    assert len(reopened.refinement.parameters()) == \
           len(project.refinement.parameters())


def test_a_project_reopens_on_the_scan_it_was_created_from(tmp_path):
    """The reader *call* is part of the reference, not just the bytes.

    A multi-scan file's sha256 and its parsed-array fingerprint say nothing
    about *which* scan was read, so ``scan`` has to be recorded beside ``block``
    — and recorded as the **effective** option, which is what re-opening
    replays.
    """
    structure, ins = perturbed_models()
    proj = rx.Project.create(tmp_path / "high.rex",
                             pattern=DATA / "rigaku_multiscan.ras",
                             structure=structure, instrument=ins,
                             reader_options={"scan": 1})

    ref = proj.doc.patterns[0]
    assert ref.reader == "ras"
    assert ref.options == {"scan": "1"}                # dict[str, str] on disk
    assert proj.data.two_theta == [20.0, 20.5, 21.0]

    reopened = rx.Project.open(tmp_path / "high.rex")
    assert reopened.data.two_theta == [20.0, 20.5, 21.0]
    assert reopened.doc.patterns[0].fingerprint == ref.fingerprint
