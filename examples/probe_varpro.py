"""WP-1125: variable projection on the background block — a count probe.

Run: ``.venv/bin/python examples/probe_varpro.py``

The question, from WP-1113: an expensive lab stage is an ftol-bound
Gauss-Newton tail walking a near-degenerate direction whose legs are
zero ↔ displacement ↔ **background**.  The background is linear in its
parameters, so profiling it out — solving it exactly at every evaluation and
handing the optimiser only the nonlinear set — removes one leg *by
construction* rather than by better stepping.  Does the tail collapse?

What this script does, per stage of a real plan: capture the compiled model
and parameter table the runner is about to solve with, run a **profiled** arm
beside the shipped **joint** arm from the same starting point and the same
tolerances, and print outer iterations, the accepted-step decay ratio and the
tail fraction for both.  The joint arm is the shipped ``run_least_squares``
call, delegated to unchanged, so the plan proceeds exactly as it would
without the probe.

**The metrics are outer iterations, decay ratio and tail fraction — not
nfev and not wall clock.**  Both arms carry an analytic Jacobian here (see
``Profiler.jacobian``), so nfev is comparable too and is printed, but the
count that decides the verdict is the accepted-step count.

Nothing in ``src/`` is touched.  ``rietx.refine.run_least_squares`` is
monkeypatched for the duration of a fit; that is a probe's licence, not a
design.

Why the projector is exact here
-------------------------------
VarPro's derivative usually needs a correction term for dc*/dθ, and Kaufman
(1975) drops part of it.  Neither applies to this case: the background design
rows are **frozen at stage compile** (the discreteness invariant), so the
projector P = M·M⁺ does not depend on θ at all and

    r̃(θ) = (I − P)·t(θ)   ⟹   dr̃/dθ = (I − P)·dt/dθ

exactly.  The profiled Jacobian is the joint one's nonlinear columns with
their background-imitable component removed, with no dropped term — which is
what ``docs/solver-survey.md`` §2.A1 states and what this measures against.
"""

from __future__ import annotations

import argparse
import copy
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares as scipy_lsq

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_refinement as bench  # noqa: E402

import rietx as rx  # noqa: E402
import rietx.refine  # noqa: E402,F401
from rietx.model import rows as row_layout  # noqa: E402
from rietx.optimize.least_squares import (  # noqa: E402
    GTOL,
    NFEV_PER_ITERATION,
    XTOL,
    _freeze_cell_windows,
    _jacobian_for,
    _lebail_snapshot,
    _make_residual,
    run_least_squares,
)

#: ``rietx.refine`` the *module*, not the top-level ``refine()`` function that
#: shadows it on the package — the monkeypatch target lives on the module.
refine_mod = sys.modules["rietx.refine"]

#: Gate 1's bar (E5 claim 1): shared parameters agree within this many esds.
AGREE_ESD = 0.1
#: Gate 2's bar (E5 claim 2, background half): the joint fit's background
#: coefficients equal the conditional ridge solution to this, relative to the
#: coefficient's own scale.  An identity, so the bar is machine-precision-ish
#: and not a tolerance anyone tuned.
IDENTITY_REL = 1e-9


class Refuse(Exception):
    """This stage is outside the probe's scope, stated rather than fudged."""


