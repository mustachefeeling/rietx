"""WP-1112 gate: the batched derivative bases prototyped on FCJ data.

**Prototype only — the shipped path is untouched.**  WP-0605 batched the
*forward* peak loop and measured the FCJ node-axis padding eating the win
(pad 0.58×); it never prototyped ``derivative_bases``, which it named as
"Phase 2's real work" and measured at ~2× the forward.  This script is that
missing measurement, on WP-1111's ``cpd-1a`` and trigger-shaped states —
picked as the FCJ pair, of which one turned out to have no FCJ at all (the
discovery below) — judged before WP-1112 touches the ``entries`` contract.

What is rebuilt batched, per (line, reflection) row of the frozen windows —
exactly the quantities ``CompiledModel.derivative_bases`` builds:

* symmetric rows: one ``pseudo_voigt_derivs`` call on the padded (R, W)
  plane → Ω, ∂Ω/∂pos (= −∂Ω/∂x), ∂Ω/∂Γ, ∂Ω/∂η;
* FCJ rows: batched node generation (``fcj_nodes_batch``, per distinct
  frozen count), one ``pseudo_voigt_derivs`` on the (R, M, W) plane, the
  node-weighted sums as batched matmuls, and the node-FD variants — a second
  node generation at pos+h for ∂Ω/∂pos (h = 1e-5, the shipped step), plus
  optionally two more at sl+h, hl+h for the axial columns (h = 1e-7).

Layouts, as in WP-0605: ``pad`` (one (R, M_max, W_max) plane set),
``bucket`` (one plane set per distinct node count, no node-axis padding),
``chunk`` (the pad layout in bounded row chunks).  ``sym+loop`` is the
fallback scope — symmetric rows batched, FCJ rows through the shipped
per-row arithmetic — which is what ships if the FCJ layouts lose.

Two loop baselines, because the FCJ node memo (WP-0605 task 0) splits the
shipped cost by stage type:

* ``warm``  — every ``_cached_fcj_nodes`` slot hits: a width-moving stage
  (positions static between iterations; nodes depend only on pos, S/L, H/L).
* ``cold``  — the FD variants (variant ≥ 1) cleared before each call,
  variant 0 left warm: a position-moving stage, where the residual at the
  same θ has just filled variant 0 and every pos+h slot misses.  ``cell``
  and ``zero_disp`` — the two most iteration-hungry stages — live here.

The batched path recomputes its node planes every call (no memo), so its one
number stands against both baselines.  ``phase_peaks`` is called once per
phase by both paths at the same θ (scalar memo warm) — shared, not measured.

Agreement is checked row by row against the loop's ``entries``: symmetric
rows must be **exactly bit-equal** (same elementwise expressions, broadcast);
FCJ rows are batched matmuls where the loop ran one dgemv per reflection, so
they agree to rounding, not to the bit (0605's precedent — the re-baseline
ritual applies if that scope ships).

Measured (2026-08-21, Apple-silicon Mac, main-checkout venv ``[dev]``,
darwin/arm64, best of 3; the go/no-go these numbers feed is recorded in
docs/wp/1112-batched-derivative-bases.md)
----------------------------------------------------------------------
Full bases build (Ω + 3 partials + pos node-FD, axial off), loop vs batched:

  cpd-1a   222 rows, **all symmetric** (the discovery below), w_max 283
           loop 3.9 ms, warm = cold (no nodes to cache)
           every layout 0.94-0.98 ms (4.0×), exactly bit-equal to the loop
  trigger  1 188 rows, 93 % FCJ, nodes 8-17, w_max 425 (Σ windows =
           114× n_points), loop warm 65.6-67.4 ms | cold pos-FD 88.7-88.8
           pad 80.5-82.7 (0.8×/1.1×) | pad chunk=64 67.4-69.6 (1.0×/1.3×)
           bucket 48.1-48.5 (1.4×/1.8×) | sym-only+loop 83.3-83.9 (0.8×/1.1×)
           axial on: loop cold 137.1-142.0 ms | bucket 50.1-51.5 (2.7-2.8×)

Where the trigger's batched time goes (diagnosed, not assumed): ~86 % is
kernel arithmetic at ~11 ns/element — the WP's microbenchmark per-point
cost — because ±30·FWHM windows make every FCJ row m×W ≈ 3 200 points, so
the *loop* is point-bound and batching removes only its dispatch share.
Padding is NOT 0605's forward killer here: W-axis waste 1.06×, node-axis
bucket waste 1.03×.  Pad-to-m_max *is* a real ~2× on the node axis (counts
8-17, majority 8), which is why pad loses to bucket — the layout answer is
bucket, as on 0605's forward.

At narrowed windows (scratch monkeypatch of WINDOW_FWHM_MULT/WINDOW_MIN_DEG,
previewing this WP's η-window task; not part of this script's output):

  mult=15: trigger loop 48.1/71.0 → bucket 26.3 ms (1.8×/2.7×); cpd-1a 5.0×
  mult=8:  trigger loop 33.0/50.9 → bucket 16.3 ms (2.0×/3.1×), axial on
           92.2 → 18.2 (5.1×); cpd-1a 6.1×

so the two tasks compose: shrinking W returns the loop to dispatch-bound
and the batching ratio *rises* while the absolute cost falls (trigger full
bases, cold: 88.7 → 16.3 ms, ≈5.4× combined).

Agreement: symmetric rows exactly bit-equal in every layout on both cases.
FCJ rows are matmul-vs-dgemv: ≤ 4e-16 rel on Ω/∂pos/∂Γ/∂η and ≤ 3e-14 on
the axial node-FDs (an FD of near-cancelling node shifts divided by 1e-7),
and at some BLAS sizes exactly bit-equal — size-dependent, so bit-equality
is never *claimed* for the FCJ scope and the re-baseline ritual applies.

The discovery: **cpd-1a — and cpd-2, every stage of the QPA acceptance
protocol — compiles with no FCJ row at all.**  ``qarr_instrument`` leaves
both axial ratios at the preset's 0.0 and ``qpa_plan`` frees only
``axial_sl``, so ``fcj_node_count`` returns 0 throughout (both apertures
must be positive — profiles/fcj.py) and the freed ``axial_sl`` is a
provably-zero column the fit reports as unmeasured.  The "FCJ" in this
case's old blurb described the instrument's doublet optics, not the
compiled state; WP-1109's profile numbers are symmetric-kernel numbers,
which is why the WP's microbenchmarks reproduce them.

**Historical note**: this measurement gated WP-1112's contract change, and
the change then landed — ``CompiledModel.derivative_bases`` has been the
batched build (bucket layout) since that WP.  The rows this script labels
``loop`` therefore no longer measure a loop; the block above is the
pre-batch record, captured before the shipped path moved.  Landed, the
shipped build measured 1.06 ms on cpd-1a and 45.5 ms (48.1 axial-on) on the
trigger — the prototype's bucket numbers, minus its scaffolding.

Usage::

    python examples/bench_batched_derivative_bases.py
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from bench_batched_peak_loop import (  # noqa: E402
    BatchedPlan,
    _fcj_planes,
    _row_scalars,
)
from bench_refinement import _cpd_1a, _trigger  # noqa: E402
from bench_torch_mps import best_of  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model.forward import _cached_fcj_nodes, compile_model  # noqa: E402
from rietx.model.profiles.pseudovoigt import pseudo_voigt_derivs  # noqa: E402
from rietx.params.vector import ParameterTable  # noqa: E402

#: the shipped FD steps (``derivative_bases``); a prototype that chose its own
#: would be measuring a different derivative
H_POS, H_AX = 1e-5, 1e-7

#: skip the unchunked pad layout above this plane budget (4 kernel output
#: planes of (R, M, W) fp64 live at once, plus temporaries of the same shape)
PAD_PLANE_MB_LIMIT = 1200.0


# ----------------------------------------------------------------------
# batched build
# ----------------------------------------------------------------------


def _mm(w: np.ndarray, planes: np.ndarray) -> np.ndarray:
    """Node-weighted sum: (B, M) against (B, M, W) → (B, W)."""
    return np.matmul(w[:, None, :], planes)[:, 0, :]


def batched_bases(model, plans: list[BatchedPlan], values, *,
                  mode: str = "pad", chunk: int | None = None,
                  axial: bool = False):
    """The full derivative-bases build as batched array operations.

    Returns one dict per plan: ``sym`` → (rows, Ω, ∂pos, ∂Γ, ∂η) on the
    padded (R_sym, W) plane, ``fcj`` → a list of (rows, Ω, ∂pos, ∂Γ, ∂η[,
    ∂sl, ∂hl]) on (R, W) planes (one per bucket, or one concatenated set in
    pad mode).  Row indices index ``plan.rows``; every plane is masked-width
    padded exactly like ``plan.x``.
    """
    sl = float(values["instrument.geometry.axial_sl"])
    hl = float(values["instrument.geometry.axial_hl"])
    pad = mode == "pad"
    out = []
    for plan in plans:
        pos, gam, eta, _inten = _row_scalars(model, plan, values)
        res: dict = {}
        sym = plan.buckets.get(0, np.zeros(0, dtype=np.int64))
        if len(sym):
            pv, d_dx, d_dg, d_de = pseudo_voigt_derivs(
                plan.x[sym] - pos[sym, None], gam[sym, None], eta[sym, None])
            res["sym"] = (sym, pv, -d_dx, d_dg, d_de)
        # node planes for every evaluation point, same bucket split and
        # concatenation order for each so the variants stay row-aligned
        base = _fcj_planes(plan, pos, sl, hl, pad=pad)
        shift = _fcj_planes(plan, pos + H_POS, sl, hl, pad=pad)
        if axial:
            v_sl = _fcj_planes(plan, pos, sl + H_AX, hl, pad=pad)
            v_hl = _fcj_planes(plan, pos, sl, hl + H_AX, pad=pad)
        else:
            v_sl = v_hl = [(None, None, None)] * len(base)
        fcj = []
        for (rows_idx, phi, om), (_, phi1, om1), (_, phi_s, om_s), \
                (_, phi_h, om_h) in zip(base, shift, v_sl, v_hl):
            step = len(rows_idx) if chunk is None else chunk
            parts = []
            for a in range(0, len(rows_idx), step):
                rs = rows_idx[a:a + step]
                s = slice(a, a + step)
                pv, d_dx, d_dg, d_de = pseudo_voigt_derivs(
                    plan.x[rs][:, None, :] - phi[s][:, :, None],
                    gam[rs, None, None], eta[rs, None, None])
                omega = _mm(om[s], pv)
                d_gamma = _mm(om[s], d_dg)
                d_eta = _mm(om[s], d_de)
                dphi = (phi1[s] - phi[s]) / H_POS
                dom = (om1[s] - om[s]) / H_POS
                d_pos = _mm(dom, pv) - _mm(om[s] * dphi, d_dx)
                row = [omega, d_pos, d_gamma, d_eta]
                if axial:
                    for phi_v, om_v in ((phi_s[s], om_s[s]),
                                        (phi_h[s], om_h[s])):
                        dphi = (phi_v - phi[s]) / H_AX
                        dom = (om_v - om[s]) / H_AX
                        row.append(_mm(dom, pv) - _mm(om[s] * dphi, d_dx))
                parts.append(row)
            fcj.append((rows_idx,
                        *[np.concatenate([p[i] for p in parts], axis=0)
                          for i in range(len(parts[0]))]))
        res["fcj"] = fcj
        out.append(res)
    return out


def sym_batched_fcj_loop(model, plans: list[BatchedPlan], values):
    """The fallback scope: symmetric rows batched, FCJ rows the shipped way.

    The FCJ arithmetic below is ``derivative_bases``' own branch, node memo
    included (``_cached_fcj_nodes``), so the warm/cold split applies to this
    scope exactly as to the loop.
    """
    sl = float(values["instrument.geometry.axial_sl"])
    hl = float(values["instrument.geometry.axial_hl"])
    out = []
    for plan in plans:
        cp = model.phases[plan.ip]
        pos, gam, eta, _inten = _row_scalars(model, plan, values)
        res: dict = {}
        sym = plan.buckets.get(0, np.zeros(0, dtype=np.int64))
        if len(sym):
            pv, d_dx, d_dg, d_de = pseudo_voigt_derivs(
                plan.x[sym] - pos[sym, None], gam[sym, None], eta[sym, None])
            res["sym"] = (sym, pv, -d_dx, d_dg, d_de)
        rows = []
        for r in np.nonzero(plan.n_fcj)[0]:
            il, k = plan.rows[r]
            n = int(plan.n_fcj[r])
            x = model.tt[plan.i0[r]:plan.i1[r]]
            phi, om = _cached_fcj_nodes(cp, il, k, 0, float(pos[r]),
                                        sl, hl, n)
            pv, d_dx, d_dg, d_de = pseudo_voigt_derivs(
                x[None, :] - phi[:, None], float(gam[r]), float(eta[r]))
            phi1, om1 = _cached_fcj_nodes(cp, il, k, 1, float(pos[r]) + H_POS,
                                          sl, hl, n)
            dphi, dom = (phi1 - phi) / H_POS, (om1 - om) / H_POS
            rows.append((r, om @ pv, (dom @ pv) - ((om * dphi) @ d_dx),
                         om @ d_dg, om @ d_de))
        res["fcj_rows"] = rows
        out.append(res)
    return out


# ----------------------------------------------------------------------
# agreement against the loop's entries
# ----------------------------------------------------------------------


def compare(plans, bases, batched, *, axial: bool) -> dict[str, tuple]:
    """Per-quantity (max rel diff, all-exact?) of batched vs loop entries.

    Rows the loop skipped (non-finite position) have no entry and are not
    compared; the batched plane computes and masks them.
    """
    names = ("omega", "d_pos", "d_gamma", "d_eta") + (
        ("d_sl", "d_hl") if axial else ())
    worst = {n: 0.0 for n in names}
    exact = {n: True for n in names}

    def check(name, loop_arr, batch_row, width):
        if loop_arr is None:
            return
        got = batch_row[:width]
        if np.array_equal(got, loop_arr):
            return
        exact[name] = False
        scale = float(np.abs(loop_arr).max()) or 1.0
        worst[name] = max(worst[name],
                          float(np.abs(got - loop_arr).max()) / scale)

    for plan, res in zip(plans, batched):
        rowmap = {ilk: i for i, ilk in enumerate(plan.rows)}
        planes: dict[int, tuple] = {}
        if "sym" in res:
            for j, r in enumerate(res["sym"][0]):
                planes[int(r)] = tuple(a[j] for a in res["sym"][1:])
        for part in res.get("fcj", []):
            for j, r in enumerate(part[0]):
                planes[int(r)] = tuple(a[j] for a in part[1:])
        for r, om, dp, dg, de in res.get("fcj_rows", []):
            planes[int(r)] = (om, dp, dg, de)
        for entry in bases.entries[plan.ip]:
            il, k, i0, i1 = entry[0], entry[1], entry[2], entry[3]
            row = planes[rowmap[(il, k)]]
            width = i1 - i0
            for name, loop_arr, batch_row in zip(names, entry[4:], row):
                check(name, loop_arr, batch_row, width)
    return {n: (worst[n], exact[n]) for n in names}


# ----------------------------------------------------------------------


def _clear_fd_variants(model) -> None:
    """A position-moving iteration's cache state: variant 0 warm, FDs cold."""
    for cp in model.phases:
        if cp.fcj_cache:
            for key in [k for k in cp.fcj_cache if k[2] != 0]:
                del cp.fcj_cache[key]


