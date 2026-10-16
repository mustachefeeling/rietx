# WP-1982 — Vale and a term list on the new tree

Milestone: unscheduled · Status: ✅ 2026-10-16 — Vale gates the new tree in CI, 0 errors over 18 pages
Track: The repo's own process
Depends on: 1978 (the new tree)

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

**The maintainer's six style rules** (WP-1981's review, 2026-10-16, now in `yue-docs-style`).
Their checkable halves belong in this WP's Vale rules and term list:
1. A heading makes sense read alone, in the sidebar, the contents list and search results.
   "The four answers are four different types" fails ("which four?"), and so do the bare
   "In" and "Out" the skill's API index used (both renamed in WP-1981). A heading with a
   finite verb is the cheap proxy for a claim heading; a one-word heading is the proxy for a
   bare one. Neither proxy is the rule, so flag, never fail.
2. The crystallographer's term leads: "lattice parameter" over "cell edge" and "cell angle".
3. No programming concept before it is explained or linked: "glob", "dot-path", "schema",
   "column". "fnmatch" never appears in reader prose.
4. Where rietx models something differently from GSAS-II, TOPAS or FullProf, the page names
   the familiar form. Not checkable by Vale; review only.
5. Notation is rendered: no `μ_B` or `x^2` as text.
6. No economic metaphor for an effect ("buy", "pays for") and no "caller", "client" or
   "intruder" in reader prose.

The `rietx.help` corpus breaks rules 2, 3 and 6 in places, measured 2026-10-16 over its 159
entries: "caller" 3, "glob" 3, "fnmatch" 1, "column" 6. Its rewrite is WP-1985's.

**The generated Reference bodies** (`docs/docs/_generated/`, WP-1981) are the package's own
text: `rietx.help` descriptions, `PLAN_INFO`, docstring first lines. The register guard reads
committed sources only, so it does not see them, and they carry em dashes and bold. This WP
decides whether Vale reads them. If it does, the fixes land in the package's strings, never in
the pages.

