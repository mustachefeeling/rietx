"""Size lever 1: the scalar-chain columns of one Jacobian, per column (shipped)
against batched across columns (prototype), on states inside a real fit.

usage: batchprobe.py REPO CASE [EVERY]

At every EVERY-th Jacobian the fit's own column calls are recorded, then
replayed twice more as two arms, interleaved three times, best of three:

  A  the shipped loop: ``_peak_chain_column`` once per column, memo primed
     at the expansion point as ``derivative_bases`` leaves it.
  B  one batched decode for every column (C @ P, the same CSR product
     ``decode`` makes per column), then per phase one block build over a
     leading column axis for three families -- widths, position shifts,
     cell -- and the shipped per-column call for everything else.  The
     scatter stays one kernel call per column in both arms.

Each B column is compared with A's.  Times exclude the scatter, which is
the kernel's and is reported on its own line.
"""
import os
import re
import sys
import time
from collections import defaultdict

repo, case = sys.argv[1], sys.argv[2]
every = int(sys.argv[3]) if len(sys.argv) > 3 else 10
sys.path.insert(0, os.path.join(repo, "examples"))
sys.path.insert(0, os.path.join(repo, "tests"))
os.environ.setdefault("RIETX_TELEMETRY", "0")

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
import rietx.optimize.least_squares as lsq  # noqa: E402
from rietx.crystallography.lattice import direct_metric_tensor, two_theta_deg  # noqa: E402
from rietx.crystallography.structure_factor import structure_factors_squared  # noqa: E402
from rietx.model.corrections import lorentz_polarization  # noqa: E402
from rietx.params.transforms import to_physical  # noqa: E402
import bench_refinement as br  # noqa: E402

WIDTH = re.compile(r"^(instrument\.profile\.[uvwxy]|phases\.(\d+)\."
                   r"(gauss_size|gauss_strain|lor_size|lor_strain))$")
POS = re.compile(r"^instrument\.(zero_shift|geometry\.sample_displacement|"
                 r"geometry\.sample_transparency)$")
CELL = re.compile(r"^phases\.(\d+)\.cell\.(a|b|c|alpha|beta|gamma)$")
WIDTH_PATHS = ["instrument.profile.u", "instrument.profile.v",
               "instrument.profile.w", "instrument.profile.x",
               "instrument.profile.y"]
PHASE_WIDTH = ["gauss_size", "gauss_strain", "lor_size", "lor_strain"]
POS_PATHS = ["instrument.zero_shift", "instrument.geometry.sample_displacement",
             "instrument.geometry.sample_transparency"]
CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")

orig_col = lsq._peak_chain_column
orig_acc = lsq._accumulate
acc_clock = [0.0]


def timed_acc(*a, **k):
    t0 = time.perf_counter()
    try:
        return orig_acc(*a, **k)
    finally:
        acc_clock[0] += time.perf_counter() - t0


def klass(path):
    if WIDTH.match(path):
        return "width"
    if POS.match(path):
        return "pos"
    if CELL.match(path):
        return "cell"
    return "other"


def plain_phase(model, bases, ip):
    """True where the batched blocks below reproduce phase_peaks exactly."""
    cp = model.phases[ip]
    return (model.mode == "rietveld" and len(bases.components(ip)) == 1
            and cp.po_axis is None and cp.skip_extinction
            and cp.batch_mag is None and cp.nuclear_mask is None)


def prime(model, values, intens):
    for ip in range(len(model.phases)):
        model.phase_peaks(ip, values, None if intens is None else intens[ip])


def arm_a(model, table, bases, theta, values, cols, intens):
    out, per = [], defaultdict(float)
    for c, path, affected, typical in cols:
        a0 = acc_clock[0]
        t0 = time.perf_counter()
        out.append(orig_col(model, table, bases, theta, values, c, path,
                            intens, affected=affected, typical=typical))
        per[klass(path)] += time.perf_counter() - t0 - (acc_clock[0] - a0)
    return out, per


