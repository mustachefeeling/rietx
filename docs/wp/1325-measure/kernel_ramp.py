"""WP-1325 task 2: a kernel over the coordinates, where one pattern cannot see the parameter.

    .venv/bin/python docs/wp/1325-measure/kernel_ramp.py [--seeds=N] [--regimes=W,O]
        [--truths=line,curve,kink] [--src=DIR] [--out=FILE]

Run from the repository root.  ``--src`` is the ``src`` directory to import
rietx from (default: this repository's own); the ``tests`` package is taken
from beside it, and both are put on ``sys.path`` *before* rietx is imported,
so a frozen copy of the tree can be measured while the working tree moves.
``--out`` defaults to ``kernel_results.txt`` beside this file; every line is
also printed.

**The ramp.**  Ten patterns at T = 300…1200 K built like
``tests/test_sequential.py``'s ``_simulate`` (Debye-Scherrer, λ = 0.4139 Å,
2θ = 3-24°, Poisson noise): the LaB₆ major phase on that file's line, plus a
**minor phase**, CaF₂ (F m -3 m, a = 5.4631 Å, built as
``tests/test_qpa_multimodal.py`` builds it), whose peaks sit apart from
LaB₆'s.  The quantity of interest is the minor phase's cell a_m(T).  Its
truth is one of three shapes over t = (T − 750 K)/450 K, with L = a_m·r·4.5
the line's half excursion (r the fractional expansion per 100 K):

* ``line``  a_m = a_mid + L·t;
* ``curve`` a_m = a_mid + L·t + (L/2)·(t² − 1) -- equal to the line at both
  ends, bowed L/2 below it at mid-ramp, slope rising from 0 to 2L; as steep a
  curve as stays monotone;
* ``kink``  a_m = a_mid + L·t for t ≤ 0 and a_mid + (L/2)·t after: the slope
  halves at T_c = 750 K, between patterns 4 and 5.

**Two regimes.**  The minor phase's scale per pattern is set so that its
*conditional* support -- ``CompiledModel.phase_support`` on the noise-free
curve's σ, the scale's z with every other column held -- takes a designed
value (calibrated at the start, printed in the header).

* **W** (weak, dissolving): sharp peaks, support falling 0.6× a pattern from
  30, so the scale's marginal significance crosses the WP-1301 3σ hold in
  roughly the last third to half of the ramp and the chain's trajectory has
  gaps.  r = 2.5e-4 per 100 K, a step of ~0.3 FWHM at 2θ = 20° so the warm
  start does not lose the phase by lag alone.
* **O** (broad, overlapped): the minor phase size-broadened (``lor_size``
  0.4°, held at its truth in every fit) so its peaks spread across LaB₆'s,
  at a constant support.  r = 5e-4.  Built so one pattern's cell esd is
  several times the step between neighbours.

**Arms** (each an estimator of a_m at every pattern):

1. ``chain`` -- ``refine_sequential`` (the warm-started chain, not
   independent fits) under ``mccusker_default``.  Where the WP-1301 hold
   leaves the minor cell out of a pattern's result, that pattern is a *gap*.
2. ``line`` -- weighted least-squares line [1, t] through the surviving chain
   points, W = 1/esd².
3. ``gp`` -- a Gaussian process fitted afterwards on the surviving points:
   explicit linear mean [1, t], Matérn-3/2 kernel s²·(1 + √3 r/ℓ)·e^(−√3 r/ℓ)
   over t, noise = each point's chain variance; s and ℓ by REML (the mean's
   coefficients profiled), s floored at 2 % of the median chain esd; the
   latent value and its variance at every pattern by universal kriging.
4. ``tie`` -- the hard parametric tie: one ``MultiHistogramRefinement`` with
   ``SharingMap(per_histogram=["phases.*"])`` and the minor cell tied in every
   table to vars.a0 + vars.a1·t_h, as ``synthetic_ramp.py`` ties LaB₆'s.
5. ``kernel`` -- the same joint fit with the minor cell its own column per
   pattern, ``vars.c0``/``vars.c1`` shared and read by nothing in the model,
   and N prior rows R(p − Φc) appended to the joint residual, RᵀR = K⁻¹,
   Φ = [1, t], K the GP's kernel at its REML hyperparameters, frozen.  The
   joint path refuses model restraints, so the rows are appended by wrapping
   ``optimize.least_squares._multi_closures`` inside this script only.  They
   sit after the data rows, so χ²_red and the Bérar-Lelann factor are taken
   on the data alone; the reported covariance is χ²_red·BL²·(JᵀJ)⁻¹ over all
   rows, the prior's included, which is how the package treats its own
   penalty rows.

Two sensitivity arms beside them, because REML on the surviving points
cannot see a bend that only the gaps hold: ``gp_fix`` and ``kernel_fix`` are
arms 3 and 5 with the hyperparameters set by hand from the design, s = L/4
and ℓ = 1 (half the ramp in t), never estimated.  Their pair isolates what
fitting *inside* buys at one kernel: the same prior, once on the chain's
survivors afterwards and once over every pattern's data.

All three joint arms start every histogram at the chain's answer for that pattern
(LaB₆ cell and scale, minor scale, zero, profile, background), and the minor
cell at the line's (``tie``) or the GP's (``kernel``) prediction: the joint
optimum is the comparison, not its basin of attraction.  The plan is
``mccusker_default`` with ``vars.*`` freed in its cell stage.

Per pattern the kernel arm reports the **data share** h_k = diag[Σ_p·I_p]:
I_p the data information on the minor cells with every other column
profiled out (the Schur complement of the data rows' normal matrix),
Σ_p the minor-cell block of (J_dᵀJ_d + J_priorᵀJ_prior)⁻¹ -- the
generalisation of diag[(I + K⁻¹)⁻¹·I] with c eliminated -- and tr(H) = Σh_k.

**Metrics** per (regime, truth, arm) over seeds: RMSE against the truth over
the patterns the chain kept, over its gaps and over all patterns the arm
gives; coverage |est − truth| ≤ 1 and 2 esd; for ``line`` the slope a₁'s
bias, scatter and mean esd; the minor phase's Hill-Howard weight fraction
against its truth (true scales and cells, the fit's own cell masses, the
formula checked against the package's W on every kept chain pattern) for
chain, tie and the kernels, split the same way; wall clock as ranges.
``RIETX_TELEMETRY=0`` keeps every fit from writing a run directory.
"""

