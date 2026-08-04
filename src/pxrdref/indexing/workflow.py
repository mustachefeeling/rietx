""":func:`index_pattern` — the public entry point — and the whole-profile
validation it drives.

``index_pattern`` runs the engines, deduplicates their candidates as reduced
cells, enumerates geometrical ambiguities, validates the survivors by a Le Bail
fit, and gates confidence on **agreement**.  Its API cannot express a confident
wrong singleton: it returns an
:class:`~pxrdref.schemas.indexing.IndexingResult`, which has no ``.cell``, and the
only route to one cell is ``best_or_none()``.

The rest of this module is that validation step, and it exists because the
figure-of-merit panel is computed on ≤20 lines and is structurally blind to three
things the whole pattern sees — the third being the one no figure of merit can be
patched to see:

1. **lines beyond the panel** — a cell can index the first twenty and fail from
   twenty-one;
2. **impurity content** — observed peaks with nothing calculated near them;
3. **reflections predicted where there is no intensity** — the classic
   doubled/oversized-cell false positive.  M₂₀ penalises it only through its
   ``N_poss`` denominator, which is Oishi-Tomiyasu's (2013) critique of the de
   Wolff figure, and both source papers on autoindexing (Bergmann *et al.* 2004;
   Altomare *et al.* 2019) close on whole-profile validation for exactly this
   reason.

So validation is **mandatory, not an option**: with no pattern every candidate
caps at ``"medium"`` and ``INDEX_NOT_VALIDATED`` fires — the *result* abstains
rather than one field being quietly downgraded.

**The plan's detector for (3) was measured wrong, and the replacement is
measured.**  WP-1024's plan named Layer 0's ``unmatched_calc`` — its
strong-negative-residual count — as ``predicted_but_absent``.  It cannot serve,
and the reason is structural rather than a threshold: Le Bail extraction sets each
reflection's intensity from ``max(y_obs − y_bkg, 0)``, so a reflection predicted
where there is nothing is assigned ~nothing and produces **no negative residual
to detect**.  What the detector then finds is 5σ noise excursions that happen to
sit near a tick.  Measured on a synthetic LaB₆ pattern (Poisson noise, 15-145° 2θ
at 0.02°, the protocol ``tests/test_indexing_consensus.py`` pins),
``unmatched_calc`` fired on **17 of the certified cell's own 28 reflections** and
on 94 of a doubled cell's 153 — 61 % either way, so it does not separate them at
all.  :func:`absent_reflections` asks the question directly instead — is there net
intensity above the *fitted* background at this position? — and separates them
cleanly: 0 of 28 against 117 of 153.

**The two detectors and ``lebail_rwp`` catch different failures, which is why all
three are reported.**  Same measurement, four cells:

| candidate | Rwp | predicted_but_absent | unmatched_observed |
|---|---|---|---|
| truth | 0.216 | 0/28 | 0 |
| doubled cell | 0.379 | **117/153** | 0 |
| a·√5 supercell | 0.957 | 27/204 | 4 |
| metric 1 % off | 0.984 | 0/30 | **95** |

Read the table by column.  Rwp is decisive on a *wrong metric* (0.98 against 0.22)
and nearly silent on an *oversized* one (0.379 — well under twice the truth's, and
on real data a gap that size is inside the spread between specimens); the oversized
cell is caught only by column three.  A wrong metric is caught from the other side
by column four, where 95 observed peaks have no calculated reflection.  The a·√5
row is the useful reminder that these overlap: its fit is already refuted by Rwp,
so its low absent *fraction* costs nothing — a badly-fitted background is what
makes that count unreliable, and a badly-fitted background comes with an Rwp that
says so.

``lebail_rwp`` is the figure the literature names; it is **not** a member of the
ranking panel.  The panel ranks every candidate and this costs a refinement, so
it is computed for the shortlist only — and ranking on it would reintroduce the
blind spot validation exists to close, since a bigger cell with more free
intensities fits better.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import CellCandidate, LeBailValidation, PeakList
from ..schemas.instrument import Instrument
from ..schemas.pattern import PatternData
from ..schemas.structure import Atom, Cell, Parameter, Phase, Structure
from .fom import lattice_group

#: Multiples of the window's propagated σ the net intensity must reach for a
#: predicted reflection to count as **present**.  Three, the same 99.7 % window
#: :data:`~pxrdref.indexing.fom.MATCH_SIGMA` uses on positions, so one number
#: means one thing across the package.
#:
#: **Its failure mode is on a correct cell and is worth knowing before you read a
#: count.**  A genuinely weak reflection — a space-group extinction that is not
#: yet known to be one (the extinction screen runs after this and asks the same
#: question with a different null model), or a high-angle line the counting time
#: did not reach — is absent for reasons that have nothing to do with the lattice, and
#: this test cannot tell it from an oversized cell's phantom.  That is
#: ``predicted_seen_fraction``'s documented blind spot one level down, and it is
#: why the 2θ of every flagged reflection travels with the count: a caller can
#: look at the pattern, which no threshold can do for them.
ABSENT_SIGMA = 3.0
#: Half-width of the integration window, in predicted FWHM.  Half a FWHM rather
#: than a whole one: the question is whether there is intensity *at the position*,
#: and a wider window on a dense supercell would collect a neighbour's tail and
#: report a phantom reflection as present.
ABSENT_WINDOW_FWHM = 0.5
#: Species of the mandatory dummy atom.  Carbon because its K edge (284 eV) is
#: nowhere near any laboratory or ordinary synchrotron wavelength, so
#: ``dispersion.resolve`` — on by default since v1.0 — can never refuse it, and
#: because the choice is inert: ``_run_stage`` force-fixes every ``.atoms.`` path
#: in lebail mode, so the atom sets the *starting* per-hkl intensities and nothing
#: else.
DUMMY_SPECIES = "C"


def structure_from_candidate(candidate: CellCandidate, *,
                             space_group: str | None = None,
                             name: str = "candidate") -> Structure:
    """A single-phase :class:`Structure` for Le Bail validation of a cell.

    **Two footguns, both load-bearing, both here rather than in a comment at the
    call site.**

    *One: the dummy atom is mandatory.*  ``Phase._nonempty`` raises on an empty
    atom list, and a candidate cell has no structure — that is the entire point of
    indexing.  So a Le Bail-only phase carries one atom that contributes nothing:
    ``_run_stage`` force-fixes every ``.atoms.`` path, ``.scale`` and
    ``.source.lines.`` in lebail/pawley mode, which is also what keeps the
    parameter surface (WP-1004) from showing it as editable — it is reported
    ``mode_fixed``, not ``locked``.

    *Two: ``space_group`` defaults to the absence-free lattice group*, never to a
    plausible-looking space group.  The default is the highest-symmetry group of
    the lattice with **no extra absences** (``P m -3 m``, ``P 4/m m m``,
    ``P 6/m m m``, ``P -3 m 1``, ``P m m m``, ``P 1 2/m 1``, ``P -1``, plus the
    centring), so validation tests the **lattice** — which is the only thing that
    has been determined.  A group carrying reflection conditions would hide
    exactly the reflections whose absence is not yet established, and hiding them
    is how an oversized cell passes: every phantom it predicts would be excused as
    an extinction.

    The real conditions are determined afterwards by
    :func:`pxrdref.indexing.extinction.determine_extinction_symbol`, which passes
    a class's representative in here as ``space_group`` — but the *validation*
    call above it must keep using the default, or the gate loses the detector.
    """
    symbol = space_group or candidate.lattice_group or lattice_group(
        candidate.system, candidate.centring)
    a, b, c, alpha, beta, gamma = candidate.cell
    return Structure(phases=[Phase(
        name=name, space_group=symbol,
        cell=Cell(a=Parameter(value=a, min=0.1), b=Parameter(value=b, min=0.1),
                  c=Parameter(value=c, min=0.1),
                  alpha=Parameter(value=alpha), beta=Parameter(value=beta),
                  gamma=Parameter(value=gamma)),
        atoms=[Atom(label="X", species=DUMMY_SPECIES,
                    x=Parameter(value=0.0), y=Parameter(value=0.0),
                    z=Parameter(value=0.0))])])


def absent_reflections(two_theta: np.ndarray, y_obs: np.ndarray,
                       y_background: np.ndarray, sigma: np.ndarray,
                       positions: np.ndarray, fwhm: np.ndarray, *,
                       k_sigma: float = ABSENT_SIGMA,
                       ) -> tuple[list[float], list[float]]:
    """Predicted positions with no net intensity above the **fitted** background.

    Returns ``(two_theta, net_over_sigma)`` for the reflections that failed.
    Integrates ``y_obs − y_background`` over ±:data:`ABSENT_WINDOW_FWHM` FWHM and
    compares the sum with the propagated σ of the same channels — so the test is
    "the pattern has nothing here", measured against the noise the pattern
    actually carries rather than against a fraction of the strongest peak.

    The *fitted* background is what makes this better than the same question
    asked of the peak list: a Le Bail fit has co-refined it under the P-spline or
    Chebyshev model, so a sloping background is not mistaken for intensity.  The
    same fact is the test's limit — a badly-fitted background makes the count
    unreliable, which is why the module docstring reads the count beside Rwp
    rather than alone.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    net = np.asarray(y_obs, dtype=np.float64) - np.asarray(y_background,
                                                           dtype=np.float64)
    sig = np.asarray(sigma, dtype=np.float64)
    pos_bad: list[float] = []
    ratio_bad: list[float] = []
    for pos, width in zip(np.asarray(positions, dtype=np.float64),
                          np.asarray(fwhm, dtype=np.float64)):
        inside = np.abs(tt - pos) <= ABSENT_WINDOW_FWHM * max(float(width), 1e-6)
        if not np.any(inside):
            continue                     # outside the fitted range: not evidence
        total = float(net[inside].sum())
        noise = float(np.sqrt((sig[inside] ** 2).sum()))
        if total < k_sigma * noise:
            pos_bad.append(float(pos))
            ratio_bad.append(total / max(noise, 1e-300))
    return pos_bad, ratio_bad


