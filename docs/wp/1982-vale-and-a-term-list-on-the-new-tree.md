# WP-1982 — Vale and a term list on the new tree

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1978 (the new tree)
Priority: P2 2026-10-16 — back to P2: WP-1978's tree is built (PR #1004)

## Goal

Vale runs in CI over the new manual's sources with Microsoft's package as the base. A term list
names one word per concept and is the accept list. The maintainer's banned words are the reject
list. Where Microsoft and the repo disagree, the repo's rule is configured in.

## Context

WP-1975 decided four style layers, the first winning (§ F8):
1. the repo's own rules, including the register guard (no em dash, no bold in prose);
2. a term list, one term per concept, with `help.py`'s names the authority and IUCr notation
   conventions added;
3. **Microsoft's Writing Style Guide** as the base, chosen for directness. Take contractions
   and short sentences; leave its marketing warmth and fragments;
4. Vale with the Microsoft package on the new tree, the term list as its accept list and the
   maintainer's banned words as its reject list.

**Measured in the spike** (WP-1975 § I, Vale 3.24.0; config in `docs/wp/1975-spike/vale/`):
- A `:::` colon-fenced admonition is linted. A backtick-fenced one is skipped like code and
  math. WP-1978 writes admonitions with `:::` for this reason.
- Out of the box: 26 alerts on three short pages. They were mostly vocabulary or misfires.
  `Microsoft.Terms` rewrote "agent" to "personal digital assistant", `Microsoft.Vocab` flagged
  "sample", and spelling flagged rietx, Rietveld, Pawley, TOPAS, GSAS and microstrain.
- With a nine-word accept list and `Microsoft.Terms`, `Microsoft.Vocab` and
  `Microsoft.OxfordComma` off: six alerts, all fair style suggestions (two passives, a
  semicolon, an adverb).
- **Two Microsoft rules contradict the house style**, which wins under layer 1. Microsoft
  wants the Oxford comma; the repo writes without it. Vale's spelling is US English; the
  house style is British. So `OxfordComma` is off and Vale needs an en_GB dictionary.

The banned words are the maintainer's: "simply", "just", "easy", "it's important to note",
and marketing adjectives (the `yue-docs-style` skill's list). Read the current list from that
skill at the start rather than from this line.

### Inherited

- **2026-10-16, from WP-1981.** The register guard reads committed sources, so the
  Reference tab's generated bodies in `docs/docs/_generated/` are not checked by it. That
  was deliberate: their prose is the package's own text (`rietx.help` descriptions,
  `PLAN_INFO`, docstring first lines), which carries em dashes and bold, and some API
  summary lines name WP numbers ("WP-0501 (cylinder)" on `AbsorptionCorrection`). Decide
  whether Vale reads the generated bodies. If it does, the fixes land in the package's
  strings, not in the pages.
- **2026-10-16, from WP-1978.** The new tree is `docs/docs/` (PR #1004). Its `conf.py` takes
  the fenced constants, the citation style, the mermaid theme and the `{source}` role from
  `docs/sphinx_shared.py`, which the old `conf.py` imports too. `tests/test_manual.py` builds
  it as the `built_docs_tree` fixture (xdist group `manual-build`), reads its pages as
  `DOCS_PAGES`, and holds each to the page contract (`_contract_breaches`). Point Vale at
  `docs/docs/`; `_build/` sits inside it and is gitignored. The stubs use no admonitions yet.

## Non-goals

- The old tree. It is exempt until each chapter retires (WP-1986).
- Report and diagnostic text (WP-1985 takes the same guide by hand).

## Tasks

- [ ] `.vale.ini` and the vocabulary in the repo, the Microsoft package pinned by version.
- [ ] The term list: generated from `help.py`'s labels and titles plus a hand-kept IUCr
      file; one concept, one term, with the rejected synonyms on the reject side.
- [ ] en_GB spelling, `OxfordComma` off, `Terms`/`Vocab` reviewed rule by rule against this
      domain rather than switched off wholesale.
- [ ] A CI step over the new tree, failing on errors and reporting warnings; decide the
      level at which it fails from a run over the pages that exist then.
- [ ] Skill: none.

## Acceptance

```sh
vale --config=.vale.ini docs/docs      # no error-level alert
```

## References

- Microsoft Writing Style Guide. https://learn.microsoft.com/style-guide/
- Vale. https://vale.sh (errata-ai/vale), package errata-ai/Microsoft.

## Handover log

- **2026-10-16** — filed from WP-1975's slate. No open WP owns prose linting.
