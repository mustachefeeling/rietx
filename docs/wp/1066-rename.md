# WP-1066 — Rename the project to `rietx`

Milestone: v1.0 · Status: ✅ 2026-08-14 — `rietx` everywhere (363 files), the
three format tokens unmoved through a second rename, the audit retargeted, and
counts identical either side (2257 passed / 108 skipped). The brand token is out
of the WP *filenames* too, which is what the audit found.
Depends on: [1062](1062-rename.md) (blocked [1003](1003-api-freeze-pypi.md))

<!--
Same argument as 1062, one rung further along: nothing is published, the freeze
(1003) embeds the current name, and every WP landing after this one is born in
the new name. What is different is the cost — 1062's Phase 1 already landed, so
the name-bearing literals are centralized and this is a sweep, not a design.
-->

## Goal

The package is `rietx` everywhere — distribution, import, CLI, state dir, repo,
and the GUI's committed dist — with the on-disk format tokens **unchanged**, and
`tests/test_no_stale_name.py` retargeted at `anatase`.

## Context

**Why again.** `anatase` is a mineral this software analyses, and it reads as a
sample name rather than a program. [1062](1062-rename.md) accepted
that cost with its eyes open — its own Context says the property making the
rename exact "will not survive the first anatase phase added to test data or a
tutorial" — and the user's judgment two days later is that the confusion is not
worth carrying into a public release. The 1062 conditions still hold verbatim:
no PyPI upload under `anatase`, no GitHub release, a private repo, and the two
study tags (`guillemot-study`, `wpem-bench-study`) untouched by a `src/` rename.
So there is again no compatibility burden and no migration to write.

**The name, verified 2026-08-14 — reserved, not merely free.** PyPI `rietx`
exists: a **0.0.0 placeholder** (wheel + sdist, MIT, author "Yue Wu", homepage
`github.com/yue-here/rietx`) uploaded to hold the name, and `github.com/yue-here/rietx`
is a public placeholder repo created the same day, 0 stars, one commit. Both are
the user's. So the availability question 1062 had to answer is already answered,
and what replaces it is a **collision**: the placeholder repo occupies the name
the real repo (`yue-here/anatase`, private, 1 star) must take. Decided with the
user 2026-08-14: delete the placeholder, then `gh repo rename` — which keeps the
real repo's star, issues and PR numbers, leaves GitHub's redirect from the old
URL in place, and makes the placeholder release's Homepage link resolve to the
real repo. The repo **stays private**; publishing is 1003's call.

**The trap 1062 accepted does not recur — it inverts.** `rietx` is not domain
vocabulary and cannot become it: `git grep -i rietx` is 0 hits, and the nearest
domain word, *Rietveld*, does not contain the token (`riet` as a whole word: 0
hits). But the audit greps the **old** name, and the old name is now the
ambiguous one. `anatase` appears zero times as vocabulary today, while `rutile`
— the other TiO₂ polymorph — appears ~168 times in the QPA round-robin data, and
anatase/rutile is the canonical QPA pair. So this audit has a foreseeable
expiry, stated where it lives: the day a fixture or tutorial gains an anatase
phase, that path joins the allowlist with the reason "the TiO₂ phase, not the
old package" — a judgement to make once, deliberately, not a reflex.

**This is Phase 2 only.** 1062's Phase 1 is already in the tree: `_about.py`
holds the nine name-bearing literals and every scattered site imports them, the
version lookup is loud rather than falling silently to `0.0.0+dev`, and
`Homepage` is correct. So the whole Phase-1 half of 1062 collapses into changing
**six values** in `_about.py` and leaving **three** alone.

**Measured surface, 2026-08-14** (regenerates — do not transcribe a file list):
`git grep -Ii anatase` is 1924 hits across 296 files; by area, tests 98 files,
src 88, docs 84, gui 10, examples 6, plus `.github`, `.claude`, both locks,
README, CLAUDE.md, ATTRIBUTION.md and `.gitignore`. Tracked paths naming it:
`src/anatase/**` only — `gui/src/lib/rxt.ts` is already a format token, not a
brand one.

