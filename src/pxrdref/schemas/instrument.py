"""Instrument schemas: source, geometry, profile, background.

``Source``/``Geometry``/profile blocks are the pluggable seams for later
neutron/TOF and fundamental-parameters work; v0.1 implements a single
constant-wavelength X-ray source and the Debye-Scherrer (capillary) geometry
used at synchrotron powder beamlines such as APS 11-BM.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import Base, Parameter


class EmissionLine(Base):
    """One wavelength component of the incident spectrum (Å, relative weight)."""

    wavelength: float = Field(gt=0.0)
    weight: float = Field(gt=0.0, default=1.0)


class Source(Base):
    """Constant-wavelength X-ray source.

    ``polarization`` is the fraction K of the beam polarised *perpendicular*
    to the diffraction plane (σ-polarised).  The polarisation factor is

        P(2θ) = K + (1 − K)·cos²2θ

    so K = 0.5 reproduces the unpolarised-beam (1 + cos²2θ)/2, and a
    synchrotron beam diffracting in the vertical plane (E-vector horizontal,
    i.e. σ) has K ≈ 0.99 → an almost flat correction.  This matches the GSAS
    POLA convention used in APS 11-BM instrument-parameter files (Larson &
    Von Dreele, 2004, GSAS manual).
    """

    kind: Literal["xray_cw"] = "xray_cw"
    lines: list[EmissionLine]
    polarization: Parameter = Field(
        default_factory=lambda: Parameter(value=0.5, min=0.0, max=1.0)
    )

    @model_validator(mode="after")
    def _nonempty(self) -> "Source":
        if not self.lines:
            raise ValueError("source has no emission lines")
        return self

    @property
    def primary_wavelength(self) -> float:
        return self.lines[0].wavelength


class Geometry(Base):
    """Diffraction geometry.

    v0.1 supports ``debye_scherrer`` (spinning capillary, synchrotron or lab).
    ``bragg_brentano`` (with sample displacement/transparency) is v0.2.
    """

    kind: Literal["debye_scherrer", "bragg_brentano"] = "debye_scherrer"
    goniometer_radius_mm: float | None = None


class ProfileTCHZ(Base):
    """Thompson-Cox-Hastings pseudo-Voigt width parameters.

    Gaussian variance (in centidegrees², GSAS convention is *not* used —
    everything here is in degrees 2θ):

        Γ_G² = U·tan²θ + V·tanθ + W          (Caglioti et al., 1958)

    Lorentzian FWHM:

        Γ_L = X/cosθ + Y·tanθ

    where the 1/cosθ term is Scherrer (size) broadening and the tanθ term is
    microstrain broadening (document physics, not letters: GSAS and FullProf
    swap the X/Y letter assignment).  Thompson, Cox & Hastings (1987),
    J. Appl. Cryst. 20, 79.
    """

    u: Parameter = Field(default_factory=lambda: Parameter(value=0.0, min=-0.05, max=1.0, unit="deg^2"))
    v: Parameter = Field(default_factory=lambda: Parameter(value=0.0, min=-0.5, max=0.5, unit="deg^2"))
    w: Parameter = Field(
        default_factory=lambda: Parameter(value=1e-3, min=0.0, max=1.0, unit="deg^2", transform="softplus")
    )
    x: Parameter = Field(
        default_factory=lambda: Parameter(value=1e-3, min=0.0, max=1.0, unit="deg", transform="softplus")
    )
    y: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, max=1.0, unit="deg", transform="softplus")
    )


class BackgroundChebyshev(Base):
    """Shifted-Chebyshev background, linear in its coefficients.

    y_bkg(x) = Σ c_n T_n(x), x = 2·(2θ − 2θ_min)/(2θ_max − 2θ_min) − 1.
    Being linear, the Jacobian columns for the coefficients are exact basis
    functions (used by the analytic-Jacobian path).
    """

    kind: Literal["chebyshev"] = "chebyshev"
    coefficients: list[Parameter] = Field(
        default_factory=lambda: [Parameter(value=0.0, vary=False) for _ in range(4)]
    )

    @classmethod
    def with_terms(cls, n: int, *, vary: bool = True) -> "BackgroundChebyshev":
        return cls(coefficients=[Parameter(value=0.0, vary=vary) for _ in range(n)])


class BackgroundFixedPlusChebyshev(Base):
    """A fixed estimated curve (never subtracted; held additively) plus a
    small refinable Chebyshev correction on top.

    The fixed curve typically comes from :func:`pxrdref.background.estimate`
    (arPLS/SNIP).  Holding it inside the model keeps Poisson weights correct.
    """

    kind: Literal["fixed_plus_chebyshev"] = "fixed_plus_chebyshev"
    fixed_two_theta: list[float]
    fixed_intensity: list[float]
    chebyshev: BackgroundChebyshev = Field(default_factory=lambda: BackgroundChebyshev())

    @model_validator(mode="after")
    def _lengths(self) -> "BackgroundFixedPlusChebyshev":
        if len(self.fixed_two_theta) != len(self.fixed_intensity):
            raise ValueError("fixed background arrays differ in length")
        return self


Background = BackgroundChebyshev | BackgroundFixedPlusChebyshev


class Instrument(Base):
    """Everything about the measurement except the sample."""

    source: Source
    geometry: Geometry = Field(default_factory=Geometry)
    zero_shift: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=-0.5, max=0.5, unit="deg")
    )
    profile: ProfileTCHZ = Field(default_factory=ProfileTCHZ)
    background: Background = Field(
        default_factory=lambda: BackgroundChebyshev(), discriminator=None
    )

    @classmethod
    def debye_scherrer(cls, wavelength: float, *, polarization: float = 0.99) -> "Instrument":
        """Synchrotron/capillary preset with a single wavelength.

        ``polarization`` follows the GSAS POLA convention (see :class:`Source`);
        0.99 matches APS 11-BM instrument-parameter files.
        """
        return cls(
            source=Source(
                lines=[EmissionLine(wavelength=wavelength)],
                polarization=Parameter(value=polarization, min=0.0, max=1.0),
            ),
            geometry=Geometry(kind="debye_scherrer"),
        )
