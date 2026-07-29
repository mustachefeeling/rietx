# WP-1010 — Frontend scaffold: build, committed dist, shell, plot, console

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1008

## Goal

A `gui/` TypeScript workspace whose build writes committed static assets
into `src/pxrdref/gui/static/`, plus the app shell, the obs/calc/diff plot
panel, and the console — the foundation every later frontend WP builds on.
Users installing the wheel never need node.

## Context

- **Svelte 5 (runes) + Vite + TS + vitest**, `package-lock.json` committed.
  Fine-grained reactivity without a virtual DOM is exactly the
  parameter-table workload (hundreds of independently-updating cells);
  ~12 kB runtime; compiled output diffs tolerably as a committed dist.
  Not load-bearing: the sync engine, decimation and fnmatch logic are
  framework-free `lib/` TS either way. Layout:

  ```
  gui/                      # TS workspace, never ships in the wheel
    package.json  package-lock.json  vite.config.ts
    src/  App.svelte  api.ts  panels/{Plot,Params,Plan,History,Report,Console,Text,Structure,Series}.svelte
          lib/{sync,decimate,fnmatch,sse}.ts
  src/pxrdref/gui/static/   # COMMITTED build output + build-info.json + help.json
  ```

- Build writes **stable filenames** (`app.js`, `app.css`, `vendor-cm.js` —
  no content hashes, so dist diffs stay reviewable) plus `build-info.json`
  (sha256 over sorted `gui/src/**` + lockfile).
- **Dist freshness is enforced twice**: `tests/test_gui_dist.py` recomputes
  the source hash in pure Python (no node in the default CI path) and fails
  with "run `npm --prefix gui run build`"; and `gui.yml` rebuilds on
  gui-path pushes and runs `git diff --exit-code`. The same test asserts
  `index.html` references no `https?://` asset — the offline guarantee,
  executable.
- plotly.js keeps being served from the installed Python package
  (`compare_app.py:102` trick via the WP-1008 `/plotly.js` route — no
  4.5 MB vendored copy, version locked to the `[gui]` extra).
- Plot panel: obs/calc/diff/ticks on Scattergl, client-side min/max
  decimation ported from `viz/html._minmax_decimate` (`viz/html.py:24`) to
  `lib/decimate.ts`; zoom refetches full-res via `/api/result/window`.
  Console: SSE-fed, one line per event with the API-echo per action (the
  DESIGN.md console-pane story: the log doubles as a session script).
- Shell: light/dark theming reusing compare's CSS-custom-properties
  approach.
- **CI cost, priced** (the WP-1002 rule): `gui.yml` triggers only on
  `gui/**` and `src/pxrdref/gui/static/**` — node setup + `npm ci` + build +
  diff + vitest ≈3 billed min; at an aggressive 40 gui-touching
  pushes/month ≈120 min against the 2000/month free tier (303 scheduled
  today). The per-push `ci.yml` job is unchanged at 5 billed min — the
  dist-hash test is milliseconds and needs no node. Goes to zero when the
  repo goes public.
- Snappiness budget (measured and reported in handovers, ranges not
  figures): interaction→paint <100 ms (decimate to ≤8 k pts/trace above
  20 k); run click→feedback <50 ms; SSE appends batched per animation
  frame. Report (don't gate): first-load JS ≤250 kB gz excluding plotly;
  boot-to-interactive <1.5 s. A raw Float64 array endpoint is the
  pre-designed fallback if a 50 k-point pattern's ~1.6 MB JSON measures
  worse than expected.

### Inherited

From the **v1.0 GUI plan** (2026-07-29): if the rebuild-diff freshness check
proves flaky cross-OS (minifier nondeterminism), downgrade `gui.yml` to
comparing `build-info.json` only and record the measurement in the handover
log — pre-authorised fallback, not a new decision.

## Non-goals

- No parameter editor, history panel, text pane, structure viewer, series
  (WP-1011…1016) — the panels exist as stubs wired to routes only as far as
  the plot + console need.
- No Playwright — vitest units only; server-level tests cover the contracts.
- No SSR, no router, no state library beyond runes.

## Tasks

- [ ] `gui/` workspace: Svelte 5 + Vite + TS + vitest, lockfile committed;
      build → `src/pxrdref/gui/static/` with stable filenames +
      `build-info.json`.
- [ ] `tests/test_gui_dist.py`: pure-Python source-hash freshness check +
      the no-external-asset (offline) assertion.
- [ ] App shell + theming + `api.ts` + `lib/sse.ts` (SSE with `?since=`
      resume, `?poll=1` fallback).
- [ ] Plot panel (obs/calc/diff/ticks, `lib/decimate.ts` port of
      `_minmax_decimate`, window refetch on zoom) + vitest decimation
      envelope property test.
- [ ] Console panel on SSE with the per-action API-echo line.
- [ ] `.github/workflows/gui.yml` (gui-paths trigger, node + build +
      `git diff --exit-code` + vitest), priced in the workflow file per the
      WP-1002 rule.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_dist.py tests/test_gui_server.py -q
npm --prefix gui ci && npm --prefix gui run build && git diff --exit-code src/pxrdref/gui/static
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

Report in the handover (don't gate): first-load JS size, boot-to-interactive.

## References

- `viz/html.py:24` `_minmax_decimate` — the algorithm to port.
- DESIGN.md §Outputs, human-GUI paragraph + its 2026-07-29 amendment (stack
  decision).

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.
