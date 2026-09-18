"""What the fit says about a displacive mode amplitude, and what it could not see.

Three statements per declared mode, and each is something a superstructure
model can get wrong in a way Rwp does not show:

1. **The amplitude, with its esd.**  A is a column of the least-squares
   problem — the mode enters every atom's coordinate row by affine tie
   (``params.vector._collect_distortion_modes``) — so its esd comes from the
   same covariance every other parameter's does, Bérar-Lelann inflation
   included (``Statistics.esd_inflation`` divides it back out).

2. **How far that actually moves an atom.**  An amplitude is a number in the
   units its mode vectors were normalised to, and the number a
   crystallographer judges is the displacement in Å.  Measured on the case
   that made this worth printing: an 84-free-coordinate P2₁/m child of
   Ba₂FeSbSe₅ moved one Fe by 2.8 Å at 3.2σ and reported ``converged``.  A
   distortion of 0.05 Å and a different structure are both "significant"; only
   one of them is a distortion.

3. **Whether the data supports it at all**, as a ratio rather than a floor.
   |F|² is even in A — the mode enters a superstructure reflection odd in A —
   so χ² is stationary at A = 0 and a mode the pattern cannot see is a *flat*
   direction: the fit leaves the amplitude near wherever it was seeded, with an
   esd as large or larger.  ``DISTORTION_MODE_UNSUPPORTED`` is that reading,
   and the honest report of it is "the data does not support this mode", not
   "A = 0.01(3) Å".

The sign is not one of the statements, because it is not measurable: A and −A
give the identical powder pattern, so a refined amplitude is read as |A|.
"""

from __future__ import annotations

import numpy as np

from .schemas import (
    DISTORTION_SIGN_CONVENTION,
    DISTORTION_SUPPORT_SIGMA,
    DistortionEvidence,
    DistortionTotal,
)


def analyse_distortion_modes(structure, values=None, *,
                             esd: dict[str, float] | None = None
                             ) -> list[DistortionEvidence]:
    """One row per declared displacive mode of ``structure``, or an empty list.

    Empty is the honest state on exactly one count and it is not "no
    distortion was found": no phase declares a mode.  A mode is a *declared*
    hypothesis — unlike a satellite candidate, which the report enumerates —
    so there is nothing to report on when none was stated.

    ``values`` is the decoded parameter dict of the fit, read for the refined
    amplitude; without it the amplitudes on the models are used, which is what
    a report built off a structure alone can say.  ``esd`` is the path → esd
    map from ``RefinementResult.parameters``, and the ratio that decides
    ``supported`` needs it: with no esd the row reports ``supported=True`` and
    says in ``note`` that nothing measured one, rather than calling an
    unmeasured amplitude unsupported.

    **Nothing here reads the abscissa** — an amplitude, its esd and a
    Cartesian displacement are functions of the modes, the cell and the
    parameter vector — exactly as ``analyse_moments`` does one module across.
    """
    if structure is None:
        return []
    esd = esd or {}
    out: list[DistortionEvidence] = []
    for ip, phase in enumerate(structure.phases):
        for n, mode in enumerate(getattr(phase, "distortion_modes", ()) or ()):
            path = f"phases.{ip}.distortion_modes.{n}.amplitude"
            amplitude = float(mode.amplitude.value if values is None
                              else values.get(path, mode.amplitude.value))
            unit = mode.unit_displacement_a(phase.cell)
            sigma = esd.get(path)
            moved = sum(1 for v in mode.vectors if any(c != 0.0 for c in v))
            insignificant = (sigma is not None and sigma > 0.0
                             and abs(amplitude) <= DISTORTION_SUPPORT_SIGMA * sigma)
            supported = not insignificant
            if insignificant:
                note = (
                    f"|A| is {abs(amplitude):.3g}, only "
                    f"{abs(amplitude) / sigma:.2g}× its own esd of "
                    f"{sigma:.3g}: |F|² is even in A, so a mode the data "
                    f"cannot see is a flat direction of the least-squares "
                    f"problem and the fit leaves the amplitude near where it "
                    f"was seeded. Read this as unsupported, not as a small "
                    f"distortion; and {DISTORTION_SIGN_CONVENTION}")
            elif sigma is None:
                note = ("no esd was measured for this amplitude — it was held, "
                        "or the stage returned no covariance — so nothing here "
                        "says whether the data supports it; "
                        + DISTORTION_SIGN_CONVENTION)
            else:
                note = (f"the largest atomic displacement this mode states is "
                        f"{abs(amplitude) * unit:.4g} Å; "
                        f"{DISTORTION_SIGN_CONVENTION}")
            out.append(DistortionEvidence(
                phase=phase.name, mode=mode.name, path=path,
                irrep_label=mode.irrep_label, direction=mode.direction,
                k=list(mode.k), parent_site=mode.parent_site or "",
                amplitude=amplitude, amplitude_esd=sigma,
                max_displacement_a=unit,
                displacement_a=abs(amplitude) * unit,
                n_atoms_moved=moved, supported=supported, note=note))
    return out


