"""Is this peak list fit to index — and what does it already say?

Both source papers on autoindexing conclude that *data quality* decides success:
"Lack of attention to data quality, even if followed by use of the most
efficient programs, will usually lead to failure" (Bergmann, Le Bail, Shirley &
Zlokazov, 2004).  This module is that sentence made executable.  It measures
what the list can support and **abstains** when it cannot, the same move Layer
1's global maturity gate makes one rank down, and for the same reason: a ranked
list of cells produced from data that cannot distinguish them is a confident
wrong answer, which is worse than no answer.

**What is knowable from a peak list alone, and what is not.**  This distinction
shaped the module and is worth stating before the code, because the WP's plan
did not resolve it.  Everything except the shift is a property of the list:

* the σ census, and σ(Q) against the mean line spacing — a *resolving power*;
* lines per metric degree of freedom, which is system-dependent, so "enough
  lines" is not one number;
* Smith's (1977) volume envelope from d at the N-th line;
* the **separability geometry** of the three shift templates over the 2θ range
  actually sampled — computable from the angles alone, before any shift is
  measured, which makes it a statement about the experiment rather than about
  the specimen.

The **magnitude and cause of a systematic shift, however, are not** knowable
from the list on its own: with no cell there is nothing to deviate *from*.
A shift is identifiable only against a reference — a certified cell, an internal
standard, or a candidate cell an engine has proposed — so
:func:`fit_shift_model` takes deviations, :func:`assess_peak_list` screens the
shift only when a caller supplies references, and the report says
``shift.source == "unavailable"`` otherwise rather than reporting a zero shift
it did not measure.  A search that then wants a shift dimension gets it from
WP-1020's ``refine_candidate``, where a cell exists.

**Dominant zone and dominant row are *not* here, and the reason is a
measurement.**  The WP's plan asserted both are "detectable in Q-space before any
search"; they are not, because neither is a summary statistic of a peak list.  A
dominant zone (one real axis much shorter than the others, Werner's short-axis
test) is the statement that the *low-angle lines satisfy a two-dimensional
quadratic form* — a 2-D indexing problem.  A dominant row (one axis much longer)
is an arithmetic progression k²B hiding among the low Q values — a 1-D one.  Each
is a search, not a census.  The obvious census — the most-repeated Q difference,
Ito's coincidence idea — was implemented and measured, and it separates neither:
at σ(Q) from a 0.002° peak list it scores dominant-zone cells (c = 3.1 and
2.7 Å) at +0.9σ and +0.8σ against a permutation null while scoring a *general*
monoclinic cell at +3.3σ.  What it actually detects is small-integer Q
commensurability — a cubic list scores +15.6σ against a uniform null, because
Q = A(h²+k²+l²) makes every difference a multiple of A.  So it was removed rather
than shipped as a diagnostic that fires on general cells and misses the cases it
names; the detection belongs in the engines (WP-1021/1022), where a candidate
zone exists to test.

**The shift model is the one genuine improvement over the programs the 2004
paper benchmarks**: they fit a single constant "zeropoint", while three distinct
physical causes produce three different angular dependences, and this package
already names all three (``report/layer2.py``'s ``_POSITION_ACTIONS``).  Both
bethanechol ICDD entries carry ~0.10° 2θ and the paper *hypothesises* specimen
displacement without a way to test it.  The templates are therefore fitted as
**nested single fits, never jointly**, restating Layer 1's measured reason: a
joint fit of collinear templates returned "a 0.02° zero-point error as a 1.8°
constant cancelled by a −1.8° cosθ" (``report/layer1.py``).
"""

from __future__ import annotations

import numpy as np

from ..report.layer1 import _templates as _trend_templates
from ..report.schemas import SEPARABILITY_MIN_SS_RATIO
from ..schemas.indexing import (
    MAX_RELATIVE_SIGMA_Q,
    METRIC_DOF,
    MIN_LINES_PER_DOF,
    PEAK_MIN_USABLE_LINES,
    SHIFT_TEMPLATES,
    SMITH_VOLUME_C1,
    SMITH_VOLUME_C2,
    DataQualityReport,
    PeakList,
    ShiftScreen,
    ShiftTemplateFit,
)

