"""WP-1326 acceptance: the satellite arm found blind, its null, and a k = 0 case.

Three measurements, each with the arm that could fail written down first:

* **A synthetic k = (0, 0, ½) satellite set, under Poisson noise.**  A nuclear
  model that knows nothing of any k is fitted to a pattern carrying intensity
  at the satellites of (0, 0, ½); the report arm must rank (0, 0, ½) first.
  If a noise peak could out-score the true k, or the runner-up tied it, the
  ranking would mean nothing.
* **The null: the same fit with no satellite intensity in the data.**  The arm
  must abstain — no unexplained peak, no candidate scored.  Noise is what
  makes this a control: on a noiseless pattern a converged fit leaves no
  residual at all and the null passes by construction.
* **Cr₂WO₆, a published k = 0 structure** (GSAS-II tutorial *Magnetic-II*,
  HB-2A, 4 K and 150 K; vendored per ``tests/data/README.md``).  The 4 K
  pattern against the nuclear model refined from it must show the k = 0
  signature — residual peaks on reciprocal-lattice points the nuclear
  structure factor forbids — and name k = 0; the 150 K pattern, above the
  ordering temperature, must show none.  What this case does **not** assert
  is the WP's "no candidate scores": measured, the best zone-boundary
  candidates index 2 of the 6 leftover 4 K peaks, and 2 of 5 on the 150 K
  null — the same chance level, because the ranking has no chance baseline.
  That is a design question for the arm, not a threshold to tune here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter

DATA = Path(__file__).parent / "data"

# ====================================================== synthetic, under noise

LAMBDA = 2.4067
CELL = (4.0, 5.0, 6.0, 90.0, 90.0, 90.0)


def _phase(k=None) -> rx.Phase:
    P = rx.Parameter
    a, b, c, al, be, ga = CELL
    return rx.Phase(
        name="Fe", space_group="P m m m",
        cell=rx.Cell(a=P(value=a), b=P(value=b), c=P(value=c),
                     alpha=P(value=al), beta=P(value=be), gamma=P(value=ga)),
        atoms=[rx.Atom(label="Fe", species="Fe", x=P(value=0.0),
                       y=P(value=0.0), z=P(value=0.0), biso=P(value=0.4))],
        scale=P(value=1.0), propagation_vector=k)


def _pattern(y=None) -> rx.PatternData:
    tt = np.arange(10.0, 110.0, 0.02)
    if y is None:
        y = np.ones_like(tt)
    return rx.PatternData(two_theta=tt.tolist(), intensity=np.asarray(y).tolist())


def _values(structure, instrument):
    table = ParameterTable(structure, instrument)
    return table.decode(table.x0())


@pytest.fixture(scope="module")
def synthetic():
    """Nuclear and satellite-only profiles, drawn through the model itself."""
    instrument = rx.Instrument.constant_wavelength_neutron(LAMBDA, fwhm_deg=0.3)
    plain = rx.Structure(phases=[_phase(None)])
    with_k = rx.Structure(phases=[_phase((0, 0, "1/2"))])
    nuclear = np.asarray(compile_model(plain, instrument, _pattern()).evaluate(
        _values(plain, instrument)), dtype=np.float64)
    seed = compile_model(with_k, instrument, _pattern(), mode="lebail")
    cp = seed.phases[0]
    cp.hkl_intensity = np.where(cp.reflections.is_satellite, 900.0, 0.0)
    magnetic = np.asarray(seed.evaluate(_values(with_k, instrument)),
                          dtype=np.float64)
    return instrument, plain, nuclear, magnetic


def _arm(instrument, plain, y):
    ref = rx.Refinement(plain, instrument, history=False)
    ref.fit(_pattern(y), plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"])]))
    arms = ref.report().satellites
    assert len(arms) == 1
    return arms[0]


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_a_k_00half_satellite_set_is_found_blind_under_noise(synthetic, seed):
    """Positive arm: (0, 0, ½) ranks first and the runner-up is far behind.

    Measured over seeds 0-9: 21-22 of 31-41 unexplained peaks matched by
    (0, 0, ½), the runner-up at most 5.  The extra unexplained peaks are noise
    at the report's 5σ default and are what the true k must beat.
    """
    instrument, plain, nuclear, magnetic = synthetic
    rng = np.random.default_rng(seed)
    arm = _arm(instrument, plain,
               rng.poisson(nuclear + magnetic + 200.0).astype(float))
    top, runner_up = arm.candidates[0], arm.candidates[1]
    assert top.vector == "(0, 0, 1/2)", [(c.vector, c.matched)
                                         for c in arm.candidates]
    assert top.matched >= 20, arm.note
    assert runner_up.matched * 3 < top.matched, arm.note
    # P m m m forbids nothing, so no peak can be the k = 0 signature here
    assert arm.excess_on_absent_lattice_lines == 0


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_the_null_abstains_under_noise(synthetic, seed):
    """Null arm: no satellite intensity, so nothing unexplained and nothing scored."""
    instrument, plain, nuclear, _magnetic = synthetic
    rng = np.random.default_rng(seed)
    arm = _arm(instrument, plain, rng.poisson(nuclear + 200.0).astype(float))
    assert arm.n_unexplained == 0, arm.note
    assert all(c.matched == 0 for c in arm.candidates), arm.note
    assert "nothing to index" in arm.note


# ============================================================ Cr₂WO₆, k = 0

#: the tutorial's wavelength and a hand-seeded width, as in
#: ``test_acceptance_magnetic.py`` (the tutorial's PNCR profile is refused)
CR_LAMBDA = 2.4067
FWHM_SEED_DEG = 0.35
_B = ["phases.0.scale"] + [f"instrument.background.c{i}" for i in range(4)]
_NUCLEAR = [
    ("scale_bkg", _B),
    ("zero", _B + ["instrument.zero_shift"]),
    ("cell", _B + ["instrument.zero_shift", "phases.0.cell.*"]),
    ("widths", _B + ["instrument.zero_shift", "phases.0.cell.*",
                     *[f"instrument.profile.{k}" for k in "uvwx"]]),
    ("coords", _B + ["instrument.zero_shift", "phases.0.cell.*",
                     *[f"instrument.profile.{k}" for k in "uvwx"],
                     "phases.0.atoms.*.dof.*"]),
    ("biso", _B + ["instrument.zero_shift", "phases.0.cell.*",
                   *[f"instrument.profile.{k}" for k in "uvwx"],
                   "phases.0.atoms.*.dof.*", "phases.0.atoms.*.biso"]),
]


def _p(value: float, **kw) -> Parameter:
    return Parameter(value=value, **kw)


def _trirutile() -> rx.Structure:
    """Ideal trirutile start (the tutorial's ICSD file is not redistributable)."""
    def atom(label, species, xyz):
        x, y, z = xyz
        return rx.Atom(label=label, species=species, x=_p(x), y=_p(y), z=_p(z),
                       occ=_p(1.0), biso=_p(0.5, unit="A^2"))

    return rx.Structure(phases=[rx.Phase(
        name="Cr2WO6", space_group="P 42/m n m",
        cell=rx.Cell(a=_p(4.58), b=_p(4.58), c=_p(8.85),
                     alpha=_p(90.0), beta=_p(90.0), gamma=_p(90.0)),
        atoms=[atom("W1", "W", (0.0, 0.0, 0.0)),
               atom("Cr1", "Cr", (0.0, 0.0, 1.0 / 3.0)),
               atom("O1", "O", (0.3, 0.3, 0.0)),
               atom("O2", "O", (0.3, 0.3, 1.0 / 3.0))])])


def _fit(structure, instrument, data):
    ref = rx.Refinement(structure, instrument, history=False)
    ref.fit(data, plan=rx.RefinementPlan(
        stages=[rx.Stage(name=n, turn_on=list(t), max_iter=200)
                for n, t in _NUCLEAR],
        intermediate_ftol=1e-6))
    return ref


@pytest.fixture(scope="module")
def cr2wo6():
    inst = rx.Instrument.constant_wavelength_neutron(CR_LAMBDA)
    inst.profile.w.value = (FWHM_SEED_DEG / 2.0) ** 2
    inst.profile.x.value = FWHM_SEED_DEG
    ref150 = _fit(_trirutile(), inst,
                  rx.read_pattern(DATA / "gsas2_hb2a_cr2wo6_150K.dat"))
    ref4 = _fit(ref150.structure.model_copy(deep=True),
                ref150.instrument.model_copy(deep=True),
                rx.read_pattern(DATA / "gsas2_hb2a_cr2wo6_4K.dat"))
    return ref4.report().satellites[0], ref150.report().satellites[0]


def test_cr2wo6_4k_shows_the_k_zero_signature_and_150k_does_not(cr2wo6):
    """The positive k = 0 statement at 4 K, and its absence above T_N.

    Measured: 4 residual peaks on forbidden reciprocal-lattice points at 4 K
    (the (0 0 1) and (1 0 2) regions near 15.8° and 44.7° among them), 0 at
    150 K.  The 150 K arm is the control: a nuclear model refined on a pattern
    with no magnetic order must put no residual on a systematic absence.
    """
    arm4, arm150 = cr2wo6
    assert arm4.radiation == "neutron"
    assert arm4.excess_on_absent_lattice_lines >= 2, arm4.note
    assert "k = 0" in arm4.note
    assert arm150.excess_on_absent_lattice_lines == 0, arm150.note
