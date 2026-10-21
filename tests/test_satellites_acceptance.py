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
* **Ba₆Co₆ClO₁₆, a real k ≠ 0 case** (GSAS-II tutorial *Magnetic-III*, ILL
  D1B, 1.4 K; vendored per ``tests/data/README.md``): the arm must return the
  tutorial's k = (0, 0, ½) first, with every other candidate matching fewer
  of the unexplained peaks.  See the last section for what that does and does
  not show.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model import compiled
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable

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


@pytest.mark.xdist_group("satellites-synthetic")
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


@pytest.mark.xdist_group("satellites-synthetic")
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
#
# Real data, so ``slow``; and the nuclear fits are the session's
# (``conftest.cr2wo6_nuclear``), the same two files from the same trirutile
# start that WP-1327's moment acceptance refines, so the test joins that
# fixture's group rather than fitting them a second time.


@pytest.fixture(scope="module")
def cr2wo6(cr2wo6_nuclear):
    return (cr2wo6_nuclear["ref4"].report().satellites[0],
            cr2wo6_nuclear["ref150"].report().satellites[0])


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-cr2wo6")
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
    # the chance-level best at 150 K is named with what judges it
    if arm150.candidates and arm150.candidates[0].matched:
        assert "runner-up" in arm150.note, arm150.note
        assert "satellite position(s) in range" in arm150.note


# ====================================== Ba₆Co₆ClO₁₆, a real k = (0, 0, ½) case
#
# GSAS-II tutorial *Magnetic-III*: Ba₆Co₆ClO₁₆ (the tutorial text writes
# Ba₆Co₆ClO₁₅.₅), ILL D1B, λ = 2.394 Å, 1.4 K, space group P -6 m 2, magnetic
# propagation vector k = (0, 0, ½) as the tutorial states it.  The tutorial
# cites Mentré, Kauffmann, Ehora, Daviero-Minaud, Abraham & Roussel, *Solid
# State Sci.* 10, 471-475 (2008), doi:10.1016/j.solidstatesciences.2007.12.032,
# which was NOT read when this test was written: k is the tutorial's, not
# checked against the paper, and no moment is asserted anywhere below.
#
# Tier (``tests/validation_matrix.py`` vocabulary): ``characterisation``, plus
# the ``ceiling`` bars on the fit.  It is not a validation: there is no
# independent value (no certificate, no second code run under an adopted
# protocol, no prediction written before the measurement), and the published k
# is a label the arm is asked to reproduce, not a measured quantity.  This
# suite is not scanned by ``test_validation_matrix`` (only
# ``test_acceptance_*.py`` is), so no matrix row exists; if the case moves
# there, the row is ``characterisation`` against a new dataset entry.
#
# What the test shows is thin and is stated as such.  The nuclear model leaves
# four residual peaks; three are unexplained by the nuclear and absent-line
# arms.  (0, 0, ½) matches all three, from 74 satellite positions, and the
# other four zone-boundary candidates match none (positions 96-154).  Against
# a random-placement null measured OUTSIDE rietx (2000 draws of the same
# number of peaks, within 0.10 deg), matching 3 of 4 has P about 0.004 and
# the mean for (0, 0, ½) is 0.42 matches.  Two of the four peaks sit at 116
# and 158 deg, where 74 positions crowd the pattern.  The arm itself says its
# count has no chance baseline; this test inherits that limit and so asserts
# the winner and the margin, never a peak position.

DATA = Path(__file__).parent / "data"

# Tutorial coordinates (Ba6Co6.cif of the tutorial repository, no database
# notice in that file; hence the model is written here, not vendored).
_BA6CO6_CIF = """data_Ba6Co6ClO16
_cell_length_a 5.6487
_cell_length_b 5.6487
_cell_length_c 14.4658
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 120
_symmetry_space_group_name_H-M 'P -6 m 2'
loop_
 _atom_site_label
 _atom_site_type_symbol
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 _atom_site_U_iso_or_equiv
 _atom_site_occupancy
 Ba1 Ba 0 0 0.2048 0.0287 1
 Ba2 Ba 0.666667 0.333333 0.3573 0.0287 1
 Ba3 Ba 0.333333 0.666667 0 0.0287 1
 Ba4 Ba 0 0 0.5 0.0287 1
 Co1 Co 0.333333 0.666667 0.2398 0.0287 1
 Co2 Co 0.333333 0.666667 0.4162 0.0287 1
 Co3 Co 0.666667 0.333333 0.1214 0.0287 1
 Cl1 Cl 0 0 0 0.0287 1
 O1 O 0.1877 -0.1877 0.3343 0.0287 1
 O2 O 0.4949 -0.4949 0.1674 0.0287 1
 O3 O 0.4861 -0.4861 0.5 0.0287 1
 O4 O 0.6994 -0.6994 0 0.0287 0.25
"""


