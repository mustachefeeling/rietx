"""WP-1325 task 1: a parametric a(T) on a synthetic ramp, joint fit against the chain.

    .venv/bin/python docs/wp/1325-measure/synthetic_ramp.py [--seeds=N] [--regimes=R1,R2,R3]

Run from the repository root (``--seeds`` defaults to 20, every regime runs).
Ten LaB6 patterns at T = 300…1200 K, built by ``tests/test_sequential.py``'s
``_simulate`` (Debye-Scherrer, λ = 0.4139 Å, Poisson noise) with the cell on a
known line, a(T) = A0·(1 + RAMP·(T − 300)/100), so the true slope is
a₁ = A0·RAMP/100 Å/K.  Every fit starts where that file's ``_start_models``
starts the chain: cell 0.1 % long, scale ×1.5, no zero shift, W ×1.5, a flat
three-term background.  Per noise seed it fits the ramp twice:

* **the chain** -- ``refine_sequential`` under ``mccusker_default``, then a
  straight line through the trajectory of ``phases.0.cell.a``: weighted
  (GLS, covariance (XᵀWX)⁻¹ from the per-pattern esds, W = 1/σ², with the
  line's χ²_red beside it) and unweighted (OLS, covariance s²(XᵀX)⁻¹ from
  the scatter about the line);
* **the joint fit** -- one ``MultiHistogramRefinement`` on today's dense
  joint path with ``SharingMap(per_histogram=["phases.*"])``, so every phase
  parameter is its own column per pattern, and ``vars.a0``/``vars.a1`` added
  to every sub-table (a ``vars.`` path is shared under the default rule, so
  each folds onto one column) with ``phases.0.cell.a`` tied in table h to
  a0 + a1·t_h, t_h = (T_h − T_ref)/T_half.  ``a0`` is a at T_ref, never at
  T = 0; ``a1`` and its esd are divided by T_half to come back in Å/K.  The
  plan is ``mccusker_default`` with ``vars.*`` added to the cell stage.

Three regimes, because theory says where a difference can and cannot appear.
With nothing shared but the coefficients, the joint a₁ is to first order the
line through the per-pattern a_k weighted by each pattern's raw information
(not by the chain's esds, which also carry each pattern's own χ²_red and
Bérar-Lelann factor; near-equal information makes it the OLS line here), so
R1 checks correctness, not value; R2 asks whether the constraint helps where
one pattern's cell is weak; R3 shares the instrument as one diffractometer would, so its gain is from
sharing.  R3 also runs a control that shares the instrument but leaves each
pattern its own free cell, with the line taken through those a_k by GLS over
their full joint covariance: if R3's gain is the sharing's and not the equation's,
the control and the tied fit agree.

* R1, strong signal: ``_simulate``'s own scale; phase and instrument per
  pattern, only a0/a1 shared.
* R2, weak signal: R1 with the phase scale ×``WEAK_SCALE``, which puts one
  pattern's cell esd at ~5× R1's (the printed ratio is the measurement).
* R3, shared instrument: R1 with ``instrument.zero_shift`` and
  ``instrument.profile.*`` shared across the ramp; the chain still fits them
  per pattern.

Per seed it prints each estimator's a₁ ± esd (1e-9 Å/K), the joint-to-line
difference over the joint esd, and the two wall clocks; per regime, each
estimator's mean, bias, scatter across seeds against its mean reported esd,
and RMS z against the truth.  Reported esds carry the Bérar-Lelann factor
(``Statistics.esd_inflation``, ≈1.13 on white residuals), printed beside
them.  Wall clock is per seed and quoted as a range; the header says what
else the machine was running.  ``RIETX_TELEMETRY=0`` keeps every fit from
writing a run directory.
"""

from __future__ import annotations

import dataclasses
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

import rietx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.multi import MultiHistogramRefinement  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.params.vector import AffineTie  # noqa: E402
from rietx.sequential import refine_sequential  # noqa: E402
from rietx.strategy.staged import RefinementPlan  # noqa: E402
from tests.test_sequential import (  # noqa: E402
    A0,
    RAMP,
    TRUE_SCALE,
    _simulate,
    _start_models,
)

