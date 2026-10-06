"""``Refinement.fix_special_positions()``: the opt-in of #728 item 4."""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx

P = rx.Parameter


def _phase(vary_all: bool) -> rx.Phase:
    def atom(label, species, x, y, z):
        return rx.Atom(label=label, species=species, x=P(value=x, vary=vary_all),
                       y=P(value=y, vary=vary_all), z=P(value=z, vary=vary_all),
                       biso=P(value=0.5))

    # P n m a: Mn on an inversion centre (no positional freedom) beside La on
    # the mirror (x, z free) and a general O
    return rx.Phase(
        name="p", space_group="P n m a",
        cell=rx.Cell(a=P(value=5.74), b=P(value=7.69), c=P(value=5.54),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        atoms=[atom("La", "La", 0.0505, 0.25, 0.9945),
               atom("Mn", "Mn", 0.0, 0.0, 0.5),
               atom("O2", "O", 0.2837, 0.0368, 0.7155)])


def _ref():
    return rx.Refinement(rx.Structure(phases=[_phase(True)]),
                         rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.5),
                         history=False)


def test_a_fully_fixed_site_with_vary_true_is_refused_at_the_first_listing():
    with pytest.raises(ValueError, match="fully fixed special position"):
        _ref().parameters()


def test_fix_special_positions_clears_exactly_those_coordinates_and_the_model_builds():
    ref = _ref()
    cleared = ref.fix_special_positions()
    assert cleared == ["phases.0.atoms.1.x", "phases.0.atoms.1.y",
                       "phases.0.atoms.1.z"]
    rows = ref.parameters()            # no longer refused
    assert rows
    atoms = ref.structure.phases[0].atoms
    assert [a.x.vary for a in atoms] == [True, False, True]
    # the free sites keep their flags: La on its mirror and the general O
    assert atoms[0].z.vary and atoms[2].y.vary
    assert ref.fix_special_positions() == []          # nothing left to fix


def test_the_structure_it_fixes_refines():
    ref = _ref()
    ref.fix_special_positions()
    grid = np.arange(10.0, 150.0, 0.1)
    truth = rx.Refinement(rx.Structure(phases=[_phase(False)]),
                          rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.5),
                          history=False)
    y = np.asarray(truth.predict(grid)) + 40.0
    data = rx.PatternData(two_theta=grid.tolist(), intensity=y.tolist())
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("xyz", ["phases.*.scale", "phases.*.atoms.*.dof.*"])]),
        telemetry=False)
    assert result.status in ("converged", "max_iter")
