"""Static plots for the indexing pipeline (matplotlib/Agg).

Three pictures, one per stage of what :func:`~pxrdref.indexing.index_pattern`
does, drawn in the same palette as the Rietveld panel in :mod:`pxrdref.viz.plots`
so a reader moving between them is not relearning colours:

* :func:`plot_peak_list` — what the search was actually given.  A peak list is an
  *input* that has already thrown most of the pattern away, and every indexing
  failure this package has measured on real data was visible here first (WP-1018's
  spurious Kα2 lines, WP-1039's satellites, the LaB6 tail components).
* :func:`plot_candidates` — the ranked answers as tick rows against the observed
  lines, which is the only view in which "indexes everything and predicts a
  forest" looks like what it is.
* :func:`plot_validation` — the Le Bail fit behind the gate, with **both**
  detector lists marked, because they catch different failures
  (:mod:`pxrdref.indexing.workflow`).

**Why the tick rows are regenerated rather than retrieved.**  A
:class:`~pxrdref.schemas.indexing.CellCandidate` carries no hkl assignment and no
predicted-2θ list — deliberately, since a candidate is a *lattice* and the
reflections it implies depend on the range you ask about.  So the ticks come from
:func:`pxrdref.indexing.fom.predicted_lines`, the same enumeration the figures of
merit are computed on, which is what keeps a picture from disagreeing with the
number printed beside it.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

#: Observed data, calculated model, and the recessive marks — the tokens
#: ``viz.plots`` already uses, restated here rather than imported so the two
#: modules stay independently readable.
OBS = "#1f5fa8"
CALC = "#c23b22"
BKG = "#7a7a7a"
DIFF = "#4a4a4a"
#: The two Le Bail detectors.  ``unmatched_observed`` keeps the purple
#: ``plot_for_vlm`` already gives that exact meaning; ``predicted_but_absent`` is
#: the amber this palette uses for "look here", and the two never share a mark
#: because they are evidence about opposite things — a wrong metric against an
#: oversized one.
ABSENT = "#f2c14e"
UNMATCHED = "#7a1fa8"
#: Candidate rows, in **rank order and never cycled**: rank 1 is always the first
#: colour, so two galleries of the same dataset are comparable.  Past the eighth
#: candidate the rows are drawn in ``DIFF`` rather than in a generated hue.
CANDIDATE_COLORS = ("#1f5fa8", "#c23b22", "#2a9d2a", "#7a1fa8",
                    "#d17b0f", "#0f8c8c", "#a8195f", "#5a5a9d")


def _pyplot():
    try:
        import matplotlib
        matplotlib.use("Agg", force=False)
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError("plotting needs matplotlib: "
                          "pip install 'pxrd-refine[viz]'") from exc
    return plt


def _two_theta_of_q(q: np.ndarray, wavelength: float) -> np.ndarray:
    """Q → 2θ, clipped at the Ewald limit rather than raising on it."""
    arg = np.clip(wavelength * np.sqrt(np.maximum(np.asarray(q), 0.0)) / 2.0,
                  -1.0, 1.0)
    return np.degrees(2.0 * np.arcsin(arg))


def plot_peak_list(peaks, data=None, *, path: str | None = None,
                   dpi: int = 150, title: str | None = None):
    """The picked lines over the pattern they came from — the search's real input.

    ``data`` is optional: with a
    :class:`~pxrdref.schemas.pattern.PatternData` the lines are drawn over the
    profile, and without one they are drawn as a stem plot against intensity,
    which is all a position list (``PeakList.from_positions``) actually carries.

    A line carrying a **per-line** quality flag — a failed fit, a position at a
    bound, an unresolved shoulder — is drawn faint, because it is in the list
    without being evidence of the same weight, and those are the lines every
    real-data indexing failure this package has measured turned out to be about.
    ``sigma_assumed`` is deliberately **not** one of them: it is a property of the
    whole list rather than of a line (every entry of a ``from_positions`` list
    carries it), so it belongs in the title, where it says once what it means.
    """
    plt = _pyplot()
    usable = peaks.usable()
    tt = np.array([p.two_theta for p in usable], dtype=np.float64)
    esd = np.array([p.two_theta_esd for p in usable], dtype=np.float64)
    inten = np.array([p.intensity for p in usable], dtype=np.float64)
    flagged = np.array([bool(set(p.flags) - {"sigma_assumed"}) for p in usable],
                       dtype=bool)
    assumed = all("sigma_assumed" in p.flags for p in usable) if usable else False

    fig, ax = plt.subplots(figsize=(11, 4.5), dpi=dpi)
    if data is not None:
        x = np.asarray(data.two_theta, dtype=np.float64)
        y = np.asarray(data.intensity, dtype=np.float64)
        ax.plot(x, y, "-", lw=0.7, color=OBS, label="pattern", zorder=1)
        top = float(y.max())
    else:
        top = float(inten.max()) if len(inten) else 1.0
        ax.vlines(tt, 0.0, inten, lw=0.9, color=OBS, label="peak list", zorder=1)

    base = -0.06 * top
    ax.vlines(tt[~flagged], base - 0.03 * top, base + 0.03 * top, lw=1.1,
              color=CALC, zorder=3,
              label=f"clean ({int((~flagged).sum())})")
    if flagged.any():
        ax.vlines(tt[flagged], base - 0.03 * top, base + 0.03 * top, lw=1.1,
                  color=CALC, alpha=0.30, zorder=3,
                  label=f"flagged ({int(flagged.sum())})")

    ax.axhline(0.0, lw=0.4, color="#cccccc", zorder=0)
    ax.set_xlabel(r"2$\theta$ (deg)")
    ax.set_ylabel("intensity")
    # σ is quoted rather than drawn: at a whole-pattern scale 3σ is well under a
    # pixel on any list worth indexing (0.03° against a 70° axis), and a mark the
    # legend promises but the eye cannot find is worse than a number
    median_sigma = float(np.median(esd)) if len(esd) else float("nan")
    ax.set_title(title or (
        f"{len(usable)} usable lines, source={peaks.source}, "
        rf"$\lambda$={peaks.wavelength:.5f} Å, "
        rf"median $\sigma$(2$\theta$)={median_sigma:.4f}°"
        + (" (assumed, not measured)" if assumed else "")), fontsize=10)
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    fig.tight_layout()
    if path is not None:
        fig.savefig(path)
    return fig


def plot_candidates(candidates: Sequence, peaks, *, path: str | None = None,
                    n: int = 5, dpi: int = 150, title: str | None = None,
                    q_match=None):
    """Ranked candidates as tick rows against the observed lines.

    **The forward and reverse directions are both visible, which is the whole
    point.**  Each row draws every line the candidate lattice predicts in range;
    a tick with an observed line under it is solid and one without is hollow.  So
    a cell that indexes everything by predicting a forest — the measured false
    positive this package ranks a panel to avoid — is the row that is mostly
    hollow, and no figure of merit has to be trusted for a reader to see it.

    **``q_match`` is the window the search matched with, and passing the wrong
    one makes the picture contradict the number printed beside it.**  CLAUDE.md's
    rule — the matching window is an argument separate from the per-line σ —
    applies here for the same reason it applies to :func:`fom.fom_panel`: on a
    pattern with a shift allowance the search asked "is this the same line" in a
    *widened* window, and asking it again in the raw σ answers a different
    question.  Measured on 11-BM NAC, which carries the default 0.05° allowance:
    with ``q_match=None`` this figure labelled a row "224/285 indexed" from the
    candidate's own field and drew **213 of 285 as unindexed** in the same
    legend.  ``None`` means ``peaks.q_esd()``, which is the identity when no
    allowance applies; callers with a result in hand should pass
    :func:`pxrdref.indexing.engines.match_window`.

    Each candidate is matched on the positions it actually claims
    (:func:`pxrdref.indexing.engines.scored_positions`), so one carrying a fitted
    shift is not marked down for the correction it declared.  The ticks are
    *drawn* at the uncorrected predicted positions, since the shifts this
    package fits are 0.03-0.07° against a 100°+ axis — sub-pixel, where the
    match is not.
    """
    from ..indexing.engines import scored_positions
    from ..indexing.fom import MATCH_SIGMA, match_lines, predicted_lines

    plt = _pyplot()
    shown = list(candidates)[:n]
    if not shown:
        raise ValueError("plot_candidates needs at least one candidate")

    q_esd = peaks.q_esd() if q_match is None else np.asarray(q_match,
                                                             dtype=np.float64)
    tt_obs = peaks.two_theta()
    inten = peaks.intensity()
    tt_lo = float(peaks.two_theta_min)
    tt_hi = float(peaks.two_theta_max)

    fig, (ax, axt) = plt.subplots(
        2, 1, figsize=(11, 2.2 + 0.62 * len(shown)), dpi=dpi, sharex=True,
        gridspec_kw={"height_ratios": [1.5, 0.55 + 0.42 * len(shown)]})

    scale = float(inten.max()) if len(inten) and inten.max() > 0 else 1.0
    ax.vlines(tt_obs, 0.0, inten / scale, lw=0.9, color=OBS, zorder=2,
              label=f"observed ({len(tt_obs)})")
    ax.set_ylabel("rel. intensity")
    ax.set_ylim(0.0, 1.15)

    for row, cand in enumerate(shown):
        colour = (CANDIDATE_COLORS[row] if row < len(CANDIDATE_COLORS) else DIFF)
        _hkl, q_pred = predicted_lines(cand.cell, cand.system, cand.centring,
                                       peaks.wavelength, tt_hi)
        tt_pred = _two_theta_of_q(q_pred, peaks.wavelength)
        # each prediction: is an observed line sitting under it?  Against the
        # positions *this* candidate claims, in the window the search used.
        q_claim, _tt_claim = scored_positions(peaks, cand)
        if len(q_claim) and len(q_pred):
            gap = np.abs(np.asarray(q_pred)[:, None] - q_claim[None, :])
            j = np.argmin(gap, axis=1)
            seen = gap[np.arange(len(q_pred)), j] <= MATCH_SIGMA * np.maximum(
                q_esd[j], 1e-300)
        else:
            seen = np.zeros(len(q_pred), dtype=bool)
        # drawn over the plotted range, matched over the panel's.  Enumerating
        # from ``tt_lo`` instead put the *boundary* prediction outside the set —
        # and ``PeakList.two_theta_min`` is the first line's own position, so
        # every candidate figure read its first observed line as unindexed.
        inview = tt_pred >= tt_lo
        y = -float(row)
        axt.vlines(tt_pred[seen & inview], y - 0.30, y + 0.30, lw=1.0,
                   color=colour, zorder=3)
        axt.vlines(tt_pred[~seen & inview], y - 0.18, y + 0.18, lw=0.8,
                   color=colour, alpha=0.30, zorder=2)
        # **The share is quoted from the panel, not recomputed here.**  The two
        # enumerate over different ranges on purpose — the panel stops at the
        # last *observed* line (``fom.fom_panel``) while the picture must cover
        # the axis it draws — so recomputing gives a number a few points from
        # ``predicted_seen_fraction`` and prints it in a figure whose whole
        # claim is that it agrees with the panel (measured on NAC: 43 % drawn
        # against the panel's 46 %).  The ticks show the lattice over the range;
        # the number is the one that was ranked on.
        fom_value = getattr(cand, "fom_value", None)
        share = fom_value("predicted_seen_fraction") if fom_value else None
        if share is None:
            share = float(np.mean(seen)) if len(seen) else 0.0
        m20 = fom_value("m20") if fom_value else None
        label = (f"#{row + 1} {cand.system} {cand.centring}  "
                 f"a={cand.cell[0]:.4f} V={cand.volume:.1f} Å³  "
                 f"{cand.n_indexed}/{cand.n_lines} indexed, "
                 f"{share:.0%} of predicted lines seen "
                 f"({int(inview.sum())} drawn)")
        if m20 is not None:
            label += f", M20={m20:.1f}"
        # ``confidence`` defaults to ``"low"`` on an *ungated* candidate, so
        # printing it unconditionally would put a verdict in the picture that
        # nothing had reached.  A gated candidate either says something other
        # than low or carries the caveats that made it low; both are shown.
        conf = getattr(cand, "confidence", None)
        caveats = list(getattr(cand, "confidence_caveats", ()) or ())
        if conf and (conf != "low" or caveats):
            # capped: a candidate can carry six caveats, and a label wider than
            # the axes is a label nobody reads.  The count is kept, so a reader
            # knows there are more rather than being shown a truncated set as
            # though it were the whole one.
            shown_caveats = caveats[:3]
            more = len(caveats) - len(shown_caveats)
            text = ", ".join(shown_caveats) + (f", +{more} more" if more else "")
            label += f"  [{conf}" + (f": {text}]" if caveats else "]")
        axt.text(0.004, y + 0.40, label, fontsize=7.5, color=DIFF, va="bottom",
                 transform=axt.get_yaxis_transform())

    # observed lines the best candidate does not claim.  ``scored_positions``
    # is duck-typed on ``shift_template``/``shift_coefficient``, which a
    # ``CellCandidate`` carries directly — the previous ``hasattr(best, "fit")``
    # guard was never true on one, so this silently drew every shift-carrying
    # candidate against positions it had not claimed.
    best = shown[0]
    q_claim, _tt_claim = scored_positions(peaks, best)
    _hkl0, q_pred0 = predicted_lines(best.cell, best.system, best.centring,
                                     peaks.wavelength, tt_hi)
    idx, _d = match_lines(q_claim, q_esd, q_pred0, k_sigma=MATCH_SIGMA)
    missed = idx < 0
    if missed.any():
        ax.vlines(tt_obs[missed], 0.0, inten[missed] / scale, lw=1.4,
                  color=UNMATCHED, zorder=3,
                  label=f"not indexed by #1 ({int(missed.sum())})")
    ax.legend(loc="upper right", fontsize=8, frameon=False)

    axt.set_ylim(-len(shown) + 0.3, 0.95)
    axt.set_yticks([])
    axt.set_xlabel(r"2$\theta$ (deg)")
    axt.set_xlim(tt_lo - 1.0, tt_hi + 1.0)
    ax.set_title(title or ("ranked candidates: solid tick = predicted line with "
                           "an observed line under it, faint = predicted and "
                           "absent"), fontsize=10)
    fig.tight_layout()
    if path is not None:
        fig.savefig(path)
    return fig


def plot_validation(validation, result=None, *, path: str | None = None,
                    dpi: int = 150, title: str | None = None):
    """The Le Bail validation fit, with both detector lists marked.

    ``result`` is the :class:`~pxrdref.schemas.results.RefinementResult` from
    ``validate_by_lebail(..., with_result=True)``.  Without it only the detector
    positions can be drawn, which is a strictly worse picture and is why the
    opt-in return exists.

    Read it the way :mod:`pxrdref.indexing.workflow`'s table says to read the
    numbers: Rwp is decisive on a **wrong metric** and nearly silent on an
    **oversized** one, so the amber marks (predicted, nothing there) and the
    purple ones (observed, nothing predicted) are not decoration — they are the
    two failures the fit statistic cannot separate.
    """
    plt = _pyplot()
    absent = np.asarray(validation.predicted_but_absent_two_theta,
                        dtype=np.float64)
    unmatched = np.asarray(validation.unmatched_observed_two_theta,
                           dtype=np.float64)

    if result is None:
        fig, ax = plt.subplots(figsize=(11, 3.2), dpi=dpi)
        ax.vlines(absent, 0.0, 1.0, lw=1.0, color=ABSENT,
                  label=f"predicted but absent ({len(absent)})")
        ax.vlines(unmatched, -1.0, 0.0, lw=1.0, color=UNMATCHED,
                  label=f"unmatched observed ({len(unmatched)})")
        ax.set_yticks([])
        ax.set_xlabel(r"2$\theta$ (deg)")
        ax.legend(loc="upper right", fontsize=8, frameon=False)
        ax.set_title(title or _validation_title(validation), fontsize=10)
        fig.tight_layout()
        if path is not None:
            fig.savefig(path)
        return fig

    tt = np.asarray(result.two_theta)
    y_obs = np.asarray(result.y_obs)
    y_calc = np.asarray(result.y_calc)
    y_bkg = np.asarray(result.y_background)
    fig, (ax, axd) = plt.subplots(
        2, 1, figsize=(11, 6.4), dpi=dpi, sharex=True,
        gridspec_kw={"height_ratios": [3, 1]})
    ax.plot(tt, y_obs, ".", ms=2.0, color=OBS, label="observed", zorder=2)
    ax.plot(tt, y_calc, "-", lw=1.0, color=CALC, label="Le Bail", zorder=3)
    ax.plot(tt, y_bkg, "--", lw=0.8, color=BKG, label="background", zorder=1)

    span = float(y_obs.max() - min(y_obs.min(), 0.0))
    if len(absent):
        ax.vlines(absent, -0.05 * span, 0.02 * span, lw=1.0, color=ABSENT,
                  zorder=4, label=f"predicted but absent ({len(absent)})")
    if len(unmatched):
        for x in unmatched:
            ax.axvline(x, color=UNMATCHED, lw=0.8, ls=":", alpha=0.8, zorder=1)
        ax.plot([], [], ls=":", lw=0.8, color=UNMATCHED,
                label=f"unmatched observed ({len(unmatched)})")
    ax.set_ylabel("intensity")
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    ax.set_title(title or _validation_title(validation), fontsize=10)

    axd.plot(tt, (y_obs - y_calc) / result.sig(), "-", lw=0.6, color=DIFF)
    axd.axhspan(-3, 3, color="#2a9d2a", alpha=0.15, lw=0)
    axd.set_ylabel(r"$\Delta/\sigma$")
    axd.set_xlabel(r"2$\theta$ (deg)")
    fig.tight_layout()
    if path is not None:
        fig.savefig(path)
    return fig


def _window_from_result(result, peaks) -> np.ndarray:
    """The σ(Q) the search matched with, rebuilt from what the result records.

    ``index_pattern`` writes ``sigma_sys_deg`` into ``provenance.notes`` on
    every run precisely so a run is reproducible from what it reports; that
    plus the quality report's shift screen feed the same
    :func:`~pxrdref.indexing.engines.effective_sigma_sys` the search read.  So
    a picture drawn from a result matches in the window the candidates were
    selected under — CLAUDE.md's rule that a fitted σ is the wrong matching
    window, honoured with **no spec in hand** (WP-1043: the visual check is
    reachable from a result, not only from the suite that ran the search).
    """
    from ..indexing.engines import SearchSpec, match_window

    notes = getattr(getattr(result, "provenance", None), "notes", None) or {}
    try:
        sigma_sys = float(notes.get("sigma_sys_deg", 0.0) or 0.0)
    except (TypeError, ValueError):
        sigma_sys = 0.0
    return match_window(peaks, SearchSpec(sigma_sys_deg=sigma_sys),
                        getattr(result, "quality", None))


def plot_indexing(result, peaks, *, data=None, instrument=None,
                  candidate: int = 0, n: int = 5, validation=None,
                  path: str | None = None, dpi: int = 150):
    """The whole visual check, as a function of (result, pattern) — WP-1043.

    The user's design call made the picture part of the deliverable: one
    ranked list with stats *plus a visual check against the diffraction data*.
    Until this function the check lived only in ``tests/indexing_gallery.py``,
    which owned the composition (window reconstruction, top-candidate refit);
    now the gallery is a consumer of this call, not the owner.

    Returns ``{name: Figure}`` in drawing order, with up to three entries
    matching what the inputs allow:

    * ``"peaks"`` — always: the search's real input (over the profile when
      ``data`` is given).
    * ``"candidates"`` — when the result carries any: the ranked tick rows,
      matched in the **window the search used**, reconstructed from the
      result's own provenance notes (:func:`_window_from_result`).
    * ``"validation"`` — the Le Bail panel for ``candidates[candidate]``.
      Pass ``validation=(LeBailValidation, RefinementResult)`` from
      ``validate_by_lebail(..., with_result=True)`` to draw a fit already in
      hand; or pass ``data`` **and** ``instrument`` to run that fit here; or
      neither, and the stored positions-only panel is drawn when the
      candidate carries one.

    ``path`` is a stem: each figure is saved as ``f"{path}_{name}.png"``.
    Figures are returned open either way — closing is the caller's, exactly
    as :func:`pxrdref.plot` behaves.
    """
    figures: dict = {}
    figures["peaks"] = plot_peak_list(peaks, data, dpi=dpi)

    cands = list(getattr(result, "candidates", ()) or ())
    if cands:
        if not 0 <= candidate < len(cands):
            raise ValueError(f"candidate {candidate} is out of range for "
                             f"{len(cands)} candidate(s)")
        figures["candidates"] = plot_candidates(
            cands, peaks, n=n, dpi=dpi,
            q_match=_window_from_result(result, peaks))
        chosen = cands[candidate]
        if validation is None and data is not None and instrument is not None:
            from ..indexing.workflow import validate_by_lebail

            validation = validate_by_lebail(chosen, data, instrument,
                                            peaks=peaks, with_result=True)
        if validation is not None:
            val, fit = validation
            figures["validation"] = plot_validation(val, fit, dpi=dpi)
        elif chosen.lebail is not None:
            # positions only — strictly worse than the fit panel and drawn
            # anyway: the two detector lists are what separate a wrong metric
            # from an oversized one, and they need no refit
            figures["validation"] = plot_validation(chosen.lebail, dpi=dpi)

    if path is not None:
        for name, fig in figures.items():
            fig.savefig(f"{path}_{name}.png")
    return figures


def _validation_title(validation) -> str:
    return (f"Le Bail validation of {validation.space_group}: "
            f"Rwp={validation.rwp:.4f}, GoF={validation.gof:.2f}, "
            f"{validation.predicted_but_absent}/{validation.n_reflections} "
            f"predicted but absent, {validation.unmatched_observed} unmatched "
            f"observed  [{validation.status}]")


__all__ = ["CANDIDATE_COLORS", "plot_candidates", "plot_indexing",
           "plot_peak_list", "plot_validation"]
