"""WP-1325, the form test out of sample: the ZrP2O7 ramp's model and protocol.

Durham TOPAS tutorial 9.5 (Stinton & Evans, 2007, *J. Appl. Cryst.* 40, 87):
ZrP2O7 with a silicon standard and Al2O3, heated 303 K -> 1173 K and cooled
back to 304 K.  This module builds the model and the fits; the measurement
drivers beside it (``zrp2o7_form.py``, ``zrp2o7_overflex.py``) import it.
It runs nothing itself.

The data is local-only: ``tests/local_data.py`` registers it as
``durham-topas/zrp2o7``, and every driver declines when it is absent.  Nothing
of the tutorial is committed.  The 37 ranges, their set temperatures, the 2θ
window, the monochromator angle, the axial term and the three phases are
parsed from the input at run time.

**Why by hand.**  ``rx.read_topas_inp`` refuses this input on its ``B1(...)``
site macros, which only the Al2O3 block uses (and whose ``param`` argument the
macro ignores, so the Al and O coordinates are fixed).  So :func:`phases_of`
reads the first pattern's three ``str`` blocks itself: cell, sites (species,
occupancy, coordinates, Biso) and the per-phase TCHZ.

* ZrP2O7, ``Pa-3``, the 8.25 Å subcell: Zr 4a, P 8c (x, x, x), O1 24d, O2 4b.
* silicon, ``Fd-3m`` read as origin choice 1 (``num_posns 8`` at (0, 0, 0)).
* Al2O3, ``R-3c`` read on hexagonal axes: Al 12c, O 18e.

**The protocol, and where it departs from TOPAS's.**

* Cu Kα1 only, monochromator 2θ from ``LP_Factor``, 2θ from ``start_X`` to
  ``finish_X``, zero held at 0 as the input holds it.
* The axial term is held, as the input holds ``ax_overall``.  TOPAS's
  ``Simple_Axial_Model(v)`` sets the filament, sample and receiving-slit full
  lengths to v mm, and FCJ's S/L and H/L take half-lengths, so both are
  v/2 over a 217.5 mm radius (TOPAS's default; the input sets none).
  ``real_ramp.py`` uses v/L.  On five patterns here (303, 753, 1173, 752 and
  304 K, single fits), v/2L lowered χ²_red by 0.045-0.085 against v/L, and
  freeing both terms on the 303 K pattern took them to 0.016-0.019.
* TOPAS adds a global 2θ calibration curve, quadratic in (2θ - 54°)
  (``step_error``, ``square``): 0.011° at 15° and 0.006° at 90°, the same in
  every pattern.  rietx has no such term, so it is left out.  It is constant
  across the ramp, so it can shift a cell but not bend a trajectory.
* TOPAS refines one TCHZ profile per phase, shared by all 37 patterns.  Here
  the instrument profile is a small constant (W, X) held fixed, and each
  phase's four sample-broadening terms refine per pattern, seeded from the
  input's per-phase TCHZ read by argument position (slots u, v, w, z, x, y;
  WP-1455): ``gauss_size`` from z, ``gauss_strain`` from u, ``lor_size`` from
  y (1/cosθ), ``lor_strain`` from x (tanθ), negatives clipped to 0.
* Per pattern, as TOPAS: the three scales, an 18-term Chebyshev background,
  one specimen displacement shared by the phases, every Biso, and the P x
  coordinate.
* TOPAS computes the Si and Al2O3 cells from the temperature (Einstein terms,
  Taylor's quadratic) and refines its temperature calibration.  Here all four
  cell edges refine per pattern instead: the WP declares equations in the set
  temperature on cell edges, never on a coordinate.

The plan is ``scale_bkg``, ``disp``, ``cell``, ``sample_profile``, ``biso``,
then the P coordinate, cumulative as rietx's staged plans are.  Cells may move
±1.5 % from the input's values.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.schemas.common import Parameter  # noqa: E402
from rietx.sequential import SequentialRefinement  # noqa: E402
from rietx.strategy.staged import RefinementPlan, Stage  # noqa: E402
from tests import local_data  # noqa: E402

DATASET = "durham-topas/zrp2o7"
INP = "d8_02999_35_annotate_04.inp"
RAW = "d8_02999.raw"
CELL_WINDOW = 0.015
N_BKG = 18
RADIUS_MM = 217.5  # TOPAS's default Rs; the input sets none
TARGETS = {
    "zrp_a": "phases.0.cell.a",
    "si_a": "phases.1.cell.a",
    "al_a": "phases.2.cell.a",
    "al_c": "phases.2.cell.c",
}
#: the input's space-group symbols in gemmi's spelling, with the setting its
#: sites imply: Si at (0, 0, 0) with 8 positions is origin choice 1, and the
#: Al2O3 cell (a, a, c, 90°, 90°, 120°) is the hexagonal setting
SPACE_GROUPS = {"Pa-3": "P a -3", "Fd-3m": "F d -3 m:1", "R-3c": "R -3 c:H"}


def _number(token: str) -> float:
    """A TOPAS value as written: ``0.0066_0.0044`` (value_esd), ``3.41``` (refined)."""
    return float(token.rstrip("`").split("_")[0])


