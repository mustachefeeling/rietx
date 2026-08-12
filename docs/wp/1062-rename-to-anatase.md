# WP-1062 — Rename the project to `anatase`

Milestone: v1.0 · Status: ✅ 2026-08-12 — `anatase` everywhere (~300 files),
with the on-disk formats deliberately decoupled from the brand (`.rex`, `.rxt`
/ `rxt N`, plain `instrument_profile`) and `tests/test_no_stale_name.py`
auditing against the **old** token. Counts moved 2162 → 2166 passed / 108
skipped, exactly the four tests added.
Depends on: — (blocked [1003](1003-api-freeze-pypi.md))

<!--
Run this BEFORE the remaining v1.0 work, not after: the name surface grew ~40 %
in the eleven days to 2026-08-12, every WP landing after the rename is born in
the new name, and the audit test this WP adds makes a reintroduction fail CI
rather than rely on a note in someone's mailbox.
-->

## Goal

The package is `anatase` everywhere — distribution, import, CLI, repo, and the
GUI's committed dist — with the on-disk format tokens deliberately *decoupled*
from the brand, and a test that fails if the old name reappears.

## Context

Nothing has ever been published: no PyPI upload, no GitHub release, and the two
tags (`guillemot-study`, `wpem-bench-study`) archive study branches that are not
meant to merge. So there is no compatibility burden and no migration to write.
This is the last cheap moment — [1003](1003-api-freeze-pypi.md) freezes an API
whose names embed the current one (`pxrdref.agent`, `pxrdref.gui.textdoc`, the
CLI `pxrdref index`, `PXRDREF_STATE_DIR`), so a rename after the freeze breaks
what the freeze promised.

**The measurement that makes this exact.** `git grep -i pxrd` over the tracked
tree has **zero false positives**: `PXRD` as the scientific term appears nowhere,
the prose consistently writes "powder X-ray diffraction". So the audit command is
the checklist, and it regenerates — do not transcribe a file list into this WP,
it will be stale by the time anyone reads it. Snapshot at 2026-08-12, for scale
only: `pxrdref` 1752 hits / 276 files, `.pxrd` 134 / 35, `pxrd-refine` 56 / 37.

**The name, verified 2026-08-12.** PyPI `anatase` free (`/simple/` and `/json`
both 404), `anatase-py` and `pyanatase` free, GitHub `yue-here/anatase` free, no
stdlib or import shadow, no existing crystallography software of that name
(nearest strings: `AnACor2.0`, `Dans_Diffraction` — neither collides). Lowercase,
no hyphen, no underscore, so one string serves all three: `pip install anatase`,
`import anatase`, `anatase gui`.

**The one cost, and it is accepted deliberately.** Anatase is a phase this
software analyses. It appears **0 times** in the tree today, but `rutile` — the
other TiO₂ polymorph — appears **168 times** as a QPA round-robin phase, and
anatase/rutile is the canonical quantitative-phase-analysis pair. The property
that makes *this* rename exact (a brand token that is not domain vocabulary) will
not survive the first anatase phase added to test data or a tutorial. Two
consequences, both handled below: the audit test is written against the **old**
token `pxrd`, never the new one; and the docs need a disambiguation convention
(the phase as `anatase (TiO₂)`, the package in code formatting) from the first
public page.

**Format tokens are decoupled from the brand on purpose.** `.pxrd`, `pxt N` and
`pxrdref_instrument_profile` become neutral tokens that encode no name. They are
already versioned contracts (`PROJECT_FORMAT_VERSION` `"1.1"`, textdoc
`FORMAT_VERSION`, `instrument_profile.FORMAT_VERSION`, `PEAKS_FORMAT_VERSION`),
and a contract should not move when a brand does — which is what stops a future
rename from ever being a format break, and stops the formats inheriting the
phase-name ambiguity above.

### Prerequisite, measured 2026-08-12: there is none

