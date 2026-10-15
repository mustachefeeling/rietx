"""WP-1325, the measurement on real data: the ZrMo2O8 ramp, Durham TOPAS tutorial 9.2.

    .venv/bin/python docs/wp/1325-measure/real_ramp.py [--first=35] [--last=67]
        [--degree=1] [--each] [--profile] > docs/wp/1325-measure/real_ramp_results.txt

Run from the repository root, alone on the machine (the wall clocks are
compared).  The data is local-only: ``tests/local_data.py`` registers it as
``durham-topas/zrmo2o8_vt``, and the script declines when it is absent.
Nothing of the tutorial is committed.  The structures come from its series
input through ``rx.read_project_model`` at run time, and the instrument
resolution function, the axial term, the fitted range and the temperatures are
parsed from the same file.

**The window.**  Ranges ``first``..``last`` of the RAW file, 0-based (TOPAS's
``#list`` numbers them from 1).  The default, 693-991.5 K, is where cubic
ZrMo2O8 is the major phase.  LT-ZrMo2O8 decays across it, and trigonal ZrMo2O8
stays a minor phase throughout.  The precursor hydrate is gone 280 K below the
window and is left out of the model.

**The protocol.**  The input's resolution function (TCHZ U, V, W, X, Y) and
axial term are held, as the input holds them.  ``TCHZ_Peak_Type`` is read by
argument position, never by its labels: slots (u, v, w, z, x, y), slot 5 the
tanθ Lorentzian term and slot 6 the 1/cosθ one (WP-1455, measured against
TOPAS 6).  Its z is zero here.  Every fit runs ``lab_sample_refine``'s scale
and background, displacement, cell and sample-broadening stages, with the zero
and the displacement parameters held.  Cells may move ±1.5 % from the input's
values, and sample broadening is capped, as the August transcription found
necessary to keep a vanishing phase from dissolving into the background.

**Three arms**, as the synthetic half's (§ Measured: the synthetic ramp):

1. ``chain``: ``SequentialRefinement`` over the window, warm-started.
2. ``line``: per target, the weighted least-squares line [1, T - T_ref]
   through the chain's points that carry an esd.  Its χ²_red is the
   lack-of-fit check the WP lists first.
3. ``joint``: one ``MultiHistogramRefinement`` over the window, every phase
   path per-pattern, seeded from the chain's fitted models, with a polynomial
   [1, T] equation on each target.  Same plan.

Targets: the cubic cell a, and the trigonal cell's a and c.  T_ref is the
window's mid-range, the joint's own default reference.  ``--degree`` sets the
polynomial's degree for the line and the joint alike.

**A second lack-of-fit check comes nearly free.**  The same joint fit with no
equation (``untied``) frees every target per pattern, so the joint's χ² above it,
per parameter the equation removed, is a nested test of the declared form: F near
1 when the form holds.  The reference is the untied joint fit and not the
chain, because the two free different sets: on this window the chain held a
fading phase in two patterns by WP-1523's answer significance, which the joint
path does not read, and that left 14 columns free in the joint only.
``--each`` fits one equation at a time, to say which target the excess comes from.
``--profile`` runs the joint fit again under cProfile, with
``jacobian_profile.py``'s accounting of the compiled kernels and the peak chain.
"""

from __future__ import annotations

import math
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.schemas.common import Parameter  # noqa: E402
from rietx.sequential import SequentialRefinement  # noqa: E402
from rietx.strategy.staged import RefinementPlan  # noqa: E402
from tests import local_data  # noqa: E402

DATASET = "durham-topas/zrmo2o8_vt"
INP = "d8_01612_vt_02.inp"
RAW = "d8_01612.raw"
STAGES = ("scale_bkg", "disp", "cell", "sample_profile")
CELL_WINDOW = 0.015
TARGETS = {  # phase index after the precursor is dropped
    "cubic_a": "phases.1.cell.a",
    "trig_a": "phases.2.cell.a",
    "trig_c": "phases.2.cell.c",
}


def parse_args(argv: list[str]) -> dict:
    out = {"first": 35, "last": 67, "degree": 1, "each": 0, "profile": 0}
    for arg in argv:
        key, _, value = arg.removeprefix("--").partition("=")
        if key not in out:
            raise SystemExit(f"unknown argument {arg!r}")
        out[key] = int(value or 1)
    return out


# -- the model, from the local input ----------------------------------------

def _call_args(text: str, name: str) -> list[str]:
    match = re.search(rf"\b{name}\(([^)]*)\)", text)
    if match is None:
        raise SystemExit(f"{INP} has no {name}(...) call")
    return [a.strip() for a in match.group(1).split(",")]


