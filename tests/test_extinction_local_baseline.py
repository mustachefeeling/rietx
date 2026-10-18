"""The extinction screen's refutations, confirmed in the raw counts (#726).

The absence test reads ``y_obs − y_calc`` of a class's own Le Bail fit, so a
background that misses under a forbidden position refutes the class on
intensity the data do not have.  ``confirm_in_data=True`` (the default) asks
each flagged position again of the raw counts against a local baseline
(:func:`~rietx.indexing.extinction._line_in_raw_data`) and withdraws a
refutation only where the net there is consistent with zero.

Each claim has an arm that must come out the other way:

* **the function** — no line on a steep background reads "no line"; a line
  reads "line"; a line off the position, a baseline the data sit below and a
  window the allowed reflections fill all read "can't tell", so a refutation
  is never withdrawn on them;
* **the screen, synthetic** — a broad excess on Si's forbidden (200) refutes
  ``F d - -`` without the check and not with it, while a line of the
  instrument's width at the same position refutes it either way;
* **the screen, public data** (``tests/data/gsas2_pbso4.gpx``, Hill 1992,
  ``slow``) — the neutron histogram at a held index cell refutes the true
  ``P c - n`` at (0,0,1), where the counts show no line, and the check
  withdraws it; a line planted on a forbidden position of the X-ray
  histogram still refutes it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import determine_extinction_symbol
from rietx.indexing.extinction import _line_in_raw_data
from rietx.schemas.indexing import CellCandidate

pytestmark = pytest.mark.xdist_group("extinction-local-baseline")

PBSO4 = Path(__file__).parent / "data" / "gsas2_pbso4.gpx"


# ----------------------------------------------------------------------
# the function
# ----------------------------------------------------------------------
W = 0.08


def _counts(*, line_at=None, height=300.0, dip=False, seed=3):
    """A steep, curved background (the low-angle shape that fools a Le Bail
    background) with Poisson noise, and optionally a line or a dip."""
    tt = np.round(np.arange(18.0, 22.0, 0.01), 3)
    y = 5000.0 * np.exp(-(tt - 18.0) / 3.0) + 800.0
    if line_at is not None:
        y = y + height * np.exp(-4 * np.log(2) * ((tt - line_at) / W) ** 2)
    if dip:
        y = y - 300.0 * np.exp(-4 * np.log(2) * ((tt - 20.0) / W) ** 2)
    obs = np.random.default_rng(seed).poisson(y).astype(float)
    return tt, obs, np.sqrt(np.maximum(obs, 1.0))


def test_the_counts_decide_line_no_line_and_cant_tell():
    none = np.array([])
    line, z = _line_in_raw_data(*_counts(), 20.0, W, none)
    assert line is False and abs(z) < 3.0

    line, z = _line_in_raw_data(*_counts(line_at=20.0), 20.0, W, none)
    assert line is True and z > 3.0

    # half a FWHM away: something is there, but not this reflection
    line, z = _line_in_raw_data(*_counts(line_at=20.0 + 0.5 * W), 20.0, W, none)
    assert line is None and z > 3.0

    # data well below the baseline: the baseline is not one
    line, z = _line_in_raw_data(*_counts(dip=True), 20.0, W, none)
    assert line is None and z < -3.0

    # allowed reflections every 0.1 degree leave no baseline to draw
    allowed = np.arange(19.0, 21.0, 0.1) + 0.05
    assert _line_in_raw_data(*_counts(), 20.0, W, allowed) == (None, None)


# ----------------------------------------------------------------------
# the screen, synthetic Si (the #939 gate test's pattern)
# ----------------------------------------------------------------------
SI_A = 5.4311
LAM = 0.825739
LIMITS = (12.1, 60.0)
P200 = float(np.degrees(2.0 * np.arcsin(LAM / SI_A)))       # forbidden in F d -3 m


def _si(extra_height: float, extra_fwhm: float):
    from rietx.schemas.structure import Atom, Cell, Parameter, Phase, Structure

    structure = Structure(phases=[Phase(
        name="Si", space_group="F d -3 m",
        cell=Cell(a=Parameter(value=SI_A), b=Parameter(value=SI_A),
                  c=Parameter(value=SI_A), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Si1", species="Si", x=Parameter(value=0.125),
                    y=Parameter(value=0.125), z=Parameter(value=0.125),
                    biso=Parameter(value=0.5))])])
    instrument = rx.Instrument.debye_scherrer(wavelength=LAM)
    instrument.source.dispersion = None         # a pinned number declares it
    instrument.profile.w.value = 3e-4
    instrument.profile.u.value = 5e-4
    instrument.profile.x.value = 5e-3
    tt = np.round(np.arange(12.088, 62.0, 0.004), 3)
    y = rx.Refinement(structure, instrument, history=False).predict(two_theta=tt)
    y = (y / y.max() * 1.3e6 + 7700.0
         + extra_height * np.exp(-4 * np.log(2) * ((tt - P200) / extra_fwhm) ** 2))
    obs = np.random.default_rng(1).poisson(y).astype(float)
    data = rx.PatternData(two_theta=tt.tolist(), intensity=obs.tolist(),
                          sigma=np.sqrt(np.maximum(obs, 1.0)).tolist())
    candidate = CellCandidate(cell=(SI_A,) * 3 + (90.0,) * 3, cell_esd=(0.0,) * 6,
                              system="cubic", centring="F", volume=SI_A ** 3)
    peaks = rx.pick_peaks(data, instrument, two_theta_range=LIMITS)
    return data, candidate, instrument, peaks


def _class(screen, symbol):
    return next(c for c in screen.candidates if c.symbol == symbol)


def test_a_broad_excess_on_a_forbidden_position_no_longer_refutes():
    """0.1 % of the strongest line, 1° wide, on (200): an undeclared container
    halo's shape (#931).  The screen's background cannot follow it, so the
    residual refutes ``F d - -``; the counts show no line there."""
    data, candidate, instrument, peaks = _si(1300.0, 1.0)
    kw = dict(peaks=peaks, two_theta_limits=LIMITS)

    old = determine_extinction_symbol(data, candidate, instrument,
                                      confirm_in_data=False, **kw)
    assert _class(old, "F d - -").refuted
    assert _class(old, "F d - -").forbidden_hkl == [(2, 0, 0)]

    screen = determine_extinction_symbol(data, candidate, instrument, **kw)
    fd = _class(screen, "F d - -")
    assert not fd.refuted and fd.n_present == 0
    assert fd.unconfirmed_hkl == [(2, 0, 0)]
    assert abs(fd.unconfirmed_z[0]) < 3.0
    assert "EXTINCTION_REFUTATION_UNCONFIRMED" in [d.code for d in fd.diagnostics]
    assert screen.best_or_none().symbol == "F d - -"


def test_a_line_on_the_same_position_still_refutes():
    """The positive arm: an instrument-width line of the same height."""
    data, candidate, instrument, peaks = _si(1300.0, 0.02)
    screen = determine_extinction_symbol(data, candidate, instrument, peaks=peaks,
                                         two_theta_limits=LIMITS)
    fd = _class(screen, "F d - -")
    assert fd.refuted and fd.forbidden_hkl == [(2, 0, 0)]
    assert fd.unconfirmed_hkl == []


# ----------------------------------------------------------------------
# the screen, public PbSO4 (Hill 1992)
# ----------------------------------------------------------------------
PBSO4_CELL = (6.9644, 5.4038, 8.4956, 90.0, 90.0, 90.0)   # index_pattern's, 0.1-0.2 % long


def _pbso4(histogram: str):
    from rietx.io.projects.gsas2 import _read_tree

    head = next(item[0] for item in _read_tree(PBSO4) if isinstance(item[0], list)
                and str(item[0][0]).startswith(f"PWDR PBSO4.{histogram}"))
    x, y, w = (np.asarray(a, dtype=float) for a in head[1][1][:3])
    keep = w > 0
    return x[keep], y[keep], 1.0 / np.sqrt(w[keep])


def _pbso4_candidate():
    return CellCandidate(cell=PBSO4_CELL, cell_esd=(0.0,) * 6, system="orthorhombic",
                         centring="P", volume=float(np.prod(PBSO4_CELL[:3])))


@pytest.mark.slow
def test_pbso4_neutron_held_cell_refutation_is_withdrawn():
    """Measured: held at the index cell on the preset instrument, the screen
    refutes the true ``P c - n`` (P n m a, a and c swapped) at (0,0,1) 12.95°,
    where the counts sit on the background (z = 1.9)."""
    x, y, sig = _pbso4("CWN")
    data = rx.PatternData(two_theta=x.tolist(), intensity=y.tolist(),
                          sigma=sig.tolist())
    instrument = rx.Instrument.constant_wavelength_neutron(wavelength=1.909)
    limits = (10.0, 155.85)
    peaks = rx.pick_peaks(data, instrument, two_theta_range=limits)
    kw = dict(peaks=peaks, two_theta_limits=limits, refine_cell=False)

    old = determine_extinction_symbol(data, _pbso4_candidate(), instrument,
                                      confirm_in_data=False, **kw)
    assert _class(old, "P c - n").refuted
    assert _class(old, "P c - n").forbidden_hkl == [(0, 0, 1)]

    screen = determine_extinction_symbol(data, _pbso4_candidate(), instrument, **kw)
    pcn = _class(screen, "P c - n")
    assert not pcn.refuted
    assert pcn.unconfirmed_hkl == [(0, 0, 1)]


@pytest.mark.slow
def test_pbso4_xray_line_planted_on_a_forbidden_position_still_refutes():
    """The positive arm on real data: a line of the picked lines' median width
    and a tenth of their median area, at (0,1,1) where the default screen puts
    it (19.431°, the prefit's cell and zero shift).  Unplanted, the default
    answers ``P c - n`` (``test_extinction_gate``)."""
    from rietx.schemas.instrument import EmissionLine, Source

    x, y, sig = _pbso4("XRA")
    instrument = rx.Instrument.bragg_brentano()
    instrument.source = Source(
        lines=[EmissionLine(wavelength=1.5405),
               EmissionLine(wavelength=1.5443,
                            weight=rx.Parameter(value=0.5, min=0.0, max=1.0))],
        polarization=rx.Parameter(value=0.5, min=0.0, max=1.0), dispersion=None)
    limits = (15.0, float(x.max()))
    picked = rx.pick_peaks(rx.PatternData(two_theta=x.tolist(), intensity=y.tolist(),
                                          sigma=sig.tolist()),
                           instrument, two_theta_range=limits).peaks
    s = float(np.median([p.fwhm for p in picked])) / 2.3548
    area = 0.1 * float(np.median([p.intensity for p in picked]))
    add = area / (s * np.sqrt(2 * np.pi)) * np.exp(-0.5 * ((x - 19.4309) / s) ** 2)
    data = rx.PatternData(two_theta=x.tolist(), intensity=(y + add).tolist(),
                          sigma=np.sqrt(sig ** 2 + add).tolist())
    peaks = rx.pick_peaks(data, instrument, two_theta_range=limits)

    screen = determine_extinction_symbol(data, _pbso4_candidate(), instrument,
                                         peaks=peaks, two_theta_limits=limits)
    pcn = _class(screen, "P c - n")
    assert pcn.refuted
    assert (0, 1, 1) in pcn.forbidden_hkl
    assert pcn.unconfirmed_hkl == []
