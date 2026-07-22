"""Weighted least-squares driver on scipy's Trust Region Reflective solver.

Minimises  S(θ) = Σ_i w_i (y_obs,i − y_calc,i(θ))²,  w_i = 1/σ_i²
(Rietveld 1969; weights per counting statistics — see PatternData.sig).

The Jacobian is assembled column-by-column, preferring exact work over
full-model finite differences:

* **linear columns** — Chebyshev background coefficients (design-matrix rows);
* **peak-chain columns** — every parameter whose effect flows through the
  per-peak scalars (position, Γ, η, intensity): cell constants, zero shift,
  displacement/transparency, Caglioti U V W, size/strain X Y, scales,
  occupancies, Biso, polarization, emission-line weights.  The expensive
  per-point part uses the analytic profile derivatives
  (``CompiledModel.derivative_bases``); the per-reflection scalar derivatives
  are finite-differenced through ``phase_peaks`` (cheap — no per-point work);
* **axial columns** — S/L, H/L through the analytic node-weighted bases;
* **plain forward differences** — anything else (fallback only).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from ..model.forward import CompiledModel, DerivativeBases
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
        r = sqrt_w * (model.y_obs - model.evaluate(values))
        pen = model.penalty_residual(values)
        return r if pen is None else np.concatenate([r, pen])

    return residual


def _peak_chain_column(model: CompiledModel, table: ParameterTable,
                       bases: DerivativeBases, theta: np.ndarray,
                       values: dict[str, float], c: int, path: str) -> np.ndarray:
    """∂y/∂θ_c via the analytic bases + per-reflection scalar FD.

    Only the phases the path touches are re-derived (``phases.2.…`` leaves
    the others' scalars untouched; instrument paths touch all).
    """
    h = 1e-6 * max(1.0, abs(theta[c]))
    tp = theta.copy()
    tp[c] += h
    values_p = table.decode(tp)
    if path.startswith("phases."):
        affected = [int(path.split(".")[1])]
    else:
        affected = range(len(model.phases))

    dy = np.zeros_like(model.tt)
    for ip in affected:
        peaks_p = model.phase_peaks(ip, values_p)
        peaks_0 = bases.peaks[ip]
        for (il, k, i0, i1, omega, d_pos, d_gamma, d_eta, _dsl, _dhl) in bases.entries[ip]:
            pos0, gam0, eta0, int0 = peaks_0[il]
            pos1, gam1, eta1, int1 = peaks_p[il]
            if not (np.isfinite(pos1[k]) and np.isfinite(pos0[k])):
                continue
            d_i = (int1[k] - int0[k]) / h
            d_p = (pos1[k] - pos0[k]) / h
            d_g = (gam1[k] - gam0[k]) / h
            d_e = (eta1[k] - eta0[k]) / h
            col = dy[i0:i1]
            if d_i != 0.0:
                col += d_i * omega
            if int0[k] != 0.0:
                if d_p != 0.0:
                    col += (int0[k] * d_p) * d_pos
                if d_g != 0.0:
                    col += (int0[k] * d_g) * d_gamma
                if d_e != 0.0:
                    col += (int0[k] * d_e) * d_eta
    return dy


def _axial_column(model: CompiledModel, bases: DerivativeBases,
                  which: int, dpdu: float) -> np.ndarray:
    """∂y/∂θ_c for S/L (which=8) or H/L (which=9) from the node-FD bases."""
    dy = np.zeros_like(model.tt)
    for ip, rows in enumerate(bases.entries):
        for row in rows:
            il, k, i0, i1 = row[0], row[1], row[2], row[3]
            d_ax = row[which]
            if d_ax is None:
                continue
            intensity = bases.peaks[ip][il][3][k]
            if intensity != 0.0:
                dy[i0:i1] += (intensity * dpdu) * d_ax
    return dy


def _make_jacobian(model: CompiledModel, table: ParameterTable):
    """Mixed analytic/FD Jacobian of the residual w.r.t. the internal vector."""
    sqrt_w = 1.0 / model.sigma
    free = table.free_paths
    n_data = len(model.tt)
    n_pen = 0 if model.bkg_penalty is None else model.bkg_penalty.shape[0]

    bkg_cols = {path: n for n, path in enumerate(model.bkg_paths)}
    axial_paths = {"instrument.geometry.axial_sl": 8, "instrument.geometry.axial_hl": 9}

    def dpdu_of(c: int, theta: np.ndarray) -> float:
        e = table.entries[table._paths[free[c]]]
        return dphys_dinternal(float(theta[c]), e.transform)

    def jacobian(theta: np.ndarray) -> np.ndarray:
        values = table.decode(theta)
        J = np.zeros((n_data + n_pen, len(theta)), dtype=np.float64)
        fd_cols = []
        bases: DerivativeBases | None = None

        def get_bases() -> DerivativeBases:
            nonlocal bases
            if bases is None:
                bases = model.derivative_bases(values)
            return bases

        for c, path in enumerate(free):
            if path in bkg_cols:
                # y is linear in the coefficient: ∂y/∂c_n = basis row; the
                # penalty rows are linear too (√λ·D₂), chain-ruled through
                # the transform for the (softplus-bounded) air term
                n = bkg_cols[path]
                dpdu = dpdu_of(c, theta)
                J[:n_data, c] = -sqrt_w * model.bkg_design[n] * dpdu
                if n_pen:
                    J[n_data:, c] = model.bkg_penalty[:, n] * dpdu
            elif path in axial_paths:
                b = get_bases()
                if b.axial_ok:
                    J[:n_data, c] = -sqrt_w * _axial_column(
                        model, b, axial_paths[path], dpdu_of(c, theta))
                else:
                    fd_cols.append(c)
            elif model.scalar_chain_supported(path):
                J[:n_data, c] = -sqrt_w * _peak_chain_column(
                    model, table, get_bases(), theta, values, c, path)
            else:
                fd_cols.append(c)

        if fd_cols:
            r0 = sqrt_w * (model.y_obs - model.evaluate(values))
            for c in fd_cols:
                h = 1e-6 * max(1.0, abs(theta[c]))
                tp = theta.copy()
                tp[c] += h
                rp = sqrt_w * (model.y_obs - model.evaluate(table.decode(tp)))
                J[:n_data, c] = (rp - r0) / h
        return J

    return jacobian


def run_least_squares(model: CompiledModel, table: ParameterTable,
                      *, max_iter: int = 100, ftol: float = 1e-9,
                      compute_uncertainties: bool = True,
                      events=None, stage: str = "") -> LSQOutcome:
    residual = _make_residual(model, table)
    jacobian = _make_jacobian(model, table)

    if events is not None:
        # scipy TRF has no per-iteration callback, so the residual closure is
        # the hook; the emitted dict is plain floats (no pydantic here)
        inner = residual
        counter = {"n": 0}

        def residual(theta: np.ndarray):
            r = inner(theta)
            counter["n"] += 1
            events.emit("eval", stage=stage, n_eval=counter["n"],
                        cost=0.5 * float(r @ r))
            return r
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
        stderr, corr = covariance_estimates(res.jac, res.fun, len(res.x),
                                            n_data=len(model.tt))
    return LSQOutcome(res.x, cost0, float(res.cost), int(res.nfev), status,
                      np.asarray(res.jac) if res.jac is not None else None, stderr, corr)


def covariance_estimates(jac: np.ndarray, fun: np.ndarray, n_free: int,
                         n_data: int | None = None
                         ) -> tuple[np.ndarray, np.ndarray]:
    """Esds and correlation matrix from the weighted Jacobian at the solution.

    Cov = χ²_red · (JᵀJ)⁻¹ with χ²_red = Σr²/(N−P); esd_i = √Cov_ii, then
    multiplied by the Bérar-Lelann serial-correlation factor (Bérar & Lelann,
    1991, J. Appl. Cryst. 24, 1 — see ``statistics.berar_lelann_factor``);
    the factor cancels in the correlation matrix.
    A pseudo-inverse guards against singular normal matrices.

    With P-spline penalty rows appended (rows beyond ``n_data``), JᵀJ keeps
    them — (J_dᵀJ_d + λD₂ᵀD₂)⁻¹ is the regularised covariance — but χ² and
    the serial-correlation factor are evaluated on the *data* rows only
    (run-of-sign statistics on penalty rows would be meaningless).
    """
    from .statistics import berar_lelann_factor

    data = fun if n_data is None else fun[:n_data]
    JTJ = jac.T @ jac
    chi2_red = float(data @ data) / max(len(data) - n_free, 1)
    cov = np.linalg.pinv(JTJ) * chi2_red
    diag = np.sqrt(np.maximum(np.diag(cov), 0.0)) * berar_lelann_factor(data)
    denom = np.outer(diag, diag)
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.where(denom > 0, cov / denom, 0.0)
    return diag, corr
