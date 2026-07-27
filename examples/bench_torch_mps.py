"""Time the torch backends against numpy on real patterns (WP-0408).

**Reported, never gated.**  Wall-clock is hardware-, thread- and thermal-
dependent, so no test asserts a speedup and none should; the numbers this
prints go into the milestone record as a measurement of one machine.  What *is*
asserted, in ``tests/test_backend_torch.py`` and WP-0404's matrix, is that every
backend computes the same Jacobian.

What is timed
-------------
Two patterns, chosen for opposite hot-loop shapes:

* **11-BM NAC** — synchrotron, one wavelength, no axial asymmetry: the simplest
  possible peak chain, so the loop overhead per reflection dominates.
* **SRM 676a corundum** — lab Cu Kα doublet through a graphite monochromator,
  *with the axial aperture opened* so FCJ quadrature is live: ~2 lines × tens of
  nodes more arithmetic per reflection, which is where a GPU has something to
  bite on.  (The acceptance test runs the same specimen with S/L = H/L = 0, i.e.
  no asymmetry; that would make this pattern the cheaper of the two, not the
  richer, so the benchmark sets them.)

and two quantities per (pattern, backend):

* one **forward** evaluation of the weighted residual — the thing a device
  accelerates;
* one full **Jacobian** — n_free columns, which is where the backends actually
  differ in *kind* (numpy assembles analytic peak-chain columns and does not
  evaluate the forward once per parameter; torch runs a vmapped ``jvp``, i.e.
  the whole forward per seed).

That last asymmetry is the honest headline: the numpy path is not "the same
algorithm on the CPU".  A per-column comparison against an analytic assembly
flatters no autodiff backend, and reading these numbers as "torch is slower
than numpy" would miss that the analytic chain is what is fast, not numpy.

Measured (2026-07-27, Apple-silicon Mac, torch 2.13, best of 3)
---------------------------------------------------------------
**MPS is 30-100× slower than numpy here, and the reason is the loop shape, not
the device.**  On 11-BM NAC the forward runs 2.0 ms (numpy) / 6.3 ms (torch CPU)
/ 199 ms (MPS); on corundum-with-FCJ 6.2 / 14.2 / 480 ms.  The printed hot-loop
line is the diagnosis: ~130 windows of 200-900 points each, evaluated one at a
time in python.  Every window is a handful of MPS kernel launches over a few
hundred elements — tens of microseconds of dispatch against a microsecond of
arithmetic — so the GPU spends its time being asked, not answering.  fp32
arithmetic cannot recover a 50× dispatch deficit; only batching the peak loop
(one padded (n_reflections × window) tensor per phase, which the frozen window
layout already makes possible) would give a device something to bite on.  That is
a change to the forward model for every backend, not to this backend, and it is
not in WP-0408's scope.

So the WP-0408 deliverable that survives is the *correctness* one: torch fp64 on
CPU is an independent third opinion in WP-0404's agreement matrix, and MPS gives
the first real-hardware confirmation that WP-0403's fp32-column policy converges
to the same answer (SRM 676a cell within 3e-5 Å — ``tests/test_backend_torch.py``).
Speed on Apple hardware waits on a batched peak loop.

Usage::

    python examples/bench_torch_mps.py
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

import pxrdref as pr
from pxrdref.model.forward import compile_model
from pxrdref.optimize.least_squares import _jacobian_for, _make_residual
from pxrdref.params.vector import ParameterTable

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"

#: the free set: one of every column family that costs real work
FREE_GLOBS = ("phases.*.scale", "phases.*.cell.*", "instrument.background.*",
              "instrument.profile.*", "instrument.zero_shift",
              "phases.*.atoms.*.biso")

#: repeats per timing; the reported number is the *best* of these, which is the
#: standard way to time on a machine that also has other work to do
REPEATS = 3


def available_backends() -> list[str]:
    """numpy plus whichever optional backends this machine actually has."""
    names = ["numpy"]
    try:
        import jax  # noqa: F401

        names.append("jax")
    except ImportError:
        pass
    try:
        import torch

        names.append("torch")
        if torch.backends.mps.is_available():
            names.append("torch-mps")
    except ImportError:
        pass
    return names


def nac_state():
    """11-BM NAC: synchrotron, single wavelength, no axial asymmetry."""
    path = DATA / "11BM_NAC.fxye"
    cif = DATA / "cod_1000236.cif"
    if not (path.exists() and cif.exists()):
        return None
    data = pr.read_pattern(path)
    structure = pr.Structure.from_cif(str(cif))
    instrument = pr.Instrument.debye_scherrer(wavelength=0.4139090)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    from pxrdref.schemas.instrument import BackgroundChebyshev

    instrument.background = BackgroundChebyshev.with_terms(6)
    return data, structure, instrument, (2.0, 24.0)


def corundum_state():
    """SRM 676a corundum: lab Cu Kα doublet + FCJ quadrature per reflection.

    The state of ``tests/test_acceptance_srm676a`` — inlined rather than imported,
    because an example must run from anywhere without the test package on the
    path.  α-Al₂O₃, R-3c on hexagonal axes (Lewis, Schwarzenbach & Flack, 1982,
    Acta Cryst. A38, 733) on the IUCr CPD round-robin's Philips Bragg-Brentano.
    """
    path = DATA / "qarr" / "corundum.prn"
    if not path.exists():
        return None
    data = pr.read_pattern(path)

    def p(v, **kw):
        return pr.Parameter(value=v, **kw)

    structure = pr.Structure(phases=[pr.Phase(
        name="corundum", space_group="R -3 c",
        cell=pr.Cell(a=p(4.7593, min=1.0), b=p(4.7593, min=1.0),
                     c=p(12.9917, min=1.0), alpha=p(90.0), beta=p(90.0),
                     gamma=p(120.0)),
        atoms=[pr.Atom(label="Al", species="Al", x=p(0.0), y=p(0.0),
                       z=p(0.35216), biso=p(0.30, min=0.0, max=25.0)),
               pr.Atom(label="O", species="O", x=p(0.30624), y=p(0.0),
                       z=p(0.25), biso=p(0.30, min=0.0, max=25.0))],
        scale=p(1e-3, min=0.0, transform="softplus"),
        lor_size=p(0.02, min=0.0, transform="softplus"))])
    instrument = pr.Instrument.bragg_brentano(radiation="CuKa",
                                             goniometer_radius_mm=173.0,
                                             monochromator_two_theta=26.6)
    from pxrdref.schemas.instrument import BackgroundChebyshev

    instrument.background = BackgroundChebyshev.with_terms(6)
    # a real axial aperture, so the FCJ quadrature is live — see the module
    # docstring on why the benchmark sets what the acceptance test leaves at zero
    instrument.geometry.axial_sl.value = 0.025
    instrument.geometry.axial_hl.value = 0.030
    # seed the scale so the calculated intensity is in the data's decade (the
    # acceptance test's seed_scales, for one phase)
    model = compile_model(structure, instrument, data, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    obs = np.asarray(data.intensity)
    structure.phases[0].scale.value *= float(
        (obs.sum() - obs.min() * len(obs)) / max(float(y.sum()), 1e-9))
    return data, structure, instrument, None


def compile_state(data, structure, instrument, limits):
    table = ParameterTable(structure, instrument)
    table.set_vary(["*"], False)
    for glob in FREE_GLOBS:
        table.set_vary([glob], True)
    model = compile_model(structure, instrument, data, mode="rietveld",
                          two_theta_limits=limits,
                          free_paths=set(table.free_paths))
    return model, table


def best_of(fn, *, repeats: int = REPEATS) -> float:
    """Seconds for the fastest of ``repeats`` calls, one warm-up discarded.

    The warm-up matters: the first torch call pays lazy kernel compilation (and
    on MPS, pipeline-state creation), which is a one-off per process, not a cost
    the solver pays per iteration.
    """
    fn()
    return min(_time_once(fn) for _ in range(repeats))


def _time_once(fn) -> float:
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


def bench(label: str, state, backends: list[str]) -> None:
    if state is None:
        print(f"\n{label}: dataset not present — skipped")
        return
    data, structure, instrument, limits = state
    model, table = compile_state(data, structure, instrument, limits)
    theta = table.x0()
    n_points, n_free = len(model.tt), len(theta)
    n_refl = sum(len(cp.reflections) for cp in model.phases)
    n_nodes = sum(int(cp.fcj_n.sum()) for cp in model.phases)
    # the number that explains the result: one `window_add` (and a whole profile
    # evaluation) per non-empty (line, reflection) window, each over a slice this
    # wide.  A few thousand kernel launches of a few hundred elements is a shape
    # in which per-launch overhead, not arithmetic, is the cost — which is why the
    # GPU loses and why fixing it means batching the peak loop, not a faster op.
    widths = np.concatenate([(cp.win[..., 1] - cp.win[..., 0]).ravel()
                             for cp in model.phases])
    widths = widths[widths > 0]
    print(f"\n{label}: {n_points} points, {n_refl} reflections × "
          f"{len(model.line_wavelengths)} line(s), {n_nodes} FCJ nodes, "
          f"{n_free} free parameters")
    print(f"  hot loop: {widths.size} windows of {widths.mean():.0f} points mean "
          f"({widths.min()}-{widths.max()})")

    # the forward is backend-dispatched through the *global* backend, so time it
    # by flipping that; the Jacobian callables carry their own backend
    residual = _make_residual(model, table)
    base_forward = best_of(lambda: residual(theta))
    print(f"  {'backend':10s}  {'forward':>10s}  {'vs numpy':>9s}  "
          f"{'jacobian':>10s}  {'vs numpy':>9s}  {'per column':>10s}")
    base_jac = None
    for name in backends:
        jac = _jacobian_for(model, table, name)
        t_jac = best_of(lambda: jac(theta))
        t_fwd = base_forward if name == "numpy" else _forward_on(name, model, table, theta)
        base_jac = base_jac if base_jac is not None else t_jac
        print(f"  {name:10s}  {t_fwd * 1e3:9.2f}ms  {base_forward / t_fwd:8.2f}×  "
              f"{t_jac * 1e3:9.2f}ms  {base_jac / t_jac:8.2f}×  "
              f"{t_jac / n_free * 1e3:9.2f}ms")


def _forward_on(name: str, model, table, theta) -> float:
    """One residual evaluation with ``name`` installed as the global backend.

    Uses each backend's own traced residual (its ``decode`` twin included), which
    is what the Jacobian differentiates — not the numpy closure with a backend
    bolted on.
    """
    from pxrdref.backend import resolve_backend, set_backend

    xp = resolve_backend(name)
    if name == "jax":
        from pxrdref.backend.jax_backend import _enable_x64, make_traced_residual

        residual = None
        set_backend(xp)
        try:
            with _enable_x64():
                residual = make_traced_residual(model, table)
                return best_of(lambda: np.asarray(residual(theta)))
        finally:
            set_backend("numpy")
    from pxrdref.backend.torch_backend import make_traced_residual

    set_backend(xp)
    try:
        residual = make_traced_residual(model, table, xp)
        t = xp.asarray(theta, dtype=np.float64)
        return best_of(lambda: np.asarray(residual(t).detach().cpu()))
    finally:
        set_backend("numpy")


def main() -> None:
    backends = available_backends()
    print(f"backends: {', '.join(backends)}")
    if "torch" in backends:
        import torch

        print(f"torch {torch.__version__}, mps available: "
              f"{torch.backends.mps.is_available()}")
    bench("11-BM NAC (synchrotron, 1 line)", nac_state(), backends)
    bench("SRM 676a corundum (Cu Kα doublet + FCJ)", corundum_state(), backends)
    print("\nReported, not gated — see the module docstring on why the numpy "
          "Jacobian column is not the same algorithm.")


if __name__ == "__main__":
    main()
