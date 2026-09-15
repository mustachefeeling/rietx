"""WP-1402 — the numbers behind a stage's picture.

The snapshot replaced a self-contained plotly page written on the fit's own
thread. What has to hold is that it is the *same picture*: the curves are the
fit's curves, every emission line's ticks are there, and a cap that fired says
so. The payload's own size is measured in the WP's handover, not asserted here
— a byte count is a fact about plotly's bundle and this machine, not about the
code.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.history.events import EventStream
from rietx.viz import snapshot as snap
from tests.test_refine_synthetic import perturbed_models, synthesize

OUT = Path(__file__).parent / "output"


@pytest.fixture(scope="module")
def synthetic_pattern():
    return synthesize()


class _Capture(EventStream):
    """A sink that keeps what a stage handed it, rather than writing a file.

    Subclasses ``EventStream`` for the reason ``LiveSession`` does: that is
    what ``events=`` accepts, and ``write_snapshot`` is found on it by the same
    duck typing the real sink is found by.
    """

    def __init__(self):
        super().__init__()
        self.calls = []

    def write_snapshot(self, model, table, outcome, stage_name):
        self.calls.append((model, table, outcome, stage_name))


@pytest.fixture(scope="module")
def last_stage(synthetic_pattern):
    """``(model, table, outcome, stage_name)`` from a real fit's last stage."""
    structure, ins = perturbed_models()
    cap = _Capture()
    rx.Refinement(structure, ins, history=False).fit(
        synthetic_pattern, events=cap)
    assert cap.calls, "no stage handed the sink a snapshot"
    return cap.calls[-1]


# ----------------------------------------------------------------------
# the curves are the fit's curves
# ----------------------------------------------------------------------
def test_the_snapshot_curves_are_the_fits_curves(last_stage):
    """Decimated and rounded, and equal to the model's own arrays there.

    The tolerance is the rounding's, not the model's: six significant figures
    is at worst 5e-6 relative. Anything looser would hide a curve built from
    the wrong θ.
    """
    model, table, outcome, name = last_stage
    payload = snap.build_snapshot(model, table, outcome, name)

    values = table.decode(outcome.theta)
    tt = np.asarray(model.tt, dtype=np.float64)
    y_calc = np.asarray(model.evaluate(values), dtype=np.float64)
    y_bkg = np.asarray(model.background(values), dtype=np.float64)
    sigma = np.asarray(model.sigma, dtype=np.float64)
    delta = (np.asarray(model.y_obs, dtype=np.float64) - y_calc) / sigma

    # the index set the payload kept, recovered from its own 2θ column
    drawn = np.asarray(payload["two_theta"], dtype=np.float64)
    idx = np.searchsorted(tt, drawn - 1e-9)
    assert np.allclose(tt[idx], drawn, atol=5e-6), "2θ is not the fit's grid"

    for field, truth in (("y_obs", np.asarray(model.y_obs, dtype=np.float64)),
                         ("y_calc", y_calc), ("y_bkg", y_bkg),
                         ("delta", delta)):
        got = np.asarray(payload[field], dtype=np.float64)
        assert np.allclose(got, truth[idx], rtol=1e-5, atol=1e-12), field

    assert payload["n_points"] == len(tt)
    assert payload["n_drawn"] == len(drawn) < payload["n_points"]


def test_delta_is_over_the_models_own_sigma(last_stage):
    """Δ/σ, with σ looked up rather than re-derived (WP-1029).

    A Poisson re-derivation from ``y_obs`` would agree on a synthetic pattern
    whose σ *is* the Poisson fallback, so the check is against the array the
    model stored, point by point.
    """
    model, table, outcome, name = last_stage
    payload = snap.build_snapshot(model, table, outcome, name)
    values = table.decode(outcome.theta)

    drawn = np.asarray(payload["two_theta"], dtype=np.float64)
    idx = np.searchsorted(np.asarray(model.tt, dtype=np.float64), drawn - 1e-9)
    expect = ((np.asarray(model.y_obs, dtype=np.float64)
               - np.asarray(model.evaluate(values), dtype=np.float64))
              / np.asarray(model.sigma, dtype=np.float64))[idx]
    assert np.allclose(np.asarray(payload["delta"], dtype=np.float64),
                       expect, rtol=1e-5, atol=1e-12)


