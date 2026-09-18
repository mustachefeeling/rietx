"""A_τ, the per-irrep amplitude, and what it is the verdict on (M-3).

WP-1419 § Inherited's fourth finding: "the reported quantity is the per-irrep
amplitude, not the basis components."  AMPLIMODES (Perez-Mato, Orobengoa &
Aroyo 2010, *Acta Cryst.* A**66**, 558) normalises each mode in absolute units
within a primitive cell of the child lattice (eq 3) *and* orthonormalises the
basis (eq 4) — and the second of those is free across irreps and across parent
orbits.  So an individual A_{τ,m} is a number about a basis somebody chose, and
only their eq (6)–(7) combination

    A_τ = (Σ_m A²_{τ,m})^½,   a_{τ,m} = A_{τ,m} / A_τ

survives the freedom.  Three groups here, and each pins one half of that:

* **invariant.**  An orthogonal rotation inside one component leaves A_τ and
  its esd exactly where they were while moving every component of the basis.
  Pinned twice: on the propagation arithmetic alone (to roundoff) and through
  two independent fits of the same data in two bases (to the solver's own
  tolerance).
* **the verdict moves.**  ``DISTORTION_MODE_UNSUPPORTED`` is gated on A_τ, so
  it is silent on a supported order parameter whose basis happens to put the
  amplitude in one component, and fires on an unsupported one however the
  amplitude is spread.
* **the degenerate case.**  Every A_{τ,m} exactly zero gives A_τ = 0, an
  undefined unit direction and a Jacobian that does not exist; the row says so
  rather than reporting a zero with an esd beside it.

The esd is propagated through the **block** covariance, σ²(A_τ) = aᵀ·Cov(A)·a —
the J·Cov·Jᵀ pattern of :func:`rietx.optimize.qpa.weight_fractions` and
:mod:`rietx.model.geometry`, and McCusker *et al.* (1999), *J. Appl. Cryst.*
**32**, 36, § 10's requirement that the whole correlation matrix be used.  A
full mode basis of one direction is collinear by construction, so the
independent approximation is not a near miss here.
"""

import numpy as np
import pytest

import rietx as rx
from rietx import Refinement
from rietx.report.distortion import analyse_distortion_totals
from rietx.report.schemas import (
    DISTORTION_SIGN_CONVENTION,
    DistortionTotal,
)
from rietx.schemas.structure import Structure
from tests.test_distortion_amplitude_absolute import (
    A_A,
    AMPLITUDE_GLOB,
    C_A,
    instrument,
    simulate,
)

PATHS = ["phases.0.distortion_modes.0.amplitude",
         "phases.0.distortion_modes.1.amplitude"]


