"""How rietx objects read when printed or shown in a notebook (WP-1544).

The regression pinned here is size: a pattern's repr was 1.4 MB and a result's
0.8 MB, and pydantic's ``__str__`` is its repr, so ``print`` was no escape. The
ceilings sit well above what the objects print now, so they fail on a sequence
leaking back in, not on a reworded line.

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


def test_a_schema_prints_as_a_tree_with_one_line_per_parameter(fap):
    text = str(fap["instrument"])
    assert text.startswith("Instrument\n")
    assert "  zero_shift: 0 deg 2θ" in text.splitlines()
    assert "None" not in text, "a None field says nothing and is left out"


def test_a_free_parameter_is_marked_and_carries_its_esd(fap):
    from rietx._display import parameter_text
    from rietx.schemas.common import Parameter
    a = fap["result"].parameter("phases.0.cell.a")
    text = parameter_text(Parameter(value=a.value, stderr=a.stderr, vary=True, unit="A"))
    assert text.endswith(" Å (vary)") and "(" in text.split()[0]


def test_diagnostics_print_every_field_in_reading_order(fap):
    from rietx.background.diagnostics import PatternDiagnostics
    order = PatternDiagnostics._READING_ORDER
    fields = set(PatternDiagnostics.model_fields) - {"n_points", "two_theta_min",
                                                     "two_theta_max"}
    assert sorted(order) == sorted(fields), "every field once, the range in the head"
    lines = str(rx.diagnose(fap["data"], wavelength=1.5406)).splitlines()
    assert lines[1] == "  signal_cutoffs: none", "an empty finding is printed, first"
    assert [ln.split(":")[0].strip() for ln in lines[1:]] == list(order)


def test_a_pattern_prints_its_sigma_even_when_absent(fap):
    lines = str(fap["data"]).splitlines()
    assert lines[0].startswith("PatternData of 5753 points, 15–130.04° 2θ")
    assert "  sigma: None" in lines


def test_a_parameter_row_prints_on_one_line(fap):
    rows = fap["ref"].parameters()
    assert all("\n" not in str(row) for row in rows)
    tied = next(r for r in rows if r.path == "phases.0.cell.b")
    assert str(tied).endswith("tied = 1·phases.0.cell.a")


def test_displaying_a_refinement_runs_nothing(fap, monkeypatch):
    """IPython builds text/plain and text/html for every displayed value, so a
    view that called ``summary()`` would build a report, and a report's layer
    2 runs rival fits, twice per cell."""
    ref = fap["ref"]

    def refuse(*a, **k):
        raise AssertionError("a display computed a fit or a report")
    for name in ("fit", "report", "summary"):
        monkeypatch.setattr(type(ref), name, refuse)
    text = str(ref)
    html = ref._repr_html_()
    assert "last fit: converged" in text
    assert "<table>" in html and "phases.0.cell.a" in html


def test_html_is_escaped_and_carries_no_style(fap):
    from rietx._display import table_html
    html = table_html(("path", "value"), [("<script>", "a & b")], caption="<x>")
    assert "<script>" not in html and "&lt;script&gt;" in html and "a &amp; b" in html
    html = fap["ref"]._repr_html_()
    assert "style" not in html and "<script" not in html


def test_a_tree_prints_its_summary(fap):
    tree = fap["ref"].history
    assert str(tree) == tree.summary()


def test_a_structure_figure_shows_its_picture(fap):
    fig = rx.viz.render_structure(fap["structure"], size=120)
    assert fig._repr_png_().startswith(b"\x89PNG\r\n\x1a\n")
    assert len(repr(fig)) < 100


@pytest.mark.parametrize("name", ["data", "instrument", "structure", "result", "ref"])
def test_ipython_text_plain_stays_short(fap, name):
    """What a notebook *stores*: text/plain is saved beside any HTML, so a
    long repr fills the .ipynb even where the HTML is what shows."""
    formatters = pytest.importorskip("IPython.core.formatters")
    bundle, _ = formatters.DisplayFormatter().format(fap[name])
    assert len(bundle["text/plain"]) < 10_000
    assert "two_theta=" not in bundle["text/plain"], "the str view, not pydantic's repr"