def _number(token: str) -> float:
    """A TOPAS value as written: ``0.0066_0.0044`` (value_esd), ``3.41``` (refined)."""
    return float(token.rstrip("`").split("_")[0])


def protocol(text: str) -> dict:
    tchz = [_number(a) for a in _call_args(text, "TCHZ_Peak_Type")[1::2]]
    if len(tchz) != 6:
        raise SystemExit(f"TCHZ_Peak_Type has {len(tchz)} values, not 6")
    u, v, w, z, s5, s6 = tchz
    if z != 0.0:
        raise SystemExit(f"TCHZ z = {z}: fold it into U and W before using this script")
    temps = {int(m.group(1)): float(m.group(2))
             for m in re.finditer(r"^\s*\S+\.raw\s+(\d+)\s+([\d.]+)\s*$", text, re.M)}
    return dict(
        u=u, v=v, w=w, lor_tan=s5, lor_cos=s6,
        axial_mm=_number(_call_args(text, "Simple_Axial_Model")[1]),
        mono=_number(_call_args(text, "LP_Factor")[1]),
        limits=(float(re.search(r"start_X\s+([\d.]+)", text).group(1)),
                float(re.search(r"finish_X\s+([\d.]+)", text).group(1))),
        temps=[temps[k] for k in sorted(temps)],
    )


def structure(path: Path) -> rx.Structure:
    model = rx.read_project_model(path, diagnostics=[])
    phases = model.to_structure().phases[1:]  # drop the precursor hydrate
    for phase in phases:
        cell = phase.cell
        for name in "abc":
            p = getattr(cell, name)
            p.min, p.max = p.value * (1 - CELL_WINDOW), p.value * (1 + CELL_WINDOW)
        phase.lor_size = Parameter.positive(0.05, max=0.50)
        phase.lor_strain = Parameter.positive(0.02, max=0.50)
        phase.gauss_size = Parameter.positive(0.0, max=0.25)
        phase.gauss_strain = Parameter.positive(0.0, max=0.25)
    return rx.Structure(phases=phases)


def instrument(proto: dict, radius_mm: float) -> rx.Instrument:
    inst = rx.Instrument.bragg_brentano(radiation="CuKa1", monochromator_two_theta=proto["mono"])
    prof = inst.profile
    prof.u = Parameter(value=proto["u"], min=-0.05, max=1.0, unit="deg^2")
    prof.v = Parameter(value=proto["v"], min=-0.5, max=0.5, unit="deg^2")
    prof.w = Parameter.positive(proto["w"], max=1.0, unit="deg^2")
    prof.x = Parameter.positive(proto["lor_cos"], max=1.0, unit="deg")  # 1/cosθ
    prof.y = Parameter.positive(proto["lor_tan"], max=1.0, unit="deg")  # tanθ
    axial = proto["axial_mm"] / radius_mm
    inst.geometry.axial_sl = Parameter(value=axial, min=0.0, max=0.2)
    inst.geometry.axial_hl = Parameter(value=axial, min=0.0, max=0.2)
    inst.background.coefficients = [Parameter(value=0.0) for _ in range(12)]
    return inst


def plan() -> RefinementPlan:
    base = rx.PLAN_PRESETS["lab_sample_refine"]()
    return RefinementPlan(stages=[s for s in base.stages if s.name in STAGES])


# -- the three arms ----------------------------------------------------------

def run_chain(patterns, start, temps, limits) -> dict:
    t0 = time.perf_counter()
    series = SequentialRefinement(*start)
    result = series.fit(patterns, x=temps, x_label="T (K)", plan=plan(), two_theta_limits=limits)
    seconds = time.perf_counter() - t0
    traj = {}
    for key, path in TARGETS.items():
        v = np.full(len(patterns), np.nan)
        e = np.full(len(patterns), np.nan)
        for k, entry in enumerate(result.entries):
            row = next((p for p in entry.parameters if p.path == path), None)
            if row is not None and row.stderr is not None:
                v[k], e[k] = row.value, row.stderr
        traj[key] = (v, e)
    stats = [e.statistics for e in result.entries]
    return dict(seconds=seconds, traj=traj, series=series, result=result,
                status=[e.status for e in result.entries],
                chi2=sum(_total_chi2(s) for s in stats),
                n_free=sum(s.n_free_parameters for s in stats),
                rwp=[s.rwp for s in stats])


def _total_chi2(s) -> float:
    """``Statistics.chi2`` is reduced, over max(N - P, 1)."""
    return s.chi2 * max(s.n_points - s.n_free_parameters, 1)