def rotated_toy(theta_rad, amplitudes, *, name="toy"):
    """The two-mode toy with its basis rotated by an orthogonal 2×2.

    e′₁ = c·e₁ + s·e₂ and e′₂ = −s·e₁ + c·e₂ span the same plane, so the set of
    structures the component can reach is unchanged; the amplitudes that name
    one particular structure are not.  ``amplitudes`` is (A′₁, A′₂) in the
    rotated basis.
    """
    from rietx import DistortionMode
    from rietx.schemas.common import Parameter
    from rietx.schemas.structure import Atom, Cell, Phase

    e1 = np.array([[0.0, 0.0, 1.0 / C_A], [0.0, 0.0, -1.0 / C_A],
                   [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    e2 = np.array([[1.0 / A_A, 0.0, 0.0], [-1.0 / A_A, 0.0, 0.0],
                   [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    c, s = np.cos(theta_rad), np.sin(theta_rad)
    vectors = [c * e1 + s * e2, -s * e1 + c * e2]
    shift = sum(a * v for a, v in zip(amplitudes, vectors, strict=True))
    base = [(0.0, 0.0, 0.25), (0.0, 0.0, 0.75),
            (0.5, 0.5, 0.0), (0.5, 0.5, 0.5)]
    labels = (("Sr1", "Sr"), ("Sr2", "Sr"), ("O1", "O"), ("O2", "O"))
    modes = [DistortionMode(
        name=f"X-Sr-{m}", irrep_label="X", direction="(a)",
        k=("0", "0", "1/2"), parent_site="Sr",
        vectors=[tuple(float(x) for x in row) for row in v],
        amplitude=Parameter(value=float(a), vary=False, min=-0.5, max=0.5,
                            unit="A"))
        for m, (v, a) in enumerate(zip(vectors, amplitudes, strict=True))]
    atoms = [Atom(label=lab, species=sp,
                  x=Parameter(value=base[j][0] + shift[j][0]),
                  y=Parameter(value=base[j][1] + shift[j][1]),
                  z=Parameter(value=base[j][2] + shift[j][2]),
                  biso=Parameter(value=0.5 if sp == "Sr" else 0.7))
             for j, (lab, sp) in enumerate(labels)]
    return Phase(
        name=name, space_group="P 1",
        cell=Cell(a=Parameter(value=A_A), b=Parameter(value=A_A),
                  c=Parameter(value=C_A), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=atoms, scale=Parameter(value=0.02), distortion_modes=modes)


@pytest.fixture(scope="module")
def two_mode_truth():
    """A pattern from the two-mode component at (0.12, 0.09) Å: A_τ = 0.15 Å."""
    truth = rotated_toy(0.0, (0.12, 0.09))
    return simulate(truth, seed=23)


def _fit(phase, data, *, seed=0.02, max_iter=400):
    ref = Refinement(Structure(phases=[phase]), instrument())
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"],
                 max_iter=100),
        rx.Stage("modes", ["phases.*.scale", AMPLITUDE_GLOB],
                 max_iter=max_iter, distortion_seed=seed)]))
    return ref, result


# ------------------------------------------------------------- invariant (a)
def test_the_propagation_is_exactly_rotation_invariant():
    """aᵀ·Cov·a under A → R·A, Cov → R·Cov·Rᵀ, to roundoff.

    The arithmetic on its own, with a hand-written covariance, so the claim is
    pinned without a solver's tolerance in the way.  A strongly correlated
    block is used on purpose: ρ = 0.97 is what a full mode basis of one
    direction actually looks like, and it is where the independent
    approximation is furthest from the answer.
    """
    a = np.array([0.12, 0.09])
    sig = np.array([0.05, 0.04])
    rho = 0.97
    cov = np.array([[sig[0] ** 2, rho * sig[0] * sig[1]],
                    [rho * sig[0] * sig[1], sig[1] ** 2]])

    def total_and_esd(amps, block):
        norm = float(np.linalg.norm(amps))
        unit = amps / norm
        return norm, float(np.sqrt(unit @ block @ unit))

    base = total_and_esd(a, cov)
    for angle in (0.1, 0.7, 1.3, 2.9):
        c, s = np.cos(angle), np.sin(angle)
        r = np.array([[c, -s], [s, c]])
        got = total_and_esd(r @ a, r @ cov @ r.T)
        assert abs(got[0] - base[0]) <= 1e-15 * base[0]
        assert abs(got[1] - base[1]) <= 1e-13 * base[1]
    # and the components genuinely move
    turned = np.array([[0.0, -1.0], [1.0, 0.0]]) @ a
    assert abs(turned[0] - a[0]) > 0.15


def test_a_rotated_basis_gives_the_same_atau_from_an_independent_fit(
        two_mode_truth):
    """Two fits of one pattern in two bases: A_τ and σ(A_τ) agree, the
    components do not.

    The physical half of the claim.  The two models span the same plane of
    structures, so they converge to the same point and the same Rwp; what
    differs is the coordinates the answer is written in.
    """
    data = two_mode_truth
    angle = 0.6
    _ref_a, result_a = _fit(rotated_toy(0.0, (0.0, 0.0)), data)
    _ref_b, result_b = _fit(rotated_toy(angle, (0.0, 0.0)), data)
    assert result_a.status == result_b.status == "converged"

    total_a, = result_a.distortion_totals
    total_b, = result_b.distortion_totals
    assert total_a.amplitude_esd is not None
    assert total_b.amplitude_esd is not None
    # ≤ 1e-10 absolute, which is the brief's figure and about as far as two
    # independent solves of the same problem can be asked to agree
    assert abs(total_b.amplitude - total_a.amplitude) <= 1e-10, (
        f"A_τ is basis-dependent: {total_b.amplitude!r} against "
        f"{total_a.amplitude!r}")
    # the esd is a second-order quantity read off the converged Jacobian, so
    # it inherits the solve's tolerance twice over: measured 3.5e-10 absolute
    # on a number of size 2.4e-4, i.e. 1.5e-6 relative
    assert total_b.amplitude_esd == pytest.approx(
        total_a.amplitude_esd, rel=1e-5), (
        f"σ(A_τ) is basis-dependent: {total_b.amplitude_esd!r} against "
        f"{total_a.amplitude_esd!r}")
    assert result_b.statistics.rwp == pytest.approx(
        result_a.statistics.rwp, rel=1e-9)

    # the components are not invariant, and by a lot
    comp_a = np.array([abs(v) for v in total_a.unit_direction])
    comp_b = np.array([abs(v) for v in total_b.unit_direction])
    assert np.abs(comp_b - comp_a).max() > 0.2, (
        f"the rotation did not move the basis: {comp_a} vs {comp_b}")
    # and A_τ found the planted 0.15 Å
    assert abs(total_a.amplitude - 0.15) <= 2.0 * total_a.amplitude_esd


def test_the_independent_esd_is_basis_dependent_and_the_block_one_is_not(
        two_mode_truth):
    """§ 10's warning, made visible rather than asserted — and sharpened.

    The diagonal-only esd is not merely approximate here: it is a *different
    number in a different basis* while describing the same structure.  Measured
    on this fixture, the same fit reports σ_indep(A_τ) = 4.45e-4 in one basis
    and 2.43e-4 in a basis rotated by 0.6 rad, a factor 1.8, while the block
    propagation gives 2.4106e-4 in both.  A diagonal esd on a mode basis is
    therefore a statement about the orthogonalisation, which is exactly what
    A_τ exists to stop reporting.
    """
    _a, result_a = _fit(rotated_toy(0.0, (0.0, 0.0)), two_mode_truth)
    _b, result_b = _fit(rotated_toy(0.6, (0.0, 0.0)), two_mode_truth)
    total_a, = result_a.distortion_totals
    total_b, = result_b.distortion_totals
    for total in (total_a, total_b):
        assert total.amplitude_esd is not None
        assert total.amplitude_esd_independent is not None

    assert total_b.amplitude_esd == pytest.approx(
        total_a.amplitude_esd, rel=1e-5)
    spread = (total_a.amplitude_esd_independent
              / total_b.amplitude_esd_independent)
    assert not np.isclose(spread, 1.0, rtol=0.1), (
        f"the independent esd barely moved under the rotation ({spread:.3f}); "
        f"this fixture does not exercise the correlation the block covariance "
        f"exists for")
    assert total_a.amplitude_esd_independent > 1.5 * total_a.amplitude_esd


# ------------------------------------------------------------ the verdict (b)
def test_the_diagnostic_fires_on_an_unsupported_order_parameter():
    """The positive arm of the new gate: a pattern with no distortion in it."""
    parent_pattern = simulate(rotated_toy(0.0, (0.0, 0.0)), seed=29)
    _ref, result = _fit(rotated_toy(0.0, (0.0, 0.0)), parent_pattern)
    total, = result.distortion_totals
    assert total.amplitude_esd is not None
    assert not total.supported, (
        f"A_τ = {total.amplitude:.4g} ± {total.amplitude_esd:.4g} on a pattern "
        f"with no distortion in it")
    fired = [d for d in result.diagnostics
             if d.code == "DISTORTION_MODE_UNSUPPORTED"]
    assert len(fired) == 1, [d.message for d in fired]
    assert fired[0].where == PATHS, (
        "the diagnostic names the whole component, not one amplitude")
    assert "A_τ" in fired[0].message
    assert "basis-independent" in fired[0].message


def test_a_held_component_never_raises_the_diagnostic(two_mode_truth):
    """A statement the caller made is not a measurement to warn about."""
    ref = Refinement(Structure(phases=[rotated_toy(0.0, (0.001, 0.0))]),
                     instrument())
    result = ref.fit(two_mode_truth, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"],
                 max_iter=100)]))
    assert not [d for d in result.diagnostics
                if d.code == "DISTORTION_MODE_UNSUPPORTED"]
    total, = result.distortion_totals
    assert total.supported and total.amplitude_esd is None
    assert "no esd was measured" in total.note


