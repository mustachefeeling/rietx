# WP-1812 — GUI, textdoc, skill and manual for bodies

Milestone: rigid-bodies · Status: ⬜
Depends on: 1805
Priority: P4 2026-10-06 — the surfaces over a feature that already works from python

## Goal

A body round-trips through the `.rxt` textdoc, appears in the GUI, and has its own
generated skill reference and manual section. This is chunk R10 of issue #561, sized S/M.

## Context

- The skill's body verbs go in a separate generated `api-<shape>.md`, never `api.md`
  (root CLAUDE.md § skill; `make_api_index.py`'s docstring). `api.md` had 402 B of
  headroom on 2026-10-01.
- `tests/api_surface.py`'s partition has to go green, moving WP-1805's deferred names
  to documented.
- Manual Part 2 gets a section with the frame contract (WP-1804's closed-form M).
- Some of this lands inside WP-1805 and WP-1808 already: the help rows, `PLACES`, and
  both Part 2 equations. Check what is left before starting.
- It touches no v1.6 file.

## Non-goals

- Fragment file formats (WP-1813).

## Tasks

- [ ] Textdoc: a body block and its round trip
- [ ] Skill: the generated per-shape reference and its routing row
- [ ] Manual: Part 1 chapter, Part 2 frame section
- [ ] GUI: a body shown in the parameter and structure panels

## Acceptance

- The textdoc round trip reproduces a body.
- `tests/api_surface.py`'s partition is green.
- The skill caps (`tests/skill_caps.py`) pass without raising `api.md`'s.

## References

- Issue #561; PR #596.

## Handover log

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.
