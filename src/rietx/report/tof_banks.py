"""What a joint fit over time-of-flight banks owes its reader about the banks.

A joint fit sums the banks' χ² with unit weights, each point weighted by 1/σ²
from the file's propagated counting statistics (``multi._refuse_sigma_less_banks``
says why), and shares the structure.  Its answer is one set of numbers, so
which bank determined which number, whether the banks agree, and whether their
σ can carry the weight are questions the pooled statistics cannot answer.  Six
codes answer them, each raised from :class:`rietx.multi.MultiHistogramRefinement`
when the list holds at least one bank and two histograms (the design and its
measurements: the 2026-11-06 multi-bank practice survey, § 5.3):

* ``BANK_WEIGHT_SHARES`` (info): per histogram, the shares of points, χ²,
  Bragg weight Σ((y_calc − y_bkg)/σ)² and, per shared column, Fisher
  information diag(J_hᵀJ_h)/diag(JᵀJ).
* ``BANK_DOMINATES_MISFIT`` (warning): one histogram holds most of the excess
  χ², with a reduced χ² well above the others'.
* ``BANK_CELL_INCONSISTENT`` (warning): with every DIFC held, a bank reads the
  shared cell at a different d-scale from the reference bank.
* ``BANK_SCALE_INCONSISTENT`` (info): vanadium-normalised banks whose
  absolute-normalisation factors (Paddison 2025; eq. 19 of its arXiv v1) disagree.
* ``BANK_SIGMA_SUSPECT`` (warning): a bank's esd column is not its own
  channel-to-channel scatter.
* ``BANK_REFERENCE_NOT_HIGHEST_ANGLE`` (warning): the DIFC held to pin the
  cell's scale is not the backscattering bank's.

``BANK_LEAVE_ONE_OUT`` (info) is the opt-in seventh, ``fit(leave_one_out=True)``,
built in ``multi.py`` because it refits.

``MAGNETIC_SCALE_UNPINNED`` (warning, T-6) is raised on a bank in a single
fit too, from :func:`magnetic_scale_unpinned`: a bank whose free scale
absorbs a free moment's magnitude because the bank holds magnetic intensity
and almost no nuclear Bragg weight (the survey's § 4).
"""

from __future__ import annotations

import math

import numpy as np

from ..optimize import lapack
from ..schemas.common import Diagnostic

