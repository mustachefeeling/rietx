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
