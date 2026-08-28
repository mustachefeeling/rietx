# WP-1303 — Retire `refine_json` and the schema export

Milestone: v1.3 · Status: ⬜
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
- **The break, recorded.** `docs/releases/1.3.0.md` § Upgrading, "Who has to do
  something": *You called `rietx.agent.refine_json`* → `rx.refine(...)` /
  `Refinement.fit`, `result.model_dump(mode="json")`, and catch `ValueError` /
  `RuntimeError` where the envelope returned `ok: false` (three lines shown); *You
  registered `tool_definition()`* → none existed in any traced run; a tool loop should
  wrap the Python API with path arguments. Rule: old files must always open, old code
  need not (rietx has few users, all in direct contact).

### Inherited

Nothing yet.

## Non-goals

Touching `capabilities()` beyond the contract field (the GUI uses it). Designing the MCP
server (v2; its substrate is the GUI server's `/api`, ROADMAP's v2+ row).

## Tasks

- [ ] Delete the module, test and chapter; fix `__init__`, `_about`, `capabilities` and
      its test.
- [ ] Manual, `CLAUDE.md`, protocol §9c, consistency test, dist test, eval harness
      references.
- [ ] `docs/releases/1.3.0.md` § Upgrading (or the section of the notes file v1.3 opens).
- [ ] Tests: fast-suite count moves by exactly the deleted count (quote venv + platform).

## Acceptance

```sh
grep -rn "refine_json\|tool_definition\|request_schema\|response_schema\|rietx.agent" src tests gui examples docs/manual CLAUDE.md   # hits nothing
.venv/bin/python -m pytest tests/test_capabilities.py tests/test_manual_api.py tests/test_docs_consistency.py -n auto --dist loadgroup
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m ruff check src tests examples
```

`capabilities()` lists five contracts; the `test_manual_api.py` partition is green (the
deleted names leave the surface).

## References

- WP-0602 (the envelope), WP-1003, WP-1110 (`tests/eval_agent_surface/PROTOCOL.md` 1.0).
- Anthropic, agent design guidance (the `claude-api` skill's `shared/agent-design.md`,
  read 2026-08-27).

## Handover log

- **2026-08-28** — created, from the parked v1.3 plan.
