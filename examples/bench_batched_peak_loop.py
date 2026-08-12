"""WP-0605 Phase-1 prototype: the peak loop as padded batched kernels.

**Prototype only — the shipped path is untouched.**  This script rebuilds the
forward Bragg component of two real compiled states as padded batched
evaluations and measures, per state and backend: wall clock against the
shipped per-(line, reflection) loop, elementwise agreement (including exact
bit-equality, which is design question 3's evidence), and the padded-plane
memory the batching costs.  The states come from ``bench_torch_mps`` and are
chosen for opposite shapes:

* **11-BM NAC** — 129 symmetric windows (no FCJ), mean 865 points: the pure
  window-padding case, 1.09× waste.
* **SRM 676a corundum + FCJ** — 128 windows all carrying FCJ quadrature
  (8-29 nodes, skewed low): the node-axis case, where WP-0408 measured the
  padding waste at ~4× — the plane here is (rows, max_nodes, max_width).

Three batched layouts are measured, because the padding mitigation is one of
the WP's design questions:

* ``pad``     — one (R, M, W) plane, node axis padded to the max count with
                zero weights (node *generation* is still per distinct count:
                different counts use different Gauss-Legendre rules, so there
                is nothing meaningful to pad the generation over);
* ``bucket``  — one (R_n, M_n, W) plane per distinct node count: no node-axis
                padding at all, at the cost of one kernel set per bucket;
* ``chunk``   — the ``pad`` layout evaluated in row chunks, bounding peak
                memory (the 615 MB extrapolation in the WP is what this
                mitigates).

Bit-identity notes (design question 3, measured by the ``exact`` column):

* the scatter is ``np.bincount`` over row-major flattened (index, weight)
  pairs, so for any output point the contributions arrive in the same
  (line, reflection) order as the shipped loop's ``window_add`` sequence —
  summation *order* is preserved by construction;
* the symmetric plane evaluates the identical elementwise expressions the
  loop does, just broadcast — those two facts together make the NAC case a
  candidate for exact bit-equality;
* the FCJ node-weighted sum is a batched matmul where the loop does a dgemv
  row at a time, and BLAS does not promise those reduce identically — so the
  corundum case is expected to agree to rounding, not to the bit.

Measured (2026-07-28, Apple-silicon Mac, best of 3; the go/no-go these
numbers feed is recorded in docs/wp/0605-batched-peak-loop.md)
----------------------------------------------------------------------
Forward Bragg component, shipped loop vs batched:

  11-BM NAC (symmetric)  loop 1.85 ms | pad 1.20 (1.55×) | bucket 1.16 (1.59×)
                         torch-cpu 0.97 (1.92×) | MPS fp32 3.35 (0.55×)
                         every numpy layout EXACTLY bit-equal to the loop
  corundum (all-FCJ)     loop 2.94 ms | pad 5.12 (0.58×) | bucket 2.56 (1.15×)
                         torch-cpu 2.97 (0.99×) | MPS fp32 5.22 (0.56×)
                         max rel diff 2e-16, not bit-equal (matmul vs dgemv)

The two headline facts: the symmetric case really is a ~1.6× forward win and
really is bit-identical, and **the FCJ pad layout is a 0.58× regression** —
the 2.5× node-axis padding waste (counts 8-29, padded to 28 images) more
than eats the kernel-count win, and bucketing by node count only recovers it
to 1.15×.  MPS loses on every layout at this problem size, exactly where
WP-0408's break-even (~50-65 k elements/kernel) predicted.  The forward is
also the minority cost: ``derivative_bases`` is ~2× the forward on both
states (measured alongside), so these ratios bound only the smaller half of
any whole-fit gain.

Usage::

    python examples/bench_batched_peak_loop.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_torch_mps import (  # noqa: E402
    available_backends,
    best_of,
    compile_state,
    corundum_state,
    nac_state,
)

from anatase.model.profiles.fcj import _gauss_legendre_01  # noqa: E402
from anatase.model.profiles.pseudovoigt import pseudo_voigt  # noqa: E402

# ----------------------------------------------------------------------
# frozen batched layout (the stage-compile part)
# ----------------------------------------------------------------------


class BatchedPlan:
    """Everything frozen at stage compile for one phase's batched evaluation.

    Rows are the non-empty (line, reflection) windows in (il, k) order — the
    shipped loop's iteration order, which is what lets the scatter reproduce
    its accumulation order.  ``sym`` and ``fcj`` split the rows by frozen node
    count; every index/mask/grid plane below is compile-time constant, so none
    of this violates frozen-per-stage discreteness (the indices are not
    data-dependent).
    """

    def __init__(self, model, ip: int):
        cp = model.phases[ip]
        rows = [(il, k) for il in range(len(model.line_wavelengths))
                for k in range(len(cp.reflections))
                if cp.win[il, k, 1] > cp.win[il, k, 0]]
        self.ip = ip
        self.rows = rows
        self.i0 = np.array([cp.win[il, k, 0] for il, k in rows], dtype=np.int64)
        self.i1 = np.array([cp.win[il, k, 1] for il, k in rows], dtype=np.int64)
        self.n_fcj = np.array([cp.fcj_n[il, k] for il, k in rows], dtype=np.int64)
        width = self.i1 - self.i0
        self.w_max = int(width.max())
        # padded index/mask/grid planes (R, W): indices clipped into the
        # window so the padded tail reads a valid point and the mask zeroes it
        ar = np.arange(self.w_max)[None, :]
        self.idx = np.minimum(self.i0[:, None] + ar, self.i1[:, None] - 1)
        self.mask = (ar < width[:, None]).astype(np.float64)
        self.x = model.tt[self.idx]                    # frozen fit grid gather
        self.n_points = len(model.tt)
        # node-count buckets (distinct frozen counts; 0 = symmetric)
        self.buckets = {int(n): np.nonzero(self.n_fcj == n)[0]
                        for n in np.unique(self.n_fcj)}
        # per-line reflection indices, for vectorised row-scalar gathers
        self.line_ks = [np.array([k for il2, k in rows if il2 == il], dtype=np.int64)
                        for il in range(len(model.line_wavelengths))]
        self.m_of = {n: (0 if n == 0 else 2 * max(n // 2, 4))
                     for n in self.buckets}
        self.m_max = max(self.m_of.values())

    def plane_mb(self) -> float:
        """fp64 MB of the largest per-evaluation plane the ``pad`` mode makes."""
        m = max(self.m_max, 1)
        return len(self.rows) * m * self.w_max * 8 / 1e6


def fcj_nodes_batch(tt_deg: np.ndarray, sl: float, hl: float, n_nodes: int
                    ) -> tuple[np.ndarray, np.ndarray]:
    """``fcj_offsets_weights`` vectorised over reflections sharing one count.

    Same expressions as profiles/fcj.py evaluated on a (B, 1) position column
    against the (m,) quadrature row; returns (B, 2m) images and normalised
    weights.  The kink split and the τ → ξ map are unchanged, so positions
    and weights match the scalar routine to fp rounding (measured below).
    """
    tau, glw = _gauss_legendre_01(max(n_nodes // 2, 4))
    tt = np.radians(np.asarray(tt_deg, dtype=np.float64))[:, None]
    with np.errstate(divide="ignore"):
        cap = np.abs(np.tan(tt))
    cap = np.where(np.isfinite(cap), cap, np.inf)
    xi_max = np.minimum(sl + hl, cap)
    xi_kink = np.minimum(abs(sl - hl), xi_max)
    xi = np.concatenate([tau * xi_kink, xi_kink + tau * (xi_max - xi_kink)], axis=1)
    seg_len = np.concatenate([np.broadcast_to(xi_kink, xi_kink.shape + tau.shape[-1:] if False else (len(tt), len(tau))),
                              np.broadcast_to(xi_max - xi_kink, (len(tt), len(tau)))], axis=1)
    glw2 = np.concatenate([glw, glw])[None, :]
    cphi = np.clip(np.cos(tt) * np.sqrt(1.0 + xi * xi), -1.0, 1.0)
    phi = np.degrees(np.arccos(cphi))
    w_overlap = np.clip(sl + hl - xi, 0.0, 2.0 * min(sl, hl))
    omega = glw2 * seg_len * w_overlap
    total = omega.sum(axis=1, keepdims=True)
    ok = (xi_max > 0.0) & (sl > 0.0) & (hl > 0.0) & (total > 0.0)
    fallback_w = np.zeros_like(omega)
    fallback_w[:, 0] = 1.0
    return (np.where(ok, phi, np.degrees(tt)),
            np.where(ok, omega / np.where(ok, total, 1.0), fallback_w))


# ----------------------------------------------------------------------
# batched evaluation (numpy)
# ----------------------------------------------------------------------


def _row_scalars(model, plan: BatchedPlan, values):
    """(pos, gamma, eta, intensity) per plan row, from the shipped phase_peaks.

    Vectorised gathers (one fancy-index per line per quantity): a Phase-2
    implementation would do the same, so per-row python indexing here would
    charge the batched path an overhead the design does not have.
    """
    peaks = model.phase_peaks(plan.ip, values)
    cols = []
    for j in range(4):
        cols.append(np.concatenate(
            [np.asarray(peaks[il][j])[ks] for il, ks in enumerate(plan.line_ks)]))
    pos, gam, eta, inten = cols
    finite = np.isfinite(pos)
    return np.where(finite, pos, 0.0), gam, eta, np.where(finite, inten, 0.0)


def _fcj_planes(plan: BatchedPlan, pos, sl, hl, *, pad: bool):
    """Per-bucket (or padded-to-M) FCJ images and weights for the FCJ rows."""
    out = []
    for n, rows_idx in plan.buckets.items():
        if n == 0:
            continue
        phi, om = fcj_nodes_batch(pos[rows_idx], sl, hl, n)
        if pad and phi.shape[1] < plan.m_max:
            padw = plan.m_max - phi.shape[1]
            phi = np.pad(phi, ((0, 0), (0, padw)), constant_values=0.0)
            om = np.pad(om, ((0, 0), (0, padw)), constant_values=0.0)
        out.append((rows_idx, phi, om))
    if pad and len(out) > 1:
        rows_idx = np.concatenate([o[0] for o in out])
        phi = np.concatenate([o[1] for o in out], axis=0)
        om = np.concatenate([o[2] for o in out], axis=0)
        out = [(rows_idx, phi, om)]
    return out


def batched_bragg(model, plans: list[BatchedPlan], values, *,
                  mode: str = "pad", chunk: int | None = None) -> np.ndarray:
    """The forward Bragg component via padded batched kernels.

    ``mode="pad"``     one (R_fcj, M, W) plane per phase;
    ``mode="bucket"``  one plane per distinct node count;
    ``chunk``          row-chunked evaluation of the pad plane (memory bound).

    Contributions are scattered with one ``bincount`` per (phase, group), each
    group's flat array in plan-row order, so within a group the accumulation
    order equals the shipped loop's.  Groups (symmetric before FCJ, buckets in
    count order) can interleave differently than the loop where their windows
    overlap — the ``exact`` column below measures whether that matters.
    """
    y = np.zeros(plans[0].n_points)
    sl = float(values["instrument.geometry.axial_sl"])
    hl = float(values["instrument.geometry.axial_hl"])
    for plan in plans:
        pos, gam, eta, inten = _row_scalars(model, plan, values)
        sym = plan.buckets.get(0, np.zeros(0, dtype=np.int64))
        if len(sym):
            prof = pseudo_voigt(plan.x[sym] - pos[sym, None],
                                gam[sym, None], eta[sym, None])
            contrib = inten[sym, None] * prof * plan.mask[sym]
            y += np.bincount(plan.idx[sym].ravel(), weights=contrib.ravel(),
                             minlength=plan.n_points)
        for rows_idx, phi, om in _fcj_planes(plan, pos, sl, hl,
                                             pad=(mode == "pad")):
            step = len(rows_idx) if chunk is None else chunk
            for a in range(0, len(rows_idx), step):
                rs = rows_idx[a:a + step]
                prof = pseudo_voigt(
                    plan.x[rs][:, None, :] - phi[a:a + step][:, :, None],
                    gam[rs, None, None], eta[rs, None, None])
                mixed = np.matmul(om[a:a + step][:, None, :], prof)[:, 0, :]
                contrib = inten[rs, None] * mixed * plan.mask[rs]
                y += np.bincount(plan.idx[rs].ravel(), weights=contrib.ravel(),
                                 minlength=plan.n_points)
    return y


# ----------------------------------------------------------------------
# batched evaluation (torch, optional)
# ----------------------------------------------------------------------


def torch_batched_forward(model, plans, values, device: str):
    """The ``pad`` layout on torch; returns (callable, dtype) or None.

    Row scalars still come from the numpy ``phase_peaks`` (uploading four
    R-sized vectors per evaluation — the realistic seam), the planes and the
    node generation run on the device, and the scatter is ``index_add`` on the
    flattened contributions.
    """
    import torch

    dt = torch.float64 if device == "cpu" else torch.float32
    dev = torch.device(device)
    sl = float(values["instrument.geometry.axial_sl"])
    hl = float(values["instrument.geometry.axial_hl"])
    frozen = []
    for plan in plans:
        t_idx = torch.from_numpy(plan.idx.ravel()).to(dev)
        t_x = torch.from_numpy(plan.x).to(dev, dt)
        t_mask = torch.from_numpy(plan.mask).to(dev, dt)
        planes = []
        for n, rows_idx in plan.buckets.items():
            if n == 0:
                continue
            tau, glw = _gauss_legendre_01(max(n // 2, 4))
            planes.append((torch.from_numpy(rows_idx).to(dev),
                           torch.from_numpy(tau).to(dev, dt),
                           torch.from_numpy(np.concatenate([glw, glw])).to(dev, dt)))
        frozen.append((plan, t_idx, t_x, t_mask, planes))

    def forward():
        y = torch.zeros(plans[0].n_points, dtype=dt, device=dev)
        for plan, t_idx, t_x, t_mask, planes in frozen:
            pos_np, gam_np, eta_np, int_np = _row_scalars(model, plan, values)
            pos = torch.from_numpy(pos_np).to(dev, dt)
            gam = torch.from_numpy(gam_np).to(dev, dt)
            eta = torch.from_numpy(eta_np).to(dev, dt)
            inten = torch.from_numpy(int_np).to(dev, dt)
            contrib = torch.zeros_like(t_x)
            sym = plan.buckets.get(0, np.zeros(0, dtype=np.int64))
            if len(sym):
                s = torch.from_numpy(sym).to(dev)
                u = (t_x[s] - pos[s, None]) / gam[s, None]
                lor = (2.0 / (np.pi * gam[s, None])) / (1.0 + 4.0 * u * u)
                gau = ((2.0 / gam[s, None]) * np.sqrt(np.log(2.0) / np.pi)
                       * torch.exp(-4.0 * np.log(2.0) * u * u))
                pv = eta[s, None] * lor + (1.0 - eta[s, None]) * gau
                contrib[s] = inten[s, None] * pv * t_mask[s]
            for rows_idx, tau, glw2 in planes:
                tt = torch.deg2rad(pos[rows_idx])[:, None]
                cap = torch.abs(torch.tan(tt))
                xi_max = torch.clamp(cap, max=sl + hl)
                xi_kink = torch.clamp(torch.full_like(xi_max, abs(sl - hl)),
                                      max=1.0) * 0 + torch.minimum(
                    torch.full_like(xi_max, abs(sl - hl)), xi_max)
                xi = torch.cat([tau * xi_kink, xi_kink + tau * (xi_max - xi_kink)], dim=1)
                seg = torch.cat([xi_kink.expand(-1, tau.shape[0]),
                                 (xi_max - xi_kink).expand(-1, tau.shape[0])], dim=1)
                cphi = torch.clamp(torch.cos(tt) * torch.sqrt(1.0 + xi * xi), -1.0, 1.0)
                phi = torch.rad2deg(torch.arccos(cphi))
                w_ov = torch.clamp(sl + hl - xi, min=0.0, max=2.0 * min(sl, hl))
                om = glw2 * seg * w_ov
                om = om / om.sum(dim=1, keepdim=True)
                u = (t_x[rows_idx][:, None, :] - phi[:, :, None]) / gam[rows_idx, None, None]
                g2 = gam[rows_idx, None, None]
                lor = (2.0 / (np.pi * g2)) / (1.0 + 4.0 * u * u)
                gau = ((2.0 / g2) * np.sqrt(np.log(2.0) / np.pi)
                       * torch.exp(-4.0 * np.log(2.0) * u * u))
                pv = eta[rows_idx, None, None] * lor + (1.0 - eta[rows_idx, None, None]) * gau
                mixed = torch.matmul(om[:, None, :], pv)[:, 0, :]
                contrib[rows_idx] = inten[rows_idx, None] * mixed * t_mask[rows_idx]
            y = y.index_add(0, t_idx, contrib.reshape(-1))
        if device == "mps":
            torch.mps.synchronize()
        return y

    return forward


# ----------------------------------------------------------------------
def bench_state(label: str, state, backends: list[str]) -> None:
    if state is None:
        print(f"\n{label}: dataset not present — skipped")
        return
    model, table = compile_state(*state)
    values = table.decode(table.x0())
    plans = [BatchedPlan(model, ip) for ip in range(len(model.phases))]

    y_loop = np.asarray(model.bragg_component(values))
    t_loop = best_of(lambda: model.bragg_component(values))

    n_rows = sum(len(p.rows) for p in plans)
    mb = sum(p.plane_mb() for p in plans)
    print(f"\n{label}: {n_rows} windows, w_max {max(p.w_max for p in plans)}, "
          f"node planes {['%d:%d' % (n, len(r)) for p in plans for n, r in p.buckets.items() if n]}")
    print(f"  pad-mode peak plane: {mb:.1f} MB fp64")
    print(f"  shipped loop (numpy):     {t_loop * 1e3:8.2f} ms")

    for mode, chunk in (("pad", None), ("bucket", None), ("pad", 32)):
        y = batched_bragg(model, plans, values, mode=mode, chunk=chunk)
        t = best_of(lambda: batched_bragg(model, plans, values, mode=mode, chunk=chunk))
        exact = bool(np.array_equal(y, y_loop))
        scale = float(np.abs(y_loop).max())
        rel = float(np.abs(y - y_loop).max()) / scale if scale else 0.0
        name = mode if chunk is None else f"{mode} chunk={chunk}"
        print(f"  batched {name:12s} (numpy): {t * 1e3:8.2f} ms   {t_loop / t:5.2f}x   "
              f"max rel diff {rel:.2e}   exact bit-equal: {exact}")

    for dev_name, dev in (("torch", "cpu"), ("torch-mps", "mps")):
        if dev_name not in backends:
            continue
        fwd = torch_batched_forward(model, plans, values, dev)
        y = fwd().cpu().double().numpy()
        t = best_of(fwd)
        scale = float(np.abs(y_loop).max())
        rel = float(np.abs(y - y_loop).max()) / scale if scale else 0.0
        print(f"  batched pad ({dev_name+',fp' + ('64' if dev == 'cpu' else '32')}): "
              f"{t * 1e3:8.2f} ms   {t_loop / t:5.2f}x   max rel diff {rel:.2e}")


def main() -> None:
    backends = available_backends()
    print(f"backends: {', '.join(backends)}")
    bench_state("11-BM NAC (symmetric windows)", nac_state(), backends)
    bench_state("SRM 676a corundum (all-FCJ windows)", corundum_state(), backends)
    big = 2000 * 2 * 64 * 300 * 8 / 1e6
    print(f"\nextrapolation: 2000 refl x 2 lines x 64 nodes x 300 pts pad plane "
          f"= {big:.0f} MB fp64; chunk=256 rows bounds it at "
          f"{256 * 64 * 300 * 8 / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
