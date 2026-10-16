# WP-1980 — Every page as clean markdown, and an llms.txt

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1978 (the new tree)
Priority: P2 2026-10-16 — back to P2: WP-1978's tree is built (PR #1004)

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

### Inherited

- **2026-10-17, from WP-1983.** The Concepts tab adds three node types a twin must carry.
  `concepts/parameters.md` has a sphinx-design `{dropdown}` holding the evidence a fold
  away, `concepts/fit.md` a mermaid flowchart, and `concepts/usage.md` a `{literalinclude}`
  sliced by `:start-at:` and `:end-before:` from `examples/tutorials/02_simple_rietveld.py`.
  `tests/test_manual_api.py`'s `_included_slice` cuts such a slice the way Sphinx does and
  can be reused.
- **2026-10-16, from WP-1979 (closed).** Each version is one `docs/docs/` build. `main`'s is
  built into `site/docs/dev/` by pages.yml. A release's is built by release.yml's `docs` job
  and stored as a tarball on its GitHub release. `docs/docs_versions.py` lays them out under
  `/docs/`. So a twin written into the HTML build's output reaches every version with no
  deploy change. A twin built by a second builder needs a step in both workflows, inside the
  tarball. The `llms.txt` proposal puts the file at the site root, and today's root is the
  landing page. A root `llms.txt` would point at `/docs/stable/` (`dev/` before v1.10.0, as
  `/docs/index.html` does). Each version's own copy then sits under its directory.
- **2026-10-16, from WP-1981.** Ten Reference pages exist. Seven of them are a committed
  title and answer sentence followed by one `{include}` of a body that `conf.py` writes into
  the ignored `docs/docs/_generated/` (`docs/reference_pages.py`, `BODIES`). A markdown twin
  built from the sources must expand those includes, or it ships seven pages that are one
  line long. `tests/test_manual.py`'s `_as_rendered` already does that expansion for the
  page contract and can be reused. The plan page's diagrams are mermaid with
  backslash-escaped stars (`\*`), which a markdown twin should unescape.
- **2026-10-16, from WP-1978.** The new tree is `docs/docs/` (PR #1004). Its `conf.py` takes
  the fenced constants, the citation style, the mermaid theme and the `{source}` role from
  `docs/sphinx_shared.py`, which the old `conf.py` imports too. `tests/test_manual.py` builds
  it as the `built_docs_tree` fixture (xdist group `manual-build`), reads its pages as
  `DOCS_PAGES`, and holds each to the page contract (`_contract_breaches`). No
  `sphinx_llms_txt` extension is configured. `myst_heading_anchors = 3`. The theme ships a
  Jinja template into `_static/` (`webpack-macros.html`) that no page renders, and the
  built-HTML guards skip `_static/` for it, so a walk over a markdown build may meet the same
  file.

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
.venv/bin/python -m sphinx -W -q -b markdown docs/docs docs/docs/_build/md
.venv/bin/python -m pytest tests/test_manual.py -k twin -n auto --dist loadgroup
```

## References

- llms.txt proposal. https://llmstxt.org

## Handover log

- **2026-10-16** — filed from WP-1975's slate. No open WP owns a markdown copy of the manual.
