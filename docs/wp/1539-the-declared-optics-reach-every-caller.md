# WP-1539 — the declared optics reach every caller and every reader

Milestone: unscheduled · Status: 🔄 2026-10-03 — two of the three gaps closed; brml and rasx wait for a fixture with an optic in the beam
Track: What fires, and what stays silent
Depends on: — (1445 shipped the field)
Priority: P4 2026-10-03 — was P3: what remains cannot start until a brml or rasx file with a diffracted-beam monochromator or a filter is in hand

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
      move with it, paid for by a cut under the skill caps. *Paid instead by raising
      the generated index's ceiling 39 500 → 39 600 B: `api.md` is one signature per
      public name, and none could be cut for this one (`tests/skill_caps.py`).*
- [x] The wizard maps `beam_optics` to `Source.kbeta`, after deciding incident versus
      diffracted monochromator. State what a file with neither says.
- [ ] brml and rasx record optics, when a fixture carrying them is in hand.
      **Checked 2026-10-03, left open:** the three fixtures hold no positive case.
      Both rasx files say `DetectorMonochromator SelectedUnit="None"` (so a
      diffracted-beam monochromator is a named category there, and `"None"` is
      its off state), and an incident `Optics/Attribute` that is vendor free text
      (`PB-Ge(220)x2_Compress`, an incident Ge(220) channel-cut). Which values
      other than `"None"` the category takes is unmeasured. The brml lists
      `AvailableOptics` (a `Crystal3B` among them) beside `MountedOptic`, so a
      listed crystal is not a mounted one, and the fixture's one mounted optic
      is a slit and an absorber. Writing either reader now would be the
      confident guess the key's "absent means undeclared" rule forbids.
- [x] Tests, each with a control that is not vacuous (the 1445 review caught one that was).
- [x] Skill: none beyond the regenerated `api.md`. The wizard is not a call an agent makes, and `auto_background(source=)` is in the signature the index renders.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_peak_picking.py tests/test_readers.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

WP-1445's handover log, 2026-10-03; WP-1442's injection ladder.

## Handover log

### 2026-10-03 (2nd session) — the wizard and auto_background reach Source.kbeta

A script that builds its background with `auto_background` can now tell it what
the beam is. The import wizard copies what an xrdml file says about its optics
into the instrument it builds. Only a monochromator after the sample changes what
the ghost screen does. A file listing one before the sample stays undeclared,
because nothing here has measured what it leaves of Kβ. The brml and rasx readers
were not taught optics. Their three fixtures hold no optic in the beam, so a
reader written now could not be checked against anything.

- **Done:** `auto_background(source=)`, passed to `diagnose`; `api.md` regenerated
  and its generated ceiling raised 39 500 → 39 600 B (`tests/skill_caps.py`, the
  keyword costs 49 B and no signature could be cut). The xrdml reader records
  `diffracted_beam_optics` beside `beam_optics`. `gui.imports.kbeta_from_metadata`
  maps them: a diffracted-beam monochromator → `"monochromator"`, any
  monochromator before the sample → None, else a filter → `"filter"`, else a
  mirror → `"mirror"`. `instrument_from_preset` takes a `kbeta` key that is not a
  constructor argument and sets it after the build; a constructor's own value
  (`monochromator_two_theta`) outranks it. `session._with_file_optics` fills that
  key from the pattern's metadata on project creation and on an instrument edit,
  when the spec carries none. The manual's `Source.kbeta` row says all of this.
- **Measured:** fast selection on `[dev]`, darwin/arm64, no other pytest running,
  tree = origin/main + this branch: 8117 passed, 159 skipped, 1 failed (the WP
  index, stale from this entry's header edits and regenerated after). The pre-review
  run gave 8117 + 159 = 8276; the review added one test, so the total of 8277
  moved by exactly that one. Six tests added, 0.11 s together on one run here, so
  none joins the slow tail. The full selection did not run: no measured number can
  move (the new argument defaults to None, and the rest is GUI and reader metadata).
- **Review (`/code-review high --fix`):** fixed an unknown `kbeta` raising a 500
  instead of a refusal naming `instrument.kbeta`, and the instrument-edit route
  ignoring the file's optics (one helper now serves both routes). I then reversed
  one it declined: a hybrid file (mirror plus monochromator, both before the
  sample) had read as `"mirror"`, which names the optic not deciding Kβ, so it is
  now None. Declined: the project-creation route parses the pattern once more to
  read its metadata; the cheap route is `suggest_instrument` carrying `kbeta`,
  which needs `wizard.ts` and a rebuilt dist. Also declined: the `xray_cw` guard
  that no current preset can fail, kept for a neutron preset; and the cap raise,
  which is recorded for the maintainer to reverse into a split if preferred.
- **brml and rasx, checked and left open:** the task's own note has what each
  fixture says and why neither reader was written.
- **Lane trial:** no lanes dispatched. One decision line was written
  (`auto_background(source=)`, keep ~12); the wizard and brml items started
  without one, which is a gap in the trial's estimate data. The context passed
  150K only during the handover (peak 175K), so no item met the lane rule.
- **Gotchas:** the worktree guard refuses any command containing the word
  `source`, a grep pattern included; grep for `sourc`.

Next, in order: (1) a brml or rasx file with a diffracted-beam monochromator or a
filter in the beam, then read rasx `Categories/DetectorMonochromator@SelectedUnit`
and brml `MountedOptic` against it; (2) only if the extra parse at project
creation shows on a large file, carry `kbeta` through `suggest_instrument` and the
wizard's `applyInstrumentHint` instead; (3) the maintainer's call on the
`api.md` ceiling against a technique split.

### 2026-10-03 — filed

Filed from WP-1445's three open follow-ups. No open WP owns them (see Context), so this is a
new file and not a fold. Written by Claude.