#: ``BANK_DOMINATES_MISFIT``: a histogram "dominates" when it holds more than
#: this fraction of the summed excess χ² (a majority) …
MISFIT_SHARE = 0.5
#: … and its reduced χ² is more than this factor above the others' median.  A
#: sharper or better-counted bank legitimately shows a larger χ²_red (Toby 2006,
#: *Powder Diffr.* 21, 67, p. 69), so the factor keeps the ordinary spread of
#: reduced χ² across HRPD banks (1.0-1.3 on the 2026-11-06 Si fits) out.  On
#: one GEM pattern (2026-11-09) the two best-counted banks read 2.26 and 2.42
#: with no single-bank cause; the code stayed silent there only because
#: neither held a majority of the excess χ² (:data:`MISFIT_SHARE`).
MISFIT_CHI2_RATIO = 2.0
#: ``BANK_CELL_INCONSISTENT`` fires above this |Δd/d| as well as above
#: :data:`INCONSISTENT_SIGMA` esds: the HRPD era-to-era calibration scatter is
#: 2-6e-4 in bank 2 and the furnace sample-position offset −1.65e-3
#: (planning HRPD_SI_CALIBRATION / HRPD_MANTID_BATCH, 2026-11-06), so a
#: smaller difference is inside what a delivered calibration promises.
CELL_SCALE_TOLERANCE = 2e-4
#: The significance both consistency codes ask of a difference, in esds.
INCONSISTENT_SIGMA = 3.0
#: ``BANK_SIGMA_SUSPECT``'s band on (lag-difference scatter)/(propagated σ).
#: Measured 0.92-1.04 on the three HRPD Si banks and 1.0-1.28 on the LaTaO4
#: banks (2026-11-06 survey, § 1.3), and 0.77-0.87 at lags 2-3 on ordinarily
#: reduced GEM and WISH banks (2026-11-09: two GEM banks of one pattern, five
#: WISH bank pairs), which is why the lower edge is 0.7: ISIS only, untested
#: beyond it.
SIGMA_RATIO_BAND = (0.7, 1.25)
#: The lags of the σ test, in channels.  Short, because the difference is of
#: y − y_calc and a fitted model misfits between peaks: on the HRPD Si banks
#: (χ²_red 12-13) the ratio is 1.00 at lag 1 and rises to 2.1-2.2 at lag 20,
#: which is the misfit's structure and not σ (2026-11-06, T-5 acceptance).
#: Not lag 1: on GEM and WISH it read 0.52-0.77 against 0.75-0.89 at lags 2-3,
#: the neighbour correlation that rebinning leaves, not a σ error (2026-11-09).
SIGMA_LAGS = (2, 3)
#: Pairs a lag needs before it is read.  A coverage gap, not only a guard: on a
#: dense two-phase GEM pattern 3 of 5 banks offer fewer (39, 0 and 0 peak-free
#: pairs), so the test is silent on them by construction (2026-11-09).
SIGMA_MIN_PAIRS = 50
#: Relative step of the central difference giving a bank's ∂y/∂ln DIFC column.
DIFC_STEP = 1e-5
#: ``MAGNETIC_SCALE_UNPINNED`` fires on a bank that keeps less than this
#: fraction of its own information on a phase's moment magnitude once its
#: scale is free (:func:`moment_information_kept`; the fraction is
#: 1 − ρ² between the bank's scale and moment-magnitude columns, which is the
#: nuclear share of the phase's Bragg weight where the two families do not
#: overlap).  Below 0.05 the bank's own esd on the magnitude is inflated
#: more than 1/√0.05 ≈ 4.5×.  Measured on synthetic banks only (a
#: magnetic-only window at 0, the same bank with its nuclear lines at 0.5-0.9);
#: untested on a real bank.
MAGNETIC_SCALE_NUCLEAR_FLOOR = 0.05


def _is_bank(model) -> bool:
    return getattr(model, "axis", "two_theta") == "tof"


def _pct(x: float) -> str:
    return f"{100.0 * x:.0f}"


def _shares(values) -> list[float]:
    total = float(sum(values))
    return [float(v) / total if total > 0 else 0.0 for v in values]


def _dense_jac(jac) -> np.ndarray | None:
    if jac is None:
        return None
    to = getattr(jac, "toarray", None)
    return np.asarray(to() if to is not None else jac, dtype=np.float64)


def _hist_rows(models) -> list[slice]:
    off = np.concatenate([[0], np.cumsum([m.n_points for m in models])]).astype(int)
    return [slice(int(off[h]), int(off[h + 1])) for h in range(len(models))]


def _family(path: str) -> str:
    """The family a shared column's Fisher share is summed over, so the
    message carries one share per kind of parameter rather than one per atom."""
    tail = path.rsplit(".", 1)[-1]
    if ".cell." in path:
        return "cell"
    if ".dof." in path or tail in ("x", "y", "z"):
        return "coordinates"
    if tail == "biso" or ".adp." in path:
        return "ADPs"
    if tail == "occ":
        return "occupancies"
    return path


