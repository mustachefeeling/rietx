"""WP-1114: peaks-buffer spike — can peak *shapes* be reused across 2θ?

Run: ``.venv/bin/python examples/bench_peaks_buffer.py``

TOPAS computes "a small number of peaks ... across the whole 2θ range"
(Coelho 2018, J. Appl. Cryst. 51, 210, §5.1) and reuses them; rietx evaluates
every (emission line, reflection) pair exactly on its own window.  This
script measures, on WP-1111's harness cases, what that reuse would cost in
accuracy and what it could win in arithmetic volume.  Nothing here touches
production code (WP-0605's spike discipline): the buffer exists only inside
this file.

Part 1 (``--part anchors``, the default) prints three tables per case/state:

* **volume** — how many profile elements one forward evaluation computes:
  ``sum win`` is window points summed over (line, reflection) pairs, and
  ``sum elem`` multiplies each window by its frozen FCJ image count (an
  FCJ-smeared peak evaluates the profile once per quadrature image).  The
  ratio ``elem/win`` is the factor a buffer removes *on top of* window
  overlap, and ``elem/pts`` is the whole per-evaluation volume relative to
  pattern points — the buffer's ceiling.
* **shape budget** — how much the shape actually varies across the range:
  Γ(2θ), η(2θ) and the FCJ extent, per phase.  These are the quantities an
  anchor grid must track.
* **anchors vs accuracy** — the WP's central measurement.  A reference set
  of exact shapes across the range is reconstructed from K anchors under
  the schemes in :data:`SCHEMES` (linear and cubic, plain and
  width-stretched) at each placement in :data:`PLACEMENTS` plus a greedy
  probe-and-bisect placement for the cubic scheme, and the worst deviation
  over the range is reported.  Deviations are quoted in the same currency
  WP-1112 used for window truncation: relative area, first moment (in FWHM
  units — cells and zero ride on positions), relative central second
  moment, and peak-relative pointwise error.  The reference and the
  anchors use a 128-image FCJ quadrature so the number measured is
  interpolation error alone.

States: each case is measured at the state its cold fit *starts* from and at
the state it converges to (the trigger's "converged" is the truth model that
generated its data) — a buffer must hold its tolerance along the whole
trajectory, and widths at convergence are not the widths at the start.

Part 2 (``--part proto``) implements the buffer of the WP's design note
(:class:`PeaksBuffer`) and measures, on the trigger-shaped and cpd-2 start
states: the forward evaluation **three ways** — the shipped scalar loop,
the WP-1112 batched kernel evaluating exact profiles (the fair baseline:
that dispatch win is bit-exact and must not be booked to the buffer), and
the buffer — plus the derivative-bases build shipped vs buffered, with
max area/moment/pointwise deviations and an attribution of the worst FCJ
rows against a 128-image reference (the shipped path deliberately skips
sub-threshold FCJ tails, and where the two disagree most the reference
sides with the buffer).

Part 3 (``--part fit``) runs each protocol end to end with
``phase_component`` and ``derivative_bases`` monkeypatched to the buffer,
against the exact fit: wall ranges, and the deviation of every reported
parameter and esd — the numbers the go/no-go quotes.

Wall clock: the full default run (all three parts) is ~10 minutes, most of
it fits; ``--start-only`` and ``--part``/``--cases`` narrow it while
iterating.
"""

from __future__ import annotations

import argparse
import platform
import sys
import time
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

import bench_refinement as bench  # noqa: E402

import rietx as rx  # noqa: E402
from rietx import _about  # noqa: E402
from rietx.model.forward import (  # noqa: E402
    WINDOW_MIN_DEG,
    CompiledModel,
    DerivativeBases,
    PhasePlanes,
    compile_model,
    window_fwhm_mult,
)
from rietx.model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm  # noqa: E402
from rietx.model.profiles.fcj import (  # noqa: E402
    fcj_extent_deg,
    fcj_node_count,
    fcj_offsets_weights,
)
from rietx.params.vector import ParameterTable  # noqa: E402

#: FCJ quadrature size for reference and anchor shapes: 128 images, ~2× the
#: shipped MAX_NODES, so quadrature error is far below the 1e-4 tolerance
#: this sweep resolves and the measured number is interpolation error alone.
N_REF_NODES = 128
ANCHOR_COUNTS = (2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64)
TOLS = (1e-3, 1e-4)


# -- states ------------------------------------------------------------------

@dataclass
class Study:
    """One (case, parameter state) the shape family is measured at."""

    key: str
    model: CompiledModel
    values: dict[str, float]


def _study(key: str, structure: rx.Structure, instrument: rx.Instrument,
           data: rx.PatternData, mode: str, limits) -> Study:
    model = compile_model(structure, instrument, data, mode=mode,
                          two_theta_limits=limits)
    table = ParameterTable(structure, instrument)
    return Study(key, model, table.decode(table.x0()))


def build_studies(case_keys: list[str], start_only: bool) -> list[Study]:
    by_key = {c.key: c for c in bench.CASES}
    out: list[Study] = []
    for key in case_keys:
        setup = by_key[key].build()
        out.append(_study(f"{key} @ start", setup.structure, setup.instrument,
                          setup.data, setup.mode, setup.limits))
        if start_only:
            continue
        if key == "trigger":
            # the state the cold fit converges to is, by construction, the
            # truth model the pattern was simulated from
            structure = rx.Structure(phases=bench._trigger_phases(0.0))
            instrument = bench._trigger_instrument(truth=True)
            out.append(_study("trigger @ truth", structure, instrument,
                              setup.data, setup.mode, setup.limits))
        else:
            ref = rx.Refinement(setup.structure.model_copy(deep=True),
                                setup.instrument.model_copy(deep=True),
                                history=False)
            ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                    two_theta_limits=setup.limits)
            out.append(_study(f"{key} @ converged", ref.fitted_structure,
                              ref.fitted_instrument, setup.data, setup.mode,
                              setup.limits))
    return out


# -- volume ------------------------------------------------------------------