# ----------------------------------------------------------------------
# the profiled residual
# ----------------------------------------------------------------------
class Profiler:
    """r̃(θ_nl) — the joint residual at the background's conditional optimum.

    ``lin`` pairs a free-vector column with its row of ``model.bkg_design``;
    ``nl`` is everything else.  The inner problem is

        min_c ‖ t(θ) − M·c ‖² ,  M = [ √w·design ; −penalty ] ,

    whose blocks are the data rows and the P-spline penalty rows, so the
    profiled cost is the joint objective minimised over c and the two are
    directly comparable at any θ.  ``M`` is constant (frozen per stage), so
    ``M⁺`` is factored once and every evaluation is one matvec.
    """

    def __init__(self, model, table):
        self.model, self.table = model, table
        free = list(table.free_paths)
        bkg_index = {p: j for j, p in enumerate(model.bkg_paths)}
        self.lin = [(i, bkg_index[p]) for i, p in enumerate(free) if p in bkg_index]
        self.nl = [i for i, p in enumerate(free) if p not in bkg_index]
        if not self.lin:
            raise Refuse("no background coefficient is free in this stage")
        if model.pawley is not None:
            raise Refuse("pawley mode: the intensity block is linear too, and "
                         "non-negative — the landing WP's business")

        self._check_linearity()

        self.sqrt_w = 1.0 / model.sigma
        design = np.asarray([model.bkg_design[j] for _, j in self.lin],
                            dtype=np.float64)
        X = (design * self.sqrt_w).T                       # (n_points, nb)
        lay = {b.name: b for b in row_layout.layout(model)}
        self.n_data = lay["data"].n
        self.n_pen = lay["background_penalty"].n
        if self.n_pen:
            pen = np.asarray(model.bkg_penalty, dtype=np.float64)
            self.Pf = pen[:, [j for _, j in self.lin]]
            self.M = np.vstack([X, -self.Pf])
        else:
            self.Pf = None
            self.M = X
        self.n_m = self.M.shape[0]
        if self.n_m != self.n_data + self.n_pen:      # the layout, not a guess
            raise Refuse("linear block rows do not cover data+penalty exactly")
        self.pinv = np.linalg.pinv(self.M)
        self.cond = float(np.linalg.cond(self.M))
        self.X = X

        self._intens = _lebail_snapshot(model)
        self._base = np.array(table.x0(), dtype=np.float64)
        self._last_c = np.zeros(len(self.lin))
        self._joint_residual = _make_residual(model, table)
        self._joint_jacobian = _jacobian_for(model, table, "numpy")
        self._verify_assembly()

    # -- scope checks --------------------------------------------------
    def _check_linearity(self) -> None:
        """The linear columns must really be linear, and really unbounded.

        A softplus entry, a finite bound or a tie would each make the inner
        solve a different problem than the one being reported, silently.  The
        tie check is empirical — perturb the column and read the decode — so
        it holds whatever the constraint machinery does internally.
        """
        table, free = self.table, list(self.table.free_paths)
        lo, hi = table.bounds()
        x0 = np.array(table.x0(), dtype=np.float64)
        for i, _ in self.lin:
            path = free[i]
            if not (np.isneginf(lo[i]) and np.isposinf(hi[i])):
                raise Refuse(f"{path} carries finite bounds "
                             f"({lo[i]:.6g}, {hi[i]:.6g}); the inner solve is "
                             "unconstrained")
            probe = x0.copy()
            probe[i] += 1.0
            before, after = table.decode(x0), table.decode(probe)
            moved = {p: after[p] - before[p] for p in after
                     if abs(after[p] - before[p]) > 1e-12}
            if set(moved) != {path} or abs(moved[path] - 1.0) > 1e-12:
                raise Refuse(f"{path} is not an identity column of the decode "
                             f"(moves {sorted(moved)}); a transform or a tie "
                             "makes the background nonlinear in θ")

    def _verify_assembly(self) -> None:
        """The hand-assembled profiled residual *is* the package residual.

        Checked at the start point and one perturbed point, against
        ``rows.assemble`` through the shipped closure at (θ_nl, c*).  This is
        the whole reason the fast path is allowed to skip a second forward
        evaluation per call.
        """
        rng = np.random.default_rng(1125)
        for scale in (0.0, 1e-3):
            theta_nl = self._base[self.nl] + scale * rng.standard_normal(len(self.nl))
            mine = self.residual(theta_nl)
            theirs = self._joint_residual(self.theta_full(theta_nl, self._last_c))
            gap = float(np.max(np.abs(mine - theirs)))
            ref = float(np.max(np.abs(theirs))) or 1.0
            if gap > 1e-10 * ref:
                raise Refuse(f"profiled residual disagrees with rows.assemble "
                             f"by {gap:.3e} (scale {ref:.3e})")

    # -- the profiled evaluation ---------------------------------------
    def theta_full(self, theta_nl: np.ndarray, c: np.ndarray) -> np.ndarray:
        out = self._base.copy()
        out[self.nl] = theta_nl
        for (i, _), value in zip(self.lin, c, strict=True):
            out[i] = value
        return out

    def _target(self, theta_nl: np.ndarray) -> np.ndarray:
        """t(θ): the residual blocks the linear block has to explain, at c = 0."""
        theta0 = self.theta_full(theta_nl, np.zeros(len(self.lin)))
        values = self.table.decode(theta0)
        y_rest = self.model.evaluate(values, self._intens)
        d = self.sqrt_w * (self.model.y_obs - y_rest)
        if self.n_pen:
            p0 = np.asarray(self.model.penalty_residual(values), dtype=np.float64)
            return np.concatenate([d, p0]), values
        return d, values

    def residual(self, theta_nl: np.ndarray) -> np.ndarray:
        t, values = self._target(theta_nl)
        c = self.pinv @ t
        self._last_c = c
        r_m = t - self.M @ c
        rest = []
        if self.model.restraints is not None:
            extra = self.model.restraint_residual(values)
            if extra is not None:
                rest.append(np.asarray(extra, dtype=np.float64))
        return np.concatenate([r_m, *rest]) if rest else r_m

    def coefficients(self, theta_nl: np.ndarray) -> np.ndarray:
        """c*(θ_nl) — the conditional weighted (ridge) solution."""
        t, _ = self._target(theta_nl)
        return self.pinv @ t

    def jacobian(self, theta_nl: np.ndarray) -> np.ndarray:
        """(I − P)·J on the linear block's rows; J unchanged below them."""
        j_full = self._joint_jacobian(self.theta_full(theta_nl, self._last_c))
        g = np.asarray(j_full[:, self.nl], dtype=np.float64)
        head = g[:self.n_m]
        out = g.copy()
        out[:self.n_m] = head - self.M @ (self.pinv @ head)
        return out


