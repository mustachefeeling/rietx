"""Schemas for a sequential (in-situ / parametric) refinement series.

A series is N separate refinements, ordered, each warm-started from its
predecessor — not one joint residual (that is the multi-histogram path,
``rietx.multi``).  What the user wants back is therefore not N unrelated
results but a **trajectory**: a(T), Biso(t), the weight fractions against the
series coordinate, with esds, and with the per-pattern status of the fit that
produced each point.

Following the history DAG's rule (see :mod:`rietx.schemas.history`), a
:class:`SeriesResult` stores **summaries, not curves**.  Nine 7251-point
patterns' worth of ``y_obs``/``y_calc``/``y_background``/``sigma`` is ~2 MB of
JSON that is already on disk as the input files; the refined values, their
esds, the agreement indices and the diagnostics are what a series is *for*, and
they are a few kB.  The full :class:`~rietx.schemas.results.RefinementResult`
of each pattern stays reachable in memory on the
:class:`~rietx.sequential.SequentialRefinement` that produced it.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field

from .common import Base, Diagnostic, Mode, Provenance
from .results import (
    DELIVERABLES,
    PhaseAgreement,
    QuantitativePhaseAnalysis,
    RefinedParameter,
    Statistics,
    _diagnostic_lines,
)


class SeriesEntry(Base):
    """One pattern's place in the series: what was fitted and how it went.

    ``n_iterations`` lives here, per pattern — a series has no single pooled
    figure, so it is not on :class:`~rietx.schemas.results.Statistics` even
    though ``statistics`` below is one.
    """

    index: int
    label: str = ""
    #: The series coordinate — temperature, time, pressure, composition.
    #: ``None`` when the caller gave none, in which case ``index`` is the axis.
    x: float | None = None

    status: Literal["converged", "max_iter", "diverged"] = "converged"
    statistics: Statistics | None = None
    parameters: list[RefinedParameter] = Field(default_factory=list)
    qpa: QuantitativePhaseAnalysis | None = None
    #: Per-phase Bragg agreement, copied from each pattern's
    #: :attr:`~rietx.schemas.results.RefinementResult.phase_agreement` by
    #: :func:`rietx.sequential._entry_from_result` (the writer — WP-1076's rule).
    #:
    #: Carried because the signal existed on every underlying result and was
    #: dropped at the series boundary, and because a series is where a per-phase
    #: index is worth *iterating*: one pattern's R_B is a value, sixty are a
    #: trajectory, and a trajectory is a shape a single number cannot be read as.
    #:
    #: **It is not the answer to "is this phase real".**  Neither index is
    #: weighted, and I(obs) is the observed pattern partitioned in proportion to
    #: I(calc) — so a phase whose reflections sit under a stronger phase's peaks
    #: receives the intensity it predicted and scores well for having predicted
    #: it.  The bias is in the definition, not in the fit, and in-repo the
    #: arithmetic runs the *other* way to intuition: 11-BM NAC's 1.35 wt% CaF₂
    #: impurity scores R_B 0.385 against the major phase's 0.052, the whole
    #: misfit sitting in four reflections under strong NAC peaks (WP-1069).  A
    #: *low* R_B on a trace phase is therefore as consistent with a fully
    #: overlapped, self-fulfilling partition as with a real phase, and nothing
    #: here separates the two.
    #: :func:`~rietx.optimize.statistics.structure_r_factors` holds the
    #: definitions and the warning.
    #:
    #: The measurement that does answer that question is ``PHASE_UNCONSTRAINED``
    #: — the phase's strongest modelled point in σ of the observation noise,
    #: reaching an entry through :attr:`diagnostics` and aggregating over the
    #: chain as ``SEQUENTIAL_PERSISTENT_FINDING``.  R_B belongs beside it and
    #: beside the weight with its esd, never in front of either.
    #:
    #: Empty outside Rietveld mode, for the reason it is empty on
    #: ``RefinementResult`` there — in Le Bail the partition *is* the fit and in
    #: Pawley the intensities are parameters, so I(obs) would be compared against
    #: itself.
    phase_agreement: list[PhaseAgreement] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    #: Total least-squares iterations over **every attempt** on this pattern,
    #: every rung of the escalation ladder included.  The headline warm-start
    #: number: it is what a warm start actually buys, and it is measured rather
    #: than assumed (see WP-0505's acceptance).
    n_iterations: int = 0
    #: True when the warm start was rejected and this pattern was refitted from
    #: the initial models (see ``SEQUENTIAL_RESEED``) — equivalently, when the
    #: ladder ran and ``rung`` came back ``"cold"``.  A reseeded point is
    #: still a good fit — but it is *not* evidence that the trajectory is
    #: continuous there, because its starting point did not come from its
    #: neighbour.  The middle rung does **not** set it: ``"warm_staged"`` is
    #: still a warm start, so the chain is unbroken there.
    reseeded: bool = False
    #: Rwp the **first** (warm) attempt reached, set whenever the ladder
    #: escalated at all.  With ``reseeded`` it says how the escalation ended:
    #: both set means a cold restart rescued the pattern, ``rwp_warm`` alone
    #: means the fence fired but a warm attempt was still the best of the
    #: ones tried — worth seeing, since it marks a pattern the series found
    #: hard for a reason no restart could fix.
    rwp_warm: float | None = None
    #: Which attempt produced the values on this entry (WP-1051).  The chain
    #: escalates only on failure: ``"warm"`` is the collapsed warm refit
    #: (``refit="single"``'s first rung), ``"warm_staged"`` the full staged plan
    #: from the warm state, ``"cold"`` the full staged plan from the initial
    #: models.  The **first** pattern of a chain is always ``"cold"`` — it has
    #: no predecessor to warm from — which is why this field says where the
    #: numbers came from while ``reseeded`` says whether the chain was *broken*
    #: here; those are different questions and only the second one has a fence.
    rung: Literal["warm", "warm_staged", "cold"] = "warm"
    #: Every rung attempted on this pattern, in ladder order: one entry for a
    #: pattern that fitted first time, up to three when the ladder ran to the
    #: end.  It is what makes the escalation auditable — ``rung`` alone cannot
    #: say whether the winning attempt was the only one, and the cost in
    #: ``n_iterations`` is the sum over exactly these.
    rungs_tried: list[str] = Field(default_factory=list)

    #: Where this pattern's own history lives (one tree per pattern — a tree is
    #: pinned to one pattern by its data fingerprint).
    node_id: str | None = None
    tree_id: str | None = None

    def value(self, path: str) -> float | None:
        for p in self.parameters:
            if p.path == path:
                return p.value
        return None

    def stderr(self, path: str) -> float | None:
        for p in self.parameters:
            if p.path == path:
                return p.stderr
        return None


class Trajectory(Base):
    """One parameter's path across the series, with its per-point esds.

    ``x`` is the series coordinate when one was given and the pattern index
    otherwise; ``x_label`` says which, so a plot axis is never mislabelled.
    ``value``/``stderr`` are aligned with it, and ``stderr`` entries are
    ``None`` wherever that pattern did not estimate one (a parameter that was
    not free in that fit, or a stage that returned no covariance).
    """

    path: str
    x: list[float] = Field(default_factory=list)
    x_label: str = "index"
    value: list[float] = Field(default_factory=list)
    stderr: list[float | None] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.value)

    def arrays(self):
        """``(x, value, stderr)`` as float arrays; missing esds become NaN."""
        import numpy as np

        return (np.asarray(self.x, dtype=float),
                np.asarray(self.value, dtype=float),
                np.asarray([np.nan if s is None else s for s in self.stderr],
                           dtype=float))


class SeriesResult(Base):
    """The result of a sequential refinement over an ordered set of patterns.

    Iterating it yields :class:`SeriesEntry` in series order.  Series-level
    diagnostics (path dependence, discontinuities, reseeds) sit on
    :attr:`diagnostics`; per-pattern ones stay on their entry.
    """

    mode: Mode = "rietveld"
    entries: list[SeriesEntry] = Field(default_factory=list)
    x_label: str = "index"
    #: ``"forward"``/``"backward"``: the chain direction whose fits are
    #: reported in :attr:`entries`.  ``"both"`` means the series was run twice
    #: and the two trajectories compared — the reported entries are the forward
    #: ones, and the comparison is in :attr:`diagnostics`.
    direction: Literal["forward", "backward", "both"] = "forward"
    #: the reverse chain, present iff ``direction == "both"`` (WP-1076).
    #: Its own ``backward`` is always ``None``: it is one extra level, not a
    #: cycle.  Without it a caller of :func:`~rietx.refine_sequential` received
    #: the ``SEQUENTIAL_PATH_DEPENDENT`` diagnostics and had no way to reach
    #: the trajectory they are about — the comparison was reachable only from
    #: ``SequentialRefinement.backward_``, which the one-shot API never
    #: returns.
    backward: "SeriesResult | None" = None
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    provenance: Provenance | None = None

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):  # type: ignore[override]
        return iter(self.entries)

    def __getitem__(self, i: int) -> SeriesEntry:
        return self.entries[i]

    @property
    def labels(self) -> list[str]:
        return [e.label for e in self.entries]

    @property
    def x(self) -> list[float]:
        """The series axis: the given coordinate, or the pattern index."""
        return [float(e.index) if e.x is None else e.x for e in self.entries]

    @property
    def rwp(self) -> list[float]:
        return [e.statistics.rwp if e.statistics else float("nan")
                for e in self.entries]

    @property
    def n_iterations(self) -> int:
        """Least-squares iterations over the chain this result *reports*.

        That is :attr:`entries`, so under ``direction="both"`` it is the
        forward chain only and **not what the run cost** — the reverse chain is
        a second complete set of fits, and its own count is
        ``result.backward.n_iterations`` (WP-1076; the docstring said "over the
        whole series", which was true of a one-directional run and false of
        this one).  Measured on the eight-mixture round robin: 816 either way,
        against a wall clock of 33.7 s forward and 83.7 s for ``"both"``.
        """
        return sum(e.n_iterations for e in self.entries)

    def trajectory(self, path: str) -> Trajectory:
        """One parameter's trajectory across the series.

        Patterns where the path is absent are skipped rather than filled — a
        gap in a trajectory is a real thing (a phase that was not in the model
        yet, a stage that did not run) and inventing a value for it would be
        exactly the confident-wrong-singleton failure the FitReport gates
        against.
        """
        traj = Trajectory(path=path, x_label=self.x_label)
        for e, xv in zip(self.entries, self.x, strict=True):
            found = next((p for p in e.parameters if p.path == path), None)
            if found is None:
                continue
            traj.x.append(xv)
            traj.value.append(found.value)
            traj.stderr.append(found.stderr)
            traj.labels.append(e.label)
        return traj

    def paths(self, *, varied_only: bool = False) -> list[str]:
        """Every parameter path present in the series, in first-seen order.

        A :class:`~rietx.schemas.results.RefinementResult` records the
        parameters the fit *determined* — free ones and the tied ones that
        follow them (a hexagonal ``cell.b`` is not free but is every bit as
        measured as ``cell.a``), so the default keeps both.  ``varied_only``
        drops the tied ones.
        """
        out: list[str] = []
        seen: set[str] = set()
        for e in self.entries:
            for p in e.parameters:
                if varied_only and not p.vary:
                    continue
                if p.path not in seen:
                    seen.add(p.path)
                    out.append(p.path)
        return out

    def qpa_trajectory(self, phase: str) -> Trajectory:
        """A phase's weight fraction (as a percentage) across the series."""
        traj = Trajectory(path=f"qpa.{phase}", x_label=self.x_label)
        for e, xv in zip(self.entries, self.x, strict=True):
            if e.qpa is None:
                continue
            row = next((r for r in e.qpa.phases if r.name == phase), None)
            if row is None:
                continue
            traj.x.append(xv)
            traj.value.append(100.0 * row.weight_fraction)
            traj.stderr.append(None if row.weight_fraction_stderr is None
                               else 100.0 * row.weight_fraction_stderr)
            traj.labels.append(e.label)
        return traj

    def agreement_trajectory(self, phase: str, *,
                             metric: str = "r_bragg") -> Trajectory:
        """A phase's structure agreement index across the series.

        ``qpa_trajectory``'s shape, over the ``phase_agreement`` each entry now
        carries.  ``metric`` is ``"r_bragg"`` (McCusker et al. 1999 eq 14) or
        ``"r_f"`` (eq 13); a fit quotes at least one of them, and *which* is a
        reader's convention rather than something this method should choose.

        **Every ``stderr`` is ``None``, and that is a fact rather than a gap.**
        A residual is not a fitted parameter: R_Bragg has no covariance entry
        to propagate from, so unlike :meth:`trajectory` and
        :meth:`qpa_trajectory` — where a ``None`` means *this* pattern did not
        estimate one — the whole column is empty for every series. Kept as a
        ``Trajectory`` anyway so plotting and export need no second shape, and
        :meth:`Trajectory.arrays` turns it into the NaNs an errorbar ignores.

        Absent for cause outside Rietveld mode: in Le Bail the partition *is*
        the fit and in Pawley the intensities are refined, so ``refine`` leaves
        ``phase_agreement`` empty there and the trajectory is legitimately
        empty rather than zero.  Patterns missing the phase are skipped, not
        filled, for :meth:`trajectory`'s reason.
        """
        if metric not in ("r_bragg", "r_f"):
            raise ValueError(
                f"metric must be 'r_bragg' or 'r_f', got {metric!r}")
        traj = Trajectory(path=f"{metric}.{phase}", x_label=self.x_label)
        for e, xv in zip(self.entries, self.x, strict=True):
            row = next((r for r in e.phase_agreement if r.name == phase), None)
            if row is None:
                continue
            value = getattr(row, metric)
            # ``None`` only for a phase with no partitionable scattering power
            # at all — a real absence, so it is skipped like a missing phase
            # rather than carried as a hole in an otherwise aligned column.
            if value is None:
                continue
            traj.x.append(xv)
            traj.value.append(value)
            traj.stderr.append(None)
            traj.labels.append(e.label)
        return traj

    #: Prefixes :meth:`resolve_trajectory` dispatches on, longest first so a
    #: future dotted sub-namespace like ``qpa.sub.`` could not be swallowed by
    #: ``qpa.``.  The trailing dot already rules out an underscore sibling like
    #: ``qpa_x.`` — it never starts with ``qpa.`` — so the ordering guards a
    #: nested namespace, not that.
    _TRAJECTORY_PREFIXES: ClassVar[tuple[str, ...]] = (
        "r_bragg.", "r_f.", "qpa.")

    def resolve_trajectory(self, path: str) -> Trajectory:
        """The trajectory a *prefixed* path names, whichever kind it is.

        The one authority for turning a display path into a curve.  Before
        this, ``viz/plots.py`` and ``gui/series.py`` each carried their own
        copy of the same two-branch conditional, so a third kind meant editing
        both and a reader had to check they still agreed — the shape this
        repo's "one authority per fact" rule exists to remove.

        An unprefixed path is an ordinary parameter dot-path and goes to
        :meth:`trajectory`, which is what makes this safe to call
        unconditionally: ``instrument.zero_shift`` contains no prefix and
        cannot be mistaken for one.
        """
        for prefix in self._TRAJECTORY_PREFIXES:
            if path.startswith(prefix):
                name = path[len(prefix):]
                if prefix == "qpa.":
                    return self.qpa_trajectory(name)
                return self.agreement_trajectory(name,
                                                 metric=prefix.rstrip("."))
        return self.trajectory(path)

    def is_derived_path(self, path: str) -> bool:
        """Whether ``path`` names a *derived* curve rather than a refined
        parameter — a QPA or one of the McCusker agreement indices.

        The one question the two layers outside this class need to put to the
        prefix set: the GUI's forward/backward guard (a derived curve gets no
        backward chain, since ``_disagreement`` divides by a σ a residual does
        not have) and the server test that skips those rows.  They ask this
        rather than reading :attr:`_TRAJECTORY_PREFIXES`, so the tuple stays a
        private detail of the dispatch and this class stays its one authority.
        """
        return path.startswith(self._TRAJECTORY_PREFIXES)

    def agreement_phases(self) -> list[str]:
        """Phase names carrying an agreement index, in first-seen order.

        The peer of the inline QPA-phase gather in ``gui/series.py``; a series
        may report agreement for a phase that has no QPA at all, since QPA
        needs Z and a molar mass and a structure R does not.
        """
        out: list[str] = []
        for e in self.entries:
            for row in e.phase_agreement:
                if row.name not in out:
                    out.append(row.name)
        return out

    # -- tabular export ------------------------------------------------
    def to_table(self, *, paths: list[str] | None = None
                 ) -> tuple[list[str], list[list]]:
        """``(header, rows)``: one row per pattern, value + esd per parameter.

        The wide form is what gets plotted or pasted into a paper; the columns
        are ``index, label, x, status, rung, rwp, gof, <path>, <path>_esd, …``.
        ``rung`` travels beside ``status`` because it is the other half of "how
        much should I trust this point": a rescued point is a good fit whose
        starting values did not come from its neighbour, and a table that hides
        that reads as a continuous trajectory.

        **The axis column takes** :attr:`x_label`, **unless that name is
        already a column**, in which case it is ``x`` (WP-1076).  ``x_label``
        defaults to ``"index"`` — it is a human label, and it is the right axis
        title for a series with no coordinate — so before that rule the default
        header carried ``index`` twice, and anything keying by name collided
        (pandas silently renames the second to ``index.1``).  The column count,
        order and meaning are unchanged, so a consumer keying by position never
        saw it either way.
        """
        paths = self.paths() if paths is None else list(paths)
        fixed = ["index", "label", "status", "rung", "rwp", "gof"]
        x_col = "x" if self.x_label in fixed else self.x_label
        header = ["index", "label", x_col, "status", "rung", "rwp", "gof"]
        for p in paths:
            header += [p, f"{p}_esd"]
        rows: list[list] = []
        for e, xv in zip(self.entries, self.x, strict=True):
            row: list = [e.index, e.label, xv, e.status, e.rung,
                         e.statistics.rwp if e.statistics else None,
                         e.statistics.gof if e.statistics else None]
            for p in paths:
                row += [e.value(p), e.stderr(p)]
            rows.append(row)
        return header, rows

    def write_csv(self, path, *, delimiter: str | None = None,
                  paths: list[str] | None = None) -> None:
        """Write :meth:`to_table` to CSV/TSV (delimiter inferred from suffix)."""
        import csv
        from pathlib import Path as _Path

        p = _Path(path)
        if delimiter is None:
            delimiter = "\t" if p.suffix.lower() in (".tsv", ".tab") else ","
        header, rows = self.to_table(paths=paths)
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, delimiter=delimiter)
            w.writerow(header)
            for row in rows:
                w.writerow(["" if v is None else v for v in row])

    def plot(self, paths: list[str] | str, *, path=None, **kw):
        """Plot one or more trajectories against the series axis."""
        from ..viz.plots import plot_trajectory

        return plot_trajectory(self, paths, path=path, **kw)

    def __str__(self) -> str:
        return self.summary()

    def summary(self, *, max_entries: int = 5,
                deliverable: str | None = None) -> str:
        """The series termination view (WP-1302): the trajectory table, the
        ``SEQUENTIAL_*`` rows, first and last ``max_entries`` with the count.

        A per-entry ``RefinementResult.__str__`` is not repeated here — a
        60-pattern series printing 60 nested reports is not a summary — so
        this reads each entry's own :attr:`SeriesEntry.status`/``rwp`` and
        leaves the full termination view to ``result.entries[i]`` (which is
        not a ``RefinementResult`` and carries no ``__str__`` of its own for
        exactly that reason: it is the row, not the fit).

        ``deliverable="series"`` adds §4b's fourth deliverable — a parameter
        as a function of the series variable — as its deciding rows, printed
        **after** the trajectory: the table is the answer, and these are what
        would have to be wrong for it to be wrong (WP-1305).  The other three
        purposes are decided on one pattern's own fit and are refused here by
        name.
        """
        n = len(self.entries)
        lines = [f"SeriesResult: {n} pattern(s), {self.mode}, "
                 f"direction={self.direction}"]
        # the same renderer RefinementResult.__str__ calls (schemas/results.py)
        # — one diagnostics-line format for the whole package, never a second
        # copy that a future change to it would not know to keep in step with
        lines += _diagnostic_lines(self.diagnostics)
        lines.append(f"  trajectory ({self.x_label}):")
        shown = (list(range(n)) if n <= 2 * max_entries else
                [*range(max_entries), None, *range(n - max_entries, n)])
        for i in shown:
            if i is None:
                lines.append(f"    … {n - 2 * max_entries} more …")
                continue
            e = self.entries[i]
            rwp = f"{e.statistics.rwp:.4f}" if e.statistics else "n/a"
            lines.append(f"    [{i + 1}/{n}] {e.label} x={self.x[i]:g} "
                         f"{e.status} Rwp={rwp}")
        if deliverable is not None:
            lines += self._deliverable_lines(deliverable)
        return "\n".join(lines)

    def _deliverable_lines(self, deliverable: str) -> list[str]:
        """§4b's fourth deliverable: the rows that decide a trajectory.

        Four of them are diagnostics this class already carries, read as
        stopping criteria rather than as messages; the last two are the ones
        **no diagnostic can supply**, because nothing in a pattern file records
        them — what pins the 2θ scale, and which of precision and accuracy the
        esds are about.  They print as an instruction to state them, since a
        blank there is exactly how an unanchored absolute gets quoted.
        """
        if deliverable in DELIVERABLES and deliverable != "series":
            raise ValueError(
                f"{deliverable!r} is decided on one pattern's own fit, not on "
                f"a series: print it from that pattern's "
                f"Refinement.summary(deliverable={deliverable!r}) — the series' "
                f"own deliverable is 'series'")
        if deliverable != "series":
            raise ValueError(
                f"unknown deliverable {deliverable!r}; one of "
                f"{', '.join(repr(d) for d in DELIVERABLES)}")

        by_code: dict[str, list[Diagnostic]] = {}
        for d in self.diagnostics:
            by_code.setdefault(d.code, []).append(d)
        lines = ["  deliverable: series (a parameter against the series axis)"]

        depend = by_code.get("SEQUENTIAL_PATH_DEPENDENT", [])
        if self.direction == "both":
            paths = ", ".join(p for d in depend for p in d.where) or "none"
            lines.append(f"    ordering artefact: measured both ways, "
                         f"{len(depend)} parameter(s) disagree ({paths})")
        else:
            lines.append(f"    ordering artefact: NOT measured — this chain ran "
                         f"{self.direction} only, and direction='both' is the "
                         f"one check that separates a trajectory from the order "
                         f"it was refined in")

        persistent = by_code.get("SEQUENTIAL_PERSISTENT_FINDING", [])
        lines.append(f"    persistent findings: {len(persistent)}")
        for d in persistent[:5]:
            lines.append(f"      {d.message}")

        steps = by_code.get("SEQUENTIAL_DISCONTINUITY", [])
        lines.append(f"    steps: {len(steps)}")
        for d in steps:
            where = ", ".join(d.where)
            verdict = ("not verified — fit(verify_discontinuities=True) refits "
                       "both patterns cold" if d.value is None else
                       f"an independent cold pair reproduces {d.value:.2f}× of it")
            lines.append(f"      {where}: {verdict}")

        held = sorted({p for e in self.entries for d in e.diagnostics
                       if d.code == "PHASE_UNCONSTRAINED" for p in d.where})
        n_held = sum(any(d.code == "PHASE_UNCONSTRAINED" for d in e.diagnostics)
                     for e in self.entries)
        if held:
            lines.append(f"    phase support: held in {n_held} of "
                         f"{len(self.entries)} patterns ({', '.join(held[:4])}"
                         f"{' …' if len(held) > 4 else ''}) — a held value is "
                         f"the one you handed in, not a measurement, so it is "
                         f"not a point on a trajectory either")
        else:
            lines.append("    phase support: every phase carried the data in "
                         "every pattern (no PHASE_UNCONSTRAINED)")

        lines.append("    2θ-scale anchor: state it — an internal standard, a "
                     "calibrant, or none. Nothing in this result knows")
        lines.append("    precision vs accuracy: the esds are precision on the "
                     "*shape*; without an anchor there is no accuracy claim on "
                     "the absolute")
        lines.append("    good enough: when every number you quote names the "
                     "one thing that would have to be wrong for it to be wrong, "
                     "and that thing has been checked")
        return lines