def _shift_path(candidate: CellCandidate, instrument: Instrument) -> str:
    """The one peak-position parameter the validation fit frees.

    **One, not three.**  The three templates are collinear over a limited 2θ
    range — that is what ``quality.fit_shift_model`` refuses to resolve and what
    Layer 1 measured one rank down (a joint fit of collinear templates reported a
    0.02° zero-point error as 1.8°) — so freeing more than one here would put two
    columns with ρ ≈ 1 into the same solve.

    Which one comes from the candidate's *own* declared template, translated
    through ``diagnostics.SHIFT_CAUSE``'s mapping: one physical cause, one name,
    package-wide.  A ``cos_theta`` candidate names the specimen displacement,
    which is live only in ``bragg_brentano`` geometry — on a capillary only
    ``zero_shift`` moves the peaks at all, so the request falls back to it rather
    than freeing a parameter with no gradient.
    """
    by_template = {
        "constant": "instrument.zero_shift",
        "cos_theta": "instrument.geometry.sample_displacement",
        "sin_2theta": "instrument.geometry.sample_transparency",
    }
    path = by_template.get(candidate.shift_template or "constant",
                           "instrument.zero_shift")
    if (path != "instrument.zero_shift"
            and instrument.geometry.kind != "bragg_brentano"):
        return "instrument.zero_shift"
    return path