The obvious worry — in-flight branches conflicting over ~276 files — does not
apply. `git worktree list` shows three entries but two directories no longer
exist (stale registrations, `git worktree prune`) and the third is clean; all
three branches are 0 commits ahead of `main`. `git branch --no-merged main`
returns only `guillemot-example-refinements` and `wpem-benchmark`, both archived
by tag, both confined to `studies/` (a directory that does not exist on `main`),
both touching `src/`, `tests/` and `gui/` not at all. No open PRs. **Re-run those
three checks before starting** — this paragraph is a measurement with a shelf
life, and if a branch does appear, note that its name-bearing files will fail the
new audit on merge, loudly, which is the intended behaviour rather than a problem.

## Non-goals

- **The API freeze itself** — [1003](1003-api-freeze-pypi.md). This WP renames a
  surface; it does not decide what is frozen.
- **The PyPI upload**, classifiers, and the `tests/data/qarr/` licence blocker —
  all 1003's.
- **`CITATION.cff` and a `@software` entry in `docs/manual/references.bib`.**
  Neither exists; a first public release wants both and both embed the name, but
  they are release metadata, so they belong to 1003.
- **Renaming physics symbols or module paths** beyond the package root. This is a
  brand change, not a refactor.

## Tasks

### Phase 1 — centralize (lands first; correct on its own merits)

- [x] Add `src/pxrdref/_about.py`: `DIST_NAME`, `PROJECT_SUFFIX`,
      `TEXTDOC_MAGIC`, `PROFILE_FORMAT_KEY`, `STATE_DIR_NAME`, `STATE_DIR_ENV`,
      `AGENT_TOOL_NAME`, `DATA_PACKAGE`, `SERVER_TOKEN`. It imports nothing from
      the package, so anything may import it.
- [x] Point the scattered literals at it: `refine.py` `version("pxrd-refine")`,
      `docs/manual/conf.py` `_dist_version(...)`, `project.py` `PROJECT_SUFFIX`
      (**a dead constant today — its definition is its only occurrence**; the
      suffix is actually enforced in `gui/src/lib/wizard.ts`),
      `gui/imports.py`, `gui/textdoc.py` (`"pxt"` ×5), `io/instrument_profile.py`
      `FORMAT_KEY`, `gui/session.py` (env var + `~/.pxrdref`), `agent.py`
      `tool_definition(name=...)`, the three `_DATA_PACKAGE = "pxrdref.data"` in
      `crystallography/`, and the `pip install 'pxrd-refine[…]'` hint strings in
      `viz/`, `backend/api.py`, `agent.py`, `gui/server.py`, `compare_app.py`.
- [x] **Make `refine.py`'s version fallback loud**, and test that the installed
      distribution resolves. Today `version("pxrd-refine")` is wrapped in
      `except PackageNotFoundError: _VERSION = "0.0.0+dev"` — a rename makes that
      a *successful lookup of the wrong name*: nothing raises, and `0.0.0+dev` is
      stamped into every `RefinementResult.provenance`, every `TreeHeader` in
      every `history.jsonl`, every `project.json`, and `/api/capabilities`. No
      existing test catches it (`test_capabilities` asserts only that the first
      character is a digit, and `"0"` is), and a zero-occurrence audit cannot
      either, because nothing stale is left behind.
- [x] Fix `pyproject.toml` `Homepage` — it names `github.com/pxrd-refine/pxrd-refine`,
      an org that does not own this repo. Wrong today, independent of the rename.

### Phase 2 — the rename (one session, start to finish)

- [x] `git mv src/pxrdref src/anatase`, then **`uv pip install -e ".[dev]"` as the
      very next command** — see the ordering hazard below. Rename
      `gui/src/lib/pxt.ts` to the new format token.
- [x] `pyproject.toml`: `name`, `authors`, the `[dev]` self-referential extra
      (`"pxrd-refine[docs]"` — stale ⇒ `pip install -e ".[dev]"` fails to
      resolve), `[project.urls]`, `[project.scripts]` (both sides),
      `[tool.hatch.build.targets.wheel] packages`.
