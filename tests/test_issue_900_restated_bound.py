"""Issue #900: a scale started 2400× high, with a restated ``min=0.0``.

Before WP-1938 a restated bound dropped the field's softplus, and TRF then
damped the scale hardest while the Biso values absorbed the excess intensity:
χ² 2.657e5 with Pb Biso 61, ``converged``.  Every field is refined in physical
units now, so the two spellings are one parameterisation, and the default LM
driver reaches the true basin from either.  TRF still fails on this start
(χ² 4.5e5, ``max_iter``), loudly: ``STAGE_MAX_ITER`` and
``BISO_UNUSUALLY_LARGE`` among seven warnings (WP-1938's 2026-10-11 Context).

Synthetic PbSO₄ with Poisson noise, no download, the issue's own script.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx


def P(v, **kw):
    return rx.Parameter(value=v, **kw)


def _build(scale):
    def atom(lab, sp, x, y, z, b):
        return rx.Atom(label=lab, species=sp, x=P(x), y=P(y), z=P(z),
                       biso=P(b, min=0.0))
    phase = rx.Phase(
        name="PbSO4", space_group="P n m a",
        cell=rx.Cell(a=P(8.4824), b=P(5.3999), c=P(6.9618),
                     alpha=P(90.0), beta=P(90.0), gamma=P(90.0)),
        atoms=[atom("Pb", "Pb", 0.1878, 0.25, 0.1673, 1.49),
               atom("S", "S", 0.0639, 0.25, 0.6848, 0.91),
               atom("O1", "O", 0.9083, 0.25, 0.5944, 0.63),
               atom("O2", "O", 0.1858, 0.25, 0.5394, 1.43),
               atom("O3", "O", 0.0792, 0.0265, 0.8126, 0.94)],
        scale=scale)
    ins = rx.Instrument.bragg_brentano(radiation="CuKa", monochromator_two_theta=26.6)
    ins.source.dispersion = None        # declared, never inherited (root CLAUDE.md)
    ins.background = rx.BackgroundChebyshev(coefficients=[P(150.0)] + [P(0.0)] * 5)
    ins.profile = rx.ProfileTCHZ(u=P(0.03), v=P(-0.05), w=P(0.03), x=P(0.01), y=P(0.01))
    return rx.Structure(phases=[phase]), ins


TRUE_SCALE = 4.2e-4
TRUE_BISO_PB = 1.49
ALL = ["phases.*.scale", "instrument.background.*", "instrument.zero_shift",
       "phases.*.cell.*", "instrument.profile.*", "phases.*.atoms.*.dof.*",
       "phases.*.atoms.*.biso"]


@pytest.fixture(scope="module")
def synthetic():
    tt = np.arange(10.0, 150.0, 0.025)
    s_true, i_true = _build(P(TRUE_SCALE))
    i_true.profile = rx.ProfileTCHZ(u=P(0.0), v=P(0.0), w=P(0.0015), x=P(0.03), y=P(0.09))
    y_true = np.asarray(rx.Refinement(s_true, i_true).predict(tt))
    y = np.random.default_rng(0).poisson(y_true).astype(float)
    sigma = np.sqrt(np.maximum(y, 1))
    data = rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist(), sigma=sigma.tolist())
    chi2_truth = float(np.sum(((y - y_true) / sigma) ** 2))
    return data, chi2_truth


@pytest.mark.parametrize("label, bound", [("restated", {"min": 0.0}), ("bare", {})])
def test_the_default_driver_reaches_the_true_basin_from_a_restated_bound(synthetic, label, bound):
    data, chi2_truth = synthetic
    structure, ins = _build(P(1.0, **bound))
    ref = rx.Refinement(structure, ins)
    plan = rx.RefinementPlan(stages=[rx.Stage(name="all", turn_on=ALL, max_iter=200)])
    result = ref.fit(data, plan=plan, telemetry=False)
    values = {r.path: r.value for r in ref.parameters()}
    chi2 = 2.0 * result.stages[-1].cost_final
    assert result.status == "converged"
    # One stage freezes its peak windows at the start's widths (root CLAUDE.md,
    # frozen-per-stage discreteness), and the Lorentzian widths here grow
    # threefold, so even the right basin sits above the truth's χ²: 7304
    # against 5777 (WP-1938, macOS arm64).  The wrong basin sat 37 to 78
    # times above it.
    assert chi2 < 2.0 * chi2_truth
    assert values["phases.0.scale"] == pytest.approx(TRUE_SCALE, rel=0.02)
    assert values["phases.0.atoms.0.biso"] == pytest.approx(TRUE_BISO_PB, abs=0.3)
    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / f"issue_900_{label}.png"))
