"""WP-1325, the form test out of sample: the WO3 cooling ramp, Durham TOPAS tutorials 9.3/9.4.

    .venv/bin/python docs/wp/1325-measure/wo3_ramp.py [--first=0] [--last=99]
        > docs/wp/1325-measure/wo3_chain_results.txt
    .venv/bin/python docs/wp/1325-measure/wo3_ramp.py --direction=backward \\
        --name=wo3_chain_back > docs/wp/1325-measure/wo3_chain_back_results.txt

Run from the repository root, forward then backward (300 K → 90 K, then
90 K → 300 K, each about six minutes).  The joint-fit scripts seed each
pattern from whichever chain fitted it better (``best_chain``).  The data is local-only (``tests/local_data.py``
registers it as ``durham-topas/wo3``) and the script declines when it is
absent.  Nothing of the tutorial is committed.  This file is also the module
the other ``wo3_*.py`` scripts import the model, the protocol and the chain
from.

**The data.**  ``d9_02592.raw`` holds 100 ranges cooled from 300 K to 90 K.
TOPAS's 100-pattern input (``parametric_05.inp`` § 2) gives each range's
temperature; its ``#list`` numbers ranges from 1, ``rx.read_pattern(scan=)``
from 0.  The file itself records no temperature.

**The model.**  The three phases, P2₁/n (γ, "m"), P-1 (δ, "t") and Pc (ε, "p"),
are read from ``d9_02592_3phase_01.inp`` by ``rx.read_project_model``.  Three
things are then taken from ``parametric_05.inp`` instead, since that is the
fit the equations come from:

* every atom's coordinates, from its site lines, matched by order within each
  phase.  TOPAS refines the W coordinates once across all 100 patterns and
  holds the O ones; here all are held at TOPAS's answer;
* each phase's starting cell, TOPAS's equations evaluated at the first pattern's
  temperature.  The single-pattern input's P-1 angles (90.52, 90.32, 90.13)
  sit 1.4° from the equations' 89.14 for α at 300 K, a weak phase's wandering;
* each phase's strain, ``Strain_G`` and ``Strain_L``: TOPAS's Gaussian and
  Lorentzian FWHM per tanθ, so ``gauss_strain`` = G² (a variance) and
  ``lor_strain`` = L.  TOPAS shares one pair per phase across all patterns;
  here each pattern refines its own, bounded at 1.0 (TOPAS caps at 0.5, and
  P-1's G sits on that cap).

**The protocol** is ``parametric_05.inp`` § 3-4 with three departures.

* Mirrored: 20-80° 2θ; Cu Kα1/Kα2 at rietx's 0.5 ratio; no monochromator; zero
  held at 0; per-pattern sample height (rietx ``sample_displacement``, ±0.5 mm,
  TOPAS's Rs of 217.5 mm since the input sets none); ``Simple_Axial_Model``
  5.74444 mm held, as S/L = H/L = 5.74444/217.5; six Chebyshev background terms
  per pattern; a scale per phase per pattern; one B per pattern for every atom
  of every phase, bounded [−4, 10] Å² as ``parametric_04.inp`` bounds it.
* No instrumental TCHZ (``parametric_05`` drops it), so the resolution
  function is U = V = X = Y = 0 and W = 1e-6 deg², held; the width is the axial
  term and each phase's strain.  rietx's Cu lines carry no intrinsic width.
  Their Lorentzian width goes as tanθ, so ``lor_strain`` absorbs it.
* Departures: coordinates held (above); strains per pattern (above); and in
  a joint fit the one B per pattern is **held at the chain's value**, since
  ``MultiHistogramRefinement`` has no tie verb and one B over 32 atoms is a
  tie.  Untied and tied joint fits hold the same B, so the nested comparison
  between them is unaffected.

The chain's plan: scale and background, displacement, cell, strain, then B.
A joint fit's: the same without B.  Cell edges may move ±1.5 % from the start;
angles keep TOPAS's own per-pattern windows (``parametric_05.inp`` § 5).

**This script** runs the chain over ranges ``first``..``last`` (0-based),
prints each pattern's Rwp, which phases its fit held as unseen
(``PHASE_UNCONSTRAINED``) and the cell trajectories with esds, saves
obs/calc/diff plots of a few patterns to the scratch directory, and caches the
chain's fitted models there for the joint-fit scripts.
"""

