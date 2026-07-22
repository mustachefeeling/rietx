"""The public refinement API: :class:`Refinement` and :func:`refine`."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import numpy as np

from .model.forward import CompiledModel, Mode, compile_model
from .optimize.least_squares import run_least_squares
from .optimize.statistics import compute_statistics
from .params.vector import ParameterTable
from .schemas.common import Diagnostic, Provenance
from .schemas.instrument import Instrument
from .schemas.pattern import PatternData
from .schemas.results import RefinedParameter, RefinementResult, StageResult
from .schemas.structure import Structure
from .strategy.staged import PLAN_PRESETS, RefinementPlan, check_guards

try:
    _VERSION = version("pxrd-refine")
except PackageNotFoundError:  # editable/dev fallback
    _VERSION = "0.0.0+dev"


class Refinement:
    """Refine ``structure`` + ``instrument`` against a powder pattern.

    The input models are deep-copied; refined values are exposed on
    ``fitted_structure`` / ``fitted_instrument`` after :meth:`fit`.
    """

    def __init__(self, structure: Structure, instrument: Instrument, *,
                 backend: str = "numpy"):
        if backend != "numpy":
            raise NotImplementedError("v0.1 ships the numpy backend only")
        self.structure = structure.model_copy(deep=True)
        self.instrument = instrument.model_copy(deep=True)
        self.result_: RefinementResult | None = None
        self._model: CompiledModel | None = None

    # ------------------------------------------------------------------
    def fit(self, data: PatternData, *, mode: Mode = "rietveld",
            plan: RefinementPlan | str = "mccusker_default",
            two_theta_limits: tuple[float, float] | None = None) -> RefinementResult:
        if isinstance(plan, str):
            if mode == "lebail" and plan == "mccusker_default":
                plan = "profile_only"
            try:
                plan = PLAN_PRESETS[plan]()
            except KeyError:
                raise ValueError(
                    f"unknown plan preset {plan!r}; available: {sorted(PLAN_PRESETS)}"
                ) from None

        table = ParameterTable(self.structure, self.instrument)
        # stages are cumulative: start from everything the user left vary=True…
        # …but the staged plan drives the turn-on sequence explicitly:
        table.set_vary(["*"], False)

        diagnostics: list[Diagnostic] = []
        stage_results: list[StageResult] = []
        outcome = None
        model = None

        for stage in plan.stages:
            freed = table.set_vary(stage.turn_on, True)
            if mode == "lebail":
                # never refine structural parameters (or the line-intensity
                # ratio, which the per-hkl intensities can absorb pairwise)
                # against empirical intensities
                for path in list(freed):
                    if ".atoms." in path or path.endswith(".scale") \
                            or ".source.lines." in path:
                        table.set_vary([path], False)

            # regenerate reflection list/windows/FCJ nodes with current values
            # (between-stage refresh; frozen within the stage); the free-path
            # set lets the compiler allocate FCJ nodes for axial parameters
            # that are about to refine from zero
            table.apply_to_models(self.structure, self.instrument)
            new_model = compile_model(self.structure, self.instrument, data, mode=mode,
                                      two_theta_limits=two_theta_limits,
                                      free_paths=set(table.free_paths))
            if model is not None and mode == "lebail" and model.mode == "lebail":
                _carry_lebail(model, new_model)
            model = new_model

            if mode == "lebail":
                values = table.decode(table.x0())
                model.lebail_update(values, n_cycles=stage.lebail_cycles)

            outcome = run_least_squares(model, table, max_iter=stage.max_iter)
            table.commit(outcome.theta)

            if mode == "lebail":
                model.lebail_update(table.decode(outcome.theta), n_cycles=stage.lebail_cycles)

            guard = check_guards(table, outcome, plan.correlation_guard)
            for msg in guard.high_correlations:
                diagnostics.append(Diagnostic(
                    level="warning", code="HIGH_CORRELATION", message=msg,
                    suggestion="consider fixing one of the correlated parameters",
                ))
            for path in guard.at_bounds:
                diagnostics.append(Diagnostic(
                    level="warning", code="BOUND_HIT", where=[path],
                    message=f"{path} refined to its bound",
                    suggestion="widen the bound or fix the parameter",
                ))
            stage_results.append(StageResult(
                name=stage.name, status=outcome.status, n_iterations=outcome.n_iterations,
                cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
                freed=freed,
            ))

        assert model is not None and outcome is not None
        self._model = model
        table.apply_to_models(self.structure, self.instrument)

        values = table.decode(outcome.theta)
        y_calc = model.evaluate(values)
        y_bkg = model.background(values)
        stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                                   n_free=len(table.free_paths), y_background=y_bkg)

        stderr_phys = (table.stderr_physical(outcome.theta, outcome.stderr_internal)
                       if outcome.stderr_internal is not None else {})
        params = []
        for e in table.entries:
            if e.vary or e.tied_to is not None:
                params.append(RefinedParameter(
                    path=e.path, value=e.value, vary=e.vary,
                    stderr=stderr_phys.get(e.path),
                ))

        ticks = {}
        for ip, cp in enumerate(model.phases):
            name = self.structure.phases[ip].name
            cell = tuple(values[f"phases.{ip}.cell.{k}"]
                         for k in ("a", "b", "c", "alpha", "beta", "gamma"))
            pos = cp.reflections.two_theta(cell, model.wavelength) + values["instrument.zero_shift"]
            ticks[name] = [float(p) for p in pos if np.isfinite(p)]

        self.result_ = RefinementResult(
            status=outcome.status, mode=mode,
            parameters=params, statistics=stats,
            stages=stage_results, diagnostics=diagnostics,
            provenance=Provenance(package_version=_VERSION),
            two_theta=model.tt.tolist(), y_obs=model.y_obs.tolist(),
            y_calc=y_calc.tolist(), y_background=y_bkg.tolist(),
            ticks=ticks,
        )
        return self.result_

    # ------------------------------------------------------------------
    def predict(self, two_theta=None) -> np.ndarray:
        """y_calc at the fitted parameters (on the fit grid)."""
        if self._model is None or self.result_ is None:
            raise RuntimeError("call fit() first")
        if two_theta is not None:
            raise NotImplementedError("arbitrary-grid prediction lands with v0.2")
        table = ParameterTable(self.structure, self.instrument)
        return self._model.evaluate(table.decode(table.x0()))

    @property
    def fitted_structure(self) -> Structure:
        return self.structure

    @property
    def fitted_instrument(self) -> Instrument:
        return self.instrument


def _carry_lebail(old, new) -> None:
    """Carry extracted intensities across a stage recompile (match by hkl)."""
    for cp_old, cp_new in zip(old.phases, new.phases, strict=True):
        if cp_old.lebail_intensity is None:
            continue
        lookup = {tuple(h): i for i, h in enumerate(map(tuple, cp_old.reflections.hkl))}
        carried = cp_new.lebail_intensity
        for i, h in enumerate(map(tuple, cp_new.reflections.hkl)):
            j = lookup.get(h)
            if j is not None:
                carried[i] = cp_old.lebail_intensity[j]


def refine(data: PatternData, structure: Structure, instrument: Instrument,
           *, mode: Mode = "rietveld", plan: RefinementPlan | str = "mccusker_default",
           two_theta_limits: tuple[float, float] | None = None) -> RefinementResult:
    """One-shot functional API: ``refine(data, structure, instrument)``."""
    ref = Refinement(structure, instrument)
    return ref.fit(data, mode=mode, plan=plan, two_theta_limits=two_theta_limits)
