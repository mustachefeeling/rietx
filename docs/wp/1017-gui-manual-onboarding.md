# WP-1017 — GUI manual, in-app help, onboarding

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1011…WP-1016 (soft — chapters can land as their panels do)

## Goal

The GUI is documented where the theory manual lives, helps from inside the
app, and onboards a first-year PhD student without a wizard that hides the
real UI.

## Context

- **Inside `docs/manual/`** — same Sphinx/MyST/furo tree, same `-W`, same
  guards (`tests/test_manual.py`); a separate doc root would need its own
  guard set for no benefit. Three layered chapters matching the audience
  gradient:
  - `gui-quickstart.md` — install (`pip install pxrd-refine[gui]`) → open →
    fit → read the report.
  - `gui-guide.md` — panel by panel, including *when to branch* (the
    history worktree is the differentiator; teach the workflow, not just
    the buttons).
  - `gui-power.md` — the **normative `.pxt` text-format spec**,
    keyboard/palette, and the console-to-script transition — the API-echo
    story as the on-ramp to the Python API.
- The manual's anti-divergence rules apply and are executable
  (`tests/test_manual.py`): fenced constants are MyST substitutions
  injected from the live package in `docs/manual/conf.py` — **the pxt
  format version becomes a fenced constant injected from
  `gui.textdoc.FORMAT_VERSION`**, so a format bump that misses the manual
  fails the build. A new fenced constant needs a `conf.py` line *and* a use
  in a chapter.
- In-app help: tooltips from `static/help.json`, each with a "learn more"
  anchor into the built manual; `tests/test_gui_help.py` asserts every
  anchor exists (dead-link guard, same spirit as `test_manual.py`).
- First run: a **non-modal progressive checklist** (Load pattern → Load
  structure → Check instrument → Run → Read the report) — never a modal
  wizard; state in `ProjectDoc.ui`.

### Inherited

From the **v1.0 GUI plan** (2026-07-29): `gui-power.md` is where the
provisional status of the HTTP routes and `.pxt` format is stated
user-facing (schemas frozen at v1.0, wire/text surfaces provisional) —
WP-1003 states it in the release notes; this chapter is the other half.

## Non-goals

- No screencasts/video, no hosted docs decisions (that is WP-1003's
  release scope).
- No autodoc API reference (0604's decision stands — a rendered API
  reference is its own document with its own failure modes).
- No restating theory — the GUI chapters link into the existing theory
  chapters rather than duplicating equations.

## Tasks

- [ ] `gui-quickstart.md` + toctree wiring; builds `-W`-clean.
- [ ] `gui-guide.md` — panel by panel, when-to-branch workflow section.
- [ ] `gui-power.md` — normative `.pxt` spec with `FORMAT_VERSION` as a
      fenced constant (conf.py line + chapter use), keyboard/palette table,
      console-to-script story.
- [ ] `static/help.json` + tooltip wiring + "learn more" anchors;
      `tests/test_gui_help.py` dead-link guard.
- [ ] First-run progressive checklist (non-modal), persisted dismissal.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_gui_help.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-0604's manual architecture (fenced constants, `*Source:*` lines,
  cited-bib guard) — the machinery these chapters extend.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.