N_PATTERNS = 10
TEMPERATURES = np.array([300.0 + 100.0 * k for k in range(N_PATTERNS)])
T_REF = float(TEMPERATURES.mean())
T_HALF = float((TEMPERATURES.max() - TEMPERATURES.min()) / 2.0)
#: the true slope, Å/K
A1_TRUE = A0 * RAMP / 100.0
#: R2's phase scale against R1's
WEAK_SCALE = 0.035
#: what R3 shares across the ramp besides the coefficients
SHARED_INSTRUMENT = ["instrument.zero_shift", "instrument.profile.*"]
#: the printed unit of a slope (Å/K), and of a at T_ref (Å)
UNIT = 1e-9
UNIT_A0 = 1e-6

REGIMES = {
    "R1": dict(title="strong signal; phase + instrument per pattern, only a0/a1 shared",
               scale=1.0, shared=[]),
    "R2": dict(title=f"weak signal (phase scale x{WEAK_SCALE}); as R1 otherwise",
               scale=WEAK_SCALE, shared=[]),
    "R3": dict(title="shared instrument (zero_shift, profile.*) in the joint fit; "
                     "the chain per pattern",
               scale=1.0, shared=SHARED_INSTRUMENT),
}


class _Joint(MultiHistogramRefinement):
    """Keeps the solver's outcome: the control needs the joint covariance."""

    def _build_result(self, models, outcome, *args, **kwargs):
        self.outcome_ = outcome
        return super()._build_result(models, outcome, *args, **kwargs)


def _num(x: float | None, what: str) -> float:
    """``x`` as a float, refusing a ``None`` by name rather than in ``float()``."""
    if x is None:
        raise RuntimeError(f"{what} is None: the fit estimated no covariance")
    return float(x)


def ramp(seed: int, scale: float) -> list:
    return [_simulate(A0 * (1.0 + RAMP * (t - 300.0) / 100.0),
                      seed=1000 * seed + k, scale=TRUE_SCALE * scale)
            for k, t in enumerate(TEMPERATURES)]


def start(scale: float):
    structure, ins = _start_models()
    structure.phases[0].scale.value = TRUE_SCALE * scale * 1.5
    return structure, ins


def parametric_plan() -> RefinementPlan:
    """``mccusker_default`` with the coefficients freed in its cell stage."""
    base = RefinementPlan.mccusker_default()
    stages = [dataclasses.replace(s, turn_on=[*s.turn_on, "vars.*"])
              if s.name == "cell" else s for s in base.stages]
    return dataclasses.replace(base, stages=stages)


def line(a: np.ndarray, cov: np.ndarray | None) -> dict:
    """The straight line a = c0 + a1·(T − T_REF) through ``a``.

    ``cov`` is the covariance of ``a``: GLS with covariance (XᵀΣ⁻¹X)⁻¹; ``None``
    is OLS with s²(XᵀX)⁻¹ from the scatter about the line.
    """
    x = np.column_stack([np.ones_like(TEMPERATURES), TEMPERATURES - T_REF])
    dof = len(a) - 2
    if cov is None:
        beta, *_ = np.linalg.lstsq(x, a, rcond=None)
        r = a - x @ beta
        c = (r @ r / dof) * np.linalg.inv(x.T @ x)
        chi2r = float("nan")
    else:
        wi = np.linalg.inv(cov)
        c = np.linalg.inv(x.T @ wi @ x)
        beta = c @ x.T @ wi @ a
        r = a - x @ beta
        chi2r = float(r @ wi @ r / dof)
    return dict(a0=float(beta[0]), a0_esd=float(np.sqrt(c[0, 0])),
                a1=float(beta[1]), a1_esd=float(np.sqrt(c[1, 1])), chi2r=chi2r)


def run_chain(patterns, scale: float) -> dict:
    structure, ins = start(scale)
    t0 = time.perf_counter()
    series = refine_sequential(patterns, structure, ins, x=TEMPERATURES.tolist(),
                               x_label="T (K)", plan="mccusker_default")
    seconds = time.perf_counter() - t0
    traj = series.trajectory("phases.0.cell.a")
    if len(traj.value) != N_PATTERNS or any(s is None for s in traj.stderr):
        raise RuntimeError(f"chain trajectory incomplete: {traj}")
    a = np.array(traj.value)
    esd = np.array(traj.stderr, dtype=float)
    return dict(seconds=seconds, a=a, esd=esd,
                weighted=line(a, np.diag(esd ** 2)), unweighted=line(a, None),
                status=[e.status for e in series.entries],
                rungs=[e.rung for e in series.entries],
                inflation=float(np.mean([_num(e.statistics.esd_inflation,
                                              "chain esd_inflation")
                                         for e in series.entries])))


