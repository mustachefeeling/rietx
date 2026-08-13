"""Build the ten eval episode fixtures and their scorer-side truth tree.

Episodes E1-E8 are WP-1052's planted-cause starts, built live from
``tests.test_fitreport_layers._truth()`` so they stay in lockstep with the
layers suite; R1/R2 (WP-1059) are the real-data pair, built live from the NIST
SRM 660c protocol's own converged state.  Nothing generated here is committed.
Each episode dir holds the fixed request core (``episode.json``:
task/structure/instrument/pattern, pydantic round-trip by design), the shared
prompt (``prompt.md``) and the condition marker (``condition.json``) the shim
enforces.  Ground truth — planted path, truth value, tolerance, expected
verdict, legitimate parameter family — goes to a **separate** tree the agent
is never pointed at.

Usage::

    python -m tests.eval_report_agent.build_fixtures \
        --episodes DIR --truth DIR --condition surface
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import anatase as pr
from tests.test_fitreport_layers import _truth

REPO_ROOT = Path(__file__).resolve().parents[2]

#: versions the whole runner protocol (prompt text, overlay contract, answer
#: schema, scoring rules) — bump on any change that alters comparability.
#: 1.1 (WP-1058/1059): the response carries the per-stage report ``trajectory``
#: and the §5 excerpt teaches it, the condition axis splits delivery from
#: instruction, and the real-data pair joins the episode set — so a 1.1 run is
#: not comparable with a 1.0 one, which is the point
PROTOCOL_VERSION = "1.1"

#: shim-enforced hard stop on refinement calls per episode — a runaway guard
#: (tests/CLAUDE.md), never a timer; the prompt advertises 6
MAX_CALLS = 8

#: E1-E8 are synthetic (WP-1052 planted causes); R1/R2 are the real SRM 660c
#: pair (WP-1059) and cost one 1.5 s baseline fit to build
SYNTHETIC_IDS = ("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8")
REAL_IDS = ("R1", "R2")
EPISODE_IDS = SYNTHETIC_IDS + REAL_IDS


@dataclass(frozen=True)
class Condition:
    """One cell of the round-2 condition axis.

    Two independent switches, both enforced by the shim rather than by the
    prompt: ``report`` is the converged-state FitReport (round 1's whole
    treatment) and ``trajectory`` is WP-1058's per-stage delivery of it.
    ``sections`` names the AGENT_PROTOCOL excerpts the prompt quotes — §9's
    "read the run" subsection is the *instruction* variable, held separate
    from the surface so the two can be told apart.
    """

    report: bool
    trajectory: bool
    sections: tuple[str, ...]


#: the round-2 matrix: a 2×2 on (trajectory × §9) plus the report-less
#: baseline.  ``off`` renders byte-for-byte the prompt round 1 called
#: "report-off" — the one cell readable against the 1.0 grid, since an arm
#: that never sees a report cannot see the content that changed under it.
CONDITIONS: dict[str, Condition] = {
    "off": Condition(report=False, trajectory=False, sections=()),
    "report": Condition(report=True, trajectory=False, sections=("5.", "6.")),
    "prompt": Condition(report=True, trajectory=False,
                        sections=("5.", "6.", "9.")),
    "surface": Condition(report=True, trajectory=True, sections=("5.", "6.")),
    "both": Condition(report=True, trajectory=True,
                      sections=("5.", "6.", "9.")),
}

#: §9 is long and half of it (the DAG, ``predict_then_verify``) describes a
#: python surface the shim does not sanction; the instruction under test is
#: its first subsection, so that is what the prompt quotes
SECTION_9_SUBSECTION = "Read the run, not just its last state"

#: mutually-substitutable cause families (test_report_loop.py's action
#: families, projected onto parameter dot-paths).  Used by the scorer to
#: count wrong-frees on recovery episodes; ``instrument.background.*`` is
#: always legitimate and lives in scorer.ALWAYS_LEGIT.
POSITION_FAMILY = [
    "instrument.zero_shift",
    "instrument.geometry.sample_displacement",
    "instrument.geometry.sample_transparency",
    "phases.*.cell.*",
]
WIDTH_FAMILY = [
    "instrument.profile.*",
    "phases.*.lor_size",
    "phases.*.lor_strain",
    "phases.*.gauss_size",
    "phases.*.gauss_strain",
]
SCALE_FAMILY = [
    "phases.*.scale",
    "phases.*.atoms.*.biso",
]


def _request_core(structure, instrument, pattern) -> dict:
    """The fixed request core — everything the agent must not touch."""
    return {
        "task": "refine",
        "structure": structure.model_dump(mode="json"),
        "instrument": instrument.model_dump(mode="json"),
        "pattern": pattern.model_dump(mode="json"),
        "mode": "rietveld",
    }


def build_episodes() -> dict[str, dict]:
    """All eight episodes: request core + truth record, keyed by id.

    Perturbations mirror ``tests/test_report_loop.py`` byte for byte; truth
    values are read from the unperturbed models, never hard-coded.
    """
    structure, ins, data = _truth()
    zero_truth = ins.zero_shift.value
    disp_truth = ins.geometry.sample_displacement.value
    w_truth = ins.profile.w.value
    scale_truth = structure.phases[0].scale.value
    a_truth = structure.phases[0].cell.a.value

    episodes: dict[str, dict] = {}

    e1_ins = ins.model_copy(deep=True)
    e1_ins.zero_shift.value = 0.008
    episodes["E1"] = {
        "core": _request_core(structure, e1_ins, data),
        "truth": {
            "episode": "E1",
            "expected_verdict": "converged",
            "planted": {"path": "instrument.zero_shift", "start": 0.008,
                        "truth": zero_truth, "tol": {"abs": 0.002}},
            "family": POSITION_FAMILY,
            "notes": "0.008 deg zero error; competence control — the "
                     "default plan's zero stage frees the planted parameter.",
        },
    }

    e2_ins = ins.model_copy(deep=True)
    e2_ins.geometry.sample_displacement.value = -0.02
    episodes["E2"] = {
        "core": _request_core(structure, e2_ins, data),
        "truth": {
            "episode": "E2",
            "expected_verdict": "converged",
            "planted": {"path": "instrument.geometry.sample_displacement",
                        "start": -0.02, "truth": disp_truth,
                        "tol": {"abs": 0.005}},
            "family": POSITION_FAMILY,
            "watch": {"cause": ["instrument.geometry.sample_displacement"],
                      "absorber": ["instrument.zero_shift"]},
            "notes": "-0.02 mm displacement (cosO signature, separable over "
                     "18-125 deg); no mccusker_default stage frees it, so the "
                     "lazy path absorbs it into a compensating zero_shift.",
        },
    }

    e3_ins = ins.model_copy(deep=True)
    e3_ins.profile.w.value = 2.0e-3
    episodes["E3"] = {
        "core": _request_core(structure, e3_ins, data),
        "truth": {
            "episode": "E3",
            "expected_verdict": "converged",
            "planted": {"path": "instrument.profile.w", "start": 2.0e-3,
                        "truth": w_truth, "tol": {"rel": 0.20}},
            "family": WIDTH_FAMILY,
            # the sign-inversion watch: which of the two width paths the
            # agent took, scored as a flag and never as pass/fail
            "watch": {"report_widths": ["phases.*.lor_size",
                                        "phases.*.lor_strain"],
                      "default_width": ["instrument.profile.w"]},
            "notes": "profile.w halved; the report's width emitters name only "
                     "lor_size/lor_strain (proxy plateau chi2_red ~4.3) while "
                     "the default plan frees w itself and reaches the ~1.01 "
                     "floor — following the report can lose to ignoring it.",
        },
    }

    e4_structure = structure.model_copy(deep=True)
    e4_structure.phases[0].scale.value = scale_truth * 0.90
    episodes["E4"] = {
        "core": _request_core(e4_structure, ins, data),
        "truth": {
            "episode": "E4",
            "expected_verdict": "converged",
            "planted": {"path": "phases.0.scale",
                        "start": scale_truth * 0.90, "truth": scale_truth,
                        "tol": {"rel": 0.02}},
            "family": SCALE_FAMILY,
            "notes": "10 % scale deficit; competence control.",
        },
    }

    tt = np.asarray(data.two_theta)
    y = np.asarray(data.intensity, dtype=float)
    y = y + 900.0 * np.exp(-0.5 * ((tt - 29.35) / 0.06) ** 2)
    doped = pr.PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                           sigma=data.sigma)
    episodes["E5"] = {
        "core": _request_core(structure, ins, doped),
        "truth": {
            "episode": "E5",
            "expected_verdict": "impurity_suspected",
            "planted": None,
            "family": None,
            "notes": "Gaussian spike at 29.35 deg (sigma 0.06, amplitude 900) "
                     "no reflection accounts for; the model is otherwise at "
                     "truth.  Must not be silently fitted through.",
        },
    }

    e6_structure = structure.model_copy(deep=True)
    e6_structure.phases[0].cell = pr.Cell.cubic(4.1568 * 1.004)
    episodes["E6"] = {
        "core": _request_core(e6_structure, ins, data),
        "truth": {
            "episode": "E6",
            "expected_verdict": "converged",
            "planted": {"path": "phases.0.cell.a",
                        "start": 4.1568 * 1.004, "truth": a_truth,
                        "tol": {"rel": 5e-4}},
            "family": POSITION_FAMILY,
            "notes": "0.4 % cell error.  The abstained report serves "
                     "add_impurity_phase at 0.9 (WP-1052 finding 1) — an "
                     "agent following it is invited to a phantom phase; a "
                     "competent one frees the cell and converges (the start "
                     "is inside the cell stage's basin).",
        },
    }

    e7_structure = structure.model_copy(deep=True)
    e7_structure.phases[0].cell = pr.Cell.cubic(4.60)
    e7_structure.phases[0].scale.value = scale_truth / 10.0
    episodes["E7"] = {
        "core": _request_core(e7_structure, ins, data),
        "truth": {
            "episode": "E7",
            "expected_verdict": "abstain",
            "planted": None,
            "family": None,
            "notes": "cell at 4.60 A (nowhere near) and scale / 10 — a "
                     "hopeless start; no refinement reachable from here is "
                     "trustworthy.",
        },
    }

    s8, ins8, data8 = _truth(lo=20.0, hi=56.0, seed=23)
    e8_ins = ins8.model_copy(deep=True)
    e8_ins.zero_shift.value = 0.02
    episodes["E8"] = {
        "core": _request_core(s8, e8_ins, data8),
        "truth": {
            "episode": "E8",
            "expected_verdict": "ambiguous",
            "planted": {"path": "instrument.zero_shift", "start": 0.02,
                        "truth": ins8.zero_shift.value, "tol": None},
            "family": None,
            "watch": {"cause": ["instrument.zero_shift"],
                      "absorber": [
                          "instrument.geometry.sample_displacement"]},
            "notes": "0.02 deg zero over 20-56 deg only: zero and "
                     "displacement are collinear on this window (|r|~0.9995) "
                     "— freeing both lands on the degenerate ridge, and the "
                     "axial-divergence term absorbs ~70 % of chi2 while "
                     "surviving verification (WP-1052 finding 2).  Recovery "
                     "is by the planted parameter, never delta-chi2; the "
                     "verdict this window supports is ambiguity.",
        },
    }

    return episodes


def build_real_episodes() -> dict[str, dict]:
    """R1/R2 — the real-data pair, off the NIST SRM 660c converged state.

    One baseline fit (~1.5 s, 5332 channels, CuKα doublet, the file's own esd
    column) supplies both starts and both truth values, which are read from it
    rather than hard-coded.  The pair is WP-1052's shape — refusal where the
    data cannot separate, recovery where it can — moved from the report loop
    onto the plan-driven surface an agent actually drives:

    - **R1** knocks the protocol's fitted displacement to −0.02 mm.  No
      ``mccusker_default`` stage frees displacement, so the lazy path absorbs
      it into ``zero_shift`` and converges (measured 2026-08-13: Rwp 0.09127
      against the baseline's 0.08661, zero at +0.0317, empty action list) —
      but the WP-1056 clause fires at that converged state: *exchangeable with
      the held instrument.geometry.sample_displacement (R² = 0.9977) … a
      confident verdict is not supported*.  Freeing displacement instead
      recovers −0.080098 and Rwp 0.08661 with the same clause the other way
      round (88σ); freeing both lands on the ridge at a *better* Rwp 0.08569
      and reports the unconstrained combination.  On this pattern the pair is
      genuinely inseparable, so the verdict the data supports is ambiguity and
      recovery is **not** the grade.
    - **R2** takes scale ×0.90 — separable, and the default plan recovers it
      to 6 ppm.  The control that keeps R1's refusal from being read as
      "real data is just hard".

    WP-1052's own zero-knock episode is deliberately *not* R1: measured, the
    default plan's zero stage fixes it (Rwp back to 0.08661), so at the agent
    surface it is a competence control, not a refusal.  The loop refuses
    there; a plan-driven agent does not have to.
    """
    from tests.test_acceptance_srm660c import (
        DATA,
        _nist_calibrated_plan,
        build_srm_inputs,
    )

    if not (DATA / "nist_srm660c_100a.cif").exists():
        raise FileNotFoundError(
            "SRM 660c dataset not present; R1/R2 cannot be built "
            "(tests/data/README.md)")

    data, structure, instrument = build_srm_inputs()
    ref = pr.Refinement(structure, instrument)
    ref.fit(data, plan=_nist_calibrated_plan())
    base_s = ref.fitted_structure.model_copy(deep=True)
    base_i = ref.fitted_instrument.model_copy(deep=True)
    disp_truth = base_i.geometry.sample_displacement.value
    scale_truth = base_s.phases[0].scale.value

    r1_ins = base_i.model_copy(deep=True)
    r1_ins.geometry.sample_displacement.value = -0.02
    r2_structure = base_s.model_copy(deep=True)
    r2_structure.phases[0].scale.value = scale_truth * 0.90

    return {
        "R1": {
            "core": _request_core(base_s, r1_ins, data),
            "truth": {
                "episode": "R1",
                "expected_verdict": "ambiguous",
                "planted": {"path": "instrument.geometry.sample_displacement",
                            "start": -0.02, "truth": disp_truth, "tol": None},
                "family": POSITION_FAMILY,
                "watch": {"cause": [
                              "instrument.geometry.sample_displacement"],
                          "absorber": ["instrument.zero_shift"]},
                "notes": "real SRM 660c, displacement knocked to -0.02 mm "
                         "from the protocol's fitted value; zero and "
                         "displacement are inseparable on this pattern "
                         "(R^2 0.9977 measured at the converged state), so "
                         "ambiguity is the supported verdict and the planted "
                         "value is recorded, never graded.",
            },
        },
        "R2": {
            "core": _request_core(r2_structure, base_i, data),
            "truth": {
                "episode": "R2",
                "expected_verdict": "converged",
                "planted": {"path": "phases.0.scale",
                            "start": scale_truth * 0.90, "truth": scale_truth,
                            "tol": {"rel": 0.02}},
                "family": SCALE_FAMILY,
                "notes": "real SRM 660c, scale x0.90 — the separable half of "
                         "the pair; the default plan recovers it.",
            },
        },
    }


# ----------------------------------------------------------------------
# prompt
# ----------------------------------------------------------------------
def _protocol_excerpt(heading: str, *, level: str = "##") -> str:
    """One section of docs/AGENT_PROTOCOL.md, verbatim, ending at the next
    heading of the same rank or higher (or the ``---`` separator) — the manual
    ships with the feature, so the excerpt is extracted live rather than
    copied, and a rewritten section reaches the prompt by itself."""
    text = (REPO_ROOT / "docs" / "AGENT_PROTOCOL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.startswith(f"{level} {heading}"))
    stops = ("---", "## ") if level == "##" else ("---", "## ", "### ")
    end = next(i for i in range(start + 1, len(lines))
               if lines[i].startswith(stops))
    return "\n".join(lines[start:end]).rstrip()


def _sections_text(sections) -> str:
    """The quoted excerpts for one condition, in the order it declares."""
    parts = []
    for name in sections:
        if name == "9.":
            parts.append(_protocol_excerpt(SECTION_9_SUBSECTION, level="###"))
        else:
            parts.append(_protocol_excerpt(name))
    return "\n\n".join(parts)


_PROMPT = """\
# Episode {eid} — powder XRD refinement

You are operating the `anatase` Rietveld refinement package through its one
JSON tool call, `agent.refine_json`.  This directory is your workspace:

- `episode.json` — the fixed request core (structure, instrument, pattern).
  Read-only: the shim merges your overlay onto it; you never edit it.  It is
  mostly bulk pattern arrays — do not read it whole; if you need a metadata
  field (phase, wavelength), query it selectively (e.g. `jq`/`head`).
- `overlay.json` — yours to write.  Allowed keys, each optional:
  - `"plan"`: a preset name, or an explicit stage list
    `{{"stages": [{{"name": "...", "turn_on": ["<path glob>", ...]}}, ...]}}`
    (stages accumulate: each stage frees its `turn_on` globs on top of the
    previous stages' — dot-paths like `instrument.zero_shift`,
    `phases.*.cell.*`).  Omitted = the `mccusker_default` preset.
  - `"mode"`: `"rietveld"` (default) | `"lebail"` | `"pawley"`.
  - `"two_theta_limits"`: `[lo, hi]` — fit only this range (legitimate for
    excluding a contaminated region; the exclusion is recorded).
  Any other key is refused by the shim.
- To run one refinement — every call starts from the same fixed starting
  values; calls do not chain — run, from the repository root:

      {python} -m tests.eval_report_agent.run_refine {episode_dir}

  The response prints to stdout (bulk curve arrays elided; every parameter,
  statistic and diagnostic{report_clause} is intact) and is appended to
  `calls.jsonl`.  A call usually returns in seconds, but a refinement that
  diverges can take 2-3 minutes before it fails — allow a 5-minute timeout.
  A failed call returns `{{"ok": false, "error": ...}}`; that is information,
  not a harness bug.
- Budget: plan on at most 6 calls; the shim hard-stops at {max_calls}.  Make
  at least one call — an answer with no refinement behind it scores zero.

When you are done, write `answer.json` in this directory:

    {{"verdict": "<converged | impurity_suspected | abstain | ambiguous>",
      "summary": "<a few sentences: what you concluded and why>"}}

Verdict meanings — pick exactly one:

- `converged` — the refinement reached a satisfactory fit; your **last** call
  is graded as your answer state.
- `impurity_suspected` — the pattern contains intensity the given phase cannot
  account for (an impurity / extra phase); say so rather than fitting
  through it.
- `abstain` — the starting model is too far from the data for any refinement
  reachable from here to be trustworthy; no answer.
- `ambiguous` — more than one physical cause explains the misfit and this
  data range cannot separate them; naming one confident cause would be wrong.

Work from the numbers in the response.  A good fit is necessary but not
sufficient: parameters compensating for each other can look converged, so
prefer the verdict the evidence supports over the one that ends the episode.
{report_section}"""

_REPORT_SECTION = """
## Reading the FitReport

Each response carries `report` — the three-layer FitReport.  The governing
sections of the package manual are quoted verbatim below.
{notice}
{sections}
"""

#: the trajectory-stripped arms need this or they hunt for a key the §5
#: excerpt promises: a factual statement about the *response shape*, never an
#: instruction — reaching an earlier state some other way is exactly the
#: operator skill the §9 arm is testing, so it is not hinted here
_NO_TRAJECTORY_NOTICE = """
This run's responses carry the converged report only: the per-stage
`trajectory` §5 points to is stripped by the harness and will not appear.
"""


def render_prompt(eid: str, episode_dir: Path, *, condition: str,
                  python: str = ".venv/bin/python") -> str:
    """The one shared prompt (PROTOCOL.md pins it; no per-model tuning).

    Report arms get the AGENT_PROTOCOL excerpts their condition declares — the
    manual ships with the feature, so §5/§6 track the report and §9's "read
    the run" subsection is the separable instruction; ``off`` gets neither the
    report nor the manual, which renders round 1's report-off prompt verbatim.
    """
    spec = CONDITIONS[condition]
    if spec.report:
        report_clause = ", and the full FitReport,"
        report_section = _REPORT_SECTION.format(
            notice="" if spec.trajectory else _NO_TRAJECTORY_NOTICE,
            sections=_sections_text(spec.sections))
    else:
        report_clause = ""
        report_section = ""
    return _PROMPT.format(eid=eid, episode_dir=episode_dir, python=python,
                          max_calls=MAX_CALLS, report_clause=report_clause,
                          report_section=report_section)


# ----------------------------------------------------------------------
# writer
# ----------------------------------------------------------------------
def write_fixtures(episodes_dir: Path, truth_dir: Path, *, condition: str,
                   python: str = ".venv/bin/python",
                   only: list[str] | None = None) -> list[Path]:
    """Write episode dirs + truth tree; returns the episode dirs written.

    The real-data pair costs a baseline fit, so it is built only when asked
    for — a synthetic-only selection stays as cheap as it was at 1.0.
    """
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of "
                         f"{'|'.join(CONDITIONS)}, got {condition!r}")
    spec = CONDITIONS[condition]
    wanted = tuple(only or EPISODE_IDS)
    episodes = build_episodes()
    if any(eid in REAL_IDS for eid in wanted):
        episodes.update(build_real_episodes())
    episodes_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for eid in wanted:
        ep = episodes[eid]
        edir = episodes_dir / eid
        edir.mkdir(exist_ok=True)
        (edir / "episode.json").write_text(
            json.dumps(ep["core"], indent=1) + "\n", encoding="utf-8")
        (edir / "condition.json").write_text(json.dumps({
            "protocol_version": PROTOCOL_VERSION,
            "condition": condition,
            "include_report": spec.report,
            "include_trajectory": spec.trajectory,
            "prompt_sections": list(spec.sections),
            "max_calls": MAX_CALLS,
        }, indent=1) + "\n", encoding="utf-8")
        (edir / "prompt.md").write_text(
            render_prompt(eid, edir, condition=condition, python=python),
            encoding="utf-8")
        (truth_dir / f"{eid}.json").write_text(
            json.dumps(ep["truth"], indent=1) + "\n", encoding="utf-8")
        written.append(edir)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=Path, required=True,
                        help="directory to write episode dirs into")
    parser.add_argument("--truth", type=Path, required=True,
                        help="scorer-side truth tree (keep it outside the "
                             "agent's workspace)")
    parser.add_argument("--condition", required=True,
                        choices=sorted(CONDITIONS))
    parser.add_argument("--python", default=".venv/bin/python",
                        help="interpreter the prompt tells the agent to use")
    parser.add_argument("--only", nargs="*", choices=EPISODE_IDS,
                        help="subset of episodes (default: all eight)")
    args = parser.parse_args(argv)
    written = write_fixtures(args.episodes, args.truth,
                             condition=args.condition, python=args.python,
                             only=args.only)
    for edir in written:
        print(edir)


if __name__ == "__main__":
    main()
