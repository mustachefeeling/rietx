"""Whole-profile validation of a candidate cell: the Le Bail fit and its two
detectors.

The figure-of-merit panel is computed on ≤20 lines and is structurally blind to
three things the whole pattern sees, and the third is the one no figure of merit
can be patched to see:

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
sit near a tick.  Measured on a synthetic LaB₆ pattern (4250 points, 15-100° 2θ,
Poisson noise), ``unmatched_calc`` was **11 of 17** for the *certified* cell and
44 of 87 for a doubled one — it does not separate them at all.
:func:`absent_reflections` asks the question directly instead — is there net
intensity above the *fitted* background at this position? — and separates them
cleanly: **0 of 17 for the truth, 67 of 87 for the doubled cell.**

**The two detectors and ``lebail_rwp`` catch different failures, which is why all
three are reported.**  Same measurement, same four cells:

| candidate | Rwp | predicted_but_absent | unmatched_observed |
|---|---|---|---|
| truth | 0.200 | 0/17 | 0 |
| doubled cell | 0.389 | **67/87** | 0 |
| a·√5 supercell | 1.097 | 9/117 | 3 |
| metric 1 % off | 1.137 | 0/17 | **87** |

Read the table by column.  Rwp is decisive on a *wrong metric* (1.1 against 0.2)
and nearly silent on an *oversized* one (0.394 — barely twice the truth's, and
on real data that gap is inside the spread between specimens); the oversized cell
is caught only by column three.  A wrong metric is caught from the other side by
column four, where 89 observed peaks have no calculated reflection.  The a·√5
row is the useful reminder that these overlap: its fit is already refuted by Rwp,
so its low absent count costs nothing — a badly-fitted background is what makes
that count unreliable, and a badly-fitted background comes with an Rwp that says
so.

``lebail_rwp`` is the figure the literature names; it is **not** a member of the
ranking panel.  The panel ranks every candidate and this costs a refinement, so
it is computed for the shortlist only — and ranking on it would reintroduce the
blind spot validation exists to close, since a bigger cell with more free
intensities fits better.
"""

from __future__ import annotations

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
#: yet known to be one (WP-1025), or a high-angle line the counting time did not
#: reach — is absent for reasons that have nothing to do with the lattice, and
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
    an extinction.  Determining the real conditions is WP-1025.
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
                       ) -> LeBailValidation:
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
    """
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
                         two_theta_limits=two_theta_limits)
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


__all__ = ["ABSENT_SIGMA", "ABSENT_WINDOW_FWHM", "DUMMY_SPECIES",
           "absent_reflections", "seed_widths", "structure_from_candidate",
           "validate_by_lebail", "validation_plan"]