def weight_shares(models, mtable, per_ycalc, per_ybkg, jac, weights) -> list[Diagnostic]:
    """``BANK_WEIGHT_SHARES``: which histogram determines which number.

    The Fisher shares are summed per family of shared column (:func:`_family`):
    cell, coordinates, ADPs, occupancies, and any other shared path by name.
    """
    n = len(models)
    pts = [m.n_points for m in models]
    chi2 = [w * float(np.sum(((m.y_obs - yc) / m.sigma) ** 2))
            for m, yc, w in zip(models, per_ycalc, weights, strict=True)]
    bragg = [w * float(np.sum(((yc - yb) / m.sigma) ** 2))
             for m, yc, yb, w in zip(models, per_ycalc, per_ybkg, weights, strict=True)]
    parts = [f"points {'/'.join(_pct(s) for s in _shares(pts))} %",
             f"χ² {'/'.join(_pct(s) for s in _shares(chi2))} %",
             f"Bragg weight {'/'.join(_pct(s) for s in _shares(bragg))} %"]
    J = _dense_jac(jac)
    if J is not None and J.shape[0] == sum(pts) and mtable.n_shared:
        rows = _hist_rows(models)
        families: dict[str, list[int]] = {}
        for k, path in enumerate(mtable.free_paths[:mtable.n_shared]):
            families.setdefault(_family(path), []).append(k)
        for name, ks in families.items():
            total = float(np.sum(J[:, ks] ** 2))
            if total <= 0.0:
                continue
            per = [float(np.sum(J[r][:, ks] ** 2)) / total for r in rows]
            parts.append(f"{name} {'/'.join(_pct(s) for s in per)} %")
    order = ", ".join(f"histogram {h}" for h in range(n))
    return [Diagnostic(
        level="info", code="BANK_WEIGHT_SHARES",
        message=(f"Shares per histogram ({order}): " + "; ".join(parts) + ". "
                 "The Bragg weight is the pull on scale, ADPs and occupancies; a "
                 "column's Fisher share is the pull on that shared parameter. A "
                 "bank's χ² share follows its point count, not its information."),
        suggestion=None)]


def dominates_misfit(models, per_ycalc, n_free, weights) -> list[Diagnostic]:
    """``BANK_DOMINATES_MISFIT``: excess χ² concentrated in one histogram."""
    n = len(models)
    if n < 2:
        return []
    chi2 = [w * float(np.sum(((m.y_obs - yc) / m.sigma) ** 2))
            for m, yc, w in zip(models, per_ycalc, weights, strict=True)]
    dof = [max(m.n_points - p, 1) for m, p in zip(models, n_free, strict=True)]
    excess = [c - d for c, d in zip(chi2, dof, strict=True)]
    red = [c / d for c, d in zip(chi2, dof, strict=True)]
    positive = sum(e for e in excess if e > 0.0)
    out = []
    for h in range(n):
        others = [red[k] for k in range(n) if k != h]
        med = float(np.median(others))
        if (positive > 0.0 and excess[h] > MISFIT_SHARE * positive
                and red[h] > MISFIT_CHI2_RATIO * med):
            out.append(Diagnostic(
                level="warning", code="BANK_DOMINATES_MISFIT", where=[f"hist.{h}"],
                value=excess[h] / positive,
                message=(f"Histogram {h} holds {_pct(excess[h] / positive)} % of the "
                         f"joint fit's excess χ² (χ² − (N − p)), at χ²_red "
                         f"{red[h]:.3g} against the others' median {med:.3g}. Its "
                         f"misfit is systematic and it pulls the shared parameters "
                         f"toward a compromise. A sharper or better-counted bank "
                         f"legitimately shows a larger χ²_red (Toby 2006, p. 69): "
                         f"this locates the misfit, it does not condemn the bank."),
                suggestion=(f"look at histogram {h}'s difference curve: crop its "
                            f"window, free its profile or background, or drop it; "
                            f"a smaller weight still biases the shared parameters")))
    return out


def _bank_angle(mtable, h: int) -> float:
    return float(mtable.instruments[h].source.two_theta_bank_deg)


def _difc_free(mtable, h: int) -> bool:
    free = set(mtable.free_paths)
    return (f"hist.{h}.instrument.source.difc" in free
            or "instrument.source.difc" in free)


def _cell_length_free(mtable) -> bool:
    return any(".cell." in p and p.rsplit(".", 1)[-1] in ("a", "b", "c")
               and not p.startswith("hist.") for p in mtable.free_paths)


def reference_bank(models, mtable) -> int | None:
    """The bank whose DIFC pins the scale: the highest-angle bank holding it."""
    held = [h for h, m in enumerate(models) if _is_bank(m) and not _difc_free(mtable, h)]
    return max(held, key=lambda h: _bank_angle(mtable, h)) if held else None


