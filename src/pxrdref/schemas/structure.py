"""Crystal-structure schemas: ``Structure`` → ``Phase`` → ``Atom``.

Conventions
-----------
* Fractional coordinates; occupancies are site fractions in [0, 1].
* Atomic displacement: isotropic ``Biso`` in Å² with ``Biso = 8π² Uiso``
  (International Tables C; anisotropic ``Uij`` arrives in v0.3).
* The structure-factor sum runs over the symmetry orbit of each listed atom
  (asymmetric-unit atoms only should be listed), with reflection multiplicity
  applied to |F|² — the standard Rietveld formulation (Rietveld, 1969,
  J. Appl. Cryst. 2, 65).
"""

from __future__ import annotations

from pydantic import Field, model_validator

from .common import Base, Parameter


class Cell(Base):
    """Unit-cell lengths (Å) and angles (degrees).

    Crystal-system constraints (e.g. cubic ``a=b=c``, α=β=γ=90°) are enforced
    by the parameter-vector compiler from the space group, not stored here.
    """

    a: Parameter
    b: Parameter
    c: Parameter
    alpha: Parameter
    beta: Parameter
    gamma: Parameter

    @classmethod
    def cubic(cls, a: float, *, vary: bool = False) -> "Cell":
        return cls(
            a=Parameter(value=a, vary=vary, min=0.1),
            b=Parameter(value=a, min=0.1),
            c=Parameter(value=a, min=0.1),
            alpha=Parameter(value=90.0),
            beta=Parameter(value=90.0),
            gamma=Parameter(value=90.0),
        )

    def lengths_angles(self) -> tuple[float, float, float, float, float, float]:
        return (self.a.value, self.b.value, self.c.value,
                self.alpha.value, self.beta.value, self.gamma.value)


class Atom(Base):
    """One site in the asymmetric unit."""

    label: str
    species: str  # scattering species, e.g. "La", "B", "Fe3+"
    x: Parameter
    y: Parameter
    z: Parameter
    occ: Parameter = Field(default_factory=lambda: Parameter(value=1.0, min=0.0, max=1.5))
    biso: Parameter = Field(default_factory=lambda: Parameter(value=0.5, min=0.0, max=25.0, unit="A^2"))


class Phase(Base):
    """A crystalline phase: symmetry, cell, atoms, scale, sample broadening."""

    name: str
    space_group: str  # Hermann-Mauguin symbol or number-as-string, resolved via gemmi
    cell: Cell
    atoms: list[Atom]
    scale: Parameter = Field(
        default_factory=lambda: Parameter(value=1.0, vary=False, min=0.0, transform="softplus")
    )
    # Sample contribution to Lorentzian width (deg 2θ units, see profiles.caglioti):
    # size term varies as 1/cosθ (Scherrer), strain term as tanθ.
    lor_size: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, unit="deg", transform="softplus")
    )
    lor_strain: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, unit="deg", transform="softplus")
    )

    @model_validator(mode="after")
    def _nonempty(self) -> "Phase":
        if not self.atoms:
            raise ValueError(f"phase {self.name!r} has no atoms")
        return self


class Structure(Base):
    """One or more phases refined against the same pattern(s)."""

    phases: list[Phase]

    @model_validator(mode="after")
    def _nonempty(self) -> "Structure":
        if not self.phases:
            raise ValueError("structure has no phases")
        return self

    @classmethod
    def from_cif(cls, path: str, *, phase_name: str | None = None) -> "Structure":
        from ..crystallography.cif import structure_from_cif

        return structure_from_cif(path, phase_name=phase_name)

    def to_cif(self, path: str) -> None:
        from ..crystallography.cif import structure_to_cif

        structure_to_cif(self, path)
