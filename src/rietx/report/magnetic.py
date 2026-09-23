"""What the fit says about a moment, and what the powder could not see.

Three statements, per magnetic site, and each of them is a thing a moment
model can get wrong in a way Rwp does not show:

1. **The magnitude, with its esd.**  |m| is the refined modulus DOF, so it is
   a column of the least-squares problem and its esd comes from the same
   covariance every other parameter's does — Bérar-Lelann inflation included
   (``Statistics.esd_inflation`` divides it back out).  The crystal-axis
   components beside it are *derived*: they carry no esd, because the direction
   they encode is either undeterminable (in which case an esd would be a number
   about nothing) or determined, in which case the angle DOF carries it.

2. **The direction the powder cannot determine.**  A cubic collinear structure
   measures |m| and nothing about its direction; a uniaxial one measures the
   angle to the unique axis and nothing about the azimuth (Shirane, 1959,
   *Acta Cryst.* **12**, 282).  Those directions come back **held**, with the
   DOF named, rather than as a small number with a small esd.

3. **Which approximation is in force.**  f(s) = ⟨j₀⟩ for a spin-only 3d ion,
   f(s) = ⟨j₀⟩ + (2/g − 1)⟨j₂⟩ for a rare earth — the difference FullProf's
   table names apart as ``MHO3`` and ``JHO3`` for the same ion.  A report that
   does not say which one it used cannot be checked.

And the fourth statement, which is a refusal rather than a number: a moment
whose modulus sits at its floor is **unsupported**, not small.  |F_m|² ∝ m², so
the column vanishes with the moment; a paramagnetic pattern drives the modulus
to nothing and every direction flat with it, and the honest report of that is
"the data does not support a moment here", not "0.02(1) μ_B".
"""

from __future__ import annotations

import math

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.structure import MOMENT_FLOOR_MU_B
from .schemas import (
    MOMENT_PAIR_RHO_MIN,
    MOMENT_SUPPORT_SIGMA,
    MomentEvidence,
)


def analyse_moments(model, values, structure=None, *,
                    held: list[str] | None = None,
                    esd: dict[str, float] | None = None,
                    correlations: list | None = None,
                    ) -> list[MomentEvidence]:
    """One row per magnetic site of the compiled model, or an empty list.

    Empty is the honest state on three counts and none of them is "no moment
    was found": no compiled model was supplied, no phase declares one, or the
    histogram carries no magnetic term at all — an X-ray one, where it is
    identically zero and the moment was never observed.  The test is
    ``cp.magnetic``, the frozen block the compile attaches exactly when
    ``forward.magnetic_wanted`` says so, so this function needs no opinion
    about radiations of its own.

    **Nothing here reads the abscissa**: the
    modulus, its esd, the crystal-axis components, the approximation in force
    and the free and unmeasured directions are all functions of the moment
    DOFs, the cell and the operator list, and no field of a
    :class:`~rietx.report.schemas.MomentEvidence` names an angle or a flight
    time.  :func:`rietx.build_report` therefore calls this above its axis
    gate.

    ``correlations`` (Q5) is the fit's own worst-|ρ| list —
    ``RefinementResult.identifiability.top_correlations`` — the one place a
    completed fit's covariance survives past fit time (WP-1055/-1056; the raw
    Jacobian itself is never serialized).  Two rows whose ``dof0`` paths
    appear there with |ρ| >= :data:`~.schemas.MOMENT_PAIR_RHO_MIN` are a
    powder-degenerate pair (S2(a,b)-shaped: ``isotropy.determinable_amplitudes``
    would have called this the same rank deficiency, pre-fit, on the
    candidate's own amplitude Jacobian) — see :func:`_pair_degenerate_moments`.
    ``None`` (the default) leaves every row exactly as before Q5: a fit whose
    top-|ρ| list was not passed in, or that never measured one, reports each
    modulus on its own, which is the honest state when nothing said otherwise
    — never "these are not paired".
    """
    if model is None:
        return []
    held_set = set(held or ())
    out: list[MomentEvidence] = []
    for ip, cp in enumerate(model.phases):
        msites = getattr(cp, "magnetic", None)
        if msites is None:
            continue
        phase_name = (structure.phases[ip].name if structure is not None
                      else f"phases.{ip}")
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        for j in range(msites.n_asym):
            if not msites.carries[j]:
                continue
            out.append(_row(model, values, ip, j, cp, msites, phase_name,
                            cell, held_set, structure, esd or {}))
    if correlations:
        out = _pair_degenerate_moments(out, correlations)
    return out