from __future__ import annotations

import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REGIME_NAMES = ("W", "O")
TRUTH_NAMES = ("line", "curve", "kink")
USAGE = ("usage: kernel_ramp.py [--seeds=N] [--regimes=W,O] [--truths=line,curve,kink] "
         "[--src=DIR] [--out=FILE]")


def parse_args(argv: list[str]) -> dict:
    """``--key=value`` options, each refused by name when malformed."""
    opts = {"seeds": "10", "regimes": ",".join(REGIME_NAMES),
            "truths": ",".join(TRUTH_NAMES), "src": str(REPO / "src"),
            "out": str(HERE / "kernel_results.txt")}
    for arg in argv:
        key, eq, value = arg.removeprefix("--").partition("=")
        if not arg.startswith("--") or not eq or key not in opts:
            sys.exit(f"unrecognised argument {arg!r}; {USAGE}")
        if not value:
            sys.exit(f"--{key} is empty; {USAGE}")
        opts[key] = value
    try:
        seeds = int(opts["seeds"])
    except ValueError:
        sys.exit(f"--seeds must be an integer, got {opts['seeds']!r}; {USAGE}")
    if seeds < 1:
        sys.exit(f"--seeds must be >= 1, got {seeds}; {USAGE}")
    out = {"seeds": seeds, "src": Path(opts["src"]).resolve(), "out": Path(opts["out"])}
    for key, names in (("regimes", REGIME_NAMES), ("truths", TRUTH_NAMES)):
        chosen = opts[key].split(",")
        unknown = [c for c in chosen if c not in names]
        if unknown or len(set(chosen)) != len(chosen):
            sys.exit(f"--{key} must be distinct members of {','.join(names)}, got "
                     f"{opts[key]!r}; {USAGE}")
        out[key] = chosen
    if not (out["src"] / "rietx" / "__init__.py").is_file():
        sys.exit(f"--src {out['src']} holds no rietx package; {USAGE}")
    if not (out["src"].parent / "tests" / "test_sequential.py").is_file():
        sys.exit(f"--src {out['src']}: no tests/test_sequential.py beside it; {USAGE}")
    return out


OPTS = parse_args(sys.argv[1:] if __name__ == "__main__" else [])
sys.path.insert(0, str(OPTS["src"].parent))
sys.path.insert(0, str(OPTS["src"]))

import dataclasses  # noqa: E402

import numpy as np  # noqa: E402
from scipy.optimize import minimize  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.model.forward import compile_model  # noqa: E402
from rietx.multi import MultiHistogramRefinement  # noqa: E402
from rietx.optimize import least_squares as lsq  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.params.vector import AffineTie, ParameterTable  # noqa: E402
from rietx.schemas.common import Parameter  # noqa: E402
from rietx.schemas.instrument import BackgroundChebyshev  # noqa: E402
from rietx.schemas.structure import Atom, Cell, Phase  # noqa: E402
from rietx.sequential import refine_sequential  # noqa: E402
from rietx.strategy.staged import RefinementPlan  # noqa: E402
from tests.test_schemas import make_lab6  # noqa: E402
from tests.test_sequential import (  # noqa: E402
    A0,
    RAMP,
    TRUE_BKG,
    TRUE_SCALE,
    TRUE_W,
    TRUE_ZERO,
    WAVELENGTH,
    _start_models,
)

N = 10
TEMPS = np.array([300.0 + 100.0 * k for k in range(N)])
T_REF = float(TEMPS.mean())
T_HALF = float((TEMPS.max() - TEMPS.min()) / 2.0)
TT = (TEMPS - T_REF) / T_HALF
TWO_THETA = np.arange(3.0, 24.0, 0.005)
#: the minor phase: CaF2 as tests/test_qpa_multimodal.py builds it
AM = 5.4631
MINOR = "phases.1.cell.a"
MINOR_NAME = "CaF2"
#: printed units: a in 1e-4 Å, a1 in 1e-9 Å/K, weight fraction in 1e-5
UA, UA1, UW = 1e-4, 1e-9, 1e-5
#: the GP amplitude's floor, as a fraction of the median chain esd
S_FLOOR = 0.02
ELL_RANGE = (0.1, 20.0)
#: the sensitivity arms' hyperparameters, set by hand from the design: s a
#: quarter of the line's true half excursion L, ℓ half the ramp (t units)
FIX_S_OVER_L = 0.25
FIX_ELL = 1.0

REGIMES = {
    "W": dict(title="weak minor phase dissolving: sharp peaks, support 30 x 0.6^k",
              rm=2.5e-4, lor=0.0, support=[30.0 * 0.6 ** k for k in range(N)]),
    "O": dict(title="broad minor phase over LaB6 (lor_size 0.4 deg, held at truth), "
                    "constant support 10",
              rm=5.0e-4, lor=0.4, support=[10.0] * N),
}


# -- truths and data ------------------------------------------------------

def a_major(T: np.ndarray | float):
    return A0 * (1.0 + RAMP * (np.asarray(T) - 300.0) / 100.0)