def run_line(t: np.ndarray, t_ref: float, v: np.ndarray, e: np.ndarray, degree: int) -> dict:
    """Weighted least squares of the declared form through the chain's points.

    The columns are (T - T_ref)^j, so each coefficient means what the joint's
    does: the j-th Taylor coefficient at T_ref, in Å/K^j.
    """
    kept = ~np.isnan(v)
    x = np.column_stack([(t[kept] - t_ref) ** j for j in range(degree + 1)])
    wi = 1.0 / e[kept] ** 2
    cov = np.linalg.inv(x.T @ (wi[:, None] * x))
    beta = cov @ x.T @ (wi * v[kept])
    r = v[kept] - x @ beta
    return dict(n=int(kept.sum()), beta=beta, esd=np.sqrt(np.diag(cov)),
                chi2r=float(r @ (wi * r)) / max(int(kept.sum()) - degree - 1, 1),
                mean_esd=float(np.mean(e[kept])))


def run_joint(patterns, chain: dict, temps, limits, keys, degree: int) -> dict:
    series = chain["series"]
    terms = [["T"] * j for j in range(degree + 1)]
    equations = [rx.ParametricEquation(name=key, target=TARGETS[key], basis="polynomial", terms=terms)
            for key in keys]
    t0 = time.perf_counter()
    fit = rx.MultiHistogramRefinement(
        list(series.fitted_structures), list(series.fitted_instruments),
        sharing=SharingMap(per_histogram=["phases.*"]),
        coordinates=rx.CoordinateTable(columns={"T": list(temps)}, units={"T": "K"}),
        parametric=equations or None)
    result = fit.fit(patterns, plan=plan(), two_theta_limits=limits)
    seconds = time.perf_counter() - t0
    coef = {(c.equation, c.term): c for c in result.parametric or []}
    s = result.statistics
    return dict(seconds=seconds, result=result, coef=coef, resolved=fit.parametric,
                chi2=_total_chi2(s), n_free=s.n_free_parameters,
                chi2r=s.chi2, inflation=s.esd_inflation)


TERM = {0: "1", 1: "T", 2: "T^2"}
UNIT = {0: ("Å", 1.0), 1: ("1e-6 Å/K", 1e6), 2: ("1e-9 Å/K²", 1e9)}


def report_joint(label: str, joint: dict, ref: dict | None) -> None:
    """One joint fit's line; against ``ref``, the untied joint fit, the nested test.

    F is (Δχ²/Δfree)/χ²_red(ref), near 1 when the equation holds.  F/f² divides by
    the untied fit's Bérar-Lelann factor squared too, since serially
    correlated residuals inflate a χ² difference by about that much, as they do
    the esds (``statistics.esd_inflation``).
    """
    s = joint["result"].statistics
    line = (f"{label:9} {joint['seconds']:.1f} s; status {joint['result'].status}; "
            f"Rwp {100 * s.rwp:.3f} %; χ² {joint['chi2']:.1f} with {joint['n_free']} free")
    if ref is None:
        line += f"; χ²r {joint['chi2r']:.3f}, f {joint['inflation']:.3f}"
    else:
        dchi2 = joint["chi2"] - ref["chi2"]
        dfree = ref["n_free"] - joint["n_free"]
        f_ratio = dchi2 / max(dfree, 1) / ref["chi2r"]
        line += (f"; Δχ² {dchi2:+.1f} for {dfree} fewer free; F {f_ratio:.2f}, "
                 f"F/f² {f_ratio / ref['inflation'] ** 2:.2f}")
    print(line, flush=True)


def coefficient_table(joint: dict, chain: dict, temps, t_ref: float, keys, degree: int) -> None:
    print(f"{'target':8} {'term':4} {'unit':>11} {'n':>3} {'χ²r line':>8} | {'line':>10} {'esd':>8} | "
          f"{'joint':>10} {'esd':>8} | {'Δ/esd':>6} {'esd ratio':>9}")
    for key in keys:
        v, e = chain["traj"][key]
        line = run_line(np.asarray(temps), t_ref, v, e, degree)
        for j in range(degree + 1):
            unit, f = UNIT[j]
            c = joint["coef"][(key, TERM[j])]
            esd = c.esd if c.esd is not None else math.nan
            d = (c.value - line["beta"][j]) / line["esd"][j]
            print(f"{key:8} {TERM[j]:4} {unit:>11} {line['n']:3d} {line['chi2r']:8.2f} | "
                  f"{f * line['beta'][j]:10.4f} {f * line['esd'][j]:8.4f} | "
                  f"{f * c.value:10.4f} {f * esd:8.4f} | {d:+6.2f} {esd / line['esd'][j]:9.3f}")


