"""Live monitoring session: rewrite-HTML-per-stage + the event stream.

``LiveSession(directory)`` is passed as ``events=`` to ``Refinement.fit``.
It is an :class:`~anatase.history.events.EventStream` writing
``events.jsonl`` in the directory, and additionally rewrites ``fit.html``
(plotly, self-contained) and ``status.json`` after every stage — the
"live view is a file that keeps getting replaced" design: no websockets, no
framework, and ``anatase watch`` is just a static file server with a
polling page on top.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..history.events import EventStream


class LiveSession(EventStream):
    """Event stream + per-stage snapshot files in one directory."""

    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        # truncate any previous run's log so the console pane starts clean
        (self.dir / "events.jsonl").write_text("", encoding="utf-8")
        super().__init__(path=self.dir / "events.jsonl")

    def write_snapshot(self, model, table, outcome, stage_name: str) -> None:
        """Called by ``Refinement.fit`` after each stage commit."""
        import numpy as np

        from ..optimize.statistics import compute_statistics
        from .html import figure_from_arrays

        values = table.decode(outcome.theta)
        y_calc = model.evaluate(values)
        y_bkg = model.background(values)
        stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                                   n_free=len(table.free_paths),
                                   y_background=y_bkg)

        ticks: dict[str, list[float]] = {}
        for ip, cp in enumerate(model.phases):
            cell = tuple(values[f"phases.{ip}.cell.{k}"]
                         for k in ("a", "b", "c", "alpha", "beta", "gamma"))
            rows = [cp.reflections.two_theta(cell, lam)
                    + values["instrument.zero_shift"]
                    for lam in model.line_wavelengths]
            pos = np.concatenate(rows)
            ticks[f"phase {ip}"] = sorted(float(p) for p in pos if np.isfinite(p))

        fig = figure_from_arrays(
            model.tt, model.y_obs, y_calc, y_bkg, ticks, sigma=model.sigma,
            title=f"after stage '{stage_name}':  Rwp={stats.rwp:.4f}  "
                  f"GoF={stats.gof:.2f}")
        tmp = self.dir / "fit.html.tmp"
        fig.write_html(str(tmp), include_plotlyjs=True, full_html=True,
                       config={"displaylogo": False})
        tmp.replace(self.dir / "fit.html")   # atomic swap — never a torn read

        (self.dir / "status.json").write_text(json.dumps({
            "stage": stage_name, "rwp": stats.rwp, "gof": stats.gof,
            "chi2": stats.chi2, "n_free": stats.n_free_parameters,
        }, indent=1), encoding="utf-8")
