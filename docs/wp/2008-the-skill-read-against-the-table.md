# WP-2008 — The agent skill read against the audit table

Milestone: generality · Status: ⬜
Track: The prose
Depends on: 2001, 2002, 2003, 2004 (2005, 2006, 2007 soft: those three move few skill rows)
Priority: P3 2026-10-18 — down a rung from P2: nothing here can start until the audits have ruled; lifts when 2002–2004 close

## Goal

Every rule in `docs/skill/rietx/` that encodes a rietx-own heuristic is tagged with the
families it was measured on or demoted to `(Hypothesis: …)`; no row states a verdict the
package no longer makes; the body stays within its 5 000-token budget and each reference
within its cap. Contested cuts are measured on `tests/eval_skill` before they land.

## Context

The rule is `../milestones/generality.md` § The rule. The skill is the second source of
overfit the open ranked, after the runner's actions: 61 000 words across `SKILL.md` and 19
`references/` files, the largest `surprises.md` (5 570 words), `judging.md` (5 546),
`series.md` (5 308), `api.md` (4 592), `diagnostics-indexing.md` (4 277). It is read whole
per task shape on every call, so a row measured on one dataset and phrased as a rule costs
tokens on every fit as well as steering the agent wrong.

**The seams.** Root CLAUDE.md § skill and WP-1330/1338: a rule goes in the cheapest place
that holds it (the package's own output first, a reference row keyed on a name the agent
holds, a routing row for a task shape, the body last). Every row written from runs is
tagged `(Measured: …)` or `(Hypothesis: …)`; 130 lines carry one today (145 tags). `tests/skill_caps.py`
has a ceiling per file and a budget that fails growth. `rietx skill --install . --copy`
re-syncs the two committed copies. `tests/test_docs_consistency.py` fails a diagnostic
code without a row; `test_skill.py` a verb the index omits; `test_skill_cli.py` a copy out
of sync.

**The tags are the entry points.** A `(Measured: …)` tag naming one dataset is a tier-3
row with one family. The audit: for each tagged row, which table row (code, action,
constant) does it rest on, what did the audit rule, and how many families does the tag
name? A row resting on a demoted action is rewritten to the number the package now
states. A row with one family is re-tagged `(Hypothesis: …)` or measured out to three.

**The tripwire does not reach prose.** 2001's guard walks `src/`; a heuristic written as a
skill row is invisible to it (2001's docstring says so). This WP's answer is a test over
the tags: every `(Measured: …)` tag names at least one family token from a list the test
holds, and a new row without a tag fails. That is weaker than the code guard and is said to
be.

**Measured before cut.** `tests/eval_skill` (WP-1905) asks whether a body change keeps
outcomes; a round is registered before it runs and its cells are a spend the maintainer
approves per session (memory `eval-spend-is-scoped-per-session`). A row the audit demotes
is cut; a row the agent is thought to need, whatever the table says, is a contested cut
and goes through the harness.

### Inherited

(none at filing)

## Non-goals

- Rewriting the skill's voice or structure (1330, 1338 and 1985 settled those).
- The manual (`docs/manual/`, `docs/docs/`): 1986 is moving it; a chapter that quotes a
  demoted verdict is that WP's or a follow-up's.
- Adding a row for a new feature.

## Tasks

- [ ] Inventory: every tagged row, the table row it rests on, the audit's ruling, the
      families the tag names; every untagged row that states a threshold or a verdict.
- [ ] The tag test (`tests/test_skill_tags.py` or in `test_skill.py`): each
      `(Measured: …)` names a family token; a threshold or verdict row without a tag fails.
- [ ] Rows resting on demoted actions rewritten to the number; rows with one family
      re-tagged or measured out; rows with none cut.
- [ ] The contested list to the maintainer with a costed `eval_skill` round; run what is
      approved; land what survives.
- [ ] The body re-measured against its 5 000-token budget; each reference against its cap;
      `rietx skill --install . --copy` and the copies' test.
- [ ] Tests; the fast count moved by exactly the tests added.
- [ ] Skill: this WP *is* the skill; the handover quotes the word count before and after
      per file and the number of rows cut, re-tagged and rewritten.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_skill*.py tests/test_docs_consistency.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The record's row "the skill encodes no untagged tier-3 rule" is checked by the tag test on
the final tree.

## References

- `docs/milestones/generality.md`; WP-1330, 1338, 1905, 1985; `tests/skill_caps.py`.

## Handover log

- **2026-10-18** — created, from the milestone's opening session. The acceptance row the
  first plan had here, "the skill's reference total falls", was dropped on the second
  review: a demoted verdict's meaning has to be interpreted somewhere, usually the skill,
  so the total may not fall and the right bar is the tag.
