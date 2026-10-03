# WP-1539 — the declared optics reach every caller and every reader

Milestone: unscheduled · Status: 🔄 2026-10-03 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: — (1445 shipped the field)
Priority: P3 2026-10-03 — a workaround covers it: the caller passes `source=` to `diagnose` directly, and an undeclared source runs the screen as before

## Goal

`Source.kbeta` (WP-1445) reaches the three places that still cannot set or read it.
A library caller of `auto_background` can hand it a source. The import wizard turns a file's
`beam_optics` into `Source.kbeta`. The brml and rasx readers record the optics they carry.

## Context

WP-1445 added `Source.kbeta` (None, filter, monochromator, mirror). The ghost screen skips the
Kβ and tungsten searches for a neutron source and for a diffracted-beam monochromator
(`background.diagnostics.ghost_searches`). A filter or a mirror is recorded and changes nothing,
because the screen still finds a leak injected at 2 % of Kα on two real patterns.
Empty means "nobody said", and the screen runs as before. The xrdml reader records optics as
`beam_optics` (`io/formats/base.py:196`, `io/formats/xrdml.py:426`).

Three gaps the 1445 review found:

1. `auto_background` (`background/auto.py:32`) takes no `source=`, so it is the one library
   caller of the screen that cannot reach the skip. A public argument moves `api.md` and the
   manual's API partition with it.
2. Nothing maps `beam_optics` to `Source.kbeta`. An incident-beam monochromator and a
   diffracted-beam one are different cases, and 1442 measured the premise only for the second.
   The mapping has to decide which a file describes before it writes `monochromator`.
3. brml and rasx files carry optics that their readers drop.

Skill caps are tight: `api.md` sits within bytes of its ceiling and `surprises.md` of its
budget, so a new public name there pays with a cut (`tests/skill_caps.py`).

No open WP owns this: 1454 (`auto_background`'s choices) closed on 2026-09-24 and 1442's
screen work closed with 1445. Checked against the index on 2026-10-03.

## Non-goals

- A `kbeta_filter=` preset argument. WP-1445 dropped it on purpose: it would cost the wizard a
  field and a rebuilt dist for a value that changes nothing.
- Making a filter or a mirror skip a search. The injection ladder says it would hide real findings.

## Tasks

- [x] `auto_background(source=)`, passed to the screen; `api.md` and the manual partition
      move with it, paid for by a cut under the skill caps.
- [ ] The wizard maps `beam_optics` to `Source.kbeta`, after deciding incident versus
      diffracted monochromator. State what a file with neither says.
- [ ] brml and rasx record optics, when a fixture carrying them is in hand.
- [ ] Tests, each with a control that is not vacuous (the 1445 review caught one that was).
- [ ] Skill: the routing row, or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_peak_picking.py tests/test_readers.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

WP-1445's handover log, 2026-10-03; WP-1442's injection ladder.

## Handover log

### 2026-10-03 — filed

Filed from WP-1445's three open follow-ups. No open WP owns them (see Context), so this is a
new file and not a fold. Written by Claude.
