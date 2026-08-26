"""The two-tier soft cap on sample strain broadening.

Measured on a 248-pattern CuO→Cu reduction series (issue #140): Cu's
``lor_strain`` exceeded 1 in 133 of 248 patterns and peaked at 1.1e5, the
support phase's at 2.2e5, against 0.3 in the TOPAS protocol for the same data.
The consequences were a starved 16 wt % phase, weight fractions inflated ×1.19
and a covariance that overflowed until 179 of 248 patterns returned
weight-fraction esds above 100 wt %.

Two tiers, because the numbers do two jobs and are two orders of magnitude
apart:

* ``params.vector.strain_cap`` — a **solver bound** derived from the pattern's
  own fitted 2θ extent (a line wider than the interval it was measured over is
  not a line).  Protects the numerics, says nothing about the specimen, and
  reports itself through the ``BOUND_HIT`` machinery that already existed.
* ``refine.STRAIN_FLAG_WIDTH`` — a **flag** set from the corpus of 606 solved
  TOPAS refinements.  Protects the interpretation, changes no number.

The rule the whole design turns on is identity: a bound is never free, since
TRF takes its per-coordinate trust-region scale from the distance to it, so a
fit whose strain stays where the data can express it must get **no bound at
all**.  ``test_a_fit_below_the_cap_is_bounded_exactly_as_before`` is that
assertion; it was also checked end to end against ``origin/main``, where the
FAP acceptance protocol reproduced all 33 parameters and its Rwp bit for bit.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.params.vector import (
    STRAIN_CAP_ARM_RTOL,
    STRAIN_CAP_RANGE_FRACTION,
    ParameterTable,
    strain_cap,
    strain_cap_hi,
)
from rietx.refine import STRAIN_FLAG_WIDTH


def _cell() -> rx.Cell:
    """A cubic cell — the cap cares about nothing in it."""
    p = rx.Parameter
    return rx.Cell(a=p(value=4.0, min=1.0), b=p(value=4.0, min=1.0),
                   c=p(value=4.0, min=1.0), alpha=p(value=90.0),
                   beta=p(value=90.0), gamma=p(value=90.0))


def _phase(name: str = "p", **kw) -> rx.Phase:
    p = rx.Parameter
    return rx.Phase(
        name=name, space_group="P m -3 m", cell=_cell(),
        atoms=[rx.Atom(label="A", species="Si", x=p(value=0.0),
                       y=p(value=0.0), z=p(value=0.0))],
        **kw)


class _FakeModel:
    """Enough ``CompiledModel`` for the tier-2 flag: it reads ``phases`` only
    to learn how many there are, and the values out of the decoded dict."""

    def __init__(self, n: int = 1):
        self.phases = [object()] * n


# ----------------------------------------------------------------------
# tier 1: the number comes from the data
# ----------------------------------------------------------------------
def test_the_cap_is_the_fitted_range_over_tan_theta_max():
    """Γ_L = lor_strain·tanθ, held to one fitted range at the highest θ."""
    cap = strain_cap(10.0, 80.0)
    assert cap == pytest.approx(
        STRAIN_CAP_RANGE_FRACTION * 70.0 / math.tan(math.radians(40.0)))
    # the statement it encodes: at the top of the range, that much strain and
    # nothing else contributes exactly one range's worth of FWHM
    assert cap * math.tan(math.radians(40.0)) == pytest.approx(70.0)


def test_the_cap_is_self_scaling_rather_than_a_constant():
    """A lab scan and a low-angle synchrotron scan get different caps.

    The point of deriving it from the data: no magic constant, and the bound
    tracks what the measurement can express.  A short high-angle scan can state
    a *tighter* bound than a long low-angle one, because tanθ is bigger there —
    the same strain buys more width.
    """
    lab = strain_cap(15.0, 80.0)
    synchrotron = strain_cap(0.5, 50.0)
    narrow = strain_cap(70.0, 80.0)
    assert lab != synchrotron != narrow
    assert narrow < lab < synchrotron
    # Generous by construction: the tightest of the three is a deliberately
    # pathological 10°-wide window at high angle, and even that clears the
    # TOPAS protocol's 0.3 on this data by 40× and the tier-2 flag by 8×.  A
    # cap that could fire on an honest fit would be worse than no cap.
    assert min(lab, synchrotron, narrow) > 30 * 0.3
    assert min(lab, synchrotron, narrow) > 5 * STRAIN_FLAG_WIDTH


def test_a_range_that_states_nothing_caps_nothing():
    """"No claim" is the honest output, not a bound of zero."""
    assert strain_cap(10.0, 10.0) == math.inf   # empty range
    assert strain_cap(80.0, 10.0) == math.inf   # reversed
    assert strain_cap(0.0, 0.0) == math.inf
    # a pattern reaching 2θ = 180° would put tanθ on its pole; the cap stays
    # finite and positive rather than collapsing for an arithmetic reason
    assert 0.0 < strain_cap(0.0, 180.0) < math.inf


def test_the_gaussian_term_is_capped_as_a_variance():
    """``gauss_strain`` multiplies tan²θ, so it takes the square of the width.

    One number governs both terms; there is no second constant to calibrate.
    """
    cap = strain_cap(10.0, 80.0)
    assert strain_cap_hi("gauss_strain", cap * cap, math.inf, cap) == cap * cap
    # a variance below the squared width is not capped even though its bare
    # number is far above the width itself
    assert strain_cap_hi("gauss_strain", cap * 1.5, math.inf, cap) == math.inf


# ----------------------------------------------------------------------
# tier 1: it is armed only where it is needed — this is what buys identity
# ----------------------------------------------------------------------
def test_the_cap_is_armed_only_where_the_term_has_reached_it():
    cap = strain_cap(10.0, 80.0)
    assert strain_cap_hi("lor_strain", 0.02, math.inf, cap) == math.inf
    assert strain_cap_hi("lor_strain", 1.0, math.inf, cap) == math.inf
    assert strain_cap_hi("lor_strain", cap, math.inf, cap) == cap
    assert strain_cap_hi("lor_strain", 1.1e5, math.inf, cap) == cap


def test_the_arming_test_has_hysteresis_so_a_capped_stage_stays_capped():
    """TRF leaves a bounded iterate a hair inside its bound.

    An exactly-equal test would disarm the cap on the very next stage and let
    the runaway restart, alternating capped and uncapped stages so that whether
    the answer is bounded came down to the parity of the stage count.
    """
    cap = strain_cap(10.0, 80.0)
    just_inside = cap * (1.0 - STRAIN_CAP_ARM_RTOL / 2.0)
    assert just_inside < cap
    assert strain_cap_hi("lor_strain", just_inside, math.inf, cap) == cap
    # and the slack is not so wide that it reaches a value a fit means
    assert strain_cap_hi("lor_strain", cap / 2.0, math.inf, cap) == math.inf


def test_a_caller_declared_bound_outranks_the_cap_and_silences_it():
    """The one-line off switch: any finite ``Parameter.max`` is the claim.

    ``cell_window``'s rule, and TOPAS's — *"user defined min/max limits
    override the defaults"*.  ±inf is what a Parameter carries when nobody set
    its bounds, so an infinite side is the only side on which no claim was
    made.
    """
    cap = strain_cap(10.0, 80.0)
    # tighter than the cap
    assert strain_cap_hi("lor_strain", 1.1e5, 0.3, cap) == 0.3
    # *looser* than the cap — deliberately enormous, which is how a caller
    # switches the cap off rather than merely moving it
    assert strain_cap_hi("lor_strain", 1.1e5, 1e9, cap) == 1e9
    # and a cap of inf (an unusable range) never invents one
    assert strain_cap_hi("lor_strain", 1.1e5, math.inf, math.inf) == math.inf


# ----------------------------------------------------------------------
# tier 1: identity, at the table
# ----------------------------------------------------------------------
def _one_phase_table(strain: float, **kw) -> ParameterTable:
    phase = _phase(lor_strain=rx.Parameter(
        value=strain, min=0.0, transform="softplus", **kw))
    table = ParameterTable(rx.Structure(phases=[phase]),
                           rx.Instrument.bragg_brentano())
    table.set_vary(["phases.*.lor_strain"], True)
    return table


def test_a_fit_below_the_cap_is_bounded_exactly_as_before():
    """**The assertion the whole design exists to keep.**

    A finite bound changes the solver's step in a coordinate even where it is
    never approached, so an untriggered fit must not get one.  Compared as the
    bound arrays themselves rather than as a fit result, because that is the
    only thing the cap can possibly change: identical bounds in, identical
    trajectory out.
    """
    table = _one_phase_table(0.02)
    lo_before, hi_before = table.bounds()
    table.freeze_strain_cap(strain_cap(10.0, 80.0))
    lo_after, hi_after = table.bounds()
    assert np.array_equal(lo_before, lo_after)
    assert np.array_equal(hi_before, hi_after)
    # and the strain column really is the unbounded one, so the comparison
    # above is not vacuously true of some other column
    k = table.free_paths.index("phases.0.lor_strain")
    assert hi_after[k] == math.inf


def test_a_term_past_the_cap_is_bounded_at_the_table():
    table = _one_phase_table(1.1e5)
    cap = strain_cap(10.0, 80.0)
    table.freeze_strain_cap(cap)
    _, hi = table.bounds()
    k = table.free_paths.index("phases.0.lor_strain")
    # internal space is softplus, so compare after mapping back
    from rietx.params.transforms import to_physical
    assert to_physical(float(hi[k]), "softplus") == pytest.approx(cap, rel=1e-9)


def test_no_claim_frozen_caps_nothing():
    """``None`` is ``freeze_cell_windows``' convention and means no claim."""
    table = _one_phase_table(1.1e5)
    table.freeze_strain_cap(None)
    _, hi = table.bounds()
    assert hi[table.free_paths.index("phases.0.lor_strain")] == math.inf