def reference_not_highest(models, mtable) -> list[Diagnostic]:
    """``BANK_REFERENCE_NOT_HIGHEST_ANGLE``: a lower-angle bank pins the scale."""
    banks = [h for h, m in enumerate(models) if _is_bank(m)]
    if len(banks) < 2 or not any(_difc_free(mtable, h) for h in banks):
        return []
    top = max(banks, key=lambda h: _bank_angle(mtable, h))
    ref = reference_bank(models, mtable)
    if ref is None or not _difc_free(mtable, top):
        return []
    return [Diagnostic(
        level="warning", code="BANK_REFERENCE_NOT_HIGHEST_ANGLE",
        where=[f"hist.{top}.instrument.source.difc"],
        value=_bank_angle(mtable, ref),
        message=(f"The DIFC held to pin the cell's scale is histogram {ref}'s "
                 f"(2θ = {_bank_angle(mtable, ref):g}°), while histogram {top}'s, "
                 f"the highest-angle bank (2θ = {_bank_angle(mtable, top):g}°), is "
                 f"free. dt/t = dL/L + cot θ·dθ, so a sample-position error moves "
                 f"the backscattering bank least, and the cell then carries the "
                 f"held bank's position error."),
        suggestion=(f"hold hist.{top}.instrument.source.difc and free the others' "
                    f"(McCusker et al. 1999, p. 45)"))]


def cell_inconsistent(models, mtable, per_values, jac, weights) -> list[Diagnostic]:
    """``BANK_CELL_INCONSISTENT``: each held bank's d-scale against the reference.

    Read at the joint answer by one Gauss-Newton step: the joint Jacobian is
    extended by one column per non-reference bank whose DIFC is held, its
    ∂r/∂ln DIFC by central difference on that bank's compiled model, and the
    stacked residual is solved over the extended set.  The step on a bank's
    new column is ε = Δd/d, the d-scale that bank alone reads the shared cell
    at against the reference (d_h/d_joint = DIFC_fit/DIFC_held), with the esd
    of the extended covariance.  Linear in ε: an offset the joint fit has
    split leaves each bank a fraction of a peak width from its own optimum,
    where one step is the answer to the order the step is small in.  Silent
    unless a shared cell length is free, at least two banks hold their DIFC,
    and the Jacobian has one row per channel.

    **A screen, confirmed by a refit.**  Far from linear the step overshoots:
    on HRPD LaTaO4 in the furnace (χ²_red 159/169 with both DIFCs held) it read
    −2.37e-3 where a refit with the bank's DIFC free gives −1.75e-3, against
    −1.14e-3 and −1.11e-3 on the 483 K run.  So
    :meth:`rietx.multi.MultiHistogramRefinement.fit` refits each flagged bank
    from the answer with its DIFC free and reports that refit's Δd/d
    (:func:`cell_diagnostic`), the one-step reading beside it.
    """
    banks = [h for h, m in enumerate(models) if _is_bank(m)]
    if len(banks) < 2 or not _cell_length_free(mtable):
        return []
    ref = reference_bank(models, mtable)
    test = [h for h in banks if h != ref and not _difc_free(mtable, h)]
    J = _dense_jac(jac)
    if ref is None or not test or J is None:
        return []
    rows = _hist_rows(models)
    if J.shape[0] != rows[-1].stop:
        return []
    r = np.concatenate([
        math.sqrt(w) * (m.y_obs - np.asarray(m.evaluate(v), dtype=np.float64)) / m.sigma
        for m, v, w in zip(models, per_values, weights, strict=True)])
    cols = []
    for h in test:
        m, v = models[h], dict(per_values[h])
        difc = v["instrument.source.difc"]
        v["instrument.source.difc"] = difc * (1.0 + DIFC_STEP)
        up = np.asarray(m.evaluate(v), dtype=np.float64)
        v["instrument.source.difc"] = difc * (1.0 - DIFC_STEP)
        dn = np.asarray(m.evaluate(v), dtype=np.float64)
        k = np.zeros(J.shape[0])
        k[rows[h]] = -math.sqrt(weights[h]) * (up - dn) / (2.0 * DIFC_STEP) / m.sigma
        cols.append(k)
    A = np.hstack([J, np.column_stack(cols)])
    norm = np.sqrt(np.sum(A ** 2, axis=0))
    norm[norm == 0.0] = 1.0
    An = A / norm
    step, *_ = lapack.lstsq(An, -r, rcond=None)
    dof = max(A.shape[0] - A.shape[1], 1)
    s2 = float(np.sum((r + An @ step) ** 2)) / dof
    cov = lapack.pinv(An.T @ An) * s2
    out = []
    for i, h in enumerate(test):
        c = J.shape[1] + i
        eps = float(step[c] / norm[c])
        esd = float(math.sqrt(max(cov[c, c], 0.0)) / norm[c])
        if cell_confirmed(eps, esd):
            out.append(cell_diagnostic(mtable, h, ref, eps, esd, screen=None))
    return out