def validation_plan(candidate: CellCandidate, instrument: Instrument):
    """The staged plan a Le Bail validation runs, and what it deliberately omits.

    **The cell is held.**  ``profile_only`` — the ordinary Le Bail plan — frees
    ``phases.*.cell.*``, and it must not here: the candidate *is* the hypothesis
    under test, and letting it walk means validating a different cell from the one
    the result reports.  A candidate whose metric is slightly wrong is supposed to
    validate badly; that is the measurement.

    What is freed: the background (a candidate cannot be judged against a
    background nobody fitted), exactly one peak-position parameter
    (:func:`_shift_path`), and then the widths in the ``profile_only`` order —
    ``w`` alone before ``u``/``v``/``x``/``y``, because ``w`` is the only width
    term that is non-zero at 2θ = 0 and freeing the four together from a
    mis-declared instrument is what the staged order exists to prevent.
    """
    from ..strategy.staged import RefinementPlan, Stage

    return RefinementPlan(stages=[
        Stage("bkg", ["instrument.background.*"]),
        Stage("shift", [_shift_path(candidate, instrument)]),
        Stage("profile_w", ["instrument.profile.w"]),
        Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                          "instrument.profile.x", "instrument.profile.y"]),
    ])


def seed_widths(instrument: Instrument, peaks: PeakList) -> tuple[Instrument, bool]:
    """Put the instrument's Gaussian ``w`` on the peak list's measured width.

    Returns ``(instrument, seeded)``; the input is never mutated.

    Only when the declared instrument is *inconsistent* with the data, judged by
    the same ``WIDTH_MISMATCH_RATIO`` the ``PEAK_WIDTH_LAW_MISMATCH`` diagnostic
    uses — so a calibrated instrument is left exactly as declared and the
    ``ProfileTCHZ`` default (``W = 1e-3 deg²``, FWHM ≈ 0.03°, a *synchrotron*
    line, which lands near a factor 13 on lab data) does not make every candidate
    validate badly for a reason that has nothing to do with its cell.

    ``w`` is a Gaussian *variance* in deg²(2θ), so the seed is the measured FWHM
    squared: with ``u = v = 0`` the Caglioti law gives Γ_G = √w.  It is a seed and
    the plan's first width stage refines it.
    """
    from .diagnostics import WIDTH_MISMATCH_RATIO
    from .peaks import predicted_fwhm

    usable = peaks.usable()
    if not usable:
        return instrument, False
    measured = float(np.median([p.fwhm for p in usable]))
    tt = np.array([p.two_theta for p in usable], dtype=np.float64)
    predicted = float(np.median(predicted_fwhm(tt, instrument)))
    if predicted <= 0.0:
        return instrument, False
    ratio = measured / predicted
    if 1.0 / WIDTH_MISMATCH_RATIO < ratio < WIDTH_MISMATCH_RATIO:
        return instrument, False
    out = instrument.model_copy(deep=True)
    out.profile.w.value = float(measured ** 2)
    return out, True