def volume_row(study: Study) -> str:
    n_pts = len(study.model.tt)
    sum_win = sum_elem = n_pairs = n_fcj = 0
    for cp in study.model.phases:
        w = (cp.win[..., 1] - cp.win[..., 0]).astype(np.int64)
        images = np.where(cp.fcj_n > 0, 2 * np.maximum(cp.fcj_n // 2, 4), 1)
        sum_win += int(w.sum())
        sum_elem += int((w * images).sum())
        n_pairs += int(w.size)
        n_fcj += int((cp.fcj_n > 0).sum())
    return (f"  {study.key:22s} {n_pts:6d} {n_pairs:6d} {n_fcj:6d} "
            f"{sum_win / n_pts:8.1f} {sum_elem / n_pts:9.1f} "
            f"{sum_elem / max(sum_win, 1):7.2f}")


# -- the shape family ---------------------------------------------------------

class ShapeFamily:
    """Exact peak shape of one phase as a function of position 2θ.

    Wraps the package's own width laws and FCJ quadrature so nothing about
    the shape is restated here; ``shape(tt0, delta)`` is the unit-area,
    FCJ-convolved profile a reflection at 2θ = ``tt0`` would add to the
    pattern, evaluated at offsets ``delta`` from its position.
    """

    def __init__(self, m: CompiledModel, v: dict[str, float], ip: int):
        self.model = m
        self.sl = v["instrument.geometry.axial_sl"]
        self.hl = v["instrument.geometry.axial_hl"]
        self.fcj = self.sl > 0.0 and self.hl > 0.0 and m.geometry_kind == "bragg_brentano"
        self.uvw = (v["instrument.profile.u"], v["instrument.profile.v"],
                    v["instrument.profile.w"])
        self.gs = v[f"phases.{ip}.gauss_size"]
        self.gstr = v[f"phases.{ip}.gauss_strain"]
        self.xl = v["instrument.profile.x"] + v[f"phases.{ip}.lor_size"]
        self.yl = v["instrument.profile.y"] + v[f"phases.{ip}.lor_strain"]
        if m.phases[ip].strain_monomials is not None:
            raise NotImplementedError("Stephens strain is per-hkl; no harness "
                                      "case carries it")

    def widths(self, tt0):
        """Shape-specific (w₁, w₂) pair at position(s) 2θ (degrees)."""
        theta = 0.5 * np.asarray(tt0, dtype=np.float64)
        gg = gaussian_fwhm(theta, *self.uvw, self.gs, self.gstr)
        gl = lorentzian_fwhm(theta, self.xl, self.yl)
        return self.model._peak_widths(gg, gl)

    def fwhm(self, tt0):
        return self.model.peak_fwhm(*self.widths(tt0))

    def shape(self, tt0: float, delta: np.ndarray) -> np.ndarray:
        w1, w2 = self.widths(tt0)
        if not self.fcj:
            return self.model.profile_at(delta, float(w1), float(w2))
        phi, om = fcj_offsets_weights(tt0, self.sl, self.hl, N_REF_NODES)
        off = np.asarray(phi, dtype=np.float64) - tt0
        prof = self.model.profile_at(delta[None, :] - off[:, None],
                                     float(w1), float(w2))
        return np.asarray(om, dtype=np.float64) @ prof


# -- metrics -----------------------------------------------------------------

def shape_metrics(s_hat: np.ndarray, s: np.ndarray, delta: np.ndarray,
                  fwhm: float) -> tuple[float, float, float, float]:
    """(area, m1, m2, pointwise) deviations of a reconstruction vs exact.

    area and m2 are relative; m1 is in FWHM units (a pure position error);
    pointwise is relative to the exact peak maximum.
    """
    a = np.trapezoid(s, delta)
    a_h = np.trapezoid(s_hat, delta)
    m1 = np.trapezoid(delta * s, delta) / a
    m1_h = np.trapezoid(delta * s_hat, delta) / a_h
    m2 = np.trapezoid((delta - m1) ** 2 * s, delta) / a
    m2_h = np.trapezoid((delta - m1_h) ** 2 * s_hat, delta) / a_h
    return (abs(a_h - a) / a, abs(m1_h - m1) / fwhm,
            abs(m2_h - m2) / m2, float(np.max(np.abs(s_hat - s)) / np.max(s)))


def _bracket(anchors: np.ndarray, tt0: float) -> tuple[int, int, float]:
    j = int(np.searchsorted(anchors, tt0))
    j = min(max(j, 1), len(anchors) - 1)
    i0, i1 = j - 1, j
    w = (tt0 - anchors[i0]) / (anchors[i1] - anchors[i0])
    return i0, i1, float(np.clip(w, 0.0, 1.0))


# -- the sweep ----------------------------------------------------------------

#: error is probed at these fractions inside every anchor segment — for a
#: smooth one-parameter family the linear-blend error peaks near the middle
#: of a segment, and probing fractions rather than a fixed dense grid keeps
#: an anchor from ever coinciding with its own probe (which flattered an
#: early version of this sweep at K close to the dense count)
SEGMENT_FRACTIONS = (0.25, 0.5, 0.75)

#: reconstruction schemes.  ``plain``: linear blend of the two bracketing
#: anchor shapes.  ``stretch``: the same blend after rescaling each anchor to
#: the true combined FWHM at the query (Γ, η are two cheap scalars per
#: reflection, so the exact width is always available).  ``cubic``: a C²
#: cubic spline through all anchor shapes in θ — the construction a
#: production buffer would ship, because the analytic-Jacobian invariant
#: needs the interpolant smooth in θ (a linear blend has C⁰ kinks at anchors
#: that a moving cell would drag through the residual).  ``cubicstretch``:
#: 4-point Lagrange cubic of the width-normalised shapes (cubic order *and*
#: exact width tracking; Lagrange rather than a spline so each anchor can be
#: evaluated exactly at the query's own rescaled offsets).
SCHEMES = ("plain", "stretch", "cubic", "cubicstretch")
PLACEMENTS = ("uniform", "motion")
#: which placement-motion metric each scheme interpolates under
_MOTION_OF = {"plain": "plain", "cubic": "plain",
              "stretch": "stretch", "cubicstretch": "stretch"}


@dataclass
class SweepResult:
    key: str
    n_anchors: int
    scheme: str
    placement: str     # "uniform" | "motion"
    worst: tuple[float, float, float, float]   # area, m1, m2, pointwise
    worst_at: float                            # 2θ of the binding deviation


def _dedupe(families: list[ShapeFamily]) -> list[tuple[ShapeFamily, int]]:
    """(family, multiplicity) with identical width/FCJ parameter sets merged —
    the harness cases start all phases from one generic width set, so this
    cuts the exact-shape evaluations by the phase count without changing any
    measured number."""
    out: list[tuple[ShapeFamily, int]] = []
    seen: dict[tuple, int] = {}
    for fam in families:
        key = (fam.uvw, fam.gs, fam.gstr, fam.xl, fam.yl, fam.sl, fam.hl,
               fam.fcj)
        if key in seen:
            out[seen[key]] = (out[seen[key]][0], out[seen[key]][1] + 1)
        else:
            seen[key] = len(out)
            out.append((fam, 1))
    return out


def _placements(dense: np.ndarray, delta: np.ndarray,
                refs: list[np.ndarray], fwhms: list[np.ndarray]
                ) -> dict[str, np.ndarray]:
    """Cumulative shape-motion coordinates for anchor placement.

    ``plain`` accumulates the L1 distance between successive dense shapes;
    ``stretch`` accumulates it between width-normalised shapes (each resampled
    to its own FWHM), which is the variation that scheme still has to
    interpolate.  Both are placement heuristics only — the sweep's error
    numbers are always measured against exact shapes.
    """
    out = {}
    for name in ("plain", "stretch"):
        motion = np.zeros(len(dense) - 1)
        for ref, fwhm in zip(refs, fwhms):
            fam_shapes = ref
            if name == "stretch":
                g0 = float(np.median(fwhm))
                u = delta / g0
                fam_shapes = np.stack([
                    np.interp(u * fwhm[i], delta, ref[i]) * fwhm[i]
                    for i in range(len(dense))])
            motion += np.trapezoid(np.abs(np.diff(fam_shapes, axis=0)),
                                   delta, axis=1)
        out[name] = np.concatenate([[0.0], np.cumsum(motion)])
    return out


def _anchor_grid(dense: np.ndarray, cum: np.ndarray, k: int,
                 placement: str) -> np.ndarray:
    if placement == "uniform" or cum[-1] <= 0.0:
        return np.linspace(dense[0], dense[-1], k)
    q = np.linspace(0.0, cum[-1], k)
    return np.interp(q, cum, dense)


def sweep_study(study: Study, n_dense: int, n_delta: int
                ) -> tuple[list[SweepResult], list[str]]:
    tt = study.model.tt
    families = [ShapeFamily(study.model, study.values, ip)
                for ip in range(len(study.model.phases))]
    dense = np.linspace(float(tt[0]), float(tt[-1]), n_dense)

    # common offset grid: wide enough for the widest window in this study
    half = 0.0
    budget_lines = []
    for ip, fam in enumerate(families):
        w1, w2 = fam.widths(dense)
        gamma = fam.fwhm(dense)
        eta_like = np.asarray(w2, dtype=np.float64)
        h = window_fwhm_mult(eta_like) * gamma + WINDOW_MIN_DEG
        ext = np.zeros_like(dense)
        if fam.fcj:
            ext = fcj_extent_deg(dense, fam.sl, fam.hl)
            h = h + ext
        half = max(half, float(np.max(h)))
        budget_lines.append(
            f"    phase {ip}: Γ {gamma.min():.4f}-{gamma.max():.4f}° "
            f"(×{gamma.max() / gamma.min():.2f})  w₂ {eta_like.min():.3f}-"
            f"{eta_like.max():.3f}"
            + (f"  FCJ extent {ext.min():.3f}-{ext.max():.3f}°"
               if fam.fcj else "  no FCJ"))
    delta = np.linspace(-half, half, n_delta)

    unique = _dedupe(families)
    if len(unique) < len(families):
        budget_lines.append(f"    ({len(families)} phases share "
                            f"{len(unique)} distinct width set(s))")

    # a modest dense reference per distinct family, for the placement metric
    refs = [np.stack([fam.shape(t, delta) for t in dense])
            for fam, _ in unique]
    fwhms = [fam.fwhm(dense) for fam, _ in unique]
    cums = _placements(dense, delta, refs, fwhms)

    results: list[SweepResult] = []
    results.extend(_greedy_sweep(study.key, unique, dense, delta))
    for n_anchor in ANCHOR_COUNTS:
        for scheme in SCHEMES:
            if scheme in ("cubic", "cubicstretch") and n_anchor < 4:
                continue
            for placement in PLACEMENTS:
                anchors = np.unique(_anchor_grid(
                    dense, cums[_MOTION_OF[scheme]], n_anchor, placement))
                worst = np.zeros(4)
                worst_at = float("nan")
                for fam, _ in unique:
                    a_shapes = np.stack([fam.shape(float(t), delta)
                                         for t in anchors])
                    a_fwhm = fam.fwhm(anchors)
                    spline = None
                    if scheme == "cubic":
                        from scipy.interpolate import CubicSpline
                        spline = CubicSpline(anchors, a_shapes, axis=0)
                    for seg in range(len(anchors) - 1):
                        t_lo, t_hi = anchors[seg], anchors[seg + 1]
                        for frac in SEGMENT_FRACTIONS:
                            t0 = float(t_lo + frac * (t_hi - t_lo))
                            ref = fam.shape(t0, delta)
                            fwhm0 = float(fam.fwhm(t0))
                            s_hat = _reconstruct(scheme, fam, anchors,
                                                 a_shapes, a_fwhm, spline,
                                                 seg, frac, t0, fwhm0, delta)
                            m = shape_metrics(s_hat, ref, delta, fwhm0)
                            if max(m[:3]) > max(worst[:3]):
                                worst_at = t0
                            worst = np.maximum(worst, m)
                results.append(SweepResult(study.key, n_anchor, scheme,
                                           placement, tuple(worst), worst_at))
    return results, budget_lines


def _greedy_sweep(key: str, unique, dense: np.ndarray, delta: np.ndarray
                  ) -> list[SweepResult]:
    """Cubic scheme under greedy error-driven placement.

    Start from 4 uniform anchors and repeatedly bisect the segment with the
    worst probed error.  This is the placement a production buffer would run
    at stage compile (place, probe, densify until the tolerance holds), and
    it is the only one of the placements here that survives a *kink* in the
    shape family — the converged cpd states have one, where the fitted
    Caglioti quadratic goes negative and ``_MIN_GAMMA_G2`` clamps Γ_G across
    2θ ≈ 92-134°: a smooth spline cannot refine through it, but bisection
    concentrates anchors around it and buys error linearly per split.
    """
    from scipy.interpolate import CubicSpline

    ref_cache: list[dict[float, tuple[np.ndarray, float]]] = [
        {} for _ in unique]
    shape_cache: list[dict[float, np.ndarray]] = [{} for _ in unique]

    def probe(i: int, t0: float) -> tuple[np.ndarray, float]:
        if t0 not in ref_cache[i]:
            fam = unique[i][0]
            ref_cache[i][t0] = (fam.shape(t0, delta), float(fam.fwhm(t0)))
        return ref_cache[i][t0]

    anchors = list(np.linspace(dense[0], dense[-1], 4))
    out: list[SweepResult] = []
    while len(anchors) <= ANCHOR_COUNTS[-1]:
        arr = np.array(sorted(anchors))
        seg_err = np.zeros(len(arr) - 1)
        seg_at = np.zeros(len(arr) - 1)
        worst = np.zeros(4)
        worst_at = float("nan")
        for i, (fam, _) in enumerate(unique):
            for t in arr:
                if float(t) not in shape_cache[i]:
                    shape_cache[i][float(t)] = fam.shape(float(t), delta)
            spline = CubicSpline(
                arr, np.stack([shape_cache[i][float(t)] for t in arr]), axis=0)
            for seg in range(len(arr) - 1):
                for frac in SEGMENT_FRACTIONS:
                    t0 = float(arr[seg] + frac * (arr[seg + 1] - arr[seg]))
                    ref, fwhm0 = probe(i, t0)
                    m = shape_metrics(spline(t0), ref, delta, fwhm0)
                    err = max(m[:3])
                    if err > seg_err[seg]:
                        seg_err[seg], seg_at[seg] = err, t0
                    if err > max(worst[:3]):
                        worst_at = t0
                    worst = np.maximum(worst, m)
        if len(arr) in ANCHOR_COUNTS:
            out.append(SweepResult(key, len(arr), "cubic", "greedy",
                                   tuple(worst), worst_at))
        j = int(np.argmax(seg_err))
        anchors.append(float(0.5 * (arr[j] + arr[j + 1])))
    return out


def _reconstruct(scheme: str, fam: ShapeFamily, anchors: np.ndarray,
                 a_shapes: np.ndarray, a_fwhm: np.ndarray, spline,
                 seg: int, frac: float, t0: float, fwhm0: float,
                 delta: np.ndarray) -> np.ndarray:
    if scheme == "cubic":
        return spline(t0)
    if scheme == "plain":
        return (1.0 - frac) * a_shapes[seg] + frac * a_shapes[seg + 1]
    if scheme == "stretch":
        support = ((seg, 1.0 - frac), (seg + 1, frac))
    else:  # cubicstretch: 4-point Lagrange window around the segment
        lo = int(np.clip(seg - 1, 0, len(anchors) - 4))
        idx = range(lo, lo + 4)
        ts = anchors[list(idx)]
        wl = [float(np.prod([(t0 - ts[m]) / (ts[j] - ts[m])
                             for m in range(4) if m != j]))
              for j in range(4)]
        support = tuple(zip(idx, wl))
    s_hat = np.zeros_like(delta)
    for j, wj in support:
        if wj == 0.0:
            continue
        r = float(a_fwhm[j]) / fwhm0
        s_hat = s_hat + wj * r * fam.shape(float(anchors[j]), delta * r)
    return s_hat


def print_sweep(study: Study, results: list[SweepResult],
                budget_lines: list[str]) -> None:
    print(f"\n  {study.key}")
    for line in budget_lines:
        print(line)
    print(f"    {'K':>3s}  {'scheme':7s} {'placed':7s} {'area':>9s} "
          f"{'m1/FWHM':>9s} {'m2':>9s} {'pointwise':>9s}  worst @")
    for r in results:
        a, m1, m2, pw = r.worst
        print(f"    {r.n_anchors:3d}  {r.scheme:7s} {r.placement:7s} "
              f"{a:9.2e} {m1:9.2e} {m2:9.2e} {pw:9.2e}  {r.worst_at:6.2f}°")
    for tol in TOLS:
        for scheme in SCHEMES:
            placements = PLACEMENTS + (("greedy",) if scheme == "cubic" else ())
            for placement in placements:
                ks = [r.n_anchors for r in results
                      if r.scheme == scheme and r.placement == placement
                      and max(r.worst[:3]) <= tol]
                note = (f"K = {min(ks)}" if ks
                        else f"not reached by K = {ANCHOR_COUNTS[-1]}")
                print(f"    -> {scheme}/{placement} meets {tol:.0e} "
                      f"on area+moments at {note}")


# -- the prototype buffer -----------------------------------------------------

#: the buffer's accuracy target on area + moments, in the sweep's currency
BUFFER_TOL = 1e-4
BUFFER_MAX_ANCHORS = 48
#: FD step for the anchor-level axial partials (matches derivative_bases)
_H_AX = 1e-7


def _bspline_weights(t: np.ndarray) -> tuple[np.ndarray, ...]:
    """4-tap cubic B-spline weights for taps at offsets (−1, 0, 1, 2).

    Applied to ``spline_filter1d``-prefiltered samples this evaluates the
    exact C² interpolating cubic spline (Unser 1999, IEEE Signal Process.
    Mag. 16, 22) — O(h⁴), where the first cut of this prototype used
    Catmull-Rom taps on raw samples, whose O(h³) error put ~1e-3 pointwise
    deviations into every symmetric case at the stored step this buffer
    uses.  The prefilter runs over the (K, planes, n_stored) anchor array —
    a few thousand values — and commutes with the θ-spline, both linear.
    """
    t2, t3 = t * t, t * t * t
    return ((1.0 - 3.0 * t + 3.0 * t2 - t3) / 6.0,
            (4.0 - 6.0 * t2 + 3.0 * t3) / 6.0,
            (1.0 + 3.0 * t + 3.0 * t2 - 3.0 * t3) / 6.0,
            t3 / 6.0)


class PeaksBuffer:
    """The spike's buffer for one compiled phase (design note in the WP file).

    Frozen at build (= stage compile in production): anchor positions
    (greedy probe-and-bisect against ``BUFFER_TOL``), per-anchor FCJ node
    counts (the shipped ``fcj_node_count`` rule), and the stored offset
    grid.  Everything else — the anchor *planes* — is recomputed from the
    current parameter values on every evaluation, so the buffered residual
    follows θ smoothly and only indices are discrete.
    """

    def __init__(self, model: CompiledModel, ip: int, values: dict[str, float]):
        cp = model.phases[ip]
        lay = cp.batch
        fam = ShapeFamily(model, values, ip)
        self.fcj = fam.fcj
        peaks = model.phase_peaks(ip, values)
        pos = lay.gather(peaks, 0)
        finite = np.isfinite(pos)
        pos_f = pos[finite]
        self.lo = float(pos_f.min()) - 0.15
        self.hi = float(pos_f.max()) + 0.15
        # stored offset grid: fine enough that 4-tap resampling sits far
        # below BUFFER_TOL, wide enough for the widest frozen window + drift.
        # Γ/16 because the O(h⁴) constant lives in σ = Γ/2.355 units and the
        # peak's flank carries f⁗ ~ 10²/σ⁴: at Γ/4 (0.59 σ) the measured
        # flank error was ~1e-3 of the peak — the resample, not the θ-spline,
        # was this prototype's first accuracy ceiling, twice
        probe_tt = np.linspace(self.lo, self.hi, 128)
        gmin = float(np.min(fam.fwhm(probe_tt)))
        step = float(np.median(np.diff(model.tt)))
        self.h = min(step, gmin / 16.0)
        x_last = lay.x[np.arange(len(lay.i0)), lay.width - 1]
        half = float(max(np.max((pos - lay.x[:, 0])[finite]),
                         np.max((x_last - pos)[finite]))) + 0.1
        n_half = int(np.ceil(half / self.h))
        self.half = n_half * self.h
        self.grid = np.arange(-n_half, n_half + 1) * self.h
        self.anchors = self._place(fam)
        if self.fcj:
            # never let an anchor fall to the sub-threshold *skip* (node
            # count 0): a row keeps its small asymmetry while a skipped
            # anchor loses it, and the spline smears that family
            # discontinuity into every nearby row — measured 1.0e-3 FWHM of
            # m1 against 1.2e-5 for a consistently-convolved anchor family
            from rietx.model.profiles.fcj import MIN_NODES

            g_anchor = np.asarray(fam.fwhm(self.anchors), dtype=np.float64)
            self.n_nodes = [max(fcj_node_count(float(t), float(g), fam.sl,
                                               fam.hl), MIN_NODES)
                            for t, g in zip(self.anchors, g_anchor)]
        else:
            self.n_nodes = [0] * len(self.anchors)

    def covers(self, model: CompiledModel, ip: int,
               values: dict[str, float]) -> bool:
        """Whether this buffer's frozen domain serves phase ``ip`` too."""
        lay = model.phases[ip].batch
        peaks = model.phase_peaks(ip, values)
        pos = lay.gather(peaks, 0)
        finite = np.isfinite(pos)
        if not finite.any():
            return True
        x_last = lay.x[np.arange(len(lay.i0)), lay.width - 1]
        ext = float(max(np.max((pos - lay.x[:, 0])[finite]),
                        np.max((x_last - pos)[finite])))
        return (float(pos[finite].min()) >= self.lo
                and float(pos[finite].max()) <= self.hi
                and ext <= self.half)

    def _place(self, fam: ShapeFamily) -> np.ndarray:
        """Greedy probe-and-bisect to ``BUFFER_TOL`` on area + moments."""
        from scipy.interpolate import CubicSpline

        anchors = list(np.linspace(self.lo, self.hi, 4))
        cache: dict[float, np.ndarray] = {}

        def exact(t: float) -> np.ndarray:
            if t not in cache:
                cache[t] = fam.shape(t, self.grid)
            return cache[t]

        while True:
            arr = np.array(sorted(anchors))
            spline = CubicSpline(arr, np.stack([exact(float(t)) for t in arr]),
                                 axis=0)
            seg_err = np.zeros(len(arr) - 1)
            for seg in range(len(arr) - 1):
                for frac in SEGMENT_FRACTIONS:
                    t0 = float(arr[seg] + frac * (arr[seg + 1] - arr[seg]))
                    m = shape_metrics(spline(t0), exact(t0), self.grid,
                                      float(fam.fwhm(t0)))
                    seg_err[seg] = max(seg_err[seg], max(m[:3]))
            if seg_err.max() <= BUFFER_TOL or len(arr) >= BUFFER_MAX_ANCHORS:
                return arr
            j = int(np.argmax(seg_err))
            anchors.append(float(0.5 * (arr[j] + arr[j + 1])))

    def _anchor_planes(self, model: CompiledModel, fam: ShapeFamily,
                       axial: bool, n_extra: int) -> np.ndarray:
        """(K, 4 + n_extra, n_stored): S, S_Γ, S_η, S_x (+ S_sl, S_hl FDs)."""
        planes = np.zeros((len(self.anchors), 4 + n_extra, len(self.grid)))
        for a, ta in enumerate(self.anchors):
            w1a, w2a = (float(w) for w in fam.widths(float(ta)))
            n = self.n_nodes[a]
            if n > 0:
                phi, om = fcj_offsets_weights(float(ta), fam.sl, fam.hl, n)
                offs = self.grid[None, :] - (np.asarray(phi) - ta)[:, None]
                pv, dx, dg, de = model._profile_derivs(offs, w1a, w2a)
                om = np.asarray(om, dtype=np.float64)
                planes[a, 0] = om @ pv
                planes[a, 1] = om @ dg
                planes[a, 2] = om @ de
                planes[a, 3] = om @ dx
                if axial:
                    for j, (dsl, dhl) in enumerate(((_H_AX, 0.0), (0.0, _H_AX))):
                        phi_p, om_p = fcj_offsets_weights(
                            float(ta), fam.sl + dsl, fam.hl + dhl, n)
                        offs_p = (self.grid[None, :]
                                  - (np.asarray(phi_p) - ta)[:, None])
                        pv_p = model._profile_basis(offs_p, w1a, w2a)
                        planes[a, 4 + j] = (np.asarray(om_p) @ pv_p
                                            - planes[a, 0]) / _H_AX
            else:
                pv, dx, dg, de = model._profile_derivs(self.grid, w1a, w2a)
                planes[a, 0], planes[a, 1] = pv, dg
                planes[a, 2], planes[a, 3] = de, dx
        return planes

    def _state(self, model: CompiledModel, fam: ShapeFamily, axial: bool,
               n_extra: int):
        """(θ-spline of prefiltered planes, S-only spline) for the current
        scalars — cached, so phases sharing a family (and the several
        buffered calls inside one solver iteration) build the anchor planes
        once.  The cache key is every scalar the planes depend on."""
        from scipy.interpolate import CubicSpline
        from scipy.ndimage import spline_filter1d

        key = (fam.uvw, fam.gs, fam.gstr, fam.xl, fam.yl, fam.sl, fam.hl,
               axial)
        if getattr(self, "_state_key", None) != key:
            planes = self._anchor_planes(model, fam, axial, n_extra)
            planes = spline_filter1d(planes, order=3, axis=2, mode="mirror")
            self._spline = CubicSpline(self.anchors, planes, axis=0)
            self._spline_s = CubicSpline(self.anchors, planes[:, :1], axis=0)
            self._state_key = key
        return self._spline, self._spline_s

    def planes(self, model: CompiledModel, ip: int, values: dict[str, float],
               peaks, profile_derivs: bool = True, axial: bool = False
               ) -> dict[str, np.ndarray | None]:
        """Buffered (n_rows, w_max) planes in ``derivative_bases``' layout."""
        lay = model.phases[ip].batch
        fam = ShapeFamily(model, values, ip)
        axial = axial and self.fcj and fam.sl > 0.0 and fam.hl > 0.0
        n_extra = 2 if axial else 0
        spline, spline_s = self._state(model, fam, axial, n_extra)

        pos = lay.gather(peaks, 0)
        w1 = lay.gather(peaks, 1)
        w2 = lay.gather(peaks, 2)
        finite = np.isfinite(pos)
        pos_c = np.clip(np.where(finite, pos, 0.5 * (self.lo + self.hi)),
                        self.lo, self.hi)
        stack = spline(pos_c)                      # (R, 4 + n_extra, n_stored)
        if profile_derivs:
            s_theta = spline_s(pos_c, 1)           # ∂S/∂θ of the S plane only
            stack = np.concatenate([stack, s_theta], axis=1)

        # 4-tap B-spline resample onto each row's own window offsets
        u = (lay.x - pos_c[:, None] + self.half) / self.h
        i = np.clip(np.floor(u).astype(np.int64), 1, len(self.grid) - 3)
        t = np.clip(u - i, 0.0, 1.0)
        w_taps = _bspline_weights(t)               # each (R, w_max)
        out = np.zeros((stack.shape[0], stack.shape[1], lay.x.shape[1]))
        for tap, wt in zip((-1, 0, 1, 2), w_taps):
            gathered = np.take_along_axis(stack, (i + tap)[:, None, :], axis=2)
            out += wt[:, None, :] * gathered

        g_law, e_law = (np.asarray(a, dtype=np.float64)
                        for a in fam.widths(pos_c))
        s_r, sg_r, se_r, sx_r = out[:, 0], out[:, 1], out[:, 2], out[:, 3]
        omega = (s_r + (w1 - g_law)[:, None] * sg_r
                 + (w2 - e_law)[:, None] * se_r)
        d_pos = d_gamma = d_eta = d_sl = d_hl = None
        if profile_derivs:
            hh = 1e-4
            gp, ep = fam.widths(pos_c + hh)
            gm, em = fam.widths(pos_c - hh)
            dg_law = (np.asarray(gp) - np.asarray(gm)) / (2 * hh)
            de_law = (np.asarray(ep) - np.asarray(em)) / (2 * hh)
            d_pos = (out[:, -1] - sx_r - dg_law[:, None] * sg_r
                     - de_law[:, None] * se_r)
            d_gamma, d_eta = sg_r, se_r
            if axial:
                d_sl, d_hl = out[:, 4], out[:, 5]
        result = {"omega": omega, "d_pos": d_pos, "d_gamma": d_gamma,
                  "d_eta": d_eta, "d_sl": d_sl, "d_hl": d_hl}
        for plane in result.values():
            if plane is None:
                continue
            np.multiply(plane, lay.mask, out=plane)
            if not finite.all():
                plane[~finite] = 0.0
        result.update(pos=pos, w1=w1, w2=w2, finite=finite,
                      inten=lay.gather(peaks, 3))
        return result


# -- buffered forward / bases entry points ------------------------------------

def _scatter_y(model: CompiledModel, ip: int, omega: np.ndarray,
               inten: np.ndarray) -> np.ndarray:
    lay = model.phases[ip].batch
    return np.bincount(lay.idx.ravel(),
                       weights=(inten[:, None] * omega).ravel(),
                       minlength=len(model.tt))


class BufferSet:
    """Lazily built buffers, deduplicated by width family (the design-note
    layout: one buffer per distinct width set per stage compile).  A family
    hit whose domain does not cover the new phase's positions or windows is
    rebuilt wider — at most once per family, before the stage's first solve
    step, so the frozen-anchor claim still holds for the stage."""

    def __init__(self):
        self._by_phase: dict[int, PeaksBuffer] = {}
        self._by_family: dict[tuple, PeaksBuffer] = {}
        #: strong refs to every keyed object — the caches key by ``id()``,
        #: and a dead CompiledModel's id is recycled by the allocator, which
        #: let a stale buffer serve a *different stage's* frozen state and
        #: made the buffered cpd-2 fit non-deterministic run to run
        self._refs: list = []
        self.builds = 0
        self.build_wall = 0.0

    def get(self, model: CompiledModel, ip: int,
            values: dict[str, float]) -> PeaksBuffer:
        key = id(model.phases[ip])
        if key in self._by_phase:
            return self._by_phase[key]
        self._refs.append((model, model.phases[ip]))
        fam = ShapeFamily(model, values, ip)
        fkey = (id(model), fam.uvw, fam.gs, fam.gstr, fam.xl, fam.yl,
                fam.sl, fam.hl)
        buf = self._by_family.get(fkey)
        if buf is None or not buf.covers(model, ip, values):
            t0 = time.perf_counter()
            buf = PeaksBuffer(model, ip, values)
            self.build_wall += time.perf_counter() - t0
            self.builds += 1
            self._by_family[fkey] = buf
        self._by_phase[key] = buf
        return buf


def buffered_evaluate(model: CompiledModel, values: dict[str, float],
                      buffers: BufferSet) -> np.ndarray:
    y = np.asarray(model.background(values), dtype=np.float64)
    for ip in range(len(model.phases)):
        peaks = model.phase_peaks(ip, values)
        buf = buffers.get(model, ip, values)
        d = buf.planes(model, ip, values, peaks, profile_derivs=False)
        y = y + _scatter_y(model, ip, d["omega"], d["inten"])
    return y


def batched_exact_evaluate(model: CompiledModel,
                           values: dict[str, float]) -> np.ndarray:
    """The forward through the WP-1112 batched kernel — the fair baseline:
    the shipped residual still runs the per-reflection scalar loop, and that
    dispatch win must not be booked to the buffer."""
    bases = model.derivative_bases(values, profile_derivs=False)
    y = np.asarray(model.background(values), dtype=np.float64)
    for ip, ph in enumerate(bases.planes):
        y = y + _scatter_y(model, ip, ph.omega, ph.inten)
    return y


def buffered_derivative_bases(model: CompiledModel, values: dict[str, float],
                              buffers: BufferSet,
                              intensities=None, axial_derivs: bool = True,
                              profile_derivs: bool = True) -> DerivativeBases:
    if not profile_derivs:
        axial_derivs = False
    sl = values["instrument.geometry.axial_sl"]
    hl = values["instrument.geometry.axial_hl"]
    planes_all, peaks_all = [], []
    axial_ok = True
    for ip, cp in enumerate(model.phases):
        peaks = model.phase_peaks(
            ip, values, None if intensities is None else intensities[ip])
        peaks_all.append(peaks)
        lay = cp.batch
        buf = buffers.get(model, ip, values)
        pos_r = lay.gather(peaks, 0)
        has_fcj = bool(np.any((lay.fcj > 0) & np.isfinite(pos_r)))
        if has_fcj and (sl <= 0.0 or hl <= 0.0):
            axial_ok = False
        d = buf.planes(model, ip, values, peaks,
                       profile_derivs=profile_derivs,
                       axial=axial_derivs and has_fcj and sl > 0.0 and hl > 0.0)
        planes_all.append(PhasePlanes(
            layout=lay, finite=d["finite"], pos=d["pos"], w1=d["w1"],
            w2=d["w2"], inten=d["inten"], omega=d["omega"], d_pos=d["d_pos"],
            d_gamma=d["d_gamma"], d_eta=d["d_eta"], d_sl=d["d_sl"],
            d_hl=d["d_hl"]))
    return DerivativeBases(planes=planes_all, peaks=peaks_all,
                           axial_ok=axial_ok)


# -- part: proto (evaluation-level wall + deviation) --------------------------

def _time(fn, repeats: int = 5) -> tuple[float, float]:
    walls = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        walls.append(time.perf_counter() - t0)
    return min(walls), max(walls)


def proto_study(study: Study) -> None:
    model, values = study.model, study.values
    print(f"\n  {study.key}")

    buffers = BufferSet()
    y_exact = np.asarray(model.evaluate(values), dtype=np.float64)
    y_buf = buffered_evaluate(model, values, buffers)
    print(f"    buffers: {buffers.builds} built "
          f"({', '.join(str(len(b.anchors)) for b in buffers._by_phase.values())} anchors), "
          f"build wall {buffers.build_wall * 1e3:.0f} ms")

    scale = float(np.max(np.abs(y_exact)))
    print(f"    forward max |Δy|/max y = "
          f"{float(np.max(np.abs(y_buf - y_exact))) / scale:.2e}")

    # per-row shape deviations vs the shipped batched planes, in the sweep's
    # currency (the shipped rows carry their own frozen quadrature, so part
    # of this deviation is the shipped path's quadrature coarseness)
    bases_exact = model.derivative_bases(values)
    worst = np.zeros(3)
    for ip, ph in enumerate(bases_exact.planes):
        lay = ph.layout
        d = buffers.get(model, ip, values).planes(
            model, ip, values, bases_exact.peaks[ip])
        mine, theirs = d["omega"], ph.omega
        a_m = (mine * lay.mask).sum(axis=1)
        a_t = (theirs * lay.mask).sum(axis=1)
        off = (lay.x - np.where(ph.finite, ph.pos, 0.0)[:, None]) * lay.mask
        ok = (a_t > 1e-12) & np.isfinite(a_t) & ph.finite
        m1_m = (off * mine).sum(axis=1)[ok] / a_m[ok]
        m1_t = (off * theirs).sum(axis=1)[ok] / a_t[ok]
        worst[0] = max(worst[0], float(np.max(np.abs(a_m[ok] / a_t[ok] - 1.0))))
        worst[1] = max(worst[1], float(np.max(
            np.abs(m1_m - m1_t) / np.asarray(ph.w1)[ok])))
        worst[2] = max(worst[2], float(np.max(
            np.abs(mine - theirs)) / np.max(np.abs(theirs))))
    print(f"    omega rows vs shipped: area {worst[0]:.2e}  "
          f"m1/FWHM {worst[1]:.2e}  pointwise {worst[2]:.2e}")
    _attribute_fcj_rows(model, values, buffers, bases_exact)

    lo, hi = _time(lambda: model.evaluate(values))
    print(f"    forward  scalar loop     {lo * 1e3:7.1f}-{hi * 1e3:7.1f} ms")
    lo, hi = _time(lambda: batched_exact_evaluate(model, values))
    print(f"    forward  batched exact   {lo * 1e3:7.1f}-{hi * 1e3:7.1f} ms")
    lo, hi = _time(lambda: buffered_evaluate(model, values, buffers))
    print(f"    forward  buffered        {lo * 1e3:7.1f}-{hi * 1e3:7.1f} ms")
    lo, hi = _time(lambda: model.derivative_bases(values))
    print(f"    bases    shipped         {lo * 1e3:7.1f}-{hi * 1e3:7.1f} ms")
    lo, hi = _time(lambda: buffered_derivative_bases(model, values, buffers))
    print(f"    bases    buffered        {lo * 1e3:7.1f}-{hi * 1e3:7.1f} ms")


def _attribute_fcj_rows(model: CompiledModel, values: dict[str, float],
                        buffers: BufferSet, bases_exact) -> None:
    """Attribute the worst FCJ-row deviations: buffer error vs the shipped
    rows' own frozen quadrature, judged against a 128-image reference.

    The rows-vs-shipped number above treats the shipped path as truth, but a
    shipped FCJ row is itself a quadrature at its frozen node count; where
    the two disagree the go/no-go needs to know which one the reference
    sides with.
    """
    worst_rows = []
    for ip, ph in enumerate(bases_exact.planes):
        lay = ph.layout
        if not np.any(lay.fcj > 0):
            continue
        d = buffers.get(model, ip, values).planes(model, ip, values,
                                                  bases_exact.peaks[ip])
        off = (lay.x - np.where(ph.finite, ph.pos, 0.0)[:, None]) * lay.mask
        a_m = (d["omega"] * lay.mask).sum(axis=1)
        a_t = (ph.omega * lay.mask).sum(axis=1)
        # every row of an FCJ family — the shipped path *skips* sub-threshold
        # rows (fcj_n = 0, rendered symmetric), and where the two disagree
        # most is exactly there, so restricting to fcj_n > 0 would assign the
        # shipped path's own approximation to the buffer
        ok = (a_t > 1e-12) & ph.finite
        m1_m = np.where(ok, (off * d["omega"]).sum(axis=1)
                        / np.where(ok, a_m, 1.0), 0.0)
        m1_t = np.where(ok, (off * ph.omega).sum(axis=1)
                        / np.where(ok, a_t, 1.0), 0.0)
        dev = np.where(ok, np.abs(m1_m - m1_t) / np.asarray(ph.w1), 0.0)
        for r in np.argsort(dev)[-8:]:
            worst_rows.append((float(dev[r]), ip, int(r)))
    if not worst_rows:
        return
    worst_rows.sort(reverse=True)
    sl = values["instrument.geometry.axial_sl"]
    hl = values["instrument.geometry.axial_hl"]
    buf_err = ship_err = 0.0
    for _, ip, r in worst_rows[:12]:
        ph = bases_exact.planes[ip]
        lay = ph.layout
        d = buffers.get(model, ip, values).planes(model, ip, values,
                                                  bases_exact.peaks[ip])
        n = int(lay.width[r])
        x = lay.x[r, :n]
        pos, w1, w2 = (float(a[r]) for a in (ph.pos, ph.w1, ph.w2))
        phi, om = fcj_offsets_weights(pos, sl, hl, N_REF_NODES)
        ref = np.asarray(om) @ model.profile_at(
            x[None, :] - np.asarray(phi)[:, None], w1, w2)

        def m1(y, x=x, pos=pos):
            return float((y * (x - pos)).sum() / y.sum())

        buf_err = max(buf_err, abs(m1(d["omega"][r, :n]) - m1(ref)) / w1)
        ship_err = max(ship_err, abs(m1(ph.omega[r, :n]) - m1(ref)) / w1)
    print(f"    worst FCJ rows vs a 128-image reference: buffered m1 dev "
          f"{buf_err:.2e}, shipped m1 dev {ship_err:.2e} (FWHM units)")


# -- part: fit (full protocol through the buffer) -----------------------------

class _buffer_substitution:
    """Monkeypatch ``phase_component`` and ``derivative_bases`` for one fit.

    Rietveld-mode models only; anything else falls through to the shipped
    path.  Buffers are keyed by compiled phase, so each stage compile gets
    its own frozen anchor set — the production shape.
    """

    def __init__(self):
        self.buffers = BufferSet()

    def __enter__(self):
        self._pc = CompiledModel.phase_component
        self._db = CompiledModel.derivative_bases
        buffers = self.buffers
        orig_pc, orig_db = self._pc, self._db

        def phase_component(model, ip, values, hkl_intensity=None):
            if model.mode != "rietveld" or model.shape == "voigt":
                return orig_pc(model, ip, values, hkl_intensity)
            peaks = model.phase_peaks(ip, values, hkl_intensity)
            buf = buffers.get(model, ip, values)
            d = buf.planes(model, ip, values, peaks, profile_derivs=False)
            return _scatter_y(model, ip, d["omega"], d["inten"])

        def derivative_bases(model, values, intensities=None,
                             axial_derivs=True, profile_derivs=True):
            if model.mode != "rietveld" or model.shape == "voigt":
                return orig_db(model, values, intensities=intensities,
                               axial_derivs=axial_derivs,
                               profile_derivs=profile_derivs)
            return buffered_derivative_bases(
                model, values, buffers, intensities=intensities,
                axial_derivs=axial_derivs, profile_derivs=profile_derivs)

        CompiledModel.phase_component = phase_component
        CompiledModel.derivative_bases = derivative_bases
        return self

    def __exit__(self, *exc):
        CompiledModel.phase_component = self._pc
        CompiledModel.derivative_bases = self._db


def fit_case(key: str, repeats: int) -> None:
    setup = {c.key: c for c in bench.CASES}[key].build()

    def run(patched: bool):
        ref = rx.Refinement(setup.structure.model_copy(deep=True),
                            setup.instrument.model_copy(deep=True),
                            history=False)
        ctx = _buffer_substitution() if patched else None
        t0 = time.perf_counter()
        if ctx is None:
            result = ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                             two_theta_limits=setup.limits)
        else:
            with ctx:
                result = ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                                 two_theta_limits=setup.limits)
        wall = time.perf_counter() - t0
        return result, wall, ctx

    print(f"\n  {key}")
    exact_walls, buf_walls = [], []
    result_e = result_b = ctx = None
    for _ in range(repeats):
        result_e, w, _ = run(False)
        exact_walls.append(w)
        result_b, w, ctx = run(True)
        buf_walls.append(w)
    print(f"    exact fit    {min(exact_walls):6.2f}-{max(exact_walls):6.2f} s"
          f"   Rwp {result_e.statistics.rwp:.5f}  {result_e.status}")
    print(f"    buffered fit {min(buf_walls):6.2f}-{max(buf_walls):6.2f} s"
          f"   Rwp {result_b.statistics.rwp:.5f}  {result_b.status}  "
          f"({ctx.buffers.builds} buffer builds, "
          f"{ctx.buffers.build_wall:.2f} s)")

    rows_b = {p.path: p for p in result_b.parameters}
    worst_v = (0.0, "")
    dvs, des, movers = [], [], []
    for pe in result_e.parameters:
        pb = rows_b.get(pe.path)
        if pb is None or not pe.stderr or pb.stderr is None:
            continue
        dv = abs(pb.value - pe.value) / pe.stderr
        de = abs(pb.stderr - pe.stderr) / pe.stderr
        dvs.append(dv)
        des.append(de)
        if dv > worst_v[0]:
            worst_v = (dv, pe.path)
        if de > 0.05:
            movers.append((de, pe.path, pe.value, pe.stderr, pb.stderr))
    print(f"    {len(dvs)} params: value dev median "
          f"{np.median(dvs):.4f} esd, worst {worst_v[0]:.3f} esd "
          f"({worst_v[1]})")
    print(f"    esd dev median {np.median(des) * 100:.2f} %, "
          f"{len(movers)} rows over 5 %:")
    for de, path, v, se, sb in sorted(movers, reverse=True):
        # esd/|value|: a ratio ≳ 1 marks a direction the data barely
        # measures, where the esd itself is the unstable quantity
        ratio = se / max(abs(v), 1e-30)
        print(f"      {path}: value {v:.3e}, esd {se:.2e} -> {sb:.2e} "
              f"({de * 100:.0f} %, esd/|value| {ratio:.2g})")