def minor_truth(shape: str, rm: float) -> np.ndarray:
    """a_m(T_k) for ``shape`` (the module docstring's definitions)."""
    a_mid = AM * (1.0 + rm * (T_REF - 300.0) / 100.0)
    half = AM * rm * T_HALF / 100.0
    if shape == "line":
        return a_mid + half * TT
    if shape == "curve":
        return a_mid + half * TT + 0.5 * half * (TT ** 2 - 1.0)
    if shape == "kink":
        return np.where(TT <= 0.0, a_mid + half * TT, a_mid + 0.5 * half * TT)
    raise ValueError(f"unknown truth {shape!r}")


def minor_phase(a: float, scale: float, lor: float) -> Phase:
    def p(v):
        return Parameter(value=v)
    phase = Phase(name=MINOR_NAME, space_group="F m -3 m", cell=Cell.cubic(a, vary=True),
                  atoms=[Atom(label="Ca", species="Ca2+", x=p(0.0), y=p(0.0), z=p(0.0)),
                         Atom(label="F", species="F1-", x=p(0.25), y=p(0.25), z=p(0.25))])
    phase.scale.value = scale
    phase.lor_size.value = lor
    return phase


def true_models(a_maj: float, a_min: float, s_min: float, lor: float):
    structure = make_lab6()
    for name in "abc":
        getattr(structure.phases[0].cell, name).value = a_maj
    for atom in structure.phases[0].atoms:
        atom.biso.value = 0.4
    structure.phases[0].scale.value = TRUE_SCALE
    structure.phases.append(minor_phase(a_min, s_min, lor))
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = TRUE_ZERO
    ins.profile.w.value = TRUE_W
    ins.background = BackgroundChebyshev(coefficients=[Parameter(value=v) for v in TRUE_BKG])
    return structure, ins