def validate_by_lebail(candidate: CellCandidate, data: PatternData,
                       instrument: Instrument, *,
                       peaks: PeakList | None = None,
                       space_group: str | None = None,
                       two_theta_limits: tuple[float, float] | None = None,
                       k_sigma: float = ABSENT_SIGMA,
                       cancel=None) -> LeBailValidation:
    """Fit ``candidate`` to the whole pattern by Le Bail and report the three
    detectors.

    Single-phase by construction, and that is a measured constraint rather than a
    simplification: ``CompiledModel.lebail_update`` partitions
    ``max(y_obs − y_bkg, 0)`` per phase with nothing to arbitrate two phases
    claiming the same channel, so two phases inflate one another without bound
    (WP-1028, measured Rwp 742-9 281 % against 7.5-24.8 % for one phase, and it
    survives seeding both the widths and the background — so it is the partition,
    not the starting point).  A candidate is never validated against a
    multi-phase hypothesis.

    A fit that *raises* comes back as ``status="failed"`` with an infinite Rwp
    rather than as an exception: a candidate the physics refuses is evidence
    about the candidate, and the gate reads it as such (the ``validation_failed``
    caveat), where a traceback would abandon every other candidate with it.

    **Except a cancellation, which is evidence about nothing** (WP-1037).
    ``cancel`` may be the caller's token or ``index_pattern``'s whole-run
    :class:`~pxrdref.indexing.engines.Deadline`; either way the fit it stops is
    a fit that *ran out of time*, and letting ``RefinementCancelled`` fall into
    the generic handler would hand the gate a ``validation_failed`` — a
    **refuting** caveat — for a cell the run merely could not afford to check.
    So it re-raises, the caller stops the loop, and the candidate keeps
    ``lebail = None``, which reads as ``not_validated`` (capping): the honest
    state, and the same one an unreached candidate was always in.
    """
    from ..optimize.cancel import RefinementCancelled
    from ..refine import Refinement
    from ..report.layer0 import build_layer0
    from .peaks import predicted_fwhm

    structure = structure_from_candidate(candidate, space_group=space_group)
    symbol = structure.phases[0].space_group
    ins = instrument
    if peaks is not None:
        ins, _seeded = seed_widths(ins, peaks)
    plan = validation_plan(candidate, ins)

    ref = Refinement(structure, ins, history=False)
    try:
        result = ref.fit(data, mode="lebail", plan=plan,
                         two_theta_limits=two_theta_limits, cancel=cancel)
    except RefinementCancelled:
        raise                       # before the generic handler — see docstring
    except Exception as exc:                        # noqa: BLE001
        return LeBailValidation(
            rwp=float("inf"), gof=float("inf"), space_group=symbol,
            n_reflections=0, status="failed",
            diagnostics=[Diagnostic(
                level="warning", code="INDEX_VALIDATION_FAILED",
                message=(f"the Le Bail validation of {candidate.system} "
                         f"{symbol} raised {type(exc).__name__}: {exc}"),
                where=[f"cell {candidate.cell}"],
                suggestion=("this is evidence about the candidate, not about the "
                            "search — but check the instrument first: a "
                            "mis-declared profile or a wavelength on an "
                            "absorption edge fails for every candidate alike"))])

    rows = [r for r in ref.reflection_table() if r.line == 0]
    positions = np.array([r.two_theta for r in rows], dtype=np.float64)
    absent_tt, _ratio = absent_reflections(
        np.asarray(result.two_theta), np.asarray(result.y_obs),
        np.asarray(result.y_background), np.asarray(result.sigma),
        positions, predicted_fwhm(positions, ref.fitted_instrument),
        k_sigma=k_sigma) if len(positions) else ([], [])

    layer0 = build_layer0(result)
    unmatched = [u.two_theta for u in layer0.unmatched
                 if u.kind == "unmatched_obs"]
    return LeBailValidation(
        rwp=float(result.statistics.rwp), gof=float(result.statistics.gof),
        space_group=symbol, n_reflections=len(rows),
        predicted_but_absent=len(absent_tt),
        unmatched_observed=len(unmatched),
        predicted_but_absent_two_theta=[round(v, 4) for v in absent_tt],
        unmatched_observed_two_theta=[round(float(v), 4) for v in unmatched],
        status=result.status, n_stages=len(result.stages))