- [x] The five path references, in one commit: `.gitignore` (the
      `!src/pxrdref/gui/static/**` negation — stale ⇒ the committed dist silently
      drops out of the repo *and the wheel*), `.github/workflows/gui.yml` (path
      filter + the `git diff --exit-code` gate), `.github/workflows/docs.yml`,
      `gui/vite.config.ts` `outDir`, `gui/scripts/build_info.py` `DIST_RELATIVE`.
- [x] `.claude/`: `hooks/session_start.py` and `commands/wp-handover.md`. The hook
      iterates `.pth` files and does `if "pxrd" not in pth.name: continue`; after
      the rename the file is `_editable_impl_anatase.pth`, so it is skipped and the
      hook reports **"no editable pxrdref pointer in .venv" at every session
      start**, on a healthy venv. It also globs `__editable__*pxrd*.py` and names
      `_editable_impl_pxrd_refine.pth` — the only place the PEP-503 underscore
      spelling appears.
- [x] Mechanical substitution over `src/`, `tests/`, `examples/`, `docs/`,
      `README.md`, `ATTRIBUTION.md`, `LICENSE` (the copyright holder — a
      deliberate legal edit, not a sed hit), and **all six `CLAUDE.md` files**:
      root, `gui/`, `tests/`, `src/anatase/gui/`, `src/anatase/indexing/`,
      `src/anatase/io/`.
- [x] `docs/manual/`: `conf.py` (`project`, `author`, `html_title`, `release`, the
      constant imports) and every `*Source:* \`pxrdref.…\`` line — each is
      `importlib.import_module`'d by `test_manual.py::test_every_source_symbol_imports`.
      `docs/VALIDATION.md` is **generated** by `tests/validation_matrix.py`: change
      the generator, not the file.
- [x] Rebuild and commit the frontend dist (`npm --prefix gui ci && npm --prefix
      gui run build`); regenerate `uv.lock` and `gui/package-lock.json`.
- [x] Rename the GitHub repo in place (`gh repo rename anatase`) and
      `git remote set-url origin`. Keeps stars, issues and the PR numbers commit
      messages reference; GitHub redirects the old URL.
- [x] `tests/test_no_stale_name.py`: the audit returns only the allowlist. Written
      against **`pxrd`**, the old token — deliberately, per the phase-name caveat
      in Context. Plus the acceptance run's obs/calc/diff PNGs to `tests/output/`
      (unchanged from baseline — this WP carries no physics).

### Two hazards that no substitution finds

**The reinstall window.** The editable install is a bare path `.pth` containing
only `…/src`, so the instant `src/pxrdref` becomes `src/anatase`, `import anatase`
works *with no reinstall* — while `dist-info` still says `pxrd_refine`, so
`version("anatase")` raises and falls through to `0.0.0+dev`. That window looks
healthy and writes corrupt provenance into anything run in it. Reinstall first;
Phase 1's loud fallback is what turns this from silent to noisy, and is the second
reason Phase 1 goes first.

**Two tests that go quiet rather than red.** `tests/test_gui_dist.py` whitelists
the exact `.gitignore` negation string as a *filter*, not an assert (stale ⇒ it
reports "the committed dist is gitignored" when it is not). And
`tests/test_gui_server.py`'s `assert "/pxrdref-upload-" not in …`, pinned to the
`mkdtemp` prefix in `gui/imports.py`: rename the prefix and not the test and the
test **still passes while checking nothing**.

**The node rebuild is mandatory.** `gui/vite.config.ts` and
`gui/scripts/build_info.py` both name the output path *and* are inside
`SOURCE_FILES`, the set hashed into `build-info.json`. Editing either makes the
committed dist stale and fails `test_gui_dist.py`. No Python-side workaround, and
never hand-edit the dist: it carries the `pip install` hint, `.pxrd`,
`<strong>pxrdref</strong>`, the `name:"pxt"` language definition and `<title>`.