def noiseless(a_maj: float, a_min: float, s_min: float, lor: float):
    structure, ins = true_models(a_maj, a_min, s_min, lor)
    blank = rx.PatternData(two_theta=TWO_THETA.tolist(),
                           intensity=np.zeros_like(TWO_THETA).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    return structure, ins, model, values


def support(a_maj: float, a_min: float, s_min: float, lor: float) -> float:
    """The minor phase's conditional support on the noise-free curve's σ."""
    structure, ins, model, values = noiseless(a_maj, a_min, s_min, lor)
    y = np.maximum(model.evaluate(values), 1.0)
    on_y = compile_model(structure, ins, rx.PatternData(two_theta=model.tt.tolist(),
                                                        intensity=y.tolist()),
                         mode="rietveld")
    return float(on_y.phase_support(values)[1])


def calibrate(spec: dict) -> list[float]:
    """Minor scales giving ``spec['support']`` at each pattern (line truth)."""
    a_min = minor_truth("line", spec["rm"])
    scales = []
    for k, target in enumerate(spec["support"]):
        s = 1e-9
        for _ in range(6):
            got = support(a_major(TEMPS[k]), a_min[k], s, spec["lor"])
            s *= target / got
        scales.append(s)
    return scales


def simulate(a_maj: float, a_min: float, s_min: float, lor: float, seed: int):
    _, _, model, values = noiseless(a_maj, a_min, s_min, lor)
    y = model.evaluate(values)
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def start_models(a_min0: float, s_min0: float, lor: float):
    """``_start_models`` (LaB6 cell 0.1 % long, scale x1.5, W x1.5, flat
    three-term background, no zero) with the minor phase 0.1 % long, x1.5."""
    structure, ins = _start_models()
    structure.phases.append(minor_phase(a_min0 * 1.001, s_min0 * 1.5, lor))
    return structure, ins


def weight_fraction(s_maj, a_maj, s_min, a_min, mass_maj, mass_min) -> np.ndarray:
    """Hill-Howard W of the minor phase: S·(ZM)·V over the sum."""
    wmin = np.asarray(s_min) * mass_min * np.asarray(a_min) ** 3
    wmaj = np.asarray(s_maj) * mass_maj * np.asarray(a_maj) ** 3
    return wmin / (wmin + wmaj)


# -- arm 1: the chain -----------------------------------------------------

def run_chain(patterns, start) -> dict:
    t0 = time.perf_counter()
    series = refine_sequential(patterns, *start, x=TEMPS.tolist(), x_label="T (K)",
                               plan="mccusker_default")
    seconds = time.perf_counter() - t0
    a = np.full(N, np.nan)
    esd = np.full(N, np.nan)
    w = np.full(N, np.nan)
    w_esd = np.full(N, np.nan)
    values = []
    masses = None
    for k, e in enumerate(series.entries):
        rows = {p.path: p for p in e.parameters}
        values.append({p: r.value for p, r in rows.items()})
        r = rows.get(MINOR)
        if r is not None and r.stderr is not None:
            a[k], esd[k] = r.value, r.stderr
        if e.qpa is not None:
            byname = {q.name: q for q in e.qpa.phases}
            q = byname[MINOR_NAME]
            w[k] = q.weight_fraction
            w_esd[k] = np.nan if q.weight_fraction_stderr is None else q.weight_fraction_stderr
            if masses is None:
                masses = (byname["LaB6"].cell_mass, q.cell_mass)
            if r is not None:
                # the truth's formula, checked against the package's own W
                mine = weight_fraction(rows["phases.0.scale"].value, rows["phases.0.cell.a"].value,
                                       rows["phases.1.scale"].value, r.value, *masses)
                if abs(mine - w[k]) > 1e-9 * max(w[k], 1e-12) + 1e-15:
                    raise RuntimeError(f"weight fraction formula {mine} != package {w[k]}")
    return dict(seconds=seconds, a=a, esd=esd, w=w, w_esd=w_esd, values=values,
                kept=~np.isnan(a), masses=masses,
                status=[e.status for e in series.entries],
                rungs=[e.rung for e in series.entries])


# -- arms 2 and 3: afterwards ---------------------------------------------

PHI = np.column_stack([np.ones(N), TT])


def run_line(chain: dict) -> dict:
    kept = chain["kept"]
    x, y, s = PHI[kept], chain["a"][kept], chain["esd"][kept]
    wi = 1.0 / s ** 2
    cov = np.linalg.inv(x.T @ (wi[:, None] * x))
    beta = cov @ x.T @ (wi * y)
    r = y - x @ beta
    pred = PHI @ beta
    pred_esd = np.sqrt(np.einsum("ij,jk,ik->i", PHI, cov, PHI))
    return dict(a=pred, esd=pred_esd, beta=beta, cov=cov,
                a1=beta[1] / T_HALF, a1_esd=math.sqrt(cov[1, 1]) / T_HALF,
                chi2r=float(r @ (wi * r)) / max(len(y) - 2, 1))


def matern32(t1: np.ndarray, t2: np.ndarray, s: float, ell: float) -> np.ndarray:
    r = math.sqrt(3.0) * np.abs(t1[:, None] - t2[None, :]) / ell
    return s * s * (1.0 + r) * np.exp(-r)


def _reml(log_s: float, log_ell: float, t, y, var) -> float:
    """−log restricted likelihood (constants dropped), mean [1, t] profiled."""
    V = matern32(t, t, math.exp(log_s), math.exp(log_ell)) + np.diag(var)
    try:
        L = np.linalg.cholesky(V)
    except np.linalg.LinAlgError:
        return 1e300
    x = np.column_stack([np.ones_like(t), t])
    vi_x = np.linalg.solve(V, x)
    A = x.T @ vi_x
    beta = np.linalg.solve(A, vi_x.T @ y)
    r = y - x @ beta
    _, logdet_a = np.linalg.slogdet(A)
    return float(np.sum(np.log(np.diag(L))) + 0.5 * logdet_a
                 + 0.5 * r @ np.linalg.solve(V, r))


def run_gp(chain: dict, fixed: tuple[float, float] | None = None) -> dict:
    """The GP afterwards: REML hyperparameters, or ``fixed`` = (s, ℓ) by hand."""
    t0 = time.perf_counter()
    kept = chain["kept"]
    t, y, var = TT[kept], chain["a"][kept], chain["esd"][kept] ** 2
    s_floor = S_FLOOR * float(np.median(np.sqrt(var)))
    if fixed is None:
        s_top = 10.0 * max(float(np.ptp(y)), float(np.max(np.sqrt(var))))
        bounds = [(math.log(s_floor), math.log(s_top)),
                  (math.log(ELL_RANGE[0]), math.log(ELL_RANGE[1]))]
        grid = [(ls, le) for ls in np.linspace(*bounds[0], 25)
                for le in np.linspace(*bounds[1], 25)]
        best = min(grid, key=lambda g: _reml(g[0], g[1], t, y, var))
        opt = minimize(lambda g: _reml(g[0], g[1], t, y, var), np.array(best),
                       method="L-BFGS-B", bounds=bounds)
        log_s, log_ell = (opt.x if opt.fun <= _reml(*best, t, y, var) else best)
        s, ell = math.exp(log_s), math.exp(log_ell)
    else:
        s, ell = fixed
    V = matern32(t, t, s, ell) + np.diag(var)
    x = np.column_stack([np.ones_like(t), t])
    vi_x = np.linalg.solve(V, x)
    a_inv = np.linalg.inv(x.T @ vi_x)
    beta = a_inv @ vi_x.T @ y
    ks = matern32(TT, t, s, ell)
    vi_r = np.linalg.solve(V, y - x @ beta)
    mean = PHI @ beta + ks @ vi_r
    vi_k = np.linalg.solve(V, ks.T)
    u = PHI - (x.T @ vi_k).T
    var_f = (s * s - np.einsum("ij,ji->i", ks, vi_k)
             + np.einsum("ij,jk,ik->i", u, a_inv, u))
    return dict(a=mean, esd=np.sqrt(np.maximum(var_f, 0.0)), s=s, ell=ell,
                s_floor=s_floor, at_floor=fixed is None and s <= s_floor * 1.001,
                beta=beta, a1=beta[1] / T_HALF, a1_esd=math.sqrt(a_inv[1, 1]) / T_HALF,
                seconds=time.perf_counter() - t0)


# -- arms 4 and 5: the joint fit --------------------------------------------

class _Joint(MultiHistogramRefinement):
    """Keeps the solver's outcome: the arms read the joint covariance."""

    def _build_result(self, models, outcome, *args, **kwargs):
        self.outcome_ = outcome
        return super()._build_result(models, outcome, *args, **kwargs)


@dataclasses.dataclass
class Prior:
    """N prior rows R(p − Φc) over ``path`` in every histogram."""

    R: np.ndarray
    path: str = MINOR
    coef: tuple[str, str] = ("vars.c0", "vars.c1")
    last: tuple | None = None


_ACTIVE: list[Prior] = []
_ORIGINAL_CLOSURES = lsq._multi_closures


def _closures_with_prior(models, mtable, *, weights=None, backend="numpy"):
    """``_multi_closures`` with the active prior's rows appended (script-only)."""
    residual, jacobian, n_data_total = _ORIGINAL_CLOSURES(
        models, mtable, weights=weights, backend=backend)
    if not _ACTIVE:
        return residual, jacobian, n_data_total
    prior = _ACTIVE[0]
    R = prior.R
    for table in mtable.tables:
        if prior.path in table._value_scale:
            raise RuntimeError(f"{prior.path} carries a value scale; the rows assume none")
    free = mtable.free_paths
    p_cols = [(free.index(f"hist.{h}.{prior.path}"), h)
              for h in range(len(mtable.tables)) if f"hist.{h}.{prior.path}" in free]
    c_cols = [(free.index(name), j) for j, name in enumerate(prior.coef) if name in free]

    def pc(theta):
        per = mtable.decode(theta)
        p = np.array([v[prior.path] for v in per])
        c = np.array([per[0][name] for name in prior.coef])
        return p, c

    def res(theta):
        p, c = pc(theta)
        return np.concatenate([residual(theta), R @ (p - PHI @ c)])

    def jac(theta):
        J = jacobian(theta)
        Jp = np.zeros((R.shape[0], J.shape[1]))
        for col, h in p_cols:
            Jp[:, col] = R[:, h]
        for col, j in c_cols:
            Jp[:, col] = -(R @ PHI[:, j])
        return np.vstack([J, Jp])

    prior.last = (jac, mtable, n_data_total)
    return res, jac, n_data_total


lsq._multi_closures = _closures_with_prior


def vars_plan() -> RefinementPlan:
    """``mccusker_default`` with ``vars.*`` freed in its cell stage."""
    base = RefinementPlan.mccusker_default()
    return dataclasses.replace(base, stages=[
        dataclasses.replace(s, turn_on=[*s.turn_on, "vars.*"]) if s.name == "cell" else s
        for s in base.stages])


def seeded_joint(start, chain: dict, minor_seed: np.ndarray) -> _Joint:
    """A joint fit whose histogram h starts at the chain's answer for pattern h,
    the minor cell at ``minor_seed[h]``."""
    fit = _Joint(start[0], [start[1]] * N, sharing=SharingMap(per_histogram=["phases.*"]))
    for h, table in enumerate(fit.mtable.tables):
        values = dict(chain["values"][h])
        for name in "abc":
            values[f"phases.1.cell.{name}"] = float(minor_seed[h])
        for e in table.entries:
            if e.path in values:
                e.value = values[e.path]
        table._rebuild()
    fit.mtable._rebuild_columns()
    return fit


def joint_answer(fit: _Joint, result) -> dict:
    rows = {p.path: p for p in result.parameters}
    w = np.full(N, np.nan)
    w_esd = np.full(N, np.nan)
    for h, hist in enumerate(result.histograms):
        q = {r.name: r for r in hist.qpa.phases}[MINOR_NAME]
        w[h] = q.weight_fraction
        w_esd[h] = np.nan if q.weight_fraction_stderr is None else q.weight_fraction_stderr
    held = sorted({p for st in result.stages for p in st.held})
    return dict(rows=rows, w=w, w_esd=w_esd, held=held, status=result.status,
                inflation=result.statistics.esd_inflation)


def _num(x, what: str) -> float:
    if x is None:
        raise RuntimeError(f"{what} is None: the fit estimated no covariance")
    return float(x)


def run_tie(patterns, start, chain: dict, line: dict) -> dict:
    t0 = time.perf_counter()
    a0, a1t = float(line["beta"][0]), float(line["beta"][1])
    fit = seeded_joint(start, chain, PHI @ line["beta"])
    for h, table in enumerate(fit.mtable.tables):
        table.add_parameter("vars.a0", a0, vary=False)
        table.add_parameter("vars.a1", a1t, vary=False)
        table.set_tie(MINOR, AffineTie(terms=(("vars.a0", 1.0), ("vars.a1", float(TT[h])))))
    fit.mtable._rebuild_columns()
    result = fit.fit(patterns, plan=vars_plan())
    seconds = time.perf_counter() - t0
    out = joint_answer(fit, result)
    rows = out["rows"]
    beta = np.array([rows["vars.a0"].value, rows["vars.a1"].value])
    for h in range(N):
        want = beta @ PHI[h]
        for name in "abc":
            got = rows[f"hist.{h}.phases.1.cell.{name}"].value
            if abs(got - want) > 1e-12:
                raise RuntimeError(f"tie: hist {h} cell.{name} {got} is off the line {want}")
    o = fit.outcome_
    idx = [fit.mtable.free_paths.index(p) for p in ("vars.a0", "vars.a1")]
    s = o.stderr_internal[idx]
    cov = o.correlation[np.ix_(idx, idx)] * np.outer(s, s)
    _num(rows["vars.a1"].stderr, "vars.a1 esd")
    out.update(seconds=seconds, a=PHI @ beta,
               esd=np.sqrt(np.einsum("ij,jk,ik->i", PHI, cov, PHI)),
               a1=beta[1] / T_HALF, a1_esd=math.sqrt(cov[1, 1]) / T_HALF)
    return out


def data_share(prior: Prior, theta: np.ndarray) -> tuple[np.ndarray, float]:
    """h_k = diag(Σ_p·I_p) at ``theta`` (the module docstring's definition)."""
    jac, mtable, n_data = prior.last
    J = np.asarray(jac(theta), dtype=np.float64)
    jd, jp = J[:n_data], J[-prior.R.shape[0]:]
    free = mtable.free_paths
    P = [free.index(f"hist.{h}.{prior.path}") for h in range(N)]
    C = [free.index(c) for c in prior.coef]
    rest = [i for i in range(len(free)) if i not in set(P) | set(C)]
    ad = jd.T @ jd
    d = np.sqrt(np.maximum(np.diag(ad[np.ix_(rest, rest)]), 1e-300))
    aoo = ad[np.ix_(rest, rest)] / np.outer(d, d)
    aop = ad[np.ix_(rest, P)] / d[:, None]
    i_p = ad[np.ix_(P, P)] - aop.T @ np.linalg.solve(aoo, aop)
    total = ad + jp.T @ jp
    dt = np.sqrt(np.diag(total))
    sigma = np.linalg.inv(total / np.outer(dt, dt)) / np.outer(dt, dt)
    h = np.diag(sigma[np.ix_(P, P)] @ i_p).copy()
    return h, float(h.sum())


def run_kernel(patterns, start, chain: dict, gp: dict) -> dict:
    t0 = time.perf_counter()
    K = matern32(TT, TT, gp["s"], gp["ell"]) + 1e-10 * gp["s"] ** 2 * np.eye(N)
    R = np.linalg.inv(np.linalg.cholesky(K))
    fit = seeded_joint(start, chain, gp["a"])
    for table in fit.mtable.tables:
        table.add_parameter("vars.c0", float(gp["beta"][0]), vary=False)
        table.add_parameter("vars.c1", float(gp["beta"][1]), vary=False)
    fit.mtable._rebuild_columns()
    prior = Prior(R=R)
    _ACTIVE.append(prior)
    try:
        result = fit.fit(patterns, plan=vars_plan())
    finally:
        _ACTIVE.clear()
    out = joint_answer(fit, result)
    rows = out["rows"]
    a = np.array([rows[f"hist.{h}.{MINOR}"].value for h in range(N)])
    esd = np.array([_num(rows[f"hist.{h}.{MINOR}"].stderr, f"hist.{h} minor cell esd")
                    for h in range(N)])
    o = fit.outcome_
    h_k, tr_h = data_share(prior, o.theta)
    seconds = time.perf_counter() - t0
    out.update(seconds=seconds, a=a, esd=esd, h=h_k, tr_h=tr_h,
               a1=rows["vars.c1"].value / T_HALF,
               a1_esd=_num(rows["vars.c1"].stderr, "vars.c1 esd") / T_HALF)
    return out


# -- one cell of the grid ---------------------------------------------------

def run_seed(regime: str, truth: str, seed: int, scales: list[float]) -> dict:
    spec = REGIMES[regime]
    a_min = minor_truth(truth, spec["rm"])
    a_maj = a_major(TEMPS)
    patterns = [simulate(a_maj[k], a_min[k], scales[k], spec["lor"], 1000 * seed + k)
                for k in range(N)]
    start = start_models(a_min[0], scales[0], spec["lor"])
    chain = run_chain(patterns, start)
    if chain["kept"].sum() < 4:
        raise RuntimeError(f"{regime}/{truth} seed {seed}: the chain kept "
                           f"{int(chain['kept'].sum())} patterns, too few for a line")
    line = run_line(chain)
    gp = run_gp(chain)
    fixed = (FIX_S_OVER_L * AM * spec["rm"] * T_HALF / 100.0, FIX_ELL)
    gp_fix = run_gp(chain, fixed=fixed)

    def fresh():
        return start_models(a_min[0], scales[0], spec["lor"])

    tie = run_tie(patterns, fresh(), chain, line)
    kernel = run_kernel(patterns, fresh(), chain, gp)
    kernel_fix = run_kernel(patterns, fresh(), chain, gp_fix)
    w_true = weight_fraction(TRUE_SCALE, a_maj, np.array(scales), a_min, *chain["masses"])
    return dict(seed=seed, truth_a=a_min, w_true=w_true, chain=chain, line=line, gp=gp,
                gp_fix=gp_fix, tie=tie, kernel=kernel, kernel_fix=kernel_fix)


# -- reporting ----------------------------------------------------------------

ARMS = ("chain", "line", "gp", "gp_fix", "tie", "kernel", "kernel_fix")
#: the arms that estimate a slope, and the arms that refit the fraction
SLOPE_ARMS = ("line", "gp", "gp_fix", "tie", "kernel", "kernel_fix")
FIT_ARMS = ("chain", "tie", "kernel", "kernel_fix")
KERNEL_ARMS = ("kernel", "kernel_fix")


class Out:
    """Print and append to the results file, line by line."""

    def __init__(self, path: Path):
        self.path = path
        path.write_text("")

    def __call__(self, line: str = "") -> None:
        print(line, flush=True)
        with self.path.open("a") as fh:
            fh.write(line + "\n")


def machine() -> list[str]:
    ps = subprocess.run(["ps", "-eo", "pid,etime,args"], capture_output=True, text=True,
                        check=False).stdout.splitlines()
    pytest = [ln.strip() for ln in ps if "pytest" in ln and "ps -eo" not in ln]
    load = os.getloadavg()
    return [
        f"machine   {platform.system()} {platform.machine()}, {os.cpu_count()} CPUs, "
        f"python {platform.python_version()}, numpy {np.__version__}",
        f"rietx     {rx.__version__} from {rx.__file__}, compiled kernels "
        f"{'on' if compiled.enabled() else 'off'}",
        f"load      {load[0]:.2f} {load[1]:.2f} {load[2]:.2f} (1/5/15 min) at start; "
        f"pytest processes running: {len(pytest)}",
        *[f"          {ln[:150]}" for ln in pytest],
    ]


def _rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else float("nan")


def _f(x: float, width: int = 8, prec: int = 2) -> str:
    return f"{x:{width}.{prec}f}" if np.isfinite(x) else " " * (width - 3) + "n/a"


def summarise(out: Out, regime: str, truth: str, rows: list[dict]) -> None:
    rm = REGIMES[regime]["rm"]
    out(f"  summary {regime}/{truth}, {len(rows)} seeds")
    kept = np.array([r["chain"]["kept"] for r in rows])          # seeds x N
    gaps = ~kept
    truth_a = np.array([r["truth_a"] for r in rows])
    out(f"    chain gaps (held) per pattern, of {len(rows)} seeds: "
        + " ".join(f"{int(g)}" for g in gaps.sum(axis=0)))
    out(f"    trajectory error, a in {UA:g} Å: RMSE over kept / gap / all patterns the "
        "arm gives; coverage |err| <= 1, 2 esd (all; gap); mean esd (kept; gap)")
    out("      arm         n_kept rmse_kept n_gap rmse_gap  rmse_all   cov1  cov2 cov2gap "
        " esd_kept  esd_gap  rms_z  max|z|")
    for arm in ARMS:
        a = np.array([r[arm]["a"] for r in rows])
        e = np.array([r[arm]["esd"] for r in rows])
        err = a - truth_a
        have = np.isfinite(a)
        ek, eg = err[kept & have], err[gaps & have]
        z = np.abs(err[have]) / e[have]
        zg = np.abs(err[gaps & have]) / e[gaps & have]
        out(f"      {arm:11} {ek.size:6d} {_f(_rmse(ek) / UA, 9)} {eg.size:5d} "
            f"{_f(_rmse(eg) / UA, 8)} {_f(_rmse(err[have]) / UA, 9)} "
            f"{np.mean(z <= 1):6.2f} {np.mean(z <= 2):5.2f} "
            f"{(np.mean(zg <= 2) if zg.size else float('nan')):7.2f} "
            f"{_f(np.mean(e[kept & have]) / UA, 9)} "
            f"{_f(np.mean(e[gaps & have]) / UA if (gaps & have).any() else np.nan, 8)} "
            f"{np.sqrt(np.mean(z ** 2)):6.2f} {np.max(z):7.2f}")
    if truth == "line":
        a1_true = AM * rm / 100.0
        out(f"    slope a1 in {UA1:g} Å/K, truth {a1_true / UA1:.2f} (gp: its mean's "
            "slope; kernel: vars.c1)")
        out("      arm            mean     bias  scatter  mean esd  scatter/esd  rms z")
        for arm in SLOPE_ARMS:
            a1 = np.array([r[arm]["a1"] for r in rows])
            e1 = np.array([r[arm]["a1_esd"] for r in rows])
            sd = float(np.std(a1, ddof=1)) if len(a1) > 1 else float("nan")
            zz = (a1 - a1_true) / e1
            out(f"      {arm:11} {a1.mean() / UA1:9.2f} {(a1.mean() - a1_true) / UA1:8.2f} "
                f"{sd / UA1:8.2f} {e1.mean() / UA1:9.2f} {sd / e1.mean():12.2f} "
                f"{np.sqrt(np.mean(zz ** 2)):6.2f}")
    w_true = np.array([r["w_true"] for r in rows])
    out(f"    minor weight fraction in {UW:g}: truth from {w_true[:, 0].mean() / UW:.2f} "
        f"(pattern 0) to {w_true[:, -1].mean() / UW:.3f} (pattern {N - 1}); bias, RMSE and "
        "coverage <= 2 esd over kept / gap patterns; sum fitted / sum true over the gaps")
    out("      arm          bias_kept rmse_kept cov2_kept  bias_gap rmse_gap cov2_gap  "
        "ratio_gap")
    for arm in FIT_ARMS:
        w = np.array([r[arm]["w"] for r in rows])
        we = np.array([r[arm]["w_esd"] for r in rows])
        err = w - w_true
        parts = []
        for mask in (kept, gaps):
            m = mask & np.isfinite(w)
            ee = err[m]
            cov = np.mean(np.abs(ee) <= 2 * we[m]) if ee.size else float("nan")
            parts.append(f"{_f(np.mean(ee) / UW if ee.size else np.nan, 9)} "
                         f"{_f(_rmse(ee) / UW, 9)} {cov:9.2f}")
        mg = gaps & np.isfinite(w)
        ratio = (np.sum(w[mg]) / np.sum(w_true[mg])) if mg.any() else float("nan")
        out(f"      {arm:11} {parts[0]} {parts[1]} {_f(ratio, 10, 3)}")
    out(f"    fraction per pattern, RMSE in {UW:g} (truth mean beside it)")
    out("        k     W_true " + " ".join(f"{a:>10}" for a in FIT_ARMS))
    for k in range(N):
        cells = []
        for arm in FIT_ARMS:
            err = np.array([r[arm]["w"][k] - r["w_true"][k] for r in rows])
            cells.append(_f(_rmse(err[np.isfinite(err)]) / UW, 10))
        out(f"      {k:3d} {w_true[:, k].mean() / UW:10.3f} " + " ".join(cells))
    out(f"    per pattern, means over seeds: esd in {UA:g} Å (chain over the seeds it kept "
        "the pattern) and the kernels' data share h_k")
    out("        k     T      z gaps   chain    line      gp  gp_fix     tie  kernel  "
        "k_fix  h_kern  h_kfix")
    sup = REGIMES[regime]["support"]
    for k in range(N):
        ce = np.array([r["chain"]["esd"][k] for r in rows])
        ce = ce[np.isfinite(ce)]
        cells = [_f(np.mean(ce) / UA if ce.size else np.nan, 7)]
        cells += [_f(np.mean([r[a]["esd"][k] for r in rows]) / UA, 7)
                  for a in ("line", "gp", "gp_fix", "tie", "kernel", "kernel_fix")]
        hs = [f"{np.mean([r[a]['h'][k] for r in rows]):7.3f}" for a in KERNEL_ARMS]
        out(f"      {k:3d} {TEMPS[k]:5.0f} {sup[k]:6.2f} {int(gaps[:, k].sum()):4d} "
            + " ".join(cells) + " " + " ".join(hs))
    out(f"    per pattern, mean error (estimate - truth) over seeds in {UA:g} Å")
    out("        k     T " + " ".join(f"{a:>10}" for a in ARMS))
    for k in range(N):
        cells = []
        for arm in ARMS:
            err = np.array([r[arm]["a"][k] - r["truth_a"][k] for r in rows])
            err = err[np.isfinite(err)]
            cells.append(_f(np.mean(err) / UA if err.size else np.nan, 10))
        out(f"      {k:3d} {TEMPS[k]:5.0f} " + " ".join(cells))
    s_ratio = np.array([r["gp"]["s"] / (r["gp"]["s_floor"] / S_FLOOR) for r in rows])
    ell = np.array([r["gp"]["ell"] for r in rows])
    out(f"    GP REML: s / median kept chain esd median {np.median(s_ratio):.3g} (range "
        f"{s_ratio.min():.3g}-{s_ratio.max():.3g}), at the {S_FLOOR:g} floor in "
        f"{sum(bool(r['gp']['at_floor']) for r in rows)} of {len(rows)}; ell (t units, "
        f"spacing {2 / (N - 1):.3f}) median {np.median(ell):.3g} (range "
        f"{ell.min():.3g}-{ell.max():.3g})")
    fix_s = rows[0]["gp_fix"]["s"]
    out(f"    fixed arms: s = {FIX_S_OVER_L:g} L = {fix_s:.3e} Å "
        f"({fix_s / np.median([r['gp']['s_floor'] / S_FLOOR for r in rows]):.3g} x the "
        f"median kept chain esd), ell = {FIX_ELL:g}")
    for arm in KERNEL_ARMS:
        tr = np.array([r[arm]["tr_h"] for r in rows])
        hg = np.array([r[arm]["h"] for r in rows])[gaps]
        out(f"    {arm}: tr(H) mean {tr.mean():.2f} (range {tr.min():.2f}-{tr.max():.2f}); "
            f"data share over the gap patterns mean {_f(hg.mean() if hg.size else np.nan, 5, 3)}"
            f", max {_f(hg.max() if hg.size else np.nan, 5, 3)}")
    chi = np.array([r["line"]["chi2r"] for r in rows])
    out(f"    line chi2_red through the kept chain points: mean {chi.mean():.2f}, range "
        f"{chi.min():.2f}-{chi.max():.2f}")
    for arm in ("chain", "gp", "tie", "kernel", "kernel_fix"):
        sec = np.array([r[arm]["seconds"] for r in rows])
        out(f"    wall clock {arm:10}: {sec.min():7.2f}-{sec.max():7.2f} s")
    joint = ("tie", "kernel", "kernel_fix")
    bad = [(r["seed"], "chain", k, s) for r in rows
           for k, s in enumerate(r["chain"]["status"]) if s != "converged"]
    bad += [(r["seed"], arm, r[arm]["status"]) for r in rows for arm in joint
            if r[arm]["status"] != "converged"]
    cold = sum(g == "cold" for r in rows for g in r["chain"]["rungs"][1:])
    out(f"    not converged: {bad or 'none'}; chain cold restarts after pattern 0: {cold}")
    for arm in joint:
        held = sorted({p for r in rows for p in r[arm]["held"]})
        out(f"    joint holds fired ({arm}): {held or 'none'}")
    bl = {arm: np.mean([r[arm]["inflation"] for r in rows]) for arm in joint}
    out("    Bérar-Lelann factor: " + ", ".join(f"{a} {bl[a]:.3f}" for a in joint))


def main() -> None:
    out = Out(OPTS["out"])
    t_start = time.perf_counter()
    for ln in machine():
        out(ln)
    out(f"ramp      {N} patterns, T = {TEMPS[0]:.0f}..{TEMPS[-1]:.0f} K, t = (T - {T_REF:.0f})"
        f"/{T_HALF:.0f}; seeds 0..{OPTS['seeds'] - 1}; noise seed 1000*seed + k")
    out(f"major     LaB6 (tests/test_sequential.py): a = {A0}*(1 + {RAMP}*(T - 300)/100), "
        f"scale {TRUE_SCALE}, per pattern in every arm")
    out(f"minor     CaF2, F m -3 m, a_mid = {AM}*(1 + r*4.5); truths over t with "
        "L = a_m*r*4.5: line a_mid + L t; curve + (L/2)(t^2 - 1); kink slope L/2 after "
        "t = 0 (750 K)")
    out(f"units     a in {UA:g} Å, a1 in {UA1:g} Å/K, weight fraction in {UW:g}; every esd "
        "as reported (Bérar-Lelann included); gaps = patterns the chain held")
    out(f"options   regimes {','.join(OPTS['regimes'])}; truths {','.join(OPTS['truths'])}")
    out()
    for regime in OPTS["regimes"]:
        spec = REGIMES[regime]
        scales = calibrate(spec)
        half = AM * spec["rm"] * T_HALF / 100.0
        out(f"{regime}: {spec['title']}; r = {spec['rm']:g} per 100 K, step "
            f"{AM * spec['rm']:.3e} Å, L = {half:.3e} Å")
        out("  minor scale per pattern: " + " ".join(f"{s:.3g}" for s in scales))
        out("  designed support:        " + " ".join(f"{z:.2f}" for z in spec["support"]))
        for truth in OPTS["truths"]:
            out(f"  {regime}/{truth}")
            out("    seed gaps            chain_s  tie_s kern_s kfix_s | a1 (1e-9 Å/K): "
                "line      tie   kernel    k_fix | gp s/sig   ell tr(H) kern  k_fix")
            rows = []
            for seed in range(OPTS["seeds"]):
                r = run_seed(regime, truth, seed, scales)
                rows.append(r)
                g = [k for k in range(N) if not r["chain"]["kept"][k]]
                gp = r["gp"]
                a1s = " ".join(f"{r[a]['a1'] / UA1:8.1f}"
                               for a in ("line", "tie", "kernel", "kernel_fix"))
                out(f"    {seed:4d} {str(g):16} {r['chain']['seconds']:7.2f} "
                    f"{r['tie']['seconds']:6.2f} {r['kernel']['seconds']:6.2f} "
                    f"{r['kernel_fix']['seconds']:6.2f} |               {a1s} | "
                    f"{gp['s'] / (gp['s_floor'] / S_FLOOR):8.3f} {gp['ell']:5.2f} "
                    f"{r['kernel']['tr_h']:10.2f} {r['kernel_fix']['tr_h']:6.2f}")
            summarise(out, regime, truth, rows)
            out()
    load = os.getloadavg()
    out(f"load      {load[0]:.2f} {load[1]:.2f} {load[2]:.2f} (1/5/15 min) at end; total "
        f"wall clock {time.perf_counter() - t_start:.0f} s")


if __name__ == "__main__":
    main()
