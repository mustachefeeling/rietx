"""One-call background automation: diagnose → select → build the model.

``auto_background(pattern)`` is the v0.2 default entry: it returns a
configured, refinable :class:`~pxrdref.schemas.instrument.BackgroundPSpline`
(or Chebyshev on request) whose complexity was chosen by the BIC +
Durbin-Watson machinery in :mod:`.select`, with the 1/x air-scatter term
enabled when the diagnostics flag a low-angle rise.
"""

from __future__ import annotations

from ..schemas.common import Parameter
from ..schemas.instrument import Background, BackgroundChebyshev, BackgroundPSpline
from ..schemas.pattern import PatternData
from .diagnostics import PatternDiagnostics, diagnose
from .select import select_chebyshev_order

#: nested-fit gain from the 1/(2θ) column that turns the air term on
AIR_SCATTER_TRIGGER = 0.3
#: envelope residual (relative to level) beyond a cubic + 1/x that calls for
#: a more flexible (finer-knot) background
HUMP_TRIGGER = 0.05
#: P-spline knot spacing scales inversely with how busy the baseline is
_KNOT_STEP_SMOOTH_DEG = 8.0
_KNOT_STEP_HUMPY_DEG = 3.0


def auto_background(data: PatternData, *, kind: str = "pspline",
                    diagnostics: PatternDiagnostics | None = None,
                    wavelength: float | None = None) -> Background:
    """Build a background model sized to the pattern.

    ``kind="pspline"`` (default): penalized co-refined spline — knot spacing
    from the amorphous-hump score, moderate fixed λ (the second-difference
    penalty rows keep it stiff against Bragg intensity), air term on
    diagnostic trigger.  ``kind="chebyshev"``: order from masked-channel
    BIC + Durbin-Watson stop.
    """
    diag = diagnostics or diagnose(data, wavelength=wavelength)
    if kind == "chebyshev":
        sel = select_chebyshev_order(data)
        return BackgroundChebyshev.with_terms(int(sel.selected))
    if kind != "pspline":
        raise ValueError(f"unknown background kind {kind!r}")

    step = (_KNOT_STEP_HUMPY_DEG if diag.amorphous_hump_score > HUMP_TRIGGER
            else _KNOT_STEP_SMOOTH_DEG)
    bkg = BackgroundPSpline.for_range(diag.two_theta_min, diag.two_theta_max,
                                      knot_step_deg=step, lambda_smooth=1.0)
    if diag.air_scatter_gain > AIR_SCATTER_TRIGGER:
        bkg.air_scatter = Parameter(value=1e-3, vary=True, min=0.0,
                                    transform="softplus")
    return bkg