#: Reflections per Laue orbit, averaged over general hkl, relative to triclinic
#: (where a Friedel pair is the whole orbit).  Smith's envelope counts *distinct
#: lines*, so a high-symmetry lattice of the same volume shows fewer of them and
#: the same N lines imply a larger cell — the triclinic constant applied to a
#: cubic search would bound the volume ~24× too tightly.  These are orbit sizes
#: divided by 2, i.e. the Laue-class order over the triclinic order, and they are
#: *checked against the package's own* ``generate_reflections`` in
#: ``tests/test_indexing_quality.py`` rather than trusted as a table.
_LAUE_ORBIT_FACTOR: dict[str, float] = {
    "triclinic": 1.0, "monoclinic": 2.0, "orthorhombic": 4.0,
    "tetragonal": 8.0, "trigonal": 6.0, "hexagonal": 12.0, "cubic": 24.0,
}


def shift_template_basis(two_theta: np.ndarray) -> dict[str, np.ndarray]:
    """The three shift templates evaluated at these angles.

    Imported from ``report.layer1._templates`` rather than restated, then
    narrowed to :data:`~pxrdref.schemas.indexing.SHIFT_TEMPLATES` — ``tan_theta``
    is a *cell* error and must not be offered here (see that constant).
    """
    full = _trend_templates("position", np.asarray(two_theta, dtype=np.float64),
                            1.0)
    return {name: full[name] for name in SHIFT_TEMPLATES}


def template_collinearity(two_theta: np.ndarray) -> float:
    """Largest |cosine| between two shift templates over the angles sampled.

    Knowable before any shift is measured, which is what makes it a property of
    the *experiment*: over a short low-angle range cos θ ≈ 1 and sin 2θ ≈ 2θ, so
    all three templates point nearly the same way and no amount of counting can
    attribute a shift measured there.  Extending the range is the fix, and this
    number is what says so.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    if len(tt) < 2:
        return 1.0
    design = np.vstack([shift_template_basis(tt)[n] for n in SHIFT_TEMPLATES])
    norm = design / np.maximum(np.linalg.norm(design, axis=1, keepdims=True),
                               1e-300)
    gram = np.abs(norm @ norm.T)
    np.fill_diagonal(gram, 0.0)
    return float(gram.max())


def fit_shift_model(two_theta: np.ndarray, deviation_deg: np.ndarray,
                    esd_deg: np.ndarray | float | None = None) -> ShiftScreen:
    """Attribute a systematic 2θ shift to one physical cause, or decline to.

    ``deviation_deg`` is observed − reference, in degrees.  Each template is
    fitted **alone**, through the origin (a template *is* the whole model of its
    cause, so there is no intercept to add — an intercept would be the
    ``constant`` template competing with itself), weighted by 1/σ².  The winner
    is called distinguishable only when the runner-up leaves
    ``SEPARABILITY_MIN_SS_RATIO`` times more variance unexplained — imported,
    not restated.

    ``sigma_sys_deg`` is the residual scatter the best template leaves, and it is
    a *floor*, not an error bar: it is what remains of the systematic after the
    named cause is removed, so it is the quantity a downstream tolerance adds in
    quadrature to each line's own σ.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    dev = np.asarray(deviation_deg, dtype=np.float64)
    if tt.shape != dev.shape or tt.ndim != 1:
        raise ValueError("two_theta and deviation_deg must be the same 1-D shape")
    if esd_deg is None:
        w = np.ones_like(tt)
    else:
        esd = np.broadcast_to(np.asarray(esd_deg, dtype=np.float64), tt.shape)
        w = 1.0 / np.maximum(esd, 1e-12)
    if len(tt) < 2:
        return ShiftScreen(n_lines=len(tt), source="measured",
                           max_collinearity=1.0)

    basis = shift_template_basis(tt)
    b = dev * w
    ss_tot = float(b @ b)
    fits: list[ShiftTemplateFit] = []
    for name in SHIFT_TEMPLATES:
        col = (basis[name] * w)[:, None]
        coef, *_ = np.linalg.lstsq(col, b, rcond=None)
        resid = b - col @ coef
        ss = float(resid @ resid)
        dof = max(len(tt) - 1, 1)
        gram = max(float(col.ravel() @ col.ravel()), 1e-300)
        fits.append(ShiftTemplateFit(
            name=name, coefficient=float(coef[0]),
            stderr=float(np.sqrt(max(ss / dof / gram, 0.0))),
            r2=float(1.0 - ss / ss_tot) if ss_tot > 0 else 0.0,
            residual_ss=ss))

    ranked = sorted(fits, key=lambda f: f.residual_ss)
    ratio = ranked[1].residual_ss / max(ranked[0].residual_ss, 1e-12)
    best = ranked[0]
    resid_best = dev - best.coefficient * basis[best.name]

    # what choosing the wrong cause would cost, over the angles sampled, among
    # the templates that fit comparably.  Measured rather than assumed, because
    # the assumption it replaces was wrong: see ShiftScreen.prediction_spread_deg
    bar = SEPARABILITY_MIN_SS_RATIO * max(best.residual_ss, 1e-12)
    rival = np.array([f.coefficient * basis[f.name] for f in fits
                      if f.residual_ss <= bar])
    spread = (float(np.max(rival.max(axis=0) - rival.min(axis=0)))
              if len(rival) > 1 else 0.0)

    return ShiftScreen(
        n_lines=len(tt), templates=fits, best=best.name,
        separable=bool(ratio > SEPARABILITY_MIN_SS_RATIO),
        separability_ratio=float(min(ratio, 1e6)),
        max_collinearity=template_collinearity(tt),
        sigma_sys_deg=float(np.std(resid_best, ddof=1)) if len(tt) > 2 else 0.0,
        prediction_spread_deg=spread,
        source="measured")


