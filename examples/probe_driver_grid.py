"""WP-1937: does each acceptance fit reach one minimum, under each driver?

Run: ``.venv/bin/python examples/probe_driver_grid.py [--jobs N] [--out DIR]
[--fits a,b] [--arms softplus:trf,physical:lm]``

Fourteen fits from the acceptance suites, each built by its own test module,
run from five starts.  Start k multiplies every ``Parameter.value`` in the
input structure and instrument by (1 + k·1e-14), a rounding-sized change.  A
fit whose χ²_red agrees across the five to under 1e-9 relative has one
answer; WP-1929 found fits that did not, and traced them to widths refined in
softplus coordinates near zero.

Each **arm** is a coordinate system and a driver:

* ``softplus`` is the tree as it is.  ``physical`` monkeypatches
  ``ParameterTable.__init__`` so every softplus entry becomes an identity
  entry with ``lo = max(lo, 0)``: WP-1929's definition, and what WP-1938 makes
  the default.  Once it lands the two arms are the same.
* ``trf`` / ``lm`` force the driver on every solve, by rebinding
  ``run_least_squares`` and ``run_multi_least_squares`` in each loaded
  ``rietx`` module (``rietx.refine`` imports the function by name).

Both patches are process-wide, so each (fit, arm) cell runs in its own
subprocess, ``--jobs`` at a time.  Each cell writes one JSON line per start to
``--out``; the table printed at the end reads them back, so an interrupted run
resumes where it stopped.  Nothing here is a wall-clock number.

Measured 2026-10-10 (macOS arm64, ``[dev]``, ``src`` at ``790c7ce7``): fits
over the 1e-9 bar were 3 of 14 under softplus + TRF (today's default), 7
under softplus + LM, 4 under physical + TRF and 2 under physical + LM.  On
the WP's final tree, whose LM start is no longer nudged off its bounds,
physical + LM misses on brucite + Stephens alone (2.1e-6).  The handover
entry of ``docs/wp/1937-a-bounded-step-solved-exactly.md`` has the tables.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

STARTS = (0, 1, 2, 3, 4)
BAR = 1e-9
ARMS = ("softplus:trf", "softplus:lm", "physical:trf", "physical:lm")


# ------------------------------------------------------------- the patches
def _install_solver(solver: str, calls: list[dict]) -> None:
    import rietx.optimize.least_squares as ls

    single_orig, multi_orig = ls.run_least_squares, ls.run_multi_least_squares

    def single(*a, **kw):
        kw["solver"] = solver
        out = single_orig(*a, **kw)
        calls.append({"stage": kw.get("stage", ""), "solver": out.solver,
                      "status": out.status, "nfev": out.n_iterations})
        return out

    def multi(*a, **kw):
        kw["solver"] = solver
        out = multi_orig(*a, **kw)
        calls.append({"stage": "multi", "solver": out.solver,
                      "status": out.status, "nfev": out.n_iterations})
        return out

    for mod in list(sys.modules.values()):
        if not getattr(mod, "__name__", "").startswith("rietx"):
            continue
        for name, orig, new in (("run_least_squares", single_orig, single),
                                ("run_multi_least_squares", multi_orig, multi)):
            if getattr(mod, name, None) is orig:
                setattr(mod, name, new)


def _install_physical() -> None:
    from rietx.params import vector

    orig = vector.ParameterTable.__init__

    def init(self, *a, **kw):
        orig(self, *a, **kw)
        for e in self.entries:
            if e.transform == "softplus":
                e.transform = "identity"
                e.lo = max(e.lo, 0.0)

    vector.ParameterTable.__init__ = init


def _nudge(obj, factor: float, seen: set[int] | None = None) -> None:
    """Multiply every ``Parameter.value`` reachable from ``obj`` by ``factor``."""
    import pydantic

    import rietx as rx

    seen = set() if seen is None else seen
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, rx.Parameter):
        v = obj.value
        if isinstance(v, float) and math.isfinite(v) and v != 0.0:
            lo = -math.inf if obj.min is None else obj.min
            hi = math.inf if obj.max is None else obj.max
            if lo <= v * factor <= hi:
                obj.value = v * factor
    elif isinstance(obj, pydantic.BaseModel):
        for name in type(obj).model_fields:
            _nudge(getattr(obj, name), factor, seen)
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            _nudge(x, factor, seen)
    elif isinstance(obj, dict):
        for x in obj.values():
            _nudge(x, factor, seen)


# ---------------------------------------------------------------- the fits
def _lab6(variant: str, f: float):
    import test_acceptance_lab6_cbn as m

    import rietx as rx

    widths = ["instrument.profile.u", "instrument.profile.v", "instrument.profile.w",
              "instrument.profile.x", "instrument.profile.y"]
    plans = {
        "shared": m.PLAN_SHARED,
        "degenerate": m.PLAN_DEGENERATE,
        # u v w x y freed together: WP-1936's free-Gaussian variant
        "uvwxy1": rx.RefinementPlan(stages=[
            *m._BASE, rx.Stage("profile", widths), *m._TAIL]),
        # the pre-WP-1930 schedule: w, then u v x y
        "uvwxy": rx.RefinementPlan(stages=[
            *m._BASE, rx.Stage("profile_w", [widths[2]]),
            rx.Stage("profile", [w for w in widths if w != widths[2]]), *m._TAIL]),
    }
    structure, ins = m._inputs()
    _nudge([structure, ins], f)
    ref = rx.Refinement(structure, ins, history=False)
    return ref.fit(rx.read_pattern(m.PATTERN), plan=plans[variant],
                   two_theta_limits=m.LIMITS)


def _bt1(which: int, f: float):
    import test_acceptance_wavelength as m

    import rietx as rx

    ins = m._xray_instrument() if which == 0 else m._neutron_instrument()
    limits = m.XRAY_LIMITS if which == 0 else m.NEUTRON_LIMITS
    structure = m._structure()
    _nudge([structure, ins], f)
    ref = rx.Refinement(structure, ins, history=False)
    return ref.fit(m._patterns()[which], plan="mccusker_structural",
                   two_theta_limits=limits)


def _nac(f: float):
    """The acceptance module's Le Bail pass, then its two-phase Rietveld fit."""
    import test_acceptance_nac as m

    import rietx as rx

    data, structure, instrument = m.build_nac_inputs()
    _nudge([structure, instrument], f)
    lebail = rx.Refinement(structure, instrument)
    lebail.fit(data, mode="lebail", two_theta_limits=m.LIMITS)
    structure2 = lebail.fitted_structure.model_copy(deep=True)
    instrument2 = lebail.fitted_instrument.model_copy(deep=True)
    structure2.phases[0].scale.value = 1e-6
    structure2.phases.append(m._caf2_phase())
    _nudge([structure2.phases[1]], f)
    plan = rx.RefinementPlan.mccusker_default()
    plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
    plan.intermediate_ftol = 1e-6
    return rx.Refinement(structure2, instrument2).fit(
        data, plan=plan, two_theta_limits=m.LIMITS)


