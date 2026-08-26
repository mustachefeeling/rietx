"""The single-call JSON surface: ``agent.refine_json(dict) → dict`` (WP-0602).

Everything here goes through plain dicts and back — the point of the surface
is that an agent never touches a python object.  One synthetic single-pattern
fit is shared module-wide (hence the xdist group pinning this module to one
worker); the validation and schema tests cost nothing.
"""

from __future__ import annotations

import copy
import json

import pytest

import rietx as rx
import rietx.agent as ag
from rietx import Instrument
from rietx.backend.api import BACKEND_NAMES
from rietx.indexing import SYSTEM_ORDER, engine_descriptions, engine_names
from rietx.optimize.least_squares import SOLVERS
from rietx.report.schemas import TRAJECTORY_MAX_ACTIONS
from rietx.schemas.plan import PlanSpec
from rietx.strategy.staged import PLAN_PRESETS
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("agent-surface")


@pytest.fixture(scope="module")
def request_parts():
    structure, ins = perturbed_models()
    pattern = synthesize()
    return (structure.model_dump(mode="json"), ins.model_dump(mode="json"),
            pattern.model_dump(mode="json"))


@pytest.fixture(scope="module")
def refined(request_parts):
    """One converged single-pattern call, shared by every round-trip test.

    ``report_trajectory=True`` is explicit: the default flipped to False at
    the freeze (WP-1003, on WP-1064's pre-registered criterion), and this
    fixture is the trajectory-content test bed.
    """
    structure, instrument, pattern = request_parts
    out = ag.refine_json(dict(task="refine", structure=structure,
                              instrument=instrument, pattern=pattern,
                              report_trajectory=True))
    assert out["ok"] is True, out.get("error")
    return out


# ----------------------------------------------------------------------
# the success envelope
# ----------------------------------------------------------------------
def test_single_pattern_round_trip(refined):
    result = refined["result"]
    assert result["status"] == "converged"
    assert result["statistics"]["rwp"] < 0.10
    assert refined["series"] is None                 # exactly one of the two
    # strict JSON round-trip (no numpy scalars, no inf leaks)
    back = json.loads(json.dumps(refined))
    assert back["result"]["statistics"]["rwp"] == result["statistics"]["rwp"]


def test_result_carries_the_full_provenance(refined):
    prov = refined["result"]["provenance"]
    assert prov["backend"] == "numpy"
    assert prov["solver"] == "trf"                   # WP-0601 → WP-0602
    from rietx.report.schemas import THRESHOLDS_VERSION

    assert prov["report_thresholds_version"] == THRESHOLDS_VERSION


def test_report_attached_and_gated(refined):
    report = refined["report"]
    assert report is not None
    assert report["rwp"] == pytest.approx(refined["result"]["statistics"]["rwp"],
                                          rel=1e-6)
    # a converged synthetic fit is mature; the layers speak
    assert report["layer1_available"] is True


def test_trajectory_is_one_rung_per_stage_when_asked(refined):
    """WP-1058's shape, under WP-1003's default.

    A request that asks (the fixture passes ``report_trajectory=True``)
    carries the report at every stage boundary.  The default is now False —
    round 3's pre-registered criterion fired (WP-1064: rungs demonstrably
    read, decisions no better at more calls) — and the bare-request half of
    that flip is asserted in ``test_trajectory_declined_two_ways``.
    """
    trajectory = refined["trajectory"]
    plan = PLAN_PRESETS["mccusker_default"]()
    assert [r["stage"] for r in trajectory] == [s.name for s in plan.stages]
    # every rung is a state of the same run, ending where the result ended
    assert trajectory[-1]["rwp"] == pytest.approx(
        refined["result"]["statistics"]["rwp"], rel=1e-6)
    assert trajectory[0]["rwp"] > trajectory[-1]["rwp"]


