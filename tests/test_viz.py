"""WP-1444: the pattern before the model, and a title on the figure.

`plot_pattern` is the result panel with nothing modelled in it, so most of
what is asserted here is *agreement*: the same data drawn by both verbs lands
on the same axis.  The title is opt-in, and the default figure must not move
for it, which is pinned by bytes where bytes can be pinned (see
`test_the_default_result_render_is_the_pre_title_render`).
"""

from __future__ import annotations

import hashlib
import io
import platform
import sys
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.pattern import PatternData
from rietx.viz.plots import PALETTES, plot_for_vlm, plot_pattern, plot_result
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("viz-pattern")

OUT = Path(__file__).parent / "output"

#: The one window the fixture's fit holds back — a stretch of background
#: between the first two LaB6 lines of the synthetic pattern.
EXCLUDED = (6.5, 7.5)


@pytest.fixture(scope="module")
def fitted():
    """One synthetic LaB6 fit with an excluded region, and the pattern it saw."""
    pattern = synthesize()
    pattern.excluded_regions = [EXCLUDED]
    structure, ins = perturbed_models()
    result = rx.Refinement(structure, ins, history=False).fit(pattern)
    return pattern, result


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return buf.getvalue()


def _as_pattern(result) -> PatternData:
    """The result's own channels as a bare pattern: the same data, no model."""
    return PatternData(two_theta=list(result.two_theta),
                       intensity=list(result.y_obs))


def _span(band) -> tuple[float, float]:
    """The x extent of an ``axvspan`` band, in data coordinates."""
    return band.get_x(), band.get_x() + band.get_width()


def _axis(ax) -> dict:
    """What a reader takes off an intensity axis, and nothing drawn on it."""
    return {"xlim": ax.get_xlim(), "xlabel": ax.get_xlabel(),
            "yscale": ax.get_yscale(), "ylabel": ax.get_ylabel(),
            "yticks": list(ax.get_yticks()),
            "spine": tuple(ax.spines["left"].get_bounds()),
            "label_y": ax.yaxis.label.get_position()[1]}


# ----------------------------------------------------------------------
# plot_pattern
# ----------------------------------------------------------------------
def test_a_pattern_and_its_fit_share_one_intensity_axis(fitted):
    """Same data, same axis: ticks, label, scale, spine and x range agree.

    On a nonlinear scale the result's data panel has the pattern figure's
    whole y range too, headroom included, so a before-and-after pair shows a
    peak at one height.  On the linear axis the result's floor is lower — the
    residual and the tick rows sit under the data there — and everything the
    reader reads off the axis still agrees.
    """
    _, result = fitted
    bare = _as_pattern(result)
    OUT.mkdir(exist_ok=True)
    lam = 0.45
    for kw in ({}, {"y_scale": "sqrt"}, {"y_scale": "log"}, {"y_scale": "asinh"},
               {"x_axis": "d", "wavelength": lam}, {"x_axis": "q", "wavelength": lam},
               {"two_theta_range": (8.0, 16.0)}):
        stem = "_".join(["viz_pattern", *(f"{k}-{v}" for k, v in kw.items())])
        mine = plot_pattern(bare, path=str(OUT / f"{stem}.png"), **kw).get_axes()
        panels = plot_result(result, **kw).get_axes()
        theirs = panels[0]
        assert len(mine) == 1, "a pattern has no residual panel"
        a, b = _axis(mine[0]), _axis(theirs)
        # the x label sits under the lowest panel, which is the residual's
        # when the result draws one
        b["xlabel"] = panels[-1].get_xlabel()
        label_a, label_b = a.pop("label_y"), b.pop("label_y")
        assert a.keys() == b.keys()
        for key in a:
            if isinstance(a[key], str):
                assert a[key] == b[key], (kw, key)
            else:
                assert np.allclose(a[key], b[key]), (kw, key, a[key], b[key])
        if kw.get("y_scale", "linear") != "linear":
            assert mine[0].get_ylim() == pytest.approx(theirs.get_ylim()), kw
            assert label_a == pytest.approx(label_b), kw


