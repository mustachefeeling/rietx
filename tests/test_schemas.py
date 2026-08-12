import math

import pytest
from pydantic import ValidationError

import anatase as pr
from anatase import Instrument, Parameter, PatternData, Structure
from anatase.schemas import Atom, Cell, Phase


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

    from anatase.schemas.plan import StageSpec

    assert set(StageSpec.model_fields) == {f.name for f in dataclasses.fields(pr.Stage)}


def test_stage_spec_round_trips_strain_seed():
    from anatase.schemas.plan import StageSpec

    stage = pr.Stage("sample_broadening", ["phases.*.microstrain.dof.*"],
                     seed=1e-3, strain_seed=1000.0)
    back = StageSpec.model_validate_json(
        StageSpec.from_stage(stage).model_dump_json()).to_stage()
    assert back == stage


def test_plan_spec_is_one_class_everywhere():
    """History and the agent surface must not re-acquire private copies."""
    from anatase import agent
    from anatase.schemas import history, plan

    assert history.StageSpec is plan.StageSpec is agent.StageSpec
    assert history.PlanSpec is plan.PlanSpec is agent.PlanSpec


def test_plan_spec_reads_a_pre_v1_history_header():
    """A tree written before ``strain_seed`` existed still validates.

    Vendored header line from a v0.6 history JSONL (schema_version 0.1), whose
    stage specs have no ``strain_seed`` key at all.
    """
    from anatase.schemas.history import HistoryRecord

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
