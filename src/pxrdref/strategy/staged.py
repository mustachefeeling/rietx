"""Minimal staged refinement runner.

Encodes the IUCr-guideline practice of turning parameter groups on
cumulatively in a stable order (McCusker, Von Dreele, Cox, Louër & Scardi,
1999, J. Appl. Cryst. 32, 36): scale + background first, then peak positions
(zero/cell), then profile widths.  Each stage runs the bounded least squares
to convergence before the next group is freed; the reflection list and
evaluation windows are regenerated between stages (the differentiability
invariant — they stay frozen *within* a stage).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Stage:
    name: str
    turn_on: list[str]  # path globs, e.g. "phases.*.cell.*"
    max_iter: int = 100
    lebail_cycles: int = 3  # intensity-partitioning refreshes (lebail mode)


@dataclass
class RefinementPlan:
    stages: list[Stage]
    correlation_guard: float = 0.98

    @classmethod
    def mccusker_default(cls) -> "RefinementPlan":
        """Default staged plan for a Rietveld run (McCusker et al., 1999)."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
        ])

    @classmethod
    def profile_only(cls) -> "RefinementPlan":
        """Le Bail-style plan: no structural parameters exist to free."""
        return cls(stages=[
            Stage("bkg", ["instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
        ])


PLAN_PRESETS = {
    "mccusker_default": RefinementPlan.mccusker_default,
    "profile_only": RefinementPlan.profile_only,
}


@dataclass
class GuardReport:
    high_correlations: list[str] = field(default_factory=list)
    at_bounds: list[str] = field(default_factory=list)


def check_guards(table, outcome, threshold: float) -> GuardReport:
    """Correlation and bound guards evaluated after each stage."""
    import numpy as np

    report = GuardReport()
    free = table.free_paths
    if outcome.correlation is not None and len(free) > 1:
        corr = np.asarray(outcome.correlation)
        for i in range(len(free)):
            for j in range(i + 1, len(free)):
                if abs(corr[i, j]) > threshold:
                    report.high_correlations.append(
                        f"{free[i]} ~ {free[j]} (ρ={corr[i, j]:+.3f})")
    lo, hi = table.bounds()
    for k, path in enumerate(free):
        t = outcome.theta[k]
        span = hi[k] - lo[k]
        tol = 1e-8 * (span if np.isfinite(span) else 1.0)
        if (np.isfinite(lo[k]) and t - lo[k] <= tol) or (np.isfinite(hi[k]) and hi[k] - t <= tol):
            report.at_bounds.append(path)
    return report
