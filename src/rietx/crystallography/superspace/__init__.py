"""(3+1)D superspace groups: the operator half of modulated structures (N-W1).

Operators and their algebra (:mod:`.operators`), the groups derived from a
basic space group and a modulation vector, with equivalence and
standardisation (:mod:`.generation`), one-line symbols (:mod:`.symbols`), and
the 3D space group of a commensurate section
(:meth:`SuperspaceGroup.section`).  No atoms, waves, structure factors or
satellites: those are later work packages of issue #258, and they consume the
operator lists built here.  d = 1 only; magnetic superspace groups (the 1′
rule) are N-W2.
"""

from .generation import (
    N_BRAVAIS_CLASSES_D1,
    N_SUPERSPACE_GROUPS_D1,
    bravais_classes,
    canonical_key,
    catalogue,
    count_superspace_groups,
    equivalent,
    family_orbits,
    generate,
    standard_setting,
    standardised,
    superspace_groups,
)
from .operators import (
    IDENTITY,
    ModulationVector,
    Section,
    SuperspaceGroup,
    SuperspaceOperator,
    SuperspaceTransform,
)
from .symbols import ITC_C_EXCEPTIONS, parse_symbol, symbol, symbol_candidates

__all__ = [
    "IDENTITY",
    "ITC_C_EXCEPTIONS",
    "N_BRAVAIS_CLASSES_D1",
    "N_SUPERSPACE_GROUPS_D1",
    "ModulationVector",
    "Section",
    "SuperspaceGroup",
    "SuperspaceOperator",
    "SuperspaceTransform",
    "bravais_classes",
    "canonical_key",
    "catalogue",
    "count_superspace_groups",
    "equivalent",
    "family_orbits",
    "generate",
    "parse_symbol",
    "standard_setting",
    "standardised",
    "superspace_groups",
    "symbol",
    "symbol_candidates",
]
