"""Static obs/calc/difference plotting (matplotlib/Agg).

The interactive plotly HTML viewer follows in v0.2; this renderer produces
the standard Rietveld panel: observed points, calculated line, difference
curve offset below, and per-phase reflection tick rows.
"""

from __future__ import annotations

import numpy as np

from ..schemas.results import RefinementResult


def plot_result(result: RefinementResult, *, path: str | None = None,
                two_theta_range: tuple[float, float] | None = None,
                show_background: bool = True, dpi: int = 150):
    try:
        import matplotlib
        matplotlib.use("Agg", force=False)
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError("plotting needs matplotlib: pip install 'pxrd-refine[viz]'") from exc

    tt = np.asarray(result.two_theta)
    y_obs = np.asarray(result.y_obs)
    y_calc = np.asarray(result.y_calc)
    y_bkg = np.asarray(result.y_background)
    diff = y_obs - y_calc

    fig, ax = plt.subplots(figsize=(10, 6), dpi=dpi)
    ax.plot(tt, y_obs, ".", ms=2.5, color="#1f5fa8", label="observed", zorder=2)
    ax.plot(tt, y_calc, "-", lw=1.0, color="#c23b22", label="calculated", zorder=3)
    if show_background and np.any(y_bkg):
        ax.plot(tt, y_bkg, "--", lw=0.8, color="#7a7a7a", label="background", zorder=1)

    span = float(y_obs.max() - min(y_obs.min(), 0.0))
    offset = -0.12 * span
    ax.plot(tt, diff + offset, "-", lw=0.7, color="#4a4a4a", label="difference", zorder=2)
    ax.axhline(offset, lw=0.4, color="#bbbbbb", zorder=1)

    tick_base = offset - 0.08 * span
    for row, (name, positions) in enumerate(result.ticks.items()):
        yline = tick_base - row * 0.05 * span
        pos = np.asarray(positions)
        if two_theta_range is not None:
            pos = pos[(pos >= two_theta_range[0]) & (pos <= two_theta_range[1])]
        ax.vlines(pos, yline - 0.015 * span, yline + 0.015 * span,
                  lw=0.6, color=f"C{row + 2}", label=f"hkl: {name}")

    if two_theta_range is not None:
        ax.set_xlim(*two_theta_range)
    ax.set_xlabel(r"2$\theta$ (deg)")
    ax.set_ylabel("intensity")
    s = result.statistics
    ax.set_title(f"{result.mode}  Rwp={s.rwp:.4f}  GoF={s.gof:.2f}")
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    fig.tight_layout()
    if path is not None:
        fig.savefig(path)
    return fig
