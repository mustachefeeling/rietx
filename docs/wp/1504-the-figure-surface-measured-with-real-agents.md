# WP-1504 — the figure surface measured with real agents

Milestone: v1.7 · Status: 🔄 2026-10-01 — harness, judge check and gypsum pilot landed; the rounds wait on the maintainer's next pick
Depends on: 1501, 1502, 1503
Priority: P3 2026-10-01 — the harness and its judge are checked; the rounds wait on a pick from `run.py --menu`

## Goal

A before-and-after measurement of whether an agent given only the skill can
make the figures a chemist asks for, on two models, with the tasks, the
harness and the scores committed. Its result decides what WP-1501 to 1503
keep and whether WP-1505's trigger has fired.

## Context

### Why a measurement, and why real agents

Three rules from earlier rounds bind this WP. An eval of usefulness to an
agent needs real agents, with model and effort as variables, and a
deterministic proxy measures nothing. A registered round is not
authorisation to run its cells: the session offers a costed menu and runs
what is picked. And a declared field with no reader is a claim, so which
numbers of `report` the agents read decides which stay.

The v1.3 round 1.1 cost $38.39 for eight cells and is the price anchor.

### The tasks

Stated as a chemist would, from the 21 phases in
`tests/data/polyhedra_phases.json`, every one COD-cited and so public:

1. Rutile's edge-sharing TiO₆ chains, seen down c.
2. One layer of gypsum with its water, seen edge-on.
3. Calcite's CO₃ groups alone, no Ca, no polyhedra.
4. NAC's AlF₆ octahedra as a 2×2×1 block.
5. LaB₆'s B₆ octahedra without the La–B sticks.
6. Fluorapatite down c for print, 17 cm at 300 dpi, with a legend.

### The conditions

- **Before**: the WP-1470 tree. The agent has `render_structure`, the
  dict, and the manual as it was. Cuts and extents must be done by hand.
- **After**: the WP-1503 tree.
- Sonnet and Opus, at the default effort, three repeats each.
- The agent gets the skill and a shell, and nothing staged in its folder.

### The scores

- Done or not. An Opus judge reads the final picture against a rubric per
  task, and the maintainer spot-checks every "done".
- Renders taken, and the size of each.
- Tokens and wall time.
- Which fields of `report` were read, from the trace.
- Where the agent stalled, in one line per run.

### Where it lives

`docs/wp/1504-eval/` holds the harness, the rubric and the run log. A
condition is enforced in a shim, never in the prompt.

## Non-goals

- Running it in CI.
- A leaderboard or a published benchmark.
- Any figure on data without a peer-reviewed citation.

## Tasks

- [x] The harness: a shim per condition, the six task prompts, the rubric,
  the trace parser for `report` reads. `docs/wp/1504-eval/`: `PROTOCOL.md`
  (registered 2026-10-01), `run.py`, `fig_trace.py`, and
  `reference_figures.py` for checking the judge before it scores a run.
- [x] A costed menu to the maintainer before any cell runs. `run.py --menu`;
  2026-10-01 the maintainer picked J (the judge on the reference figures)
  and A (the gypsum pilot, after, one run per model).
- [ ] The before round, on the picked cells.
- [ ] The after round, on the same cells.
- [ ] The table in this file's handover, and one line per `report` field:
  read or never read.
- [ ] The cuts pushed into 1501 to 1503's `### Inherited`, and 1505's
  trigger rated.

## Acceptance

- Every run's picture, trace and score are in `docs/wp/1504-eval/`.
- The handover states, per task and model, done or not before and after,
  with renders and tokens as ranges.

```sh
.venv/bin/python docs/wp/1504-eval/run.py --menu
```

## References

- The v1.3 record, round 1.1, for the harness pattern and the cost.
- The agent skill's `references/api-figure.md`.

## Handover log

- **2026-10-01** (after the handover below, same session) — Amendment 1.2 is
  written. At the maintainer's question, the round now tests expansion beyond
  one cell properly, and it checks two figure defects nothing caught before.
  The new seventh task asks for one rutile chain, four cells long, seen from
  the side. Every figure is now also checked for bonds ending in empty space,
  and for atoms drawn without their polyhedron. The second check found that
  one cell of rutile or fluorapatite already draws such bare atoms, and that
  the figure's report cannot see a stub left by `hidden=`. No run has used
  1.2 yet, and the judge must be checked again before one does.

  *Measured* (after surface, `[dev]`, darwin): `hidden=("Ca",)` leaves the O
  half of every Ca–O bond drawn while `report.dangling_bonds` reads 0. One
  cell draws 2 Ti bare in rutile and 4 P bare in fluorapatite, and 0 in NAC,
  gypsum, calcite and LaB₆. `keep` drops a polyhedron missing a corner and
  never draws part of one. One rutile chain by `component(via="edges")` and
  `keep` gives 4 Ti and 4 octahedra, and `complete=True` adds 22 bare Ti.
  The figures are in `PROTOCOL.md` § Amendment 1.2.

  *Done.* `run.py`: the `chains` task, two common criteria, the judge's
  `--setting-sources`, `PROTOCOL_VERSION` 1.2, pilot costs beside the prior
  in the menu. `reference_figures.py`: rutile and fluorapatite drop their
  bare centres, calcite keeps whole carbonate groups, and chains is new.
  `fig_trace.py`: comments only, copied into both venvs. The 1.1 pilot moved
  to `pilot-1.1/`, and the 1.1 judge check to `references-1.1.json`.

  *Gotchas.* Two findings belong to item 6, the cuts. No verb removes bare
  centres and no report field counts them. And `dangling_bonds` is blind to
  `hidden=` stubs by its own docstring. Both may be rietx defects rather than
  agent errors, and the round will show whether agents trip on them.

  Next: offer J again (14 judge calls, $1-4 by the prior). Only once every
  right reference passes and every default fails, bring the menu for A or B.