def _call_args(text: str, name: str) -> list[str]:
    match = re.search(rf"\b{name}\(([^)]*)\)", text)
    if match is None:
        raise SystemExit(f"{INP} has no {name}(...) call")
    return [a.strip() for a in match.group(1).split(",")]


def _last_number(arg: str) -> float:
    """``lpa_zrp2o7_t_0303  8.245820``` or ``=lpa_si_t_0303;:5.431294``: the value."""
    return float(re.findall(r"-?\d+\.?\d*", arg)[-1])


def _site(line: str) -> dict:
    coords = []
    for axis, macro in (("x", "B1"), ("y", "B2"), ("z", "B3")):
        m = (re.search(rf"\b{macro}\(\s*[^,]*,\s*(-?[\d.]+)", line)
             or re.search(rf"\s{axis}\s+(?:[A-Za-z_]\w*\s+)?(-?[\d.]+)", line))
        coords.append(float(m.group(1)))
    occ = re.search(r"\bocc\s+([A-Za-z]+)\s+([\d.]+)", line)
    beq = re.search(r"\bbeq\s+(?:[A-Za-z_]\w*\s+)?(-?[\d.]+)", line)
    return dict(label=line.split()[1], species=occ.group(1), occ=float(occ.group(2)),
                xyz=coords, biso=float(beq.group(1)))


def phases_of(text: str) -> list[dict]:
    """The first pattern's three ``str`` blocks, as plain numbers."""
    start = text.index("#ifdef use_t_0303")
    block = text[start:text.index('out "temp.res"', start)]
    out = []
    for part in re.split(r"\n\s*str\b", block)[1:]:
        cubic = re.search(r"\bCubic\(([^)]*)\)", part)
        trig = re.search(r"\bTrigonal\(([^)]*)\)", part)
        if cubic is not None:
            a, c, hexagonal = _last_number(cubic.group(1)), None, False
        else:
            a, c = (_last_number(x) for x in trig.group(1).split(","))
            hexagonal = True
        out.append(dict(
            name=re.search(r"phase_name\s+(\S+)", part).group(1),
            space_group=re.search(r"space_group\s+(\S+)", part).group(1),
            a=a, c=c, hexagonal=hexagonal,
            tchz=[_number(x) for x in _call_args(part, "TCHZ_Peak_Type")[1::2]],
            sites=[_site(line) for line in part.splitlines() if line.strip().startswith("site ")],
        ))
    if [p["name"] for p in out] != ["ZrP2O7", "silicon", "Al2O3"]:
        raise SystemExit(f"{INP}: expected ZrP2O7, silicon and Al2O3, read "
                         f"{[p['name'] for p in out]}")
    return out


def _p(v: float, **kw) -> Parameter:
    return Parameter(value=v, **kw)


