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

**Every figure that shows a fit draws it from the case that is already
asserted somewhere**, never from a second copy of it: ``examples/nac_11bm.py``
for the two refinement panels and the geometry esds (a worked example has one
authority and it is ``examples/`` — root CLAUDE.md), and the fixtures of
``tests/test_data_support.py`` and ``tests/test_restraints.py`` for the two
figures whose whole content is a measured claim those files pin.  Importing
them is deliberate: a figure drawn from its own copy of a case can disagree
with the test that proves the claim, and nobody would find out.
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
    # 200 rather than the old 110: at 110 the type and the reflection marks
    # fringe on any retina display, which is where the manual is read
    fig.savefig(path, dpi=200, bbox_inches="tight")
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


def geometry_esds(data, ref) -> None:
    """What dropping the parameter correlations does to a distance's esd.

    Continues the walkthrough's session into `mccusker_structural`, the
    protocol WP-1072 measured the spread under (it quotes full/diagonal, 0.713
    to 1.152; this axis is the reciprocal), and the reason it has to be *this*
    plan is itself the point: under the walkthrough's own
    `mccusker_default` the only free parameter a cubic distance depends on is
    `a`, the quadratic form has one term, and full and diagonal agree exactly.
    Correlations between coordinates are what the guideline is about.

    Ratio rather than a scatter against the line of equality: the claim is that
    the diagonal-only number lands on *both* sides of the full one, and a ratio
    against 1 is where that is legible.  The esds themselves span a decade and
    would cluster the interesting part of a 1:1 plot into one corner.
    """
    print("geometry-esd")
    result = ref.fit(data, plan="mccusker_structural", two_theta_limits=(2.0, 24.0))
    print(f"  mccusker_structural: Rwp {result.statistics.rwp:.5f}, "
          f"{len(result.geometry.distances)} distances")
    rows = [d for d in result.geometry.distances
            if d.stderr and d.stderr_diagonal]
    bonded = [(d.distance, d.stderr_diagonal / d.stderr) for d in rows if d.bonded]
    contacts = [(d.distance, d.stderr_diagonal / d.stderr) for d in rows if not d.bonded]
    print(f"  {len(rows)} distances with an esd; ratio "
          f"{min(r for _, r in bonded + contacts):.2f}-"
          f"{max(r for _, r in bonded + contacts):.2f}")

    for style in STYLES:
        with plt.style.context([] if style == "light" else ["dark_background"]):
            fig, ax = plt.subplots(figsize=(7.0, 3.4))
            hue = rx.viz.plots.PALETTES[style]
            ax.axhline(1.0, lw=0.8, ls=":", color=FG[style])
            for (points, colour, marker, label) in (
                (bonded, hue["obs"], "o", "bonds"),
                (contacts, hue["calc"], "^", "contacts"),
            ):
                if not points:
                    continue
                ax.plot([d for d, _ in points], [r for _, r in points], marker,
                        ms=4, mfc="none", color=colour, label=label)
            ax.set_xlabel("distance (Å)")
            ax.set_ylabel("esd, diagonal only ÷ full covariance")
            # A categorical scatter is the one case the house style keeps a
            # legend for; the marker shapes carry it in greyscale.
            ax.legend(fontsize=9, frameon=False, loc="lower right")
            fig.tight_layout()
            _save(fig, "geometry-esd", style)


def effective_observations() -> None:
    """The overlap the raw reflection count cannot see.

    The sweep is `tests/test_data_support.py`'s: one LaB6 pattern, Cu Kα,
    15-140°, widened with Lorentzian size broadening alone so the cell, the
    range and the reflection list stay put and M_ind is the only thing that can
    move.  Drawn at more points than the test asserts on, which is the whole
    difference between a figure and an assertion.
    """
    print("effective-observations")
    from rietx.optimize.statistics import count_unique_reflections
    from rietx.optimize.statistics import effective_observations as m_ind
    from tests.test_data_support import _compiled, _lab6

    tt = np.arange(15.0, 140.0, 0.01)
    widths = np.concatenate([np.arange(0.0, 2.0, 0.25), np.arange(2.0, 16.1, 1.0)])
    raw, eff = [], []
    for width in widths:
        structure, instrument = _lab6(radiation="CuKa")
        structure.phases[0].lor_size.value = float(width)
        model, values = _compiled(structure, instrument, tt)
        raw.append(count_unique_reflections(model, values))
        eff.append(m_ind(model, values))
    print(f"  {raw[0]} reflections throughout; {eff[0]:.1f} -> {eff[-1]:.1f} effective")

    for style in STYLES:
        with plt.style.context([] if style == "light" else ["dark_background"]):
            fig, ax = plt.subplots(figsize=(7.0, 3.4))
            hue = rx.viz.plots.PALETTES[style]
            ax.plot(widths, raw, "-", lw=1.6, color=hue["bkg"])
            ax.plot(widths, eff, "-", lw=1.6, color=hue["obs"])
            ax.set_xlabel("Lorentzian size broadening, lor_size (deg)")
            ax.set_ylabel("observations")
            ax.set_ylim(0.0, max(raw) * 1.15)
            for y, text, colour in ((raw[-1], "reflections measured", hue["bkg"]),
                                    (eff[-1], "effective observations", hue["obs"])):
                ax.annotate(text, xy=(widths[-1], y), xytext=(8, 0),
                            textcoords="offset points", fontsize=9, color=colour,
                            va="center", annotation_clip=False)
            ax.set_xlim(widths[0], widths[-1])
            fig.tight_layout()
            # right-margin labels: tight_layout measures axes, not annotations
            fig.subplots_adjust(right=0.70)
            _save(fig, "effective-observations", style)