# ----------------------------------------------------------------------
# trajectory bookkeeping — WP-1113's definitions, reused verbatim
# ----------------------------------------------------------------------
@dataclass
class Arm:
    name: str
    costs: list[float] = field(default_factory=list)   # every evaluation
    accepted: list[bool] = field(default_factory=list)
    nfev: int = 0
    status: str = ""
    termination: str = ""
    theta: np.ndarray | None = None

    def record(self, cost: float) -> None:
        best = min(self.costs, default=np.inf)
        self.nfev += 1
        self.costs.append(cost)
        self.accepted.append(bool(cost < best))

    @property
    def acc_costs(self) -> np.ndarray:
        return np.array([c for c, a in zip(self.costs, self.accepted, strict=True) if a])

    @property
    def n_accepted(self) -> int:
        return int(sum(self.accepted))

    def tail_fraction(self) -> tuple[int, int, float]:
        """(accepted evals to bank 99.99 % of the drop, total, tail fraction)."""
        costs = self.acc_costs
        if len(costs) < 2:
            return len(costs), len(costs), 0.0
        drop = costs[0] - costs[-1]
        if drop <= 0:
            return len(costs), len(costs), 0.0
        done = int(np.argmax(costs <= costs[-1] + 1e-4 * drop)) + 1
        return done, len(costs), (len(costs) - done) / len(costs)

    def decay_ratio(self) -> float:
        """Median (c_{k+1}−c_∞)/(c_k−c_∞) over the accepted tail.

        WP-1113's ≈ 0.93/iteration ridge walk is this number.  ``nan`` when
        the stage is too short to have a tail, which is itself the answer.
        """
        costs = self.acc_costs
        if len(costs) < 4:
            return float("nan")
        excess = costs - costs[-1]
        half = len(costs) // 2
        ratios = [excess[k + 1] / excess[k]
                  for k in range(half, len(costs) - 2)
                  if excess[k] > 0 and excess[k + 1] > 0]
        return float(np.median(ratios)) if ratios else float("nan")