def test_the_pattern_draws_the_measurement_and_nothing_modelled(fitted):
    """Observed markers in the result's own ink, one gutter name, no σ, no title."""
    pattern, _ = fitted
    ax = plot_pattern(pattern).get_axes()[0]
    (line,) = ax.get_lines()        # σ is not drawn, even where it is known
    assert line.get_linestyle() == "None" and line.get_marker() == "x"
    assert line.get_color() == PALETTES["light"]["obs"]
    assert [t.get_text() for t in ax.texts] == ["observed"]
    lo, hi = ax.get_ylim()
    assert lo <= ax.texts[0].get_position()[1] <= hi
    assert ax.get_title() == "" and ax.get_legend() is None

    dark = plot_pattern(pattern, style="dark")
    assert sum(dark.get_facecolor()[:3]) < 0.3
    assert dark.get_axes()[0].get_lines()[0].get_color() == PALETTES["dark"]["obs"]


def test_an_excluded_region_is_shaded_over_channels_the_fit_left_out(fitted):
    """The shading covers exactly the gap the result's own channels leave.

    A result carries only the fitted channels, so the region is a hole in its
    data; the pattern still holds those counts, so they are drawn and the
    region is shaded over them instead.  The agreement asserted is that the
    band and the hole are the same stretch of 2θ.
    """
    pattern, result = fitted
    OUT.mkdir(exist_ok=True)
    ax = plot_pattern(pattern, path=str(OUT / "viz_pattern_excluded.png")).get_axes()[0]
    (band,) = ax.patches
    assert _span(band) == pytest.approx(EXCLUDED)

    drawn = ax.get_lines()[0].get_xdata()
    assert np.any((drawn >= EXCLUDED[0]) & (drawn <= EXCLUDED[1])), \
        "the excluded channels are still a measurement, and are drawn"
    fit_x = plot_result(result).get_axes()[0].get_lines()[0].get_xdata()
    inside = (fit_x >= EXCLUDED[0]) & (fit_x <= EXCLUDED[1])
    assert not inside.any(), "the result has no channel inside the region"
    gap = np.diff(fit_x).argmax()
    assert fit_x[gap] < EXCLUDED[0] and fit_x[gap + 1] > EXCLUDED[1]

    # on a d axis the edges arrive in the other order and the band follows
    lam = 0.45
    d_ax = plot_pattern(pattern, x_axis="d", wavelength=lam).get_axes()[0]
    expect = sorted(lam / (2 * np.sin(np.radians(t) / 2)) for t in EXCLUDED)
    assert _span(d_ax.patches[0]) == pytest.approx(expect)
    # a window that misses the region draws no band at all
    assert not plot_pattern(pattern, two_theta_range=(10.0, 14.0)).get_axes()[0].patches


def test_pattern_data_plot_forwards_and_refuses_what_the_result_refuses(fitted):
    pattern, _ = fitted
    OUT.mkdir(exist_ok=True)
    out = OUT / "viz_pattern_default.png"
    fig = pattern.plot(str(out), y_scale="sqrt")
    assert out.stat().st_size > 5_000
    assert fig.get_axes()[0].get_yscale() == "function"
    with pytest.raises(ValueError, match="style must be one of"):
        pattern.plot(style="solarized")
    with pytest.raises(ValueError, match="wavelength"):
        pattern.plot(x_axis="q")
    with pytest.raises(ValueError, match="y_scale must be one of"):
        pattern.plot(y_scale="logit")
    with pytest.raises(ValueError, match="contains no points"):
        pattern.plot(two_theta_range=(90.0, 91.0))


