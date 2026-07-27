"""Chunked forward-mode Jacobians on the torch backend (WP-0408).

The strategy differs from WP-0402's on purpose, and the difference is about
*where the win is*:

* On **CPU fp64** this module is a correctness instrument.  ``torch.func.jvp``
  over one-hot seeds gives a Jacobian that is independent of both the analytic
  peak chain and jax's jacfwd, so it is a third opinion in WP-0404's agreement
  matrix — that is what proves the torch implementation of the op set computes
  the same derivatives.
* On **Apple MPS** it is an accelerator.  The analytic columns are already exact
  and cheap, so what a GPU can add is forward throughput; and since no Apple GPU
  supports fp64 in any framework (docs/DESIGN.md, locked decisions), the device
  necessarily computes the whole peak chain in **fp32**.  That makes this the
  first *real-hardware* measurement of WP-0403's fp32-Jacobian-column policy:
  the CPU gate there round-trips fp64→fp32→fp64 and so captures fp32
  representation loss only, while an MPS pass accumulates error inside the
  forward evaluation as well.

Either way the host boundary is unchanged (architecture invariant 2): the
produced Jacobian is a plain fp64 numpy array in
``optimize.least_squares._make_jacobian``'s exact row/column layout, and the
residual used for cost/statistics plus the TRF solve stay numpy fp64.
``_jacobian_for`` applies WP-0403's ``cast_columns`` at the exit, so nothing
here needs a second precision hook.

Design notes shared with the jax backend, restated because they bind:

* **Frozen state closed over as constants.**  The residual closure reads the
  compiled model's numpy buffers (windows, design matrices, restraint rows, the
  Le Bail intensity snapshot) directly; only θ is traced.  The active backend is
  flipped to torch *only inside* the Jacobian call, so ``compile_model`` and the
  numpy residual never see a tensor — WP-0401 gotcha (1), which for a device
  backend would otherwise put non-fp64 arrays into frozen state.
* **Dense-C decode.**  ``ParameterTable`` promises p = C·θ_phys + d is a
  constant affine map during a solve; C is materialised dense here and the
  softplus/exp/logit transforms become elementwise torch ops, so ``decode`` is
  exact under autodiff.
"""

from __future__ import annotations

import numpy as np

from .api import get_backend, resolve_backend, set_backend

#: parameter-axis chunk for the vmapped one-hot tangent seeds (the jax backend's
#: DEFAULT_CHUNK, same reasoning: peak memory ≈ chunk × n_rows × 8 B per block)
DEFAULT_CHUNK = 32


def make_traced_decode(table, xp):
    """Traceable twin of :meth:`ParameterTable.decode` (θ → value dict).

    The numpy ``decode`` runs ``to_physical(float(t))`` per element — the
    ``float()`` coercions make it untraceable.  This builds the same map from
    frozen constants: elementwise transform application (grouped by kind into
    static masks) followed by the dense constant matmul p = C·θ_phys + d.
    Values come back as 0-d tensors keyed by dot-path, exactly the dict shape
    the forward model consumes.
    """
    torch = xp._torch
    C, d = table.constraint_block()
    C_dense = xp.asarray(np.asarray(C.toarray(), dtype=np.float64))
    d = xp.asarray(np.asarray(d, dtype=np.float64))
    paths = [e.path for e in table.entries]
    transforms = [table.entries[i].transform for i in table._free_idx]
    masks = {kind: np.array([t == kind for t in transforms])
             for kind in set(transforms) if kind != "identity"}
    # logaddexp(0, u), not torch.nn.functional.softplus: the latter switches to a
    # linear branch above threshold=20, which would not match params.transforms
    apply = {"softplus": lambda u: torch.logaddexp(torch.zeros_like(u), u),
             "exp": torch.exp,
             "logit": torch.sigmoid}

    def decode(theta):
        p = theta
        for kind, mask in masks.items():
            # static mask; both branches are smooth everywhere, so the
            # discarded branch cannot poison the selected tangent
            p = xp.where(mask, apply[kind](theta), p)
        full = C_dense @ p + d
        # scalarize: these 0-d values come from indexing, not from an op, so the
        # backend's own guard has not seen them (identity off MPS —
        # backend.api.scalar_tensor_class)
        return {path: xp.scalarize(full[i]) for i, path in enumerate(paths)}

    return decode


