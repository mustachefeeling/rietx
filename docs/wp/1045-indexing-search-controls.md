# WP-1045 — Indexing search controls: one surface for the GUI and the agent

Milestone: v1.0 · Status: ⬜
Depends on: 1027, 1042 (1043 soft)

## Goal

A caller who knows something can say it, in either chair: the GUI's indexing
panel grows the controls a human would set — engines, crystal systems, cell
parameter ranges, budget/preset — the agent schema exposes the same fields, and
both gain **priors**: a structural analogue's cell or space group, tried first.
One spec behind both surfaces; priors steer the search, they never gate it.

## Context

### The user's design call, 2026-08-06

> In the indexing GUI, user should be able to specify engines, crystal systems
> and cell parameter ranges, plus any things I've forgotten. This should mirror
> the agent surface, where agents might have more information such as structural
> analogues, so they might try similar SGs or cells first.

Two ideas, and the second is the design-bearing one.

**1. The controls are one surface with two views.** Everything the GUI form
offers is a `SearchSpec` field or an `index_pattern` kwarg, and the agent tool
schema already quotes engine names from the live registry (WP-0602's rule). So
this is the capabilities pattern once more: the GUI form, the agent schema and
`SearchSpec`/`index_pattern` are held in bijection by a meta-test — a field
exposed in one and absent in another is a test failure, not a drift. Enums are
quoted live: engines from `engine_names()`, systems from `SYSTEM_ORDER`,
presets from `SEARCH_PRESETS` once WP-1042 lands it.

**2. A prior steers, never gates.** An agent (or a human with a database hit)
often holds a structural analogue — an isostructural compound whose cell and
space group are approximately right. The package's premise (a reasoning
consumer given good surfaces beats a mechanical rule) says give the reasoner a
way to *state* that knowledge, under three rules:

- **Priors reorder and seed; they never inject candidates past the engines.**
  A prior's system jumps the `SYSTEM_ORDER` queue in WP-1042's scheduler, and a
  prior cell can seed engine starting points (trial_error's base-line
  assignment, svd's starting basin, dichotomy's volume bracket). A prior cell
  that is real is then *found* by the engines from the seeded start, so
  `found_by` and `grade` keep their meaning — at least two independent finders.
  A prior confirmed only by `refine_with_shift` and not by any engine enters the
  candidate list with its provenance and grades `low` structurally, which is the
  honest reading: stated, shift-consistent, unconfirmed.
- **A prior narrows *order*, never the box** — no system dropped, no range
  tightened by a prior (the no-silent-caps rule). Explicit narrowing stays the
  caller's own act and is already recorded in `spec_notes`.
- **A prior used is recorded** — `INDEX_PRIOR_USED` naming what was supplied
  and what it changed — because assumed knowledge must never look like measured
  knowledge (the `INDEX_SHIFT_ALLOWANCE` precedent).

### The inventory (what "specify" concretely means)

Already in `SearchSpec`, needing only exposure: `systems`, `centrings`
(per-system), the axis-length range `min_d_axis`/`max_d_axis`, the volume range
`min_volume`/`max_volume` (float or per-system), `n_unindexed`,
`n_search_lines`, `k_sigma`, `budget_seconds`/`total_budget_seconds` (the
preset, once 1042 lands), `max_candidates`, `seed`. On `index_pattern` itself:
`engines`, `validate`, `check_top`, `two_theta_limits` (the project's excluded
regions already govern picking). New in this WP: the prior block only. The
panel need not show all of it at top level — disclosure is a GUI question
(gui/CLAUDE.md) — but everything above must be *reachable*, and everything
reachable must round-trip the project document as a project setting.

### GUI notes

The panel extends WP-1027's indexing panel; mutating verbs return 409 while a
run is in flight (gui/CLAUDE.md); control state is a *project* setting
(`project.json`), not history. Provisional candidates and the evidence view are
what the panel *shows* (WP-1042/1043); this WP is what the panel *asks*.

## Non-goals

- The evidence view and its visual check — WP-1043. Streaming, presets and the
  scheduler — WP-1042.
- Search-match phase identification and multi-phase indexing (v2+ fence) — a
  prior here is a *cell hypothesis for this pattern*, not phase ID.
- Any change to `grade` or the gate.

## Tasks

- [ ] The bijection meta-test: GUI form fields ↔ agent schema ↔
      `SearchSpec`/`index_pattern` kwargs, with enums quoted from the live
      registries (the `capabilities()` meta-test is the template).
- [ ] Expose the existing inventory in the GUI panel (disclosure per
      gui/CLAUDE.md) and round-trip it through the project document.
- [ ] `prior_cells` / `prior_spacegroups` on `SearchSpec`: schedule reordering
      + engine seeding + `INDEX_PRIOR_USED`; the steer-never-gate rule pinned by
      a test — a deliberately wrong prior on a scoreboard dataset changes no
      final rank and no grade, only when things were searched.
- [ ] `agent.refine_json`'s index task and `tool_definition()` accept the same
      fields; `docs/AGENT_PROTOCOL.md` gains a "state what you know" row with a
      structural-analogue worked example.

## Acceptance

A poisoned prior costs time, never truth: on a scoreboard dataset, a wrong prior
cell changes no final rank and no grade, and the result records that the prior
was tried. A correct analogue prior (a certified cell perturbed by a few hundred
ppm) surfaces the truth in the first streamed shortlist. GUI and agent runs with
identical controls produce identical `spec_notes`.

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py tests/test_indexing_consensus.py \
    tests/test_agent_surface.py tests/test_capabilities.py -n auto
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- [WP-1042](1042-anytime-results-quick-default.md) § What `quick` is — the
  scheduler priors reorder; [WP-1043](1043-agent-and-human-indexing.md) — the
  evidence view a prior-only candidate lands in.
- `capabilities()` (WP-1007) and the agent schema registry meta-test (WP-0602)
  — the two bijection precedents this WP's meta-test copies.
- `indexing/engines.py` `SearchSpec` — the one object all three views expose.

## Handover log

- **2026-08-06** — created in the 1042/1043 review session from the user's
  design call (controls + agent mirror + analogue priors). Split so 1043 keeps
  the output half (evidence, visual check) and this WP the input half; sized
  after 1042's scheduler and presets exist, which is why it depends on 1042.
