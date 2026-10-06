"""Does the data want a rigid body to be a different shape? (``RIGID_BODY_MISFIT``)

A rigid body imposes a geometry, and a wrong one still refines to a converged
fit with sensible esds.  Measured on a synthetic lactate pattern: the right body
fitted at GOF 1.01, the same body with one C–C bond 0.3 Å too long at GOF 2.33
(Δχ² ≈ 1.7×10⁴ at equal parameter count), and nothing named the body —
``RESTRAINT_TENSION`` cannot fire for a body, which has no restraint rows.

**The check.**  Per body, two short refinements from the fitted state, each an
internal trial (``telemetry=False``, no history):

* the **body** arm: the body's own DOFs (origin, rotation, torsions) and the
  caller's ``free`` globs;
* the **released** arm: the body removed and its atoms' coordinates freed, held
  near the template by soft restraints on every template bond and bonded angle
  (observational restraints, Waser 1963, *Acta Cryst.* **16**, 1091), with the
  same ``free`` globs.

The two are compared on the **data** χ² (restraint rows excluded, as every
``Statistics`` field is) with the package's two model-comparison tests, both at
the effective sample size N/f² (``optimize.statistics.effective_sample_size``,
#270): Hamilton's R-factor ratio test (Hamilton 1965, *Acta Cryst.* **18**, 502)
at ``alpha`` through :func:`~rietx.report.layer2.hamilton_justified`, and ΔBIC
(Schwarz 1978, *Ann. Statist.* **6**, 461) through
:func:`~rietx.report.layer2.delta_bic`, against ``bic_threshold`` (10, "very
strong": Kass & Raftery 1995, *J. Am. Stat. Assoc.* **90**, 773).  It fires on
the **conjunction**, so a serially correlated residual cannot make a released
molecule's noise-fitting look significant.

**Where.**  The released arm's bond and angle deviations from the template, in
units of their restraint σ, ranked; the message names the worst three.

It is never run inside ``fit()``: it costs two refinements per body, so a
caller asks for it once, before quoting a body's geometry or calling a solve
solved.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.structure import AngleRestraint, BondRestraint, Structure

#: the default significance of the Hamilton test (the conjunction's first half)
MISFIT_ALPHA = 1e-3
#: the default ΔBIC threshold, "very strong" (Kass & Raftery 1995)
MISFIT_BIC = 10.0


@dataclass
class BodyMisfitRow:
    """One body's comparison; ``deviations`` are (label, template, released, Δ/σ)."""

    phase_index: int
    body: str
    chi2_body: float
    chi2_released: float
    n_points: int
    n_effective: float
    n_free_body: int
    n_added: int
    f_statistic: float
    p_value: float
    delta_bic: float
    fires: bool
    deviations: list[tuple[str, float, float, float]] = field(default_factory=list)


@dataclass
class BodyMisfitResult:
    rows: list[BodyMisfitRow]
    diagnostics: list[Diagnostic]


def _element(species: str) -> str:
    return re.match(r"[A-Z][a-z]?", species).group(0)


def _template_geometry(phase, body):
    """Bonded pairs and angles of the body as placed, by the geometry table's
    bonding criterion (covalent radii + ``BOND_SLACK_ANG``)."""
    import gemmi

    from ..model.geometry import BOND_SLACK_ANG
    from ..params.derived import cartesian_frame

    index = {a.label: j for j, a in enumerate(phase.atoms)}
    members = [index[lab] for lab in body.atoms]
    m = np.asarray(cartesian_frame(phase.cell.lengths_angles()))
    xyz = {j: m @ np.array([phase.atoms[j].x.value, phase.atoms[j].y.value,
                            phase.atoms[j].z.value]) for j in members}
    rad = {j: float(gemmi.Element(_element(phase.atoms[j].species)).covalent_r)
           for j in members}
    bonds = []
    for a_i, i in enumerate(members):
        for j in members[a_i + 1:]:
            d = float(np.linalg.norm(xyz[i] - xyz[j]))
            if d <= rad[i] + rad[j] + BOND_SLACK_ANG:
                bonds.append((i, j, d))
    neigh: dict[int, list[int]] = {j: [] for j in members}
    for i, j, _ in bonds:
        neigh[i].append(j)
        neigh[j].append(i)
    angles = []
    for k, nb in neigh.items():
        for a in range(len(nb)):
            for b in range(a + 1, len(nb)):
                i, j = nb[a], nb[b]
                u, v = xyz[i] - xyz[k], xyz[j] - xyz[k]
                ang = math.degrees(math.acos(np.clip(
                    u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1.0, 1.0)))
                if 5.0 < ang < 175.0:         # a straight angle is not restrainable
                    angles.append((i, k, j, ang))
    return members, bonds, angles