def _d1b_wavelength() -> float:
    """λ from the ``ICONS`` record of the vendored GSAS-I ``.prm`` (2.394 Å)."""
    text = (DATA / "gsas2_d1b.prm").read_text(encoding="utf-8")
    return float(re.search(r"ICONS\s+([0-9.]+)", text).group(1))


@pytest.fixture(scope="module")
def ba6co6(tmp_path_factory):
    """The nuclear fit of the 1.4 K pattern, six McCusker stages, four-term background."""
    cif = tmp_path_factory.mktemp("ba6co6") / "ba6co6.cif"
    cif.write_text(_BA6CO6_CIF, encoding="utf-8")
    data = rx.read_pattern(DATA / "gsas2_d1b_ba6co6.xye")
    lam = _d1b_wavelength()
    inst = rx.Instrument.constant_wavelength_neutron(lam)
    fwhm = 0.30  # starting width only; U, V, W, X are refined in stage 4
    inst.profile.w.value = (fwhm / 2) ** 2
    inst.profile.x.value = fwhm
    base = ["phases.0.scale"] + [f"instrument.background.c{i}" for i in range(4)]
    zero, cell = "instrument.zero_shift", "phases.0.cell.*"
    prof = [f"instrument.profile.{k}" for k in "uvwx"]
    coords, biso = "phases.0.atoms.*.dof.*", "phases.0.atoms.*.biso"
    stages = [("scale_bkg", base), ("zero", base + [zero]),
              ("cell", base + [zero, cell]),
              ("widths", base + [zero, cell, *prof]),
              ("coords", base + [zero, cell, *prof, coords]),
              ("biso", base + [zero, cell, *prof, coords, biso])]
    # intermediate_ftol 1e-6 is the schedule the measurement was made under;
    # no dispersion applies to a neutron source, so nothing is declared there.
    plan = rx.RefinementPlan(
        stages=[rx.Stage(name=n, turn_on=list(t), max_iter=200) for n, t in stages],
        intermediate_ftol=1e-6)
    ref = rx.Refinement(rx.Structure.from_cif(cif), inst, history=False)
    # the numpy path is declared, not inherited from an earlier test on this
    # worker or RIETX_COMPILED (tests/CLAUDE.md § Quoting numbers)
    was = compiled.set_enabled(False)
    try:
        result = ref.fit(data, plan=plan, two_theta_limits=(4.0, 159.9))
        satellites = ref.report().satellites
    finally:
        compiled.set_enabled(was)
    return data, lam, result, satellites


@pytest.mark.slow
@pytest.mark.xdist_group("satellites-ba6co6")
def test_ba6co6_d1b_returns_the_tutorials_k_first_with_every_other_candidate_behind(ba6co6):
    """Characterisation: (0, 0, ½) ranks first and no other candidate ties it.

    Measured (main 5ecd4d70b, numpy path, 2026-10-20): Rwp 0.1219, GoF 1.09,
    4 residual peaks (31.8, 37.3, 116.0, 158.0 deg), 3 unexplained;
    (0, 0, ½) matches 3 of 3 from 74 positions (worst offset 0.099 deg), the
    four other candidates 0 from 96-154 positions.  The evidence is thin, see
    the section header: three weak peaks, P about 0.004 on a random-placement
    null, and the published moment is not asserted.
    """
    data, lam, result, satellites = ba6co6
    # the right file and the right wavelength
    assert len(data.two_theta) == 3120
    assert lam == pytest.approx(2.394)
    # ceiling bars on the nuclear fit: loose by design, no accuracy claim
    assert result.status == "converged"
    assert result.statistics.rwp < 0.20
    # the arm
    assert len(satellites) == 1
    arm = satellites[0]
    assert arm.radiation == "neutron"
    assert arm.n_unexplained >= 2, arm.note
    top, rest = arm.candidates[0], arm.candidates[1:]
    assert top.vector == "(0, 0, 1/2)", [(c.vector, c.matched) for c in arm.candidates]
    assert top.matched >= 2, arm.note
    assert all(c.matched < top.matched for c in rest), \
        [(c.vector, c.matched) for c in arm.candidates]