def test_decimation_keeps_a_peak_top(last_stage):
    """The one authority on which points survive, exercised through here.

    Striding would drop peak tops, and a live view whose peaks are shorter
    than the fit's is a picture of a worse fit than the one that ran.
    """
    model, table, outcome, name = last_stage
    payload = snap.build_snapshot(model, table, outcome, name, max_points=200)
    y_obs = np.asarray(model.y_obs, dtype=np.float64)
    kept = np.asarray(payload["y_obs"], dtype=np.float64)
    assert kept.max() == pytest.approx(y_obs.max(), rel=1e-5)
    assert kept.min() == pytest.approx(y_obs.min(), rel=1e-5, abs=1e-9)


# ----------------------------------------------------------------------
# ticks
# ----------------------------------------------------------------------
def test_ticks_carry_every_emission_line(synthetic_pattern):
    """Not just the primary, or Layer 0 reads each Kα2 peak as an impurity."""
    structure, ins = perturbed_models()
    one_line = len(ins.source.lines)
    cap = _Capture()
    rx.Refinement(structure, ins, history=False).fit(
        synthetic_pattern, events=cap)
    model, table, outcome, name = cap.calls[-1]
    values = table.decode(outcome.theta)

    ticks = snap.stage_ticks(model, values)
    phase = ticks["phase 0"]
    primary = len(model.phases[0].reflections.two_theta(
        tuple(values[f"phases.0.cell.{k}"]
              for k in ("a", "b", "c", "alpha", "beta", "gamma")),
        model.line_wavelengths[0]))
    assert phase["n_total"] == primary * len(model.line_wavelengths)
    assert one_line == len(model.line_wavelengths)


def test_a_tick_cap_is_reported_not_silent(last_stage):
    """``n_total`` beside the list, the way ``MAX_CANDIDATE_TICKS`` does it.

    A cap with no count reads as coverage: a reader sees ten ticks and
    concludes the phase has ten reflections.
    """
    model, table, outcome, _name = last_stage
    values = table.decode(outcome.theta)
    uncapped = snap.stage_ticks(model, values)["phase 0"]
    capped = snap.stage_ticks(model, values, max_per_phase=5)["phase 0"]

    assert uncapped["n_total"] > 5, "fixture is too small to cap"
    assert len(capped["two_theta"]) <= 5
    assert capped["n_total"] == uncapped["n_total"]
    # thinned across the range, never truncated at some 2θ nobody chose
    assert capped["two_theta"][-1] == pytest.approx(
        uncapped["two_theta"][-1], abs=1e-5)


# ----------------------------------------------------------------------
# what the payload says about itself
# ----------------------------------------------------------------------
def test_weighted_reports_whether_sigma_was_measured(synthetic_pattern):
    """``weighted`` is the σ-measured fact, and it changes no number.

    The same pattern with and without its esd column: Δ/σ is what the fit
    minimised either way, so only the flag moves.
    """
    from rietx.schemas.pattern import PatternData

    with_sigma = PatternData(
        two_theta=list(synthetic_pattern.two_theta),
        intensity=list(synthetic_pattern.intensity),
        sigma=[float(s) for s in synthetic_pattern.sig()])
    assert synthetic_pattern.sigma is None

    seen = {}
    for label, data in (("fallback", synthetic_pattern), ("file", with_sigma)):
        structure, ins = perturbed_models()
        cap = _Capture()
        rx.Refinement(structure, ins, history=False).fit(data, events=cap)
        model, table, outcome, name = cap.calls[-1]
        seen[label] = snap.build_snapshot(model, table, outcome, name)

    assert seen["fallback"]["weighted"] is False
    assert seen["file"]["weighted"] is True
    assert np.allclose(np.asarray(seen["fallback"]["delta"], dtype=float),
                       np.asarray(seen["file"]["delta"], dtype=float),
                       rtol=1e-5, atol=1e-12)


def test_statistics_are_the_stages_own(last_stage):
    """Computed once here, so ``status.json`` cannot disagree with the plot."""
    from rietx.optimize.statistics import compute_statistics

    model, table, outcome, name = last_stage
    payload = snap.build_snapshot(model, table, outcome, name)
    values = table.decode(outcome.theta)
    stats = compute_statistics(
        model.y_obs, model.evaluate(values), model.sigma,
        n_free=len(table.free_paths), y_background=model.background(values))

    assert payload["statistics"]["rwp"] == pytest.approx(stats.rwp)
    assert payload["statistics"]["gof"] == pytest.approx(stats.gof)
    assert payload["statistics"]["n_free"] == stats.n_free_parameters
    assert payload["schema"] == snap.SCHEMA_VERSION