**The format tokens do not move.** `.rex`, `rxt` / `.rxt` and
`instrument_profile` name versioned contracts (`PROJECT_FORMAT_VERSION`, textdoc
`FORMAT_VERSION`, `instrument_profile.FORMAT_VERSION`), and `_about.py`'s rule
is that a contract must not move because a brand did — which is exactly what
makes *this* rename a sweep rather than a format break, one rename after the
rule was written. They now read as though derived from `rietx`; that is a
coincidence and neither a reason to touch them nor a reason to re-couple them.

## Non-goals

- **The API freeze** — [1003](1003-api-freeze-pypi.md). This renames a surface;
  it does not decide what is frozen.
- **The PyPI upload**, making the repo public, `CITATION.cff`, and the
  `tests/data/qarr/` licence blocker — all 1003's.
- **Renaming module paths or physics symbols** beyond the package root.
- **Retiring the `pxrd`/`pxt` half of the audit.** Two old names now, and the
  older one costs one regex alternation.

## Tasks

- [x] `git mv src/anatase src/rietx` and `pyproject.toml` (`name`, `authors`,
      the self-referential `[dev]` extra, `[project.urls]`, `[project.scripts]`
      both sides, `[tool.hatch.build.targets.wheel] packages`) in one step, then
      `uv pip uninstall anatase && uv pip install -e ".[dev]"`. Nothing runs in
      that window — see the hazards below.
- [x] `_about.py`: the six brand values (`DIST_NAME`, `STATE_DIR_NAME`,
      `STATE_DIR_ENV`, `AGENT_TOOL_NAME`, `DATA_PACKAGE`, `SERVER_TOKEN`); the
      three format values untouched; and the docstring's audit paragraph
      rewritten, because its domain-vocabulary argument now points at `anatase`.
- [x] The five path references, in one commit: `.gitignore` (the
      `!src/anatase/gui/static/**` negation — stale ⇒ the committed dist drops
      out of the repo *and* the wheel), `.github/workflows/gui.yml` (path filter
      + the `git diff --exit-code` gate), `.github/workflows/docs.yml`,
      `gui/vite.config.ts` `outDir`, `gui/scripts/build_info.py` `DIST_RELATIVE`.
- [x] `.claude/`: `hooks/session_start.py` — the `.pth` name filter, the
      `__editable__*anatase*.py` glob and the three report strings; stale ⇒ every
      session starts with "no editable pointer" on a healthy venv — and
      `commands/wp-handover.md`.
- [x] Mechanical sweep over `src/`, `tests/`, `examples/`, `docs/`, `README.md`,
      `ATTRIBUTION.md`, and all six `CLAUDE.md` files (root, `gui/`, `tests/`,
      `src/rietx/{gui,indexing,io}/`). `tests/test_docs_consistency.py`'s
      `SIZE_CAPS` keys are two of those paths.
- [x] `docs/manual/`: `conf.py` (`project`, `author`, `html_title`, the constant
      imports) and the 156 `*Source:* \`anatase.…\`` lines, each of which
      `test_manual.py` imports. `docs/VALIDATION.md` is **generated** — change
      `tests/validation_matrix.py`, not the file.
- [x] Rebuild and commit the frontend dist; regenerate `uv.lock` and
      `gui/package-lock.json`.
- [x] GitHub: `gh repo delete yue-here/rietx` (the placeholder), then
      `gh repo rename rietx` and `git remote set-url origin`.
- [x] `tests/test_no_stale_name.py` retargeted: `STALE` gains `anatase`, keeps
      `pxrd|pxt`, allowlist and docstring rewritten around the inverted trap.
- [x] **Unplanned, and the audit's own finding:** both rename WPs renamed to a
      bare `NNNN-rename.md`. A brand token in a *filename* fails the path test
      on its own name and the content test on every file that links to it,
      because a markdown link spells the filename. Rule recorded in the path
      test, where the failure appears.
- [x] `~/.anatase` → `~/.rietx` on this machine (untracked, operational: the
      recent list and theme, which otherwise look lost).

