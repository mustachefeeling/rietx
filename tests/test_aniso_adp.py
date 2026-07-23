"""Anisotropic displacement parameters (WP-0303).

Structures used here on purpose:
* NAC, Na₂Ca₃Al₂F₁₄ (I2₁3, COD 1000236) — the real acceptance structure, whose
  CIF carries published U^ij for six sites spanning three different site
  symmetries (2-fold, 3-fold, general).  Any constraint error shows up as a
  mismatch against numbers someone else published.
* Rutile TiO₂ (P4₂/mnm) — Ti on 2a (4/mmm..), O on 4f (m.mm): both sites carry
  the U11 = U22 tie that a transposed rotation would silently break.
* A hexagonal toy — the case where the isotropic limit is *not* U_ij = Uiso·δ_ij
  (γ* = 60° ⇒ U12 = Uiso/2), which is the cheapest guard against pretending the
  CIF U^ij tensor lives in an orthonormal frame.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from pxrdref.crystallography import adp
from pxrdref.schemas.common import Parameter
from pxrdref.schemas.structure import AnisoU, Atom, Cell

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"


def make_hex_cell() -> Cell:
    return Cell(
        a=Parameter(value=3.0, min=0.1), b=Parameter(value=3.0, min=0.1),
        c=Parameter(value=5.0, min=0.1), alpha=Parameter(value=90.0),
        beta=Parameter(value=90.0), gamma=Parameter(value=120.0),
    )


# -- schema ------------------------------------------------------------


def test_aniso_block_json_round_trip():
    atom = Atom(
        label="Fe", species="Fe",
        x=Parameter(value=0.1), y=Parameter(value=0.2), z=Parameter(value=0.3),
        aniso=AnisoU.from_values([0.011, 0.012, 0.013, 0.001, -0.002, 0.0],
                                 vary=True),
    )
    # ±inf bounds must survive the JSON round trip as strings, as elsewhere
    atom.aniso.u11.max = math.inf
    back = Atom.model_validate_json(atom.model_dump_json())
    assert back.aniso is not None
    assert back.aniso.values() == atom.aniso.values()
    assert back.aniso.u11.max == math.inf
    assert back.aniso.u12.vary is True


def test_aniso_block_forbids_extra_fields():
    with pytest.raises(ValueError, match="u21|extra"):
        AnisoU.model_validate({"u11": {"value": 0.01}, "u22": {"value": 0.01},
                               "u33": {"value": 0.01}, "u21": {"value": 0.0}})


def test_isotropic_atom_keeps_no_aniso_block():
    atom = Atom(label="B", species="B", x=Parameter(value=0.2),
                y=Parameter(value=0.5), z=Parameter(value=0.5))
    assert atom.aniso is None
    assert "aniso" in atom.model_dump()  # explicit null, not a silent omission


def test_varying_biso_alongside_aniso_is_rejected():
    with pytest.raises(ValueError, match="does not enter the model"):
        Atom(label="Fe", species="Fe", x=Parameter(value=0.0),
             y=Parameter(value=0.0), z=Parameter(value=0.0),
             biso=Parameter(value=0.5, vary=True),
             aniso=AnisoU.from_values([0.01] * 3 + [0.0] * 3))


# -- representations ---------------------------------------------------


def test_isotropic_u6_is_delta_only_for_orthogonal_axes():
    cubic = (4.0, 4.0, 4.0, 90.0, 90.0, 90.0)
    assert adp.isotropic_u6(0.02, cubic) == pytest.approx([0.02] * 3 + [0.0] * 3)

    hexagonal = (3.0, 3.0, 5.0, 90.0, 90.0, 120.0)
    u6 = adp.isotropic_u6(0.02, hexagonal)
    # γ* = 60° ⇒ U12 = Uiso·cos(60°); U13 = U23 = 0 (c* ⊥ a*, b*)
    assert u6 == pytest.approx([0.02, 0.02, 0.02, 0.01, 0.0, 0.0])


def test_u_equivalent_and_principal_values_of_an_isotropic_tensor():
    cell = (3.0, 3.0, 5.0, 90.0, 90.0, 120.0)
    u6 = adp.isotropic_u6(0.017, cell)
    assert adp.u_equivalent(u6, cell) == pytest.approx(0.017, rel=1e-12)
    assert adp.principal_values(u6, cell) == pytest.approx([0.017] * 3, rel=1e-12)


def test_positive_definiteness_sign_is_representation_independent():
    cell = (5.2, 6.4, 7.8, 90.0, 105.0, 90.0)  # monoclinic: no orthogonal frame
    good = [0.010, 0.012, 0.008, 0.001, -0.002, 0.0005]
    bad = [0.010, 0.012, 0.008, 0.020, -0.002, 0.0005]  # U12 too large
    assert adp.is_positive_definite(good)
    assert not adp.is_positive_definite(bad)
    # the physical tensor agrees with the cell-free test in both directions
    assert np.min(adp.principal_values(good, cell)) > 0
    assert np.min(adp.principal_values(bad, cell)) < 0