def test_trajectory_declined_two_ways(request_parts):
    """The bare request carries no rungs (the WP-1003 default);
    ``include_report=False`` drops both halves — a caller who declines the
    report must not be handed one a rung at a time (it is what keeps a
    report-off A/B arm one)."""
    structure, instrument, pattern = request_parts
    core = dict(task="refine", structure=structure, instrument=instrument,
                pattern=pattern)

    bare = ag.refine_json(dict(core))
    assert bare["ok"], bare.get("error")
    assert bare["trajectory"] == [], "the default is off (WP-1064's criterion)"
    assert bare["report"] is not None

    for request in (dict(core, include_report=False),
                    dict(core, include_report=False, report_trajectory=True)):
        out = ag.refine_json(request)
        assert out["ok"], out.get("error")
        assert out["report"] is None
        assert out["trajectory"] == [], "include_report=False is the master switch"


def test_trajectory_does_not_move_the_answer(refined, request_parts):
    """Asking for rungs must not refine anything extra: the states are the
    ones the plan already passes through, so the fit lands in the same place.

    Bit-for-bit, not to a tolerance — a trajectory that perturbed the answer
    would make every report-on/report-off comparison compare two refinements
    instead of two deliveries.
    """
    structure, instrument, pattern = request_parts
    without = ag.refine_json(dict(task="refine", structure=structure,
                                  instrument=instrument, pattern=pattern,
                                  report_trajectory=False))
    assert without["ok"], without.get("error")
    assert (without["result"]["statistics"]["rwp"]
            == refined["result"]["statistics"]["rwp"])
    assert without["result"]["parameters"] == refined["result"]["parameters"]


def test_trajectory_payload_is_a_projection_not_five_reports(refined):
    """The documented budget (WP-1058): a rung is the statements, not the
    evidence — so the trajectory is a fraction of the report it ships beside,
    where five full FitReports would be several times it."""
    report_bytes = len(json.dumps(refined["report"]))
    rung_bytes = [len(json.dumps(r)) for r in refined["trajectory"]]
    assert max(rung_bytes) < 4000, rung_bytes
    assert sum(rung_bytes) < report_bytes, (sum(rung_bytes), report_bytes)
    # nothing is dropped silently: a capped rung says how many it left out
    for rung, size in zip(refined["trajectory"], rung_bytes, strict=True):
        assert len(rung["actions"]) <= TRAJECTORY_MAX_ACTIONS
        if rung["n_actions_omitted"]:
            assert len(rung["actions"]) == TRAJECTORY_MAX_ACTIONS, size


def test_history_off_by_default_and_on_by_path(refined, request_parts, tmp_path):
    assert refined["result"]["node_id"] is None
    assert refined["result"]["tree_id"] is None

    structure, instrument, pattern = request_parts
    path = tmp_path / "history.jsonl"
    out = ag.refine_json(dict(
        task="refine", structure=structure, instrument=instrument,
        pattern=pattern, history_path=str(path),
        plan={"stages": [{"name": "scale_bkg",
                          "turn_on": ["phases.*.scale",
                                      "instrument.background.*"]}]},
        include_report=False))
    assert out["ok"], out.get("error")
    assert out["result"]["node_id"] is not None      # persisted DAG
    assert out["report"] is None                     # opted out
    assert path.exists()


def test_custom_plan_spec_runs_and_reports_its_stage(request_parts):
    structure, instrument, pattern = request_parts
    out = ag.refine_json(dict(
        task="refine", structure=structure, instrument=instrument,
        pattern=pattern, include_report=False,
        plan={"stages": [{"name": "only_scale",
                          "turn_on": ["phases.*.scale"], "max_iter": 30}]}))
    assert out["ok"], out.get("error")
    assert [s["name"] for s in out["result"]["stages"]] == ["only_scale"]