from __future__ import annotations

import json
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
from rietx.schemas.common import Parameter  # noqa: E402
from rietx.sequential import SequentialRefinement  # noqa: E402
from rietx.strategy.staged import RefinementPlan, Stage  # noqa: E402
from tests import local_data  # noqa: E402

DATASET = "durham-topas/wo3"
PHASE_INP = "d9_02592_3phase_01.inp"
SERIES_INP = "parametric_05.inp"
RAW = "d9_02592.raw"
RS_MM = 217.5  # TOPAS's default Rs; parametric_05.inp sets none
CELL_WINDOW = 0.015
B_START, B_MIN, B_MAX = -1.0, -4.0, 10.0
STRAIN_MAX = 1.0
SCRATCH = Path(os.environ.get(
    "WO3_SCRATCH",
    "/private/tmp/claude-501/-Users-yue-Code-rietx--claude-worktrees-claude-happy-bardeen-b6d4g0/"
    "fff668c4-fa90-4a1f-a866-e53050a71725/scratchpad/wo3"))

#: phase index -> (TOPAS's phase tag in parametric_05, free cell names)
PHASES = {0: ("m", "P21/n", ("a", "b", "c", "beta")),
          1: ("t", "P-1", ("a", "b", "c", "alpha", "beta", "gamma")),
          2: ("p", "Pc", ("a", "b", "c", "beta"))}
#: TOPAS's angle-equation parameter stems per (phase, angle)
ANGLE_STEMS = {(0, "beta"): "beta_m", (1, "alpha"): "alph_t", (1, "beta"): "beta_t",
               (1, "gamma"): "gamm_t", (2, "beta"): "beta_p"}
#: TOPAS's per-pattern angle windows (parametric_05.inp § 5's minmax macros)
ANGLE_WINDOWS = {(0, "beta"): (90.0, 92.0), (1, "alpha"): (87.0, 90.0),
                 (1, "beta"): (90.0, 92.0), (1, "gamma"): (90.0, 92.0),
                 (2, "beta"): (91.6, 91.8)}


def targets() -> dict[str, str]:
    """Every refinable cell parameter, keyed ``m_a``, ``t_alpha`` …"""
    return {f"{tag}_{name}": f"phases.{i}.cell.{name}"
            for i, (tag, _, names) in PHASES.items() for name in names}


# -- the protocol, from the local inputs ------------------------------------

def _number(token: str) -> float:
    return float(token.rstrip("`").split("_")[0])