def cell_diagnostic(mtable, h: int, ref: int, eps: float, esd: float, *,
                    screen: float | None) -> Diagnostic:
    """One ``BANK_CELL_INCONSISTENT``.  ``screen`` is the one-step reading
    when ``eps`` is the confirming refit's, ``None`` when ``eps`` is the
    one-step reading itself."""
    how = ("Linearised at the joint answer (one Gauss-Newton step with this bank's "
           "DIFC added)." if screen is None else
           f"Measured by a refit from the joint answer with this bank's DIFC free; "
           f"the one-step screen read {screen:+.3g}.")
    return Diagnostic(
        level="warning", code="BANK_CELL_INCONSISTENT",
        where=[f"hist.{h}.instrument.source.difc"], value=eps,
        message=(f"Histogram {h} (2θ = {_bank_angle(mtable, h):g}°) reads the shared "
                 f"cell at Δd/d = {eps:+.3g} ± {esd:.2g} against histogram {ref} "
                 f"(2θ = {_bank_angle(mtable, ref):g}°, the reference), with every "
                 f"DIFC held. That is a sample-position or calibration offset of the "
                 f"bank, and the joint cell splits it between the banks. {how}"),
        suggestion=(f"free hist.{h}.instrument.source.difc (or its TZERO) and keep "
                    f"hist.{ref}.instrument.source.difc held, then refit"))


def cell_confirmed(eps: float, esd: float) -> bool:
    """The firing test, applied to the screen and to the confirming refit alike."""
    return abs(eps) > CELL_SCALE_TOLERANCE and abs(eps) > INCONSISTENT_SIGMA * esd


def scale_inconsistent(models, mtable, per_values, esd_of) -> list[Diagnostic]:
    """``BANK_SCALE_INCONSISTENT``: normalisation factors that disagree.

    On a vanadium-normalised bank (one declaring no incident spectrum) the
    absolute-normalisation factor is s_t ∝ scale·sinθ/DIFC (Paddison 2025,
    *J. Appl. Cryst.* 58, 1022, eq. 19 of the arXiv v1, with the d⁴·sinθ
    Lorentz factor rietx uses too).  Banks normalised to one vanadium are one
    physical quantity, so their s_t should agree (our inference from the
    equation; the paper reports one bank).  A disagreement points at
    absorption, extinction or normalisation in the outlying bank.
    """
    banks = [h for h, m in enumerate(models) if _is_bank(m)
             and getattr(mtable.instruments[h].source.incident_spectrum, "itype", 0) == 0]
    if len(banks) < 2:
        return []
    out = []
    n_phases = min(len(m.phases) for m in models)
    for ip in range(n_phases):
        rows = []
        for h in banks:
            path = f"hist.{h}.phases.{ip}.scale"
            esd = esd_of(path)
            if esd is None:
                continue
            v = per_values[h]
            q = (v[f"phases.{ip}.scale"] * math.sin(math.radians(0.5 * _bank_angle(mtable, h)))
                 / v["instrument.source.difc"])
            rel = esd / v[f"phases.{ip}.scale"] if v[f"phases.{ip}.scale"] else math.inf
            rows.append((h, q, rel))
        if len(rows) < 2:
            continue
        ref = max(rows, key=lambda t: _bank_angle(mtable, t[0]))
        bad = [(h, q / ref[1] - 1.0, math.hypot(rel, ref[2]))
               for h, q, rel in rows if h != ref[0]]
        bad = [b for b in bad if abs(b[1]) > INCONSISTENT_SIGMA * b[2]]
        if bad:
            worst = max(bad, key=lambda b: abs(b[1]))
            out.append(Diagnostic(
                level="info", code="BANK_SCALE_INCONSISTENT",
                where=[f"hist.{h}.phases.{ip}.scale" for h, _r, _e in bad],
                value=worst[1],
                message=(f"Phase {ip}: the banks' normalisation factors "
                         f"scale·sinθ/DIFC (Paddison 2025; eq. 19 of its arXiv v1) differ from "
                         f"histogram {ref[0]}'s by "
                         + ", ".join(f"{100 * r:+.2g} % (histogram {h}, ± {100 * e:.2g})"
                                     for h, r, e in bad)
                         + ". On banks normalised to one vanadium these are one "
                           "quantity; a difference points at absorption, extinction "
                           "or normalisation in the outlying bank."),
                suggestion=("check the bank's absorption (capillary radius, packing) "
                            "and its vanadium normalisation before reading its ADPs")))
    return out


