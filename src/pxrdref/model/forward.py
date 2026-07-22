"""The Rietveld forward model.

Assembles

    y_calc(2θ_i) = y_bkg(2θ_i)
                 + Σ_p Σ_l Σ_k I_{pk} · w_l · Ω_lk(2θ_i)

where the sums run over phases p, source emission lines l (Kα1/Kα2 …, each
diffracting at its own Bragg angle so the splitting grows with tanθ) and
reflections k.  For **Rietveld mode** the integrated reflection intensity is

    I_{pk} = S_p · m_{pk} · |F_{pk}|² · Lp(2θ_{lk})            (Rietveld 1969)

(|F|² depends only on sinθ/λ = 1/2d and is shared across lines; Lp is
evaluated per line) and for **Le Bail mode** I_{pk} are empirical per-hkl
values updated between least-squares cycles by observed-intensity
partitioning summed over lines (Le Bail, Duroy & Fourquet, 1988, Mater. Res.
Bull. 23, 447).  Ω_lk is the unit-area TCHZ pseudo-Voigt
(profiles.pseudovoigt), optionally smeared by the Finger-Cox-Jephcoat
axial-divergence aberration (profiles.fcj) into a fixed-node quadrature sum
of images that still integrates to exactly 1.

Peak positions:  2θ_lk = 2θ_Bragg(d_k, λ_l) + zero
                       [+ displacement/transparency shifts, Bragg-Brentano]

Differentiability invariants honoured here (see docs/ROADMAP.md):
* the reflection list is frozen in the compiled model (regenerate between
  stages);
* each (line, reflection) pair is evaluated only inside a *frozen*
  point-index window, chosen wide enough at compile time (incl. the FCJ
  smear extent) that the profile is ≈ 0 at the edges;
* FCJ quadrature node counts are frozen per stage; node positions follow
  the refined parameters smoothly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from ..background.models import chebyshev_design_matrix, interpolate_fixed
from ..crystallography.lattice import d_spacings, two_theta_deg
from ..crystallography.structure_factor import (
    PhaseSites,
    compile_phase_sites,
    structure_factors_squared,
)
from ..crystallography.symmetry import ReflectionSet, generate_reflections
from ..schemas.instrument import BackgroundChebyshev, BackgroundFixedPlusChebyshev, Instrument
from ..schemas.pattern import PatternData
from ..schemas.structure import Structure
from .corrections import (
    displacement_shift_deg,
    lorentz_polarization,
    transparency_shift_deg,
)
from .profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
from .profiles.fcj import fcj_extent_deg, fcj_node_count, fcj_offsets_weights
from .profiles.pseudovoigt import pseudo_voigt, tch_gamma_eta

Mode = Literal["rietveld", "lebail"]

#: windows extend ±(WINDOW_FWHM_MULT · Γ_est + WINDOW_MIN_DEG + FCJ extent)
WINDOW_FWHM_MULT = 30.0
WINDOW_MIN_DEG = 0.3
#: when the axial S/L, H/L parameters are about to be *refined* from zero,
#: quadrature nodes are sized as if they were at least this large, so the
#: finite-difference Jacobian sees a live parameter instead of a frozen
#: zero-node profile
AXIAL_SIZING_FLOOR = 0.02


@dataclass
class CompiledPhase:
    reflections: ReflectionSet
    sites: PhaseSites
    # frozen evaluation windows, one (start, stop) point-index pair per
    # (emission line, reflection)
    win: np.ndarray  # (n_lines, N, 2) int
    # frozen FCJ quadrature node counts, 0 → symmetric peak
    fcj_n: np.ndarray  # (n_lines, N) int
    lebail_intensity: np.ndarray | None = None  # (N,) per hkl, set in lebail mode


@dataclass
class CompiledModel:
    """Everything frozen for one refinement stage + fast evaluation buffers."""

    tt: np.ndarray          # fit grid (in-range points only), deg 2θ
    y_obs: np.ndarray
    sigma: np.ndarray
    tt_min: float
    tt_max: float
    wavelength: float                 # primary line, used for tick positions
    line_wavelengths: tuple[float, ...]
    geometry_kind: str
    radius_mm: float | None
    mode: Mode
    phases: list[CompiledPhase]
    fixed_background: np.ndarray | None  # sampled on tt, or None
    n_cheb: int
    cheb_design: np.ndarray  # (n_cheb, n_points)
    meta: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    def background(self, values: dict[str, float]) -> np.ndarray:
        coeffs = np.array([values[f"instrument.background.c{n}"] for n in range(self.n_cheb)])
        y = coeffs @ self.cheb_design
        if self.fixed_background is not None:
            y = y + self.fixed_background
        return y

    def _position_shift_deg(self, theta: np.ndarray, tt_bragg: np.ndarray,
                            values: dict[str, float]) -> np.ndarray | float:
        """Detector-space peak shifts beyond the Bragg angle (zero + geometry)."""
        shift = values["instrument.zero_shift"]
        if self.geometry_kind == "bragg_brentano":
            s = values["instrument.geometry.sample_displacement"]
            if s != 0.0:
                shift = shift + displacement_shift_deg(theta, s, self.radius_mm)
            t = values["instrument.geometry.sample_transparency"]
            if t != 0.0:
                shift = shift + transparency_shift_deg(tt_bragg, t)
        return shift

    def phase_peaks(self, ip: int, values: dict[str, float]
                    ) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
        """Per-line (positions, widths, mixing, intensities) for phase ip.

        Returns one (pos, gamma, eta, intensity) tuple per emission line;
        arrays run over the frozen reflection list.  ``intensity`` already
        carries the line weight (and Lp per line in Rietveld mode).
        """
        cp = self.phases[ip]
        cell = tuple(values[f"phases.{ip}.cell.{k}"] for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        d = d_spacings(cp.reflections.hkl, *cell)

        if self.mode == "lebail":
            base = cp.lebail_intensity
        else:
            xyz = np.array([[values[f"phases.{ip}.atoms.{j}.{c}"] for c in ("x", "y", "z")]
                            for j in range(cp.sites.n_asym)])
            occ = np.array([values[f"phases.{ip}.atoms.{j}.occ"] for j in range(cp.sites.n_asym)])
            biso = np.array([values[f"phases.{ip}.atoms.{j}.biso"] for j in range(cp.sites.n_asym)])
            # |F|² samples the form factors at sinθ/λ = 1/2d — line-independent
            f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites, xyz, occ, biso)
            base = values[f"phases.{ip}.scale"] * cp.reflections.multiplicity * f2

        out = []
        for il, lam in enumerate(self.line_wavelengths):
            w_line = values[f"instrument.source.lines.{il}.weight"]
            tt_bragg = two_theta_deg(d, lam)
            theta = 0.5 * tt_bragg  # Bragg angle drives widths and Lp
            pos = tt_bragg + self._position_shift_deg(theta, tt_bragg, values)
            gam_g = gaussian_fwhm(theta, values["instrument.profile.u"],
                                  values["instrument.profile.v"], values["instrument.profile.w"])
            gam_l = lorentzian_fwhm(theta,
                                    values["instrument.profile.x"] + values[f"phases.{ip}.lor_size"],
                                    values["instrument.profile.y"] + values[f"phases.{ip}.lor_strain"])
            gamma, eta = tch_gamma_eta(gam_g, gam_l)
            if self.mode == "lebail":
                intensity = base * w_line
            else:
                intensity = base * w_line * lorentz_polarization(tt_bragg, values["instrument.polarization"])
            out.append((pos, gamma, eta, intensity))
        return out

    def _reflection_profile(self, cp: CompiledPhase, il: int, k: int,
                            pos_k: float, gamma_k: float, eta_k: float,
                            sl: float, hl: float) -> np.ndarray | None:
        """Unit-area profile of one (line, reflection) on its frozen window."""
        i0, i1 = cp.win[il, k]
        if i1 <= i0 or not np.isfinite(pos_k):
            return None
        x = self.tt[i0:i1]
        n_fcj = int(cp.fcj_n[il, k])
        if n_fcj == 0:
            return pseudo_voigt(x - pos_k, gamma_k, eta_k)
        # FCJ images computed at the apparent position: the ≤0.1° detector
        # shifts change the aberration geometry negligibly (≪ node spacing)
        phi, omega = fcj_offsets_weights(pos_k, sl, hl, n_fcj)
        return omega @ pseudo_voigt(x[None, :] - phi[:, None], gamma_k, eta_k)

    def phase_component(self, ip: int, values: dict[str, float]) -> np.ndarray:
        """Bragg contribution of one phase (used by the analytic scale Jacobian)."""
        y = np.zeros_like(self.tt)
        cp = self.phases[ip]
        sl = values["instrument.geometry.axial_sl"]
        hl = values["instrument.geometry.axial_hl"]
        for il, (pos, gamma, eta, intensity) in enumerate(self.phase_peaks(ip, values)):
            for k in range(len(pos)):
                prof = self._reflection_profile(cp, il, k, pos[k], gamma[k], eta[k], sl, hl)
                if prof is None:
                    continue
                i0, i1 = cp.win[il, k]
                y[i0:i1] += intensity[k] * prof
        return y

    def bragg_component(self, values: dict[str, float]) -> np.ndarray:
        y = np.zeros_like(self.tt)
        for ip in range(len(self.phases)):
            y += self.phase_component(ip, values)
        return y

    def evaluate(self, values: dict[str, float]) -> np.ndarray:
        return self.background(values) + self.bragg_component(values)

    # ------------------------------------------------------------------
    def lebail_update(self, values: dict[str, float], n_cycles: int = 1) -> None:
        """Refresh Le Bail intensities by observed-intensity partitioning.

        Per-hkl intensities are shared across emission lines: reflection k
        contributes through every line l with profile mass w_l·Ω_lk, so

            I_k ← Σ_l Σ_i [I_k·w_l·Ω_lk,i / y_bragg,i] · max(y_obs,i − y_bkg,i, 0)
                  / Σ_l w_l·Σ_i Ω_lk,i

        which is a fixed point when y_obs = y_calc (Le Bail et al., 1988).
        """
        if self.mode != "lebail":
            raise RuntimeError("lebail_update on a Rietveld-mode model")
        sl = values["instrument.geometry.axial_sl"]
        hl = values["instrument.geometry.axial_hl"]
        for _ in range(n_cycles):
            bkg = self.background(values)
            net = np.maximum(self.y_obs - bkg, 0.0)
            for ip, cp in enumerate(self.phases):
                peaks = self.phase_peaks(ip, values)
                n = len(cp.reflections)
                n_lines = len(self.line_wavelengths)
                profs: list[list[np.ndarray | None]] = []
                y_bragg = np.zeros_like(self.tt)
                for il, (pos, gamma, eta, intensity) in enumerate(peaks):
                    row: list[np.ndarray | None] = []
                    for k in range(n):
                        om = self._reflection_profile(cp, il, k, pos[k], gamma[k], eta[k], sl, hl)
                        row.append(om)
                        if om is not None:
                            i0, i1 = cp.win[il, k]
                            y_bragg[i0:i1] += intensity[k] * om
                    profs.append(row)
                new_int = np.asarray(cp.lebail_intensity, dtype=np.float64).copy()
                for k in range(n):
                    num = 0.0
                    den = 0.0
                    for il in range(n_lines):
                        om = profs[il][k]
                        if om is None or om.sum() <= 0:
                            continue
                        i0, i1 = cp.win[il, k]
                        denom = y_bragg[i0:i1]
                        good = denom > 1e-12
                        if not np.any(good):
                            continue
                        intensity = peaks[il][3]
                        share = np.zeros_like(om)
                        share[good] = intensity[k] * om[good] / denom[good]
                        w_line = values[f"instrument.source.lines.{il}.weight"]
                        num += float((share * net[i0:i1]).sum())
                        den += w_line * float(om.sum())
                    if den > 0.0:
                        new_int[k] = num / den
                cp.lebail_intensity = np.maximum(new_int, 1e-10)


def compile_model(structure: Structure, instrument: Instrument, pattern: PatternData,
                  *, mode: Mode = "rietveld",
                  two_theta_limits: tuple[float, float] | None = None,
                  free_paths: set[str] | None = None) -> CompiledModel:
    """Freeze reflection lists, orbits, windows and FCJ nodes for one stage.

    ``free_paths`` (the parameters the coming stage will refine) only affects
    *sizing* decisions: when the axial parameters are free, FCJ nodes are
    allocated even if their current values are still zero.
    """
    mask = pattern.in_range_mask()
    tt_all, y_all, s_all = pattern.tt(), pattern.y(), pattern.sig()
    if two_theta_limits is not None:
        lo, hi = two_theta_limits
        mask &= (tt_all >= lo) & (tt_all <= hi)
    tt, y_obs, sigma = tt_all[mask], y_all[mask], s_all[mask]
    if len(tt) < 10:
        raise ValueError("fewer than 10 points remain in the fit range")
    tt_min, tt_max = float(tt[0]), float(tt[-1])

    lams = tuple(line.wavelength for line in instrument.source.lines)
    lam_gen = min(lams)  # smallest λ → smallest 2θ → largest d-sphere needed
    zero = instrument.zero_shift.value
    geom = instrument.geometry

    # FCJ sizing values (floored when the axial parameters are about to refine)
    free_paths = free_paths or set()
    axial_free = ("instrument.geometry.axial_sl" in free_paths
                  or "instrument.geometry.axial_hl" in free_paths)
    sl_eff = geom.axial_sl.value
    hl_eff = geom.axial_hl.value
    if axial_free:
        sl_eff = max(sl_eff, AXIAL_SIZING_FLOOR)
        hl_eff = max(hl_eff, AXIAL_SIZING_FLOOR)
    fcj_on = sl_eff > 0.0 and hl_eff > 0.0

    # a reflection is kept if *any* line lands in range: the min-λ line sits
    # lowest, so generate with λ_min and translate the low-2θ cutoff from the
    # max-λ line's frame (same d ⇒ sinθ ∝ λ)
    lo_eff = max(tt_min - zero - 0.5, 0.1)
    hi_eff = tt_max - zero + 0.5
    sin_lo = np.sin(np.radians(lo_eff / 2.0)) * lam_gen / max(lams)
    gen_min = max(2.0 * np.degrees(np.arcsin(min(sin_lo, 1.0))), 0.05)

    def _shift_est(theta: np.ndarray, tt_bragg: np.ndarray) -> np.ndarray | float:
        shift = zero
        if geom.kind == "bragg_brentano":
            s = geom.sample_displacement.value
            if s != 0.0:
                shift = shift + displacement_shift_deg(theta, s, geom.goniometer_radius_mm)
            t = geom.sample_transparency.value
            if t != 0.0:
                shift = shift + transparency_shift_deg(tt_bragg, t)
        return shift

    phases: list[CompiledPhase] = []
    for phase in structure.phases:
        cell = phase.cell.lengths_angles()
        refl = generate_reflections(phase.space_group, cell, lam_gen,
                                    two_theta_max=hi_eff, two_theta_min=gen_min)
        sites = compile_phase_sites(phase)

        n = len(refl)
        n_lines = len(lams)
        win = np.zeros((n_lines, n, 2), dtype=np.int64)
        fcj_n = np.zeros((n_lines, n), dtype=np.int64)
        for il, lam in enumerate(lams):
            tt_bragg = refl.two_theta(cell, lam)
            theta = 0.5 * tt_bragg
            pos = tt_bragg + _shift_est(theta, tt_bragg)
            g_est = gaussian_fwhm(theta, instrument.profile.u.value,
                                  instrument.profile.v.value, instrument.profile.w.value)
            l_est = lorentzian_fwhm(theta,
                                    instrument.profile.x.value + phase.lor_size.value,
                                    instrument.profile.y.value + phase.lor_strain.value)
            gamma_est, _ = tch_gamma_eta(g_est, l_est)
            half = WINDOW_FWHM_MULT * gamma_est + WINDOW_MIN_DEG
            if fcj_on:
                half = half + fcj_extent_deg(pos, sl_eff, hl_eff)
            valid = np.isfinite(pos)
            pos_v = np.where(valid, pos, 0.0)
            half_v = np.where(valid, half, 0.0)
            i0 = np.searchsorted(tt, pos_v - half_v, side="left")
            i1 = np.searchsorted(tt, pos_v + half_v, side="right")
            i0[~valid] = 0
            i1[~valid] = 0
            win[il, :, 0], win[il, :, 1] = i0, i1
            if fcj_on:
                for k in range(n):
                    if valid[k] and i1[k] > i0[k]:
                        fcj_n[il, k] = fcj_node_count(float(pos[k]), float(gamma_est[k]),
                                                      sl_eff, hl_eff)

        cp = CompiledPhase(reflections=refl, sites=sites, win=win, fcj_n=fcj_n)
        if mode == "lebail":
            cp.lebail_intensity = np.full(n, max(float(np.median(y_obs)), 1.0))
        phases.append(cp)

    # background compilation
    bkg = instrument.background
    if isinstance(bkg, BackgroundChebyshev):
        n_cheb = len(bkg.coefficients)
        fixed = None
    elif isinstance(bkg, BackgroundFixedPlusChebyshev):
        n_cheb = len(bkg.chebyshev.coefficients)
        fixed = interpolate_fixed(tt, np.asarray(bkg.fixed_two_theta),
                                  np.asarray(bkg.fixed_intensity))
    else:  # pragma: no cover - schema exhausts the union
        raise TypeError(f"unsupported background model {type(bkg).__name__}")

    return CompiledModel(
        tt=tt, y_obs=y_obs, sigma=sigma, tt_min=tt_min, tt_max=tt_max,
        wavelength=instrument.source.primary_wavelength,
        line_wavelengths=lams,
        geometry_kind=geom.kind, radius_mm=geom.goniometer_radius_mm,
        mode=mode, phases=phases,
        fixed_background=fixed, n_cheb=n_cheb,
        cheb_design=chebyshev_design_matrix(tt, n_cheb, tt_min, tt_max),
    )
