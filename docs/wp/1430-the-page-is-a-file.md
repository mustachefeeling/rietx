# WP-1430 — the page is a file

Milestone: unscheduled · Status: ✅ 2026-09-16 — the page is four files in `watch/static/`, its DOM-free half has 15 node cases, and the browser test took no diff
Depends on: 1423 (the page as it stands)

## Goal

The `rietx watch` page's script and stylesheet are files in the package,
served as files, with the pure functions in an ES module that `node --test`
runs from the suite. The page behaves exactly as it does today and the
browser test passes unchanged. Every later WP on this page edits a file an
editor lints and a test imports.

## Context

Seven WPs (1424–1429, 1431) are queued against one page. Today that page is
`_PAGE_TEMPLATE` in `src/rietx/watch.py`: about 90 lines of CSS and 520 lines
of JavaScript quoted inside a Python string, with three `@TOKEN@`
substitutions and a regex that has to be spelt `\\/` to survive the quoting.
Its only check is `node --check` (`tests/test_watch_app.py`), which sees
syntax and nothing else. WP-1402 and WP-1405 each shipped a page defect no
test could see. Nothing in it is unit-tested: `rangesOf` and the Δ/σ ladder,
`ago`, `num`, `patchList`'s ordering, the panel state.

Two of the queued WPs need this directly. 1425 ports the GUI's `clampSize`
and wants to pin the port to the original on the GUI's own cases. That needs
the port to be importable. 1426 and 1427 both rewrite `drawRun`
and `patchList`; a merge conflict inside a Python string is worse than one in
a `.js` file.

### The precedents

- `src/rietx/gui/static/` is served by `gui/server.py` through `STATIC_DIR`.
  Hatchling takes every non-ignored file under `src/rietx`
  (`pyproject.toml` § wheel), so a static directory ships with no build
  configuration.
- `viz/plotlyjs.py` serves a file out of the installed package on a route.
- `node --test` is in Node since 18 and needs no `npm install`. The suite
  already shells out to `node --check` and skips without it; the same
  fixture runs the tests.
- `compare_app.py` has the same shape (a page in a string, lines 200–560)
  and is not touched here. It has one WP queued against it (1429), which can
  do the move if it wants to and is told so.

### The shape

`watch.py` becomes the package `watch/` with `__init__.py` holding the server
and `static/` holding `index.html`, `watch.css`, `watch.js` and
`watch-core.mjs`. `rietx.watch` stays importable; `cli.py` and the tests do
not change their imports. `watch-core.mjs` holds the functions that touch no
DOM: `rangesOf`, `LADDER`, `ago`, `num`, `esc`, `deltaTitle`, `extent`,
`finiteOf`, the panel-state reducer. `watch.js` imports it as a module
script and owns the DOM. The three substitutions (`@SUFFIX@`, `@DIST@`,
`@HUE@`) become fields on the `api/runs` payload, which the page already
fetches first; the HTML is then a static file and
`test_no_page_token_is_left_unsubstituted` becomes a test that the payload
carries the three.

The `node --check` test becomes `node --test static/*.test.mjs`, skipping the
same way. The browser test is the regression bar: it passes before and after
without an edit, or the move changed behaviour.

## Non-goals

- Any change to what the page does or how it looks. Behaviour is bit-for-bit
  the fence; the browser test is its witness.
- Bundling, TypeScript, or `gui/`'s vitest. The page stays a script the
  browser runs as written. If a later WP wants jsdom for DOM logic, it argues
  for it then.
- Moving `compare_app.py`'s page. Named here for 1429 to pick up.

## Tasks

- [x] `watch/` package, static files, the three substitutions on the payload,
      routes serving the files with the right content types
- [x] `watch-core.mjs` with the pure functions, imported by `watch.mjs`
- [x] `node --test` over `rangesOf` (the ladder rungs, the 99.9th percentile,
      the data-derived ranges), `ago`, `num` on `"NaN"`, and the panel
      reducer's last-panel rule; run from `tests/test_watch_app.py`, skipping
      without node
- [x] `tests/test_watch_app.py` adapted (the substitution test, the
      `node --check` test), `tests/test_watch_browser.py` untouched and green
- [x] Root CLAUDE.md § Conventions: the `node --check` rule becomes "a page
      that is JavaScript is a file, checked by `node --test`", one line, with
      `compare_app.py` named as the remaining string
- [x] Skill: none. The page is a human's.

Two revisions to the shape, both made while building it and both recorded in
the handover entry:

- **The DOM half is `watch.mjs`, not `watch.js`.** `node --check` parses a
  `.js` file as CommonJS, where the `import` of `watch-core.mjs` is a syntax
  error, so the plan's own check could not have run on it. A browser cares
  about `type="module"` and the content type, never the extension.
