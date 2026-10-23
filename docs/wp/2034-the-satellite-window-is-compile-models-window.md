# WP-2034 — the satellite arm generates over `compile_model`'s window, not a copy of it

Milestone: magnetic · Status: ⬜
Depends on: — (1908, closed: the apparent-position shift both windows widen by; 1326, closed: the arm)
Priority: P3 2026-10-23 — a satellite that should be ranked can go unenumerated near either end of the range, unmeasured on a real pattern; the fix is one shared helper

## Goal

The satellite report arm enumerates reflections over the same Bragg-angle window
`compile_model` uses, through one helper both call. A satellite whose image
under any emission line lands inside the fitted range is enumerated.

## Context

- **Found by `/code-review high` on PR #942 (WP-1908), and left there as
  outside that diff.** It passed to 1326's `### Inherited` on 2026-10-15 and
  moved here at 1326's close, by the maintainer's decision of 2026-10-23.
- **Still true at `12f459e`.** `report/satellites._generation_window`
  (`report/satellites.py:142`) scans the 33-point shift grid that
  `compile_model` scans. It returns
  `(max(tt_min - hi_shift, 0.05), min(tt_max - lo_shift, 179.0))`.
  `compile_model`'s window (`model/forward.py:3812-3813`) subtracts the zero,
  adds `REFLECTION_MARGIN_DEG` (0.5°) on both sides, and caps at 180°. The
  arm's copy differs in three ways. It has no margin. It caps at 179°. And it
  applies the low cutoff in the shortest line's frame without translating it
  from the longest line's. So on a Cu Kα doublet, a satellite whose Kα1 image
  falls just below `tt_min` while its Kα2 image lies inside is never
  enumerated. Both callers (`:175`, `:347`) filter on the apparent position
  afterwards, so a superset is harmless and a subset is the defect.
- **Unmeasured on a real pattern.** No fixture yet puts a satellite in the
  strip either copy disagrees on.

## Non-goals

- What the arm ranks, or the candidate set (WP-1418's M-8).

## Tasks

- [ ] A test that fails on the current tree: a synthetic doublet pattern with
      a satellite whose Kα1 image lies below `tt_min` and whose Kα2 image lies
      inside, which the arm must enumerate.
- [ ] One helper, called by `compile_model` and by the arm, so the margin, the
      cap and the per-line frame are written once. Every satellite and
      reflection list in the tree is unchanged except where the old window
      cut one off. Name each list that changes.
- [ ] Skill: none expected, since no field or code changes.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_satellites.py tests/test_satellites_acceptance.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- [WP-1908](1908-a-tick-misses-the-displacement-shift.md) (PR #942);
  [WP-1326](1326-satellites-without-a-moment.md).

## Handover log

- **2026-10-23** — created by WP-1326's close, from its `### Inherited` entry
  of 2026-10-15. No open WP owns the arm's window. 1418's M-8 rewrites the
  candidate generator, not the angular window it generates over.
