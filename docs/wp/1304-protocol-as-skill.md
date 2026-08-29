# WP-1304 — The protocol is a skill

Milestone: v1.3 · Status: ✅ 2026-08-29 — the tree, the caps, `rietx skill`, the
wheel copy, the manual chapter and every caller re-pointed
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
the one rule (one integration surface, a failure raises). **The API index is
generated, not written** (the review round, below): `docs/skill/make_api_index.py`
holds the selection as data and renders every signature, constructor field and default
from the installed package, and `tests/test_skill.py` pins the committed file to what
the generator renders. The body is 31.6 kB / 470 lines, and the headroom is thin enough
that 1305's fourth deliverable row should expect to pay for itself somewhere. The manual
is reached by URL (`https://rietx.org/using/<page>.html`), never by repository path: an
installed skill sits in a repository that has no `docs/`. There is no §9c — WP-1303 deleted it with
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
- [x] Sphinx pages + the pointer file.
- [x] The three consistency tests over the tree; the eval harness's fixture builder.
- [x] Docs, `CLAUDE.md` and `AGENTS.md` (`docs/AGENT_PROTOCOL.md` mentions → the skill;
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

### 2026-08-29 — review round: the plan re-read against the tree, six findings, all landed

The user asked for the implementation to be checked against the plan and the design
intent, this being a load-bearing WP. Held file by file against this WP's Shape and the
parked plan's WP-1304 section, and against what a fresh wheel install actually does,
rather than against the session's memory of it. Everything the first entry claims
holds, and the acceptance item it had *not* run — `rietx skill --path` from a fresh
venv install of a built wheel — was run: it resolves into `site-packages`,
`capabilities().skill_path` agrees, `--install` lands and links, `--print` prints.

Six gaps, in the order they mattered, each fixed on this branch:

1. **The API index was not the document the plan specified.** The plan asked for
   entry points *with signatures* and model objects *with their constructors*, no
   signature quoted by hand — rendered from `inspect.signature` or asserted equal to it.
   The first cut satisfied "none by hand" by quoting none: 4.1 kB of names. The
   campaign's errors were signature errors, which a name list cannot prevent. Now
   `docs/skill/make_api_index.py` holds the selection as data and renders every
   signature, pydantic field, dataclass field and default from the installed package,
   with its own annotation spelling so the file is identical on 3.11-3.14 where
   `inspect`'s is not; 92 entries, 27.7 kB against the 36 kB cap; pinned byte for byte
   by `test_skill.py`, which says how to regenerate.
2. **`api.md` claimed a guard that did not exist** — "every name here is checked by
   test" — while the test's regex reached `rx.X…` only, not the ~60 `.field` items.
   All were correct (checked by hand); the claim was the WP-1076 shape. The generated
   file makes it true by construction, and a second test walks the body's own
   `report.x` / `result.x` / `statistics.x` names through the types.
3. **The installed skill named documents no install has** — twelve `using/*.md`
   chapters and three repository files — under a `compatibility:` line saying every
   document it refers to ships in the wheel. The index table now maps each situation
   to its reference file *and* its manual page as `https://rietx.org/using/x.html`,
   See also names the repository as the repository, and one link still on the old
   host moved to `DOCS_URL`.
4. **`description` was three sentences, 638 chars**, against the plan's one sentence
   budgeted for Codex's 8 000-char catalogue. Now one sentence, 354.
5. **The milestone record had no 1304 entry** where 1301-1303 each have one.
6. **Minor**: a Claude Code tool name (`Read`) in a harness-neutral body; install
   symlinks absolute where `npx skills add` uses relative, so a moved project broke
   them; the wheel's 1.0-1.2 path `rietx/data/AGENT_PROTOCOL.md` simply gone where
   the transition clause wanted the pointer there for one release; rules 8 and 14
   with their explanation inside the numbered item rather than under it.

Body after the round: **31 593 B / 470 lines**. Fast selection **3411 → 3413 passed,
122 skipped at both ends** (`[dev]`, darwin/arm64, this worktree's venv, nothing else
running): exactly +2 for the two new tests. Acceptance selection 85 → 87; `sphinx -W`
clean with the rendered page checked; `ruff` clean.
The full suite is **not** re-run: the post-review commits touch the skill text, a
generator script, a symlink target and a force-include, none of which reaches a
measured number, and the rule is once on the final tree only when it could. The
3558 / 131 below stands for the numeric tree, which is unchanged.

### 2026-08-29 — shipped: the document is a directory, and the cap decided its shape

The operating protocol is an Agent Skill. `docs/skill/rietx/` holds a `SKILL.md`
an agent reads whole when the task calls for it and nine reference files it
loads only when it needs one; it ships in the wheel, is committed at
`.agents/skills/rietx/` and `.claude/skills/rietx/` so a session in this
repository loads it under any harness, installs into another repository with
`rietx skill --install`, and is published at `rietx.org/skill/rietx/SKILL.md`.
`docs/AGENT_PROTOCOL.md` is a ten-line pointer and goes in v1.4.

**The one thing to carry forward is what the cap did to the shape.** The WP's
Shape named five reference files and left everything else in the body. Written
as tightly as it goes, that body is ~39.5 kB — 23 % over its own 32 kB cap — so
four more things moved out, and choosing *which* is the rule worth keeping: **a
lookup leaves the body, a rule and its decisive number stay.** §6's 25-row
signal table went to `abstention.md` while its six rules stayed; §4/§4b's
long-form measured evidence went to `judging.md` while each step kept the
number that decides it; §5 went whole to `numbers.md`; and the API index went to
`api.md` behind a four-line pointer that keeps the one rule (one integration
surface, a failure raises). The body landed at 31 623 B / 475 lines, and the
375-byte headroom is thin enough that 1305's fourth deliverable row should
expect to pay for itself somewhere.

I do not think the cap is wrong. It is what makes the skill a *skill* rather
than the 144 kB document nobody loaded, and the split it forced is the same
progressive disclosure the format is built around. But it is not free, and the
next session to add to the body will meet it immediately.

**What landed.**

- **The split is verbatim.** Every non-separator line of the 1677-line source
  is in the tree byte for byte, verified by reconstruction; the only mechanical
  edit is heading level, fence-aware so a `#` python comment inside a code block
  is untouched. Section numbers are unchanged, which is what keeps every `§7d`
  and `§8.11` citation in `src/` resolving.
- **Spec-only frontmatter**, against the specification re-fetched today: `name`
  matching the directory and its character rules, `description` ≤ 1024,
  `compatibility` ≤ 500, `metadata` values as strings, and nothing outside the
  six fields (claude.ai's upload rejects a seventh; Codex caps the whole
  catalogue at 8 000 chars, which is why `description` is budgeted).
- **`rietx skill --path | --print [SECTION] | --install [DIR] | --list-agents`**,
  with `--user`, repeatable `--agent` and `--copy`. One real copy in
  `.agents/skills/`, symlinks from every harness that reads elsewhere, copies on
  Windows. The harness table is data — fifteen rows, each with the URL its
  directories came from and the date they were read.
- **`capabilities().skill_path`**, `SCHEMA_VERSION` 0.12 → 0.13. Additive, but
  that model's field list *is* the contract a client reads, so the string moves.
- **The manual chapter** is generated in `conf.py` like the glossary, not
  `{include}`d: the body's frontmatter is a contract with a harness and noise on
  a page, and the tree's relative links are correct for an agent and nine
  `myst.xref_missing` warnings under `-W`. File and section order are derived,
  so a new reference file renders in protocol order with no edit there.

**Two bugs the tests found, and one they found late.**

The API index resolves every dotted name against the installed package, and it
caught six names I had drafted from memory: `SeriesResult.trajectories`,
`SuggestionResult.candidates`, `RefinedParameter.esd`,
`Refinement.compare_rivals`, `Refinement.predict_then_verify`, `viz.plot`. The
protocol's own names were all correct — this was my draft, not its rot — but it
is exactly the WP-1037 shape and the reason the index is tested rather than
written.

The eval's excerpt extractor had two bugs on the naive port, both silent: it
matched `# 5. numbers, not pixels` inside `SKILL.md`'s worked-example code fence
and returned four lines of python comments, and it preferred the body's
condensed §6 rule list over the reference file holding §6's table, which would
have quietly *shortened* a registered condition's prompt. Fixed by searching the
reference files first and tracking fences. Verified against the pre-split
document at `6feda6f8`: §6 is byte-identical, §5 differs only by a dead relative
link the move had to repair. `PROTOCOL.md` carries a dated note rather than a
rewrite — a registered protocol is not edited after the fact — saying that a
round run after today does not pool with one before it on any row that turns on
what the agent could read.

`test_portability` caught `read_text('utf-8')` passing the encoding
positionally in `skill.read`. It works; the guard wants the keyword, and the
guard is why nothing in this tree reads under a platform default.

**Numbers** (`[dev]`, darwin/arm64, this worktree's own venv, machine otherwise idle).

- Fast selection **3378 → 3411 passed, 122 skipped at both ends**. Exactly +33,
  and 33 is what `--collect-only` counts in the two new files (20 in
  `test_skill.py`, 13 in `test_skill_cli.py`): no new skip, nothing else moved.
- Full suite, once, on this entry's final tree (`0c66671d`): **3558 passed /
  131 skipped in 24:03** — exactly +33 on WP-1303's 3525 / 131, machine
  otherwise idle.
- Sizes: `SKILL.md` 31 623 B / 475 lines against caps of 32 000 / 500; the
  largest reference is `diagnostics-indexing.md` at 30 824 B against 36 000.
  Whole tree 155 858 B across ten files, against the single document's 144 427 B
  — the ~8 % growth is the per-file blurb and back-link, and the point is that
  no *one* read is over 31 kB where the old one was 144.
- **The harness token count the acceptance asks for was not taken.** `/context`
  is a user-facing command this session cannot invoke, and I would rather record
  that than convert bytes to tokens with a ratio and call it a measurement. The
  byte counts above are what I measured; the check the number was for — does the
  body fit one Read — is answered by 31 623 B against the ~66 kB the tool
  returned on the old document.

**The install works end to end, observed rather than asserted.** Partway through
this session the harness running it listed `rietx` among its available skills,
sourced from `.claude/worktrees/wp1304-protocol-as-skill/.claude/skills` — the
committed copy `rietx skill --install . --copy` had just written. That is the
whole claim of the WP (a skill a harness finds without being told) happening to
the session that wrote it, and no test could have shown it.

**Next.**

**1305** adds the fourth deliverable, which means a row in §4b's table inside a
body with ~400 bytes of headroom (407 after the review round). **1306** and **1307** both build on the skill
being installable: 1307's round 1.2 wanted a behavioural test on a second
harness, which `rietx skill --install` now makes a one-line episode change.

- **2026-08-28** — created, from the parked v1.3 plan.