def test_a_locked_lor_strain_cannot_be_capped():
    """A Stephens block *locks* ``lor_strain`` — no contradiction is possible.

    Its isotropic direction is identically that column, so a declared
    ``microstrain`` block holds the term fixed; a fixed entry is not in the
    free vector and ``bounds()`` never sees it.  The cap therefore cannot
    contradict the lock, which is the interaction worth pinning rather than
    assuming.
    """
    from rietx.schemas.structure import StephensStrain

    phase = _phase(
        lor_strain=rx.Parameter(value=1.1e5, min=0.0, transform="softplus"),
        microstrain=StephensStrain.isotropic(1e-3, _cell()))
    table = ParameterTable(rx.Structure(phases=[phase]),
                           rx.Instrument.bragg_brentano())
    assert table.set_vary(["phases.*.lor_strain"], True) == []
    table.freeze_strain_cap(strain_cap(10.0, 80.0))
    assert "phases.0.lor_strain" not in table.free_paths
    table.bounds()   # and it does not raise


# ----------------------------------------------------------------------
# tier 2: the flag, and what it must not do
# ----------------------------------------------------------------------
def test_the_flag_sits_above_the_corpus_of_solved_refinements():
    """Set from the archive's 606 TOPAS refinements, not from taste.

    p99 of 1213 strain records is 1.21 and the hand-written ceilings those
    authors used top out at 1.5; above that the corpus holds 8 records in 5
    contexts, every one a divergence signature.  Pinned so that a later edit
    to the constant has to argue with the survey.
    """
    assert STRAIN_FLAG_WIDTH == 1.5
    # two orders of magnitude below the numerical fence on a normal lab scan:
    # the tiers must not collapse into each other
    assert strain_cap(10.0, 80.0) > 30 * STRAIN_FLAG_WIDTH


