"""Measured powder pattern container."""

from __future__ import annotations

import numpy as np
from pydantic import Field, model_validator

from .common import Base


def _floor_sigma(s: np.ndarray) -> np.ndarray:
    """``s`` with zero and negative esds raised to a floor, so no channel takes
    an infinite weight.

    The floor is a thousandth of the column's median positive esd, and nothing
    else. It used to be ``max(1e-3, …)`` as well — an absolute number in
    whatever units the intensity happened to be in, which never binds on counts
    (median esd ≥ 1) and silently raised every esd of a normalised pattern,
    whose esds sit near 1e-3 and below, to 1e-3 (#650). A column with no
    positive entry has no scale to be relative to, and keeps 1.0.

    One rule for :meth:`PatternData.sig` and
    :meth:`~rietx.schemas.results.RefinementResult.sig`, so the two cannot
    drift apart.
    """
    floor = float(np.median(s[s > 0])) * 1e-3 if np.any(s > 0) else 1.0
    return np.maximum(s, floor)


class PatternData(Base):
    """A 1-D constant-wavelength powder pattern.

    Numbers out: ``tt()``, ``y()``, ``sig()`` — numpy views of the two theta,
    intensity and per-point σ; the fields themselves stay plain lists so the
    model round-trips through JSON.

    ``sigma`` is the per-point standard deviation of the intensity.  When it is
    absent the refinement assumes raw Poisson counting statistics,
    σᵢ = √max(yᵢ, 1) — which is *invalid* for normalised/merged/smoothed data;
    readers populate ``sigma`` from the file whenever the format carries it
    (e.g. the third column of ``.xye`` / GSAS ESD files).
    """

    two_theta: list[float]
    intensity: list[float]
    sigma: list[float] | None = None
    excluded_regions: list[tuple[float, float]] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> "PatternData":
        n = len(self.two_theta)
        if n < 2:
            raise ValueError("pattern needs at least 2 points")
        if len(self.intensity) != n:
            raise ValueError("two_theta and intensity differ in length")
        if self.sigma is not None and len(self.sigma) != n:
            raise ValueError("sigma length does not match two_theta")
        tt = np.asarray(self.two_theta)
        if not np.all(np.diff(tt) > 0):
            raise ValueError("two_theta must be strictly increasing")
        return self

    # -- numpy views -------------------------------------------------------
    def tt(self) -> np.ndarray:
        return np.asarray(self.two_theta, dtype=np.float64)

    def y(self) -> np.ndarray:
        return np.asarray(self.intensity, dtype=np.float64)

    def sig(self) -> np.ndarray:
        """Per-point σ, applying the Poisson fallback where needed."""
        if self.sigma is not None:
            return _floor_sigma(np.asarray(self.sigma, dtype=np.float64))
        y = self.y()
        return np.sqrt(np.maximum(y, 1.0))

    def in_range_mask(self) -> np.ndarray:
        """True for points kept in the fit (excluded_regions removed)."""
        tt = self.tt()
        mask = np.ones(tt.shape, dtype=bool)
        for lo, hi in self.excluded_regions:
            mask &= ~((tt >= lo) & (tt <= hi))
        return mask

    def __str__(self) -> str:
        """The range and step on one line, then what was measured beside it
        (WP-1544). ``sigma: None`` and an empty ``excluded_regions`` are printed,
        because whether the file carried σ decides the weights."""
        from .._display import tree
        tt = self.tt()
        head = (f"PatternData of {tt.size} points, {tt[0]:g}–{tt[-1]:g}° 2θ, "
                f"median step {float(np.median(np.diff(tt))):.4g}°")
        return tree(self, order=("intensity", "sigma", "excluded_regions", "metadata"),
                    show_empty=True, head=head)

    def plot(self, path: str | None = None, **kw):
        """Draw the pattern with no model: :func:`rietx.viz.plots.plot_pattern`,
        the peer of :meth:`RefinementResult.plot`, forwarding ``**kw``."""
        from ..viz.plots import plot_pattern

        return plot_pattern(self, path=path, **kw)

    def crop(self, lo: float, hi: float) -> "PatternData":
        tt = self.tt()
        keep = (tt >= lo) & (tt <= hi)
        return PatternData(
            two_theta=tt[keep].tolist(),
            intensity=self.y()[keep].tolist(),
            sigma=None if self.sigma is None else np.asarray(self.sigma)[keep].tolist(),
            excluded_regions=self.excluded_regions,
            metadata=self.metadata,
        )
