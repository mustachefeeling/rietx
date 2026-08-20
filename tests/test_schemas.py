import copy
import dataclasses
import inspect
import math

import pytest
from pydantic import ValidationError

import rietx as rx
from rietx import Instrument, Parameter, PatternData, Structure
from rietx.schemas import Atom, Cell, Phase


def make_lab6() -> Structure:
    return Structure(phases=[Phase(
        name="LaB6",
        space_group="P m -3 m",
        cell=Cell.cubic(4.1566, vary=True),
        atoms=[
            Atom(label="La", species="La", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="B", species="B", x=Parameter(value=0.1993),
                 y=Parameter(value=0.5), z=Parameter(value=0.5)),
        ],
    )])


def test_parameter_bounds_validated():
    with pytest.raises(ValidationError):
        Parameter(value=2.0, min=0.0, max=1.0)
    with pytest.raises(ValidationError):
        Parameter(value=0.5, min=1.0, max=0.0)


def test_parameter_expr_reserved():
    with pytest.raises(ValidationError):
        Parameter(value=1.0, expr="2*a")


def test_unknown_field_rejected():
    with pytest.raises(ValidationError) as err:
        Parameter(value=1.0, vry=True)  # typo
    assert "vry" in str(err.value)


def test_structure_json_round_trip():
    s = make_lab6()
    s2 = Structure.model_validate_json(s.model_dump_json())
    assert s2 == s


def test_instrument_json_round_trip():
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins2 = Instrument.model_validate_json(ins.model_dump_json())
    assert ins2 == ins
    assert math.isclose(ins2.source.primary_wavelength, 0.4139)


def test_pattern_validation():
    with pytest.raises(ValidationError):
        PatternData(two_theta=[1.0, 0.5], intensity=[1.0, 2.0])  # not increasing
    with pytest.raises(ValidationError):
        PatternData(two_theta=[1.0, 2.0], intensity=[1.0])  # length mismatch
    p = PatternData(two_theta=[1.0, 2.0, 3.0], intensity=[4.0, 9.0, 16.0])
    assert p.sig().tolist() == [2.0, 3.0, 4.0]  # Poisson fallback


# ------------------------------------------------------- the one plan schema
def test_stage_spec_mirrors_every_stage_field():
    """StageSpec must carry every field of the dataclass it mirrors.

    The mirror lost data before WP-1004: ``strain_seed`` existed on ``Stage``
    and on the agent surface's copy of this schema but not on the history one,
    so a Stephens stage round-tripped through a history tree with its seed
    reset to 0.  A field-set assertion is the guard that makes the next added
    ``Stage`` field fail loudly instead of silently failing to serialize.
    """
    import dataclasses

    from rietx.schemas.plan import StageSpec

    assert set(StageSpec.model_fields) == {f.name for f in dataclasses.fields(rx.Stage)}


def test_stage_spec_round_trips_strain_seed():
    from rietx.schemas.plan import StageSpec

    stage = rx.Stage("sample_broadening", ["phases.*.microstrain.dof.*"],
                     seed=1e-3, strain_seed=1000.0)
    back = StageSpec.model_validate_json(
        StageSpec.from_stage(stage).model_dump_json()).to_stage()
    assert back == stage


def test_the_mirror_is_crossed_in_both_directions():
    """A plan and its mirror are interchangeable at every surface (WP-1110 item 15).

    ``PLAN_PRESETS`` hands back the dataclass; a request, a project file and a
    history header hold the pydantic mirror.  Before this the crossing existed
    nowhere, so a caller had to know which of two same-shaped types each
    surface wanted — two agents on the trigger dataset took a preset, were
    answered ``INVALID_REQUEST``, and rebuilt it field by field.
    """
    from rietx.schemas.plan import PlanSpec, StageSpec
    from rietx.strategy.staged import resolve_plan

    plan = rx.PLAN_PRESETS["mccusker_default"]()
    spec = PlanSpec.from_plan(plan)

    # inbound: the dataclass validates as its mirror, at both ranks
    assert PlanSpec.model_validate(plan) == spec
    assert StageSpec.model_validate(plan.stages[0]) == spec.stages[0]
    # outbound: the mirror resolves to the dataclass
    assert resolve_plan(spec, "rietveld") == plan
    # and a name still resolves through the mode mapping it always did
    assert resolve_plan("mccusker_default", "lebail") == rx.RefinementPlan.profile_only()


