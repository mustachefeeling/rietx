import math

import pytest
from pydantic import ValidationError

from pxrdref import Instrument, Parameter, PatternData, Structure
from pxrdref.schemas import Atom, Cell, Phase


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
