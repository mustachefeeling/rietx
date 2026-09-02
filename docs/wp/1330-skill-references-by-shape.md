# WP-1330 — The skill grows by reference: one file per task shape, and the row an agent can write

Milestone: unscheduled · Status: 🔄 2026-09-02 — in flight
Depends on: 1304 (the skill), 1308 (the derived verb gate)

## Goal

A rule an agent driving rietx needs lands in the skill by a written route
rather than by a session's memory: the body takes only what holds for every
fit, a task *shape* (a series, a batch, a magnetic phase) has one reference
file each, and a reference written from runs carries its evidence on every row,
so an agent-written row is reviewable. `references/batch.md` is the first such
file, opened for the contributor whose batch runs will fill it, and the
rituals, the contributor docs and `tests/test_skill.py` all name the route.

## Context

Measured on the tree at 4e37e96a (2026-09-02), the day this WP opened:

- **Everything with a name is gated; nothing with a rule is routed.**
  `tests/test_docs_consistency.py` fails on an engine code, a gate or an
  action without a skill row; `tests/test_skill.py` on a public verb the API
  index omits (1308), a dead link, an unexported `rx.` name, a body over its
  cap; `tests/test_skill_cli.py` on a committed copy out of sync. Every
  checklist line in `/wp-handover` step 6 and `/pr-review` step 6, and root
  CLAUDE.md's skill bullet, ask the same mechanised question — "a diagnostic
  code or a correction with no row?" — and none asks the one no test can: did
  this session measure a rule an agent driving rietx needs, and is it in the
  skill or only in the handover log? Protocol rule 4 routes *findings* out of
  the CLAUDE.md files into the handover log, which no consumer reads, and
  names no third destination. WP-1131 and WP-1301 reached the skill by their
  sessions' own judgement.
- **The body is full.** SKILL.md at 32 949 B of a 33 000 B cap, raised once
  (1131, +1000 for a deliverable row); `references/diagnostics.md` at 35 130
  of 36 000. A routing row costs ~200 B, so every new reference is paid for by
  a cut, and nothing said so.
- **Coverage is by mention.** A backticked code in a stale row passes; 1308
  recorded that the routing row's wording has no test. The behavioural
  instrument is the agent-surface eval (`tests/eval_agent_surface/`), a paid
  round launched by hand.
- **The mechanism already exists**: §5, §7, §7b-7f, §8, §9 and §9b live
  entirely in `references/`, cited from the body's routing table by
  situation. `series.md` (6 240 B) is a shape reference: a normal refinement
  never opens it. Batch refinement — candidates against one pattern, patterns
  fitted as separate jobs — is the same shape one rank up, under §9 "one fit
  is not the answer". A sibling skill was considered and declined: two
  judgement cores drift, and every gate above would need generalising (install
  of N skills, two copies each, per-skill caps, a plural
  `capabilities().skill_path`). Promotion criterion, decided now: a shape
  earns its own skill when it needs a judgement core with more than one
  reference of its own, or a trigger vocabulary under which a user would not
  load a Rietveld protocol first.
- **Every reference already opens the same way** — an H1, a "Load it when …"
  paragraph, the italic provenance line — by convention, unpinned.
  `docs/manual/conf.py` renders every reference file without an edit
  (`_write_skill`, verified), so a new file reaches the manual by existing.

Seams: `docs/skill/rietx/SKILL.md` (routing table, description, header),
`docs/skill/rietx/references/`, `tests/test_skill.py`,
`.claude/commands/{wp-handover,pr-review}.md`, `docs/wp/TEMPLATE.md`,
`CONTRIBUTING.md`, `AGENTS.md`, root CLAUDE.md § skill, ROADMAP rule 4.

## Non-goals

- The batch heuristics themselves. The contributor's runs are the evidence;
  this WP opens the file, seeds it with four rows whose evidence is already in
  the repo (two measured, two hypotheses naming what would decide them), and
  fixes the form. A seeded row the runs contradict is the contributor's to
  overwrite.
- A batch *verb* in the package. `Refinement` per candidate and history
  branches are the surface; whether a `refine_batch` earns its place is
  measured on the contributor's logs, not decided here (CLAUDE.md's "gates,
  renders, audits or parallelises" rule).
- A second skill. Declined above, with the criterion that would reopen it.
- Retrofitting evidence tags onto `surprises.md`: its rows carry their numbers
  inline and its header does not opt in.
- The eval round 1.2 (owes a sealed workspace; WP-1307).

## Tasks

- [x] The WP, filed: this file, its ROADMAP row, and protocol rule 4's
      third destination
- [x] `tests/test_skill.py`: every reference opens with an H1, a "Load it"
      paragraph and the provenance line; a reference declaring "Every row
      carries its evidence" has every numbered row tagged `(Measured: …)` or
      `(Hypothesis: …)`, numbered under its own section, increasing
- [x] `references/batch.md` (§9c): the header, the row form, four seeded rows;
      the routing row, the description phrase and the placement sentence in
      the body, paid for by cuts; copies re-synced
- [x] Root CLAUDE.md § skill: the three destinations and the shape rule; the
      CLAUDE.md cap raised by the lines it costs, in the caps diary
- [x] `/wp-handover` step 6 and `/pr-review` step 6 ask the unmechanised
      question; `docs/wp/TEMPLATE.md` carries a Skill line in Tasks
- [x] `CONTRIBUTING.md` § The agent skill (placement, the row form, the two
      commands) and `AGENTS.md`'s pointer to it
- [ ] Tests: the four skill/doc suites, the manual build, ruff, the fast
      suite; counts in the handover entry
- [x] Skill: the §9c routing row and `references/batch.md` (above); the
      body's `resolution_limited` name kept where its paragraph is

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_skill.py tests/test_skill_cli.py tests/test_docs_consistency.py tests/test_manual_api.py
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

And by hand: delete the tag from one row of `references/batch.md`, or the
"Load it" paragraph from any reference — `tests/test_skill.py` goes red naming
the file and the row.

## References

- agentskills.io specification (progressive disclosure: the body on
  activation, references on demand), verified 2026-08-29 by 1304.
- WP-1304 (the split and its caps), WP-1308 (the derived door gate, and the
  row wording no test covers), WP-1307 round 1.1 (R11: three of four cells
  stopped on a §4b row against 0 of 6 in the campaign; R5: the flat
  direction's 27 %).

## Handover log

- **2026-09-02** — created, from a session's audit of where a new heuristic is
  told to go: none of the four places (CLAUDE.md, the two rituals, protocol
  rule 4) said.
