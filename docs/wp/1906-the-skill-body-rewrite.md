# WP-1906 — the skill body rewrite: under 5 000 tokens, rules first, evidence in the references, the contradictions resolved

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1905 (the before-and-after it is judged by); 1532 soft (its fourteen rows land on the rewritten body)
Priority: P2 2026-10-06 — 1905 measured the baseline, and on Haiku the body steers every from-scratch fit to a degenerate route; every session that loads the skill pays its 8 700 tokens

## Goal

`SKILL.md`'s body is at or under `SKILL_BUDGET_BYTES` (17 000 B, the
specification's 5 000 tokens), every rule it carried still holds, the
contradictions WP-1904's audit listed are resolved by stating the condition
each side holds under, and WP-1905's suite shows no case losing against the
current body on Haiku or Sonnet, at fewer input tokens per run.

## Context

WP-1904's audit (`docs/wp/1904-eval/audit.md`) is the work list; this file
restates what decides the design.

- **Where the bytes go.** The body below the frontmatter is 29 687 B, about
  8 700 tokens measured on Haiku (WP-1904). By paragraph class: actionable
  rules 43 %, evidence 23 %, rhetoric and framing 12 %, routing and headings
  15 %, code 7 %. About 8.2 kB of it is restated in `judging.md`,
  `abstention.md` and `surprises.md` (the audit's § D table, rule by rule).
  Evidence plus rhetoric is about 10.4 kB against a 12.7 kB overage, so the
  budget is reachable without losing a rule.
- **Why the budget is a cliff and not a preference.** Claude Code keeps only
  a skill's first 5 000 tokens after context compaction. On the current body
  that cut falls at line 232 of 439: § 4b (the deliverable table), § 6
  (abstention) and § 10 (the worked default) are what a long session loses.
  So the rewrite orders each section by stakes, and the whole body by what a
  session that has already fit once still needs.
- **The contradictions to resolve** (the audit's § B, each with line numbers):
  Le Bail first against "a known structure is no Le Bail job"; the worked
  default breaking its own rules 4 and 5 (a string plan cannot set
  `lebail_passes`, and the background is never seeded); "not negotiable"
  against "a default"; the width seed `W ≈ (FWHM/2)²` against the package's
  own `Γ_G² = U·tan²θ + V·tanθ + W` (so W ≈ FWHM² at low angle, which is also
  what the body's own `W = 1e-3 → FWHM ≈ 0.03°` implies); stop condition 26's
  raw ΔBIC against § 4's N/f²; a 0.5 % cell move called implausible beside a
  1 % starting tolerance; an `ambiguous` verdict that is no field value.
  Each is resolved by writing the condition, checked against the installed
  package, not by picking a side.
- **Structure.** § 5, 7, 8 and 9 exist only as reference-file titles while the
  routing table cites them as body sections; rule 23 is missing; `api.md` is
  routed four times. Reference headings cite the body's rule numbers ("§2
  rules 4-5", "§3 rule 8", "Step 9…17"), so a renumbering edits those
  headings in the same change, and `test_the_body_carries_the_judgement_core`
  pins the seven `## N.` anchors and the phrase "stop condition".
- **Style, from the sources WP-1904 collected.** Imperative; one rule per
  row: the action, the API name, the one-clause reason where the reason
  changes what the agent does. State the positive action where one exists
  and keep a genuine prohibition as one. No intensifiers, no "X is not Y; it
  is Z", no appeal to an unnamed measurement: a reason is a link to the
  reference row that holds the number. Anthropic's current guidance is that
  Claude 4.5+ over-triggers on emphatic language, and the skill-creator
  guide's yellow flag is an ALL-CAPS MUST. "Neuralese" was considered and
  declined: the measured compression results (LLMLingua, telegraphic
  rewrites) test fact retention, not rule compliance, and a terse rule the
  maintainer cannot review is a rule nobody can audit. Tables and short rows
  are the compression; the words stay English.
- **The gaps at fit time** (the audit's § E): a first-call sequence that
  holds together, the plan by data type, instrument setup from a `.prm`, the
  width seed as a parameter path, multi-phase setup, how to read
  `print(result)`, what to do when `max_shift_over_esd` is large, the
  `vary=False` hold trap, the fit range. Each takes the cheapest place that
  holds it (CONTRIBUTING.md § The agent skill): a `help.py` entry or a
  `Diagnostic.suggestion` first, a reference row keyed by a name second, the
  body only for what every fit needs, paid for by a cut.
- **The prototype.** WP-1904 had a compressed body drafted under these rules
  and ran it through `tests/test_skill.py` and the suite's two cases; its
  handover says what it scored and what it lost. The prototype is a
  measurement of the direction, not the rewrite: it is in
  `docs/wp/1904-eval/SKILL.compressed.txt` to be read, not copied.

### Inherited

- **From WP-1904 (2026-10-04), the prototype's numbers.** The prototype
  body (`docs/wp/1904-eval/SKILL.compressed.txt`) is 16 401 B and 5 297
  tokens on Haiku against 8 683; `tests/test_skill.py` (137 tests) passed
  with it in place. On Sonnet at N = 2 it lost nothing on `fap-judge`
  (a ceiling there) and produced the only completed with-skill `fap-fit`
  cell of either body under the pilot's CPU contention, so the direction is
  not refuted and not yet shown: 1905's serial round is the measurement.
  Two of its choices need a decision here: its worked default converges
  `usable` over 15-90° and ends `max_iter` over the whole 15-130° range, so
  the example states its range or the plan changes; and it uses a Chebyshev
  background because the P-spline default fired about 778 `HIGH_CORRELATION`
  findings between spline coefficients in its author's run, which is a
  package question (dedup or a different pairing rule) before it is a skill
  one. Both prototype-driven Sonnet runs followed its worked default line
  for line, so what the example says is what an agent does.
- **From WP-1905 (2026-10-04), the suite this rewrite is judged by.** A
  candidate is measured as `tests/eval_skill/build.py docs/skill/rietx <out>
  --body <file>`, run `--ablation none` beside today's body's two-arm round,
  and read with `tests/eval_skill/readout.py compare`; the rule is
  `tests/eval_skill/PROTOCOL.md` § The decision rule. Two things change how
  the pilot's numbers above read. The harness's own score is not comparable
  across ablation modes (the same `fap-fit` state scored 1 of 7 two-arm and
  2 of 8 one-arm), so the pilot's current-against-prototype Sonnet scores set
  a 7-weight score against an 8-weight one; `readout.py` rescores both on the
  same graders. And `fap-fit`'s cell windows are now measured and ask for
  value(esd), because the CIF's starting cell sat inside the pilot's windows:
  the pilot's Haiku with-skill pass was on starting values.
- **From WP-1905 (2026-10-06), the baseline.** Today's body was measured on
  Haiku and Sonnet at N = 3 (`tests/eval_skill/PROTOCOL.md` § Results; result
  files in `docs/wp/1905-eval/round1/`). Compare a candidate's with-skill
  arm against `B2.json` and `B.json`'s `fap-judge` rows on Haiku, and against
  `C.json` on Sonnet. Five things bear on the rewrite.
  - **Haiku's `fap-fit` is the deciding case.** All three with-skill runs
    freed zero and displacement together and reported a = 9.3683(16) Å,
    c = 6.8833(12) Å, outside the window. All three without the skill landed
    inside it. The body's worked default is what Haiku follows, as the
    prototype's Sonnet runs showed (above).
  - **On Sonnet today's body passes every case 3 of 3**, so there the rewrite
    can only be checked for regressions.
  - **The no-skill arm is not skill-free on Sonnet.** It found the wheel's
    copy (`rietx skill`, site-packages) in four of six fit-case runs. The
    decision rule never reads that arm, but a case's role does.
  - **Tier 0 found one over-trigger**: Sonnet loads the skill to convert a
    CIF to POSCAR, three runs of three, which the description's "before
    drawing a crystal structure from a CIF" invites. Haiku's four misses are
    tier 0's absent fixtures, not the description.
  - A build for a round needs `--venv DIR` outside `/Users`, `/tmp` and the
    plugin root on macOS (PROTOCOL § Prerequisites).

## Non-goals

- New physics or new rules: a rule enters the body only from a measured
  failure, with its row in a reference.
- The references' own prose, except the headings that cite body rule
  numbers and the rows that take evidence moved out of the body.
- The description's wording: tier 0 of WP-1905 measures it, and a change to
  it is its own commit with the trigger-set numbers.

## Tasks

- [ ] Resolve the audit's § B contradictions, each as one condition clause
      checked on the package, and fix the width formula
- [ ] Move the § D duplicates out: a link per rule to the row that holds the
      evidence; cut the rhetoric classes the audit lists
- [ ] Re-order: § 1-4 by stakes, the worked default and the stop conditions
      inside the first 5 000 tokens; fix § numbering and rule 23; the
      reference headings that cite rule numbers
- [ ] The worked default runs as written (`examples/` holds it, the manual
      `{literalinclude}`s it, `tests/test_examples.py` runs it)
- [ ] The § E gaps: each placed by the placement rule or declined with a
      reason, row by row in the handover
- [ ] WP-1905's suite: the rewritten body against the current one, N = 3,
      Haiku and Sonnet, tokens per run beside the score; the decision rule
      applied and recorded
- [ ] `rietx skill --install . --copy`; `tests/test_skill.py` green; the
      budget met without raising a cap
- [ ] Skill: this WP is the skill change

## Acceptance

```sh
.venv/bin/python -m tests.skill_caps          # SKILL.md: 0 over its budget
.venv/bin/python -m pytest tests/test_skill.py tests/test_skill_cli.py tests/test_docs_consistency.py tests/test_examples.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1904's audit and prototype, `docs/wp/1904-eval/`.
- agentskills.io specification (body < 5 000 tokens, < 500 lines) and its
  best-practices page ("add what the agent lacks, omit what it knows");
  Anthropic skill-authoring best practices; Claude Code skills docs (the
  5 000-token compaction keep).
- McCusker et al. (1999) *J. Appl. Cryst.* **32**, 36; Toby (2024) *J. Appl.
  Cryst.* **57**, 175 — the two sources the body's protocol rests on.

## Handover log

- **2026-10-04** — created by WP-1904's session. No open WP owns the body's
  size or its contradictions: 1338 closed with the budget ratchet, and 1532
  places fourteen rows but rewrites nothing. Next: wait for 1905's first
  round, then start from the audit's § B.