def _pair_degenerate_moments(rows: list[MomentEvidence],
                             correlations: list) -> list[MomentEvidence]:
    """Q5: fold a powder-degenerate pair into one measured number.

    ``isotropy.analyse`` computes, pre-fit, how many of a candidate's free
    amplitudes a powder can determine at all (``determinable_amplitudes``'s
    SVD rank); when that count is short of the free count, two sites' moduli
    are not separately measured, only their combination is.  The signature of
    exactly that at *fit* time is |rho| -> 1 between the two ``dof0`` columns
    of the covariance — a rank-1 direction where 2 were free is what a
    correlation of 1 *is* — so ``correlations`` (the fit's own worst-|rho|
    list, the one place the covariance survives past fit time) is read
    instead of re-deriving the candidate.

    Only pairs (never a larger group: ``CorrelationPair`` is inherently
    two-wide, and "moment pair" is what WP-1327's own vocabulary for this
    names).  A row already claimed by an earlier, more strongly correlated
    pair is not claimed twice — the greedy match by |rho|, worst first, is
    what keeps this well-defined when more than one pair in a phase crosses
    the bar.
    """
    by_path = {r.path: i for i, r in enumerate(rows) if r.path}
    claimed: set[str] = set()
    updated = list(rows)
    ranked = sorted(
        (c for c in correlations
         if abs(getattr(c, "rho", 0.0)) >= MOMENT_PAIR_RHO_MIN
         and c.path_a in by_path and c.path_b in by_path),
        key=lambda c: -abs(c.rho))
    for c in ranked:
        if c.path_a in claimed or c.path_b in claimed:
            continue
        ia, ib = by_path[c.path_a], by_path[c.path_b]
        a, b = updated[ia], updated[ib]
        if a.magnitude_esd is None or b.magnitude_esd is None:
            continue
        m = math.sqrt(a.magnitude ** 2 + b.magnitude ** 2)
        if m <= 0.0:
            continue
        cov_ab = c.rho * a.magnitude_esd * b.magnitude_esd
        var_m = ((a.magnitude / m) ** 2 * a.magnitude_esd ** 2
                 + (b.magnitude / m) ** 2 * b.magnitude_esd ** 2
                 + 2.0 * (a.magnitude / m) * (b.magnitude / m) * cov_ab)
        esd_m = math.sqrt(max(var_m, 0.0))
        note = (f"not separately determined: this modulus and {b.atom}'s "
                f"({b.path}) are correlated at rho={c.rho:.3f} — the powder "
                f"measures their quadrature sum, sqrt(m_a^2 + m_b^2) = "
                f"{m:.3f} +/- {esd_m:.3f}, and not each on its own "
                f"(MOMENT_PAIR_DEGENERATE)")
        note_b = (f"not separately determined: this modulus and {a.atom}'s "
                  f"({a.path}) are correlated at rho={c.rho:.3f} — the powder "
                  f"measures their quadrature sum, sqrt(m_a^2 + m_b^2) = "
                  f"{m:.3f} +/- {esd_m:.3f}, and not each on its own "
                  f"(MOMENT_PAIR_DEGENERATE)")
        updated[ia] = a.model_copy(update={
            "paired_with": [b.path], "paired_magnitude": m,
            "paired_magnitude_esd": esd_m, "note": note})
        updated[ib] = b.model_copy(update={
            "paired_with": [a.path], "paired_magnitude": m,
            "paired_magnitude_esd": esd_m, "note": note_b})
        claimed.add(c.path_a)
        claimed.add(c.path_b)
    return updated