def gather(lay, arrs):
    """(K, R) from per-line (K, n) arrays: lay.gather with a column axis."""
    K = arrs[0].shape[0]
    out = np.empty((K, len(lay.i0)))
    for il in range(len(lay.line_ptr) - 1):
        a, b = int(lay.line_ptr[il]), int(lay.line_ptr[il + 1])
        out[:, a:b] = arrs[il][:, lay.k[a:b]]
    return out


def cell_d(cp, cells):
    """(K, n) d-spacings for K cells: d_spacings with a column axis."""
    g = np.stack([direct_metric_tensor(*c) for c in cells])
    gstar = np.linalg.inv(g)
    h = np.asarray(cp.reflections.index, dtype=np.float64)
    return 1.0 / np.sqrt(np.einsum("ni,kij,nj->kn", h, gstar, h))


def arm_b(model, table, bases, theta, values, cols, intens, base):
    """``base`` holds what derivative_bases' own phase_peaks call has already
    built at the expansion point (read from the memo, outside the clock)."""
    per = defaultdict(float)
    t0 = time.perf_counter()
    # one decode for every column: θ_c + h in column c, θ elsewhere
    ent, free = table.entries, table._free_idx
    p_free = np.array([to_physical(float(t), ent[i].transform)
                       for t, i in zip(theta, free, strict=True)])
    K = len(cols)
    hs = np.array([lsq.fd_step(theta[c], typ) for c, _p, _a, typ in cols])
    pf = np.repeat(p_free[:, None], K, axis=1)
    for k, (c, _p, _a, _t) in enumerate(cols):
        pf[c, k] = to_physical(float(theta[c] + hs[k]), ent[free[c]].transform)
    P = np.asarray(table._C @ pf) + table._d[:, None]
    row = base["row"]
    per["decode"] += time.perf_counter() - t0

    parts = [[] for _ in cols]
    fallback = []
    groups = defaultdict(list)   # (class, ip) -> column indices
    for k, (c, path, affected, _t) in enumerate(cols):
        kl = klass(path)
        if kl == "cell":
            ip = int(CELL.match(path).group(1))
            if list(affected) != [ip] or not plain_phase(model, bases, ip):
                kl = "other"
            else:
                groups[("cell", ip)].append(k)
                continue
        if kl in ("width", "pos") and all(plain_phase(model, bases, ip)
                                          for ip in affected):
            for ip in affected:
                groups[(kl, ip)].append(k)
            continue
        fallback.append(k)

    for (kl, ip), ks in groups.items():
        t0 = time.perf_counter()
        cp, pp = model.phases[ip], bases.planes[ip]
        lay, h = pp.layout, hs[ks][:, None]
        b = base[ip]
        vk = dict(values)
        if kl == "width":
            for p in WIDTH_PATHS + [f"phases.{ip}.{n}" for n in PHASE_WIDTH]:
                vk[p] = P[row[p], ks][:, None]
            widths = model._width_block(ip, vk, b["tt"], b["aniso"])
            w1p = gather(lay, [w[0] for w in widths])
            w2p = gather(lay, [w[1] for w in widths])
            pos1, int1 = pp.pos[None, :], pp.inten[None, :]
        elif kl == "pos":
            for p in POS_PATHS:
                vk[p] = P[row[p], ks][:, None]
            posk = [tt + model._position_shift_deg(0.5 * tt, tt, vk)
                    for tt in b["tt"]]
            pos1 = gather(lay, posk)
            w1p, w2p, int1 = pp.w1[None, :], pp.w2[None, :], pp.inten[None, :]
        else:  # cell
            cells = [tuple(P[row[f"phases.{ip}.cell.{n}"], k] for n in CELL_NAMES)
                     for k in ks]
            for n in CELL_NAMES:
                vk[f"phases.{ip}.cell.{n}"] = P[row[f"phases.{ip}.cell.{n}"], ks][:, None]
            d = cell_d(cp, cells)
            ttk = [two_theta_deg(d, lam) for lam in b["lams"]]
            posk = [tt + model._position_shift_deg(0.5 * tt, tt, values)
                    for tt in ttk]
            widths = model._width_block(ip, values, ttk, b["aniso"])
            hkl = np.asarray(cp.reflections.hkl)
            f0 = time.perf_counter()
            f2 = structure_factors_squared(
                np.tile(hkl, (len(ks), 1)), d.ravel(), cp.sites,
                *model._site_values(ip, values, cells[0])).reshape(d.shape)
            per["cell f2"] += time.perf_counter() - f0
            mult = np.asarray(cp.reflections.multiplicity, dtype=np.float64)
            basek = values[f"phases.{ip}.scale"] * mult * f2
            ints = []
            for il in range(len(b["lams"])):
                w_line = values[f"instrument.source.lines.{il}.weight"]
                inten = basek * w_line * lorentz_polarization(
                    ttk[il], values["instrument.polarization"])
                inten = inten * model._absorption(ttk[il])
                ints.append(np.where(np.isfinite(posk[il]), inten, 0.0))
            pos1 = gather(lay, posk)
            w1p = gather(lay, [w[0] for w in widths])
            w2p = gather(lay, [w[1] for w in widths])
            int1 = gather(lay, ints)
        pair = pp.finite & np.isfinite(pos1)
        with np.errstate(invalid="ignore"):
            coefs = (np.where(pair, (int1 - pp.inten) / h, 0.0),
                     np.where(pair, pp.inten * ((pos1 - pp.pos) / h), 0.0),
                     np.where(pair, pp.inten * ((w1p - pp.w1) / h), 0.0),
                     np.where(pair, pp.inten * ((w2p - pp.w2) / h), 0.0))
        planes = (pp.omega, pp.d_pos, pp.d_gamma, pp.d_eta)
        coefs = [np.broadcast_to(cf, (len(ks), len(lay.i0))) for cf in coefs]
        nz = [(cf != 0.0).any(axis=1) for cf in coefs]
        for j, k in enumerate(ks):
            terms = [(np.ascontiguousarray(cf[j]), pl)
                     for cf, pl, z in zip(coefs, planes, nz) if z[j]]
            parts[k].append((ip, lay, terms))
        per[kl] += time.perf_counter() - t0

    out = [None] * len(cols)
    for k, parts_k in enumerate(parts):
        if k in fallback:
            continue
        c, path, affected, _t = cols[k]
        order = {ip: i for i, ip in enumerate(affected)}
        parts_k.sort(key=lambda t: order[t[0]])
        out[k] = lsq._accumulate(len(model.tt), [(lay, terms)
                                                 for _ip, lay, terms in parts_k])
    for k in fallback:
        c, path, affected, typical = cols[k]
        a0 = acc_clock[0]
        t0 = time.perf_counter()
        out[k] = orig_col(model, table, bases, theta, values, c, path, intens,
                          affected=affected, typical=typical)
        per["other"] += time.perf_counter() - t0 - (acc_clock[0] - a0)
    return out, per