def test_the_crossing_is_by_type_not_by_shape():
    """`.stages` is not evidence: the two types share every field name.

    Which is exactly what let a ``PlanSpec`` run through ``fit(plan=...)``
    undeclared before WP-1110 — it fitted, bit-identically, because a plan is
    only ever read.  A duck-typed crossing would certify that accident, so
    both validators test ``isinstance`` against the real class.
    """
    from rietx.schemas.plan import PlanSpec

    assert {f.name for f in dataclasses.fields(rx.RefinementPlan)} == set(
        PlanSpec.model_fields)

    class LooksLikeAPlan:
        stages = []
        correlation_guard = 0.98

    with pytest.raises(ValidationError):
        PlanSpec.model_validate(LooksLikeAPlan())


def test_a_preset_is_the_builder_and_says_so():
    """``PLAN_PRESETS[name]`` builds a plan; asking it for one names the call.

    The registry stores builders on purpose — a plan is a mutable dataclass, so
    a shared instance would carry one caller's edit to the next — and the cost
    was ``'function' object has no attribute 'stages'`` (WP-1110 item 4), which
    names neither the registry nor the call.
    """
    factory = rx.PLAN_PRESETS["mccusker_default"]

    with pytest.raises(AttributeError, match=r"PLAN_PRESETS\['mccusker_default'\]\(\)"):
        factory.stages
    assert factory() is not factory(), "a preset must not hand out a shared plan"

    # every preset, not one: the wrapper is what stands between the registry
    # and the plan that every fit in the package runs, so the claim it builds
    # exactly what the classmethod builds is checked across the whole registry
    for name in rx.PLAN_PRESETS:
        assert rx.PLAN_PRESETS[name]() == getattr(rx.RefinementPlan, name)()
    # ``functools.update_wrapper``: an agent reading help() must reach the
    # builder, not the wrapper — the round measured one leave for the source
    # over exactly this.
    assert factory.__name__ == "mccusker_default"
    assert inspect.getdoc(factory) == inspect.getdoc(rx.RefinementPlan.mccusker_default)


@pytest.mark.parametrize("obj, mirror", [
    (rx.RefinementPlan.mccusker_default(), "PlanSpec.from_plan"),
    (rx.Stage("cell", ["phases.*.cell.*"]), "StageSpec.from_stage"),
])
def test_asking_a_plan_dataclass_for_pydantic_names_the_mirror(obj, mirror):
    """These two are the only non-pydantic objects a caller handles here.

    So ``.model_dump()`` is the natural next keystroke, and the bare
    ``'Stage' object has no attribute 'model_dump'`` says nothing about where
    serialization lives.  An error message is the documentation an agent reads.
    """
    with pytest.raises(AttributeError, match=mirror):
        obj.model_dump()
    # everything else still raises the ordinary way, so hasattr and copy are
    # unchanged
    with pytest.raises(AttributeError):
        obj.no_such_attribute
    assert copy.deepcopy(obj) == obj


def test_plan_spec_is_one_class_everywhere():
    """History and the agent surface must not re-acquire private copies.

    The compat re-exports went pre-freeze (WP-1003): ``StageSpec`` is spelled
    only ``schemas.plan.StageSpec``, and its *absence* from the two old homes
    is the guard — a re-acquired private copy would make the attribute exist.
    ``PlanSpec`` stays imported in both because both use it, and it must be
    the one class.
    """
    from rietx import agent
    from rietx.schemas import history, plan

    assert history.PlanSpec is plan.PlanSpec is agent.PlanSpec
    assert not hasattr(history, "StageSpec")
    assert not hasattr(agent, "StageSpec")


def test_plan_spec_reads_a_pre_v1_history_header():
    """A tree written before ``strain_seed`` existed still validates.

    Vendored header line from a v0.6 history JSONL (schema_version 0.1), whose
    stage specs have no ``strain_seed`` key at all.
    """
    from rietx.schemas.history import HistoryRecord

    line = (
        '{"record":"header","header":{"tree_id":"t0","created_utc":'
        '"2026-07-28T10:00:00Z","data_fingerprint":"abc","data_source":"",'
        '"n_points":100,"plan":{"stages":[{"name":"scale_bkg","turn_on":'
        '["phases.*.scale"],"max_iter":100,"lebail_cycles":3,"seed":0.0},'
        '{"name":"cell","turn_on":["phases.*.cell.*"],"max_iter":100,'
        '"lebail_cycles":3,"seed":0.0}],"correlation_guard":0.98},'
        '"package_version":"0.6.0.dev0","schema_version":"0.1"}}'
    )
    rec = HistoryRecord.model_validate_json(line)
    assert rec.header is not None
    assert [s.name for s in rec.header.plan.stages] == ["scale_bkg", "cell"]
    assert all(s.strain_seed == 0.0 for s in rec.header.plan.stages)