def run_joint(patterns, scale: float, shared: list[str], *, tied: bool) -> dict:
    """The joint fit, tied (the parametric form) or with every cell its own."""
    structure, ins = start(scale)
    t0 = time.perf_counter()
    fit = _Joint(structure, [ins] * N_PATTERNS,
                 sharing=SharingMap(per_histogram=["phases.*"], shared=list(shared)))
    mt = fit.mtable
    if tied:
        a_start = structure.phases[0].cell.a.value
        for h, table in enumerate(mt.tables):
            table.add_parameter("vars.a0", a_start, vary=False)
            table.add_parameter("vars.a1", 0.0, vary=False)
            t_h = (TEMPERATURES[h] - T_REF) / T_HALF
            table.set_tie("phases.0.cell.a", AffineTie(
                terms=(("vars.a0", 1.0), ("vars.a1", float(t_h)))))
        mt._rebuild_columns()
    result = fit.fit(patterns, plan=parametric_plan() if tied else "mccusker_default")
    seconds = time.perf_counter() - t0
    rows = {p.path: p for p in result.parameters}
    held = sorted({p for st in result.stages for p in st.held})
    out = dict(seconds=seconds, status=result.status, held=held,
               n_columns=len(mt.free_paths), n_rows=sum(len(p.two_theta) for p in patterns),
               inflation=_num(result.statistics.esd_inflation, "joint esd_inflation"),
               shared=list(mt.shared_paths))
    a = np.array([rows[f"hist.{h}.phases.0.cell.a"].value for h in range(N_PATTERNS)])
    out["a"] = a
    if tied:
        # the equation held: b and c follow a, which follows the line, in every table
        for h in range(N_PATTERNS):
            want = rows["vars.a0"].value + rows["vars.a1"].value * (
                (TEMPERATURES[h] - T_REF) / T_HALF)
            for name in "abc":
                got = rows[f"hist.{h}.phases.0.cell.{name}"].value
                if abs(got - want) > 1e-12:
                    raise RuntimeError(f"hist {h} cell.{name} = {got} is off the line {want}")
        cell_freed = [st.freed for st in result.stages if st.name == "cell"][0]
        out.update(cell_freed=cell_freed,
                   a0=rows["vars.a0"].value,
                   a0_esd=_num(rows["vars.a0"].stderr, "vars.a0 esd"),
                   a1=rows["vars.a1"].value / T_HALF,
                   a1_esd=_num(rows["vars.a1"].stderr, "vars.a1 esd") / T_HALF)
    else:
        # the line through the jointly-fitted cells, by GLS over their joint
        # covariance (cell.a is a free column at value scale 1: one wavelength)
        o = fit.outcome_
        idx = [mt.free_paths.index(f"hist.{h}.phases.0.cell.a") for h in range(N_PATTERNS)]
        s = o.stderr_internal[idx]
        cov = o.correlation[np.ix_(idx, idx)] * np.outer(s, s)
        fitted = line(a, cov)
        out.update(a0=fitted["a0"], a0_esd=fitted["a0_esd"], a1=fitted["a1"],
                   a1_esd=fitted["a1_esd"], chi2r=fitted["chi2r"])
    return out


def machine() -> list[str]:
    ps = subprocess.run(["ps", "-eo", "pid,etime,args"], capture_output=True, text=True,
                        check=False).stdout.splitlines()
    pytest = [ln.strip() for ln in ps if "python -m pytest" in ln and "ps -eo" not in ln]
    load = os.getloadavg()
    return [
        f"machine   {platform.system()} {platform.machine()}, {os.cpu_count()} CPUs, "
        f"python {platform.python_version()}, numpy {np.__version__}",
        f"rietx     {rietx.__version__} from {Path(rietx.__file__).parent} ([dev] venv), "
        f"compiled kernels {'on' if compiled.enabled() else 'off'}",
        f"load      {load[0]:.2f} {load[1]:.2f} {load[2]:.2f} (1/5/15 min) at start; "
        f"'python -m pytest' processes running: {len(pytest)}",
        *[f"          {ln}" for ln in pytest],
    ]


def u(x: float) -> str:
    return f"{x / UNIT:9.2f}"