def base_blocks(model, table, values):
    base = {"row": {e.path: i for i, e in enumerate(table.entries)}}
    for ip, cp in enumerate(model.phases):
        cell = tuple(values[f"phases.{ip}.cell.{n}"] for n in CELL_NAMES)
        lams = model.line_lambdas(values)
        d, tt = model._cell_block(cp, cell, lams)
        base[ip] = {"tt": tt, "lams": lams,
                    "aniso": model.strain_width(ip, values, d)}
    return base


totals = defaultdict(float)
diffs = []
n_jac = [0]
rec = []


def rec_col(model, table, bases, theta, values, c, path, intens=None,
            affected=None, typical=1.0):
    if affected is None:
        affected = ([int(path.split(".")[1])] if path.startswith("phases.")
                    else range(len(model.phases)))
    rec.append((model, table, bases, theta.copy(), values, intens,
                (c, path, list(affected), typical)))
    return orig_col(model, table, bases, theta, values, c, path, intens,
                    affected=affected, typical=typical)


orig_jac_for = lsq._jacobian_for


def jac_for(model, table, backend):
    inner = orig_jac_for(model, table, backend)

    def jacobian(theta):
        rec.clear()
        J = inner(theta)
        n_jac[0] += 1
        if rec and n_jac[0] % every == 0:
            measure()
        return J

    return jacobian


