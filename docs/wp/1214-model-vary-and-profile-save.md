# WP-1214 — Model: vary in the editor, and save instrument profile

Milestone: v1.2 · Status: ⬜
Depends on: WP-1201

## Goal

Refinement on/off flags can be set where crystallographers read the model
(the Model panel), through the same verb the parameter table uses; an
instrument profile can be saved from the GUI, not only loaded.

## Context

The user: "The natural place for crystallographers to set refinement on/off
flags is in Model panel, as the structure and instrument parameters are much
more readable there. Parameters is not a familiar interface." And: "Need a
GUI route for save instrument profile."

Findings (2026-08-25):

- `Model.svelte` has no vary control; its writes are `PATCH /api/params
  {values}` (`:416`), `PATCH /api/structure`, `PATCH /api/instrument`,
  `POST /api/structure/aniso` and the symmetry routes.
- `Params.svelte:253-269` renders the vary checkbox for `row.refinable` and,
  for a held row, no checkbox at all with `held_because` as the tooltip and
  the three reasons as three glyphs (WP-1011's rule). Per-row edits go as
  one `PATCH /api/params {values, vary}` with a console echo per path
  (`:118-126`); bulk goes by glob (`:111-114`). Server side `params_patch`
  applies `values` then each `vary` key (`session.py:567-595`), one
  `set_vary` node per key.
- `GET /api/structure` is `structure.model_dump()` (`session.py:740`), so
  every `Parameter` carries `vary`; `held_because` is a `ParameterRow`
  property only. `Model.svelte` already joins the params rows by path
  (`byPath`, `:326`; `heldReason()`, `:602-606`) and refetches `api.params()`
  in `load()` (`:364`). The missing piece is the widget and a `vary` key in
  the existing `api.patchParams` call.
- `save_instrument_profile` (`io/instrument_profile.py:40-63`) has no
  caller in `src/rietx/gui` or `gui/src`; the GUI only loads
  (`imports.py:340-356`, `Model.svelte:834-837, 1117-1120`). The export
  family (`server.py:274-277`, `session.export`, `session.py:2178-2212`) is
  **result-gated** (`_need_result`, 409 `NO_RESULT`) and writes under
  `exports/` (`_export_target`, path-confined); there is no download route.
- Format: tag `instrument_profile` (`_about.py:55`), version `"1"`; the
  writer zeroes displacement and transparency and drops the specimen terms.

Design: a `vary` toggle beside every editable value in Model (cell edges,
occ, Biso, DOFs, ADPs, the strain and size terms, every instrument field);
a held value shows the reason, no toggle (the WP-1011 rule); toggles
accumulate with the value edits and go in the same `PATCH`, one node per
path, echoed as `ref.set_vary(...)`. `POST /api/export/instrument_profile`
joins the family but is **model-gated** (`_need_project`, not
`_need_result`), writes `exports/<name>.json` via `save_instrument_profile`,
and the button sits beside `Load profile…` with the written path shown.

## Non-goals

- The structure table's shape (WP-1215), the instrument grid (WP-1216).
- A download route: exports stay files under the project, as today.

## Tasks

- [ ] `Model.svelte`: the vary toggle on every editable field; held reason
      rendering shared with Params (`lib/table.ts` helper); the `vary` key
      in the apply; `model.test.ts` on the payload.
- [ ] `POST /api/export/instrument_profile` (model-gated) + the button;
      `test_gui_server.py` round-trips save → `load_instrument_profile`
      with every `vary` false and the specimen terms cleared.
- [ ] Manual: `using/model.md` (vary from the editor), `files.md` (the
      profile's save route).
- [ ] Browser pass; dist.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q -k "profile or vary"
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1011 (a held row gets no checkbox), WP-1014 (what the table owns).

## Handover log

- **2026-08-25** — created from the v1.2 triage.