def test_a_non_finite_point_is_null_and_the_file_still_parses(tmp_path,
                                                              last_stage):
    """``json.dumps`` writes a bare ``NaN`` and ``JSON.parse`` refuses it.

    One such point would cost a viewer the whole curve, so they go out as
    ``null`` — which is also the right picture of a point with no value.
    """
    model, table, outcome, name = last_stage
    payload = snap.build_snapshot(model, table, outcome, name)
    payload["y_obs"] = snap._json_list(
        np.array([1.0, np.nan, np.inf, -np.inf, 2.0]))
    text = json.dumps(payload)
    assert "NaN" not in text and "Infinity" not in text
    assert json.loads(text)["y_obs"] == [1.0, None, None, None, 2.0]


def test_the_write_is_atomic_and_leaves_no_temporary(tmp_path, last_stage):
    model, table, outcome, name = last_stage
    returned = snap.write_snapshot(tmp_path, model, table, outcome, name)
    written = json.loads(
        (tmp_path / snap.SNAPSHOT_FILE).read_text(encoding="utf-8"))

    assert not list(tmp_path.glob("*.tmp"))
    assert written["stage"] == name
    # the payload comes back so a second file is written from it rather than
    # from a second computation
    assert returned["statistics"] == written["statistics"]


def test_building_a_snapshot_needs_no_plotly(tmp_path, last_stage, monkeypatch):
    """Recording a run must work on an install with no plotting library."""
    model, table, outcome, name = last_stage
    monkeypatch.setitem(sys.modules, "plotly", None)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", None)
    snap.write_snapshot(tmp_path, model, table, outcome, name)
    assert (tmp_path / snap.SNAPSHOT_FILE).is_file()

# ----------------------------------------------------------------------
# what the picture looks like
# ----------------------------------------------------------------------
def test_the_drawn_curves_are_worth_looking_at(last_stage):
    """Draw what the viewer draws, over what the fit computed.

    An assertion says the kept points equal the model's *at those indices*,
    which is true of any index set including a bad one. What it cannot say is
    whether the picture still looks like the fit — a decimation that clipped
    peak tops passes every test above and is obvious here in a second. Rwp
    hides locally-bad fits, and a decimated plot hides nothing but itself.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    model, table, outcome, name = last_stage
    payload = snap.build_snapshot(model, table, outcome, name)
    # a hard decimation too, so the comparison has something to show
    thin = snap.build_snapshot(model, table, outcome, name, max_points=300)

    values = table.decode(outcome.theta)
    tt = np.asarray(model.tt, dtype=np.float64)
    y_obs = np.asarray(model.y_obs, dtype=np.float64)
    y_calc = np.asarray(model.evaluate(values), dtype=np.float64)

    OUT.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True,
                             height_ratios=[3, 3, 2])
    for ax, drawn, label in ((axes[0], payload, f"drawn: {payload['n_drawn']}"),
                             (axes[1], thin, f"drawn: {thin['n_drawn']}")):
        ax.plot(tt, y_obs, lw=0.6, color="0.75",
                label=f"obs, all {len(tt)} points")
        ax.plot(drawn["two_theta"], drawn["y_obs"], lw=0.8, color="#1f77b4",
                label=label)
        ax.plot(tt, y_calc, lw=0.8, color="#ff7f0e", label="calc")
        ax.legend(fontsize=8, frameon=False)
        ax.set_ylabel("intensity")
    axes[2].plot(payload["two_theta"], payload["delta"], lw=0.6,
                 color="0.45")
    axes[2].axhline(0, lw=0.5, color="0.7")
    axes[2].set_ylabel("Δ/σ")
    axes[2].set_xlabel("2θ (°)")
    axes[0].set_title(f"WP-1402 snapshot — stage {name!r}, "
                      f"Rwp {payload['statistics']['rwp']:.4f}")
    fig.tight_layout()
    fig.savefig(OUT / "wp1402_snapshot_curves.png", dpi=110)
    plt.close(fig)

    assert (OUT / "wp1402_snapshot_curves.png").is_file()
    # the peak top survives even the hard decimation, which is the property
    # the picture is there to make visible
    assert max(thin["y_obs"]) == pytest.approx(y_obs.max(), rel=1e-5)