def protocol(text: str) -> dict:
    """``parametric_05.inp``'s ranges, temperatures, equations, strains and sites."""
    rows = re.findall(r'"d9_02592\.raw"\s+(\d+)\s+(\d+)', text)
    if len(rows) != 111:
        raise SystemExit(f"{SERIES_INP}: expected 11 + 100 #list rows, found {len(rows)}")
    full = rows[11:]
    prm = {m.group(1): _number(m.group(2))
           for m in re.finditer(r"\bprm\s+!?(\w+)\s+(-?\d[\d.eE+-]*`?)", text)}
    theta = prm["theta_ma"]
    strains = {}
    for tag, name in (("m", "p21n"), ("t", "pb1"), ("p", "pc")):
        g = re.search(rf"Strain_G\(strainG_{name},\s*([\d.eE+-]+)", text)
        lo = re.search(rf"Strain_L\(strainL_{name},\s*([\d.eE+-]+)", text)
        strains[tag] = (float(g.group(1)), float(lo.group(1)))
    # site lines per str block, in order: A1(param, value, value2)
    blocks = re.split(r"\n\s*str\s*\n", text)[1:4]
    sites = []
    for block in blocks:
        rows_xyz = []
        for m in re.finditer(r"site\s+(\w+)\s+A1\(\s*!?\w+,\s*(-?[\d.]+)`?\s*,[^)]*\)\s*"
                             r"A2\(\s*!?\w+,\s*(-?[\d.]+)`?\s*,[^)]*\)\s*"
                             r"A3\(\s*!?\w+,\s*(-?[\d.]+)`?\s*,[^)]*\)", block):
            rows_xyz.append((m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))))
        sites.append(rows_xyz)
    return dict(
        ranges=[int(r) - 1 for _, r in full],
        temps=[float(t) for t, _ in full],
        theta=theta, prm=prm, strains=strains, sites=sites,
        axial_mm=_number(re.search(r"Simple_Axial_Model\(!axial,\s*([\d.]+)", text).group(1)),
        limits=(float(re.search(r"start_X\s+([\d.]+)", text).group(1)),
                float(re.search(r"finish_X\s+([\d.]+)", text).group(1))),
    )


def einstein(t: float, theta: float) -> float:
    """1/(exp(θ/T) − 1), the Einstein term of TOPAS's cell-edge equation."""
    return 1.0 / math.expm1(theta / t)


def topas_equation(proto: dict, phase: int, name: str, t: float) -> float:
    """TOPAS's parametric_05 equation for one cell parameter at temperature t."""
    tag = PHASES[phase][0]
    prm = proto["prm"]
    if name in "abc":
        return prm[f"zero_{tag}{name}"] + prm[f"grad_{tag}{name}"] * einstein(t, proto["theta"])
    stem = ANGLE_STEMS[(phase, name)]
    c0, c1, c2 = prm[f"{stem}0"], prm[f"{stem}1"], prm[f"{stem}2"]
    return c0 * (1 + c1 * 1e-6 * t + c2 * 1e-9 * t * t)


def structure(where: Path, proto: dict, t_start: float) -> rx.Structure:
    model = rx.read_project_model(where / PHASE_INP, diagnostics=[])
    phases = model.to_structure().phases
    if len(phases) != 3:
        raise SystemExit(f"{PHASE_INP} gave {len(phases)} phases, not 3")
    for i, phase in enumerate(phases):
        sites = proto["sites"][i]
        if len(sites) != len(phase.atoms):
            raise SystemExit(f"phase {i}: {len(sites)} TOPAS sites, {len(phase.atoms)} atoms")
        for atom, (_, x, y, z) in zip(phase.atoms, sites, strict=True):
            atom.x.value, atom.y.value, atom.z.value = x, y, z
            atom.biso = Parameter(value=B_START, min=B_MIN, max=B_MAX, unit="A^2")
        cell = phase.cell
        for name in PHASES[i][2]:
            p = getattr(cell, name)
            p.value = topas_equation(proto, i, name, t_start)
            if name in "abc":
                p.min, p.max = p.value * (1 - CELL_WINDOW), p.value * (1 + CELL_WINDOW)
            else:
                p.min, p.max = ANGLE_WINDOWS[(i, name)]
                p.value = min(max(p.value, p.min + 1e-3), p.max - 1e-3)
        g, lo = proto["strains"][PHASES[i][0]]
        phase.gauss_strain = Parameter(value=g * g, min=0.0, max=STRAIN_MAX, unit="deg^2")
        phase.lor_strain = Parameter(value=lo, min=0.0, max=STRAIN_MAX, unit="deg")
        phase.gauss_size = Parameter.positive(0.0, unit="deg^2")
        phase.lor_size = Parameter.positive(0.0, unit="deg")
    return rx.Structure(phases=phases)