def restraint_schedule() -> None:
    """Two converged fits of one pattern, and the difference curve's silence.

    `tests/test_restraints.py`'s under-determined P-1 case, run twice with c_w
    the only variable.  The panels share both axes because the point is that
    they look alike: what separates them is the bond length annotated on each,
    which no residual plot shows.
    """
    print("restraint-schedule")
    from tests.test_restraints import _sched_run, schedule_inputs

    pattern, bonds = schedule_inputs()
    runs = []
    for label, (first, second) in (("scheduled: c_w 300 then 1", (300.0, 1.0)),
                                   ("flat: c_w 1 throughout", (1.0, 1.0))):
        _, result = _sched_run(pattern, bonds, first, second)
        # row 0 is the Zr-O1 restraint, the bond that starts 1.9 A too long
        row = result.restraints.rows[0]
        worst = max(abs(r.deviation_over_sigma) for r in result.restraints.rows)
        runs.append((label, result, row.computed, worst))
        print(f"  {label}: Zr-O1 {row.computed:.3f} A (target {row.target:.3f}), "
              f"Rwp {result.statistics.rwp:.4f}, restraint {worst:.0f} sigma")

    for style in STYLES:
        with plt.style.context([] if style == "light" else ["dark_background"]):
            fig, axes = plt.subplots(2, 1, figsize=(7.0, 4.4), sharex=True, sharey=True)
            hue = rx.viz.plots.PALETTES[style]
            for ax, (label, result, distance, worst) in zip(axes, runs, strict=True):
                tt = np.asarray(result.two_theta)
                delta = ((np.asarray(result.y_obs) - np.asarray(result.y_calc))
                         / np.asarray(result.sigma))
                ax.axhspan(-3.0, 3.0, color=hue["band"], alpha=0.12, lw=0)
                ax.plot(tt, delta, "-", lw=0.8, color=hue["diff"])
                ax.annotate(f"{label}\nZr–O1 {distance:.2f} Å, "
                            f"restraint {worst:.0f}σ, Rwp {result.statistics.rwp:.4f}",
                            xy=(0.015, 0.95), xycoords="axes fraction", fontsize=9,
                            color=FG[style], va="top")
            axes[-1].set_xlabel("2θ (deg)")
            axes[0].set_ylim(-6.0, 9.0)
            fig.supylabel("Δ/σ", fontsize=10, color=FG[style])
            fig.tight_layout()
            _save(fig, "restraint-schedule", style)


def refinement_figures():
    """The 11-BM NAC fit: the quickstart's panel, and the impurity peak.

    Returns the Rietveld result, which `geometry_esds` draws from — one
    refinement, three figures.

    `plot_for_vlm`'s montage is deliberately *not* here.  It is drawn for a
    vision model — high contrast, annotated redundancy, one fixed ground — so
    it has no dark twin and is the wrong figure for a human page.
    """
    print("running examples/nac_11bm.py …")
    sys.path.insert(0, str(REPO_ROOT / "examples"))
    from nac_11bm import WAVELENGTH, run

    data, ref, lebail, result = run()

    print("nac-fit / impurity-peak")
    for style in STYLES:
        fig = result.plot(two_theta_range=(2.0, 12.0), style=style,
                          wavelength=WAVELENGTH)
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
    return data, ref


if __name__ == "__main__":
    angular_signatures()
    data, ref = refinement_figures()
    geometry_esds(data, ref)
    effective_observations()
    restraint_schedule()
