# WP-1304 — The protocol is a skill

Milestone: v1.3 · Status: ⬜
Depends on: 1303 (§9c and the envelope rows go with it)

## Goal

The agent-facing document is a skill directory in the open Agent Skills format: one
`SKILL.md` an agent reads whole in one call, reference files loaded when a task calls
for them; it ships in the wheel, is committed where every harness finds it, is published
on the site, installs into another repo with one verb, and the consistency tests cover
the whole tree.

## Context

- **The document never loaded.** `docs/AGENT_PROTOCOL.md` is 146 656 B (1755 lines, 36 k
  tokens), 2.2× the Read tool's ~66 kB cap: the ramp agent got lines 1-707, then a
  `grep` for a TOC and three `sed` ranges, one of which exceeded Bash's 40 kB output cap
  and came back as a 2 kB preview. So §7 (the 99-row diagnostics table), §7b-7f and §9
  were never in context, and loading the protocol cost 5 roundtrips. Across a
  contributor's 86-run campaign (2026-08): 2 Reads of the protocol (both by agents
  editing it, one truncated at line 792), 40 Reads of `CLAUDE.md`, 0 uses of `help_for`
  or `capabilities()`. Its "See also" does not link the Part 1 manual; the agent found
  `using/series.md` by `ls`; `using/agents.md`, written for this reader, was never
  opened.
- **Two readers, one text.** In that campaign the workers never opened the protocol;
  their briefs restated its rules (71 references to the brief, 0 to the document), and
  the coordinator briefed from `CLAUDE.md`, the file its own session had in context. When
  it needed the API it spawned three "explore the library" runs (114 calls) to write an
  API reference from source; one asserted "everything public is re-exported from the
  top-level package", which is false, and three later runs paid for it. So the skill's
  reader is either a cold agent that loads it or an orchestrator that distils it into a
  brief, and both are served by one property: the judgement core is a **numbered list of
  rules short enough to copy into a brief** (the three stop conditions, the abstention
  rules, the "would not quote" list's shape, the four deliverables' deciding rows), with
  the explanation under each rule and not in it. The API index is the document the
  explore runs were trying to write, so it carries what theirs carried (entry points with
  signatures, the model objects and their constructors, the result's shape, the series
  entry, the report) and is tested.
- **The format is an open standard, not a Claude feature** (researched 2026-08-28;
  the per-harness table with URLs is the maintainer's memory
  `harness-skill-support-2026-08`; re-verify before quoting). agentskills.io, Apache-2.0
  / CC-BY-4.0: `name` and `description` required, `license`, `compatibility`,
  `metadata`, experimental `allowed-tools`; `SKILL.md` under 500 lines, `description` ≤
  1024 chars. Read natively with progressive disclosure by Claude Code, Codex, Cursor,
  Copilot, Gemini CLI, opencode, Goose, Cline, Amp, Kiro, Devin, Zed, Junie, Qwen Code,
  OpenHands, Hermes, Mistral Vibe (~45 listed clients); open-weight models are served by
  the skills-aware harnesses (opencode, Cline, Goose, OpenHands, Qwen Code, Hermes run
  Ollama/llama.cpp models); a custom loop uses the spec's `skills-ref` Python reference
  (`to_prompt`) or the plain text. Aider is the one Markdown-only holdout (`aider --read
  <path>`). What differs is the directory: the spec recommends `.agents/skills/` +
  `~/.agents/skills/` and most harnesses scan it; Claude Code scans `.claude/skills/`
  only; Cline, Kiro, Qwen Code, Junie, Devin add a native dir each. `AGENTS.md`
  (Agentic AI Foundation) is for a repo's own instructions and Claude Code does not read
  it; `llms.txt` is effectively unread (97 % of published files got zero requests in May
  2026, Ahrefs, 137 k domains); MCP prompts/resources reach Claude Code, Gemini CLI and
  VS Code only, Codex takes tools plus 512 chars of `instructions`, the OpenAI and Gemini
  APIs tools only. A pip extra can add a dependency and never write a file, so no
  harness extra exists. Precedent for a library: Laravel Boost (packages ship
  `skills/<name>/SKILL.md`; one verb installs into six harnesses), fastmcp `install
  <harness>`, `npx skills add` (canonical `.agents/skills/` + symlinks, 77 agents), `gh
  skill install`.

### Shape

Canonical `docs/skill/rietx/`: `SKILL.md` (frontmatter `name: rietx`, `description:` one
sentence naming the trigger, `license: MIT`, `compatibility`, `metadata: {version:
<package version>}`, nothing Claude-only; body: §1-3 condensed, §4 judging and the three
stop conditions as a numbered rule list, §4b deliverables (1305 adds the fourth), §6
abstention, §10 worked default printing `d.suggestion`, the tested API index, an index
table "task → manual chapter / reference file", and a See-also linking
`using/quickstart.md`, `using/series.md`, `using/report.md`, `using/history.md` and naming
`rx.help_for` and `capabilities()`); `references/diagnostics.md` (§7's 99 "must not do"
rows, complementary to the runtime `suggestion`, not the same text),
`references/diagnostics-indexing.md` (§7b-7f), `references/surprises.md` (§8),
`references/history.md` (§9), `references/series.md` (§9b). **Four more reference files
than that list, all forced by the same cap** (measured 2026-08-29): the material this
Shape puts in the body is ~39.5 kB written as tightly as it can be, so what does not fit
is the part that is a *lookup* rather than a rule. §5 → `references/numbers.md`; §6's
25-row signal table → `references/abstention.md` (its rules stay in the body); §4/§4b's
long-form measured evidence → `references/judging.md` (each rule keeps its decisive
number); the API index → `references/api.md`, reached by a four-line pointer that keeps
the one rule (one integration surface, a failure raises). The body is 31.6 kB / 475
lines, and the headroom is thin enough that 1305's fourth deliverable row should expect
to pay for itself somewhere. There is no §9c — WP-1303 deleted it with
`rietx.agent`, so the skill must not expect the envelope's request/response vocabulary;
the one rule that survived (engine `Diagnostic` codes against the GUI server's session
codes, two vocabularies sharing an UPPER_SNAKE shape) is in **§7's preamble** and the
skill quotes it from there. Caps pinned by test with the
numbers in the comment: `SKILL.md` ≤ 32 kB and < 500 lines (Read returned 66 kB; the
spec's limit; a skill body is read whole), every reference ≤ 36 kB (Bash output above
40 kB becomes a 2 kB preview). Committed copies at `.agents/skills/rietx/` and
`.claude/skills/rietx/`, pinned byte-equal to the canonical tree by test, so a session
in this repo loads it under any harness; the wheel ships `rietx/data/skill/` (replaces
the force-included `AGENT_PROTOCOL.md` in `pyproject.toml`); `capabilities()` gains
`skill_path` (contract bump); `CLAUDE.md`'s and `AGENTS.md`'s first paragraphs name it.

