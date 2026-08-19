# WP-1105 — AGENT_PROTOCOL hygiene: stale claims out, vocabularies covered

Milestone: v1.1 · Status: ⬜
Depends on: 1104 (same document; the audit decides which claims stay before
the tables document them). Docs + tests only — no contract change, no version
event; may land before the v1.1 version flip.

## Goal

AGENT_PROTOCOL.md states nothing false about the shipped surface, documents
every member of the three vocabularies an agent can branch on, and a meta-test
fails whenever a vocabulary member or an engine diagnostic code loses its
protocol row — the drift that produced today's gaps cannot recur silently.

## Context

Verified 2026-08-18 (file:line against the working tree at `6517c914`):

- **§9 is stale since the WP-1003 default flip.** `AGENT_PROTOCOL.md:1213-1215`
  says `task="refine"` returns `trajectory[]` "by default"; `:1413` says "The
  whole of §9a arrives on the plain request, with no extra call and no flag to
  know about" (and **§9a does not exist** — headings run 9, 9b, 9c); the §9c
  JSON sample (`:1420-1436`) shows a populated `trajectory` on a plain
  request. `agent.py:258` is `report_trajectory: bool = Field(False, …)` —
  flipped at the freeze by WP-1003 on WP-1064's pre-registered kill criterion.
  `docs/manual/using/agents.md` has this right; the protocol does not. The
  tool description (`agent.py:698,715`) was updated; §9 was not.
- **Two engine diagnostic codes have no row**: `EXTINCTION_SCREEN_FAILED`
  (`indexing/extinction.py:731`, level `error`) and `INDEX_VALIDATION_FAILED`
  (`indexing/workflow.py:402`). Root CLAUDE.md's rule — "a WP that adds a
  diagnostic code or a correction adds its row there" — is enforced by
  nothing: `tests/test_docs_consistency.py` contains zero references to
  AGENT_PROTOCOL.md.
- **All four `GateCode` members are undocumented.** WP-1003 promoted
  `gate_failures` from formatted strings to typed `GateFailure(code, message)`
  precisely so a consumer could branch on the name; §6 says only "read
  `region.gate_failures`". No protocol text says that `no_significant_misfit`
  is not a failure, that `outside_validity_radius` means re-detect rather
  than shift, or that `gram_condition` is the resolution-limited signature.
- **Ten of eighteen `ActionKind` members are never named in the protocol**,
  and there is no vocabulary table (§5 says only "typed suggested actions
  from a closed enum"). The `how ∈ {stage, index, advice}` split exists in
  `report/apply.py`'s RECIPES but is served only to the GUI, so the table is
  the sole place a JSON consumer can currently learn that an advice action's
  empty `parameter_paths` is by design. (The structured fix — a field — is
  [1106](1106-report-placement-fields.md); the table is honest today either
  way.)
- **§9c omissions**: `task="refine_multi"` returns no report at all
  (`agent.py:281-283` — reports are per-histogram and python-only) and the
  protocol never says so, leaving §4's ladder unrunnable on that task with no
  explanation; the per-task listing omits the `evidence` companion though the
  envelope line at `:1453` includes it.
- **Payload numbers disagree**: `StageReport`'s docstring says a FitReport is
  26–40 kB; `using/agents.md` says 114 kB with a 3.6 kB trajectory (~3 %)
  while the `report_trajectory` field description says ~26 %. Different
  fixtures; nothing says which.
- **Two code namespaces, undeclared**: ~47 GUI/session codes
  (`NOT_FOUND`, `RUN_IN_FLIGHT`, `STALE_REVISION`, …) share the
  `Diagnostic`-style code shape with the ~81 engine codes but correctly have
  no protocol rows. One sentence should say the split exists, so an agent
  reading a code knows which namespace it is in.
- Also noticed, fix in passing: the §7 subsection ordering runs
  7 → 7b → 7c → **7e** → **7d** → 7f.

## Non-goals

- Re-grounding claims in literature (1104) or demoting/promoting Layer 2's
  posture — WP-1064's grid left it ("not isolable from Layer 0").
- Any schema, field, or emitter change (1106); `Diagnostic.code` stays an
  open vocabulary (`str`, per its design note) — the meta-test pins *rows for
  what is emitted*, never a closed code list.
- Documenting the two emitter-less `ActionKind` members as if they fired: the
  table marks them "no emitter — resolution in 1106" until 1106 resolves
  them.

## Tasks

- [ ] Fix §9/§9c: the three stale trajectory claims, the §9a dangling
      reference, the JSON sample annotated (`trajectory` only with
      `"report_trajectory": true`); renumber or reorder the §7 subsections.
- [ ] Add the two missing diagnostic rows (`EXTINCTION_SCREEN_FAILED`,
      `INDEX_VALIDATION_FAILED`) in the tables where their families live
      (§7e / §7c), remedy included, per the house row format ("what it means
      you must not do").
- [ ] Add the `GateCode` table to §6 (4 rows: code → meaning → correct
      response) and the `ActionKind` table to §5 (18 rows: kind → how
      (stage/index/advice, quoted from RECIPES) → emitter condition → why
      `parameter_paths` may be empty).
- [ ] §9c: `refine_multi` returns no report (and why); add `evidence` to the
      per-task listing; one sentence declaring the engine vs GUI code
      namespaces.
- [ ] Reconcile the payload numbers with one fresh measurement (state the
      fixture and channel count beside each figure, in both files).
- [ ] Meta-tests in `tests/test_docs_consistency.py`: (a) every
      `GateCode`/`ActionKind` Literal member appears in the protocol (import
      the Literals — quoted from the live registry, the `capabilities()`
      idiom); (b) every engine-emitted `Diagnostic` code has a protocol row —
      collect `code=` string literals by AST walk over `src/rietx` excluding
      `gui/`, plus the three envelope codes from `agent.py`. **Write the
      collector first and watch it fail on the two known-missing codes**
      before their rows land — that failure is the proof it sees real
      emissions. A code the walker cannot see statically goes in an explicit
      exceptions list with a comment naming its emitter. (c) citation
      resolution (from 1104): every WP the protocol names inline exists as a
      file, and every author-year citation resolves in the protocol's stated
      references location — 1104 verified both by hand and added ~10
      citations, so the check protects more than when this WP was planned.
- [ ] Handover: state the fast-suite delta (+N = the new meta-tests, per the
      "say which numbers moved" rule).

## Acceptance

The meta-tests pass and are demonstrably live (reverting one new protocol row
makes (b) fail); no stale §9 claim survives a grep for "by default" near
`trajectory`.

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1003 (the freeze: `report_trajectory` default flip; `GateFailure`
  promotion), WP-1064 (the pre-registered kill criterion and grid).
- Root CLAUDE.md § Roadmap: "a WP that adds a diagnostic code or a correction
  adds its row there" — the rule this WP gives teeth.

## Handover log

- **2026-08-19** — session start: pruned `### Inherited` — its one entry
  (1104's citation-resolution coverage test) is still true and actionable, so
  it is folded into the meta-test task as item (c) rather than left as
  arrival context.
- **2026-08-18** — created from the agentic-report planning session
  (evidence file:lines verified against `6517c914` that day), with
  [1104](1104-agent-protocol-literature-audit.md)/[1106](1106-report-placement-fields.md)/[1107](1107-eval-placement-round.md).
