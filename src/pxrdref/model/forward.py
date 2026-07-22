"""The Rietveld forward model.

Assembles

    y_calc(2θ_i) = y_bkg(2θ_i)
                 + Σ_p Σ_k I_{pk} · Ω(2θ_i − 2θ_{pk}; Γ, η)

where for **Rietveld mode** the integrated reflection intensity is

    I_{pk} = S_p · m_{pk} · |F_{pk}|² · Lp(2θ_{pk})            (Rietveld 1969)

and for **Le Bail mode** I_{pk} are empirical values updated between
least-squares cycles by observed-intensity partitioning (Le Bail, Duroy &
Fourquet, 1988, Mater. Res. Bull. 23, 447).  Ω is the unit-area TCHZ
pseudo-Voigt (profiles.pseudovoigt).

Differentiability invariants honoured here (see plan):
* the reflection list is frozen in the compiled model (regenerate between
  stages);
* each reflection is evaluated only inside a *frozen* point-index window,
  chosen wide enough at compile time that the profile is ≈ 0 at the edges.
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
from .corrections import lorentz_polarization
from .profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
from .profiles.pseudovoigt import pseudo_voigt, tch_gamma_eta

Mode = Literal["rietveld", "lebail"]

#: windows extend ±(WINDOW_FWHM_MULT · Γ_est + WINDOW_MIN_DEG) around each peak
WINDOW_FWHM_MULT = 30.0
WINDOW_MIN_DEG = 0.3


@dataclass
class CompiledPhase:
    reflections: ReflectionSet
    sites: PhaseSites
    # frozen evaluation windows, one (start, stop) point-index pair per reflection
    win: np.ndarray  # (N, 2) int
    lebail_intensity: np.ndarray | None = None  # set in lebail mode


@dataclass
class CompiledModel:
    """Everything frozen for one refinement stage + fast evaluation buffers."""

    tt: np.ndarray          # fit grid (in-range points only), deg 2θ
    y_obs: np.ndarray
    sigma: np.ndarray
    tt_min: float
    tt_max: float
    wavelength: float
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

    def phase_peaks(self, ip: int, values: dict[str, float]) -> tuple[np.ndarray, ...]:
        """Per-reflection positions, widths, mixing and intensities for phase ip."""
        cp = self.phases[ip]
        cell = tuple(values[f"phases.{ip}.cell.{k}"] for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        d = d_spacings(cp.reflections.hkl, *cell)
        pos = two_theta_deg(d, self.wavelength) + values["instrument.zero_shift"]
        theta = 0.5 * (pos - values["instrument.zero_shift"])  # Bragg angle drives widths

        gam_g = gaussian_fwhm(theta, values["instrument.profile.u"],
                              values["instrument.profile.v"], values["instrument.profile.w"])
        gam_l = lorentzian_fwhm(theta,
                                values["instrument.profile.x"] + values[f"phases.{ip}.lor_size"],
                                values["instrument.profile.y"] + values[f"phases.{ip}.lor_strain"])
        gamma, eta = tch_gamma_eta(gam_g, gam_l)

        if self.mode == "lebail":
            intensity = cp.lebail_intensity
        else:
            xyz = np.array([[values[f"phases.{ip}.atoms.{j}.{c}"] for c in ("x", "y", "z")]
                            for j in range(cp.sites.n_asym)])
            occ = np.array([values[f"phases.{ip}.atoms.{j}.occ"] for j in range(cp.sites.n_asym)])
            biso = np.array([values[f"phases.{ip}.atoms.{j}.biso"] for j in range(cp.sites.n_asym)])
            f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites, xyz, occ, biso)
            lp = lorentz_polarization(pos, values["instrument.polarization"])
            intensity = (values[f"phases.{ip}.scale"] * cp.reflections.multiplicity
                         * f2 * lp)
        return pos, gamma, eta, intensity

    def bragg_component(self, values: dict[str, float]) -> np.ndarray:
        y = np.zeros_like(self.tt)
        for ip in range(len(self.phases)):
            cp = self.phases[ip]
            pos, gamma, eta, intensity = self.phase_peaks(ip, values)
            for k in range(len(pos)):
                i0, i1 = cp.win[k]
                if i1 <= i0 or not np.isfinite(pos[k]):
                    continue
                x = self.tt[i0:i1] - pos[k]
                y[i0:i1] += intensity[k] * pseudo_voigt(x, gamma[k], eta[k])
        return y

    def evaluate(self, values: dict[str, float]) -> np.ndarray:
        return self.background(values) + self.bragg_component(values)

    # ------------------------------------------------------------------
    def lebail_update(self, values: dict[str, float], n_cycles: int = 1) -> None:
        """Refresh Le Bail intensities by observed-intensity partitioning.

        For each reflection k with calculated contribution c_ik = I_k·Ω_ik:

            I_k ← Σ_i [c_ik / y_bragg,i] · max(y_obs,i − y_bkg,i, 0) / Σ_i Ω_ik

        which is a fixed point when y_obs = y_calc (Le Bail et al., 1988).
        """
        if self.mode != "lebail":
            raise RuntimeError("lebail_update on a Rietveld-mode model")
        for _ in range(n_cycles):
            bkg = self.background(values)
            net = np.maximum(self.y_obs - bkg, 0.0)
            for ip, cp in enumerate(self.phases):
                pos, gamma, eta, intensity = self.phase_peaks(ip, values)
                n = len(pos)
                profs: list[np.ndarray] = []
                y_bragg = np.zeros_like(self.tt)
                for k in range(n):
                    i0, i1 = cp.win[k]
                    if i1 <= i0 or not np.isfinite(pos[k]):
                        profs.append(np.zeros(0))
                        continue
                    om = pseudo_voigt(self.tt[i0:i1] - pos[k], gamma[k], eta[k])
                    profs.append(om)
                    y_bragg[i0:i1] += intensity[k] * om
                new_int = np.array(intensity, dtype=np.float64)
                for k in range(n):
                    i0, i1 = cp.win[k]
                    om = profs[k]
                    if len(om) == 0 or om.sum() <= 0:
                        continue
                    denom = y_bragg[i0:i1]
                    good = denom > 1e-12
                    if not np.any(good):
                        continue
                    share = np.zeros_like(om)
                    share[good] = intensity[k] * om[good] / denom[good]
                    new_int[k] = float((share * net[i0:i1]).sum() / om.sum())
                cp.lebail_intensity = np.maximum(new_int, 1e-10)


def compile_model(structure: Structure, instrument: Instrument, pattern: PatternData,
                  *, mode: Mode = "rietveld",
                  two_theta_limits: tuple[float, float] | None = None) -> CompiledModel:
    """Freeze reflection lists, orbits, and windows for one stage."""
    mask = pattern.in_range_mask()
    tt_all, y_all, s_all = pattern.tt(), pattern.y(), pattern.sig()
    if two_theta_limits is not None:
        lo, hi = two_theta_limits
        mask &= (tt_all >= lo) & (tt_all <= hi)
    tt, y_obs, sigma = tt_all[mask], y_all[mask], s_all[mask]
    if len(tt) < 10:
        raise ValueError("fewer than 10 points remain in the fit range")
    tt_min, tt_max = float(tt[0]), float(tt[-1])

    wavelength = instrument.source.primary_wavelength
    zero = instrument.zero_shift.value

    phases: list[CompiledPhase] = []
    for phase in structure.phases:
        cell = phase.cell.lengths_angles()
        refl = generate_reflections(phase.space_group, cell, wavelength,
                                    two_theta_max=tt_max - zero + 0.5,
                                    two_theta_min=max(tt_min - zero - 0.5, 0.1))
        sites = compile_phase_sites(phase)

        # frozen windows around compile-time positions
        pos = refl.two_theta(cell, wavelength) + zero
        theta = 0.5 * (pos - zero)
        g_est = gaussian_fwhm(theta, instrument.profile.u.value,
                              instrument.profile.v.value, instrument.profile.w.value)
        l_est = lorentzian_fwhm(theta,
                                instrument.profile.x.value + phase.lor_size.value,
                                instrument.profile.y.value + phase.lor_strain.value)
        gamma_est, _ = tch_gamma_eta(g_est, l_est)
        half = WINDOW_FWHM_MULT * gamma_est + WINDOW_MIN_DEG
        i0 = np.searchsorted(tt, pos - half, side="left")
        i1 = np.searchsorted(tt, pos + half, side="right")
        win = np.column_stack([i0, i1]).astype(np.int64)

        cp = CompiledPhase(reflections=refl, sites=sites, win=win)
        if mode == "lebail":
            cp.lebail_intensity = np.full(len(refl), max(float(np.median(y_obs)), 1.0))
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
        wavelength=wavelength, mode=mode, phases=phases,
        fixed_background=fixed, n_cheb=n_cheb,
        cheb_design=chebyshev_design_matrix(tt, n_cheb, tt_min, tt_max),
    )