def moment_pair_diagnostics(rows: list[MomentEvidence]) -> list[Diagnostic]:
    """``MOMENT_PAIR_DEGENERATE`` (info), one per pair :func:`analyse_moments`
    folded (Q5) — never twice, and never for an ordinary row."""
    out: list[Diagnostic] = []
    seen: set[frozenset] = set()
    for r in rows:
        if not r.paired_with:
            continue
        pair = frozenset([r.path, *r.paired_with])
        if pair in seen or len(pair) != 2:
            continue
        seen.add(pair)
        other = next(p for p in r.paired_with)
        out.append(Diagnostic(
            level="info", code="MOMENT_PAIR_DEGENERATE",
            message=(f"{r.path} and {other} are a powder-degenerate moment "
                     f"pair: the fit determines their quadrature sum, "
                     f"sqrt(m_a^2 + m_b^2) = {r.paired_magnitude:.3f} +/- "
                     f"{r.paired_magnitude_esd:.3f}, and not each modulus "
                     f"separately"),
            where=[r.path, other], value=r.paired_magnitude))
    return out


def _row(model, values, ip, j, cp, msites, phase_name, cell, held_set,
         structure, esd) -> MomentEvidence:
    from ..crystallography.magnetic.moments import DOF_NAMES, moment_from_dofs
    from ..crystallography.magnetic.operators import moment_magnitude

    base = f"phases.{ip}.atoms.{j}.moment"
    n = msites.n_dofs(j)
    dofs = np.array([values[f"{base}.dof{k}"] for k in range(n)])
    components = moment_from_dofs(msites.frames[j], dofs)
    modulus = abs(float(dofs[0])) if n else 0.0
    names = DOF_NAMES[n]
    unmeasured = [names[k] for k in range(1, n) if f"{base}.dof{k}" in held_set]
    label = (structure.phases[ip].atoms[j].label if structure is not None
             else f"atoms.{j}")
    sigma = esd.get(f"{base}.dof0")
    at_floor = modulus <= MOMENT_FLOOR_MU_B
    insignificant = sigma is not None and modulus <= MOMENT_SUPPORT_SIGMA * sigma
    supported = not (at_floor or insignificant)
    note = ""
    if not supported:
        # the reason is quoted, because the two are different readings: a
        # modulus driven to the floor is a fit that removed the magnetic
        # intensity outright, while one that is merely inside its own esd is
        # a fit that could not tell it from none.  Both are "unsupported";
        # only the second has a ratio worth printing.
        why = (f"is at its floor ({MOMENT_FLOOR_MU_B:g} μ_B)" if at_floor
               else f"is {modulus:.3g} μ_B, only {modulus / sigma:.2g}× its "
                    f"own esd of {sigma:.3g}")
        note = (f"the modulus {why}: |F_m|² is proportional to m², so a "
                f"moment the data cannot see is a flat direction of the "
                f"least-squares problem and the fit leaves it at nothing. "
                f"Read this as unsupported, not as a small moment")
    elif unmeasured:
        note = (f"the powder average does not determine "
                f"{', '.join(unmeasured)} on this site; "
                f"{'it is' if len(unmeasured) == 1 else 'they are'} held, and "
                f"the direction reported is the one it was stated with")
    return MomentEvidence(
        phase=phase_name, atom=label, ion=msites.ions[j] or "",
        path=f"{base}.dof0",
        magnitude=modulus, magnitude_esd=sigma,
        magnitude_from_components=float(moment_magnitude(components, cell)),
        crystalaxis=[float(c) for c in components],
        approximation=msites.approximations[j] or "",
        free_directions=list(names[1:]),
        unmeasured_directions=unmeasured,
        supported=supported,
        note=note,
    )