# -- figure ------------------------------------------------------------------

def plot_sweep(all_results: dict[str, list[SweepResult]], out: Path) -> None:
    """The anchors-vs-accuracy curve: one panel per study, shared axes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    studies = list(all_results)
    n = len(studies)
    ncol = min(n, 4)
    nrow = (n + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.1 * ncol, 2.9 * nrow),
                             sharex=True, sharey=True, squeeze=False)
    # the four informative combinations; the full table is in the stdout log
    color = {("plain", "uniform"): "#999999", ("plain", "motion"): "#4477aa",
             ("cubic", "motion"): "#cc6677", ("cubic", "greedy"): "#882255",
             ("cubicstretch", "motion"): "#117733"}
    for ax, key in zip(axes.ravel(), studies):
        labels = []
        for (scheme, placement), c in color.items():
            rows = [r for r in all_results[key]
                    if r.scheme == scheme and r.placement == placement]
            ks = [r.n_anchors for r in rows]
            errs = [max(r.worst[:3]) for r in rows]
            ax.loglog(ks, errs, "-", color=c, lw=1.4)
            labels.append([errs[-1], f"{scheme}/{placement}", c, ks[-1]])
        if ax is axes.ravel()[0]:
            # right-margin labels, spread by one line of type in log space
            labels.sort()
            for j in range(1, len(labels)):
                labels[j][0] = max(labels[j][0], labels[j - 1][0] * 2.4)
            for y, text, c, k_end in labels:
                ax.annotate(text, (k_end, y), textcoords="offset points",
                            xytext=(3, 0), color=c, fontsize=8,
                            ha="left", va="center")
        for tol in TOLS:
            ax.axhline(tol, color="0.6", lw=0.7, ls=":")
        ax.set_title(key, fontsize=9, loc="left")
        ax.set_xticks([2, 4, 8, 16, 32, 64], ["2", "4", "8", "16", "32", "64"])
        ax.minorticks_off()
        ax.tick_params(labelsize=8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    for ax in axes.ravel()[len(studies):]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("anchors across the range", fontsize=9)
    for row in axes:
        row[0].set_ylabel("worst area/moment error", fontsize=9)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    print(f"\nfigure: {out}")


# -- driver ------------------------------------------------------------------

#: the two states the prototype and the fit check run on — the WP names them:
#: the FCJ-heavy trigger (the milestone's cold target) and cpd-2 (the QPA
#: acceptance protocol on real lab data)
PROTO_CASES = ("cpd-2", "trigger")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WP-1114 peaks-buffer spike")
    ap.add_argument("--part", default="anchors,proto,fit",
                    help="comma list of: anchors, proto, fit")
    ap.add_argument("--cases", default="nac,cpd-1a,cpd-2,trigger",
                    help="anchors-part case keys")
    ap.add_argument("--start-only", action="store_true",
                    help="skip the converged states (no fits; for iteration)")
    ap.add_argument("--dense", type=int, default=257,
                    help="reference positions across the range")
    ap.add_argument("--delta", type=int, default=1501,
                    help="offset-grid points across the widest window")
    ap.add_argument("--fit-repeats", type=int, default=2)
    ap.add_argument("--plot", default="tests/output/wp1114_anchor_curve.png")
    args = ap.parse_args(argv)

    print(f"{_about.DIST_NAME} {version(_about.DIST_NAME)} · "
          f"numpy {np.__version__} · python {platform.python_version()} · "
          f"{platform.system().lower()}/{platform.machine()} · "
          f"venv {Path(sys.prefix)}")
    parts = {p.strip() for p in args.part.split(",") if p.strip()}
    case_keys = [c.strip() for c in args.cases.split(",") if c.strip()]
    by_key = {c.key: c for c in bench.CASES}

    if "anchors" in parts:
        t0 = time.perf_counter()
        studies = build_studies(case_keys, args.start_only)
        print(f"states built in {time.perf_counter() - t0:.0f} s "
              f"({len(studies)} studies)")

        print(f"\n  {'study':22s} {'pts':>6s} {'pairs':>6s} {'fcj':>6s} "
              f"{'win/pts':>8s} {'elem/pts':>9s} {'elem/win':>7s}")
        for study in studies:
            print(volume_row(study))

        all_results: dict[str, list[SweepResult]] = {}
        for study in studies:
            results, budget = sweep_study(study, args.dense, args.delta)
            print_sweep(study, results, budget)
            all_results[study.key] = results

        if args.plot:
            plot_sweep(all_results, Path(args.plot))

    if "proto" in parts:
        print(f"\nproto: evaluation-level wall + deviation "
              f"(buffer tol {BUFFER_TOL:.0e}, max {BUFFER_MAX_ANCHORS} anchors)")
        for key in PROTO_CASES:
            setup = by_key[key].build()
            study = _study(f"{key} @ start", setup.structure,
                           setup.instrument, setup.data, setup.mode,
                           setup.limits)
            proto_study(study)

    if "fit" in parts:
        print("\nfit: full protocol through the buffer vs exact")
        for key in PROTO_CASES:
            fit_case(key, args.fit_repeats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