def sigma_ratio(model, y_calc) -> float | None:
    """Lag-difference scatter over the propagated σ, off every reflection window.

    For each lag k in :data:`SIGMA_LAGS`, the standard deviation of
    ((y − y_calc)[i+k] − (y − y_calc)[i]) / √(σ_i² + σ_{i+k}²) over pairs both
    outside every frozen reflection window; the median over the lags.  1 when
    σ is the channel-to-channel scatter.  ``None`` without a measured σ or
    with too few peak-free pairs.
    """
    n = model.n_points
    inside = np.zeros(n, dtype=bool)
    for idx, _seg in getattr(model, "flat_windows", ()):
        inside[np.asarray(idx, dtype=np.intp)] = True
    free = ~inside
    d = model.y_obs - np.asarray(y_calc, dtype=np.float64)
    s = model.sigma
    ratios = []
    for k in SIGMA_LAGS:
        if k >= n:
            continue
        m = free[:-k] & free[k:]
        if int(m.sum()) < SIGMA_MIN_PAIRS:
            continue
        z = (d[k:] - d[:-k])[m] / np.sqrt(s[k:] ** 2 + s[:-k] ** 2)[m]
        ratios.append(float(np.std(z)))
    return float(np.median(ratios)) if ratios else None


def sigma_suspect(h: int, model, y_calc, *, measured: bool) -> list[Diagnostic]:
    """``BANK_SIGMA_SUSPECT``: σ that is not the bank's own scatter.

    ``measured``: whether the σ is the file's; a √y fallback is not tested.
    """
    ratio = sigma_ratio(model, y_calc) if measured else None
    lo, hi = SIGMA_RATIO_BAND
    if ratio is None or lo <= ratio <= hi:
        return []
    # a residual with no channel-to-channel scatter at all (noiseless or
    # synthetic counts) has ratio exactly 0: the bank carries none of the
    # weight its scatter justifies, and nothing is divided by the ratio
    return [Diagnostic(
        level="warning", code="BANK_SIGMA_SUSPECT", where=[f"hist.{h}"], value=ratio,
        message=(f"Histogram {h}'s channel-to-channel scatter off the reflections is "
                 f"{ratio:.3g} × its esd column (lags {SIGMA_LAGS[0]}-{SIGMA_LAGS[-1]} "
                 f"channels). A joint fit weights each point by 1/σ², so this bank "
                 f"carries {ratio ** 2:.2g} × the weight its counts justify "
                 f"against the others. Measured 0.92-1.28 on HRPD banks and "
                 f"0.77-0.87 on GEM and WISH banks; untested beyond ISIS."),
        suggestion=("check how the bank's σ was propagated through reduction "
                    "(rebinning, smoothing, a σ written as √y on normalised data) "
                    "before quoting the joint esds"))]