def bench_case(key: str, setup) -> None:
    model = compile_model(setup.structure, setup.instrument, setup.data,
                          mode=setup.mode, two_theta_limits=setup.limits)
    assert model.shape == "tchz_pv", "prototype batches the TCHZ kernel only"
    table = ParameterTable(setup.structure, setup.instrument)
    values = table.decode(table.x0())
    plans = [BatchedPlan(model, ip) for ip in range(len(model.phases))]

    n_rows = sum(len(p.rows) for p in plans)
    n_fcj = sum(int((p.n_fcj > 0).sum()) for p in plans)
    counts = sorted({int(n) for p in plans for n in p.buckets if n})
    w_max = max(p.w_max for p in plans)
    mb = sum(p.plane_mb() for p in plans)
    fcj_txt = (f"node counts {counts[0]}-{counts[-1]}" if counts
               else "no FCJ")
    print(f"\n{key}: {setup.title}")
    print(f"  {n_rows} rows, {n_fcj} FCJ ({100 * n_fcj / n_rows:.0f} %), "
          f"{fcj_txt}, w_max {w_max}, pad plane {mb:.0f} MB/quantity")

    # verification first (also warms every cache variant, axial included)
    layouts = [("pad", None), ("pad", 64), ("bucket", None)]
    if mb * 4 > PAD_PLANE_MB_LIMIT:
        print(f"  pad unchunked skipped: 4 x {mb:.0f} MB "
              f"> {PAD_PLANE_MB_LIMIT:.0f} MB")
        layouts = layouts[1:]
    bases = model.derivative_bases(values, axial_derivs=True)
    for mode, chunk in layouts:
        got = batched_bases(model, plans, values, mode=mode, chunk=chunk,
                            axial=True)
        agree = compare(plans, bases, got, axial=True)
        tag = mode if chunk is None else f"{mode} chunk={chunk}"
        print(f"  agree {tag:12s}: " + "  ".join(
            f"{n}={'exact' if ex else f'{w:.1e}'}"
            for n, (w, ex) in agree.items()))
    got = sym_batched_fcj_loop(model, plans, values)
    agree = compare(plans, bases, got, axial=False)
    print("  agree sym+loop    : " + "  ".join(
        f"{n}={'exact' if ex else f'{w:.1e}'}"
        for n, (w, ex) in agree.items()))

    # timings: the hot-loop shape (axial off) against both cache baselines
    t_warm = best_of(lambda: model.derivative_bases(values,
                                                    axial_derivs=False))

    def loop_cold():
        _clear_fd_variants(model)
        return model.derivative_bases(values, axial_derivs=False)

    t_cold = best_of(loop_cold)
    print(f"  loop  warm nodes  : {t_warm * 1e3:8.2f} ms   "
          f"(width-moving stage)")
    print(f"  loop  cold pos-FD : {t_cold * 1e3:8.2f} ms   "
          f"(position-moving stage)")

    for mode, chunk in layouts:
        t = best_of(lambda: batched_bases(model, plans, values, mode=mode,
                                          chunk=chunk, axial=False))
        tag = mode if chunk is None else f"{mode} chunk={chunk}"
        print(f"  batched {tag:11s}: {t * 1e3:8.2f} ms   "
              f"{t_warm / t:4.1f}x warm / {t_cold / t:4.1f}x cold")

    def fallback_cold():
        _clear_fd_variants(model)
        return sym_batched_fcj_loop(model, plans, values)

    t = best_of(fallback_cold)
    print(f"  sym batched+loop  : {t * 1e3:8.2f} ms   "
          f"{t_warm / t:4.1f}x warm / {t_cold / t:4.1f}x cold   "
          f"(fallback scope, cold pos-FD)")

    # the FitReport path: axial node-FDs on (cold — its callers run once)
    def loop_axial():
        _clear_fd_variants(model)
        return model.derivative_bases(values, axial_derivs=True)

    t_ax_loop = best_of(loop_axial)
    t_ax = best_of(lambda: batched_bases(model, plans, values, mode="bucket",
                                         axial=True))
    print(f"  axial on: loop cold {t_ax_loop * 1e3:.2f} ms | "
          f"bucket {t_ax * 1e3:.2f} ms ({t_ax_loop / t_ax:.1f}x)")


def main() -> None:
    print(f"rietx {rx.__version__} | numpy {np.__version__} | "
          f"python {platform.python_version()} | {platform.platform()}")
    for key, build in (("cpd-1a", _cpd_1a), ("trigger", _trigger)):
        try:
            setup = build()
        except FileNotFoundError as exc:
            print(f"\n{key}: {exc} — skipped")
            continue
        bench_case(key, setup)


if __name__ == "__main__":
    main()
