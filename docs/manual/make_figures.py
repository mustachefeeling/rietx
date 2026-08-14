"""Regenerate Part 1's committed figures (WP-1068).

    .venv/bin/python docs/manual/make_figures.py

The figures are **committed**, not built.  Two reasons: the sphinx build stays
seconds rather than minutes, and it stays offline and dependency-free — a docs
build should not have to refine a real pattern.  The cost is that a figure can
go stale, so this script is the one authority for how each was drawn, and
``tests/test_manual_api.py`` checks that every figure a chapter references
exists.

Each figure is written twice, ``-light`` and ``-dark``, and the chapters select
between them with furo's ``only-light`` / ``only-dark`` classes.  A single
white-ground figure on a dark page is the thing this avoids.

The refinement figures come from ``examples/nac_11bm.py``'s ``run()``, not from
a second copy of that walkthrough: a worked example has one authority and it is
``examples/`` (root CLAUDE.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (after the backend is fixed)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIGURES = Path(__file__).resolve().parent / "using" / "figures"
sys.path.insert(0, str(REPO_ROOT))

import rietx as rx  # noqa: E402  (needs the repo on sys.path)

STYLES = ("light", "dark")
#: Foreground for the hand-drawn figures, per style.  `plot_result` carries its
#: own palette; these are for the ones drawn here.
FG = {"light": "#222222", "dark": "#e6e6e6"}
LINES = {
    "light": ("#1f5fa8", "#c23b22", "#2a7f3f", "#8a5cc4"),
    "dark": ("#6fb1ff", "#ff8a72", "#6ede8a", "#c9a6ff"),
}


def _save(fig, stem: str, style: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / f"{stem}-{style}.png"
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"  {path.relative_to(REPO_ROOT)}")


def angular_signatures() -> None:
    """Why the correlated groups are correlated: their shapes in 2θ.

    Each curve is normalised to 1 at the mid-point of the range, because what
    decides separability is the *shape* over the measured range and not the
    scale — two curves that differ only by a factor are one parameter.
    """
    print("angular-signatures")
    two_theta = np.linspace(10.0, 120.0, 400)
    theta = np.radians(two_theta / 2.0)
    curves = [
        ("zero shift: constant", np.ones_like(theta)),
        ("displacement: cos θ", np.cos(theta)),
        ("cell: tan θ", np.tan(theta)),
        ("size: 1/cos θ", 1.0 / np.cos(theta)),
    ]
    for style in STYLES:
        with plt.style.context([] if style == "light" else ["dark_background"]):
            fig, (wide, narrow) = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
            for ax, lo, hi, title in (
                (wide, 10.0, 120.0, "over 110° of data the shapes separate"),
                (narrow, 20.0, 40.0, "over 20° they are one parameter"),
            ):
                keep = (two_theta >= lo) & (two_theta <= hi)
                anchor = np.argmin(abs(two_theta - 0.5 * (lo + hi)))
                for (label, y), colour in zip(curves, LINES[style], strict=True):
                    ax.plot(two_theta[keep], (y / y[anchor])[keep], lw=1.6,
                            color=colour, label=label)
                ax.set_xlabel("2θ (deg)")
                ax.set_title(title, fontsize=9, color=FG[style])
                ax.axhline(1.0, lw=0.5, ls=":", color=FG[style], alpha=0.5)
            wide.set_ylabel("effect, normalised at mid-range")
            wide.set_ylim(0.0, 3.0)
            wide.legend(fontsize=8, frameon=False, loc="upper left")
            fig.tight_layout()
            _save(fig, "angular-signatures", style)


def refinement_figures() -> None:
    """The 11-BM NAC fit: the quickstart's panel, and the impurity peak.

    `plot_for_vlm`'s montage is deliberately *not* here.  It is drawn for a
    vision model — high contrast, annotated redundancy, one fixed ground — so
    it has no dark twin and is the wrong figure for a human page.
    """
    print("running examples/nac_11bm.py …")
    sys.path.insert(0, str(REPO_ROOT / "examples"))
    from nac_11bm import run

    _, _, lebail, result = run()

    print("nac-fit / impurity-peak")
    for style in STYLES:
        fig = result.plot(two_theta_range=(2.0, 12.0), style=style)
        _save(fig, "nac-fit", style)

        # The CaF2 111 line at 7.5 deg: the Le Bail model does not contain the
        # impurity, so the report flags an unmatched observed peak there.  This
        # is the concrete version of "Le Bail first" in the quickstart.
        hue = rx.viz.plots.PALETTES[style]
        with plt.style.context([] if style == "light" else ["dark_background"]):
            fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), sharey=True)
            for ax, res, name in zip(axes, (lebail, result),
                                     ("Le Bail, impurity not in the model",
                                      "Rietveld, CaF₂ added"), strict=True):
                tt = np.asarray(res.two_theta)
                keep = (tt >= 7.25) & (tt <= 7.75)
                ax.plot(tt[keep], np.asarray(res.y_obs)[keep], ".", ms=3,
                        color=hue["obs"], label="observed")
                ax.plot(tt[keep], np.asarray(res.y_calc)[keep], "-", lw=1.2,
                        color=hue["calc"], label="calculated")
                ax.set_xlabel("2θ (deg)")
                ax.set_title(name, fontsize=9, color=FG[style])
            axes[0].annotate("unmatched\nobserved peak", xy=(7.50, 14000),
                             xytext=(7.30, 9000), fontsize=8, color=FG[style],
                             arrowprops={"arrowstyle": "->", "color": FG[style]})
            axes[0].set_ylabel("intensity")
            axes[0].legend(fontsize=8, frameon=False)
            fig.tight_layout()
            _save(fig, "impurity-peak", style)


if __name__ == "__main__":
    angular_signatures()
    refinement_figures()
