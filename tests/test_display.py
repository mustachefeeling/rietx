"""How rietx objects read when printed or shown in a notebook (WP-1544).

The regression pinned here is size: a pattern's repr was 1.4 MB and a result's
0.8 MB, and pydantic's ``__str__`` is its repr, so ``print`` was no escape. The
ceilings are an order of magnitude above what the objects print now, so they
fail on a sequence leaking back in, not on a reworded line.

One FAP fit is shared by the module, so it sits on one xdist worker.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx
from rietx._display import summarise

DATA = Path(__file__).parent / "data"

pytestmark = pytest.mark.xdist_group("display")


@pytest.fixture(scope="module")
def fap():
    data = rx.read_pattern(DATA / "FAP.XRA")
    structure = rx.Structure.from_cif(str(DATA / "fluorapatite.cif"))
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    instrument.background = rx.BackgroundChebyshev.with_terms(6)
    ref = rx.Refinement(structure, instrument)
    result = ref.fit(data, plan="mccusker_default", two_theta_limits=(15, 130))
    return {"data": data, "structure": structure, "instrument": instrument,
            "ref": ref, "result": result}


@pytest.mark.parametrize("name, ceiling", [
    ("data", 1_000), ("instrument", 6_000), ("structure", 12_000),
    ("result", 30_000)])
def test_repr_and_str_stay_short(fap, name, ceiling):
    obj = fap[name]
    assert len(repr(obj)) < ceiling, f"repr({name}) is {len(repr(obj))} chars"
    assert len(str(obj)) < ceiling, f"str({name}) is {len(str(obj))} chars"


def test_a_pattern_repr_keeps_its_range_not_its_channels(fap):
    text = repr(fap["data"])
    n = len(fap["data"].two_theta)
    assert f"two_theta=<{n} floats 15…130.04>" in text


def test_summarise_walks_dicts_and_short_sequences():
    ticks = {"phase": [float(x) for x in range(100)]}
    assert repr(summarise(ticks)) == "{'phase': <100 floats 0…99>}"
    assert summarise([1.0, 2.0]) == [1.0, 2.0]
    assert repr(summarise([[1.0, 2.0]] * 20)) == "<20 lists>"
    assert repr(summarise(["a"] * 9)) == "<9 strings>"