def test_multi_task_declares_the_history_absence(request_parts):
    structure, instrument, pattern = request_parts
    second = Instrument.debye_scherrer(wavelength=0.4139)
    second.profile.w.value = instrument["profile"]["w"]["value"]
    out = ag.refine_json(dict(
        task="refine_multi", structure=structure,
        instruments=[instrument, second.model_dump(mode="json")],
        patterns=[pattern, pattern]))
    assert out["ok"], out.get("error")
    result = out["result"]
    assert len(result["histograms"]) == 2
    # the deliberate 0308 answer: no DAG for a joint fit, and no top-level
    # report (reports are per-histogram)
    assert result["node_id"] is None and result["tree_id"] is None
    assert out["report"] is None
    json.dumps(out)


def test_sequential_task_returns_a_series(request_parts):
    structure, instrument, pattern = request_parts
    out = ag.refine_json(dict(
        task="refine_sequential", structure=structure, instrument=instrument,
        patterns=[pattern, pattern], x=[300.0, 310.0], x_label="T (K)"))
    assert out["ok"], out.get("error")
    assert out["result"] is None                     # the other arm this time
    series = out["series"]
    assert [e["status"] for e in series["entries"]] == ["converged", "converged"]
    assert series["x_label"] == "T (K)"
    assert series["provenance"]["solver"] == "trf"
    json.dumps(out)


# ----------------------------------------------------------------------
# the failure envelope
# ----------------------------------------------------------------------
def test_invalid_request_names_the_fields():
    out = ag.refine_json({"task": "refine", "bogus": 1})
    assert out["ok"] is False
    err = out["error"]
    assert err["code"] == "INVALID_REQUEST"
    where = {d["where"] for d in err["details"]}
    # missing fields and the extra key are all named, as dot-paths without
    # the union-branch prefix
    assert {"structure", "instrument", "pattern", "bogus"} <= where
    types = {d["type"] for d in err["details"]}
    assert "extra_forbidden" in types                # strict schemas are the point


def test_missing_task_is_a_structured_error():
    out = ag.refine_json({})
    assert out["error"]["code"] == "INVALID_REQUEST"
    assert "task" in json.dumps(out["error"]["details"])


def test_non_dict_input_is_a_structured_error():
    out = ag.refine_json("refine")  # type: ignore[arg-type]
    assert out["ok"] is False
    assert out["error"]["code"] == "INVALID_REQUEST"


def test_a_preset_goes_straight_into_a_request(request_parts):
    """The friction item 15 actually names, closed end to end (WP-1110).

    ``PLAN_PRESETS`` hands back the dataclass and this request wants the
    pydantic mirror, and until WP-1110 the two did not cross: both mandated
    agents of round 1.0 took a preset, were answered ``INVALID_REQUEST``, and
    rebuilt the plan field by field.  Driven here rather than at the schema
    seam because the union ``str | PlanSpec`` is its own coercion path — a
    passing ``PlanSpec.model_validate`` says nothing about what the union
    does with the same input.

    The three spellings of one plan must give one answer, so the assertion is
    equality of the fit, not merely that the call was accepted.
    """
    structure, instrument, pattern = request_parts
    plan = PLAN_PRESETS["profile_only"]()

    answers = {}
    for label, spelling in [("dataclass", plan),
                            ("spec", PlanSpec.from_plan(plan)),
                            ("name", "profile_only")]:
        out = ag.refine_json(dict(task="refine", mode="lebail", plan=spelling,
                                  structure=structure, instrument=instrument,
                                  pattern=pattern))
        assert out["ok"], (label, out["error"])
        answers[label] = out["result"]["statistics"]["rwp"]

    assert len(set(answers.values())) == 1, answers


def test_a_request_holding_a_dataclass_plan_still_refuses_an_empty_one():
    """The crossing must not smuggle a plan past the request's own check.

    ``PlanSpec`` allows an empty stage list so it can read a history header
    written before the first stage ran; a request about to spend minutes on a
    plan that frees nothing is a mistake, and ``_known_plan`` is where that is
    caught.  A dataclass arriving by the new inbound path has to reach it.
    """
    from rietx.strategy.staged import RefinementPlan

    out = ag.refine_json(dict(task="refine", plan=RefinementPlan(stages=[]),
                              structure={}, instrument={}, pattern={}))
    assert out["error"]["code"] == "INVALID_REQUEST"
    detail = next(d for d in out["error"]["details"] if d["where"] == "plan")
    assert "must not be empty" in detail["message"]


