# WP-1009 — Project text document: format + parser

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1004, WP-1005

## Goal

A line-oriented text rendering of the project (`.pxt`) with a single
server-side parser: `render(session state) → text` and `parse(text) → delta +
errors`, deltas applied as the same public verbs the forms use. The format
lands **before** the editor pane (WP-1013) so it is settled independently of
CodeMirror.

## Context

- **A line-oriented DSL, not TOML/YAML** — those lose the aligned columns
  that rectangular selection exists to bulk-edit, and their parse errors
  don't speak dot-paths. `@` marks vary (TOPAS muscle memory); bare value =
  fixed; blocks scope dot-path prefixes; `#` comments round-trip. Example:

  ```
  pxt 1
  project "NAC 11-BM"
  pattern "11BM_NAC.fxye"            # sha256 9f3ac2…  45,001 pts  3.0–155.0°
  mode rietveld
  limits 3.0 60.0

  phase 0 "NAC"                      # Ia-3d, cubic: b,c tied to a
    cell.a         @ 10.251285       min 10.1  max 10.4
    scale          @ 1.234e-6
    atoms.0.biso   @ 0.52            # Na
    atoms.1.biso     0.61            # Al  (fixed)

  instrument
    zero_shift     @ 0.00210
    background.c*  @                 # glob line: frees c0..c5

  plan mccusker_default
  stage cell     free phases.*.cell.*                       max_iter 100
  ```

- Locked/tied entries render as read-only annotations (`cell.b = tied
  cell.a`); editing one is an apply error **naming the tie** — same message
  the WP-1004 verb raises, surfaced with a 1-based line number. Glob lines
  are bulk-edit sugar, normalised to per-parameter flags on the next render
  (canonical output never emits them). Unknown keys are errors
  (`extra="forbid"` spirit).
- Deltas are applied as WP-1004's public verbs (`set_vary`, the set-value
  verb, plan PUT), so a text apply shows up in the console as API calls and
  in history as nodes — identical to a form edit. All-or-nothing: any error
  in the delta applies none of it.
- `src/pxrdref/gui/textdoc.py` carries `FORMAT_VERSION` (the `pxt 1` line);
  WP-1017 injects it into the manual as a fenced constant, so a format bump
  that misses the manual fails the build.
- **The parser lives only in Python.** The frontend gets a regex highlighter
  and no grammar (WP-1013), so there is no dual-parser drift to test.
- Server routes: `GET/PUT /api/textdoc` on the WP-1008 skeleton — GET
  returns `{text, revision}`; PUT takes `{text, base_revision,
  validate_only}` and CAS-rejects (409) a stale `base_revision`. The sync
  state machine on top is WP-1013's; this WP only guarantees the primitive.

### Inherited

From **WP-1004**: locked/tied refusal messages come from the verbs — quote
them, don't restate them, so the two surfaces cannot disagree.

From **WP-1005** (project container, landed 2026-07-30) — the sketch above is
missing one line and mis-sources two others:

- **`excluded 7.5 8.0 / 24.0 25.2` (or equivalent) must be in the format.**
  Excluded regions are protocol — CLAUDE.md's rule is to mirror another code's
  excluded regions or not compare Rwp at all — and they are in **neither** the
  pattern file **nor** `RefinementState`, so a history node cannot say what was
  excluded when it ran and the fingerprint does not change when they do. The
  project document is the only record (`ProjectDoc.excluded_regions`), which
  makes the text view the only place a human will ever *see* them. Apply through
  `Project.set_excluded_regions`, which is one verb precisely so the document and
  the `PatternData` cannot disagree. (Whether `RefinementState` should carry them
  is parked in WP-1003's `### Inherited`; the text document needs them either
  way.)
- The `pattern` comment should quote `DataRef`, which already has every field the
  sketch invents: `sha256`, `n_points`, `two_theta_range`, plus **`has_sigma`** —
  worth rendering, since "weights from the file's esd column" vs "Poisson
  fallback" is a correctness property of the fit that is otherwise invisible. And
  a pdCIF's **`block`** must render (it is in `DataRef.options`): the same file
  reads as a different pattern without it.
- `mode`, `limits` and `plan` come from `ProjectDoc` (the *next* run's settings),
  not from the head node (what a *past* run used). The two legitimately differ,
  and rendering the wrong one would show a user a plan they did not select.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): **reserve a
`peaks` block in `FORMAT_VERSION` now**, so WP-1027 fills it in without a
format bump. Two properties settle its design. Peaks are **not refinable
parameters**, so they carry **no `@` marker** — that absence is the visual
distinction from every other block. And only two of its columns are editable
on apply: `2theta` (which becomes a `move_peak` + group refit) and `flags`
(a `set_peak_flags`); esd, fwhm and intensity are *derived* and are
regenerated on the next render, so an edit to them must be rejected rather
than silently discarded. Sketch:

```
peaks 20                              # pick_peaks(min_sigma=5.0, shape=tchz)
  #      2theta      esd     fwhm         I    flags
   0     8.4712   0.0009   0.0812     10420
   1    10.7743   0.0011   0.0834      3310   impurity
```

From **WP-1008** (GUI server, landed 2026-07-30): `GET/PUT /api/textdoc` are
**already reserved** in `gui.session.RESERVED_ROUTES` and answer 404 naming this
WP, so filling them in is adding two entries to `gui.server.ROUTES` and two
methods to `GuiSession` — no routing work. Three things that shape the format:

- **The preset a project chose is not stored.** `ProjectDoc.plan` is an expanded
  `PlanSpec` with no name, so `GET /api/plan` *derives* `preset` by comparing the
  stored spec against all seven registry presets (`gui.session._matching_preset`,
  `null` for an edited plan). If the text document wants to render `plan:
  mccusker_default` rather than eight stage blocks, quote that helper — do not
  add a name field to the document, which would be a second authority that can
  disagree with the stages beside it.
- **Selecting a preset expands it through the mode**, because `Project.fit`
  passes `doc.plan` verbatim: `mccusker_default` under `lebail` stores
  `profile_only`'s stages. A text document round-trip must not "helpfully"
  re-collapse that back to the name the user typed.
- **Settings persist on the verb, not on Save** (the GUI writes `project.json`
  on every settings mutation), so a text-document edit that changes settings
  should behave the same way rather than waiting for a save the UI never shows.

## Non-goals

- No editor, no CodeMirror, no sync engine (WP-1013).
- No three-way merge — CAS conflict is a 409, full stop.
- No reading `.pxt` as a project interchange format (the project *is* the
  `.pxrd/` dir; the text pane is a view).

## Tasks

- [ ] `src/pxrdref/gui/textdoc.py`: `FORMAT_VERSION`, `render`,
      `parse → (delta, errors)` with 1-based line numbers on every error.
- [ ] Delta application through the WP-1004 verbs, all-or-nothing;
      locked/tied refused with the verb's own message + line number.
- [ ] `GET/PUT /api/textdoc` with CAS revisions on the WP-1008 server.
- [ ] `tests/test_textdoc.py`: hypothesis round-trip — `render → parse →
      render` is a fixed point over generated projects (globs normalised
      away, comments preserved); every error carries a line number;
      glob-line expansion matches Python `fnmatch` semantics.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_textdoc.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Profex/TOPAS-jEdit lineage: continuous validation, explicit apply.
- Parameter path conventions: dot-separated, fnmatch globs, no brackets
  (CLAUDE.md Conventions).

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.