# ----------------------------------------------------------------------
# one stage, both arms
# ----------------------------------------------------------------------
@dataclass
class StageProbe:
    case: str
    stage: str
    schedule: str
    n_free: int
    n_lin: int
    ftol: float
    joint: Arm
    profiled: Arm | None = None
    refused: str = ""
    cond: float = float("nan")
    #: gate 2 at the joint *endpoint* — E5 claim 2's bar
    identity_rel: float = float("nan")
    #: the same gap at the stage *start*: the precondition of the step
    #: identity below, and what decides whether the two arms can differ at all
    start_identity: float = float("nan")
    #: gate 3 — ‖Δθ_joint − Δθ_profiled‖/‖Δθ_joint‖ for the unconstrained
    #: Gauss-Newton step at the stage start, trust region and bounds removed
    gn_step_rel: float = float("nan")
    worst_esd: float = float("nan")
    worst_path: str = ""
    cost_joint: float = float("nan")
    cost_profiled: float = float("nan")


def gauss_newton_gap(prof: Profiler) -> tuple[float, float]:
    """(start-identity gap, GN-step gap) at the point the stage starts from.

    The mechanism this probe ended up measuring, stated as an equality that
    either holds or does not.  Minimising the joint linearised model over the
    linear block *first* gives

        min_Δθ ‖(I − P)·(r + J_θ·Δθ)‖²

    which is the profiled Gauss-Newton subproblem exactly — the Schur
    complement of the joint normal matrix.  And it holds **wherever c sits**,
    not only at the conditional optimum, because (I − P)·M = M − M·M⁺·M = 0 is
    a Moore-Penrose identity: the projection annihilates the linear block's
    contribution to the residual whatever coefficients it currently carries.
    So the two arms ask for one vector, and TRF's globalisation — a trust
    region and bounds over 11 variables against 5 — is the only thing left
    that can make them differ.

    Both steps are taken **unconstrained** here, no trust region and no
    bounds, so what is compared is the step the method asks for rather than
    the step the driver took.  ``start_identity`` is reported beside it
    because it is what an intuition would predict the answer depends on, and
    measuring it is how that intuition was refuted.
    """
    x0 = np.array(prof.table.x0(), dtype=np.float64)
    c_now = np.array([x0[i] for i, _ in prof.lin])
    c_cond = prof.coefficients(x0[prof.nl])
    scale = float(np.max(np.abs(c_now))) or 1.0
    start_gap = float(np.max(np.abs(c_now - c_cond))) / scale

    r_j = prof._joint_residual(x0)
    j_j = np.asarray(prof._joint_jacobian(x0), dtype=np.float64)
    step_j = np.linalg.lstsq(j_j, -r_j, rcond=None)[0][prof.nl]
    r_p = prof.residual(x0[prof.nl])
    j_p = prof.jacobian(x0[prof.nl])
    step_p = np.linalg.lstsq(j_p, -r_p, rcond=None)[0]
    denom = float(np.max(np.abs(step_j))) or 1.0
    return start_gap, float(np.max(np.abs(step_j - step_p))) / denom


def _run_profiled(prof: Profiler, ftol: float, max_iter: int) -> Arm:
    arm = Arm("profiled")
    lo, hi = prof.table.bounds()
    x0 = np.array(prof.table.x0(), dtype=np.float64)
    x0 = np.clip(x0, lo + 1e-12, hi - 1e-12)
    lo_nl, hi_nl = lo[prof.nl], hi[prof.nl]

    def fun(theta_nl: np.ndarray) -> np.ndarray:
        r = prof.residual(theta_nl)
        arm.record(0.5 * float(r @ r))
        return r

    res = scipy_lsq(fun, x0[prof.nl], jac=prof.jacobian, bounds=(lo_nl, hi_nl),
                    method="trf", ftol=ftol, xtol=XTOL, gtol=GTOL,
                    max_nfev=max_iter * NFEV_PER_ITERATION)
    arm.status = ("converged" if res.status > 0
                  else ("max_iter" if res.status == 0 else "diverged"))
    arm.termination = str(res.status)
    arm.theta = np.asarray(res.x, dtype=np.float64)
    return arm