### Hazards

Five are 1062's, measured there rather than reasoned here; the sixth is new.

1. **Ordering.** mv → sweep → reinstall. "mv then install as the very next
   command" cannot work: the install reads a `pyproject.toml` still naming the
   old path. Nothing may run in that window — the editable `.pth` is a bare path
   to `src`, so `import rietx` starts working before `dist-info` agrees, and
   anything run there writes `0.0.0+dev` into its provenance.
2. **`uv pip install -e .` under a new name leaves the old distribution
   installed**, so `version("anatase")` keeps resolving and an "old name is
   gone" check passes on a dirty venv. `uv pip uninstall anatase` first.
3. **`test_gui_server.py`'s `assert "/anatase-upload-" not in …`** is pinned to
   the `mkdtemp` prefix in `gui/imports.py`: rename the prefix and not the test,
   and the test still passes while checking nothing.
4. **The node rebuild is mandatory** — `gui/vite.config.ts` and
   `gui/scripts/build_info.py` both name the output path *and* are hashed into
   `build-info.json`. Never hand-edit the dist: it carries the `pip install`
   hint, the header, the `<title>` and the wizard's strings.
5. **`git check-ignore` consults the index** and answers for tracked files
   without reading `.gitignore` at all; `--no-index` is what makes it ask.
6. **New: the audit cannot guard its own retarget.** `test_no_stale_name.py` is
   the one file that must spell both names, and 1062 recorded that its first run
   passed only because the file was still untracked and `git grep` cannot see an
   untracked file. Make it fail on purpose once, and confirm the failure names
   the file you expected.

### Allowlist — the only places an old name may survive

- **This file** and **[1062](1062-rename.md)**: both document a
  rename, so both name every side of it and cannot be swept.
- `src/rietx/data/mu_McMaster.dat` and `data/f1f2_CromerLiberman.dat` —
  `#C Modifications for pxrd-refine`, historical provenance in vendored data,
  parsed byte-sensitively. Amend with a "formerly" note if anything.
- `docs/milestones/v1.0.md` — the lines recording that each rename happened.
- Third-party attribution URLs in `ATTRIBUTION.md` and `tests/data/README.md`.

**Must not change:** port `8731`, the format tokens above, and the third-party
file magics in the readers (`*RAS_DATA_START`, `_FILEVERSION`, `xrdMeasurements`,
the BRML XSI namespace).

## Acceptance

**Zero numbers move — with no exception this time.** 1062 added four tests and
expected `+4`; this WP adds none and retargets three, so passed+skipped must be
**identical** before and after in both selections. Baseline measured on this
branch before the first edit; a moved count is a bug in the rename.

```sh
git grep -nIiE 'anatase|pxrd|pxt'                       # allowlist only
git ls-files | grep -iE 'anatase|pxrd'                  # empty
uv venv --python 3.12 && uv pip install -e ".[dev]"     # proves the self-extra resolves
.venv/bin/python -c "import rietx; print(rietx.capabilities().package_version)"  # NOT 0.0.0+dev
.venv/bin/rietx --help
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
npm --prefix gui ci && npm --prefix gui run build && npm --prefix gui test
git diff --exit-code --stat src/rietx/gui/static        # fresh, not merely rebuilt
.venv/bin/python -m pytest -n auto --dist loadgroup     # full suite, incl. acceptance
.venv/bin/python examples/nac_11bm.py
.venv/bin/rietx gui
```

Then the checks no test makes: **start a new Claude session** and confirm the
`session_start` hook reports a healthy venv rather than "no editable pointer" —
invisible to everything above. Run a fit and confirm `provenance.package_version`
is real. Open the GUI and confirm the header, `<title>` and the wizard hint read
the new name while the text-pane chip still reads `rxt 1`.

## References

- The prior rename, its measured gotchas and the Phase-1 design this one
  inherits: [1062](1062-rename.md).
- Name reservation (PyPI 0.0.0, placeholder repo) and the collision decision:
  verified and decided 2026-08-14, recorded in Context above.