# ----------------------------------------------------------------------
# the entry point
# ----------------------------------------------------------------------
def _pair_shift_diagnostics(quality) -> list[Diagnostic]:
    """``INDEX_SHIFT_FROM_PAIRS``, when the pair screen actually measured one."""
    from .engines import shift_from_pairs_diagnostic

    shift = getattr(quality, "shift", None)
    if shift is None or shift.source != "reflection_pairs" or shift.pairs is None:
        return []
    return [shift_from_pairs_diagnostic(shift)]


def _adopt_measured_shift(spec, quality):
    """Adopt a pair-measured shift *template* into the spec, when it is safe to name.

    Measuring the shift's **magnitude** and naming its **cause** are separate
    permissions, and this function is where the second one is refused.  The
    magnitude reaches the search through ``effective_sigma_sys`` and needs no
    template; adopting a template additionally tells ``refine_with_shift`` which
    *shape* to fit once a candidate survives, and fitting the wrong shape biases
    the cell it corrects.

    So adoption requires the cause to be safe to name — ``separable``, or the
    competitive templates disagreeing, over the angles actually sampled, by less
    than the list's own median σ.  **Measured (WP-1038), that is rare and the
    refusal is the common case**: on corundum the two collinear templates predict
    corrections differing by 0.0505° against a median σ of 0.0056°, because cos θ
    runs from ~1 to ~0.26 across 5-150° while a constant does not.  A caller who
    knows the cause declares ``spec.shift_template`` and is never overridden here.

    **Clearing the caveat without adopting a template would be the trap.**  A cell
    found inside a widened window has absorbed the shift — +1400 ppm, measured on
    corundum — so when nothing is adopted the run keeps saying so.
    """
    from ..schemas.indexing import TRUSTED_SHIFT_SOURCES

    shift = getattr(quality, "shift", None)
    if (spec.shift_template is not None or shift is None
            or shift.source not in TRUSTED_SHIFT_SOURCES or shift.best is None):
        return spec
    median_sigma = float(getattr(quality, "sigma_two_theta_median", 0.0) or 0.0)
    nameable = bool(shift.separable
                    or (shift.prediction_spread_deg <= median_sigma
                        and median_sigma > 0.0))
    if not nameable:
        return spec
    return replace(spec, shift_template=shift.best)