def summarise(name: str, rows: list[dict], estimators: list[tuple[str, str]]) -> list[str]:
    out = [f"  summary {name}, {len(rows)} seeds; a1 in {UNIT:g} Å/K, truth "
           f"{A1_TRUE / UNIT:.2f}",
           "    estimator                 mean      bias   scatter  mean esd  scatter/esd"
           "  rms z   min esd   max esd"]
    for key, label in estimators:
        a1 = np.array([r[key]["a1"] for r in rows])
        esd = np.array([r[key]["a1_esd"] for r in rows])
        z = (a1 - A1_TRUE) / esd
        sd = float(np.std(a1, ddof=1)) if len(a1) > 1 else float("nan")
        out.append(f"    {label:20} {u(a1.mean())} {u(a1.mean() - A1_TRUE)} {u(sd)} "
                   f"{u(esd.mean())}  {sd / esd.mean():11.2f}  {np.sqrt(np.mean(z ** 2)):5.2f}"
                   f" {u(esd.min())} {u(esd.max())}")
    a_ref = A0 * (1.0 + RAMP * (T_REF - 300.0) / 100.0)
    out.append(f"    a(T_ref) in {UNIT_A0:g} Å against truth {a_ref:.6f} Å: "
               "estimator, mean bias, mean esd, rms z")
    for key, label in estimators:
        if key == "chain.unweighted":
            continue
        a0 = np.array([r[key]["a0"] for r in rows])
        e0 = np.array([r[key]["a0_esd"] for r in rows])
        out.append(f"      {label:20} {(a0.mean() - a_ref) / UNIT_A0:8.3f} "
                   f"{e0.mean() / UNIT_A0:8.3f} {np.sqrt(np.mean(((a0 - a_ref) / e0) ** 2)):6.2f}")
    ratio = np.array([r["joint"]["a1_esd"] / r["chain"]["weighted"]["a1_esd"] for r in rows])
    diff = np.array([abs(r["joint"]["a1"] - r["chain"]["weighted"]["a1"]) / r["joint"]["a1_esd"]
                     for r in rows])
    chi2r = np.array([r["chain"]["weighted"]["chi2r"] for r in rows])
    out += [
        f"    joint esd / weighted-line esd: mean {ratio.mean():.3f}, "
        f"range {ratio.min():.3f}-{ratio.max():.3f}",
        f"    |joint - weighted line| / joint esd: mean {diff.mean():.3f}, max {diff.max():.3f}",
        f"    weighted line chi2_red: mean {chi2r.mean():.2f}, range "
        f"{chi2r.min():.2f}-{chi2r.max():.2f}",
        f"    per-pattern cell esd (chain), mean over patterns and seeds: "
        f"{np.mean([r['chain']['esd'].mean() for r in rows]):.3e} Å",
        f"    Bérar-Lelann factor: chain (mean per pattern) "
        f"{np.mean([r['chain']['inflation'] for r in rows]):.3f}, joint "
        f"{np.mean([r['joint']['inflation'] for r in rows]):.3f}",
    ]
    if "control" in rows[0]:
        cd = np.array([abs(r["joint"]["a1"] - r["control"]["a1"]) / r["joint"]["a1_esd"]
                       for r in rows])
        ce = np.array([r["control"]["a1_esd"] / r["joint"]["a1_esd"] for r in rows])
        out += [f"    |joint - control| / joint esd: mean {cd.mean():.3f}, max {cd.max():.3f}; "
                f"control esd / joint esd {ce.min():.3f}-{ce.max():.3f}"]
    for key, label in (("chain", "chain"), ("joint", "joint"), ("control", "control")):
        if key not in rows[0]:
            continue
        sec = np.array([r[key]["seconds"] for r in rows])
        out.append(f"    wall clock {label:7}: {sec.min():6.2f}-{sec.max():6.2f} s")
    jr = np.array([r["joint"]["seconds"] / r["chain"]["seconds"] for r in rows])
    out.append(f"    wall clock joint / chain: {jr.min():.2f}-{jr.max():.2f}")
    bad = [(r["seed"], k, r[k]["status"]) for r in rows for k in ("joint", "control")
           if k in r and r[k]["status"] != "converged"]
    bad += [(r["seed"], "chain", s) for r in rows for s in r["chain"]["status"]
            if s != "converged"]
    cold = sum(g == "cold" for r in rows for g in r["chain"]["rungs"][1:])
    held = sorted({p for r in rows for k in ("joint", "control") if k in r
                   for p in r[k]["held"]})
    out += [f"    not converged: {bad or 'none'}; chain cold restarts after pattern 0: {cold}",
            f"    absent-phase / ridge holds fired in a joint fit: {held or 'none'}"]
    return out


