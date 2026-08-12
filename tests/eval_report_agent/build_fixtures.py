"""Build the eight WP-1053 episode fixtures and their scorer-side truth tree.

Episodes are WP-1052's planted-cause starts, built live from
``tests.test_fitreport_layers._truth()`` so they stay in lockstep with the
layers suite — nothing generated here is committed.  Each episode dir holds
the fixed request core (``episode.json``: task/structure/instrument/pattern,
pydantic round-trip by design), the shared prompt (``prompt.md``) and the
condition marker (``condition.json``) the shim enforces.  Ground truth —
planted path, truth value, tolerance, expected verdict, legitimate parameter
family — goes to a **separate** tree the agent is never pointed at.

Usage::

    python -m tests.eval_report_agent.build_fixtures \
        --episodes DIR --truth DIR --condition report-on|report-off
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import anatase as pr
from tests.test_fitreport_layers import _truth

REPO_ROOT = Path(__file__).resolve().parents[2]

#: versions the whole runner protocol (prompt text, overlay contract, answer
#: schema, scoring rules) — bump on any change that alters comparability.
#: 1.1 (WP-1058): the response carries the per-stage report ``trajectory`` and
#: the §5 excerpt teaches it, so a 1.1 run is not comparable with a 1.0 one —
#: which is the point, since that is the content WP-1059 re-A/Bs
PROTOCOL_VERSION = "1.1"

#: shim-enforced hard stop on refinement calls per episode — a runaway guard
#: (tests/CLAUDE.md), never a timer; the prompt advertises 6
MAX_CALLS = 8

EPISODE_IDS = ("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8")

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


# ----------------------------------------------------------------------
# prompt
# ----------------------------------------------------------------------
def _protocol_excerpt(section_prefix: str) -> str:
    """One ``## N.`` section of docs/AGENT_PROTOCOL.md, verbatim, ending at
    the ``---`` separator — the manual ships with the feature, so the excerpt
    is extracted live rather than copied."""
    text = (REPO_ROOT / "docs" / "AGENT_PROTOCOL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.startswith(f"## {section_prefix}"))
    end = next(i for i in range(start + 1, len(lines))
               if lines[i].startswith("---") or lines[i].startswith("## "))
    return "\n".join(lines[start:end]).rstrip()


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

Each response carries `report` — the three-layer FitReport.  The two
governing sections of the package manual are quoted verbatim below.

{s5}

{s6}
"""


def render_prompt(eid: str, episode_dir: Path, *, condition: str,
                  python: str = ".venv/bin/python") -> str:
    """The one shared prompt (PROTOCOL.md pins it; no per-model tuning).

    Report-on runs get the AGENT_PROTOCOL §5/§6 excerpts — the manual ships
    with the feature; report-off runs get neither the report nor the manual.
    """
    if condition == "report-on":
        report_clause = ", and the full FitReport,"
        report_section = _REPORT_SECTION.format(
            s5=_protocol_excerpt("5."), s6=_protocol_excerpt("6."))
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
    """Write episode dirs + truth tree; returns the episode dirs written."""
    if condition not in ("report-on", "report-off"):
        raise ValueError(f"condition must be report-on|report-off, "
                         f"got {condition!r}")
    episodes = build_episodes()
    episodes_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for eid in only or EPISODE_IDS:
        ep = episodes[eid]
        edir = episodes_dir / eid
        edir.mkdir(exist_ok=True)
        (edir / "episode.json").write_text(
            json.dumps(ep["core"], indent=1) + "\n", encoding="utf-8")
        (edir / "condition.json").write_text(json.dumps({
            "protocol_version": PROTOCOL_VERSION,
            "condition": condition,
            "include_report": condition == "report-on",
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
                        choices=["report-on", "report-off"])
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