@pytest.mark.parametrize("field,bad,registry", [
    ("backend", "cuda", BACKEND_NAMES),
    ("solver", "banana", SOLVERS),
    ("plan", "nope", tuple(sorted(PLAN_PRESETS))),
])
def test_unknown_registry_names_quote_the_live_registry(request_parts, field,
                                                        bad, registry):
    structure, instrument, pattern = request_parts
    out = ag.refine_json(dict(task="refine", structure=structure,
                              instrument=instrument, pattern=pattern,
                              **{field: bad}))
    assert out["error"]["code"] == "INVALID_REQUEST"
    detail = next(d for d in out["error"]["details"] if d["where"] == field)
    for name in registry:
        assert name in detail["message"]             # actionable: the live set


def test_cross_field_lengths_are_invalid_request(request_parts):
    structure, instrument, pattern = request_parts
    out = ag.refine_json(dict(task="refine_multi", structure=structure,
                              instruments=[instrument],
                              patterns=[pattern, pattern]))
    assert out["error"]["code"] == "INVALID_REQUEST"

    out = ag.refine_json(dict(task="refine_sequential", structure=structure,
                              instrument=instrument, patterns=[pattern],
                              x=[1.0, 2.0]))
    assert out["error"]["code"] == "INVALID_REQUEST"
    assert any("x has 2 entries" in d["message"] for d in out["error"]["details"])


def test_engine_exception_becomes_refinement_failed(request_parts):
    structure, instrument, pattern = request_parts
    out = ag.refine_json(dict(task="refine", structure=structure,
                              instrument=instrument, pattern=pattern,
                              two_theta_limits=(100.0, 120.0)))
    assert out["ok"] is False
    assert out["error"]["code"] == "REFINEMENT_FAILED"
    assert "fewer than" in out["error"]["message"]   # the engine's own words


def test_deep_validation_paths_point_into_nested_objects(request_parts):
    structure, instrument, pattern = request_parts
    bad = json.loads(json.dumps(pattern))
    bad["intensity"] = bad["intensity"][:-3]         # length mismatch
    out = ag.refine_json(dict(task="refine", structure=structure,
                              instrument=instrument, pattern=bad))
    assert out["error"]["code"] == "INVALID_REQUEST"
    assert any(d["where"].startswith("pattern") for d in out["error"]["details"])


def test_backend_unavailable_is_its_own_code(request_parts):
    """A valid name whose package is missing must not read as a typo.

    **Asserted against the condition, not against a mapping** (WP-1076). The
    version of this test before that WP monkeypatched `Refinement.__init__` to
    raise `NotImplementedError` and said so in its own docstring, so it pinned
    the exception-to-code arm and never the thing the code claims to mean —
    and the arm was wrong: `resolve_backend` raises `ImportError`, so a real
    missing jax came back `REFINEMENT_FAILED` for the whole life of the code.
    That is `_SURFACE_FLAGS` one rank over, in a test rather than a predicate.

    So the request here is a *real* one, made on whichever backend this venv
    genuinely lacks. On a `[dev,jax,torch]` venv there is none and the test
    skips, which is the honest outcome: the condition it asserts does not
    exist here.
    """
    unavailable = [c for c in rx.capabilities().backends if not c.available]
    if not unavailable:
        pytest.skip("every backend's dependency is importable in this venv")

    structure, instrument, pattern = request_parts
    for cap in unavailable:
        out = ag.refine_json(dict(task="refine", structure=structure,
                                  instrument=instrument, pattern=pattern,
                                  backend=cap.name))
        assert out["error"]["code"] == "BACKEND_UNAVAILABLE", cap.name
        assert cap.requires in out["error"]["message"]
        assert "backend='numpy'" in out["error"]["suggestion"]


