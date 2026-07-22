"""Refinement result schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Base, Diagnostic, Provenance


class RefinedParameter(Base):
    path: str
    value: float
    stderr: float | None = None
    initial: float | None = None
    vary: bool = True
    at_bound: bool = False


class Statistics(Base):
    """Agreement indices, defined per Toby (2006), Powder Diffraction 21, 67.

    ``rwp_background_subtracted`` re-evaluates Rwp with the background removed
    from both y_obs and y_calc, which Toby recommends as the more meaningful
    number when the background is a large fraction of the signal.
    """

    rwp: float
    rp: float
    rexp: float
    chi2: float
    gof: float
    rwp_background_subtracted: float | None = None
    durbin_watson: float | None = None
    n_points: int
    n_free_parameters: int


class IterationRecord(Base):
    stage: str
    iteration: int
    cost: float
    grad_norm: float | None = None
    step_norm: float | None = None


class StageResult(Base):
    name: str
    status: Literal["converged", "max_iter", "diverged", "skipped"]
    n_iterations: int
    cost_initial: float
    cost_final: float
    freed: list[str] = Field(default_factory=list)


class RefinementResult(Base):
    status: Literal["converged", "max_iter", "diverged"]
    mode: Literal["rietveld", "lebail"]
    parameters: list[RefinedParameter]
    statistics: Statistics
    correlation_warnings: list[str] = Field(default_factory=list)
    stages: list[StageResult] = Field(default_factory=list)
    history: list[IterationRecord] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    provenance: Provenance

    # Arrays for plotting/export (kept as lists for JSON round-trip; use
    # the exporters for column files).
    two_theta: list[float] = Field(default_factory=list)
    y_obs: list[float] = Field(default_factory=list)
    y_calc: list[float] = Field(default_factory=list)
    y_background: list[float] = Field(default_factory=list)
    # per-phase reflection tick positions (deg 2θ)
    ticks: dict[str, list[float]] = Field(default_factory=dict)

    def plot(self, path: str | None = None, **kw):
        from ..viz.plots import plot_result

        return plot_result(self, path=path, **kw)

    def parameter(self, path: str) -> RefinedParameter:
        for p in self.parameters:
            if p.path == path:
                return p
        raise KeyError(path)
