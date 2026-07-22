# WP-0602 — Agent JSON surface hardened

Milestone: v0.6 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Agent JSON surface hardened: `agent.refine_json(dict) → dict`, JSON-Schema
  export for tool-calling

## Context pointers

- Every schema already exports JSON Schema (pydantic v2, `extra="forbid"`,
  ±inf-safe serialization) — this WP is the single-call composition and its
  hardening (errors as structured, actionable JSON), not new schema work.
- The MCP server wrapping `refine_json` stays fenced in v2.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