- Session protocol and the size caps this file must satisfy:
  [../ROADMAP.md](../ROADMAP.md) § Session protocol; `tests/test_docs_consistency.py`.

## Handover log

- **2026-08-14** — **closed.** Three commits: created, the rename, the audit.

  **Done.** Every checklist item. `src/anatase` → `src/rietx` across 363 files
  in one sweep (mv → pyproject → sweep → `uv pip uninstall` → reinstall, nothing
  run in the window); six brand values in `_about.py`, three format tokens
  untouched; the five path references, the session-start hook, both locks, the
  dist rebuilt *fresh* (a second build reproduces it byte for byte); GitHub
  placeholder deleted (backed up first) and the real repo renamed in place with
  its star and redirect intact, still private; `~/.anatase` → `~/.rietx`; the
  audit retargeted and made to fail on purpose first.

  **Counts** (`[dev]` only — no jax/torch — darwin/arm64, the main checkout's
  venv): fast suite **2257 passed, 108 skipped** before *and after*, 2:41 and
  3:21. vitest 408 in 19 files, svelte-check 0 errors, ruff and `sphinx -W`
  clean. `examples/nac_11bm.py` lands a = 10.251216(46) Å at Rwp 0.0932 — the
  digits 1062 recorded, so the physics is provably untouched. All five
  `*_version` contracts unmoved. Full suite **2364 passed, 117 skipped** in
  29:08, green including the real-data acceptance and the indexing row 1062
  measured as load-sensitive. Read that last figure as a fresh measurement, not
  a comparison: **the identical-count proof is the fast suite**, measured either
  side of the sweep in this session (and 2257/108 is also what 1065 recorded, so
  it was the tree's figure before this session touched it). No pre-rename
  full-suite count was taken, and the most recent one on record is ~300 tests
  old, so the two are not a pair.

  **The finding, and it cost the WP an unplanned item.** A brand token in a
  **filename** is worse than one in a line: `docs/wp/1062-rename-to-anatase.md`
  failed the path test on its own name *and* the content test on all five files
  that linked to it, because a markdown link spells the filename. Both rename
  WPs are now bare `NNNN-rename.md`. The same trap caught this session twice
  more, which is why it is a rule and not an anecdote: writing the 1003 mailbox
  entry, prose *about* the rename spelled the retired names in a live WP file —
  reworded rather than allowlisted, because allowlisting the freeze WP would
  blind the audit on the file that most needs it.

  **Gotchas for whoever is next.**
  1. **The audit's `anatase` token has an expiry.** It is a phase this software
     analyses. The first fixture or tutorial with an anatase phase allowlists
     *that path* with the reason "the TiO₂ phase, not the old package" — a
     judgement made once, never a reflex for silencing a red test.
  2. **`gh` needs the `delete_repo` scope** and will not have it by default:
     `gh auth refresh -h github.com -s delete_repo`, which is interactive.
  3. **`npm ci` does not rewrite `package-lock.json`'s `name` field** — it
     installs *from* the lock. `npm install --package-lock-only` is what
     regenerates it, and the audit is what noticed.
  4. **The checkout directory is still `~/Code/anatase`.** Renaming it breaks
     the editable `.pth` (absolute path ⇒ reinstall) and orphans the Claude
     Code session state keyed on the old path. Left deliberately; cosmetic.
  5. **1003's mailbox gained a correction, not just an entry**: its inherited
     line saying nothing was uploaded to PyPI is false — a 0.0.0 placeholder is
     published, and it declares `requires-python >=3.10` against pyproject's
     `>=3.11`.

  **Next.** 1003, unchanged — the freeze now covers a surface whose brand/format
  split has been tested by a real rename rather than merely asserted.

- **2026-08-14** — created. Name already reserved by the user on both indexes
  (PyPI 0.0.0 placeholder, public placeholder repo, both dated today), so the
  availability question was replaced by the repo-name collision; deleting the
  placeholder and renaming the real repo was chosen with the user, visibility
  left private for 1003. Baseline counts measured on this branch before any
  edit. Not started.