- **2026-10-01** — The harness for the figure round is built and checked end
  to end, and no round has run yet. The Opus judge reads a picture as the
  rubric needs: it passed all six right reference figures and failed all six
  defaults. The first pilot found that a user-level figure skill on the
  maintainer's machine can take a run off rietx entirely. So every run now
  launches without user-level skills (amendment 1.1). Under 1.1 the gypsum
  pilot split. Opus drew the layer with the new extent and cut verbs in under
  a minute for $0.25. Sonnet never opened the rietx skill and drew it by hand
  in matplotlib. That is one run each, so it is a question for the round and
  not yet an answer.

  *Done.* Items 1 and 2. `docs/wp/1504-eval/`: `PROTOCOL.md` (registered,
  then amendment 1.1), `run.py`, `fig_trace.py`, `reference_figures.py`,
  `references.json`, `pilot-1.0/`, `runs/`. Both conditions are prepared at
  `~/rietx-agent-runs/2026-10-01-wp1504-figure` (before `5304b85a`, after
  `97c1d9cc`), and each passed `prepare`'s instrument check. The maintainer
  picked J + A from the menu, then A again under 1.1.

  *Measured* (darwin, Claude Code 2.1.286, `claude-sonnet-5-5` and
  `claude-opus-5-5`; the harness's own venv `[dev]`):
  - Judge check (J): 12 of 12 agree with the reference, $1.30.
  - Pilot under 1.0, kept apart and pooled with nothing: Sonnet not done
    ($0.21, 0.8 min, no render, loaded `yue-figure-style` first and never
    imported rietx); Opus done ($1.42, 5.3 min, 11 renders, loaded `rietx`
    and `yue-figure-style`).
  - Two Haiku probes of `--setting-sources project,local`, $0.03: the six
    user-level skills drop out, while the workspace's `rietx`, the built-ins
    (`dataviz` among them) and the user `CLAUDE.md` still load.
  - Pilot under 1.1 (`run.py table`):

    | task | model | condition | done | renders | looks | tokens (k) | minutes | $ |
    |---|---|---|---|---|---|---|---|---|
    | gypsum | sonnet | after | 0/1 | 0 | 4 | 191 | 1.0 | 0.20 |
    | gypsum | opus | after | 1/1 | 4 | 2 | 233 | 0.8 | 0.25 |

    The Opus run read `hidden`, `dangling_bonds` and `empty`, and printed the
    whole report three times. Judging the two cost $0.15.
  - Spend this session: $3.79 (judge check $1.30, pilot 1.0 $1.86 with
    judging, probes $0.03, pilot 1.1 $0.60 with judging).
  - Lane trial (`/wp-lanes`): no lane dispatched, because context passed
    150K only after the harness item had begun. Kept items: harness estimated
    45 requests, took 48 (decided at 128K); pilot-1.1 estimated 5, took 5.
    The main session ran 91 requests, peaked at 282K and cost $7.90.
  - Fast selection on the final tree (`[dev]`, darwin): 7311 passed, 159
    skipped, 8:17 with no check for another session's suite. No test was
    added, and `tests.added_test_times` agrees: zero. The full selection did
    not run, because nothing here can move a measured number: the harness
    lives under `docs/wp/` and pytest never collects it.

  *Gotchas.*
  - `render_structure(hidden=("La",))` drops La but leaves the B half of
    every La–B bond as a stub. `keep(g, select(g, element="B"))` drops both.
    It is a candidate for item 6's list, and for a skill line if the round's
    agents trip on it.
  - Relaunching a run name under a new protocol first double-counted it: the
    trace is per condition, and both launches logged under the bare name. A
    launch now keys its rows by run and session, read inside the session's
    window.
  - The menu's per-run price is still the prior until a model has two 1.1
    runs. The 1.1 pilot's $0.20 and $0.25 sit well under it.
  - The committed record runs about 140 KB a run (figure at 800 px, trace,
    trail), so option C adds about 10 MB to the repository.
  - A trail's last lines (refinement seconds, per-process floor) are round
    1.1's read-outs and mean nothing here. Each `score.json` holds this
    round's.

  *Review* (`/code-review high --fix`): ten findings, seven fixed in one
  commit. The fixes cover first reads from a process killed before its exit
  row, path containment in place of a string prefix, a judge verdict compared
  case-blind, two guards, and `check()` now holding the launch flags to
  `PROTOCOL.md`. None moved a committed score. Three were declined, each
  needing an amendment. (1) The judge launches without `--setting-sources`.
  All 16 judge sessions so far used `Read` alone and invoked no skill, so
  every verdict on record stands. (2) Two comments in `fig_trace.py` are
  stale: `_short` records a rotation in full, and `RIETX_FIG_RUN` now holds
  `run@session`. The prepared venvs hold a copy of the shim, so editing it
  would part the record from what ran. (3) The registered text says
  `RIETX_FIG_RUN` names the run.

  Next: write amendment 1.2 before any more runs: the judge gains
  `--setting-sources project,local`, and the two shim comments and the
  `RIETX_FIG_RUN` wording are corrected. The flag changes the judge's launch,
  so offer J again ($1.30) with the menu. Then bring `run.py --menu` to the
  maintainer. B (one repeat of
  every cell, 24 runs) comes before C, because N = 1 per cell already says
  whether Sonnet bypassing the skill is general or a gypsum quirk. Then the
  table, one line per `report` field, and the cuts.
- **2026-09-27** — filed from the session that closed WP-1470. Next: wait
  for 1503; then write the harness and bring the menu.