def _cell(a: float, c: float | None = None, hexagonal: bool = False) -> rx.Cell:
    def edge(v):
        return _p(v, min=v * (1 - CELL_WINDOW), max=v * (1 + CELL_WINDOW))
    c = a if c is None else c
    return rx.Cell(a=edge(a), b=edge(a), c=edge(c), alpha=_p(90.0), beta=_p(90.0),
                   gamma=_p(120.0 if hexagonal else 90.0))


def structure(proto: dict) -> rx.Structure:
    phases = []
    for ph in proto["phases"]:
        if len(ph["tchz"]) != 6:
            raise SystemExit(f"{ph['name']}: TCHZ_Peak_Type has {len(ph['tchz'])} values, not 6")
        u, _v, _w, z, x, y = ph["tchz"]  # by argument position (WP-1455)
        phases.append(rx.Phase(
            name=ph["name"], space_group=SPACE_GROUPS[ph["space_group"]],
            cell=_cell(ph["a"], ph["c"], ph["hexagonal"]),
            atoms=[rx.Atom(label=s["label"], species=s["species"],
                           x=_p(s["xyz"][0]), y=_p(s["xyz"][1]), z=_p(s["xyz"][2]),
                           occ=_p(s["occ"]), biso=_p(s["biso"], min=0.0, max=25.0))
                   for s in ph["sites"]],
            scale=_p(1.0, min=0.0),
            gauss_size=Parameter.positive(max(z, 0.0), max=0.25),
            gauss_strain=Parameter.positive(max(u, 0.0), max=0.25),
            lor_size=Parameter.positive(max(y, 0.0), max=0.50),
            lor_strain=Parameter.positive(max(x, 0.0), max=0.50)))
    return rx.Structure(phases=phases)


def protocol(text: str) -> dict:
    """The input's ranges, set temperatures, window, monochromator, axial term, phases."""
    rows = [(int(m.group(1)), int(m.group(2))) for m in re.finditer(
        r"#define use_t_\d+ prm !set_t_\d+\s+(\d+) macro r_t_\d+ \{\s*(\d+) \}", text)]
    ax = re.search(r"prm !ax_overall\s+([\d.]+)", text)
    return dict(
        temps=[float(t) for t, _ in rows],
        scans=[r - 1 for _, r in rows],  # TOPAS numbers ranges from 1
        mono=_number(re.search(r"LP_Factor\(!th2_monochromator,\s*([\d.]+)\)", text).group(1)),
        limits=(float(re.search(r"start_X\s+([\d.]+)", text).group(1)),
                float(re.search(r"finish_X\s+([\d.]+)", text).group(1))),
        axial_mm=float(ax.group(1)),
        phases=phases_of(text),
    )


def instrument(proto: dict) -> rx.Instrument:
    inst = rx.Instrument.bragg_brentano(radiation="CuKa1", monochromator_two_theta=proto["mono"])
    prof = inst.profile
    prof.u = Parameter(value=0.0, min=-0.05, max=1.0, unit="deg^2")
    prof.v = Parameter(value=0.0, min=-0.5, max=0.5, unit="deg^2")
    prof.w = Parameter.positive(0.001, max=1.0, unit="deg^2")
    prof.x = Parameter.positive(0.001, max=1.0, unit="deg")  # 1/cosθ
    prof.y = Parameter.positive(0.0, max=1.0, unit="deg")  # tanθ
    # TOPAS's Simple_Axial_Model(v) sets the filament, sample and receiving
    # slit *full* lengths to v mm; FCJ's S/L and H/L take half-lengths.
    axial = proto["axial_mm"] / 2 / RADIUS_MM
    inst.geometry.axial_sl = Parameter(value=axial, min=0.0, max=0.2)
    inst.geometry.axial_hl = Parameter(value=axial, min=0.0, max=0.2)
    inst.geometry.sample_displacement = Parameter(value=0.0, min=-1.0, max=1.0, unit="mm")
    inst.background.coefficients = [Parameter(value=0.0) for _ in range(N_BKG)]
    return inst


