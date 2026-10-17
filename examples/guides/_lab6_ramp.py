"""A synthetic LaB6 heating ramp, shared by the series guides.

Seven synchrotron capillary patterns of LaB6 from 300 K to 900 K, made from a
known model with Poisson noise, so a guide can say how far each fitted value
lies from the truth. The cell edge grows by 0.05 % per 100 K. The settings are
those of `examples/tutorials/05_sequential_fits.py`.

`tests/test_examples.py` runs every guide script but skips a file whose name
starts with an underscore, because this one has no page of its own.
"""

import tempfile
from pathlib import Path

import numpy as np

import rietx as rx

TEMPERATURES = [300, 400, 500, 600, 700, 800, 900]
A0, EXPANSION = 4.1566, 5e-4  # Å at 300 K, and the fractional growth per 100 K
TRUE_A = [A0 * (1 + EXPANSION * k) for k in range(len(TEMPERATURES))]

_CIF = (
    "data_LaB6\n_space_group_name_H-M_alt 'P m -3 m'\n"
    + "".join(f"_cell_length_{k} {A0}\n" for k in "abc")
    + "".join(f"_cell_angle_{k} 90\n" for k in ("alpha", "beta", "gamma"))
    + "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
      "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n"
      "La1 La 0 0 0 0.4\nB1 B 0.1996 0.5 0.5 0.4\n")
_TWO_THETA = np.arange(3.0, 24.0, 0.005)


def lab6():
    """The LaB6 structure at 300 K, read from a short CIF."""
    path = Path(tempfile.mkdtemp()) / "LaB6.cif"
    path.write_text(_CIF, encoding="utf-8")
    return rx.Structure.from_cif(path)


def _true_instrument():
    instrument = rx.Instrument.debye_scherrer(wavelength=0.4139)
    instrument.zero_shift.value = 0.008
    instrument.profile.w.value = 2.5e-4
    instrument.background = rx.BackgroundChebyshev.with_terms(3)
    for coefficient, value in zip(instrument.background.coefficients, (40.0, -6.0, 1.5)):
        coefficient.value = value
    return instrument


def simulate(a, seed):
    """One pattern of the true specimen at cell edge `a`, with Poisson noise."""
    structure = lab6()
    for edge in "abc":
        getattr(structure.phases[0].cell, edge).value = a
    structure.phases[0].scale.value = 5e-4
    y = rx.Refinement(structure, _true_instrument()).predict(_TWO_THETA)
    counts = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=_TWO_THETA, intensity=counts)


def ramp():
    """The seven patterns, in temperature order."""
    return [simulate(a, seed=11 + k) for k, a in enumerate(TRUE_A)]


def starting_model():
    """What you would have before the first fit: the cell 0.1 % off, no zero
    shift, and peaks 50 % too wide."""
    structure = lab6()
    for edge in "abc":
        getattr(structure.phases[0].cell, edge).value = A0 * 1.001
    instrument = rx.Instrument.debye_scherrer(wavelength=0.4139)
    instrument.profile.w.value = 2.5e-4 * 1.5
    instrument.background = rx.BackgroundChebyshev.with_terms(3)
    return structure, instrument
