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
the base install works without it (``pip install 'pxrd-refine[viz]'``).
"""

from __future__ import annotations

import numpy as np

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
                       *, title: str = "", max_points: int = 200_000):
    """Build the plotly Figure (shared by the file writer and the live view)."""
    try:
        import plotly.graph_objects as go
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "the HTML viewer needs plotly: pip install 'pxrd-refine[viz]'") from exc

    diff = y_obs - y_calc
    curves = [y_obs, y_calc, diff] + ([y_bkg] if y_bkg is not None else [])
    tt_d, dec = _minmax_decimate(np.asarray(tt), [np.asarray(c) for c in curves],
                                 max_points)
    y_obs_d, y_calc_d, diff_d = dec[0], dec[1], dec[2]
    y_bkg_d = dec[3] if y_bkg is not None else None

    span = float(np.max(y_obs_d) - min(float(np.min(y_obs_d)), 0.0)) or 1.0
    offset = -0.15 * span

    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=tt_d, y=y_obs_d, mode="markers",
                               marker={"size": 3, "color": "#1f5fa8"},
                               name="observed"))
    fig.add_trace(go.Scattergl(x=tt_d, y=y_calc_d, mode="lines",
                               line={"width": 1.2, "color": "#c23b22"},
                               name="calculated"))
    if y_bkg_d is not None and np.any(y_bkg_d):
        fig.add_trace(go.Scattergl(x=tt_d, y=y_bkg_d, mode="lines",
                                   line={"width": 1, "dash": "dash",
                                         "color": "#7a7a7a"},
                                   name="background"))
    fig.add_trace(go.Scattergl(x=tt_d, y=diff_d + offset, mode="lines",
                               line={"width": 1, "color": "#4a4a4a"},
                               name="difference"))

    tick_base = offset - 0.08 * span
    palette = ("#2a9d2a", "#7a1fa8", "#b8860b", "#008b8b")
    for row, (name, positions) in enumerate(ticks.items()):
        y_row = tick_base - row * 0.05 * span
        pos = np.asarray(positions, dtype=np.float64)
        fig.add_trace(go.Scattergl(
            x=pos, y=np.full_like(pos, y_row), mode="markers",
            marker={"symbol": "line-ns-open", "size": 7,
                    "color": palette[row % len(palette)]},
            name=f"hkl: {name}"))

    fig.update_layout(
        title=title, template="simple_white",
        xaxis_title="2θ (deg)", yaxis_title="intensity",
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom"},
        margin={"l": 60, "r": 20, "t": 60, "b": 50},
    )
    return fig


def write_html(result: RefinementResult, path: str, *,
               include_plotlyjs: bool | str = True,
               max_points: int = 200_000) -> None:
    """Render a :class:`RefinementResult` to a self-contained HTML file."""
    s = result.statistics
    fig = figure_from_arrays(
        np.asarray(result.two_theta), np.asarray(result.y_obs),
        np.asarray(result.y_calc),
        np.asarray(result.y_background) if result.y_background else None,
        result.ticks,
        title=f"{result.mode}  Rwp={s.rwp:.4f}  GoF={s.gof:.2f}",
        max_points=max_points)
    fig.write_html(path, include_plotlyjs=include_plotlyjs,
                   full_html=True, config={"displaylogo": False})