def analyse_distortion_totals(structure, values=None, *,
                              esd: dict[str, float] | None = None,
                              covariance=None) -> list[DistortionTotal]:
    r"""One row per (k, irrep, direction) component: AMPLIMODES' A_τ (M-3).

    The verdict layer above :func:`analyse_distortion_modes`.  An irrep fixes
    its modes only up to an orthogonal basis of the component, so a single
    A_{τ,m} is a number about a basis somebody chose; A_τ = (Σ_m A²_{τ,m})^½
    and the unit direction a_{τ,m} = A_{τ,m}/A_τ are Perez-Mato, Orobengoa &
    Aroyo (2010), *Acta Cryst.* A**66**, 558, eq (6)–(7), and A_τ is what
    survives that freedom.

    ``covariance`` maps ``(phase index, component index)`` to the physical
    covariance block of that component's amplitudes, **in the component's own
    mode order** — ``ParameterTable.physical_covariance`` returns exactly that.
    With it, σ²(A_τ) = aᵀ·Cov(A)·a, which is the J·Cov·Jᵀ propagation
    :func:`~rietx.optimize.qpa.weight_fractions` established and McCusker
    *et al.* (1999), *J. Appl. Cryst.* **32**, 36, § 10 requires ("the whole
    correlation matrix, not just the diagonal elements").  Without it — a
    loaded result, a replayed one, a report built off a structure alone — only
    the independent approximation from the per-mode ``esd`` map is available,
    and the row says so in ``note`` rather than passing it off as the answer.

    **The grouping is (k, irrep, direction) and not irrep alone.**  Two
    directions of one irrep are two different order parameters with two
    different isotropy subgroups, so summing their squares would add
    amplitudes of structures that are not the same structure.  For every phase
    ``displacive_statement`` builds this is the same grouping as "per irrep",
    since such a phase carries one direction per irrep; it differs only for a
    hand-built multi-direction phase, where the finer grouping is the correct
    one.  :attr:`~rietx.schemas.structure.Phase.distortion_components` is the
    view, M2's, so nothing here re-derives it.
    """
    if structure is None:
        return []
    esd = esd or {}
    out: list[DistortionTotal] = []
    for ip, phase in enumerate(structure.phases):
        modes = list(getattr(phase, "distortion_modes", ()) or ())
        if not modes:
            continue
        # by identity, with the name as the fallback: ``distortion_components``
        # regroups the phase's own ``DistortionMode`` objects rather than
        # copying them, and a mode's name is unique within a phase either way
        by_id = {id(m): n for n, m in enumerate(modes)}
        by_name = {m.name: n for n, m in enumerate(modes)}
        for ic, component in enumerate(phase.distortion_components):
            paths = [
                f"phases.{ip}.distortion_modes."
                f"{by_id.get(id(m), by_name[m.name])}.amplitude"
                for m in component.modes]
            a = np.array([float(values.get(p, m.amplitude.value))
                          if values is not None else float(m.amplitude.value)
                          for p, m in zip(paths, component.modes, strict=True)],
                         dtype=np.float64)
            total = float(np.sqrt(np.dot(a, a)))
            unit = max(m.unit_displacement_a(phase.cell) for m in component.modes)
            sigmas = [esd.get(p) for p in paths]
            measured = [s for s in sigmas if s is not None and s > 0.0]
            block = None if covariance is None else covariance.get((ip, ic))

            if total == 0.0:
                # A_τ = ‖A‖ has no derivative at the origin: the unit direction
                # is 0/0 and every one-sided directional derivative is 1, so
                # there is no Jacobian to propagate a covariance through.  The
                # component states the parent, which is not a measurement of a
                # distortion — but a *held* block at zero is the deliberate
                # A = 0 negative control, and calling that unsupported would be
                # a verdict on a number nobody refined.
                out.append(DistortionTotal(
                    phase=phase.name, irrep_label=component.irrep_label,
                    direction=component.direction, k=list(component.k),
                    modes=[m.name for m in component.modes], paths=paths,
                    amplitude=0.0, unit_direction=[],
                    max_displacement_a=unit, n_modes=len(component.modes),
                    supported=not measured,
                    note=("every amplitude of this component is exactly zero, "
                          "so A_τ = 0, the unit direction {a_τ,m} is "
                          "undefined, and A_τ = ‖A‖ is not differentiable at "
                          "the origin — no esd can be propagated through it. "
                          "The component states the parent structure"
                          + ("" if measured else
                             "; no esd was measured for any of its amplitudes "
                             "either, so nothing here says whether the data "
                             "supports it"))))
                continue

            direction = a / total
            # the gauge: the primary mode (largest |A|, ties by list order) is
            # stated positive and every other sign is read relative to it.  A
            # whole-vector sign flip is the other antiphase domain and is not a
            # different structure, so fixing one component's sign costs nothing
            # and printing an unfixed one would be the confident wrong singleton
            # the FitReport rule forbids.
            primary = int(np.argmax(np.abs(a)))
            domain_sign = 1 if a[primary] >= 0.0 else -1
            direction = direction * domain_sign
            sigma = None
            if block is not None:
                cov = np.asarray(block, dtype=np.float64)
                var = float(direction @ cov @ direction)
                if var > 0.0:
                    sigma = float(np.sqrt(var))
            sigma_indep = None
            if len(measured) == len(paths):
                sigma_indep = float(np.sqrt(sum(
                    (d * s) ** 2 for d, s in zip(direction, sigmas, strict=True))))
            best = sigma if sigma is not None else sigma_indep
            insignificant = best is not None and total <= DISTORTION_SUPPORT_SIGMA * best
            if insignificant:
                note = (
                    f"A_τ is {total:.3g}, only {total / best:.2g}× its own esd "
                    f"of {best:.3g}: the whole order parameter is inside its "
                    f"own uncertainty, which is the basis-independent reading "
                    f"of 'unsupported'. The per-mode rows beneath this one are "
                    f"information about the basis, not the verdict; "
                    f"{DISTORTION_SIGN_CONVENTION}")
            elif best is None:
                note = ("no esd was measured for this component — its "
                        "amplitudes were held, or the stage returned no "
                        "covariance — so nothing here says whether the data "
                        "supports it; " + DISTORTION_SIGN_CONVENTION)
            else:
                note = (
                    f"the order parameter states a largest atomic displacement "
                    f"of {total * unit:.4g} Å. A_τ is basis-independent and the "
                    f"individual A_τ,m beneath it are not; "
                    f"{DISTORTION_SIGN_CONVENTION}")
            if sigma is None and sigma_indep is not None:
                note += ("; the esd is the independent approximation from the "
                         "per-mode esds, because no covariance block was "
                         "available — the correlated value is the one "
                         "McCusker et al. (1999) § 10 asks for")
            out.append(DistortionTotal(
                phase=phase.name, irrep_label=component.irrep_label,
                direction=component.direction, k=list(component.k),
                modes=[m.name for m in component.modes], paths=paths,
                amplitude=total, amplitude_esd=sigma,
                amplitude_esd_independent=sigma_indep,
                unit_direction=[float(d) for d in direction],
                primary_mode=component.modes[primary].name,
                domain_sign=domain_sign,
                max_displacement_a=unit, n_modes=len(component.modes),
                supported=not insignificant, note=note))
    return out