#: Largest centring multiplicity each system admits — the number of lattice
#: points per conventional cell of the most centred Bravais type available to it.
#: A centred lattice extinguishes reflections (F keeps 1/4 of hkl, R in the
#: hexagonal setting 1/3, I/A/B/C a half), so the *same* N distinct lines imply a
#: correspondingly larger conventional cell.  Centring is not knowable before a
#: search — it is part of the answer (the extinction symbol, determined after
#: one by ``indexing.extinction``) — so the
#: envelope must use the **worst case**, since the one failure a search bound may
#: not have is excluding the true cell.
_MAX_CENTRING: dict[str, int] = {
    "triclinic": 1, "monoclinic": 2, "orthorhombic": 4, "tetragonal": 2,
    "trigonal": 3, "hexagonal": 1, "cubic": 4,
}


def volume_envelope(d_n: float, n_lines: int, system: str = "triclinic",
                    *, centring_multiplicity: int | None = None) -> float:
    """Smith's (1977) upper envelope on the unit-cell volume, Å³.

        V ≈ 0.6·d_N³/(1/N − 0.0052)

    from the d-spacing of the N-th line — a *statistical* statement (how large a
    cell can be while still producing only N distinct lines above d_N), so it is
    a search bound and never a measurement.  At N = 20 the constant is 13.39.

    Scaled by **two** factors, because the published form is for a *primitive
    triclinic* lattice and the count Smith's derivation makes is of *distinct
    lines*:

    * the Laue orbit factor (:data:`_LAUE_ORBIT_FACTOR`) — a cubic lattice of the
      same volume shows ~24× fewer distinct lines, so the triclinic constant
      bounds a cubic search 24× too tightly;
    * the centring multiplicity (:data:`_MAX_CENTRING`) — measured while writing
      this: the triclinic-with-Laue-scaling form put corundum's envelope at
      125 Å³ against a true 255 Å³, i.e. it **excluded the right answer**,
      because R-centring extinguishes two thirds of hkl.

    Pass ``centring_multiplicity`` once an extinction symbol is known
    (:func:`pxrdref.indexing.extinction.determine_extinction_symbol`, whose
    leading class names the centring) to tighten the bound; the default is the
    loosest the system allows.
    """
    if d_n <= 0.0 or n_lines < 2:
        raise ValueError("need a positive d and at least two lines")
    denom = 1.0 / n_lines - SMITH_VOLUME_C2
    if denom <= 0.0:                    # N ≳ 192: the envelope stops existing
        return float("inf")
    factor = _LAUE_ORBIT_FACTOR.get(system, 1.0)
    centring = (_MAX_CENTRING.get(system, 1) if centring_multiplicity is None
                else int(centring_multiplicity))
    return float(factor * centring * SMITH_VOLUME_C1 * d_n ** 3 / denom)