def machine() -> list[str]:
    from rietx.model import compiled

    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=False).stdout.strip()
    return [
        f"machine   {platform.system()} {platform.machine()}, {os.cpu_count()} CPUs, "
        f"python {platform.python_version()}, numpy {np.__version__}",
        f"rietx     {rx.__version__} at {head}, compiled kernels "
        f"{'on' if compiled.enabled() else 'off'}",
        f"load      {' '.join(f'{x:.2f}' for x in os.getloadavg())}",
    ]


def main() -> None:
    args = parse_args(sys.argv[1:])
    where = local_data.dataset(DATASET)
    if where is None:
        raise SystemExit(f"{DATASET} is not on this machine: python -m tests.local_data {DATASET}")
    text = (where / INP).read_text(encoding="utf-8", errors="replace")
    proto = protocol(text)
    radius = rx.read_topas_inp(where / INP).goniometer_radius_mm or 217.5
    window = range(args["first"], args["last"] + 1)
    temps = np.array([proto["temps"][k] for k in window])
    t_ref = 0.5 * (temps.min() + temps.max())
    patterns = [rx.read_pattern(where / RAW, scan=k) for k in window]
    start = (structure(where / INP), instrument(proto, radius))
    degree, keys = args["degree"], list(TARGETS)

    print("WP-1325 real-data measurement: the ZrMo2O8 ramp (Durham TOPAS tutorial 9.2)")
    for line in machine():
        print(line)
    print(f"window    ranges {window.start}..{window.stop - 1} (0-based), {len(window)} patterns, "
          f"T {temps.min():.1f}-{temps.max():.1f} K, T_ref {t_ref:.2f} K")
    print(f"protocol  {', '.join(STAGES)}; resolution held; 2θ {proto['limits']}; "
          f"phases {[p.name for p in start[0].phases]}")
    print(f"form      polynomial of degree {degree} in T on {', '.join(keys)}")
    print(flush=True)

    chain = run_chain(patterns, start, temps.tolist(), proto["limits"])
    print(f"chain     {chain['seconds']:.1f} s; status {sorted(set(chain['status']))}; "
          f"Rwp {100 * min(chain['rwp']):.2f}-{100 * max(chain['rwp']):.2f} %; "
          f"Σχ² {chain['chi2']:.1f} with {chain['n_free']} free", flush=True)
    untied = run_joint(patterns, chain, temps.tolist(), proto["limits"], [], degree)
    report_joint("untied", untied, None)
    joint = run_joint(patterns, chain, temps.tolist(), proto["limits"], keys, degree)
    report_joint("joint", joint, untied)
    print(f"cost      joint ÷ chain {joint['seconds'] / chain['seconds']:.2f}; "
          f"untied ÷ chain {untied['seconds'] / chain['seconds']:.2f}")
    print()
    coefficient_table(joint, chain, temps, t_ref, keys, degree)
    print()
    print("joint diagnostics:", sorted({d.code for d in joint["result"].diagnostics}))
    held = sorted({p for st in joint["result"].stages for p in st.held})
    print(f"joint held ({len(held)}):", held[:12], "…" if len(held) > 12 else "")

    if args["each"]:
        print()
        print("one equation per joint fit: which target the Δχ² comes from")
        for key in keys:
            one = run_joint(patterns, chain, temps.tolist(), proto["limits"], [key], degree)
            report_joint(f"  {key}", one, untied)

    print()
    print("chain trajectories (T, value, esd; nan = held):")
    for key in keys:
        v, e = chain["traj"][key]
        print(f"  {key}: " + " ".join(f"{t:.0f}:{x:.5f}({s:.5f})" for t, x, s in zip(temps, v, e)))

    if args["profile"]:
        # jacobian_profile.py's accounting, on this structure: does a larger
        # cell raise the compiled kernels' share of a joint fit?
        import cProfile
        import pstats

        sys.path.insert(0, str(Path(__file__).parent))
        from jacobian_profile import profile_shares

        prof = cProfile.Profile()
        prof.enable()
        again = run_joint(patterns, chain, temps.tolist(), proto["limits"], keys, degree)
        prof.disable()
        sh = profile_shares(pstats.Stats(prof))
        print()
        print(f"profile   the joint fit again under cProfile: {sh['total']:.1f} s "
              f"(plain {joint['seconds']:.1f} s, profiled {again['seconds']:.1f} s)")
        print(f"          rietx_kernels calls {sh['kernels']:.2f} s = "
              f"{100 * sh['kernels'] / sh['total']:.1f} % of the profiled fit, "
              f"{100 * sh['kernels'] / joint['seconds']:.1f} % of the plain wall")
        print(f"          _peak_chain_column {sh['chain_cum']:.1f} s over {sh['chain_calls']} calls "
              f"= {100 * sh['chain_cum'] / sh['total']:.1f} %")


if __name__ == "__main__":
    main()
