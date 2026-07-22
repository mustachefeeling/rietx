"""Weighted least-squares driver on scipy's Trust Region Reflective solver.

Minimises  S(θ) = Σ_i w_i (y_obs,i − y_calc,i(θ))²,  w_i = 1/σ_i²
(Rietveld 1969; weights per counting statistics — see PatternData.sig).

The Jacobian combines *exact analytic columns* for parameters the model is
linear in (the Chebyshev background coefficients, whose columns are the design
matrix rows, and — in Rietveld mode — the phase scale factors, whose columns
are the per-phase Bragg component divided by the scale) with forward finite
differences for the remaining, nonlinear parameters.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from ..model.forward import CompiledModel
from ..params.transforms import dphys_dinternal
from ..params.vector import ParameterTable


@dataclass
class LSQOutcome:
    theta: np.ndarray
    cost_initial: float
    cost_final: float
    n_iterations: int
    status: str  # "converged" | "max_iter" | "diverged"
    jac: np.ndarray | None
    stderr_internal: np.ndarray | None
    correlation: np.ndarray | None


def _make_residual(model: CompiledModel, table: ParameterTable):
    sqrt_w = 1.0 / model.sigma

    def residual(theta: np.ndarray) -> np.ndarray:
        values = table.decode(theta)
        return sqrt_w * (model.y_obs - model.evaluate(values))

    return residual


def _make_jacobian(model: CompiledModel, table: ParameterTable):
    """Mixed analytic/FD Jacobian of the residual w.r.t. the internal vector."""
    sqrt_w = 1.0 / model.sigma
    free = table.free_paths

    cheb_paths = {f"instrument.background.c{n}": n for n in range(model.n_cheb)}
    scale_paths = {f"phases.{ip}.scale": ip for ip in range(len(model.phases))}

    def jacobian(theta: np.ndarray) -> np.ndarray:
        values = table.decode(theta)
        J = np.empty((len(model.tt), len(theta)), dtype=np.float64)
        fd_cols = []
        for c, path in enumerate(free):
            if path in cheb_paths:
                # y is linear in the coefficient: ∂y/∂c_n = T_n(x); residual = −√w·∂y
                J[:, c] = -sqrt_w * model.cheb_design[cheb_paths[path]]
            elif path in scale_paths and model.mode == "rietveld":
                ip = scale_paths[path]
                scale = values[path]
                if scale > 1e-30:
                    # Bragg component of this phase is proportional to its scale
                    contrib = _phase_component(model, ip, values)
                    dy_dscale = contrib / scale
                    e = table.entries[table._paths[path]]
                    idx_free = free.index(path)
                    dpdu = dphys_dinternal(float(theta[idx_free]), e.transform)
                    J[:, c] = -sqrt_w * dy_dscale * dpdu
                else:
                    fd_cols.append(c)
            else:
                fd_cols.append(c)

        if fd_cols:
            r0 = sqrt_w * (model.y_obs - model.evaluate(values))
            for c in fd_cols:
                h = 1e-6 * max(1.0, abs(theta[c]))
                tp = theta.copy()
                tp[c] += h
                rp = sqrt_w * (model.y_obs - model.evaluate(table.decode(tp)))
                J[:, c] = (rp - r0) / h
        return J

    return jacobian


def _phase_component(model: CompiledModel, ip: int, values: dict[str, float]) -> np.ndarray:
    from ..model.profiles.pseudovoigt import pseudo_voigt

    cp = model.phases[ip]
    pos, gamma, eta, intensity = model.phase_peaks(ip, values)
    y = np.zeros_like(model.tt)
    for k in range(len(pos)):
        i0, i1 = cp.win[k]
        if i1 <= i0 or not np.isfinite(pos[k]):
            continue
        y[i0:i1] += intensity[k] * pseudo_voigt(model.tt[i0:i1] - pos[k], gamma[k], eta[k])
    return y


def run_least_squares(model: CompiledModel, table: ParameterTable,
                      *, max_iter: int = 100, ftol: float = 1e-9,
                      compute_uncertainties: bool = True) -> LSQOutcome:
    residual = _make_residual(model, table)
    jacobian = _make_jacobian(model, table)
    x0 = table.x0()
    lo, hi = table.bounds()
    # TRF requires x0 strictly inside the bounds
    x0 = np.clip(x0, lo + 1e-12, hi - 1e-12) if len(x0) else x0

    r0 = residual(x0)
    cost0 = 0.5 * float(r0 @ r0)
    if len(x0) == 0:
        return LSQOutcome(x0, cost0, cost0, 0, "converged", None, None, None)

    res = least_squares(residual, x0, jac=jacobian, bounds=(lo, hi), method="trf",
                        ftol=ftol, xtol=1e-12, gtol=1e-12, max_nfev=max_iter * max(len(x0), 1))
    status = "converged" if res.status > 0 else ("max_iter" if res.status == 0 else "diverged")

    stderr = corr = None
    if compute_uncertainties and res.jac is not None and len(res.fun) > len(res.x):
        stderr, corr = covariance_estimates(res.jac, res.fun, len(res.x))
    return LSQOutcome(res.x, cost0, float(res.cost), int(res.nfev), status,
                      np.asarray(res.jac) if res.jac is not None else None, stderr, corr)


def covariance_estimates(jac: np.ndarray, fun: np.ndarray, n_free: int
                         ) -> tuple[np.ndarray, np.ndarray]:
    """Esds and correlation matrix from the weighted Jacobian at the solution.

    Cov = χ²_red · (JᵀJ)⁻¹ with χ²_red = Σr²/(N−P); esd_i = √Cov_ii.
    (Toby 2006; the Bérar-Lelann serial-correlation inflation is v0.2.)
    A pseudo-inverse guards against singular normal matrices.
    """
    JTJ = jac.T @ jac
    chi2_red = float(fun @ fun) / max(len(fun) - n_free, 1)
    cov = np.linalg.pinv(JTJ) * chi2_red
    diag = np.sqrt(np.maximum(np.diag(cov), 0.0))
    denom = np.outer(diag, diag)
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.where(denom > 0, cov / denom, 0.0)
    return diag, corr
