# WP-1904 — the skill evaluation strategy: how the agent skill is measured, rewritten and kept in sync, decided on a pilot

Milestone: unscheduled · Status: 🔄 2026-10-04 — strategy written and piloted; the three follow-ups filed (1905, 1906, 1907)
Track: The repo's own process
Depends on: —
Priority: P2 2026-10-04 — a scoping WP three others wait on

## Goal

A strategy, verified on a pilot, for the two things the skill was shown to
need: a way to evaluate and design it that fits the budget on hand and keeps
it in step with development, and a body that conveys the practice of driving
rietx at the lowest token cost that keeps the rules. The implementation is
three WPs this one files.

## Context

### The question

Issue #661 (fourteen wrong turns by an agent driving rietx through the
installed skill), WP-1504's round B (the skill opened in 5 of 28 figure runs)
and two reviews that found stale skill text (WP-1523, WP-1541) say the skill
needs work. The maintainer's brief, 2026-10-04: find the current best
practice for evaluating and designing skills without a full benchmark
budget, including keeping the skill in sync with development; and make the
text convey the optimal practice token-efficiently, since it reads as dense
and arcane, with suppositions, contradictions and LLM rhetorical tics, and
need not follow the repository's prose style where that costs tokens.

### What is already here

- Three registered eval rounds with one discipline (`tests/CLAUDE.md` § Three
  eval protocols): register before running, enforce the condition in the
  workspace, fix the read-outs in advance, keep split cells as split. The
  placement round (`tests/eval_skill_placement/`) is the nearest: a colleague's
  fluorapatite fit to judge, four rubric items graded blind by Sonnet, reach
  of a code's row read off the transcript, 18 cells for $3.84.
- Gates that already hold: byte caps and a growth budget per file
  (`tests/skill_caps.py`), every dotted name resolving against the installed
  package, generated `api*.md` pinned byte for byte, every diagnostic code
  and `help.py` key with a row somewhere in the tree, two committed copies
  held identical, a placement rule for where new guidance goes
  (CONTRIBUTING.md § The agent skill).
- No gate on a **value or a formula**, and no measurement of the body's
  **usefulness** since the placement round, which measured routing only.

### What the research found (2026-10-04, sources in § References)

- The harness exists first-party: `claude plugin eval` in this Claude Code
  build (2.1.289) runs cases with and without a plugin, six grader types
  (four free, two judged), N per arm, a cost ceiling, JSON and HTML output,
  in an isolated home with fixtures from a scaffold script. It targets a
  plugin directory, so a skill tree is **built** into one.
- Claude Code keeps only the first 5 000 tokens of a skill after context
  compaction (a shared 25 000-token keep across skills). On the current body
  that cut falls at line 232 of 439: § 4b, § 6 and § 10 are what a long
  session loses. The agentskills.io body recommendation (< 5 000 tokens) is
  therefore a cliff in this harness, not a style preference.
- Anthropic's own guidance: write only what the model lacks; explain the why
  and drop emphatic MUST/NEVER (Claude 4.5+ over-triggers on it); imperative
  voice; one default, alternatives briefly; scripts for deterministic steps;
  evals from three realistic tasks before iterating; read the transcripts;
  a held-out set against overfitting. agentskills.io adds the description
  recipe: ~20 prompts, half near-miss negatives, three runs each, 60/40
  split, stop at five iterations.
- Evidence that padding costs: context files raised agent cost 20-23 % with
  no gain in one ICLR 2026 study; focused skills beat comprehensive ones in
  SkillsBench; instruction-following degrades with density and shows a
  primacy bias (IFScale). All from search snippets; none measured on this
  body. **Terse or symbolic rewrites ("neuralese") are measured on fact
  retention, not rule compliance**, so the rewrite compresses by structure
  and cuts, and keeps English the maintainer can review.
- Variance: decide on paired per-case differences; a single run is noise;
  three runs per arm is the floor every source uses.

### What the audit found (`1904-eval/audit.md`)

