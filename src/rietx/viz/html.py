"""Self-contained interactive HTML viewer (plotly Scattergl).

``write_html(result, path)`` renders the standard Rietveld panel — observed
points, calculated line, background, offset difference curve, per-phase tick
rows — as one HTML file with plotly.js embedded (~3.6 MB, no network needed;
pass ``include_plotlyjs="cdn"`` to trade offline use for a ~10 kB file).

Scattergl draws with WebGL, so full-resolution patterns (10⁴-10⁵ points)
zoom smoothly without decimation; beyond ``max_points`` a min-max decimation
per pixel-bucket keeps the *envelope* of the data (never plain striding,
which would drop peak tops), and the size budget holds.

Zero heavy imports at module load: plotly is imported inside the call, and
the base install works without it (``pip install 'rietx[viz]'``).
"""

from __future__ import annotations

import numpy as np

from .._about import DIST_NAME
from ..schemas.results import RefinementResult


def _minmax_decimate(tt: np.ndarray, ys: list[np.ndarray], max_points: int
                     ) -> tuple[np.ndarray, list[np.ndarray]]:
    """Keep per-bucket min AND max of every curve (preserves peak envelopes)."""
    n = len(tt)
    if n <= max_points:
        return tt, ys
    n_buckets = max(max_points // 2, 1)
    edges = np.linspace(0, n, n_buckets + 1, dtype=int)
    keep: set[int] = set()
    for y in ys:
        for a, b in zip(edges[:-1], edges[1:]):
            if b > a:
                keep.add(a + int(np.argmin(y[a:b])))
                keep.add(a + int(np.argmax(y[a:b])))
    idx = np.array(sorted(keep))
    return tt[idx], [y[idx] for y in ys]


def figure_from_arrays(tt: np.ndarray, y_obs: np.ndarray, y_calc: np.ndarray,
                       y_bkg: np.ndarray | None, ticks: dict[str, list[float]],
                       *, sigma: np.ndarray | None = None, title: str = "",
                       max_points: int = 200_000):
    """Build the plotly Figure (shared by the file writer and the live view).

    With ``sigma`` the difference is drawn weighted (Δ/σ) in its own lower
    panel with a ±3σ band — expectation 1 under a correct model, so the curve
    reads on an absolute statistical scale (Toby, 2024, J. Appl. Cryst. 57,
    175); it cannot share the intensity axis. Without ``sigma`` the classic
    offset raw difference is drawn in the single panel.

    Either way the reflection rows go **below the difference**, which in the
    weighted case means inside the lower panel: the residual is read against
    the peaks that caused it, so nothing comes between them, and the rows are
    an index of what the model contains.

    Series colours are quoted from :data:`rietx.viz.plots.PALETTES`, not chosen
    here: this and the matplotlib panel are two pictures of one fit, and a
    person who flips between them must not have to relearn which curve is which.
    The layout is the viewer's own — the legend stays, because in an interactive
    figure it is a control (click a name to hide its trace) rather than a colour
    key the eye has to look up.
    """
    try:
        import plotly.graph_objects as go
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            f"the HTML viewer needs plotly: pip install '{DIST_NAME}[viz]'") from exc

    from .plots import PALETTES

    hue = PALETTES["light"]
    weighted = sigma is not None
    diff = (y_obs - y_calc) / sigma if weighted else y_obs - y_calc
    curves = [y_obs, y_calc, diff] + ([y_bkg] if y_bkg is not None else [])
    tt_d, dec = _minmax_decimate(np.asarray(tt), [np.asarray(c) for c in curves],
                                 max_points)
    y_obs_d, y_calc_d, diff_d = dec[0], dec[1], dec[2]
    y_bkg_d = dec[3] if y_bkg is not None else None

    span = float(np.max(y_obs_d) - min(float(np.min(y_obs_d)), 0.0)) or 1.0

    if weighted:
        from plotly.subplots import make_subplots
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.72, 0.28], vertical_spacing=0.05)
        # the rows live in the lower panel, under the Δ/σ trace, and are spaced
        # in its units rather than the intensity's
        d_lo = min(float(np.min(diff_d)), -3.0)
        d_hi = max(float(np.max(diff_d)), 3.0)
        d_span = (d_hi - d_lo) or 1.0
        tick_base, tick_step = d_lo - 0.14 * d_span, 0.09 * d_span
    else:
        fig = go.Figure()
        offset = -0.15 * span
        # under the *drawn* difference, not under a fixed fraction of the
        # intensity span: a noisy residual on a weak pattern reaches further
        # down than the fraction allows and the rows land inside it
        tick_base = offset + float(np.min(diff_d)) - 0.06 * span
        tick_step = 0.05 * span

    fig.add_trace(go.Scattergl(x=tt_d, y=y_obs_d, mode="markers",
                               marker={"size": 3, "color": hue["obs"]},
                               name="observed"))
    fig.add_trace(go.Scattergl(x=tt_d, y=y_calc_d, mode="lines",
                               line={"width": 1.2, "color": hue["calc"]},
                               name="calculated"))
    if y_bkg_d is not None and np.any(y_bkg_d):
        fig.add_trace(go.Scattergl(x=tt_d, y=y_bkg_d, mode="lines",
                                   line={"width": 1, "dash": "dash",
                                         "color": hue["bkg"]},
                                   name="background"))
    if weighted:
        fig.add_trace(go.Scattergl(x=tt_d, y=diff_d, mode="lines",
                                   line={"width": 1, "color": hue["diff"]},
                                   name="Δ/σ"), row=2, col=1)
        fig.add_hrect(y0=-3, y1=3, row=2, col=1, line_width=0,
                      fillcolor=hue["band"], opacity=0.15)
    else:
        fig.add_trace(go.Scattergl(x=tt_d, y=diff_d + offset, mode="lines",
                                   line={"width": 1, "color": hue["diff"]},
                                   name="difference"))

    # one row per phase, and the single-phase row stays neutral: colour is for
    # telling rows apart, so one row has nothing to be told apart from
    for row, (name, positions) in enumerate(ticks.items()):
        y_row = tick_base - row * tick_step
        pos = np.asarray(positions, dtype=np.float64)
        colour = (hue["tick"] if len(ticks) == 1
                  else hue["phase"][row % len(hue["phase"])])
        trace = go.Scattergl(
            x=pos, y=np.full_like(pos, y_row), mode="markers",
            marker={"symbol": "line-ns-open", "size": 7, "color": colour},
            name=f"hkl: {name}")
        if weighted:
            fig.add_trace(trace, row=2, col=1)
        else:
            fig.add_trace(trace)

    fig.update_layout(
        title=title, template="simple_white",
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom"},
        margin={"l": 60, "r": 20, "t": 60, "b": 50},
    )
    if weighted:
        fig.update_xaxes(title_text="2θ (deg)", row=2, col=1)
        fig.update_yaxes(title_text="intensity", row=1, col=1)
        fig.update_yaxes(title_text="Δ/σ", row=2, col=1)
    else:
        fig.update_layout(xaxis_title="2θ (deg)", yaxis_title="intensity")
    return fig


def write_html(result: RefinementResult, path: str, *,
               weighted: bool = False, include_plotlyjs: bool | str = True,
               max_points: int = 200_000) -> None:
    """Render a :class:`RefinementResult` to a self-contained HTML file.

    ``weighted`` defaults off, matching :func:`rietx.viz.plots.plot_result`:
    both are a file someone takes away and reads as a figure, so they show the
    same difference.  The *live* view (:mod:`rietx.viz.live`) passes ``sigma``
    explicitly and keeps Δ/σ, because a stage-by-stage diagnostic is asking a
    different question — is the model right yet — of the same numbers.
    """
    s = result.statistics
    y_obs = np.asarray(result.y_obs)
    sigma = result.sig() if weighted else None
    fig = figure_from_arrays(
        np.asarray(result.two_theta), y_obs,
        np.asarray(result.y_calc),
        np.asarray(result.y_background) if result.y_background else None,
        result.ticks, sigma=sigma,
        title=f"{result.mode}  Rwp={s.rwp:.4f}  GoF={s.gof:.2f}",
        max_points=max_points)
    fig.write_html(path, include_plotlyjs=include_plotlyjs,
                   full_html=True, config={"displaylogo": False})
