# WP-1980 — Every page as clean markdown, and an llms.txt

Milestone: unscheduled · Status: ✅ 2026-10-17
Track: The repo's own process
Depends on: 1978 (the new tree)

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

So the twin is a translator subclass over sphinx-markdown-builder for those four node types.
Keep only the light image of a pair, and write an admonition as a labelled blockquote. Mermaid
sources stay as fenced `mermaid` blocks.

**Re-measured on the new tree, 2026-10-17** (the four losses still hold, and four more were
found). A baseline `-b markdown` build of `docs/docs/` warned on a `mermaid` node, a generic
`admonition` (its whole body dropped, not just the label), and sphinx-design's
`PassthroughTextElement` (the card titles). `theory/references` came out empty. Its tables
are padded to column width, which put two pages over the cap: `reference/diagnostics` at 51 511
characters and `reference/parameters` at 56 763. The `<!-- Generated … -->` comments of the
Reference bodies leaked into the text.

**What was built, and where it departs from the plan above.**
- The twin is written **inside the HTML build**, not by a second builder. `docs/markdown_twin.py`
  is a Sphinx extension in `docs/docs/conf.py`. On `doctree-resolved` it copies the resolved
  doctree, resolves its toctrees, rewrites the nodes the translator cannot write
  (`_normalise`) and translates the rest (`TwinTranslator`). So it reaches every version
  WP-1979 deploys with no workflow change (inherited from WP-1979, below), and no second build
  doubles the docs job.
- **`page.html.md`**, decided at the start: it is the llms.txt proposal's spelling. A link in
  a twin is the HTML page's own resolved link with `.md` appended.
- **No sphinx-llms-txt.** Its `llms-full.txt` is the raw `_sources` concatenated, which is the
  MyST this WP removes. Its `llms.txt` is one flat `## Docs` list of titles. `write_llms_txt`
  writes the proposal's shape from the twins instead: an H2 per tab and a line per page
  carrying its answer sentence, which the page contract guarantees. `llms-full.txt` is the
  twins in toctree order, links rebased to the build root.
- `docs/docs_versions.py` copies the hosted tree's `llms.txt` to the site root, its links
  rebased onto `/docs/stable/` (dev's until a release carries one).

**Carried from the inherited notes (2026-10-16/17, WPs 1978, 1979, 1981, 1983).** Each version
is one `docs/docs/` build, so a twin in the HTML output reaches every version (WP-1979). The
Reference pages' `{include}`d bodies and the Concepts tab's dropdown, mermaid chart and sliced
`{literalinclude}` all arrive resolved in the doctree, so the twin needed no expansion of its
own (WP-1981, WP-1983). The plan page's `\*` in mermaid sources is unescaped. The theme's
`_static/webpack-macros.html` is no page and has no twin (WP-1978).

## Non-goals

- An MCP server. The skill is the agent's entry point.
- The skill's own published copy at `/skill/rietx/` (unchanged).

## Tasks

- [x] The translator: the four node types above, `-W` clean on the new tree.
- [x] A test over the built twin: no `{`-role, `:::` or `{{` survives, every page has its H1
      and answer sentence, and no page passes 50 000 characters.
- [x] `llms.txt` and `llms-full.txt` ~~from sphinx-llms-txt~~ (written from the twins, see
      Context), linking the twins; the summary sentence is the front page's answer sentence.
- [x] Served beside each HTML page (decide `page.md` or `page.html.md` at the start), in every
      version WP-1979 deploys.
- [x] Skill: ~~one row in the skill's references~~ the body's last line, which already said
      where the manual lives, now says where `llms.txt` lives too (+42 B, body 16 986 of 17 000).

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -E -b html docs/docs docs/docs/_build   # writes page.html.md and llms.txt
.venv/bin/python -m pytest tests/test_manual.py tests/test_docs_versions.py -k "twin or llms or residue" -n auto --dist loadgroup
```

## References

- llms.txt proposal. https://llmstxt.org

## Handover log

- **2026-10-17** — An agent can now read any page of the new manual as clean markdown. Each
  page has a copy beside it, `page.html.md`, with no MyST syntax left in it, and the site
  root's `llms.txt` lists every page with its one-sentence answer. The copies are written
  by the HTML build itself, so every hosted version gets them and no deploy step was
  added. The node types the Theory and Guides chapters will bring are already handled and
  tested, so WP-1986's migration lands into a guard that exists. sphinx-llms-txt was
  measured and not used: its `llms-full.txt` is the raw MyST this WP removes.

  *Done.* `docs/markdown_twin.py`: a Sphinx extension in `docs/docs/conf.py`, translating
  the resolved doctree on `doctree-resolved` with a subclass of sphinx-markdown-builder
  0.6.11's translator (pinned `>=0.6.11,<0.7`, since it reaches private internals).
  `_normalise` rewrites cards, dropdowns, tabs, mermaid, citations, the dark half of an
  image pair, and HTML comments and icons. `TwinTranslator` writes admonitions as labelled
  blockquotes, tables unpadded, image paths into `_images/`, and links with `.md` appended.
  Section anchors are on, so the 290 cross-page `#fragment` links land. `llms.txt` and
  `llms-full.txt` come from `write_llms_txt`, and `docs_versions.assemble` copies the
  hosted tree's `llms.txt` to the site root with its links rebased. The skill body's
  manual line names `llms.txt` (+42 B; body 16 986 of 17 000).
  *Measured* (`[dev]`, darwin/arm64). The baseline `-b markdown` build of the new tree
  warned on three node types and put two Reference pages over 50 000 characters, from
  table padding (`reference/parameters` 56 763, now under the cap). The twins total about
  410 000 characters in `llms-full.txt`. Tests added: 10, in `tests/test_manual.py` and
  `tests/test_docs_versions.py`. Making `_normalise` a no-op turned all three twin tests
  red. The residue check's paired test caught one hole while it was being written: an
  inline-code strip that also removed a role's argument.
  *Review.* `/code-review high --fix` found 9 issues and fixed 6: section anchors, an
  author's acronym title recased, `llms.txt` summaries not rebased, a card's header and
  footer dropped, the `dirhtml`/`singlehtml` builders, and the distribution name spelt in
  a test. It declined the dependency ceiling, which was then added by hand. Two stay
  declined. The relative-link regex is written twice, because `docs_versions.py` runs in
  the deploy and should not import Sphinx. `_SENTENCE_END` splits on any stop before
  whitespace, matching the page contract's own split.
  *Reconciled with #1027* (WP-1996, the Switching-tab corrections). The two branches merge
  clean, and the merged tree passed the twin, contract, Switching-example and `-W` tests
  (26).
  *Gotchas.* A new node type with no handler fails `-W` as `unknown node type`, which is
  the intended alarm. `{download}` has a handler that no test has run.

  Next: nothing in this WP. WP-1986 inherits the twin contract and the coverage list.
- **2026-10-16** — filed from WP-1975's slate. No open WP owns a markdown copy of the manual.