def plan() -> RefinementPlan:
    base = {s.name: s for s in rx.PLAN_PRESETS["lab_sample_refine"]().stages}
    stages = [base[n] for n in ("scale_bkg", "disp", "cell", "sample_profile")]
    stages.append(Stage(name="biso", turn_on=["phases.*.atoms.*.biso"]))
    stages.append(Stage(name="p_x", turn_on=["phases.0.atoms.1.dof.*"]))
    return RefinementPlan(stages=stages)


def load() -> dict:
    where = local_data.dataset(DATASET)
    if where is None:
        raise SystemExit(f"{DATASET} is not on this machine: python -m tests.local_data {DATASET}")
    text = (where / INP).read_text(encoding="utf-8", errors="replace")
    proto = protocol(text)
    if len(proto["temps"]) != 37:
        raise SystemExit(f"{INP}: {len(proto['temps'])} ranges, not 37")
    patterns = [rx.read_pattern(where / RAW, scan=k) for k in proto["scans"]]
    temps = np.array(proto["temps"])
    top = int(np.argmax(temps))
    heat = list(range(0, top + 1))       # 303 K .. 1173 K, the top point heating's
    cool = list(range(top + 1, len(temps)))  # 1152 K .. 304 K
    return dict(proto=proto, patterns=patterns, temps=temps, heat=heat, cool=cool)


# -- the fits ----------------------------------------------------------------

def total_chi2(s) -> float:
    """``Statistics.chi2`` is reduced, over max(N - P, 1)."""
    return s.chi2 * max(s.n_points - s.n_free_parameters, 1)


def run_chain(data: dict) -> dict:
    t0 = time.perf_counter()
    series = SequentialRefinement(structure(data["proto"]), instrument(data["proto"]))
    result = series.fit(data["patterns"], x=data["temps"].tolist(), x_label="T (K)",
                        plan=plan(), two_theta_limits=data["proto"]["limits"])
    seconds = time.perf_counter() - t0
    traj = {}
    n = len(data["patterns"])
    for key, path in TARGETS.items():
        v = np.full(n, np.nan)
        e = np.full(n, np.nan)
        for k, entry in enumerate(result.entries):
            row = next((p for p in entry.parameters if p.path == path), None)
            if row is not None and row.stderr is not None:
                v[k], e[k] = row.value, row.stderr
        traj[key] = (v, e)
    stats = [e.statistics for e in result.entries]
    return dict(seconds=seconds, traj=traj, series=series, result=result,
                status=[e.status for e in result.entries],
                chi2=sum(total_chi2(s) for s in stats),
                n_free=sum(s.n_free_parameters for s in stats),
                n_points=sum(s.n_points for s in stats),
                rwp=[s.rwp for s in stats])


def poly_equation(name: str, key: str, degree: int, patterns: list[int] | None) -> rx.ParametricEquation:
    return rx.ParametricEquation(name=name, target=TARGETS[key], basis="polynomial",
                                 terms=[["T"] * j for j in range(degree + 1)], patterns=patterns)


def run_joint(data: dict, chain: dict, equations: list[rx.ParametricEquation]) -> dict:
    series = chain["series"]
    t0 = time.perf_counter()
    fit = rx.MultiHistogramRefinement(
        list(series.fitted_structures), list(series.fitted_instruments),
        sharing=SharingMap(per_histogram=["phases.*"]),
        coordinates=rx.CoordinateTable(columns={"T": data["temps"].tolist()}, units={"T": "K"}),
        parametric=equations or None)
    result = fit.fit(data["patterns"], plan=plan(), two_theta_limits=data["proto"]["limits"])
    s = result.statistics
    return dict(seconds=time.perf_counter() - t0, fit=fit, result=result,
                chi2=total_chi2(s), n_free=s.n_free_parameters, chi2r=s.chi2,
                inflation=s.esd_inflation, rwp=s.rwp)


def reading(r) -> str:
    if r is None or r.statistic is None:
        return "not tested"
    verdict = "REJECT" if r.rejected else "keep"
    return (f"{r.statistic:8.1f} for {r.dof:3d} dof, cut {r.cut:6.1f}, "
            f"p {r.p_value:.3g} {verdict}")


def machine() -> list[str]:
    from real_ramp import machine as _machine

    return _machine()
