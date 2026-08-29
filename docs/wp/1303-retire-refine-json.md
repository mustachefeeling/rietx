# WP-1303 — Retire `refine_json` and the schema export

Milestone: v1.3 · Status: ✅ 2026-08-29 — `rietx.agent` deleted, the eval shim owns the
envelope it always defined, and the manual chapter is rewritten rather than dropped
Depends on: —

## Goal

`rietx.agent` no longer exists; the agent envelope is no longer a versioned contract;
the break is recorded the way `docs/manual/using/compatibility.md` prescribes.

## Context

- **Baseline.** Zero calls of `refine_json`, `rietx.agent`, `tool_definition` or the
  request/response schemas in: WP-1110's surface round (235 traced interpreter starts;
  the `pointed` cell's 25 calls were the only ones, and prompted); the 2026-08-26 ramp run
  (91 tool calls, told to read the protocol); a contributor's four projected runs (222
  tool calls, confirmed by raw grep with a positive control); and the same contributor's
  whole 86-run bundle (5,430 tool calls; a lower bound, since script bodies are not
  rendered). Every agent with the choice used the notebook API: `Instrument.*`,
  `read_pattern`, `Structure`, `Refinement.fit`, `refine_sequential`, `build_report`.
- **Why it cannot serve the case it was built for.** One
  `PatternData.model_dump_json()` of a lab pattern is 44 399 chars (11.1 k tokens);
  `SequentialRefineRequest.patterns` is `list[PatternData]`, inline only, so a 68-pattern
  series is ≈ 754 k tokens in one request. Its own docstring fences paths and CIF text to
  v2. Anthropic's agent-design guidance says the same thing from the other side: a
  dedicated tool earns its place only to gate, render, audit or parallelise, and a
  refinement needs none of those from a shell-equipped agent; lightweight identifiers
  (paths) beat inline payloads.
- **Decision (maintainer, 2026-08-27): full delete**, not freeze. An MCP server (v2)
  would not reuse this shape: it would take paths and project results, and its natural
  substrate is the GUI server's existing `/api` contract over a project directory. The
  `{ok, error}` discipline is re-derivable then. NSLS-II PowderLine, the one
  process-boundary caller in sight, brings its own JSON recipe (WP-1306).
- **Cost of keeping it.** ~1900 lines (module 769, test 650, manual chapter 475) touched
  on every schema change.