The body below the frontmatter is 29 687 B; measured on Haiku it costs
8 700 tokens, `api.md` 13 000, `judging.md` 10 300, so a session that follows
the body's own pointers before its first fit pays about 30 000 tokens. By
paragraph class: rules 43 %, evidence 23 %, rhetoric 12 %, routing 15 %, code
7 %; about 8.2 kB is restated in three reference files. Seven contradictions
with line numbers (Le Bail first against "no Le Bail job"; a worked default
that breaks its own rules 4 and 5; a width seed `W ≈ (FWHM/2)²` that
contradicts the package's own Caglioti form; stop condition 26 against § 4's
ΔBIC rule; others), four phantom body sections cited by the routing table, a
missing rule 23, and fourteen fit-time gaps a driving agent meets. The tic
counts: ~30 "X is not Y" constructions, ~11 epigram closers, ~10
intensifiers, 72 bold spans.

### The strategy

1. **Measure with the first-party harness, cases from real failures, free
   graders first** (WP-1905). `tests/eval_skill/build.py` turns any skill
   tree into a plugin; a registered protocol fixes read-outs; three tiers of
   grader (trigger set, judge-free outcome, short-answer rubric); the
   decision rule for a body change is paired per-case Δ against the current
   body at N = 3 on Haiku and Sonnet, with tokens per run beside the score.
   Cost per two-arm Haiku case measured at $0.16.
2. **Rewrite the body to the budget by cutting evidence and rhetoric, not
   rules** (WP-1906). Rules stay as rows with the API name and a one-clause
   reason; evidence lives in the reference row the rule links; contradictions
   become conditions checked on the package; the first 5 000 tokens hold what
   a long session still needs; the fit-time gaps are placed by the placement
   rule. Judged by WP-1905's suite before merging.
3. **Pin what the skill states, at the points where it drifts** (WP-1907).
   Constants and formulas rendered from the package or asserted; a
   changed-surface step at review that prints the skill rows a PR's renames
   touch; the judge-free tier nightly against model drift; evidence tags that
   name the WP that measured them.

### The pilot (this session; numbers in the handover)

The strategy was tried before it was filed: the harness on this machine, one
case from the placement round and one from-scratch refinement with numeric
graders, the current body on Haiku; a compressed body drafted under the
rewrite rules, run through `tests/test_skill.py`'s gates and the same cases
on Sonnet against the current body. What it showed is in the handover and in
WP-1905's and 1906's Context.

## Non-goals

- The rewrite, the suite and the sync gates themselves: 1906, 1905, 1907.
- Changing where the skill is loaded from, or making the skill tree a plugin.
- The fourteen rows of issue #661: WP-1532, on the rewritten body.

## Tasks

- [x] Prior art: the repo's own rounds and gates, `claude plugin eval`,
      skill-creator, agentskills.io, Anthropic's guidance, the measured
      literature on instruction density and compression
- [x] The audit of the body: structure, contradictions, byte classes,
      duplication, gaps (`1904-eval/audit.md`)
- [x] Token cost measured on Haiku for the body and the two references a
      first fit loads; the compaction cut located
- [x] The pilot: harness on this machine, two cases, the current body
- [ ] The prototype body through the gates and the two cases against the
      current body on Sonnet
- [x] The follow-ups filed: 1905 (suite), 1906 (rewrite), 1907 (sync)
- [ ] Skill: none here — the body change is 1906's

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py -q      # the four WP files and the index
python3 .claude/hooks/wp_index.py && git diff --quiet docs/wp/README.md
```

## References

- Claude Code: `claude plugin eval` <https://code.claude.com/docs/en/plugin-evals>;
  skills (the 5 000-token compaction keep) <https://code.claude.com/docs/en/skills>;
  headless <https://code.claude.com/docs/en/headless>.
- agentskills.io specification and skill-creation pages (best practices,
  evaluating skills, optimising descriptions), via github.com/agentskills/agentskills.
- Anthropic: skill authoring best practices
  <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>;
  skill-creator <https://github.com/anthropics/skills>; "Demystifying evals
  for AI agents", "Effective context engineering", "Writing tools for
  agents", "A statistical approach to model evals" (anthropic.com).
- Snippets, unverified against full texts: SkillsBench (arXiv 2602.12670);
  "Evaluating AGENTS.md" (ICLR 2026); IFScale (arXiv 2507.11538); LLMLingua
  (Microsoft Research).
- Issue #661; `docs/wp/1504-eval/`; `tests/eval_skill_placement/PROTOCOL.md`.

## Handover log

- **2026-10-04** — created. No open WP owns the strategy: 1338 closed the
  gates, 1532 places rows, 1504 measures figures.