### Allowlist — the only places the old name may survive

- **This file.** It documents the rename, so it names both sides ~32 times and
  cannot be swept; the same holds for whatever remains of 1003's `### Inherited`
  entry (which is consumed when 1003 closes, so it is transient). Add both paths
  to `test_no_stale_name.py`'s allowlist in the same commit that adds the test —
  this is the one self-collision the audit has, and it is easy to discover only
  by running it.
- `src/anatase/data/mu_McMaster.dat` and `data/f1f2_CromerLiberman.dat` —
  `#C Modifications for pxrd-refine (see ATTRIBUTION.md)`. Historical provenance
  in vendored third-party data, parsed byte-sensitively by
  `crystallography/{attenuation,dispersion}.py`. Amend with a "formerly" note if
  anything; do not replace.
- One line in `../milestones/v1.0.md` recording the rename itself.
- Third-party attribution URLs in `ATTRIBUTION.md` and `tests/data/README.md`.

**Must not change:** port `8731` (a port, not a name), and the third-party file
magics in the readers — `*RAS_DATA_START` (`io/formats/ras.py`), `_FILEVERSION`
(`uxd.py`), `xrdMeasurements` (`xrdml.py`), the XSI namespace (`brml.py`). Other
vendors' formats; a sweep aimed at "format constants" reaches them.

## Acceptance

**Zero numbers move.** This WP changes no physics and no test logic, so
passed+skipped must be **identical** before and after in both selections, except
`+1` for `test_no_stale_name` and `+1` for the Phase-1 version test. Measure the
fast suite before starting and quote both counts with venv and platform
(`tests/CLAUDE.md` § Quoting numbers). A moved count is a bug in the rename, not
a new result.

```sh
git grep -nIi 'pxrd'                                    # allowlist only
git ls-files | grep -i 'pxrd'                           # empty
uv venv --python 3.12 && uv pip install -e ".[dev]"     # proves the self-extra resolves
.venv/bin/python -c "import anatase; print(anatase.capabilities().package_version)"  # NOT 0.0.0+dev
.venv/bin/anatase --help
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
npm --prefix gui ci && npm --prefix gui run build && npm --prefix gui test
git diff --exit-code --stat src/anatase/gui/static      # fresh, not merely rebuilt
.venv/bin/python -m pytest -n auto --dist loadgroup     # full suite, incl. acceptance
.venv/bin/python examples/nac_11bm.py
.venv/bin/anatase gui
```

Then the checks no test makes: **start a new Claude session** and confirm the
`session_start` hook reports a healthy venv rather than "no editable pointer" —
that failure is invisible to everything above. Run a fit and confirm
`provenance.package_version` is the real version. Open the GUI and confirm the
header, `<title>`, the wizard's project-suffix hint and the text-pane chip all
read the new tokens. Save and reload an instrument profile.

## References

- PyPI/GitHub availability and the software-name survey: verified 2026-08-12,
  recorded in Context above.
- Session protocol and the "a number is claimed by merging, not writing" rule:
  `../ROADMAP.md` § Session protocol.
- Size caps and the WP/ROADMAP bijection this file must satisfy:
  `tests/test_docs_consistency.py`.

## Handover log