# ----------------------------------------------------------- degenerate (c)
def test_a_component_at_exactly_zero_reports_no_direction_and_no_esd():
    """A_τ = 0: the unit direction is 0/0 and ‖A‖ has no derivative there."""
    structure = Structure(phases=[rotated_toy(0.0, (0.0, 0.0))])
    total, = analyse_distortion_totals(structure)
    assert total.amplitude == 0.0
    assert total.unit_direction == []
    assert total.amplitude_esd is None
    assert total.amplitude_esd_independent is None
    assert total.supported, "nothing measured it, so nothing calls it unsupported"
    assert "not differentiable at the origin" in total.note
    assert "states the parent structure" in total.note


def test_a_component_at_zero_with_esds_is_not_supported():
    """The same state, but something did measure it: then it is a verdict."""
    structure = Structure(phases=[rotated_toy(0.0, (0.0, 0.0))])
    total, = analyse_distortion_totals(
        structure, esd={p: 0.01 for p in PATHS})
    assert total.amplitude == 0.0 and not total.supported
    assert total.amplitude_esd is None


# ---------------------------------------------------------------- the shape
def test_the_row_names_the_component_and_its_modes(two_mode_truth):
    _ref, result = _fit(rotated_toy(0.0, (0.0, 0.0)), two_mode_truth)
    total, = result.distortion_totals
    assert isinstance(total, DistortionTotal)
    assert total.phase == "toy"
    assert total.irrep_label == "X" and total.direction == "(a)"
    assert total.k == ["0", "0", "1/2"]
    assert total.modes == ["X-Sr-0", "X-Sr-1"]
    assert total.paths == PATHS
    assert total.n_modes == 2
    assert total.max_displacement_a == pytest.approx(1.0, abs=1e-9)
    assert np.isclose(np.linalg.norm(total.unit_direction), 1.0, atol=1e-12)