def _fap(f: float):
    import test_acceptance_fap as m

    import rietx as rx

    data, structure, instrument = m.build_fap_inputs()
    _nudge([structure, instrument], f)
    return rx.Refinement(structure, instrument).fit(data, plan=m._gsas_protocol_plan())


def _capillary(f: float):
    import test_acceptance_capillary as m

    import rietx as rx

    structure = m._structure()
    ins = m._instrument(capillary=True, dispersion=False)
    _nudge([structure, ins], f)
    return rx.Refinement(structure, ins).fit(
        rx.read_pattern(m.DATA / "11BM_LaB6_660a.fxye"), plan=m._plan(),
        two_theta_limits=m.LIMITS)


def _absent(f: float):
    import test_absent_phase as m

    import rietx as rx

    structure, ins = m._absent_phase_inputs()
    _nudge([structure, ins], f)
    return rx.Refinement(structure, ins, history=False).fit(
        m.synthesize(), plan="mccusker_default")


def _si640c(f: float):
    import test_acceptance_si640c as m

    import rietx as rx

    structure, ins = m._structure(), m._instrument(m.FULL_LIMITS)
    _nudge([structure, ins], f)
    ref = rx.Refinement(structure, ins, history=False)
    ref.tie_equal(["instrument.geometry.axial_sl", "instrument.geometry.axial_hl"])
    return ref.fit(rx.read_pattern(m.PATTERN), plan=m._plan(asymmetric=True),
                   two_theta_limits=m.FULL_LIMITS)


def _stephens(which: str, f: float):
    import test_acceptance_stephens as m
    from test_acceptance_qpa_roundrobin import (
        brucite_phase,
        corundum_phase,
        qarr_instrument,
        seed_scales,
    )

    import rietx as rx

    if which == "corundum":
        name, phase = "corundum", corundum_phase()
        plan = m._plan(texture=False, stephens=False)
    elif which == "brucite_aniso":
        name, phase = "brucite", m._with_block(brucite_phase(textured=True))
        plan = m._plan(texture=True, stephens=True)
    else:
        name, phase = "brucite", brucite_phase(textured=True)
        plan = m._plan(texture=True, stephens=False)
    data = rx.read_pattern(m.DATA / f"{name}.prn")
    structure = rx.Structure(phases=[phase])
    ins = qarr_instrument()
    seed_scales(structure, ins, data)
    _nudge([structure, ins], f)
    return rx.Refinement(structure, ins).fit(data, plan=plan)