def _identity_op(sites, j) -> int:
    ops_r, ops_t = sites.ops[j]
    for k, (r, t) in enumerate(zip(ops_r, ops_t, strict=True)):
        if np.array_equal(np.asarray(r), np.eye(3)) and np.allclose(np.asarray(t), 0.0):
            return k
    raise ValueError(f"atom {j}'s orbit holds no identity operation")


def _fit(structure, instrument, data, globs, max_iter, mode):
    from ..refine import Refinement
    from ..strategy.staged import RefinementPlan, Stage

    ref = Refinement(structure, instrument, history=False)
    res = ref.fit(data, mode=mode, telemetry=False, plan=RefinementPlan(stages=[
        Stage("misfit_check", list(globs), max_iter=max_iter)]))
    return ref, res


def rigid_body_misfit(ref, data, *, free: tuple[str, ...] = (
        "phases.*.scale", "instrument.background.*"),
        alpha: float = MISFIT_ALPHA, bic_threshold: float = MISFIT_BIC,
        bond_sigma: float = 0.02, angle_sigma: float = 2.0,
        max_iter: int = 200) -> BodyMisfitResult:
    """Test every rigid body of ``ref``'s fitted model against ``data``.

    ``free`` are the non-body globs both arms refine (the scale and background
    by default; add the profile or a free atom's DOFs to match your plan).
    ``bond_sigma`` (Å) and ``angle_sigma`` (deg) are the released arm's
    restraint widths: stiff enough to keep the molecule a molecule, loose enough
    that the data can say which bond it disagrees with.  Returns a row per
    body and a ``RIGID_BODY_MISFIT`` warning per body that fails.
    """
    from ..crystallography.structure_factor import compile_phase_sites
    from ..optimize.statistics import _chi2_absolute, effective_sample_size
    from .layer2 import delta_bic, hamilton_justified

    base: Structure = ref.fitted_structure.model_copy(deep=True)
    instrument = ref.fitted_instrument.model_copy(deep=True)
    mode = getattr(ref, "_mode", "rietveld")
    rows: list[BodyMisfitRow] = []
    diagnostics: list[Diagnostic] = []
    for ip, phase in enumerate(base.phases):
        for b, body in enumerate(phase.rigid_bodies):
            bb = f"phases.{ip}.rigid_bodies.{b}"
            _, res_a = _fit(base.model_copy(deep=True), instrument, data,
                            [*free, f"{bb}.origin.dof.*", f"{bb}.rotation.*",
                             f"{bb}.torsions.*.angle"], max_iter, mode)
            # the released arm: same model, this body's atoms freed and held
            # by restraints at the geometry the body placed them in
            members, bonds, angles = _template_geometry(phase, body)
            sites = compile_phase_sites(phase)
            ident = {j: _identity_op(sites, j) for j in members}
            restraints = [BondRestraint(atom_i=i, atom_j=j, target=d, sigma=bond_sigma,
                                        op_index=ident[j]) for i, j, d in bonds]
            restraints += [AngleRestraint(atom_i=i, atom_j=k, atom_k=j, target_deg=a,
                                          sigma=angle_sigma, op_index_i=ident[i],
                                          op_index_k=ident[j]) for i, k, j, a in angles]
            released_phase = phase.model_copy(update={
                "rigid_bodies": [x for x in phase.rigid_bodies if x.name != body.name],
                "restraints": [*phase.restraints, *restraints]}, deep=True)
            released = base.model_copy(deep=True)
            released.phases[ip] = released_phase
            ref_b, res_b = _fit(released, instrument, data,
                                [*free, *(f"phases.{ip}.atoms.{j}.dof.*" for j in members)],
                                max_iter, mode)
            sa, sb = res_a.statistics, res_b.statistics
            chi_a, chi_b = _chi2_absolute(sa), _chi2_absolute(sb)
            n = int(sa.n_points)
            n_eff = effective_sample_size(n, sa.esd_inflation)
            k_a = int(sa.n_free_parameters)
            added = int(sb.n_free_parameters) - k_a
            dof = n_eff - k_a - added
            f_stat = (((chi_a - chi_b) / added) / (chi_b / dof)
                      if added > 0 and dof > 0 and chi_b > 0 else 0.0)
            from scipy.stats import f as f_dist
            p = float(f_dist.sf(f_stat, added, dof)) if added > 0 and dof > 0 else 1.0
            dbic = delta_bic(chi_a, chi_b, n, added, n_effective=n_eff)
            fires = (hamilton_justified(chi_a, chi_b, n, k_a, added, alpha=alpha,
                                        n_effective=n_eff)
                     and dbic > bic_threshold)
            # where: the released geometry against the template, in σ units
            fitted = ref_b.fitted_structure.phases[ip]
            _, bonds_after, angles_after = _template_geometry(
                fitted, body.model_copy(update={"atoms": body.atoms}))
            after_b = {(i, j): d for i, j, d in bonds_after}
            after_a = {(i, k, j): a for i, k, j, a in angles_after}
            labels = [a.label for a in phase.atoms]
            devs = []
            from ..params.derived import cartesian_frame
            m = np.asarray(cartesian_frame(fitted.cell.lengths_angles()))

            def cart(j, ph=fitted, m=m):
                return m @ np.array([ph.atoms[j].x.value, ph.atoms[j].y.value,
                                     ph.atoms[j].z.value])
            for i, j, d in bonds:
                d1 = after_b.get((i, j), float(np.linalg.norm(cart(i) - cart(j))))
                devs.append((f"{labels[i]}–{labels[j]}", d, d1, (d1 - d) / bond_sigma))
            for i, k, j, a in angles:
                a1 = after_a.get((i, k, j))
                if a1 is None:
                    u, v = cart(i) - cart(k), cart(j) - cart(k)
                    a1 = math.degrees(math.acos(np.clip(
                        u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1)))
                devs.append((f"{labels[i]}–{labels[k]}–{labels[j]}", a, a1,
                             (a1 - a) / angle_sigma))
            devs.sort(key=lambda r: -abs(r[3]))
            row = BodyMisfitRow(
                phase_index=ip, body=body.name, chi2_body=chi_a, chi2_released=chi_b,
                n_points=n, n_effective=n_eff, n_free_body=k_a, n_added=added,
                f_statistic=f_stat, p_value=p, delta_bic=dbic, fires=fires,
                deviations=devs)
            rows.append(row)
            if fires:
                worst = "; ".join(
                    f"{lab} {t:.3f} → {r:.3f} ({s:+.1f}σ)" for lab, t, r, s in devs[:3])
                diagnostics.append(Diagnostic(
                    level="warning", code="RIGID_BODY_MISFIT",
                    message=(f"rigid body {body.name!r} (phase {ip}): released as "
                             f"restrained free atoms it fits the data better than as "
                             f"a body — χ² {chi_a:.4g} → {chi_b:.4g} for {added} more "
                             f"parameters, Hamilton p = {p:.2g}, ΔBIC = {dbic:.1f} at "
                             f"N_eff = {n_eff:.0f}.  Largest released deviations "
                             f"from the template: {worst}"),
                    where=[f"phases.{ip}.atoms.{j}" for j in members],
                    suggestion=("the template is the likeliest cause: check the "
                                "named bond and angle values against their source, "
                                "or a wrong atom assignment; a profile or background "
                                "misfit moves every arm alike and does not fire this"),
                    value=dbic))
    return BodyMisfitResult(rows=rows, diagnostics=diagnostics)
