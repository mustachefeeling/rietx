# WP-1980 — Every page as clean markdown, and an llms.txt

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1978 (the new tree)
Priority: P3 2026-10-16 — down a rung from P2: nothing can start until 1978's tree exists

## Goal

Every page of the new manual has a markdown twin an agent can read, with no MyST syntax left in
it, and the site serves an `llms.txt` that links those twins.

## Context

WP-1975 decided the agent layer (§ F8): an agent is served by the skill and by a clean markdown
copy of each page, never by front-page prose. The bars it adopted (§ F4): a page over 100 000
characters fails agent-score, and the `llms.txt` proposal asks for 50 000 or less. WP-1978's
page contract caps a page at 50 000.

**What exists, measured in the spike** (WP-1975 § I, § G5; sources in `docs/wp/1975-spike/`):
- Sphinx's own `_sources/*.md.txt` copies are the raw source. `{eq}`, `:::` and unexpanded
  `{{ }}` all reach the reader.
- sphinx-llms-txt 0.7.1 writes `llms.txt` and `llms-full.txt`, but links each page to those
  raw copies, and `llms-full.txt` is the sources concatenated. Its `llms_txt_uri_template`
  option can point the links elsewhere.
- sphinx-markdown-builder 0.6.11 gets closest. Math becomes `$$`, substitutions are expanded,
  and equation refs and citations become links. It loses four things:
  1. admonition labels (a note becomes plain text);
  2. sphinx-design card titles and links;
  3. the bibliography (an unknown `citation` node, which warns);
  4. the figure-pair markers (both the light and the dark image are emitted side by side).
- sphinx-llm 1.1.0 failed the old tree's `-W` on 21 nodes (WP-1975 § G5).

So the twin is a translator subclass over sphinx-markdown-builder for those four node types,
with sphinx-llms-txt pointed at its output. Keep only the light image of a pair, and write an
admonition as a labelled blockquote. Mermaid sources stay as fenced `mermaid` blocks.

## Non-goals

- An MCP server. The skill is the agent's entry point.
- The skill's own published copy at `/skill/rietx/` (unchanged).

## Tasks

- [ ] The translator: the four node types above, `-W` clean on the new tree.
- [ ] A test over the built twin: no `{`-role, `:::` or `{{` survives, every page has its H1
      and answer sentence, and no page passes 50 000 characters.
- [ ] `llms.txt` and `llms-full.txt` from sphinx-llms-txt, linking the twins; the summary
      sentence is the front page's answer sentence.
- [ ] Served beside each HTML page (decide `page.md` or `page.html.md` at the start), in every
      version WP-1979 deploys.
- [ ] Skill: one row in the skill's references saying where the twin and `llms.txt` live.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b markdown <new tree> <new tree>/_build/md
.venv/bin/python -m pytest tests/test_manual.py -k twin -n auto --dist loadgroup
```

## References

- llms.txt proposal. https://llmstxt.org

## Handover log

- **2026-10-16** — filed from WP-1975's slate. No open WP owns a markdown copy of the manual.
