"""One-call background automation: diagnose → select → build the model.

``auto_background(pattern)`` is the v0.2 default entry: it returns a
configured, refinable :class:`~rietx.schemas.instrument.BackgroundPSpline`
(or Chebyshev on request) whose complexity was chosen by the BIC +
Durbin-Watson machinery in :mod:`.select`, with the 1/x air-scatter term
enabled when the diagnostics flag a low-angle rise.
"""

from __future__ import annotations

from ..schemas.common import Parameter
from ..schemas.instrument import Background, BackgroundChebyshev, BackgroundPSpline
from ..schemas.pattern import PatternData
from ..schemas.project import check_interval
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
#: fewest fitted channels ``two_theta_limits`` may leave: ``compile_model``'s
#: own floor, below which no fit runs (and ``diagnose`` divides by zero at 2)
_MIN_FIT_CHANNELS = 10


def auto_background(data: PatternData, *, kind: str = "pspline",
                    diagnostics: PatternDiagnostics | None = None,
                    wavelength: float | None = None,
                    two_theta_limits: tuple[float, float] | None = None) -> Background:
    """Build a background model sized to the pattern.

    ``kind="pspline"`` (default): penalized co-refined spline — knot spacing
    from the amorphous-hump score, moderate fixed λ (the second-difference
    penalty rows keep it stiff against Bragg intensity), air term on
    diagnostic trigger.  ``kind="chebyshev"``: order from masked-channel
    BIC + Durbin-Watson stop.

    ``two_theta_limits`` is the range the fit will use, the same tuple
    ``fit`` takes.  The diagnostics, the order selection and the knots are
    all taken over it.  Without it the knots span the whole file, and every
    coefficient past the fitted range is held by the penalty alone, which
    extends the curve to wherever its slope points (WP-1454: on a private
    series, negative from 75° past a 40° limit).  ``diagnostics`` supplied by the
    caller are used as given, and the knots are still confined to the limits.
    """
    if two_theta_limits is not None:
        lo, hi = (float(v) for v in two_theta_limits)
        check_interval("two_theta_limits", lo, hi)
        # the channels a fit under these limits uses, asked of the one
        # authority for that (WP-1033); imported here, since project sits
        # above this package
        from ..project import fitted_mask

        n_fit = int(fitted_mask(data, (lo, hi)).sum())
        if n_fit < _MIN_FIT_CHANNELS:
            raise ValueError(
                f"two_theta_limits ({lo}, {hi}) leave {n_fit} fitted channels, "
                f"fewer than the {_MIN_FIT_CHANNELS} a fit needs")
        data = data.crop(lo, hi)
    diag = diagnostics or diagnose(data, wavelength=wavelength)
    if kind == "chebyshev":
        sel = select_chebyshev_order(data)
        return BackgroundChebyshev.with_terms(int(sel.selected))
    if kind != "pspline":
        raise ValueError(f"unknown background kind {kind!r}")

    step = (_KNOT_STEP_HUMPY_DEG if diag.amorphous_hump_score > HUMP_TRIGGER
            else _KNOT_STEP_SMOOTH_DEG)
    k_lo, k_hi = diag.two_theta_min, diag.two_theta_max
    if two_theta_limits is not None:
        k_lo, k_hi = max(k_lo, lo), min(k_hi, hi)
        if k_lo >= k_hi:  # caller's diagnostics cover none of the limits
            raise ValueError(
                f"the supplied diagnostics span {diag.two_theta_min:g}-"
                f"{diag.two_theta_max:g}°, which does not overlap "
                f"two_theta_limits ({lo}, {hi})")
    bkg = BackgroundPSpline.for_range(k_lo, k_hi, knot_step_deg=step,
                                      lambda_smooth=1.0)
    # Declined means absent, never a zero one: a plan's ``instrument.background.*``
    # frees whatever path exists (WP-1454).
    if diag.air_scatter_gain > AIR_SCATTER_TRIGGER:
        bkg.air_scatter = Parameter(value=1e-3, vary=True, min=0.0,
                                    transform="softplus")
    return bkg
