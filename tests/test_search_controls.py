"""WP-1045 — one indexing control surface, three chairs, held by meta-test.

``SearchSpecSpec`` (the pydantic twin of the frozen ``SearchSpec``) lives in
``schemas/indexing.py`` and every chair consumes it: the agent request
re-exports it (the ``StageSpec`` precedent), the project document embeds it
(``ProjectDoc.indexing``, which is what the GUI form edits and the index run
reads), and ``index_pattern`` is called with what it maps to.  These tests are
the bijection: a field added to one view and not the others fails here, not in
a user's hands.

The GUI form's own half lives in ``gui/src/lib/peaks.test.ts``, replaying the
committed corpus this file writes (``tests/data/gui/index_controls.json``) —
the ``test_gui_fnmatch`` mechanism: python owns the vocabulary, TS proves it
renders it.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from pathlib import Path

import pytest

from rietx.indexing.engines import (
    CENTRINGS,
    SEARCH_PRESETS,
    SYSTEM_ORDER,
    SearchSpec,
    engine_names,
)
from rietx.schemas.indexing import (
    SHIFT_TEMPLATES,
    IndexingControls,
    SearchSpecSpec,
)

# ----------------------------------------------------------------------
# the bijection: SearchSpecSpec ↔ SearchSpec
# ----------------------------------------------------------------------
#: model fields that are deliberately *not* ``SearchSpec`` fields, each with
#: the reason it rides the model anyway.  Grow this only with a reason.
MODEL_EXTRAS = {
    # an ``index_pattern`` kwarg, not a spec field: the preset *fills in*
    # total_budget_seconds, and recording which name governed the ceiling is
    # the run's job (``spec_notes["preset"]``), not the spec's
    "preset",
}


def test_searchspecspec_mirrors_searchspec_field_for_field():
    """The ``ParameterRow``/``Entry`` pin one surface over: pinned by
    ``dataclasses.fields``, so a field added to either side fails until the
    other has it (or names itself in ``MODEL_EXTRAS`` with a reason)."""
    spec_fields = {f.name for f in dataclasses.fields(SearchSpec)}
    model_fields = set(SearchSpecSpec.model_fields)
    assert model_fields - spec_fields == MODEL_EXTRAS
    assert spec_fields - model_fields == set(), (
        "SearchSpec grew a field the control surface cannot state")


#: one non-default value per model field — ``to_spec`` must carry every one.
#: A field added to the model without a row here fails the coverage assert.
_ROUND_TRIP = {
    "systems": ["tetragonal", "cubic"],
    "centrings": {"cubic": ["P", "I"]},
    "min_d_axis": 2.5,
    "max_d_axis": 11.0,
    "min_volume": 20.0,
    "max_volume": 900.0,
    "n_unindexed": 1,
    "n_search_lines": 18,
    "k_sigma": 2.5,
    "shift_allowance_deg": 0.03,
    "shift_template": "constant",
    "budget_seconds": 12.0,
    "total_budget_seconds": 77.0,
    "preset": "quick",
    "max_candidates": 7,
    "seed": 3,
    "prior_cells": [(4.76, 4.76, 12.99, 90.0, 90.0, 120.0)],
    "prior_spacegroups": ["R -3 c"],
}


def test_to_spec_carries_every_field():
    assert set(_ROUND_TRIP) == set(SearchSpecSpec.model_fields), (
        "a model field has no round-trip row — add one, or to_spec can drop "
        "it silently")
    spec = SearchSpecSpec(**_ROUND_TRIP).to_spec()
    assert spec == SearchSpec(
        systems=("tetragonal", "cubic"), centrings={"cubic": ("P", "I")},
        min_d_axis=2.5, max_d_axis=11.0, min_volume=20.0, max_volume=900.0,
        n_unindexed=1, n_search_lines=18, k_sigma=2.5,
        shift_allowance_deg=0.03, shift_template="constant",
        budget_seconds=12.0, total_budget_seconds=77.0,
        max_candidates=7, seed=3,
        prior_cells=((4.76, 4.76, 12.99, 90.0, 90.0, 120.0),),
        prior_spacegroups=("R -3 c",))


def test_the_models_defaults_are_the_dataclasss_defaults():
    """Two default sets is a drift channel; one line closes it."""
    assert SearchSpecSpec().to_spec() == SearchSpec()
    assert IndexingControls().search == SearchSpecSpec()


# ----------------------------------------------------------------------
# the bijection: IndexingControls ↔ index_pattern's signature
# ----------------------------------------------------------------------
#: ``index_pattern`` parameters that are *call-time inputs*, not settings a
#: chair stores: the data itself, plumbing, and facts another authority owns.
CALL_TIME_INPUTS = {
    "peaks", "data", "instrument",   # the data itself
    "quality",                       # a precomputed report, an optimisation
    "shift_from_pairs",              # the screen's own switch, not a control
    "events", "cancel",              # plumbing
    "two_theta_limits",              # the project document owns this fact
}
#: parameters the controls reach through ``search`` rather than by name
VIA_SEARCH = {"spec", "preset"}
#: controls-field → index_pattern parameter
CONTROL_TO_KWARG = {
    "engines": "engines",
    "validate_candidates": "validate",
    "check_top": "check_top",
}


def test_indexing_controls_cover_index_pattern():
    from rietx.indexing.workflow import index_pattern

    params = set(inspect.signature(index_pattern).parameters)
    assert params == CALL_TIME_INPUTS | VIA_SEARCH | set(
        CONTROL_TO_KWARG.values()), (
        "index_pattern's signature moved; the control surface (and this "
        "test's declared exceptions) must move with it")
    assert set(IndexingControls.model_fields) == (
        {"search"} | set(CONTROL_TO_KWARG))


# ----------------------------------------------------------------------
# the bijection: the agent request
# ----------------------------------------------------------------------
def test_the_agent_re_exports_the_one_model():
    """``SearchSpecSpec`` reaches the agent as the one class (it is the
    ``IndexRequest.search`` annotation); the pure ``IndexingControls``
    re-export went pre-freeze (WP-1003), and its absence is the guard against
    a private copy coming back under that name."""
    import rietx.agent as ag

    assert ag.SearchSpecSpec is SearchSpecSpec
    assert not hasattr(ag, "IndexingControls")


def test_the_agent_request_carries_every_control():
    """Flat on the request (agent ergonomics), same names, same model."""
    import rietx.agent as ag

    fields = ag.IndexRequest.model_fields
    assert fields["search"].annotation is SearchSpecSpec
    for name in CONTROL_TO_KWARG:
        assert name in fields, f"IndexRequest lacks the {name!r} control"


# ----------------------------------------------------------------------
# the project document
# ----------------------------------------------------------------------
def test_the_project_document_round_trips_the_controls():
    from rietx.schemas.project import ProjectDoc

    doc = ProjectDoc(indexing=IndexingControls(
        search=SearchSpecSpec(**_ROUND_TRIP), engines=["svd"],
        validate_candidates=False, check_top=2))
    back = ProjectDoc.model_validate_json(doc.model_dump_json())
    assert back.indexing == doc.indexing

    # a document written before WP-1045 has no key — defaults, not a refusal
    old = json.loads(ProjectDoc().model_dump_json())
    old.pop("indexing")
    assert ProjectDoc.model_validate(old).indexing == IndexingControls()


# ----------------------------------------------------------------------
# the vocabulary validators quote the live registries
# ----------------------------------------------------------------------
@pytest.mark.parametrize("bad,where", [
    ({"systems": ["cubbic"]}, "cubic"),
    ({"centrings": {"cubic": ["R"]}}, "P, I, F"),
    ({"centrings": {"cubic": []}}, "empty"),
    ({"centrings": {"nonagonal": ["P"]}}, "unknown crystal system"),
    ({"shift_template": "cos"}, "cos_theta"),
    ({"preset": "fast"}, "quick"),
])
def test_a_wrong_vocabulary_member_is_refused_with_the_live_list(bad, where):
    with pytest.raises(ValueError, match=where):
        SearchSpecSpec(**bad)


def test_a_wrong_engine_is_refused_with_the_live_list():
    with pytest.raises(ValueError, match="dichotomy"):
        IndexingControls(engines=["dicvol"])


# ----------------------------------------------------------------------
# the GUI's half: the committed corpus the form test replays
# ----------------------------------------------------------------------
CORPUS = Path(__file__).parent / "data" / "gui" / "index_controls.json"


def test_the_form_corpus_quotes_the_live_registries():
    """Writes the corpus (the ``test_gui_fnmatch`` mechanism): python owns the
    field inventory and the vocabularies; ``gui/src/lib/peaks.test.ts``
    replays this file and fails if the form cannot state a field.  Committed,
    so a stale corpus shows up as a diff and CI needs no python-node bridge.
    """
    corpus = {
        "search_fields": list(SearchSpecSpec.model_fields),
        "control_fields": [n for n in IndexingControls.model_fields
                           if n != "search"],
        "enums": {
            "engines": list(engine_names()),
            "systems": list(SYSTEM_ORDER),
            "centrings": {k: list(v) for k, v in CENTRINGS.items()},
            "presets": sorted(SEARCH_PRESETS),
            "shift_templates": list(SHIFT_TEMPLATES),
        },
    }
    CORPUS.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(corpus, indent=1, sort_keys=True) + "\n"
    if not CORPUS.exists() or CORPUS.read_text(encoding="utf-8") != text:
        CORPUS.write_text(text, encoding="utf-8")
    assert json.loads(CORPUS.read_text(encoding="utf-8")) == corpus


# ----------------------------------------------------------------------
# the acceptance criterion: two chairs, identical controls, identical notes
# ----------------------------------------------------------------------
@pytest.mark.xdist_group("search-controls-chairs")
def test_gui_and_agent_runs_produce_identical_spec_notes(tmp_path):
    """The WP's acceptance sentence, run literally: the GUI chair (a project
    whose document carries the controls, the run reading them) and the agent
    chair (the same fields on the request) hand ``index_pattern`` the same
    call, and the result's ``spec_notes`` — which since WP-1045 record every
    ``SearchSpec`` field — are byte-identical."""
    import time

    import rietx as rx
    import rietx.agent as ag
    from rietx.gui import GuiSession
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import perturbed_models, synthesize

    controls = {
        "search": {"systems": ["cubic"], "max_volume": 800.0,
                   "shift_allowance_deg": 1e-9, "budget_seconds": 20.0,
                   "total_budget_seconds": 60.0, "seed": 5},
        "validate_candidates": False,
    }

    pattern = synthesize()
    structure, instrument = perturbed_models()
    file = _write_xye(tmp_path / "chairs.xye", pattern)
    project = rx.Project.create(tmp_path / "chairs.rex", pattern=file,
                                structure=structure, instrument=instrument)
    session = GuiSession(project, state_dir=tmp_path / "state")
    try:
        session.project_patch({"indexing": controls})
        session.run({"kind": "index"})
        deadline = time.monotonic() + 120.0
        while session.run_state()["state"] != "idle":
            assert time.monotonic() < deadline, "index run did not finish"
            time.sleep(0.1)
        assert session.run_state()["run"]["status"] == "completed"
        gui_notes = session.index_result()["result"]["provenance"]["notes"]
    finally:
        session.close()

    out = ag.refine_json({
        "task": "index",
        "pattern": json.loads(pattern.model_dump_json()),
        "instrument": json.loads(instrument.model_dump_json()),
        **{k: v for k, v in controls.items() if k != "search"},
        "search": controls["search"],
    })
    assert out["ok"] is True, out.get("error")
    agent_notes = out["indexing"]["provenance"]["notes"]

    assert gui_notes == agent_notes