**The tree** is `docs/docs/` (WP-1978, PR #1004). `tests/test_manual.py` builds it as the
`built_docs_tree` fixture and reads its pages as `DOCS_PAGES`. `_build/` sits inside it and is
gitignored. The stubs use no admonitions yet.

## Non-goals

- The old tree. It is exempt until each chapter retires (WP-1986).
- Report and diagnostic text (WP-1985 takes the same guide by hand).

## Tasks

- [x] `.vale.ini` and the vocabulary in the repo, the Microsoft package pinned by version.
      v0.15.1, by the release URL `vale sync` reads; the synced copy is gitignored.
- [x] The term list: generated from `help.py`'s labels and titles plus a hand-kept IUCr
      file; one concept, one term, with the rejected synonyms on the reject side.
      `docs/vale/terms.py` writes the accept list from `rietx.help` and
      `docs/vale/terms.txt`; `docs/vale/rietx/Terms.yml` is the reject side;
      `tests/test_vale.py` holds both.
- [x] en_GB spelling, `OxfordComma` off, `Terms`/`Vocab` reviewed rule by rule against this
      domain rather than switched off wholesale. `Quotes` and `HeadingColons` are off too
      (British usage), and `Contractions` is a suggestion: welcome, never required.
- [x] The checkable halves of the six style rules above, as `rietx.*` Vale rules: rule 1
      as `Headings` (a one-word section heading, suggestion), 2 in `Terms`, 3 as
      `Programming` (suggestion) and `Fnmatch` (error), 5 as `Notation`, 6 as `Metaphor`
      and `Roles` (warnings). Rule 4 is review only.
- [x] Decide whether Vale reads the generated Reference bodies, from a measured run.
      Not yet: 107 errors over their 20 915 words (55 spellings, 46 em dashes), all in the
      package's strings. `.vale.ini`'s section skips `_generated/`, and WP-1985 widens it.
- [x] A CI step over the new tree, failing on errors and reporting warnings; decide the
      level at which it fails from a run over the pages that exist then. The lint job, so
      a draft runs it. It fails on an error and prints warnings: 0 and 5 over 18 pages.
- [x] Skill: none. Vale reads the manual, which no agent driving rietx edits.

## Acceptance

```sh
vale --config=.vale.ini docs/docs      # no error-level alert
```

## References

- Microsoft Writing Style Guide. https://learn.microsoft.com/style-guide/
- Vale. https://vale.sh (errata-ai/vale), package errata-ai/Microsoft.

## Handover log

- **2026-10-16** — closed. The new manual now has a prose linter that fails CI on a decided
  rule. Vale reads every committed page of `docs/docs/` with British spelling, Microsoft's
  style guide as the base and the maintainer's rules on top. Spelling against the British
  dictionary and a crystallographer's term list, the banned words and "fnmatch" in prose are
  errors. A rejected synonym, notation left as text, "caller" and an economic metaphor are
  warnings, printed for whoever edits the page. The 18 pages that exist pass with 0 errors
  and 5 warnings. The generated Reference bodies are left out on purpose: their 107 errors
  are the package's own strings, which WP-1985 rewrites. The maintainer chose "esd" over the
  IUCr's "standard uncertainty", and GSAS-II writes "esd" too.

  *Done.* `.vale.ini` at the root, styles under `docs/vale/`: the Microsoft package pinned at
  v0.15.1 by the release URL `vale sync` reads (synced copy gitignored); `rietx.Spelling` on
  the en_GB-ise SCOWL dictionary, committed with its licence and an ATTRIBUTION.md row;
  `rietx.Terms` (the repo's synonyms plus Microsoft.Terms less six stated entries) and
  `rietx.Vocab` (Microsoft.Vocab less sample, against, above, author, alias, beta);
  `rietx.Banned`, `Fnmatch`, `Notation`, `Metaphor`, `Roles`, `Programming`, `Headings` for
  the six review rules (rule 4 is review only). Microsoft's OxfordComma, Quotes and
  HeadingColons are off and Contractions is a suggestion, each with its reason in
  `.vale.ini`. The term list: `docs/vale/terms.py` writes the accept list from
  `rietx.help`'s titles and labels (words the dictionary lacks; it took TOF, DIFC, DIFA,
  DIFB, TZERO, bkg) and the hand-kept `docs/vale/terms.txt` (259 words), and
  `tests/test_vale.py` holds it equal and checks no term is both accepted and rejected.
  CI: a step in the lint job fetches Vale 3.24.0 by version and SHA-256 and runs at
  warning level, so a draft runs it. `CONTRIBUTING.md` says how to run it. The two real
  hits on `foreign-names.md` are fixed ("Polarization", "cell edge").

  *Measured* (Vale 3.24.0, macOS arm64; CI's Linux run gave the same 0 errors and 5
  warnings over 18 files). Out of the box the new tree drew 58 alerts and the old manual
  7 848, 1 839 of them spelling. Configured: the new tree 0 errors, 5 warnings, 25
  suggestions; the generated bodies (20 915 words) 107 errors (55 spelling, 46 em dashes),
  82 warnings; the old manual 463 errors (417 spelling, 14 banned, 8 fnmatch), 458 warnings
  (101 notation, 62 roles, 36 terms, 35 metaphors). Vale exits 1 on a probe page with
  "just" and "color". Fast suite, `[dev]` venv, macOS arm64, alone on the machine: 10 676
  passed, 191 skipped on the final tree. The run before the review gave 10 667 passed, 191
  skipped and 1 failed (`test_no_stale_name`, fixed in `3a0f20ce`), and the review's 8
  cases account for the difference. `test_vale.py` adds 21 cases, 0.65 s in all on one
  run. The full suite did not run: no measured number can move.
  "esd" in other codes: GSAS-II 5.8.4 source 278 "esd" and 80 "esds" against 13 "standard
  uncertainty"; the TOPAS Technical Reference says "estimated standard deviations" in its
  one section on errors; no FullProf manual was on disk.

  *Gotchas.* Vale.Terms holds an accepted word to its listed case even at a sentence's
  start, so the generator writes a lower-case term as `[aA]nisotropic`. A Vale section glob's
  `*` crosses `/`, so the section is `[docs/docs/[!_]*.md]` to skip `_build/` and
  `_generated/`, and an empty `BasedOnStyles` in a later section does not switch styles
  off. Hunspell has no possessive for most stems, so `rietx.Spelling` filters `'s` forms.
  The dictionary's affix flag strings match `test_no_stale_name`'s old-name pattern, so
  the file is on its allowlist. MyST `{{ NAME }}` substitutions and "et al." are token
  ignores. Root CLAUDE.md is at its size cap, so the run command lives in CONTRIBUTING.md.

  *Review.* `/code-review high --fix` found seven and fixed five (`f41bdbe9`): the generator
  dropped only "-ize" American forms and now drops six patterns; the accepted-and-rejected
  test read only the hand-kept half; the comments gave a wrong reason for copying
  Microsoft's Terms and Vocab (an accept-list word exempts every phrase holding it, measured
  as 12 lost "sample displacement" alerts); a MyST `(label)=` target is a token ignore; the
  tests cache the dictionary. Declined: a retry on `vale sync` in CI (three runs passed),
  and keeping a title-initial capital, which touches no word today.

  Next: WP-1985 widens the section to `_generated/` once the package's strings are
  rewritten (its Inherited has the counts). WP-1983 and WP-1984 write their tabs under the
  gate. WP-1986 moves chapters that carry 463 errors between them.

- **2026-10-16** — filed from WP-1975's slate. No open WP owns prose linting.