- **The node test file lives in `tests/`, not beside the module.** Hatchling
  takes every non-ignored file under `src/rietx`, so a `.test.mjs` there ships
  in the wheel — the trap `pyproject.toml`'s `exclude = ["**/CLAUDE.md"]`
  already names. Nothing under `src/rietx` is a test file, and this does not
  become the first.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py tests/test_telemetry.py
.venv/bin/python -m ruff check src tests examples
node --test tests/watch_core.test.mjs
```

No assertion in the browser test file moves on this branch; the `/code-review`
pass corrected a stale `watch.py` in one of its comments, and that is the whole
diff. `node --test` runs at least six cases and is invoked by the suite.

## References

- WP-1402 and WP-1405 (the two page defects that motivated `node --check`),
  WP-1423 (the page as it stands), `gui/server.py:STATIC_DIR`.

## Handover log

- **2026-09-16** — The `rietx watch` page is out of its python string. Its
  stylesheet and its javascript are files in the package now, served as files,
  and the half of the javascript that touches no document is a module with
  fifteen `node --test` cases behind it. Nothing the page does changed.
  WP-1423's chromium test passes with no assertion touched, and for a move like
  this that is the only evidence worth having. What it buys is the seven WPs queued
  against this page: they edit files an editor lints, a test imports and a
  merge can resolve, and the Δ/σ ladder, the "NaN" guard and the panel rule are
  checked now by something other than a person looking at a browser. The move
  also turned up one thing nobody had ever looked at. The ladder's spike guard
  does nothing on a pattern of 1000 points or fewer. That is pinned as the
  behaviour and handed to 1426, whose axis it is.

  **Done.**

  - `src/rietx/watch.py` is the package `src/rietx/watch/` now. `__init__.py`
    holds the server, `__main__.py` holds the `-m` entry that a package's
    `__init__` no longer fires, and `static/` holds `index.html`, `watch.css`,
    `watch.mjs` (the document) and `watch-core.mjs` (no DOM). `rietx.watch`
    imports are unchanged and `cli.py` was untouched.
  - Four routes, from one table `watch.STATIC_FILES` mapping name to content
    type. It is consulted before `SimpleHTTPRequestHandler`'s fallback, so a
    run directory holding a `watch.css` of its own cannot replace the page's.
    Four fixed names, so nothing can be walked out of it.
  - `@SUFFIX@`, `@DIST@` and `@HUE@` are gone. A file cannot carry a token,
    since `const HUE = @HUE@;` is no javascript, so the three ride on the first
    `/api/runs` as `payload.page.{suffix,dist,palette}`. The page fetches that
    before it draws anything. `drawSnapshot` gained `if (!HUE) return false;`,
    because a poll can reach the draw before that answer has landed, and
    "undrawn" is what `false` already meant.
  - `watch-core.mjs` exports `LADDER`, `esc`, `ago`, `num`, `deltaTitle`,
    `finiteOf`, `extent`, `rangesOf`, and the panel state as `parsePanels(raw)`
    plus `nextPanels(p, which)`. `watch.mjs` keeps `localStorage` and the
    document.
  - `tests/watch_core.test.mjs`, 15 cases, invoked from
    `tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`.
    It skips without node, the way the old `node --check` test did.
  - `.gitignore` gained `!src/rietx/watch/static/**`, and
    `test_the_pages_files_reach_a_fresh_clone` guards all four files.
  - `test_every_element_the_script_reaches_for_exists` compares the ids
    `watch.mjs` reaches for against the ids `index.html` declares, with `plot`
    the one declared exception because `buildShell` writes it. A page split
    across two files can have an id renamed in one of them, and that throws at
    the first poll with every python test green.
  - Root CLAUDE.md § Conventions: the `node --check` clause is the file rule
    now, and the file lands at 833 lines against a cap of 833.
    `docs/manual/using/cli.md` said the page is a client of seven routes. It is
    a client of eleven, and seven of them are the data that section is about.
  - Forward references into the `### Inherited` of 1424, 1425, 1426, 1427,
    1428, 1429 and 1431. None of them had one before.

  **Measured** on this worktree's venv, `[dev]` **plus playwright**, darwin
  arm64, node 26.3.1. The playwright install is load-bearing for the counts:
  without it `tests/test_watch_browser.py` is one skipped item, and with it
  four passes, so a plain `[dev]` fast count sits three lower than what follows
  for a reason that is the venv and has nothing to do with the change.

  - `tests/test_watch_app.py` + `tests/test_watch_browser.py`: **46 passed
    before the move, 51 after**, so +5 net. Six new cases, less one from
    un-parametrising the `node --check` test down to `compare_app` alone. The
    15 node cases are counted separately, like vitest's.
  - Fast selection after: **5006 passed, 132 skipped**, on an idle machine.
    Another session's full suite was running when this one started and was
    waited out. Wall clock is a range here: 2:14 for this run, 5:04 for the one
    before the last test landed. The same venv before the change is 5001 + 132,
    from the +5 above. Nothing else in the suite moved.
  - The WP's acceptance (`test_watch_app`, `test_watch_browser`,
    `test_telemetry`): 98 passed in 46 s. `ruff check src tests examples`
    clean. `node --test tests/watch_core.test.mjs`: 15 pass, 0 fail.
  - The page as files is 31 939 B. `watch.mjs` 20 263, `watch.css` 5020,
    `watch-core.mjs` 4289, `index.html` 2367.
  - The payload's new `page` block is **299 B**, against a 41-run `/api/runs`
    of 30 431 B whose rows are **735 B each**, so 1 %. That is the number 1427
    should weigh if it wants the poll slimmer. Moving it to a boot-only route
    is one key and one function.
  - The move read as a set of code lines: **404 before, 419 after**, and every
    difference is one of the import, the three constants, the `!HUE` guard, the
    `panels()`/`nextPanels` split, and three assignments at boot. The CSS diffs
    to **zero lines** after dedenting. The body diffs to **one**, with
    `<code>@SUFFIX@</code>` becoming `<code id="empty-suffix"></code>`.
  - The wheel: `uv build --wheel` ships all four files under
    `rietx/watch/static/` and no `.test.mjs`. Installed into a fresh venv,
    `serve()` answers `/` and all four names with the right content types and
    the page constants. So "a static directory ships with no build
    configuration" is measured here. The `gui/` precedent said it would be;
    this is the check.

  **Gotchas.**

  - **`.mjs` is load-bearing.** `node --check` parses a `.js` as CommonJS,
    where the `import` of `watch-core.mjs` is a syntax error, so the WP's own
    plan (`watch.js`) could not have been checked. A browser reads
    `type="module"` and the content type, and ignores the extension.
  - **`node --test` picks its reporter by whether stdout is a terminal.** The
    count is read under an explicit `--test-reporter=tap`. The `spec` reporter
    a pipe gets writes `ℹ pass 15`, and the regex wanted `# pass 15`.
  - **`.gitignore`'s `*.html` took `index.html`.** That is the sixth committed
    file that one rule has swallowed, by the file's own count. `git
    check-ignore` answers from the index for a tracked file and never reads the
    rules, so the guard passes `--no-index` (`tests/CLAUDE.md` § Guards that go
    quiet). Both new absence guards were made to fail on purpose before being
    trusted.
  - **`rangesOf`'s 99.9th percentile is inert at n ≤ 1000**, since
    `floor(0.999·n)` is `n − 1` there. One spiked point then sets the Δ/σ scale
    for a whole run on a short pattern. It bites as intended above that, and a
    snapshot decimates to `MAX_POINTS` = 4000. Pinned both ways and left
    alone, because 1430's fence was that nothing the page does changes. It is
    handed to 1426.
  - **This session's worktree was on an already-merged branch.** The
    session-start hook reported `ahead 2 / behind 0` and a clean tree, which
    reads as work to continue. A `git fetch` showed the branch's own PR (#337)
    had merged and that it was `ahead 1 / behind 1`. A commit pushed there
    would have been stranded. The work moved to `wp1430-the-page-is-a-file`,
    cut from `origin/main`, with the claim commit cherry-picked.

  **What `/code-review high --fix` changed.** It found one defect and four
  stale paths, and all five were taken. The defect: `HUE` and `DIST` were read
  in the boot fetch alone, so a boot `fetch` that rejects leaves the IIFE's
  promise rejected and `schedule()` unrun, while the `visibilitychange` and
  `hashchange` listeners still call `refresh()`. The list and the log recover
  on the next poll and `drawSnapshot` declines every write for the life of the
  tab, because `HUE` is still `null`. `readPage(payload)` now reads the block
  off whichever `/api/runs` answers first, and the `!HUE` guard stays as the
  belt. The four stale paths were docstrings naming `watch.py` in
  `viz/plotlyjs.py`, `history/events.py`, `tests/test_watch_app.py` and
  `tests/test_watch_browser.py`. One finding was declined by the pass itself
  and stands: `_static` lets an `OSError` out of `do_GET`, so a missing page
  file drops the connection instead of answering 500. The `.gitignore` comment
  promising a 500 has been corrected to say what happens.

  **Not done, deliberately.** `compare_app.py` is still a page in a python
  string. WP-1430 named it for 1429 and left it alone. No `viz/compare.py` row
  and no diagnostic code, since nothing here is a correction. Part 1 of the
  manual gained no chapter. The page's files are its own assets, and what that
  part documents is a user-facing surface.

  **Next:** 1426, then 1424, 1431, 1425, 1429, 1427, and 1428 last because it
  carries a decision. 1426 should start from its own `### Inherited`. It
  inherits both the `!HUE` guard, which has to survive whatever `drawSnapshot`
  becomes, and the ladder edge above.

- **2026-09-16** — created in the revision of 1424–1429, as the WP that
  should have come first.