class Probe:
    """The monkeypatch: profile every stage that has a free linear block."""

    def __init__(self, case: str, schedule: str, stages: set[str] | None):
        self.case, self.schedule, self.stages = case, schedule, stages
        self.results: list[StageProbe] = []
        self._joint = Arm("joint")

    # the events sink for the joint arm's trajectory
    def watch(self, event: dict) -> None:
        data = event.get("data", {})
        if event["kind"] == "eval":
            self._joint.costs.append(float(data["cost"]))
            self._joint.accepted.append(bool(data["accepted"]))
            self._joint.nfev += 1

    def wrapper(self, model, table, **kw):
        stage = kw.get("stage", "")
        ftol = kw.get("ftol", 1e-9)
        wanted = self.stages is None or stage in self.stages
        prof = None
        arm_p: Arm | None = None
        refused = ""
        gn = (float("nan"), float("nan"))
        if wanted:
            _freeze_cell_windows(model, table)   # idempotent; the same bounds
            try:
                prof = Profiler(model, table)
                # measured at the stage start, before either arm has moved
                gn = gauss_newton_gap(prof)
                arm_p = _run_profiled(prof, ftol, kw.get("max_iter", 100))
            except Refuse as exc:
                refused = str(exc)

        self._joint = Arm("joint")
        outcome = run_least_squares(model, table, **kw)
        self._joint.status = outcome.status
        self._joint.termination = outcome.termination
        self._joint.theta = np.asarray(outcome.theta, dtype=np.float64)
        if not wanted:
            return outcome

        rec = StageProbe(self.case, stage, self.schedule,
                         n_free=len(table.free_paths),
                         n_lin=0 if prof is None else len(prof.lin),
                         ftol=ftol, joint=self._joint, profiled=arm_p,
                         refused=refused, cost_joint=outcome.cost_final)
        rec.start_identity, rec.gn_step_rel = gn
        if prof is not None and arm_p is not None:
            rec.cond = prof.cond
            rec.cost_profiled = min(arm_p.costs) if arm_p.costs else float("nan")
            self._gates(rec, prof, outcome, arm_p)
        self.results.append(rec)
        return outcome

    def _gates(self, rec: StageProbe, prof: Profiler, outcome, arm_p: Arm) -> None:
        theta_j = np.asarray(outcome.theta, dtype=np.float64)
        # gate 2 — identity: the joint endpoint's coefficients ARE the
        # conditional solution at the joint endpoint's nonlinear values
        c_joint = np.array([theta_j[i] for i, _ in prof.lin])
        c_cond = prof.coefficients(theta_j[prof.nl])
        scale = float(np.max(np.abs(c_joint))) or 1.0
        rec.identity_rel = float(np.max(np.abs(c_joint - c_cond))) / scale
        # gate 1 — agreement on every shared (nonlinear) parameter, in esds
        if outcome.stderr_internal is not None and arm_p.theta is not None:
            free = list(prof.table.free_paths)
            sig = np.asarray(outcome.stderr_internal, dtype=np.float64)[prof.nl]
            delta = np.abs(arm_p.theta - theta_j[prof.nl])
            with np.errstate(divide="ignore", invalid="ignore"):
                esds = np.where(sig > 0, delta / sig, np.nan)
            if np.any(np.isfinite(esds)):
                k = int(np.nanargmax(esds))
                rec.worst_esd = float(esds[k])
                rec.worst_path = free[prof.nl[k]]


def probe_case(case_key: str, schedule: str, stages: set[str] | None) -> list[StageProbe]:
    setup = {c.key: c for c in bench.CASES}[case_key].build()
    if setup.patterns is not None:
        raise SystemExit(f"{case_key} is a series case; probe an ordinary one")
    plan = copy.deepcopy(setup.plan)   # a dataclass, not a pydantic model
    if schedule == "none":
        plan.intermediate_ftol = None
    probe = Probe(case_key, schedule, stages)
    original = refine_mod.run_least_squares
    refine_mod.run_least_squares = probe.wrapper
    try:
        ref = rx.Refinement(setup.structure.model_copy(deep=True),
                            setup.instrument.model_copy(deep=True),
                            history=False)
        ref.fit(setup.data, plan=plan, mode=setup.mode,
                two_theta_limits=setup.limits, events=probe.watch)
    finally:
        refine_mod.run_least_squares = original
    return probe.results