def main(n_seeds: int, regimes: list[str]) -> None:
    for ln in machine():
        print(ln)
    print(f"ramp      {N_PATTERNS} patterns, T = {TEMPERATURES[0]:.0f}..{TEMPERATURES[-1]:.0f} K; "
          f"a(T) = {A0}*(1 + {RAMP}*(T - 300)/100); T_ref = {T_REF:.0f} K, "
          f"T_half = {T_HALF:.0f} K; seeds 0..{n_seeds - 1}")
    print(f"units     a1 in {UNIT:g} Å/K (truth {A1_TRUE / UNIT:.2f}); every esd as "
          "reported, Bérar-Lelann factor included; |d|/sj = |joint - line(w)| / joint esd")
    print(flush=True)
    per_pattern: dict[str, float] = {}
    for name in regimes:
        spec = REGIMES[name]
        control = bool(spec["shared"])
        print(f"{name}: {spec['title']}")
        head = ("  seed  chain s  joint s  ratio |   line(w) ±       esd chi2r |"
                "   line(u) ±       esd |     joint ±       esd |d|/sj")
        if control:
            head += " |   control ±       esd"
        print(head, flush=True)
        rows = []
        for seed in range(n_seeds):
            patterns = ramp(seed, spec["scale"])
            row = dict(seed=seed, chain=run_chain(patterns, spec["scale"]),
                       joint=run_joint(patterns, spec["scale"], spec["shared"], tied=True))
            if control:
                row["control"] = run_joint(patterns, spec["scale"], spec["shared"], tied=False)
            rows.append(row)
            c, j = row["chain"], row["joint"]
            w, ol = c["weighted"], c["unweighted"]
            line_out = (f"  {seed:4d} {c['seconds']:8.2f} {j['seconds']:8.2f} "
                        f"{j['seconds'] / c['seconds']:6.2f} |{u(w['a1'])} ±{u(w['a1_esd'])} "
                        f"{w['chi2r']:5.2f} |{u(ol['a1'])} ±{u(ol['a1_esd'])} |"
                        f"{u(j['a1'])} ±{u(j['a1_esd'])} "
                        f"{abs(j['a1'] - w['a1']) / j['a1_esd']:6.3f}")
            if control:
                k = row["control"]
                line_out += f" |{u(k['a1'])} ±{u(k['a1_esd'])}"
            print(line_out, flush=True)
        if rows:
            first = rows[0]["joint"]
            print(f"  joint θ: {first['n_columns']} columns ({len(first['shared'])} shared: "
                  f"{', '.join(first['shared'])}) x {first['n_rows']} rows; cell stage freed "
                  f"{first['cell_freed']}")
        estimators = [("chain.weighted", "chain line, weighted"),
                      ("chain.unweighted", "chain line, OLS"),
                      ("joint", "joint a0 + a1*t")]
        if control:
            estimators.append(("control", "control (no equation)"))
        flat = [dict(r, **{"chain.weighted": r["chain"]["weighted"],
                           "chain.unweighted": r["chain"]["unweighted"]}) for r in rows]
        for ln in summarise(name, flat, estimators):
            print(ln)
        per_pattern[name] = float(np.mean([r["chain"]["esd"].mean() for r in rows]))
        if name != "R1" and "R1" in per_pattern:
            print(f"    per-pattern cell esd {name}/R1: "
                  f"{per_pattern[name] / per_pattern['R1']:.2f}")
        print(flush=True)


if __name__ == "__main__":
    usage = "usage: synthetic_ramp.py [--seeds=N] [--regimes=R1,R2,R3]"
    opts: dict[str, str] = {}
    for arg in sys.argv[1:]:
        key, eq, value = arg.lstrip("-").partition("=")
        if not eq or key not in ("seeds", "regimes"):
            sys.exit(f"unrecognised argument {arg!r}; {usage}")
        opts[key] = value
    n_seeds = int(opts.get("seeds", 20))
    regimes = opts.get("regimes", "R1,R2,R3").split(",")
    unknown = [r for r in regimes if r not in REGIMES]
    if n_seeds < 1 or unknown:
        sys.exit(f"--seeds must be >= 1 and --regimes a subset of "
                 f"{','.join(REGIMES)} (got {n_seeds}, {unknown or regimes}); {usage}")
    main(n_seeds, regimes)