def index_pattern(peaks: PeakList | None = None, *,
                  data: PatternData | None = None,
                  instrument: Instrument | None = None,
                  spec=None,
                  engines: Sequence[str] | None = None,
                  quality=None,
                  shift_from_pairs: bool = True,
                  validate: bool = True,
                  check_top: int | None = None,
                  two_theta_limits: tuple[float, float] | None = None,
                  events=None, cancel=None):
    """Find the unit cell — or say, in the shape of the answer, that it cannot.

    Give it a :class:`~pxrdref.schemas.indexing.PeakList`, or a ``data`` +
    ``instrument`` pair it will pick peaks from.  Supplying ``data`` is what turns
    whole-profile validation on: without a pattern every candidate caps at
    ``"medium"`` and ``INDEX_NOT_VALIDATED`` fires, because the figure-of-merit
    panel is blind to three things only the profile shows
    (:func:`validate_by_lebail`).

    ``engines`` names which searches to run, from the **live registry**
    (``engines.engine_names()``); the default is all of them, and that default is
    the one to keep — ``high`` confidence *means* every engine that ran found the
    same lattice, so restricting the list narrows what the answer can say.

    ``cancel`` is WP-1006's :class:`~pxrdref.optimize.cancel.CancelToken` and works
    here unchanged: the check is cooperative, read between units of search work, so
    it needs no stages, no Rwp and no history node.  A cancelled search returns
    what it has rather than raising — an indexing run has nothing to abandon,
    unlike a seeding refinement stage.

    ``spec.total_budget_seconds`` (WP-1037) is the whole-run ceiling — search,
    probe *and* validation, where ``budget_seconds`` is one (engine × system)
    slice.  It is enforced as a :class:`~pxrdref.indexing.engines.Deadline`,
    a clock shaped as a cancel token, so it nests under every cooperative
    check above with no engine changes and the run still returns a complete
    :class:`~pxrdref.schemas.indexing.IndexingResult` over what was reached.
    ``systems_searched`` then distinguishes three states — a system searched to
    completion (``search_complete`` true), one truncated mid-search (false),
    and one never reached (absent) — and ``INDEX_BUDGET_EXHAUSTED`` names them.
    ``estimate_ceiling`` is the pre-run arithmetic for choosing the value.

    **Abstention is checked before any budget is spent.**  A peak list that cannot
    support a search comes back with the candidates empty and
    ``INDEX_DATA_INSUFFICIENT`` from the quality gate, never as an exception and
    never as a ranked list with nothing behind it.
    """
    from ..history.events import as_event_stream
    from ..optimize.cancel import RefinementCancelled
    from ..refine import _VERSION, _utcnow
    from ..report.schemas import THRESHOLDS_VERSION
    from ..schemas.common import Provenance
    from ..schemas.indexing import IndexingResult
    from .consensus import CONSENSUS_CHECK_TOP, apply_gate, checked_indices, consensus
    from .diagnostics import candidate_diagnostics, index_diagnostics
    from .engines import (
        SYSTEM_ORDER,
        Deadline,
        Progress,
        SearchSpec,
        budget_exhausted_diagnostic,
        engine_names,
        get_engine,
    )
    from .pick import pick_peaks
    from .quality import assess_peak_list

    if peaks is None:
        if data is None or instrument is None:
            raise ValueError(
                "index_pattern needs a PeakList, or a data= + instrument= pair to "
                "pick one from; it cannot index a pattern whose wavelength and "
                "profile it does not know")
        peaks = pick_peaks(data, instrument)
    spec = spec or SearchSpec()
    if quality is None:
        quality = assess_peak_list(peaks, shift_from_pairs=shift_from_pairs,
                                   pair_seed=spec.seed)
    spec = _adopt_measured_shift(spec, quality)
    names = tuple(engines) if engines is not None else engine_names()
    top = CONSENSUS_CHECK_TOP if check_top is None else check_top

    # the whole-run clock, if one was declared: a Deadline both *is* the token
    # every cooperative check reads (so it binds the engines, the probe and the
    # validation fits alike) and *carries* the caller's own token, so either
    # stops the run and cancelled_by_user() says which did
    deadline = None
    run_cancel = cancel
    if spec.total_budget_seconds is not None:
        deadline = Deadline(spec.total_budget_seconds, cancel=cancel)
        run_cancel = deadline

    provenance = Provenance(
        package_version=_VERSION, created_utc=_utcnow(),
        report_thresholds_version=THRESHOLDS_VERSION,
        notes=_spec_notes(spec, names, quality))
    stream = as_event_stream(events)
    if stream is not None:
        extra = ({"total_budget_seconds": float(spec.total_budget_seconds)}
                 if spec.total_budget_seconds is not None else {})
        stream.emit("index_start", engines=list(names),
                    systems=[s for s in spec.systems],
                    n_usable_lines=len(peaks.usable()),
                    wavelength=peaks.wavelength,
                    supports_indexing=quality.supports_indexing, **extra)
    # one flat ladder over everything the run does (WP-1037): a search unit per
    # (engine × system), plus probe and validation units add()-ed when their
    # counts become known — never a second per-engine ladder beside it, which
    # is what made a progress bar jump (two writers, one ``n_stages``)
    n_systems = len([s for s in SYSTEM_ORDER if s in spec.systems])
    progress = Progress(stream, total=len(names) * n_systems)

    if not quality.supports_indexing:
        # abstention *is* the result: the gate has already decided the data cannot
        # support a search, and running one anyway returns a rank order with
        # nothing behind it
        result = IndexingResult(
            engines_run=[], systems_searched=[], quality=quality,
            wavelength=peaks.wavelength, n_usable_lines=len(peaks.usable()),
            validated=False, provenance=provenance,
            diagnostics=list(quality.diagnostics))
        out = result.model_copy(update={
            "diagnostics": list(result.diagnostics)
            + index_diagnostics(result, instrument)})
        _emit_end(stream, out)
        return out

    results = []
    for name in names:
        # per-(engine × system) progress is emitted by the engines themselves
        # through ``progress`` — the per-engine stage pair that used to sit
        # here is *replaced*, not nested (WP-1037's trap 2)
        if run_cancel is not None and bool(run_cancel):
            break
        engine_result = get_engine(name)(peaks, spec=spec, quality=quality,
                                         cancel=run_cancel, progress=progress)
        results.append(engine_result)

    outcome = consensus(results, peaks, spec=spec, quality=quality, top=top,
                        cancel=run_cancel)
    checked = checked_indices(outcome.candidates, outcome.engines_run, top=top)
    validated = False
    if validate and data is not None and instrument is not None:
        progress.add(len(checked))
        for i in checked:
            if run_cancel is not None and bool(run_cancel):
                break
            cand = outcome.candidates[i]
            label = f"validate:{cand.system} {cand.centring}"
            progress.start(label, system=cand.system, validation=True)
            try:
                cand.lebail = validate_by_lebail(
                    cand, data, instrument, peaks=peaks,
                    two_theta_limits=two_theta_limits, cancel=run_cancel)
            except RefinementCancelled:
                # a truncated fit is not evidence about the candidate: leave
                # ``lebail = None`` (reads ``not_validated``, capping) and stop
                progress.end(label, validation=True, status="cancelled")
                break
            progress.end(label, validation=True, status=cand.lebail.status)
        validated = True

    if deadline is not None and deadline.expired() \
            and not deadline.cancelled_by_user():
        requested = [s for s in SYSTEM_ORDER if s in spec.systems]
        outcome.diagnostics.append(budget_exhausted_diagnostic(
            float(spec.total_budget_seconds),
            engines_not_run=[n for n in names if n not in outcome.engines_run],
            systems_truncated=[s for s, ok in outcome.search_complete.items()
                               if not ok],
            systems_not_reached=[s for s in requested
                                 if s not in outcome.systems_searched],
            candidates_not_validated=sum(
                1 for i in checked if outcome.candidates[i].lebail is None)
            if validated else 0))

    # the gate's ``checked`` is what the enumeration actually covered, not what
    # was scheduled: under a fired token the two differ, and a candidate whose
    # ambiguity question was never asked must not read as answered (WP-1037)
    apply_gate(outcome.candidates, engines_run=outcome.engines_run,
               panel_disagrees=outcome.fom_panel_disagrees, validated=validated,
               search_complete=outcome.search_complete,
               shift_allowance_assumed=outcome.shift_allowance_assumed,
               checked=outcome.ambiguity_checked, quality=quality)
    for cand in outcome.candidates:
        cand.diagnostics = list(cand.diagnostics) + candidate_diagnostics(cand)

    result = IndexingResult(
        candidates=outcome.candidates, engines_run=outcome.engines_run,
        systems_searched=outcome.systems_searched,
        search_complete=outcome.search_complete,
        engine_stats=outcome.engine_stats,
        fom_panel_disagrees=outcome.fom_panel_disagrees, quality=quality,
        validated=validated, wavelength=peaks.wavelength,
        n_usable_lines=len(peaks.usable()), provenance=provenance,
        diagnostics=list(quality.diagnostics) + outcome.diagnostics
        + _pair_shift_diagnostics(quality))
    out = result.model_copy(update={
        "diagnostics": list(result.diagnostics)
        + index_diagnostics(result, instrument)})
    _emit_end(stream, out)
    return out