# ----------------------------------------------------------------------
# reporting
# ----------------------------------------------------------------------
def _fmt(x: float, spec: str = "6.3f") -> str:
    return "—".rjust(int(spec.split(".")[0])) if not np.isfinite(x) else f"{x:{spec}}"


def print_table(rows: list[StageProbe]) -> None:
    print("\n  accepted = accepted steps (outer iterations); decay = median "
          "(c-c∞) ratio\n  along the accepted tail; tail = fraction of accepted "
          "steps past 99.99 % of the drop")
    print(f"\n  {'case':8s} {'stage':17s} {'sched':6s} {'free':>5s} {'lin':>4s} "
          f"{'joint':>7s} {'prof':>7s} {'gain':>6s} "
          f"{'decay j':>7s} {'decay p':>7s} {'tail j':>7s} {'tail p':>7s} "
          f"{'nfev j':>7s} {'nfev p':>7s}")
    for r in rows:
        if r.refused or r.profiled is None:
            print(f"  {r.case:8s} {r.stage:17s} {r.schedule:6s} {r.n_free:5d} "
                  f"{'—':>4s}   refused: {r.refused}")
            continue
        ja, pa = r.joint.n_accepted, r.profiled.n_accepted
        ratio = ja / pa if pa else float("nan")
        _, _, jt = r.joint.tail_fraction()
        _, _, pt = r.profiled.tail_fraction()
        print(f"  {r.case:8s} {r.stage:17s} {r.schedule:6s} {r.n_free:5d} "
              f"{r.n_lin:4d} {ja:7d} {pa:7d} {_fmt(ratio, '6.2f')} "
              f"{_fmt(r.joint.decay_ratio(), '7.3f')} "
              f"{_fmt(r.profiled.decay_ratio(), '7.3f')} "
              f"{jt:7.2f} {pt:7.2f} {r.joint.nfev:7d} {r.profiled.nfev:7d}")


def print_gates(rows: list[StageProbe]) -> None:
    print(f"\n  gates — 1: shared parameters agree within {AGREE_ESD} esd (E5 "
          f"claim 1).  2: at the joint\n  endpoint the background coefficients "
          f"ARE the conditional solution, to {IDENTITY_REL:g} rel (claim 2).\n"
          "  3 (the mechanism): the unconstrained Gauss-Newton step in θ_nl is "
          "the SAME\n  vector in both arms — which it must be wherever 'start "
          "id' is zero.\n")
    print(f"  {'case':8s} {'stage':17s} {'sched':6s} {'start id':>9s} "
          f"{'end id':>9s} {'GN step':>9s} {'worst Δ/esd':>11s}  "
          f"{'parameter':26s} {'Δcost/cost':>11s}")
    for r in rows:
        if r.refused or r.profiled is None:
            continue
        base = abs(r.cost_joint) or 1.0
        dcost = (r.cost_profiled - r.cost_joint) / base
        print(f"  {r.case:8s} {r.stage:17s} {r.schedule:6s} "
              f"{r.start_identity:9.2e} {r.identity_rel:9.2e} "
              f"{r.gn_step_rel:9.2e} {_fmt(r.worst_esd, '11.3f')}  "
              f"{r.worst_path[:26]:26s} {dcost:11.2e}")