def test_the_report_carries_what_the_fit_measured(two_mode_truth):
    """The report copies the fit-close row rather than recomputing a diagonal one."""
    ref, result = _fit(rotated_toy(0.0, (0.0, 0.0)), two_mode_truth)
    report = ref.report()
    assert len(report.distortion_totals) == 1
    assert report.distortion_totals[0] == result.distortion_totals[0]
    assert report.distortion_totals[0].amplitude_esd is not None


def test_a_structure_only_report_falls_back_to_the_independent_esd():
    """Without a covariance the row says which esd it is quoting."""
    structure = Structure(phases=[rotated_toy(0.0, (0.12, 0.09))])
    total, = analyse_distortion_totals(
        structure, esd={PATHS[0]: 0.02, PATHS[1]: 0.03})
    assert total.amplitude == pytest.approx(0.15, abs=1e-12)
    assert total.amplitude_esd is None
    assert total.amplitude_esd_independent is not None
    assert "independent approximation" in total.note


# ------------------------------------------------- the sign convention (M-3 item 4)
def test_every_printed_amplitude_states_the_sign_convention(two_mode_truth):
    """Grep the rendered report: one sentence, verbatim, on every row.

    "Anything printing an amplitude states the convention, or it is the
    confident wrong singleton the FitReport rule forbids" (WP-1419
    § Inherited).  One shared string rather than a phrasing per printer, so a
    reader meets the same words on a report row, on a component row and in a
    diagnostic — and so this test is a grep rather than a paraphrase check.
    """
    ref, result = _fit(rotated_toy(0.0, (0.0, 0.0)), two_mode_truth)
    report = ref.report()
    assert report.distortion, "nothing was printed at all"
    for row in report.distortion:
        assert DISTORTION_SIGN_CONVENTION in row.note, row.mode
    for total in report.distortion_totals:
        assert DISTORTION_SIGN_CONVENTION in total.note, total.irrep_label

    # the held case and the unsupported case print it too
    held = analyse_distortion_totals(Structure(phases=[rotated_toy(
        0.0, (0.12, 0.09))]))
    assert DISTORTION_SIGN_CONVENTION in held[0].note
    unsupported = analyse_distortion_totals(
        Structure(phases=[rotated_toy(0.0, (0.001, 0.0005))]),
        esd=dict.fromkeys(PATHS, 0.01))
    assert not unsupported[0].supported
    assert DISTORTION_SIGN_CONVENTION in unsupported[0].note

    # and the diagnostic
    parent_pattern = simulate(rotated_toy(0.0, (0.0, 0.0)), seed=29)
    _r, bad = _fit(rotated_toy(0.0, (0.0, 0.0)), parent_pattern)
    fired = [d for d in bad.diagnostics
             if d.code == "DISTORTION_MODE_UNSUPPORTED"]
    assert fired and DISTORTION_SIGN_CONVENTION in fired[0].message