def test_a_phase_free_model_is_its_own_code_not_a_failed_refinement(request_parts):
    """`NO_PHASES` is the fourth envelope code, and neither neighbour (WP-1207).

    The request is well-formed and the model is legal — a phase-free structure
    is a real thing to hold — so `INVALID_REQUEST` would send a consumer back to
    check its field spelling and `REFINEMENT_FAILED` would suggest the engine
    might succeed on a retry. Neither is true: what is missing is a cell, and
    the suggestion says where to get one.

    Every task that refines is covered, because each reaches the refusal
    through a different verb.
    """
    structure, instrument, pattern = request_parts
    empty = {"phases": []}

    out = ag.refine_json(dict(task="refine", structure=empty,
                              instrument=instrument, pattern=pattern))
    assert out["ok"] is False
    assert out["error"]["code"] == "NO_PHASES"
    assert "at least one phase" in out["error"]["message"]
    assert 'task="index"' in out["error"]["suggestion"]

    for request in (dict(task="refine_multi", structure=empty,
                         instruments=[instrument] * 2, patterns=[pattern] * 2),
                    dict(task="refine_sequential", structure=empty,
                         instrument=instrument, patterns=[pattern] * 2)):
        out = ag.refine_json(request)
        assert out["error"]["code"] == "NO_PHASES", request["task"]

    # …and the same model is fine to *hold*: only refining is refused, which is
    # what makes the code worth branching on
    assert rx.Structure(**empty).phases == []


def test_an_unsupported_feature_is_not_a_missing_backend(request_parts):
    """`NotImplementedError` means the engine refused, never "install jax".

    The other half of the same repair. `refine_json` used to map every
    `NotImplementedError` to `BACKEND_UNAVAILABLE`; the exception is in fact
    raised by unsupported *feature* paths, so a soft-restrained joint fit on
    `backend="numpy"` — a request with no optional dependency anywhere near it
    — came back advising an install of jax or torch.
    """
    from rietx.schemas.structure import ValueRestraint

    structure, instrument, pattern = request_parts
    restrained = copy.deepcopy(structure)
    restrained["phases"][0]["restraints"] = [
        ValueRestraint(path="phases.0.atoms.0.biso", target=0.5,
                       sigma=0.05).model_dump(mode="json")]

    out = ag.refine_json(dict(task="refine_multi", structure=restrained,
                              instruments=[instrument] * 2,
                              patterns=[pattern] * 2))
    assert out["error"]["code"] == "REFINEMENT_FAILED"
    assert "soft restraints" in out["error"]["message"]
    assert "install" not in out["error"]["suggestion"]


# ----------------------------------------------------------------------
# task="index" (WP-1024)
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def cubic_peaks_json():
    """A 23-line cubic peak list as plain JSON — enough lines to pass the gate.

    The σ is *declared*, and ``shift_allowance_deg`` is declared too in the request
    below: exact synthetic positions carry no systematic, so inheriting the
    engines' assumed allowance would test looseness rather than the surface (the
    declare-your-physics rule, DESIGN.md §Testing & validation policy).
    """
    import numpy as np

    from rietx import PeakList
    from rietx.crystallography.symmetry import generate_reflections

    lam = 1.5405929
    refl = generate_reflections("P m -3 m", (4.1566,) * 3 + (90.0,) * 3, lam,
                                140.0)
    tt = np.degrees(2.0 * np.arcsin(lam / (2.0 * np.asarray(refl.d))))
    return PeakList.from_positions(np.sort(tt), lam,
                                   two_theta_esd=0.005).model_dump(mode="json")


@pytest.fixture(scope="module")
def indexed(cubic_peaks_json):
    out = ag.refine_json({
        "task": "index", "peaks": cubic_peaks_json,
        "search": {"systems": ["cubic"], "max_d_axis": 12.0,
                   "max_volume": 1500.0, "shift_allowance_deg": 1e-9,
                   "budget_seconds": 60.0}})
    assert out["ok"] is True, out.get("error")
    return out


