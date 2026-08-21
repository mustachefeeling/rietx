"""WP-1113: print/plot one stage's optimizer trajectory off the event stream.

Run: ``.venv/bin/python examples/stage_trajectory.py --case cpd-2 --stage zero_disp``

The mechanism question this answers: is an expensive stage a **crawl** (the
accepted steps are pinned at a small physical scale, few rejections — the
trust region tracking a violently nonlinear residual at a fraction of a peak
width per iteration) or a **collapse** (large trial steps repeatedly rejected,
the step norm shrinking by factors between rejections — ill-conditioning), or
something else?  It reads only the WP-1113 ``eval`` event fields
(``accepted``/``step_norm``/``values``, plus ``lam`` under ``--solver lm``),
so what it prints is what any stream consumer could reconstruct.

Cases come from ``bench_refinement.CASES`` (the WP-1111 harness) so a
trajectory quoted here names the same fit as the harness's iteration columns.
The whole plan runs — a stage's starting point is the previous stages' work —
but only the named stage's events are kept.

Physical step columns are per-parameter deltas in *external* units (degrees,
Å, …): for an accepted evaluation the step actually taken from the previous
incumbent; for a rejected one the trial offset from the incumbent it failed
to replace.  Internal ``step_norm`` is printed beside them because its
*ratios* are scale-free — a rejection cascade shows as step_norm collapsing
whatever the units — while the physical columns are what a peak-width
comparison needs.

This is an analysis scaffold, not an API: nothing here is imported by the
package, and the numbers it prints carry the same rules as the harness's
(wall clock is not printed at all; counts are properties of the fit).
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_refinement as bench  # noqa: E402

import rietx as rx  # noqa: E402


def _collect(setup: bench.Setup, stage: str, solver: str):
    """Run the case's whole plan; keep the named stage's eval trajectory."""
    if setup.patterns is not None:
        raise SystemExit("series cases have no single stage trajectory; "
                         "pick an ordinary case")
    free_paths: list[str] = []
    rows: list[dict] = []
    stages_seen: list[str] = []
    end: dict = {}

    def watch(event: dict) -> None:
        data = event.get("data", {})
        if event["kind"] == "stage_start":
            stages_seen.append(data.get("stage", "?"))
            if data.get("stage") == stage:
                free_paths.extend(data.get("free_paths", []))
        elif event["kind"] == "eval" and data.get("stage") == stage:
            rows.append(data)
        elif event["kind"] == "stage_end" and data.get("stage") == stage:
            end.update(data)

    ref = rx.Refinement(setup.structure.model_copy(deep=True),
                        setup.instrument.model_copy(deep=True),
                        history=False, solver=solver)
    ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
            two_theta_limits=setup.limits, events=watch)
    if not rows:
        raise SystemExit(f"stage {stage!r} not found or emitted no evals; "
                         f"stages: {', '.join(stages_seen)}")
    return free_paths, rows, end


def _pick_params(free_paths: list[str], rows: list[dict],
                 globs: list[str], limit: int = 6) -> list[int]:
    """Column indices to print: the caller's globs, else the biggest movers.

    "Biggest" is total accepted travel normalised by the parameter's own
    scale, so a background coefficient moving by 40 counts does not outrank a
    zero error moving by 0.02°.
    """
    if globs:
        picked = [i for i, p in enumerate(free_paths)
                  if any(fnmatch.fnmatch(p, g) for g in globs)]
        if not picked:
            raise SystemExit(f"no free path matches {globs!r}; "
                             f"free: {', '.join(free_paths)}")
        return picked
    accepted = np.array([r["values"] for r in rows if r["accepted"]])
    if len(accepted) < 2:
        return list(range(min(limit, len(free_paths))))
    travel = np.abs(np.diff(accepted, axis=0)).sum(axis=0)
    scale = np.maximum(np.abs(accepted).max(axis=0), 1e-12)
    order = np.argsort(travel / scale)[::-1]
    return sorted(order[:limit].tolist())


def _deltas(rows: list[dict]) -> list[np.ndarray]:
    """Per-eval physical offset from the incumbent it was measured against."""
    out: list[np.ndarray] = []
    incumbent = np.asarray(rows[0]["values"], dtype=np.float64)
    for row in rows:
        values = np.asarray(row["values"], dtype=np.float64)
        out.append(values - incumbent)
        if row["accepted"]:
            incumbent = values
    return out


def _print_table(free_paths, rows, picked, tail: int | None) -> None:
    deltas = _deltas(rows)
    has_lam = "lam" in rows[0]
    names = [free_paths[i].split(".")[-1] if len(free_paths[i]) > 14
             else free_paths[i] for i in picked]
    lam_head = f" {'lam':>8s}" if has_lam else ""
    print(f"  {'eval':>5s} {'cost':>14s}  a {'step_norm':>9s}{lam_head}  "
          + " ".join(f"{n:>11s}" for n in names))
    start = 0 if tail is None else max(0, len(rows) - tail)
    if start:
        print(f"  … {start} earlier evaluations (--tail to widen)")
    for row, delta in zip(rows[start:], deltas[start:], strict=True):
        mark = "+" if row["accepted"] else "·"
        norm = f"{row['step_norm']:9.2e}" if "step_norm" in row else " " * 9
        lam = f" {row['lam']:8.1e}" if has_lam else ""
        cols = " ".join(f"{delta[i]:+11.3e}" for i in picked)
        print(f"  {row['n_eval']:5d} {row['cost']:14.8e}  {mark} {norm}{lam}  {cols}")


def _summary(free_paths, rows, picked) -> None:
    accepted = [r for r in rows if r["accepted"]]
    flags = [r["accepted"] for r in rows]
    runs: list[int] = []
    n = 0
    for flag in flags:
        if flag:
            if n:
                runs.append(n)
            n = 0
        else:
            n += 1
    if n:
        runs.append(n)
    norms = np.array([r["step_norm"] for r in accepted if "step_norm" in r])
    print(f"\n  {len(rows)} evals = {len(accepted)} accepted "
          f"+ {len(rows) - len(accepted)} rejected; "
          f"rejection runs {sorted(runs, reverse=True)[:12] or 'none'}"
          + (" …" if len(runs) > 12 else ""))
    # how much of the stage is tail: evals until 99.99 % of the total cost
    # decrease is banked, vs evals spent after that point
    costs = np.array([r["cost"] for r in accepted])
    drop = costs[0] - costs[-1]
    if drop > 0:
        done = int(np.argmax(costs <= costs[-1] + 1e-4 * drop)) + 1
        print(f"  cost decrease 99.99 % banked by accepted eval {done} of "
              f"{len(accepted)}; the remaining {len(accepted) - done} "
              f"accepted evals move the last 1e-4 of it")
    if len(norms):
        q = np.percentile(norms, [25, 50, 75])
        print(f"  accepted step_norm (internal): median {q[1]:.2e}, "
              f"IQR {q[0]:.2e}-{q[2]:.2e}, max {norms.max():.2e}")
    values = np.array([r["values"] for r in accepted])
    print(f"  {'parameter':34s} {'start':>12s} {'final':>12s} "
          f"{'travel':>10s} {'mean |step|':>11s} {'max |step|':>10s}")
    for i in picked:
        v = values[:, i]
        steps = np.abs(np.diff(v))
        mean_step = steps.mean() if len(steps) else 0.0
        max_step = steps.max() if len(steps) else 0.0
        print(f"  {free_paths[i]:34s} {v[0]:12.6g} {v[-1]:12.6g} "
              f"{np.abs(np.diff(v)).sum():10.3e} {mean_step:11.3e} "
              f"{max_step:10.3e}")


def _plot(free_paths, rows, picked, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    deltas = np.array(_deltas(rows))
    n_eval = np.array([r["n_eval"] for r in rows])
    cost = np.array([r["cost"] for r in rows])
    acc = np.array([r["accepted"] for r in rows])
    norm = np.array([r.get("step_norm", np.nan) for r in rows])

    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    axes[0].semilogy(n_eval[acc], cost[acc], "-o", ms=3, label="accepted")
    axes[0].semilogy(n_eval[~acc], cost[~acc], "x", ms=4, color="C3",
                     label="rejected")
    axes[0].set_ylabel("cost ½·rᵀr")
    axes[0].legend(frameon=False)
    axes[1].semilogy(n_eval[acc], norm[acc], "-o", ms=3)
    axes[1].semilogy(n_eval[~acc], norm[~acc], "x", ms=4, color="C3")
    axes[1].set_ylabel("step_norm (internal)")
    for i in picked:
        axes[2].plot(n_eval[acc], deltas[acc][:, i].cumsum(),
                     "-", lw=1, label=free_paths[i])
    axes[2].set_ylabel("physical travel from stage start")
    axes[2].set_xlabel("n_eval")
    axes[2].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"\n  plot written to {path}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="print/plot one stage's optimizer trajectory (WP-1113)")
    ap.add_argument("--case", required=True,
                    help=f"one of: {', '.join(c.key for c in bench.CASES)}")
    ap.add_argument("--stage", required=True, help="stage name in the plan")
    ap.add_argument("--solver", default="trf", choices=["trf", "lm"])
    ap.add_argument("--params", default="",
                    help="comma-separated path globs for the value columns "
                         "(default: the six biggest scale-relative movers)")
    ap.add_argument("--tail", type=int, default=None,
                    help="print only the last N evaluations (default: all)")
    ap.add_argument("--plot", default="", help="write a PNG here")
    args = ap.parse_args(argv)

    by_key = {c.key: c for c in bench.CASES}
    if args.case not in by_key:
        ap.error(f"unknown case {args.case!r}")
    setup = by_key[args.case].build()
    print(bench._header(1))
    print(f"\n  case {args.case} · stage {args.stage!r} · solver {args.solver}")

    free_paths, rows, end = _collect(setup, args.stage, args.solver)
    globs = [g.strip() for g in args.params.split(",") if g.strip()]
    picked = _pick_params(free_paths, rows, globs)
    print(f"  {len(free_paths)} free; ended {end.get('status', '?')} "
          f"on {end.get('termination', '?')}; columns are physical offsets "
          f"from the incumbent (a=accepted, ·=rejected)\n")
    _print_table(free_paths, rows, picked, args.tail)
    _summary(free_paths, rows, picked)
    if args.plot:
        _plot(free_paths, rows, picked, args.plot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