def test_a_legitimately_broad_fit_is_not_flagged():
    """The regression that matters: nanocrystalline and defective specimens
    live in the corpus's 0.4-1.5 tail (dozens of independent files) and must
    stay silent, or the flag is noise and gets ignored."""
    from rietx.refine import _strain_flag_diagnostics

    structure = rx.Structure(phases=[_phase("nanocrystalline")])
    for width in (0.3, 0.7, 1.2, 1.5):
        values = {"phases.0.lor_strain": width, "phases.0.gauss_strain": 0.0}
        assert _strain_flag_diagnostics(_FakeModel(), values, structure) == [], width


def test_the_flag_names_the_phase_and_the_value():
    from rietx.refine import _strain_flag_diagnostics

    structure = rx.Structure(phases=[_phase("mayenite")])
    found = _strain_flag_diagnostics(
        _FakeModel(),
        {"phases.0.lor_strain": 2.2e5, "phases.0.gauss_strain": 0.0},
        structure)
    assert [d.code for d in found] == ["STRAIN_UNUSUALLY_LARGE"]
    d = found[0]
    assert d.where == ["phases.0.lor_strain"]
    assert d.value == pytest.approx(2.2e5)
    assert "mayenite" in d.message and "2.2e+05" in d.message
    # the register: a number to check, not a refusal and not a certificate
    assert "physically possible" in d.suggestion
    assert d.level == "warning"


def test_the_flag_reads_gauss_strain_as_a_variance():
    """``gauss_strain`` is deg², so it is compared as its square root.

    Without the conversion the flag would fire on every Gaussian variance above
    1.5 deg² — a width of only 1.22 deg — and be wrong about the units.
    """
    from rietx.refine import _strain_flag_diagnostics

    structure = rx.Structure(phases=[_phase()])
    below = {"phases.0.lor_strain": 0.0,
             "phases.0.gauss_strain": STRAIN_FLAG_WIDTH ** 2 * 0.9}
    above = {"phases.0.lor_strain": 0.0,
             "phases.0.gauss_strain": STRAIN_FLAG_WIDTH ** 2 * 1.5}
    assert _strain_flag_diagnostics(_FakeModel(), below, structure) == []
    flagged = _strain_flag_diagnostics(_FakeModel(), above, structure)
    assert [d.where for d in flagged] == [["phases.0.gauss_strain"]]
    # reported as the width it contributes, not as the stored variance
    assert flagged[0].value == pytest.approx(
        math.sqrt(STRAIN_FLAG_WIDTH ** 2 * 1.5))
