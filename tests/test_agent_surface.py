"""The single-call JSON surface: ``agent.refine_json(dict) → dict`` (WP-0602).

Everything here goes through plain dicts and back — the point of the surface
is that an agent never touches a python object.  One synthetic single-pattern
fit is shared module-wide (hence the xdist group pinning this module to one
worker); the validation and schema tests cost nothing.
"""

from __future__ import annotations

import json

import pytest

import pxrdref.agent as ag
from pxrdref import Instrument
from pxrdref.backend.api import BACKEND_NAMES
from pxrdref.optimize.least_squares import SOLVERS
from pxrdref.strategy.staged import PLAN_PRESETS
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
    """One converged single-pattern call, shared by every round-trip test."""
    structure, instrument, pattern = request_parts
    out = ag.refine_json(dict(task="refine", structure=structure,
                              instrument=instrument, pattern=pattern))
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
    from pxrdref.report.schemas import THRESHOLDS_VERSION

    assert prov["report_thresholds_version"] == THRESHOLDS_VERSION


def test_report_attached_and_gated(refined):
    report = refined["report"]
    assert report is not None
    assert report["rwp"] == pytest.approx(refined["result"]["statistics"]["rwp"],
                                          rel=1e-6)
    # a converged synthetic fit is mature; the layers speak
    assert report["layer1_available"] is True


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


def test_backend_unavailable_is_its_own_code(request_parts, monkeypatch):
    """A valid name whose package is missing must not read as a typo.

    Forced via the constructor's fail-fast path rather than uninstalling
    jax: what matters is the NotImplementedError → BACKEND_UNAVAILABLE
    mapping, which is the same whichever backend is absent.
    """
    import sys

    def unavailable(self, *a, **kw):
        raise NotImplementedError(
            "backend 'jax' needs the optional dependency: pip install "
            "'pxrd-refine[jax]'")

    # sys.modules, because the package attribute `pxrdref.refine` is the
    # *function* re-exported by __init__, shadowing the module of that name
    refine_mod = sys.modules["pxrdref.refine"]
    monkeypatch.setattr(refine_mod.Refinement, "__init__", unavailable)
    structure, instrument, pattern = request_parts
    out = ag.refine_json(dict(task="refine", structure=structure,
                              instrument=instrument, pattern=pattern,
                              backend="jax"))
    assert out["error"]["code"] == "BACKEND_UNAVAILABLE"
    assert "pxrd-refine[jax]" in out["error"]["message"]


# ----------------------------------------------------------------------
# schema export for tool-calling
# ----------------------------------------------------------------------
def test_request_schema_is_a_discriminated_union():
    schema = ag.request_schema()
    assert schema["discriminator"]["propertyName"] == "task"
    assert len(schema["oneOf"]) == 3


def test_schemas_quote_every_live_registry_member():
    """A new backend/solver/plan cannot ship invisible to the tool schema.

    The descriptions are built from the registries at import, so this is the
    meta-test that keeps them honest (the WP-0408 lesson: the fourth backend
    name arrived two days after the third).
    """
    text = json.dumps(ag.request_schema())
    for name in (*BACKEND_NAMES, *SOLVERS, *PLAN_PRESETS):
        assert name in text, f"{name!r} missing from the exported schema"


def test_response_schema_covers_both_envelopes():
    text = json.dumps(ag.response_schema())
    for code in ag.ERROR_CODES:
        assert code in text
    assert "SeriesResult" in text and "RefinementResult" in text


def test_tool_definition_shape():
    tool = ag.tool_definition()
    assert set(tool) == {"name", "description", "input_schema"}
    assert tool["name"] == "pxrdref_refine"
    assert "diagnostics" in tool["description"]      # the protocol pointer
    assert tool["input_schema"] == ag.request_schema()
    json.dumps(tool)                                 # registrable as-is
