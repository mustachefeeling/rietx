"""Closed-loop FitReport usefulness eval (WP-1052): does *following* the report
converge anything?

The misfit-injection suite (``test_fitreport_layers.py``) measures whether the
report tells the truth about a planted cause.  This module measures the next
question: starting from a planted-cause state, repeatedly follow the report's
top surviving suggestion through the history DAG (``predict_then_verify``:
branch → verify stage → keep on >1 % χ² improvement → checkout winner /
structural rollback) and check that the planted *parameter* is recovered — Rwp
alone is never the criterion — that the loop stops when nothing actionable
remains, and that every rejection leaves the DAG clean.  It is the first
executable version of AGENT_PROTOCOL §9's canonical agent loop.

``_run_report_loop`` is a measurement instrument, not product: WP-1050's fence
holds verbatim — *"No automatic stage insertion: the staged runner stays
preset; suggest() informs a caller (human, GUI, or the agent loop), it does
not drive."*  Nothing importable from ``pxrdref`` may become an autopilot.

Honest framing for every baseline comparison here: on a synthetic single-cause
start every other parameter is already at truth, so "the loop freed fewer
parameters than ``mccusker_default``" means **the report localised the
cause**, never "report-driven refinement is cheaper".

Placement: fast suite, deliberately **no** ``xdist_group`` — the shared
``_truth()`` is cheap synthesis, not a fitted fixture, so grouping the
episodes would create a serial group rivalling the whole fast-suite wall.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pytest

import pxrdref as pr
from pxrdref.report import predict_then_verify
from pxrdref.report.apply import recipe
from pxrdref.report.schemas import FitReport, VerificationOutcome
from pxrdref.strategy.staged import RefinementPlan, Stage
from tests.test_fitreport_layers import _result_for, _truth

_OUT = Path(__file__).parent / "output"

#: hard stop on loop rounds — a runaway guard (tests/CLAUDE.md), never a timer
ROUND_CAP = 4
#: strict > over the collinearity cap (``confidence = min(confidence, 0.3)`` on
#: non-separable trends, layer2.py) — the loop never acts on an attribution the
#: report itself flagged non-separable
CONFIDENCE_FLOOR = 0.3
#: two consecutive rejections mean the report has nothing left worth trying
REJECTION_STOP = 2

#: mutually-substitutable cause families, as in the layers suite's
#: calibration-ensemble test — "the top suggestion is in the planted family"
#: is the success criterion, never "is exactly the planted kind"
POSITION_FAMILY = {"refine_zero_shift", "refine_sample_displacement",
                   "refine_sample_transparency", "refine_cell"}
WIDTH_FAMILY = {"refine_profile_widths", "refine_sample_size_broadening",
                "refine_sample_strain_broadening"}
SCALE_FAMILY = {"refine_scale", "refine_biso"}


# ----------------------------------------------------------------------
# the driver — a measurement instrument, private to this module
# ----------------------------------------------------------------------
@dataclass
class RoundRecord:
    """One report → select → verify round."""

    report: FitReport
    #: kind selected this round, None when nothing survived selection
    selected: str | None
    #: (kind, why) for every action ranked above the selection that was
    #: passed over; at a stopping round this covers the whole report
    blocked: list[tuple[str, str]]
    outcome: VerificationOutcome | None
    #: id of the accepted verify node (None on rejection/stop)
    verify_node: str | None
    #: working-state χ² after the round
    chi2: float


@dataclass
class EpisodeResult:
    ref: pr.Refinement
    rounds: list[RoundRecord] = field(default_factory=list)
    stop_reason: str = ""
    bootstrap_chi2: float = 0.0

    @property
    def accepted(self) -> list[str]:
        return [r.selected for r in self.rounds
                if r.outcome is not None and r.outcome.accepted]

    @property
    def rejected(self) -> list[str]:
        return [r.selected for r in self.rounds
                if r.outcome is not None and not r.outcome.accepted]

    @property
    def first_accepted(self) -> VerificationOutcome | None:
        for r in self.rounds:
            if r.outcome is not None and r.outcome.accepted:
                return r.outcome
        return None

    @property
    def final_chi2(self) -> float:
        return self.rounds[-1].chi2 if self.rounds else self.bootstrap_chi2

    @property
    def final_report(self) -> FitReport:
        return self.rounds[-1].report

    def blocked_kinds(self) -> list[str]:
        """Kinds passed over at the stopping round, report order."""
        return [k for k, _ in self.rounds[-1].blocked]


def _select(report: FitReport, rejected: set[str]):
    """First surviving action in report order (= confidence desc), with the
    reasons everything ranked above it was passed over.

    The four rules, in order: (i) active — ``Refinement.report()`` passes the
    working free set, so every previously-accepted action is auto-vetoed
    "already free", the built-in anti-thrash; (ii) a stage recipe — the index
    and advice kinds inform, they are not one ``run_stage``; (iii) strictly
    above the collinearity cap; (iv) not already rejected this episode
    (loop-local memory; correct for single-cause episodes only).
    """
    blocked: list[tuple[str, str]] = []
    for action in report.suggested_actions:
        if not action.active:
            blocked.append((action.kind, f"vetoed: {action.vetoed_by}"))
        elif recipe(action.kind).how != "stage":
            blocked.append((action.kind, f"how={recipe(action.kind).how}"))
        elif not action.confidence > CONFIDENCE_FLOOR:
            blocked.append((action.kind,
                            f"confidence {action.confidence} <= {CONFIDENCE_FLOOR}"))
        elif action.kind in rejected:
            blocked.append((action.kind, "rejected earlier this episode"))
        else:
            return action, blocked
    return None, blocked


def _run_report_loop(structure, instrument, data, *,
                     round_cap: int = ROUND_CAP) -> EpisodeResult:
    """Bootstrap fit, then follow the report until it stops itself.

    Bootstrap is a background-only stage: ``predict_then_verify`` needs a
    prior fit, and a zero-free-parameter solve won't run.  Each accepted
    action is followed by ``checkout`` of the verify node and one
    empty-``turn_on`` refit stage — ``checkout`` nulls ``_model``/``result_``
    and the refit re-establishes them without freeing anything
    (``set_vary([], True)`` frees nothing; ``_prepare_table(restore=True)``
    restores the node's free set).
    """
    ref = pr.Refinement(structure, instrument)
    ref.fit(data, plan=RefinementPlan(stages=[
        Stage("bootstrap", ["instrument.background.*"])]))
    episode = EpisodeResult(ref=ref, bootstrap_chi2=ref.result_.statistics.chi2)

    rejected: set[str] = set()
    consecutive_rejections = 0
    for _ in range(round_cap):
        report = ref.report()
        action, blocked = _select(report, rejected)
        if action is None:
            episode.rounds.append(RoundRecord(
                report=report, selected=None, blocked=blocked, outcome=None,
                verify_node=None, chi2=ref.result_.statistics.chi2))
            episode.stop_reason = "no_action"
            return episode

        parent_id = ref._head_id
        parent_chi2 = ref.result_.statistics.chi2
        outcome = predict_then_verify(ref, data, action)
        verify_node = None
        if outcome.accepted:
            # after an accepted trial the shared tree's HEAD *is* the verify
            # node (RefinementTree.add advances it; the parent's private head
            # stays put); VerificationOutcome carries no node id, so navigate
            # by HEAD and sanity-check the node is the one the action ran
            verify_node = ref.history.head
            node = ref.history[verify_node]
            assert node.action.kind == "stage", node.action
            assert node.action.name == f"verify:{action.kind}", node.action
            assert node.parents == [parent_id], (node.parents, parent_id)
            ref.checkout(verify_node)
            ref.run_stage(data, Stage(f"refit:{action.kind}", []))
            consecutive_rejections = 0
        else:
            # structural rollback: the parent working state is untouched, bit
            # for bit, and the trial is at most a dead leaf in the DAG
            assert ref._head_id == parent_id
            assert ref.result_.statistics.chi2 == parent_chi2
            rejected.add(action.kind)
            consecutive_rejections += 1
        episode.rounds.append(RoundRecord(
            report=report, selected=action.kind, blocked=blocked,
            outcome=outcome, verify_node=verify_node,
            chi2=ref.result_.statistics.chi2))
        if consecutive_rejections >= REJECTION_STOP:
            episode.stop_reason = "two_rejections"
            return episode
    episode.stop_reason = "round_cap"
    return episode


# ----------------------------------------------------------------------
# shared assertions and helpers
# ----------------------------------------------------------------------
def _truth_chi2(structure, instrument, data) -> float:
    """χ² of a model state evaluated (not refined) against ``data`` — the
    noise floor when called with the truth models."""
    result, _, _ = _result_for(structure, instrument, data)
    return result.statistics.chi2


def _dead_verify_leaves(tree) -> list:
    """Rejected trials: verify nodes nothing ever built on."""
    return [n for n in tree.leaves()
            if n.action.kind == "stage"
            and (n.action.name or "").startswith("verify:")]


def _assert_dag_hygiene(episode: EpisodeResult) -> None:
    """The DAG as audit trail, not scenery.

    Every rejection that got as far as a solve leaves exactly one dead leaf
    whose ``history.compare`` row shows it improved < 1 % over its parent —
    the acceptance criterion, read back out of the record.  (A trial that
    *failed* to solve is a rejection with no node, so the leaf count is the
    count of "rolled back" rejections, not of all rejections.)
    """
    tree = episode.ref.history
    leaves = _dead_verify_leaves(tree)
    rolled_back = [r for r in episode.rounds
                   if r.outcome is not None and not r.outcome.accepted
                   and "rolled back" in r.outcome.reason]
    assert len(leaves) == len(rolled_back), (
        f"{len(rolled_back)} rolled-back rejections but {len(leaves)} dead "
        f"verify leaves: {[n.id for n in leaves]}")
    for leaf in leaves:
        assert len(leaf.parents) == 1, leaf.parents
        parent_row, leaf_row = tree.compare([leaf.parents[0], leaf.id])
        improvement = parent_row["chi2"] - leaf_row["chi2"]
        assert improvement <= 0.01 * abs(parent_row["chi2"]), (
            f"dead leaf {leaf.id} improved {improvement:.4g} over its parent "
            f"({parent_row['chi2']:.4g}) — that should have been accepted")


def _plot(episode: EpisodeResult, stem: str) -> None:
    """obs/calc/diff PNGs to tests/output/ (gitignored), full range + a
    low-angle zoom — Rwp hides locally-bad fits (house convention)."""
    from pxrdref.viz.plots import plot_result

    _OUT.mkdir(exist_ok=True)
    result = episode.ref.result_
    plot_result(result, path=str(_OUT / f"{stem}.png"))
    plot_result(result, path=str(_OUT / f"{stem}_zoom.png"),
                two_theta_range=(18.0, 45.0))


def _actions_in_order(report: FitReport) -> list[str]:
    return [a.kind for a in report.suggested_actions]


# ----------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def truth():
    return _truth()


# ----------------------------------------------------------------------
# E1 — zero shift: the loop's canonical accepted round
# ----------------------------------------------------------------------
def test_e1_zero_shift_loop(truth):
    """A 0.008° zero error: one accepted ``refine_zero_shift`` round, the
    planted parameter recovered, nothing wrong kept, and the final state at
    least as good as every other leaf in the DAG."""
    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.zero_shift.value = 0.008

    episode = _run_report_loop(structure, start, data)

    # pre-loop calibration transfer: the bootstrap's background stage can
    # absorb part of the planted misfit, so the loop's starting report is not
    # the layers suite's unrefined state — establish, don't assume, that the
    # planted family is still top-ranked after the bootstrap
    report0 = episode.rounds[0].report
    assert report0.layer1_available, report0.abstained_reason
    assert _actions_in_order(report0)[0] in POSITION_FAMILY, (
        _actions_in_order(report0))

    assert episode.accepted == ["refine_zero_shift"], (
        episode.accepted, episode.rejected, episode.stop_reason)

    # recovery is the planted *parameter* at truth, never Rwp alone
    zero = episode.ref.fitted_instrument.zero_shift.value
    assert zero == pytest.approx(0.0, abs=0.002), zero

    # nothing else on the instrument moved off its start
    disp = episode.ref.fitted_instrument.geometry.sample_displacement.value
    assert disp == 0.0, disp

    # the accepted branch is the best leaf (within the keep threshold)
    stats_leaves = [n.metrics.statistics.chi2
                    for n in episode.ref.history.leaves()
                    if n.metrics.statistics is not None]
    assert episode.final_chi2 <= 1.01 * min(stats_leaves), (
        episode.final_chi2, min(stats_leaves))

    _assert_dag_hygiene(episode)
    _plot(episode, "report_loop_e1")


def test_e1_zero_shift_baseline(truth):
    """``mccusker_default`` recovers the same start too (its ``zero`` stage
    frees exactly the planted parameter) — the contrast with the loop is
    localisation, not capability: the preset also frees scale, cell and the
    whole profile block on a state where those were already at truth."""
    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.zero_shift.value = 0.008

    ref = pr.Refinement(structure, start)
    ref.fit(data, plan="mccusker_default")
    assert ref.fitted_instrument.zero_shift.value == pytest.approx(0.0, abs=0.002)