def measure():
    model, table, bases, theta, values, intens, _ = rec[0]
    if table.derived:
        return
    cols = [r[6] for r in rec]
    base = base_blocks(model, table, values)
    lsq._accumulate = timed_acc
    best_a, best_b = None, None
    try:
        for _ in range(3):
            prime(model, values, intens)
            acc_clock[0] = 0.0
            t0 = time.perf_counter()
            out_a, per_a = arm_a(model, table, bases, theta, values, cols, intens)
            ta = (time.perf_counter() - t0, acc_clock[0], per_a)
            prime(model, values, intens)
            acc_clock[0] = 0.0
            t0 = time.perf_counter()
            out_b, per_b = arm_b(model, table, bases, theta, values, cols,
                                 intens, base)
            tb = (time.perf_counter() - t0, acc_clock[0], per_b)
            if best_a is None or ta[0] - ta[1] < best_a[0] - best_a[1]:
                best_a = ta
            if best_b is None or tb[0] - tb[1] < best_b[0] - best_b[1]:
                best_b = tb
    finally:
        lsq._accumulate = orig_acc
    for (c, path, _a, _t), ya, yb in zip(cols, out_a, out_b):
        scale = np.abs(ya).max()
        diffs.append((klass(path), float(np.abs(ya - yb).max() / scale)
                      if scale else float(np.abs(yb).max())))
    totals["A"] += best_a[0] - best_a[1]
    totals["B"] += best_b[0] - best_b[1]
    totals["A acc"] += best_a[1]
    totals["B acc"] += best_b[1]
    for k, v in best_a[2].items():
        totals[f"A {k}"] += v
    for k, v in best_b[2].items():
        totals[f"B {k}"] += v
    totals["cols"] += len(cols)
    totals["jacobians"] += 1


setup = {c.key: c for c in br.CASES}[case].build()
lsq._peak_chain_column = rec_col
lsq._jacobian_for = jac_for
ref = rx.Refinement(setup.structure.model_copy(deep=True),
                    setup.instrument.model_copy(deep=True), history=False)
ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
        two_theta_limits=setup.limits)

print(f"{case}: {int(totals['jacobians'])} Jacobians sampled of {n_jac[0]}, "
      f"{int(totals['cols'])} scalar-chain columns")
print(f"shipped loop (A), scatter excluded: {totals['A']:.4f} s")
print(f"batched (B), scatter excluded:      {totals['B']:.4f} s   "
      f"ratio {totals['A'] / totals['B']:.2f}x")
print(f"scatter: A {totals['A acc']:.4f} s, B {totals['B acc']:.4f} s")
for kl in ("width", "pos", "cell", "other"):
    print(f"  {kl:6s} A {totals.get('A ' + kl, 0):.4f} s   "
          f"B {totals.get('B ' + kl, 0):.4f} s   (scatter excluded)")
print(f"  B decode {totals.get('B decode', 0):.4f} s, "
      f"B cell f2 {totals.get('B cell f2', 0):.4f} s (inside B cell)")
from collections import Counter  # noqa: E402
print("columns per class:", dict(Counter(kl for kl, _d in diffs)))
by = defaultdict(float)
for kl, dv in diffs:
    by[kl] = max(by[kl], dv)
print("largest |A - B| / max|A| per class:",
      {k: f"{v:.1e}" for k, v in by.items()})
