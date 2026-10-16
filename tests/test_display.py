"""How rietx objects read when printed or shown in a notebook (WP-1544).

The regression pinned here is size: a pattern's repr was 1.4 MB and a result's
0.8 MB, and pydantic's ``__str__`` is its repr, so ``print`` was no escape. The
ceilings sit well above what the objects print now, so they fail on a sequence
leaking back in, not on a reworded line.

One FAP fit is shared by the module, so it sits on one xdist worker.
"""
from __future__ import annotations

import os
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
    data, md = fig._repr_png_()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    # the width alone, or a column narrower than the figure squashes it (WP-1957)
    assert md == {"width": fig.image.shape[1] // 2}
    import io

    from PIL import Image
    assert Image.open(io.BytesIO(data)).mode == "P"  # a notebook palette, like a fit figure
    from rietx.viz import plots
    from rietx.viz.figure3d import render
    assert render.NOTEBOOK_COLOURS == plots._NOTEBOOK_COLOURS  # restated across the boundary
    assert render.NOTEBOOK_DARK_GROUND == plots.PALETTES["dark"]["ground"]  # likewise
    clear = rx.viz.render_structure(fap["structure"], size=120, background=None)
    assert Image.open(io.BytesIO(clear._repr_png_()[0])).mode == "RGBA"  # its alpha kept
    assert len(repr(fig)) < 100


def test_a_structure_figure_carries_a_dark_copy_drawn_from_what_it_was(fap):
    """WP-1970: on the default white ground the figure's notebook output
    carries the pair, the dark one drawn again from the recipe on the dark
    page's ground.  It is drawn from a copy taken at the call, so a structure
    edited afterwards cannot make the two pictures differ.  A figure on any
    other ground was the caller's choice, and shows alone."""
    import base64
    import re

    from rietx.viz.plots import PALETTES

    structure = fap["structure"].model_copy(deep=True)
    fig = rx.viz.render_structure(structure, size=120)
    dark = rx.viz.render_structure(structure, **{
        **fig.recipe, "background": PALETTES["dark"]["ground"]})
    structure.phases[0].cell.a.value *= 1.2
    bundle, metadata = fig._repr_mimebundle_()
    assert bundle["image/png"] == fig._repr_png_()[0]
    assert metadata == {"image/png": fig._repr_png_()[1]}
    light_img, dark_img = re.findall(r"<img [^>]*>", bundle["text/html"])
    assert "display:none" in dark_img and "display:none" not in light_img
    assert (re.search(r'base64,([^"]+)"', dark_img).group(1)
            == base64.b64encode(dark._repr_png_()[0]).decode())
    for ground in ("black", None, "#ffeedd"):
        alone = rx.viz.render_structure(structure, size=120, background=ground)
        assert list(alone._repr_mimebundle_()[0]) == ["image/png"]


def test_a_result_html_is_its_text_and_its_parameter_table(fap):
    result = fap["result"]
    html = result._repr_html_()
    assert html.startswith("<pre>RefinementResult: ")
    assert html.count("<tr>") == 1 + len(result.parameters)


def test_an_indexing_result_prints_its_candidates_and_verdict():
    from rietx.schemas.common import Provenance
    from rietx.schemas.indexing import CellCandidate, IndexingResult
    cand = CellCandidate(cell=(5.43, 5.43, 5.43, 90, 90, 90), cell_esd=(1e-4,) * 3 + (0,) * 3,
                         system="cubic")
    res = IndexingResult(candidates=[cand], engines_run=["svd"], systems_searched=["cubic"],
                         provenance=Provenance(package_version="test",
                                               created_utc="2026-10-07T00:00:00Z"))
    text = str(res)
    assert text.splitlines()[0].startswith("engines: svd   systems: cubic")
    assert "5.43000 5.43000 5.43000 Å" in text and "NO CELL" in text
    html = res._repr_html_()
    assert html.count("<tr>") == 2 and "5.43000 5.43000 5.43000" in html
    assert "NO CELL" in html and "found by" not in html, "the table replaces the lines"


def test_a_peak_list_prints_one_row_per_peak():
    """The generic tree spent fourteen lines a peak (WP-1545's notebook 03)."""
    from rietx.schemas.indexing import PeakList
    peaks = PeakList.from_positions([21.07, 26.22, 27.22], 1.5406)
    text = str(peaks)
    lines = text.splitlines()
    assert lines[0].startswith("PeakList: 3 peaks, 3 usable")
    assert len(lines) == 2 + 3 and "26.2200" in lines[3]
    html = peaks._repr_html_()
    assert html.count("<tr>") == 4 and "26.2200" in html


def test_a_diagnostic_prints_its_headline_and_folds_the_rest():
    """The text form is rustc's; the HTML shows the headline and folds the
    suggestion, the paths and the code's explanation (WP-1985)."""
    from rietx._display import diagnostics_html
    from rietx.help import explain
    from rietx.schemas.common import Diagnostic
    d = Diagnostic(level="warning", code="BOUND_HIT", message="a refined to its upper bound",
                   where=["phases.0.cell.a"], suggestion="check the tie")
    assert str(d).splitlines() == ["warning[BOUND_HIT]: a refined to its upper bound",
                                   "  at: phases.0.cell.a", "  help: check the tie"]
    html = diagnostics_html([d], context="candidate cubic P")
    head, fold = html.split("</summary>")
    assert head == "<details><summary>warning[BOUND_HIT]: a refined to its upper bound"
    assert fold.index("on: candidate") < fold.index("at: phases") < fold.index("help: check")
    assert explain("BOUND_HIT").description in fold
    unknown = Diagnostic(level="info", code="NOT_A_CODE_HERE", message="from another version")
    assert unknown.explanation is None and "<p>" not in diagnostics_html([unknown])


def test_pre_fit_ticks_are_where_the_fit_puts_its_own(fap):
    """One answer to where a tick goes: drawn from the fitted refinement, the
    pre-fit rows are the result's own ticks over the same range."""
    import numpy as np

    from rietx.viz.plots import _model_ticks
    drawn = _model_ticks(fap["ref"], fap["data"])
    (name, own), = fap["result"].ticks.items()
    lo, hi = fap["result"].two_theta[0], fap["result"].two_theta[-1]
    pos = np.asarray(drawn[name])
    pos = pos[(pos >= lo) & (pos <= hi)]
    own = np.asarray(own)
    own = own[(own >= lo) & (own <= hi)]
    assert pos.size == own.size and np.allclose(pos, own, atol=1e-5)


def test_pre_fit_ticks_draw_one_row_per_phase_and_need_a_linear_axis(fap):
    pytest.importorskip("matplotlib")
    ref = rx.Refinement(fap["structure"], fap["instrument"])
    fig = fap["data"].plot(model=ref, two_theta_range=(25, 40), dpi=72)
    texts = [t.get_text() for t in fig.axes[0].texts]
    assert texts == ["observed", "fluorapatite"]
    with pytest.raises(ValueError, match="linear intensity axis"):
        fap["data"].plot(model=ref, y_scale="log")
    import matplotlib.pyplot as plt
    plt.close("all")


def test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone():
    """Measured before WP-1544: no rietx figure showed an image in a kernel,
    and one plot call left the session on Agg, so a plain ``plt.show()``
    afterwards warned and drew nothing. With Agg no longer forced, a bare
    call showed twice and later figures leaked into the next ``plt.show()``."""
    nbformat = pytest.importorskip("nbformat")
    nbclient = pytest.importorskip("nbclient")
    cells = [f"import rietx as rx\ndata = rx.read_pattern({str(DATA / 'FAP.XRA')!r})",
             "data.plot()",
             "data.plot();",
             "fig = data.plot()",
             "import matplotlib, matplotlib.pyplot as plt\n"
             "plt.plot([1, 2]); plt.show()\nprint(matplotlib.get_backend())"]
    nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(c) for c in cells])
    # the suite pins MPLBACKEND=Agg (conftest), and a kernel honours it as a
    # choice, so this kernel starts without it, as a notebook's does
    env = {k: v for k, v in os.environ.items() if k != "MPLBACKEND"}
    nbclient.NotebookClient(nb, timeout=120, kernel_name="python3").execute(env=env)

    def images(cell):
        return sum("image/png" in o.get("data", {}) for o in cell.outputs)
    assert [images(c) for c in nb.cells[1:]] == [1, 0, 0, 1]
    backend = "".join(o.get("text", "") for o in nb.cells[-1].outputs)
    assert "inline" in backend

    # the notebook encoding reached the rietx figure (132 320 base64 chars at
    # the figure's own 300 dpi, 34 392 encoded), and only the rietx figure
    rietx_out = next(o for o in nb.cells[1].outputs if "image/png" in o.get("data", {}))
    assert len(rietx_out["data"]["image/png"]) < 60_000
    assert rietx_out["metadata"]["image/png"]["width"] < 800
    plain_out = next(o for o in nb.cells[-1].outputs if "image/png" in o.get("data", {}))
    assert "width" not in plain_out.get("metadata", {}).get("image/png", {})
    # beside the PNG, the light and dark pair a frontend's theme picks from
    # (WP-1970), and only for the rietx figure
    assert rietx_out["data"]["text/html"].count("<img ") == 2
    assert "text/html" not in plain_out["data"]