def test_index_answers_in_its_own_arm(indexed):
    """Three answer arms, and which one is set says what ran.

    ``indexing`` rather than ``result`` because an ``IndexingResult`` is a
    different kind of answer — most importantly it has **no single cell**, and
    coercing it into the refinement arm would have to invent one.
    """
    assert indexed["result"] is None and indexed["series"] is None
    idx = indexed["indexing"]
    assert idx["engines_run"] == list(engine_names())
    assert idx["systems_searched"] == ["cubic"]
    assert idx["candidates"], "the cubic truth should be found"


def test_index_answer_carries_no_singleton_field(indexed):
    """The API-shape rule survives serialisation: there is no ``cell`` key.

    The envelope is where a confident wrong singleton would be easiest to
    reintroduce — a convenience field for the agent's benefit — so it is asserted
    on the JSON rather than only on the python object.
    """
    idx = indexed["indexing"]
    for forbidden in ("cell", "best", "solution"):
        assert forbidden not in idx


def test_index_answer_carries_the_evidence_view(indexed):
    """WP-1043: the gate's inputs reach the JSON consumer, kinds included.

    The refuting/capping split used to live only in ``INDEX_REFUTING_CAVEATS``,
    a package constant no JSON reader can see; the ``evidence`` arm is that
    judgement's inputs serialized — computed from the answer beside it at
    dispatch time, so the two arms cannot disagree."""
    ev = indexed["evidence"]
    assert ev is not None
    idx = indexed["indexing"]
    assert len(ev["candidates"]) == len(idx["candidates"])
    top = ev["candidates"][0]
    assert top["index"] == 0
    assert top["caveats"] == [{"name": "not_validated", "kind": "capping"}]
    # this list clears the scoring bar: the full panel ranked, nothing absent
    assert ev["fom_undefined"] == {}
    assert "m20" in ev["fom_ranked"]
    assert set(top["fom"]) == set(ev["fom_ranked"])
    # no whole-profile fit ran (peaks only): absent for cause, never zero
    assert top["validated"] is False and top["lebail_rwp"] is None
    # and the API-shape rule holds here too: no singleton key
    for forbidden in ("cell", "best", "solution"):
        assert forbidden not in ev


def test_index_reports_the_truth_ranked_first_and_qualified(indexed):
    top = indexed["indexing"]["candidates"][0]
    assert top["system"] == "cubic" and top["centring"] == "P"
    assert top["cell"][0] == pytest.approx(4.1566, abs=2e-3)
    # both engines agree, but no pattern was supplied, so the whole-profile test
    # did not run and the answer caps at medium *by declaration*
    assert sorted(top["found_by"]) == sorted(engine_names())
    assert top["confidence"] == "medium"
    assert top["confidence_caveats"] == ["not_validated"]
    codes = {d["code"] for d in indexed["indexing"]["diagnostics"]}
    assert {"INDEX_NOT_VALIDATED", "INDEX_SYSTEMS_NOT_COVERED"} <= codes


def test_unknown_engine_quotes_the_live_registry(cubic_peaks_json):
    out = ag.refine_json({"task": "index", "peaks": cubic_peaks_json,
                          "engines": ["montecarlo"]})
    assert out["error"]["code"] == "INVALID_REQUEST"
    detail = next(d for d in out["error"]["details"]
                  if d["where"].startswith("engines"))
    for name in engine_names():
        assert name in detail["message"]


def test_index_without_peaks_or_a_pattern_is_an_invalid_request():
    out = ag.refine_json({"task": "index"})
    assert out["error"]["code"] == "INVALID_REQUEST"
    assert any("pattern + instrument" in d["message"]
               for d in out["error"]["details"])


def test_unknown_crystal_system_quotes_the_live_order(cubic_peaks_json):
    out = ag.refine_json({"task": "index", "peaks": cubic_peaks_json,
                          "search": {"systems": ["rhombic"]}})
    assert out["error"]["code"] == "INVALID_REQUEST"
    detail = next(d for d in out["error"]["details"]
                  if d["where"].startswith("search.systems"))
    for name in SYSTEM_ORDER:
        assert name in detail["message"]


