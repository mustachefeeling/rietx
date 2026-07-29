# WP-1008 — GUI server, session model, `pxrdref gui`

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1004, WP-1005, WP-1006, WP-1007

## Goal

`pxrdref gui [PROJECT.pxrd]` serves a localhost web app whose HTTP surface
covers the full loop — project, params, plan, run/cancel, events, result,
report, history, export — with every verb a plain method on a `GuiSession`
so the transport layer stays swappable (the Tauri seam).

## Context

- **Stdlib `http.server`, decided.** It is the repo precedent twice —
  `compare_app.py` (`ThreadingHTTPServer` at `:172`, handler factory
  `_handler(state)` at `:113`) and `watch.py` (`:117`, port 8899). Zero new
  deps preserves the base-install discipline (`[gui]` = plotly only);
  offline/CSP/air-gap safe; a single-user localhost app with ~25 routes
  gains nothing from FastAPI/uvicorn (+15 MB and async ceremony). SSE works
  fine on `ThreadingHTTPServer`. Snappiness lives in payload design and the
  frontend — `pxrdref compare` already proves the loop feels instant.
- `src/pxrdref/gui/session.py` — `GuiSession` holds the `Project`,
  `Refinement`, a lock, the run state machine (`idle | running |
  cancelling`), the `CancelToken` (WP-1006), and a seq-numbered event ring
  buffer with a `threading.Condition` for SSE followers; one worker thread
  (the `compare_app._State` pattern, `:35` — lock, pending queue, daemon
  worker). **Every verb is a plain method here and `server.py` is only
  transport** — that is the Tauri/framework seam. Mutating verbs return 409
  while a run is in flight, so the GUI *structurally* cannot mutate a
  running fit's compiled state (frozen-per-stage discreteness, enforced at
  the session boundary rather than by discipline).
- Routes (all bound 127.0.0.1; Host header checked against DNS rebinding):

  ```
  GET  /  /assets/*  /plotly.js        (plotly from the installed package — compare's trick, compare_app.py:102)
  GET  /api/capabilities  /api/version     POST /api/shutdown
  POST /api/project/new|open   GET/POST /api/project(/save)   GET /api/recent
  POST /api/upload/pattern|cif|instrument                      (lands in WP-1014)
  GET/PATCH /api/structure  /api/instrument  /api/params    GET/PUT /api/plan   GET /api/plans
  POST /api/run  /api/cancel   GET /api/run/state
  GET  /api/events           (SSE; ?since=seq replay; ?poll=1 JSON fallback)
  GET  /api/result   /api/result/window?lo=&hi=   /api/report   POST /api/report/apply   (apply lands in WP-1012)
  GET  /api/history  /api/history/diff  /api/history/compare
  POST /api/history/{checkout,branch,tag,annotate}
  GET/PUT /api/textdoc       GET /api/structure3d       POST /api/export/{cif,reflections,qpa,html,result_json}
  ```

  This WP lands the session + routing skeleton and every route that needs
  only WP-1004…1007; routes marked for later WPs 404 cleanly until then.
- History verbs live on `Refinement` (`checkout` `refine.py:182`, `branch`
  `:202`, `merge` `:250`, `cherry_pick` `:309`), tree read-side on
  `RefinementTree` (`compare` `history/tree.py:231`, `diff` `:249`).
- Boot: `pxrdref gui [PROJECT.pxrd] [--port 8731] [--no-open] [--machine]`.
  Compare owns 8730 (`compare_app.py:32` `DEFAULT_PORT`); fall back to
  port 0 if busy. `--machine` prints a JSON boot line (port, project path,
  pid) — the Tauri seam. One project per process. CLI dispatch is
  hand-rolled in `cli.py:13` (`watch` `:26`, `compare` `:31`, `html` `:35`)
  — add `gui` there, argparse inside `gui/server.py:main` like the siblings.
- Run events are teed to `<project>/live/events.jsonl` so `pxrdref watch`
  and the GUI stay two views of one stream.

### Inherited

From the **v1.0 GUI plan** (2026-07-29): the HTTP routes are declared
**provisional** at v1.0 — schemas frozen, wire surface not (recorded in
WP-1003's `### Inherited`). Don't burn effort on wire-level backcompat here.

## Non-goals

- No frontend (WP-1010) — this WP is testable entirely over HTTP with the
  static dir empty.
- No auth/TLS/multi-user — localhost, one user, Host-header check only.
- No upload sniffing (WP-1014), no textdoc semantics (WP-1009), no report
  apply (WP-1012), no series (WP-1016) — their routes arrive with them.

## Tasks

- [ ] `src/pxrdref/gui/{__init__,session}.py`: `GuiSession` — verbs, lock,
      state machine, ring buffer + `Condition`, worker thread, 409 rule.
- [ ] `src/pxrdref/gui/server.py`: route table → session verbs; SSE with
      `?since=` replay and `?poll=1` fallback; Host-header check;
      `/plotly.js` from the installed package; `POST /api/shutdown`.
- [ ] `cli.py`: `gui` subcommand (`--port/--no-open/--machine`, port-0
      fallback); tee run events to `live/events.jsonl`.
- [ ] `tests/test_gui_server.py`: real server on port 0 — project create →
      params PATCH → run → SSE events → result → history checkout → export;
      409 while running; cancel honoured; Host-header rejection.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- `compare_app.py` — `_State`, `_plotly_js`, port; `tests/test_compare_ui.py`
  `server` fixture (`:211`) — the port-0 live-server test recipe to copy.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan. Precedents verified: the
  `_State` pattern, the `/plotly.js` trick, port ownership (compare 8730,
  watch 8899), and the hand-rolled CLI dispatch.