def instrument(proto: dict) -> rx.Instrument:
    inst = rx.Instrument.bragg_brentano(radiation="CuKa", goniometer_radius_mm=RS_MM)
    prof = inst.profile
    prof.u = Parameter(value=0.0, unit="deg^2")
    prof.v = Parameter(value=0.0, unit="deg^2")
    prof.w = Parameter.positive(1e-6, unit="deg^2")
    prof.x = Parameter.positive(0.0, unit="deg")
    prof.y = Parameter.positive(0.0, unit="deg")
    axial = proto["axial_mm"] / RS_MM
    inst.geometry.axial_sl = Parameter(value=axial, min=0.0, max=0.2)
    inst.geometry.axial_hl = Parameter(value=axial, min=0.0, max=0.2)
    inst.geometry.sample_displacement = Parameter(value=0.0, min=-0.5, max=0.5, unit="mm")
    inst.background.coefficients = [Parameter(value=0.0) for _ in range(6)]
    return inst


def plan(with_b: bool) -> RefinementPlan:
    stages = [
        Stage(name="scale_bkg", turn_on=["phases.*.scale", "instrument.background.*"]),
        Stage(name="disp", turn_on=["instrument.geometry.sample_displacement"]),
        Stage(name="cell", turn_on=["phases.*.cell.*"]),
        Stage(name="strain", turn_on=["phases.*.lor_strain", "phases.*.gauss_strain"]),
    ]
    if with_b:
        stages.append(Stage(name="b", turn_on=["vars.B"]))
    return RefinementPlan(stages=stages)


def one_b(index: int, ref) -> None:
    """The chain's constrain hook: one B per pattern for every atom."""
    ref.add_variable("B", B_START, min=B_MIN, max=B_MAX, unit="A^2")
    ref.tie_equal("phases.*.atoms.*.biso", source="vars.B")


def load(first: int = 0, last: int = 99, direction: str = "forward") -> dict:
    where = local_data.dataset(DATASET)
    if where is None:
        raise SystemExit(f"{DATASET} is not on this machine: python -m tests.local_data {DATASET}")
    proto = protocol((where / SERIES_INP).read_text(encoding="utf-8", errors="replace"))
    window = list(range(first, last + 1))
    temps = np.array([proto["temps"][k] for k in window])
    patterns = [rx.read_pattern(where / RAW, scan=proto["ranges"][k]) for k in window]
    t_start = temps[0] if direction == "forward" else temps[-1]
    start = (structure(where, proto, t_start), instrument(proto))
    return dict(where=where, proto=proto, window=window, temps=temps,
                patterns=patterns, start=start, direction=direction)


# -- the chain ---------------------------------------------------------------

def _total_chi2(s) -> float:
    """``Statistics.chi2`` is reduced, over max(N - P, 1)."""
    return s.chi2 * max(s.n_points - s.n_free_parameters, 1)


def run_chain(data: dict, plots: dict[int, str] | None = None) -> dict:
    """The warm-started chain; ``plots`` maps a window index to a PNG stem."""
    plots = plots or {}

    def on_result(k, result):
        if k in plots:
            stem = SCRATCH / plots[k]
            rx.viz.plot_result(result, path=str(stem) + ".png", dpi=110,
                               title=f"WO3 {data['temps'][k]:.0f} K")
            rx.viz.plot_result(result, path=str(stem) + "_zoom.png", dpi=110,
                               two_theta_range=(22.5, 25.5),
                               title=f"WO3 {data['temps'][k]:.0f} K, 22.5-25.5°")

    t0 = time.perf_counter()
    series = SequentialRefinement(*data["start"])
    result = series.fit(data["patterns"], x=data["temps"].tolist(), x_label="T (K)",
                        plan=plan(True), two_theta_limits=data["proto"]["limits"],
                        constrain=one_b, on_result=on_result,
                        direction=data.get("direction", "forward"))
    seconds = time.perf_counter() - t0
    traj = {}
    for key, path in targets().items():
        v = np.full(len(data["patterns"]), np.nan)
        e = np.full(len(data["patterns"]), np.nan)
        for k, entry in enumerate(result.entries):
            row = next((p for p in entry.parameters if p.path == path), None)
            if row is not None and row.stderr is not None:
                v[k], e[k] = row.value, row.stderr
        traj[key] = (v, e)
    return dict(seconds=seconds, series=series, result=result, traj=traj)