def print_verdict(rows: list[StageProbe]) -> None:
    live = [r for r in rows if r.profiled is not None and not r.refused]
    if not live:
        print("\n  no stage carried a free linear block — nothing to decide")
        return
    gains = [(r.joint.n_accepted / r.profiled.n_accepted, r)
             for r in live if r.profiled.n_accepted]
    gains.sort(reverse=True, key=lambda p: p[0])
    total_j = sum(r.joint.n_accepted for r in live)
    total_p = sum(r.profiled.n_accepted for r in live)
    bad_id = [r for r in live if not (r.identity_rel <= IDENTITY_REL)]
    bad_agree = [r for r in live
                 if np.isfinite(r.worst_esd) and r.worst_esd > AGREE_ESD]
    print(f"\n  accepted steps over every probed stage: joint {total_j}, "
          f"profiled {total_p} ({total_j / total_p if total_p else float('nan'):.2f}×)")
    if gains:
        best, rb = gains[0]
        worst, rw = gains[-1]
        print(f"  best stage {rb.case}/{rb.stage} {best:.2f}×; "
              f"worst {rw.case}/{rw.stage} {worst:.2f}×")
    print(f"  gate 2 (identity) failures: {len(bad_id)} of {len(live)}"
          + (f" — worst {max(r.identity_rel for r in bad_id):.2e}" if bad_id else ""))
    print(f"  gate 1 (agreement) failures: {len(bad_agree)} of {len(live)}"
          + (f" — worst {max(r.worst_esd for r in bad_agree):.3f} esd"
             if bad_agree else ""))
    # the mechanism: gate 3 holds everywhere, so whatever separates the arms
    # is TRF's globalisation and not the method
    worst_gn = max(r.gn_step_rel for r in live)
    print(f"  gate 3 (same Gauss-Newton step) worst gap: {worst_gn:.2e} over "
          f"{len(live)} stages,\n    at start-identity gaps spanning "
          f"{min(r.start_identity for r in live):.1e}-"
          f"{max(r.start_identity for r in live):.1e} — so the step identity "
          "does NOT\n    depend on the background already being converged")

    # where TRF never rejects it takes the Gauss-Newton step, and the arms
    # then cannot differ; where it rejects, its trust region is what differs
    pure = [r for r in live if r.joint.nfev - r.joint.n_accepted <= 1]
    mixed = [r for r in live if r.joint.nfev - r.joint.n_accepted > 1]
    if pure:
        same = sum(r.joint.n_accepted == r.profiled.n_accepted for r in pure)
        print(f"\n  stages TRF ran on pure Gauss-Newton steps (≤1 rejection): "
              f"{len(pure)} of {len(live)},\n    accepted-step counts identical "
              f"in {same} of them")
    if mixed:
        g = [r.joint.n_accepted / r.profiled.n_accepted for r in mixed
             if r.profiled.n_accepted]
        print(f"  stages where TRF rejected steps: {len(mixed)}, gain spans "
              f"{min(g):.2f}×-{max(g):.2f}×, median {np.median(g):.2f}×")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="variable projection on the background block (WP-1125)")
    ap.add_argument("--case", default="cpd-1a,cpd-2",
                    help=f"comma-separated; one of: "
                         f"{', '.join(c.key for c in bench.CASES)}")
    ap.add_argument("--schedule", default="default,none",
                    help="'default' (intermediate_ftol=1e-6), 'none' "
                         "(every stage at the solver's 1e-9), or both")
    ap.add_argument("--stages", default="",
                    help="comma-separated stage names (default: every stage)")
    args = ap.parse_args(argv)

    stages = {s.strip() for s in args.stages.split(",") if s.strip()} or None
    print(bench._header(1))
    print("\n  WP-1125 — the background profiled out, against the joint solve.\n"
          "  Metrics are accepted steps (outer iterations), the accepted-step\n"
          "  decay ratio and the tail fraction; nfev and wall clock are not\n"
          "  the measurement (root CLAUDE.md § Numbers).")

    rows: list[StageProbe] = []
    for case_key in (c.strip() for c in args.case.split(",") if c.strip()):
        for schedule in (s.strip() for s in args.schedule.split(",") if s.strip()):
            print(f"\n  … {case_key} at intermediate_ftol="
                  f"{'1e-6' if schedule == 'default' else 'None'}")
            rows.extend(probe_case(case_key, schedule, stages))

    print_table(rows)
    print_gates(rows)
    print_verdict(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