# ----------------------------------------------------------------------
# schema export for tool-calling
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# task="suggest" — the first no-solve task (WP-1050)
# ----------------------------------------------------------------------
def test_suggest_answers_in_its_own_arm(request_parts):
    structure, instrument, pattern = request_parts
    out = ag.refine_json(dict(task="suggest", structure=structure,
                              instrument=instrument, pattern=pattern))
    assert out["ok"] is True, out.get("error")
    assert (out["result"] is None and out["series"] is None
            and out["indexing"] is None)
    sug = out["suggestion"]
    assert sug["n_evaluated"] > 0
    assert sug["noise_floor"] >= 9.0 * max(sug["chi2_red"], 1.0) * 0.999
    for group in sug["groups"]:
        assert group["resolved"] == (len(group["members"]) == 1)


def test_suggest_refuses_solver_and_plan(request_parts):
    """The no-solve task has no solver/plan; extra='forbid' names them."""
    structure, instrument, pattern = request_parts
    out = ag.refine_json(dict(task="suggest", structure=structure,
                              instrument=instrument, pattern=pattern,
                              solver="lm", plan="mccusker_default"))
    assert out["ok"] is False
    assert out["error"]["code"] == "INVALID_REQUEST"
    wheres = {d["where"] for d in out["error"]["details"]}
    assert {"solver", "plan"} <= wheres


def test_request_schema_is_a_discriminated_union():
    schema = ag.request_schema()
    assert schema["discriminator"]["propertyName"] == "task"
    assert len(schema["oneOf"]) == len(ag._TASK_TAGS) == 5


def test_schemas_quote_every_live_registry_member():
    """A new backend/solver/plan/**engine** cannot ship invisible to the tool
    schema.

    The descriptions are built from the registries at import, so this is the
    meta-test that keeps them honest (the WP-0408 lesson: the fourth backend
    name arrived two days after the third).  The indexing engines joined in
    WP-1024, and for them it is not only a documentation question: ``high``
    confidence *means* every engine that ran agreed, so an engine an agent cannot
    see is one it cannot ask for and therefore a confidence ceiling it cannot
    reach.
    """
    text = json.dumps(ag.request_schema())
    from rietx.indexing import SEARCH_PRESETS

    for name in (*BACKEND_NAMES, *SOLVERS, *PLAN_PRESETS, *engine_names(),
                 *SYSTEM_ORDER, *SEARCH_PRESETS):
        assert name in text, f"{name!r} missing from the exported schema"


def test_every_engine_description_reaches_the_schema():
    """Registration carries a one-line description precisely so the schema can
    quote it; a name without its purpose is not usable by a chooser."""
    text = json.dumps(ag.request_schema())
    for name, desc in engine_descriptions().items():
        assert name in text
        # the first clause is enough: the full sentence is re-wrapped in the
        # description string, so pinning it verbatim would pin the formatting
        assert desc.split(",")[0].split(";")[0] in text, name


def test_response_schema_covers_every_answer_arm():
    text = json.dumps(ag.response_schema())
    for code in ag.ERROR_CODES:
        assert code in text
    for arm in ("SeriesResult", "RefinementResult", "IndexingResult",
                "SuggestionResult"):
        assert arm in text, arm
    # the companions that ride beside an arm rather than being one (WP-1043,
    # WP-1058): a consumer that cannot see their shape cannot read them
    for companion in ("IndexingEvidence", "FitReport", "StageReport"):
        assert companion in text, companion


def test_tool_definition_shape():
    tool = ag.tool_definition()
    assert set(tool) == {"name", "description", "input_schema"}
    assert tool["name"] == "rietx_refine"
    assert "diagnostics" in tool["description"]      # the protocol pointer
    assert tool["input_schema"] == ag.request_schema()
    json.dumps(tool)                                 # registrable as-is