- **2026-08-12** — **closed.** Both phases landed in five commits.

  **Done.** Phase 1: `_about.py` with the nine literals, every scattered site
  pointed at it, the version lookup made loud (verified by hand against the real
  failure — `DIST_NAME="anatase"` on the old install warns and stamps
  `0.0.0+dev`), `Homepage` fixed to the account that owns the repo. Phase 2:
  `git mv`, an ordered substitution over ~300 files, both locks regenerated, the
  dist rebuilt (and *fresh* — a second build reproduces it byte for byte), the
  GitHub repo renamed with its star and redirect intact, origin re-pointed.
  Format tokens landed as `.rex` / `.rxt` + `rxt N` / plain `instrument_profile`
  — chosen with the user, from prior art in `exp`/`inp`/`pcr`; every "powder"
  or "xrd" candidate was rejected because neutron/TOF is on the v2 fence and
  would date them exactly as `pxrd` dated.

  **Counts** (`[dev]` only — no jax/torch — darwin/arm64, this worktree's venv):
  fast suite **2162 → 2166 passed, 108 skipped**, wall clock 2:49–4:26 across
  three runs. The +4 is one version test and **three** audit tests, not the
  one the WP predicted: contents, tracked *paths*, and allowlist hygiene are
  three different invariants and a failure should name which. Full suite
  **2264 passed, 117 skipped** in 28:01. vitest 408 in 19 files, svelte-check
  0 errors, ruff and `sphinx -W` clean; `examples/nac_11bm.py` lands
  a = 10.251216(46) Å at Rwp 0.0932 and stamps a real version.

  **One acceptance row is load-sensitive, measured.** The *first* full run was
  contended (a killed run's workers, plus a stray watcher polling) and gave
  2263 passed / 1 failed:
  `test_a_short_clean_list_is_searched_ranked_and_reported_unscored`, on
  `assert all(res.search_complete[s] …)`. Alone and serial it passes in 3:28,
  and on a quiet machine the full suite is green. That is the category
  `tests/CLAUDE.md` already names — "some system did not finish" is a statement
  about machine load — so it is quoted here as its measurement rather than
  re-litigated: **this row needs a quiet machine, or the assertion needs
  restating as "every system reports whether its domain was exhausted".**
  Nothing in this WP touches search, budgets or physics.

  **Gotchas for whoever is next.**
  1. **The WP's Phase-2 ordering cannot work as written.** "`git mv` then
     `uv pip install` as the very next command" fails: the install reads a
     `pyproject.toml` still naming `src/pxrdref`. It is mv → sweep → reinstall,
     and nothing may run in that window.
  2. **`uv pip install -e .` under a new name leaves the old distribution
     installed.** Both dist-infos coexisted, so `version("pxrd-refine")` still
     resolved — an "old name is gone" check would have passed on a dirty venv.
     `uv pip uninstall pxrd-refine` was needed. Anyone with an older venv has
     this.
  3. **`git check-ignore` consults the index**, so the dist's gitignore guard
     was green *without reading `.gitignore` at all* — every file it checks is
     tracked. Unrelated to the rename, months old, fixed with `--no-index`; the
     rule is now in `tests/CLAUDE.md`.
  4. **`pxt` has no audit backstop.** The old textdoc magic contains no `pxrd`,
     so `test_no_stale_name.py` greps it as a **second** token. A future token
     change needs the same treatment or nothing will notice.
  5. **Old `.pxrd` projects still open**, verified on a real one from before the
     rename (`format_version` 1.1 read, pattern and phases intact, text pane
     rendering `rxt 1`). The suffix was always conventional, never enforced.
     But `~/.pxrdref` is *not* migrated: an existing user's recent list and
     theme look lost until that directory is copied to `~/.anatase`.
  6. **A judgment call worth revisiting:** textdoc `FORMAT_VERSION` stayed `"1"`
     although its magic word changed, on the grounds that the document is
     rendered afresh and never persisted, so no stored file can carry the old
     header. If a `.rxt` ever lands on disk, that reasoning expires.

  **Next.** 1058 → 1059 → 1003, unchanged. 1003's `### Inherited` has the
  freeze-facing surface; 1017's has the naming rules for its manual pages.

- **2026-08-12** — created. Name chosen and namespace verified; the
  three-worktree blocker an earlier draft carried was **measured and refuted**
  (all three branches 0 ahead, two directories already gone, both unmerged
  branches archived by tag and confined to `studies/`), which is what moved this
  WP from "last before the freeze" to "as early as convenient". Not started.