def _emit_end(stream, result) -> None:
    if stream is None:
        return
    best = result.best_or_none()
    stream.emit("index_end", n_candidates=len(result.candidates),
                confidence=[c.confidence for c in result.candidates],
                abstained=best is None,
                cell=list(best.cell) if best is not None else None,
                validated=result.validated)


def _spec_notes(spec, names: Sequence[str], quality) -> dict[str, str]:
    """The search's own settings, recorded so a run is reproducible from what it
    reports — including ``seed``, which is the only field a stochastic engine
    would need and which is therefore recorded whether one ran or not."""
    return {
        "engines": ", ".join(names),
        "systems": ", ".join(spec.systems),
        "d_axis_range_A": f"{spec.min_d_axis:g}-{spec.max_d_axis:g}",
        "n_unindexed": str(spec.n_unindexed),
        "n_search_lines": str(spec.n_search_lines),
        "k_sigma": f"{spec.k_sigma:g}",
        "sigma_sys_deg": f"{spec.sigma_sys_deg:g}",
        "budget_seconds": f"{spec.budget_seconds:g}",
        # only when declared, so a default run's notes are byte-identical to
        # every run recorded before the field existed
        **({"total_budget_seconds": f"{spec.total_budget_seconds:g}"}
           if spec.total_budget_seconds is not None else {}),
        "seed": str(spec.seed),
        "indexing_thresholds_version": quality.thresholds_version,
    }


__all__ = ["ABSENT_SIGMA", "ABSENT_WINDOW_FWHM", "DUMMY_SPECIES",
           "absent_reflections", "index_pattern", "seed_widths",
           "structure_from_candidate", "validate_by_lebail", "validation_plan"]