def test_the_convention_names_the_primary_mode_and_states_it_positive(
        two_mode_truth):
    """The gauge: the largest |A| is the primary mode and is printed positive."""
    _ref, result = _fit(rotated_toy(0.0, (0.0, 0.0)), two_mode_truth)
    total, = result.distortion_totals
    values = [result.parameter(p).value for p in PATHS]
    biggest = max(range(len(values)), key=lambda i: abs(values[i]))
    assert total.primary_mode == total.modes[biggest]
    assert total.unit_direction[biggest] > 0.0
    assert total.domain_sign == (1 if values[biggest] >= 0 else -1)


def test_the_convention_is_a_gauge_and_loses_nothing(two_mode_truth):
    """``domain_sign`` × ``unit_direction`` is the refined direction, exactly.

    The reason this package fixes the sign rather than dropping it in favour of
    |A|: the relative signs inside a component say whether two sublattices move
    together or against each other, and that *is* measured.  Nothing printed
    here is a second authority on ``RefinementResult.parameters`` — the
    convention is recoverable from the row.
    """
    _ref, result = _fit(rotated_toy(0.0, (0.0, 0.0)), two_mode_truth)
    total, = result.distortion_totals
    refined = np.array([result.parameter(p).value for p in PATHS])
    recovered = (total.domain_sign * np.array(total.unit_direction)
                 * total.amplitude)
    assert np.abs(recovered - refined).max() < 1e-12


def test_both_domains_print_the_same_relative_signs(two_mode_truth):
    """Seeded ±, the two runs differ by ``domain_sign`` and nothing else.

    The measurement behind the convention: the two antiphase domains are one
    structure, so the gauge-fixed direction has to be identical and only the
    label that says which domain the solver landed in may differ.
    """
    _a, plus = _fit(rotated_toy(0.0, (0.0, 0.0)), two_mode_truth, seed=0.02)
    _b, minus = _fit(rotated_toy(0.0, (0.0, 0.0)), two_mode_truth, seed=-0.02)
    tp, = plus.distortion_totals
    tm, = minus.distortion_totals
    assert tp.domain_sign == 1 and tm.domain_sign == -1
    assert tp.primary_mode == tm.primary_mode
    assert np.allclose(tp.unit_direction, tm.unit_direction, atol=1e-6), (
        f"the gauge-fixed direction differs between domains: "
        f"{tp.unit_direction} against {tm.unit_direction}")
    assert plus.statistics.rwp == pytest.approx(minus.statistics.rwp, rel=1e-12)