def test_a_notebook_figure_is_encoded_for_a_screen_and_files_are_not(fap, tmp_path):
    """Twice a 100-dpi screen, a 256-colour palette, drawn at half its pixel
    width; ``savefig`` still writes the figure's own dpi in full colour."""
    pytest.importorskip("matplotlib")
    import io

    from PIL import Image

    fig = fap["data"].plot()
    data, md = fig._repr_png_()
    image = Image.open(io.BytesIO(data))
    assert image.mode == "P"
    # the width alone, or a column narrower than the figure squashes it (WP-1957)
    assert md == {"width": image.size[0] // 2}
    fig.savefig(tmp_path / "file.png")
    saved = Image.open(tmp_path / "file.png")
    assert saved.mode == "RGBA"
    assert saved.size[0] == round(fig.get_figwidth() * fig.dpi) and fig.dpi == 300
    import matplotlib.pyplot as plt
    plt.close("all")


@pytest.mark.parametrize("name", ["data", "instrument", "structure", "result", "ref"])
def test_ipython_text_plain_stays_short(fap, name):
    """What a notebook *stores*: text/plain is saved beside any HTML, so a
    long repr fills the .ipynb even where the HTML is what shows."""
    formatters = pytest.importorskip("IPython.core.formatters")
    bundle, _ = formatters.DisplayFormatter().format(fap[name])
    assert len(bundle["text/plain"]) < 10_000
    assert "two_theta=" not in bundle["text/plain"], "the str view, not pydantic's repr"