**`rietx skill`.** `--path` prints the wheel's copy; `--print [section]` prints text for
a harness with no skill support (Aider's `--read`, a custom loop's system prompt);
`--install [DIR] [--user] [--agent NAME …] [--copy]` writes the canonical copy to
`<DIR>/.agents/skills/rietx/` and symlinks (copies with `--copy`, and always on Windows)
into each requested native dir, default `.claude`; `--user` targets `~/.agents/skills` +
`~/.claude/skills`. The harness → directory table is **data** in `cli.py`, one URL and
date per row. `--install` prints, never writes, the two-line `AGENTS.md` / `CLAUDE.md`
snippet naming the skill: the user's `AGENTS.md` is theirs. `description` is budgeted:
Codex caps the whole skill catalogue at 8 000 chars.

**Transition.** `docs/AGENT_PROTOCOL.md` stays for one release as a ten-line pointer
(external links, the site URL, the wheel's old path), deleted in v1.4. Sphinx: Part 1
gets a "For agents" page that `{include}`s `SKILL.md` and the references
(`tests/test_manual.py` builds them `-W`). MCP stays v2; when it lands, its
`instructions` string is the skill's `description` and the body a resource for the
harnesses that read one.

**Tests to move** (at 79e5ae82): `tests/test_docs_consistency.py:748-815`
(`_protocol_text()` → the concatenation of every `.md` under the skill tree; the three
assertions unchanged); `tests/test_gui_dist.py:282,341`;
`tests/eval_report_agent/python_arm.py` + `build_fixtures._section()` (ship the
directory; byte equality per file); citations in `test_report_loop.py:12,802`,
`test_extinction_symbol.py:693`, `test_robustness_external.py:523` re-pointed by section
name.

## Non-goals

Generating §7 from the `Diagnostic(` constructors (needs a code registry; ~100 sites; a
later WP if the two texts drift). Per-harness renderings of the skill (one format covers
every harness found). A rietx harness of its own (v2+; the skill text and the Python
API are what it would consume). Writing into a user's `AGENTS.md`. A behavioural test on
a second harness (WP-1307 round 1.2's, once `rietx skill --install` makes it a one-line
episode change).

## Tasks

- [x] The split, mechanical: move sections into the files, no rewriting; caps test.
- [x] Rewrite `SKILL.md` to budget (the only authored change: condensation as a numbered
      rule list, the tested API index with every dotted name resolving and every `rx.X`
      in `__all__`, no signature quoted by hand, the `suggestion` line in §10, the links).
- [x] Spec-only frontmatter + its test (field set equals the spec's; `description` ≤
      1024 chars; `SKILL.md` < 500 lines).
- [x] Wheel copy + `rietx skill --path | --print | --install` with the harness table as
      data + `capabilities().skill_path`; `--install` into a temp dir passes a spec
      validator (`skills-ref` as a dev dependency, or the check re-implemented in twenty
      lines if it stays "demonstration only").
- [x] The two committed copies + the byte-equality test.
- [ ] Sphinx pages + the pointer file.
- [ ] The three consistency tests over the tree; the eval harness's fixture builder.
- [ ] Docs, `CLAUDE.md` and `AGENTS.md` (`docs/AGENT_PROTOCOL.md` mentions → the skill;
      `using/cli.md` gets the one sentence on why there is no `rietx[<harness>]` extra).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_gui_dist.py tests/test_manual.py tests/test_manual_api.py tests/test_skill.py tests/test_skill_cli.py -n auto --dist loadgroup
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m ruff check src tests examples
```

(`tests/test_cli.py`, which this line named when the WP was written, does not exist and
never did: the CLI's only coverage was `test_events_viz_history.py::test_cli_help_and_html`.
The skill's own CLI is `tests/test_skill_cli.py`, named for what it covers.)

`rietx skill --path` resolves from a fresh venv install; `rietx skill --install` into a
temp dir lands in both directories and validates. A token count of `SKILL.md` measured
with the harness (`/context` before and after a Read) recorded in the handover, never
asserted.

## References

- Agent Skills specification, https://agentskills.io/specification (Anthropic-originated,
  open; `skills-ref` at github.com/agentskills/agentskills).
- Anthropic agent-design guidance: skills as progressive disclosure.
- WP-1003 (the protocol in the wheel), WP-1110 (the surface round), WP-1202 (`help.py`).

## Handover log

- **2026-08-28** — created, from the parked v1.3 plan.
