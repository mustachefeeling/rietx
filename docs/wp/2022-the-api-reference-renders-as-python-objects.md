# WP-2022 — The API reference renders as Python objects

Milestone: unscheduled · Status: 🔄 2026-10-22 — claimed
Track: The repo's own process
Depends on: —
Priority: P3 2026-10-22 — a reader nobody is blocked on: the page is correct and hard to read

## Goal

The three API reference pages (`reference/api.md`, `api-techniques.md`, `api-types.md`) render
each name as a Sphinx Python-domain object: a highlighted signature broken one parameter a
line, a permalink, an "On this page" entry and a search-index entry, with a model's fields as
attributes carrying their type and default. The selection, the tiers and the signature text
stay exactly what the skill's `api.md` prints.

## Context

- The maintainer, 2026-10-22: rietx.org/docs/dev/reference/api.html "is very hard to read as it
  doesn't have syntax highlighting or structuring".
- Why: `docs/reference_pages.py:_api_entry` writes each name as a MyST definition list whose
  term is the whole signature in one inline code span, and a model's fields as one
  comma-joined run of code spans. To Sphinx that is text, so the theme has nothing to style.
- The fix is the standard one: the `py:function` / `py:method` / `py:class` /
  `py:exception` / `py:data` / `py:attribute` directives, which is what autodoc emits
  underneath. Sphinx parses the signature string into name, parameters, annotations and
  defaults (each its own CSS class, which pydata-sphinx-theme styles), and
  `python_maximum_signature_line_length` breaks a long one a parameter per line.
- **Not autodoc.** WP-1981 chose a generator over autodoc because autodoc renders whole
  docstrings, written in the rulebook register; writing the directives ourselves keeps that.
  **One source of signature text**: `docs/skill/make_api_index.py`'s `_signature`,
  `_doc_line` and its field builders, so the skill's index and the manual cannot differ.
- `-W` constraints: a name described twice is "duplicate object description", so a repeat
  carries `:no-index:`; nitpicky is off, so an annotation naming a type the domain does not
  describe stays plain text, while one it does describe becomes a link.
- **A model's fields are one `py:fields` directive, never a `py:attribute` each**
  (`docs/py_fields.py`). One attribute per field cost ~60 characters of fence and options and
  took `api-types.md` (102 models, 826 fields) from 38 163 to 79 932 characters, over the page
  contract's 50 000 cap (`tests/test_manual.py` `PAGE_CHAR_CAP`, which reads a generated body in
  place). `py:fields` reads one `name: annotation = default` a body line, MyST handing a
  directive only its first line as an argument, and renders them as one object's signatures:
  stacked, each anchored, the annotation linked, indexed as an `attribute` so `{py:attr}`
  resolves, and kept out of the page contents.
- The markdown twin (`docs/markdown_twin.py`, WP-1980) translates the same doctree.
  sphinx-markdown-builder knows the `desc` nodes, but not the `abbreviation` Sphinx wraps a
  bare `*` in (an unknown node, so `-W` fails), and it writes every signature as a heading,
  so `_normalise` writes the `*` as text and a `py:fields` block as a list of code spans.
- Tier: no rule, threshold or automatic action is added; presentation only.

## Non-goals

- Per-parameter descriptions (a numpy-style "Parameters" field list). The docstrings are prose
  and stay so; this WP changes how the existing text renders, not what it says.
- The old tree under `docs/manual/` (WP-1986 retires it).

## Tasks

- [x] Generator emits Python-domain directives; signature and field text from
  `make_api_index`'s own builders; repeats `:no-index:`; conf sets the signature line length
- [x] Tests: the generated body parses as directives and every signature equals the skill's;
  the manual builds `-W`; the twin reads cleanly
- [ ] Skill: none — the skill's `api.md` is unchanged byte for byte, and no agent-facing rule moves

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_reference_pages.py tests/test_manual.py tests/test_skill.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python docs/skill/make_api_index.py --check   # the skill's index unchanged
.venv/bin/python -m ruff check src tests examples
```

## References

- Sphinx, *The Python domain* (`py:function`, `python_maximum_signature_line_length`,
  `toc_object_entries`), sphinx-doc.org.

## Handover log

- **2026-10-22** — created. No open WP owns the API page's rendering: WP-1981, which wrote the
  generator, is closed, and WP-1986 moves Guides and Theory, not the Reference tab.