# ----------------------------------------------------------------------
# title=
# ----------------------------------------------------------------------
def test_a_title_is_the_callers_words_in_the_panels_type(fitted):
    pattern, result = fitted
    OUT.mkdir(exist_ok=True)
    for kw in ({}, {"weighted": True}, {"y_scale": "log"}):
        fig = plot_result(result, title="pattern 3 of 30", font_size=9.0, **kw)
        top = fig.get_axes()[0]
        assert top.get_title() == "pattern 3 of 30", kw
        assert top.title.get_fontsize() == 9.0, "one type size for the figure"
        # the statistics stay a corner annotation beside a title, not in it
        assert any("R_" in t.get_text() for t in top.texts)
        assert all(ax.get_title() == "" for ax in fig.get_axes()[1:])
    result.plot(path=str(OUT / "viz_result_titled.png"), title="LaB6, synthetic")
    ax = pattern.plot(str(OUT / "viz_pattern_titled.png"),
                      title="LaB6, before the model").get_axes()[0]
    assert ax.get_title() == "LaB6, before the model"


def test_no_title_is_the_figure_without_the_keyword(fitted):
    """`title=None` draws nothing, byte for byte, on every figure that takes it."""
    pattern, result = fitted
    assert _png(plot_result(result)) == _png(plot_result(result, title=None))
    assert _png(plot_result(result, weighted=True)) == \
        _png(plot_result(result, weighted=True, title=None))
    assert _png(plot_pattern(pattern)) == _png(plot_pattern(pattern, title=None))
    assert _png(plot_result(result)) != _png(plot_result(result, title="x"))


def test_the_vlm_montage_refuses_a_title_by_name(fitted, tmp_path):
    """Its panel titles are evidence a model reads; a caller's is not added."""
    _, result = fitted
    with pytest.raises(TypeError, match="title"):
        plot_for_vlm(result, path=str(tmp_path / "vlm.png"), title="x")


#: sha256 of :func:`plot_result`'s renders of :func:`_pinned_result`,
#: captured from ``origin/main`` at ``f1b89d63`` — before WP-1444 moved the
#: intensity-axis code into a helper and added ``title=`` — and matched by the
#: tree after it.  Pinned where it was captured, as the bit-identity goldens
#: are (``tests/test_backend_shim.py``): a PNG's bytes follow matplotlib's and
#: FreeType's versions, not only this code.
PRE_TITLE_RENDER = {
    "default": "16aa396da1565046be969cbca4e458c57598e5ac7055a53e67997bb1064a6077",
    "weighted": "d19f16a14a49342cd105305fdb1a8b408b957076412621fbb9252b236ef9f459",
    "log": "2b3d16a670d3462256bc64dcd3cad94dc262b04a9be527f4ae1e08efeffbf379",
}
PINNED_ON = (("darwin", "arm64"), "3.11.1")


def _pinned_result(result):
    """A result whose drawn arrays are closed-form, so no fit's last digit
    reaches the render; only the rendering code and its libraries do."""
    pinned = result.model_copy(deep=True)
    tt = np.arange(5.0, 25.0, 0.02)
    peaks = sum(a * np.exp(-0.5 * ((tt - c) / 0.05) ** 2)
                for a, c in ((1000.0, 8.0), (600.0, 12.5), (300.0, 19.0)))
    bkg = 50.0 + 2.0 * (tt - 5.0)
    pinned.two_theta = tt.tolist()
    pinned.y_calc = (peaks + bkg).tolist()
    pinned.y_obs = (peaks * 1.03 + bkg + 3.0 * np.sin(7.0 * tt)).tolist()
    pinned.y_background = bkg.tolist()
    pinned.sigma = np.sqrt(peaks + bkg).tolist()
    pinned.ticks = {"LaB6": [8.0, 12.5, 19.0]}
    pinned.statistics = pinned.statistics.model_copy(update={"rwp": 0.05, "gof": 1.5})
    return pinned


def test_the_default_result_render_is_the_pre_title_render(fitted):
    import matplotlib

    here = ((sys.platform, platform.machine()), matplotlib.__version__)
    if here != PINNED_ON:
        pytest.skip(f"render pinned on {PINNED_ON}, this is {here}")
    _, result = fitted
    pinned = _pinned_result(result)
    for name, kw in (("default", {}), ("weighted", {"weighted": True}),
                     ("log", {"y_scale": "log"})):
        got = hashlib.sha256(_png(plot_result(pinned, **kw))).hexdigest()
        assert got == PRE_TITLE_RENDER[name], name