def assess_peak_list(peaks: PeakList, *,
                     reference_two_theta: np.ndarray | None = None,
                     sigma_sys_deg: float | None = None,
                     envelope_n: int = PEAK_MIN_USABLE_LINES,
                     ) -> DataQualityReport:
    """Judge a peak list fit to index, or abstain with a reason.

    ``reference_two_theta`` — positions the observed ones should be compared
    against (a certified cell's, an internal standard's, a candidate cell's).
    Supplying them is what turns the shift screen on; without them the report
    carries ``shift.source == "unavailable"`` rather than a shift of zero.
    ``sigma_sys_deg`` declares a systematic floor from outside (a calibration),
    and is recorded as such — an *assumed* precision must never be quoted as a
    measured one, the same rule ``PeakList.from_positions`` follows.
    """
    from .diagnostics import quality_diagnostics

    usable = peaks.usable()
    tt, esd = peaks.two_theta(), peaks.two_theta_esd()
    q, q_esd = peaks.q(), peaks.q_esd()

    if len(usable) < 2:
        report = DataQualityReport(
            n_usable=len(usable), n_total=len(peaks.peaks),
            two_theta_min=peaks.two_theta_min, two_theta_max=peaks.two_theta_max,
            source=peaks.source, sigma_two_theta_median=float("nan"),
            sigma_two_theta_worst=float("nan"),
            relative_sigma_q_median=float("nan"), sigma_over_spacing=float("nan"),
            supports_indexing=False,
            abstained_reason=(f"{len(usable)} usable line(s): a lattice cannot "
                              "be constrained by fewer than two"))
        return report.model_copy(update={
            "diagnostics": quality_diagnostics(report, peaks)})

    order = np.argsort(q)
    q, q_esd = q[order], q_esd[order]
    spacing = float(np.mean(np.diff(q))) if len(q) > 1 else float("inf")
    rel_sigma = float(np.median(q_esd / np.maximum(q, 1e-300)))
    n = len(usable)
    per_dof = {sys: n / dof for sys, dof in METRIC_DOF.items()}
    supported = sorted(s for s, v in per_dof.items() if v >= MIN_LINES_PER_DOF)

    n_env = min(envelope_n, n)
    d_n = float(np.min(np.sort(q)[:n_env] ** -0.5))
    envelope = {system: volume_envelope(d_n, n_env, system)
                for system in METRIC_DOF}

    shift = None
    if reference_two_theta is not None:
        ref = np.asarray(reference_two_theta, dtype=np.float64)
        if ref.shape != tt.shape:
            raise ValueError(
                f"reference_two_theta has {ref.shape[0]} entries against "
                f"{tt.shape[0]} usable lines — pass one reference per usable "
                "line, in the same 2θ order")
        shift = fit_shift_model(tt, tt - ref, esd)
    elif sigma_sys_deg is not None:
        shift = ShiftScreen(n_lines=n, sigma_sys_deg=float(sigma_sys_deg),
                            max_collinearity=template_collinearity(tt),
                            source="unavailable")
    else:
        shift = ShiftScreen(n_lines=n,
                            max_collinearity=template_collinearity(tt),
                            source="unavailable")

    reason = None
    if n < PEAK_MIN_USABLE_LINES:
        reason = (f"{n} usable lines, below the {PEAK_MIN_USABLE_LINES} that "
                  "M20, F20 and Smith's volume envelope are defined on")
    elif not supported:
        reason = (f"{n} usable lines is fewer than {MIN_LINES_PER_DOF:g} per "
                  "metric degree of freedom in every crystal system")
    elif rel_sigma > MAX_RELATIVE_SIGMA_Q:
        reason = (f"median σ(Q)/Q = {rel_sigma:.2e}, above "
                  f"{MAX_RELATIVE_SIGMA_Q:.0e}: cells differing by 0.1 % in a "
                  "lattice parameter are not distinguishable at this precision")

    report = DataQualityReport(
        n_usable=n, n_total=len(peaks.peaks),
        two_theta_min=peaks.two_theta_min, two_theta_max=peaks.two_theta_max,
        source=peaks.source,
        sigma_two_theta_median=float(np.median(esd)),
        sigma_two_theta_worst=float(np.max(esd)),
        relative_sigma_q_median=rel_sigma,
        sigma_over_spacing=float(np.median(q_esd) / max(spacing, 1e-300)),
        lines_per_dof=per_dof, systems_supported=supported,
        volume_envelope=envelope, shift=shift,
        supports_indexing=reason is None, abstained_reason=reason)
    return report.model_copy(update={
        "diagnostics": quality_diagnostics(report, peaks)})


__all__ = ["assess_peak_list", "fit_shift_model", "shift_template_basis",
           "template_collinearity", "volume_envelope"]
