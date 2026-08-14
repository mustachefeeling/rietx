"""Measured powder pattern container."""

from __future__ import annotations

import numpy as np
from pydantic import Field, model_validator

from .common import Base


class PatternData(Base):
    """A 1-D constant-wavelength powder pattern.

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
            s = np.asarray(self.sigma, dtype=np.float64)
            # guard against zero/negative reported esds
            floor = max(1e-3, float(np.median(s[s > 0])) * 1e-3) if np.any(s > 0) else 1.0
            return np.maximum(s, floor)
        y = self.y()
        return np.sqrt(np.maximum(y, 1.0))

    def in_range_mask(self) -> np.ndarray:
        """True for points kept in the fit (excluded_regions removed)."""
        tt = self.tt()
        mask = np.ones(tt.shape, dtype=bool)
        for lo, hi in self.excluded_regions:
            mask &= ~((tt >= lo) & (tt <= hi))
        return mask

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