- **Files** (at 79e5ae82; grep again on arrival). Delete `src/rietx/agent.py`,
  `tests/test_agent_surface.py`, `docs/manual/using/agents.md`. Edit:
  `src/rietx/__init__.py:3` (`from . import agent`, the first import; removing it changes
  nothing measurable about import time, since `indexing` is imported directly at `:16`)
  and `__all__`; `_about.py:84` `AGENT_TOOL_NAME` (delete; grep its users);
  `capabilities.py` (drop the envelope's contract field; `Capabilities.schema_version`
  bump with its comment; `tests/test_capabilities.py` contract list);
  `docs/manual/using/compatibility.md:44-58` (six contracts → five);
  `docs/manual/index.md:32`; `docs/manual/using/cli.md:31` ("Prefer the Python API");
  `CLAUDE.md` (the `agent.refine_json` paragraph and the "six versioned contracts"
  clause); `docs/AGENT_PROTOCOL.md` §9c deleted, its GUI-namespace note moved to §7's
  preamble; `tests/test_docs_consistency.py:774` (drop the `ERROR_CODES` union);
  `tests/api_surface.py:358` comment; `tests/test_gui_dist.py:282` rationale ("the tool
  description's pointer" → "an offline agent's copy"); `tests/eval_report_agent/` and
  `tests/eval_agent_surface/rietx_surface_trace.py` (only the import that would fail; the
  shim's target list changes in WP-1307 with its protocol bump); docstring mentions in
  `schemas/plan.py:159`, `indexing/engines.py:412`, `schemas/common.py:70` (history,
  keep).
- **Callers the list above missed** (grepped on arrival, 2026-08-29). Five test files
  outside `test_agent_surface.py` reach the envelope to exercise *other* features, so
  each needs its arm rewritten against the Python API rather than deleted:
  `tests/test_report_loop.py` (WP-1058's acceptance, one call), `tests/test_report_apply.py`
  (a docstring), `tests/test_search_controls.py` (four, WP-1045's JSON path),
  `tests/test_schemas.py` and `tests/test_fitreport_layers.py`. Plus
  `docs/manual/using/indexing.md:759`.
- **The break, recorded.** `docs/releases/1.3.0.md` § Upgrading, "Who has to do
  something": *You called `rietx.agent.refine_json`* → `rx.refine(...)` /
  `Refinement.fit`, `result.model_dump(mode="json")`, and catch `ValueError` /
  `RuntimeError` where the envelope returned `ok: false` (three lines shown); *You
  registered `tool_definition()`* → none existed in any traced run; a tool loop should
  wrap the Python API with path arguments. Rule: old files must always open, old code
  need not (rietx has few users, all in direct contact).

## Non-goals

Touching `capabilities()` beyond the contract field (the GUI uses it). Designing the MCP
server (v2; its substrate is the GUI server's `/api`, ROADMAP's v2+ row).

## Tasks

- [x] Delete the module, test and chapter; fix `__init__`, `_about`, `capabilities` and
      its test. (`SCHEMA_VERSION` 0.11 → 0.12 with it: the removal is the first
      non-additive step on that ladder. `report_trajectory` re-derives from
      `Refinement.fit`'s keyword, `rietx.agent` becomes a `_TOP_LEVEL_HINTS` pointer.)
- [x] Manual, `CLAUDE.md`, protocol §9c, consistency test, dist test, eval harness
      references. (The chapter is **rewritten, not deleted** — it also documents
      `capabilities()` and the six version strings, whose names survive; deleting it
      would have dropped them from the manual-API partition and broken ten
      cross-references. The eval shim keeps the envelope and now runs it itself.)
- [x] `docs/releases/1.3.0.md` § Upgrading (the file is opened by this WP; later v1.3
      WPs add their own sections).
- [x] Tests: fast-suite count moves by exactly the deleted count (quote venv + platform).
      **3431 → 3378 passed, 122 skipped both ends** (`[dev]`, darwin/arm64, this session
      alone on the machine): −39 the deleted file, −2 the two agent-request chairs in
      `test_search_controls.py`, −12 `test_schemas.py`'s per-`Base`-subclass
      parametrisation losing `agent.py`'s twelve models. No skip moved.

## Acceptance

```sh
# 1. no live use: no import, no call, no attribute access
grep -rn "refine_json(\|tool_definition(\|request_schema(\|response_schema(\|import rietx\.agent\|from rietx import agent\|from \.agent import\|rietx\.agent\." src tests gui examples docs/manual CLAUDE.md | grep -v PROTOCOL.md   # hits nothing
# 2. every surviving mention is history: a WP-1303 note, or an eval round's record
grep -rn "refine_json\|tool_definition\|request_schema\|response_schema\|rietx\.agent" src tests gui examples docs/manual CLAUDE.md | grep -v "WP-1303\|eval_agent_surface/\|eval_report_agent/PROTOCOL.md\|tests/CLAUDE.md"   # hits nothing
.venv/bin/python -m pytest tests/test_capabilities.py tests/test_manual_api.py tests/test_docs_consistency.py -n auto --dist loadgroup
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m ruff check src tests examples
```

The `test_manual_api.py` partition is green (the deleted names leave the surface, and
the chapter that documented them keeps documenting `capabilities()`).

**The acceptance grep was sharpened on arrival, and the reason is a rule.** As
written it demanded no mention at all, which cannot be met without editing two
things that must not be edited: the **pre-registered** eval records
(`eval_agent_surface/PROTOCOL.md` + its round-1.0 scorer, `eval_report_agent/
PROTOCOL.md`'s kill/keep table), whose whole discipline is that a round's
registration is not rewritten once it has run — the retirement is *their result*
— and the **removal notes** themselves (`SCHEMA_VERSION`'s comment, which must
name what it removed to be a changelog at all). So the check is now two greps: no
live use, and every survivor identifiable as history. `capabilities()` still lists
**six** contracts, not five: the WP file predicted a `Capabilities` field for the
envelope and there was never one — the six are schema / report-thresholds /
event-schema / project-format / textdoc-format / indexing-thresholds, and the
envelope rode on `schema_version`, which is what bumps.

## References

- WP-0602 (the envelope), WP-1003, WP-1110 (`tests/eval_agent_surface/PROTOCOL.md` 1.0).
- Anthropic, agent design guidance (the `claude-api` skill's `shared/agent-design.md`,
  read 2026-08-27).

## Handover log

### 2026-08-29 — shipped: one integration surface, and two places the WP's own plan was wrong

`rietx.agent` is gone. A program that drives this package now does what every
traced agent already did — build the models, call `Refinement.fit`, dump the
answer with `model_dump(mode="json")` — and catches an exception where the
envelope returned `{"ok": false}`. Nothing that computes moved: the four answer
types the envelope wrapped are untouched and serialize byte for byte, so a
stored 1.2 answer still validates. What a reader of this WP could not know
before is that the delete was **not** a straight subtraction in two places, and
both are decisions rather than accidents. The manual chapter had to be
*rewritten* rather than deleted, because it documented `capabilities()` and the
six version strings as well as the envelope, and those names are live: deleting
the file would have dropped them out of `test_manual_api.py`'s partition and
broken ten cross-references from other chapters. And the eval harness's JSON
shim now **runs the request itself** — 50 lines in `run_refine.run_request` —
because that envelope was always the eval protocol's contract rather than the
package's, read by the scorer and the agent and called by nothing outside
`tests/`. Retiring the package's copy moved the recipe to where it was already
owned, which is the same argument the delete rests on.

**Done.**

- `src/rietx/agent.py` (769 lines), `tests/test_agent_surface.py` (650) deleted;
  `rietx.__init__` loses the import and the `__all__` entry, `_about` loses
  `AGENT_TOOL_NAME` (seven brand tokens, not eight).
- **`SCHEMA_VERSION` 0.11 → 0.12**, the first step on that ladder to remove
  rather than add — the comment beside the constant is the changelog and says
  what went and what did not.
- **Two derived surfaces needed a new authority, not a deletion.**
  `features["report_trajectory"]` read `AgentSuccess.model_fields` and now reads
  `inspect.signature(Refinement.fit)` for the keyword that turns the feature on
  — as derived as the field lookup, and it stops importing the same way if the
  keyword is renamed. `features["agent_json"]` is gone with its export.
  `rietx.agent` joins `_TOP_LEVEL_HINTS` (WP-1302's mechanism), so a 1.2 caller
  gets "removed in v1.3 — call rietx.refine() or Refinement.fit()…" rather than
  a bare `AttributeError`; that hint dict now covers two kinds of miss, a name
  one level down and a name that used to exist.
- **Five test files outside the deleted one reached the envelope to exercise
  something else**, and each was rewritten against the python API rather than
  dropped: WP-1058's one-call acceptance (`test_report_loop`), WP-1108's license
  placement (`test_fitreport_layers`), WP-1045's chairs
  (`test_search_controls`, three chairs → two — the bijection is what said they
  could not disagree, so losing a consumer does not lose the rule), the
  plan-mirror pin (`test_schemas`) and one docstring (`test_report_apply`).
  Two of them assemble the old response dict from the two dumps it wrapped, so
  every assertion stayed byte for byte; **order matters there** — `ref.report()`
  must be called *before* `result.model_dump()`, since building the report is
  what writes `statistics.identifiability_clause` (WP-1108's declared write).
- Manual: `using/agents.md` rewritten (envelope half → the python API, the
  upgrade path and when a dedicated tool surface is worth having; the
  `capabilities()` and contracts sections kept verbatim); `index.md`, `cli.md`,
  `indexing.md`, `compatibility.md` follow. `AGENT_PROTOCOL.md` § 9c deleted (86
  lines) with its namespace note moved up into § 7's preamble. `CLAUDE.md`'s
  entry-points paragraph now states the one-surface rule. `docs/releases/1.3.0.md`
  opened with § Upgrading.
- `tests/eval_agent_surface/rietx_surface_trace.py` drops the four targets it
  can no longer reach. Round 1.0's own records (`PROTOCOL.md`, `score_round.py`)
  are **not** edited — see Gotchas.

**Measured** (`[dev]` venv, darwin/arm64, this session alone on the machine;
`pgrep` checked before each suite run).

- Fast selection **3431 → 3378 passed, 122 skipped at both ends**. The baseline
  is measured, not quoted: WP-1302's handover said 3427, which was already stale
  by its own later commits, so `origin/main` was snapshotted with `git archive`
  into the scratchpad and run under this venv with `PYTHONPATH` pointing at the
  snapshot's `src` (3429 passed + 2 that fail only because a `git archive` tree
  has no `.git` — `test_a_fresh_clone_can_rebuild_the_frontend`,
  `test_every_allowlisted_file_still_exists_and_still_needs_it`).
- All **53** are accounted for, and only 41 of them were obvious: 39 from the
  deleted file (37 functions, one parametrised ×3), 2 the agent-request chairs
  in `test_search_controls.py`, and **12 from `test_schemas.py`**, whose
  `test_every_base_subclass_survives_the_new_getattr` is parametrised over every
  `Base` subclass — `agent.py` defined twelve of them. Per-file
  `--collect-only` diffs against the snapshot are what found that; the
  arithmetic alone would have been quietly wrong.
- Fast suite 2:10-2:13 on both trees. **Full suite green on the final tree:
  3525 passed, 131 skipped** (~23 min in this run; two short docs-test
  selections overlapped its first minute). WP-1302's post-review figure was
  3578/131, so the full selection moved by the same **−53** the fast one did
  and no skip moved — which is the check that says every removed test was in
  the fast selection, none of them slow.

**Gotchas for whoever follows.**

- **The acceptance grep as filed could not be satisfied honestly**, and the fix
  is written into the Acceptance section above. "Hits nothing" would have meant
  editing the pre-registered eval records (whose discipline is that a
  registration is never rewritten once it has run — and this retirement is
  literally their measured result) and the removal notes themselves. It is now
  two greps: no live use, every survivor identifiable as history.
- **`capabilities()` reports six contracts, not five.** The WP file predicted a
  `Capabilities` field for the envelope; there never was one — it rode on
  `schema_version`. Six stands: schema / report-thresholds / event-schema /
  project-format / textdoc-format / indexing-thresholds.
- **Both always-loaded CLAUDE.md files sat at or near their pinned caps**, so
  the paragraphs had to be rewrapped to pay for what they added — the cap is
  what forced the evidence out of `CLAUDE.md` and into this entry, which is
  protocol rule 4 working rather than an obstacle.
- **Install this worktree's venv by naming its interpreter.** `VIRTUAL_ENV` is
  exported by the user's shell profile, so a bare `uv pip install -e ".[dev]"`
  in a fresh worktree installs *this* source into the **main checkout's** venv;
  it happened at session start and was repaired. Already in `tests/CLAUDE.md`
  § Quoting numbers, and it still caught this session.

**Next:** WP-1304 (the protocol as a harness-neutral skill). Forward notes are
in the `### Inherited` of 1304 (§ 9c is gone, its namespace rule moved into
§ 7), 1306 (no shipped envelope to reuse; `run_request` is the worked
precedent, and paths-not-payloads is now a CLAUDE.md rule) and 1307 (the
tracer's target list, and why round 1.0's scorer was left alone).

- **2026-08-28** — created, from the parked v1.3 plan.