def unseen_phases(entry) -> list[int]:
    """The phases one chain entry's fit held as unseen (``PHASE_UNCONSTRAINED``)."""
    out = set()
    for d in entry.diagnostics:
        if d.code == "PHASE_UNCONSTRAINED":
            for w in d.where or []:
                m = re.match(r"phases\.(\d+)\.", w)
                if m:
                    out.add(int(m.group(1)))
    return sorted(out)


def save_chain(data: dict, chain: dict, name: str) -> Path:
    path = SCRATCH / f"{name}.json"
    payload = dict(
        window=data["window"], temps=data["temps"].tolist(),
        structures=[s.model_dump(mode="json") for s in chain["series"].fitted_structures],
        instruments=[i.model_dump(mode="json") for i in chain["series"].fitted_instruments],
        traj={k: [np.nan_to_num(v, nan=-1).tolist(), np.nan_to_num(e, nan=-1).tolist()]
              for k, (v, e) in chain["traj"].items()},
        seconds=chain["seconds"],
        rwp=[e.statistics.rwp if e.statistics else None for e in chain["result"].entries],
        chi2=[_total_chi2(e.statistics) if e.statistics else None
              for e in chain["result"].entries],
        unseen=[unseen_phases(e) for e in chain["result"].entries],
        status=[e.status for e in chain["result"].entries],
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def load_chain(name: str) -> dict | None:
    path = SCRATCH / f"{name}.json"
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["structures"] = [rx.Structure.model_validate(s) for s in raw["structures"]]
    raw["instruments"] = [rx.Instrument.model_validate(i) for i in raw["instruments"]]
    raw["traj"] = {k: (np.where(np.array(v) == -1, np.nan, v), np.where(np.array(e) == -1, np.nan, e))
                   for k, (v, e) in raw["traj"].items()}
    return raw


def best_chain(names: tuple[str, ...] = ("wo3_chain", "wo3_chain_back")) -> dict | None:
    """Per pattern, the cached chain answer with the lower χ².

    The forward chain left Pc's c on its lower bound (7.567 Å, against 7.68
    either side) from 221 K to 206 K, a minimum the warm start carried down
    until 204 K; the backward chain reaches those patterns from the side where
    Pc is the major phase.  A joint fit seeded in a wrong minimum would make
    its untied refit a worse fit than the tied one, so every joint fit starts
    from each pattern's better answer.  ``source`` says which chain gave it.
    """
    chains = [load_chain(n) for n in names]
    chains = [c for c in chains if c is not None]
    if not chains:
        return None
    if any(c["window"] != chains[0]["window"] for c in chains):
        raise SystemExit(f"the cached chains {names} cover different windows")
    n = len(chains[0]["window"])
    pick = [min(range(len(chains)), key=lambda j, k=k: chains[j]["chi2"][k]) for k in range(n)]
    out = dict(window=chains[0]["window"], temps=chains[0]["temps"],
               seconds=sum(c["seconds"] for c in chains),
               source=[names[j] for j in pick])
    for field in ("structures", "instruments", "rwp", "chi2", "unseen", "status"):
        out[field] = [chains[pick[k]][field][k] for k in range(n)]
    out["traj"] = {key: (np.array([chains[pick[k]]["traj"][key][0][k] for k in range(n)]),
                         np.array([chains[pick[k]]["traj"][key][1][k] for k in range(n)]))
                   for key in chains[0]["traj"]}
    out["chains"] = {names[j]: chains[j] for j in range(len(chains))}
    return out


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


def parse_args(argv: list[str], defaults: dict) -> dict:
    out = dict(defaults)
    for arg in argv:
        key, _, value = arg.removeprefix("--").partition("=")
        if key not in out:
            raise SystemExit(f"unknown argument {arg!r}")
        out[key] = type(out[key])(value) if value else 1
    return out


def main() -> None:
    args = parse_args(sys.argv[1:], {"first": 0, "last": 99, "name": "wo3_chain",
                                     "direction": "forward"})
    SCRATCH.mkdir(parents=True, exist_ok=True)
    data = load(args["first"], args["last"], args["direction"])
    n = len(data["window"])
    print("WP-1325 out-of-sample measurement: the WO3 cooling ramp (Durham TOPAS 9.3/9.4)")
    for line in machine():
        print(line)
    print(f"window    ranges {data['window'][0]}..{data['window'][-1]} (0-based), {n} patterns, "
          f"T {data['temps'].max():.0f} -> {data['temps'].min():.0f} K")
    first_t = data["temps"][0 if args["direction"] == "forward" else -1]
    print(f"direction {args['direction']}; the first fit starts from TOPAS's equations at {first_t:.0f} K")
    print(f"protocol  chain plan {[s.name for s in plan(True).stages]}; 2θ "
          f"{data['proto']['limits']}; θ_E {data['proto']['theta']:.6f} K")
    s0 = data["start"][0]
    for i, phase in enumerate(s0.phases):
        cell = phase.cell
        print(f"start     {phase.name}: " + ", ".join(
            f"{name} {getattr(cell, name).value:.5f}" for name in PHASES[i][2])
            + f"; gauss_strain {phase.gauss_strain.value:.4f}, lor_strain {phase.lor_strain.value:.4f}")
    print(flush=True)
    picks = sorted({0, n // 4, n // 2, (3 * n) // 4, n - 1})
    tag = "" if args["direction"] == "forward" else "back_"
    chain = run_chain(data, {k: f"chain_{tag}{data['temps'][k]:.0f}K" for k in picks})
    res = chain["result"]
    stats = [e.statistics for e in res.entries]
    print(f"chain     {chain['seconds']:.1f} s ({chain['seconds'] / n:.2f} s a pattern); "
          f"status {sorted(set(e.status for e in res.entries))}; rungs "
          f"{sorted(set(e.rung for e in res.entries))}; "
          f"Rwp {100 * min(s.rwp for s in stats):.2f}-{100 * max(s.rwp for s in stats):.2f} %")
    print("series diagnostics:", sorted({d.code for d in res.diagnostics}))
    path = save_chain(data, chain, args["name"])
    print(f"cached    {path.name} in the scratch directory")
    print()
    print("per pattern: T, Rwp %, GoF, unseen phases (PHASE_UNCONSTRAINED), rung, B, wt % by phase")
    for k, e in enumerate(res.entries):
        b = next((p for p in e.parameters if p.path == "vars.B"), None)
        wt = ""
        if e.qpa is not None:
            wt = " ".join(f"{100 * q.weight_fraction:5.1f}" for q in e.qpa.phases)
        print(f"  {data['temps'][k]:5.0f} {100 * e.statistics.rwp:6.2f} {e.statistics.gof:5.2f} "
              f"{str(unseen_phases(e)):9} {e.rung:11} "
              f"{(f'{b.value:6.3f}' if b else '  held')} {wt}")
    print()
    print("chain trajectories (T: value(esd); nan = not reported, held or unseen):")
    for key in targets():
        v, e = chain["traj"][key]
        print(f"  {key}: " + " ".join(
            f"{t:.0f}:{x:.5f}({s:.5f})" for t, x, s in zip(data["temps"], v, e)))


if __name__ == "__main__":
    main()