def make_traced_residual(model, table, xp):
    """The weighted residual as a pure traceable function of the combined θ.

    Mirrors ``optimize.least_squares._make_residual`` row for row — [data |
    background-penalty | Pawley-restraint] — with the Le Bail intensity snapshot
    and every weight/design constant closed over.  Any drift between the two is
    caught by ``tests/test_backend_torch.py``'s residual test and, column-wise,
    by WP-0404's matrix.
    """
    decode = make_traced_decode(table, xp)
    n_table = len(table.free_paths)
    sqrt_w = xp.asarray(np.asarray(1.0 / model.sigma, dtype=np.float64))
    y_obs = xp.asarray(np.asarray(model.y_obs, dtype=np.float64))
    # Le Bail extraction runs *between* solves; the snapshot is a constant of
    # the trace exactly as it is a constant of the numpy closure
    fixed_intens = ([xp.asarray(np.asarray(cp.hkl_intensity, dtype=np.float64))
                     for cp in model.phases] if model.mode == "lebail" else None)

    def residual(theta):
        if model.pawley is not None:
            intens = model.split_pawley_intensities(theta[n_table:])
            values = decode(theta[:n_table])
        else:
            intens = fixed_intens
            values = decode(theta)
        r = sqrt_w * (y_obs - model.evaluate(values, intens))
        parts = [r]
        pen = model.penalty_residual(values)
        if pen is not None:
            parts.append(pen)
        if model.pawley is not None:
            rpen = model.pawley_restraint_residual(theta[n_table:])
            if rpen is not None:
                parts.append(rpen)
        return parts[0] if len(parts) == 1 else xp.concatenate(parts)

    return residual


def make_torch_jacobian(model, table, *, chunk_size: int = DEFAULT_CHUNK,
                        device: str = "cpu"):
    """A drop-in replacement for ``_make_jacobian``'s callable, via ``jvp``.

    Chunks over the *parameter* axis: ``torch.func.vmap`` over blocks of
    ``chunk_size`` one-hot tangent seeds through ``torch.func.jvp``, the trailing
    block zero-padded to keep one shape (and hence one set of traced kernels).
    No ``torch.compile``: the peak loop is a few thousand tiny ops whose graph
    capture costs more than it saves, and correctness is this path's job.

    ``device="mps"`` runs the forward and the columns in fp32 on the Apple GPU;
    the returned array is fp64 on host either way.
    """
    xp = resolve_backend("torch" if device == "cpu" else f"torch-{device}")
    torch = xp._torch
    residual = make_traced_residual(model, table, xp)

    def jvp_block(theta, seeds):
        return torch.func.vmap(
            lambda s: torch.func.jvp(residual, (theta,), (s,))[1])(seeds)

    def jacobian(theta: np.ndarray) -> np.ndarray:
        theta = np.asarray(theta, dtype=np.float64)
        n = theta.shape[0]
        prev = get_backend()
        set_backend(xp)
        try:
            t = xp.asarray(theta, dtype=np.float64)
            eye = np.eye(n, dtype=np.float64)
            blocks = []
            for a in range(0, n, chunk_size):
                seeds = eye[a:a + chunk_size]
                if seeds.shape[0] < chunk_size:
                    seeds = np.concatenate(
                        [seeds, np.zeros((chunk_size - seeds.shape[0], n))])
                block = jvp_block(t, xp.asarray(seeds, dtype=np.float64))
                # .cpu() here, fp64 widening at the linalg64 boundary: this is a
                # device→host transfer of one seed block, not a precision policy
                blocks.append(np.asarray(block.detach().cpu(), dtype=np.float64))
            J = np.concatenate(blocks, axis=0)[:n]
        finally:
            set_backend(prev)
        return np.ascontiguousarray(J.T)

    return jacobian