FITS = {
    "lab6_shared": lambda f: _lab6("shared", f),
    "lab6_degenerate": lambda f: _lab6("degenerate", f),
    "lab6_uvwxy": lambda f: _lab6("uvwxy", f),
    "lab6_uvwxy1": lambda f: _lab6("uvwxy1", f),
    "bt1_xray": lambda f: _bt1(0, f),
    "bt1_neutron": lambda f: _bt1(1, f),
    "nac": _nac,
    "fap": _fap,
    "capillary": _capillary,
    "absent_phase": _absent,
    "si640c": _si640c,
    "brucite_iso": lambda f: _stephens("brucite_iso", f),
    "corundum": lambda f: _stephens("corundum", f),
    "brucite_aniso": lambda f: _stephens("brucite_aniso", f),
}


# ------------------------------------------------------------- one cell
def run_cell(fit: str, arm: str, out: Path) -> None:
    """Every start of one (fit, arm), one JSON line each.  Runs in-process."""
    coord, solver = arm.split(":")
    calls: list[dict] = []
    if coord == "physical":
        _install_physical()
    _install_solver(solver, calls)
    with out.open("w", encoding="utf-8") as fh:
        for k in STARTS:
            calls.clear()
            row = {"fit": fit, "arm": arm, "k": k}
            try:
                result = FITS[fit](1.0 + k * 1e-14)
                row["chi2"] = result.statistics.chi2
                row["max_iter"] = sorted({s.name for s in result.stages
                                          if s.status == "max_iter"})
                row["nfev"] = sum(s.n_iterations for s in result.stages)
            except Exception:  # recorded, never fatal to the cell
                row["error"] = traceback.format_exc()[-2000:]
            row["calls"] = list(calls)
            fh.write(json.dumps(row) + "\n")
            fh.flush()


# ------------------------------------------------------------- the grid
def _cell_path(out: Path, fit: str, arm: str) -> Path:
    return out / f"{fit}__{arm.replace(':', '_')}.jsonl"


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _spawn(fit: str, arm: str, out: Path) -> str:
    path = _cell_path(out, fit, arm)
    if len(_rows(path)) == len(STARTS):
        return f"{fit} {arm}: kept"
    env = dict(os.environ, RIETX_TELEMETRY="0", MPLBACKEND="Agg",
               RIETX_COMPILED_THREADS="1")
    t0 = time.time()
    rc = subprocess.call([sys.executable, __file__, "--cell", fit, arm, str(path)],
                         cwd=ROOT, env=env)
    return f"{fit} {arm}: rc={rc}, {time.time() - t0:.0f} s"


def table(out: Path, fits: list[str], arms: list[str]) -> str:
    lines = ["| fit | arm | χ²_red min | spread | max_iter stages | Σ nfev |",
             "|---|---|---|---|---|---|"]
    for fit in fits:
        for arm in arms:
            rows = _rows(_cell_path(out, fit, arm))
            chi = [r["chi2"] for r in rows if "chi2" in r]
            if len(chi) < len(rows) or not rows:
                lines.append(f"| {fit} | {arm} | error or missing | | | |")
                continue
            spread = (max(chi) - min(chi)) / min(chi)
            mark = "" if spread < BAR else " ✗"
            stopped = sorted({s for r in rows for s in r["max_iter"]})
            nfev = [r["nfev"] for r in rows]
            lines.append(f"| {fit} | {arm} | {min(chi):.9f} | {spread:.1e}{mark} | "
                         f"{', '.join(stopped) or '—'} | {min(nfev)}–{max(nfev)} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--out", type=Path, default=Path("driver_grid"))
    p.add_argument("--fits", default=",".join(FITS))
    p.add_argument("--arms", default=",".join(ARMS))
    p.add_argument("--cell", nargs=3, metavar=("FIT", "ARM", "PATH"),
                   help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    if a.cell:
        run_cell(a.cell[0], a.cell[1], Path(a.cell[2]))
        return 0
    fits, arms = a.fits.split(","), a.arms.split(",")
    a.out.mkdir(parents=True, exist_ok=True)
    cells = [(fit, arm, a.out.resolve()) for fit in fits for arm in arms]
    with ThreadPoolExecutor(a.jobs) as pool:
        for line in pool.map(lambda c: _spawn(*c), cells):
            print(line, flush=True)
    print(table(a.out, fits, arms))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
