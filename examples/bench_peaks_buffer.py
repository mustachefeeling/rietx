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
* **anchors vs accuracy** — the WP's central measurement.  A dense reference
  set of exact shapes across the range is reconstructed from K anchors under
  two schemes, and the worst deviation over the range is reported:

  - scheme **plain**: anchor shapes on a common Δ2θ grid, linear blend in θ.
  - scheme **stretch**: each anchor is stretched to the *true* combined FWHM
    at the query angle before the same linear blend — Γ(θ) and η(θ) are two
    cheap scalars per reflection (Caglioti + TCH), so the exact width is
    always available and only the dimensionless shape is interpolated.

  Deviations are quoted in the same currency WP-1112 used for window
  truncation: relative area, first moment (in FWHM units — cells and zero
  ride on positions), relative central second moment, and peak-relative
  pointwise error.  The reference and the anchors use a 128-image FCJ
  quadrature so the number measured is interpolation error alone, not
  quadrature error (which the shipped path owns and sizes separately).

Anchors are uniform in 2θ.  The per-θ table row (``worst @``) says where the
binding error sits; if it concentrates at low angle the production grid
should densify there, and the uniform numbers printed here are then an upper
bound on the anchor count.

States: each case is measured at the state its cold fit *starts* from and at
the state it converges to (the trigger's "converged" is the truth model that
generated its data) — a buffer must hold its tolerance along the whole
trajectory, and widths at convergence are not the widths at the start.

Wall clock: rebuilding the converged states runs one fit per case
(~30-60 s total); ``--start-only`` skips them during iteration.
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
    compile_model,
    window_fwhm_mult,
)
from rietx.model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm  # noqa: E402
from rietx.model.profiles.fcj import fcj_extent_deg, fcj_offsets_weights  # noqa: E402
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

    def __init__(self, study: Study, ip: int):
        m, v = study.model, study.values
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
    families = [ShapeFamily(study, ip) for ip in range(len(study.model.phases))]
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
        for (scheme, placement), c in color.items():
            rows = [r for r in all_results[key]
                    if r.scheme == scheme and r.placement == placement]
            ks = [r.n_anchors for r in rows]
            errs = [max(r.worst[:3]) for r in rows]
            ax.loglog(ks, errs, "-", color=c, lw=1.4)
            if ax is axes.ravel()[0]:
                ax.annotate(f"{scheme}/{placement}", (ks[-1], errs[-1]),
                            textcoords="offset points", xytext=(3, 0),
                            color=c, fontsize=8, ha="left", va="center")
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

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WP-1114 peaks-buffer spike")
    ap.add_argument("--part", default="anchors", choices=("anchors",))
    ap.add_argument("--cases", default="nac,cpd-1a,cpd-2,trigger")
    ap.add_argument("--start-only", action="store_true",
                    help="skip the converged states (no fits; for iteration)")
    ap.add_argument("--dense", type=int, default=257,
                    help="reference positions across the range")
    ap.add_argument("--delta", type=int, default=1501,
                    help="offset-grid points across the widest window")
    ap.add_argument("--plot", default="tests/output/wp1114_anchor_curve.png")
    args = ap.parse_args(argv)

    print(f"{_about.DIST_NAME} {version(_about.DIST_NAME)} · "
          f"numpy {np.__version__} · python {platform.python_version()} · "
          f"{platform.system().lower()}/{platform.machine()} · "
          f"venv {Path(sys.prefix)}")
    case_keys = [c.strip() for c in args.cases.split(",") if c.strip()]
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