def moment_information_kept(model, values, ip: int) -> tuple[float, float] | None:
    """``(f, W_M)`` for phase ``ip`` on one histogram, or ``None``.

    A moment's magnitude reaches a pattern only as m² times the phase's
    scale, and the scale also carries the nuclear lines, so it is the nuclear
    lines that let one histogram tell the two apart.  With y the phase's
    component and y_M its magnetic part (y with every moment modulus set to
    zero, subtracted), the scale's column is ∂y/∂ln s = y and the column of a
    common change of every modulus is ∂y/∂ln μ = 2·y_M.  ``f`` = 1 − ρ² of
    those two columns under the fit's 1/σ² weights: the fraction of this
    histogram's information on the magnitude that survives freeing its scale
    (1 with no scale to fear, 0 when the two are the same column).  Where the
    nuclear and magnetic lines do not overlap it is exactly
    W_N/(W_N + W_M), the nuclear share of the phase's Bragg weight.

    ``W_M`` = Σ(y_M/σ)² is the magnetic Bragg weight; ``None`` when the phase
    has no magnetic data on this histogram, or no magnetic intensity in its
    window.  Extinction couples the two terms; at ``extinction = 0`` the split
    is exact.
    """
    cp = model.phases[ip]
    if getattr(cp, "magnetic", None) is None:
        return None
    dof0 = [f"phases.{ip}.atoms.{j}.moment.dof0" for j in range(cp.sites.n_asym)
            if cp.magnetic.n_dofs(j) > 0]
    if not dof0:
        return None
    zero = dict(values)
    for path in dof0:
        zero[path] = 0.0
    y = np.asarray(model.phase_component(ip, values), dtype=np.float64)
    y_m = y - np.asarray(model.phase_component(ip, zero), dtype=np.float64)
    w = 1.0 / np.asarray(model.sigma, dtype=np.float64) ** 2
    w_m = float(np.sum(y_m * y_m * w))
    w_t = float(np.sum(y * y * w))
    if w_m <= 0.0 or w_t <= 0.0:
        return None
    rho2 = float(np.sum(y * y_m * w)) ** 2 / (w_t * w_m)
    return max(0.0, 1.0 - rho2), w_m


def magnetic_scale_unpinned(models, per_values, *, scale_free, moment_free
                            ) -> list[Diagnostic]:
    """``MAGNETIC_SCALE_UNPINNED``: a bank whose free scale absorbs a moment.

    ``scale_free(h, ip)`` says whether histogram h's scale for phase ip is a
    free column (a held or tied scale pins the moment and is never reported);
    ``moment_free(ip)`` whether any moment modulus of phase ip is free.
    Fires per (bank, phase) where :func:`moment_information_kept` is below
    :data:`MAGNETIC_SCALE_NUCLEAR_FLOOR`, and names the histograms that do pin
    the magnitude, or says none does.  Silent on constant-wavelength
    histograms (the same arithmetic holds there; the code is the
    time-of-flight track's, where low-angle banks see the magnetic lines and
    little else).
    """
    out: list[Diagnostic] = []
    n_phases = min(len(m.phases) for m in models)
    for ip in range(n_phases):
        if not moment_free(ip):
            continue
        kept = {}
        for h, (m, v) in enumerate(zip(models, per_values, strict=True)):
            k = moment_information_kept(m, v, ip)
            if k is not None:
                kept[h] = 1.0 if not scale_free(h, ip) else k[0]
        weak = [h for h, f in kept.items() if f < MAGNETIC_SCALE_NUCLEAR_FLOOR
                and _is_bank(models[h])]
        if not weak:
            continue
        pins = [h for h, f in kept.items() if f >= MAGNETIC_SCALE_NUCLEAR_FLOOR]
        prefix = "hist.{h}." if len(models) > 1 else ""
        for h in weak:
            others = ", ".join(f"histogram {g} keeps {kept[g]:.2g}" for g in pins)
            pinned = (f"The other histograms fix it ({others})." if pins else
                      "No other histogram fixes it, so its esd carries the whole "
                      "scale-moment correlation, and at 0 the two are one "
                      "direction and the moment is not measured.")
            where = prefix.format(h=h) + f"phases.{ip}.scale"
            out.append(Diagnostic(
                level="warning", code="MAGNETIC_SCALE_UNPINNED", where=[where],
                value=kept[h],
                message=(f"Phase {ip}, histogram {h}: with its scale free this "
                         f"bank keeps {kept[h]:.2g} of its information on the "
                         f"moment's magnitude (1 − ρ² of the scale and magnitude "
                         f"columns; the nuclear share of the phase's Bragg weight "
                         f"where the lines do not overlap), because its scale fits "
                         f"its magnetic lines. {pinned} Floor "
                         f"{MAGNETIC_SCALE_NUCLEAR_FLOOR:g}, measured on synthetic "
                         f"banks only."),
                suggestion=("pair the bank with one holding the phase's nuclear "
                            "lines (a joint fit), widen its window to reach them, "
                            "or tie its scale to another bank's")))
    return out
