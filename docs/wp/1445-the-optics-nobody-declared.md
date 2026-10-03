# WP-1445 — the optics nobody declared: a source that cannot emit the line

Milestone: unscheduled · Status: 🔄 2026-10-03 — the seven tasks landed; three follow-ups remain (see Handover log)
Track: What fires, and what stays silent
Depends on: — (1442 soft)
Priority: P2 2026-09-23 — an X-ray ghost search fires on a neutron source; the schema decision is this WP's first task

## Goal

An instrument declares what its beam can carry, and the contamination screen
reads it. A neutron source never runs an X-ray ghost search, and a tube behind
a filter or a monochromator either narrows the ratio window or skips.

## Context

WP-1442's task 5, split out on 2026-09-22 because it needs a schema decision
and three readers taught new file paths, and because a schema seam decided
inside a diff about a contamination screen gets waved through.

**1442 removed the live wrong answer this was filed against.** The screen is
now joint: it reports nothing unless `GHOST_MIN_PARENTS` = 5 of the eight
strongest reflections carry a line at one common ratio. Measured on the tree
at that close, the BT-1 neutron pattern goes from three flags to none and the
17 monochromated round-robin patterns from 68 to none. So what is left here is
a **robustness gate, not a defect with a victim**: the searches still run where
they cannot be right, and they are silent because the joint bar is doing the
work rather than because anybody told the screen what the optics are.

**Nothing records whether the beam can carry Kβ** (measured 2026-09-22 on
`75ac934a`). Three findings, and the first is the one that reframes the task:

- `Instrument.bragg_brentano(monochromator_two_theta=)` **consumes** its
  argument and discards it. It computes the polarisation factor
  K = 1/(1 + cos²2θ_m) at construction and stores that number on
  `Source.polarization`; `Geometry` has no monochromator field, and
  `schemas/instrument.py` has no other. So the 17 round-robin fixtures, every
  one of which passes 2θ_m ≈ 26.6° for its graphite monochromator, carry the
  fact only as `polarization = 0.556` against an unpolarised 0.5 — a number a
  consumer would have to invert, and one a *incident*-beam monochromator does
  not produce at all.
- A Kβ **filter** (Ni foil on Cu) is not declarable anywhere.
- The vendor readers parse no optics element. The xrdml reader (`_read_scan`)
  takes `anodeMaterial`, `usedWavelength` and `radius` from
  `<incidentBeamPath>` and stops; brml and rasx read none either. The worked
  case is the demo notebook's file
  (github.com/LLongley94/rietx_demo, `10102023 LLTest_B4_...xrdml`), which
  declares `<xRayMirror>` — a W/Si graded elliptic focusing mirror,
  `hybrid="false"` — no `<filter>` and no `<monochromator>`, plus a PIXcel1D
  with a 25-80 % pulse-height window. A graded mirror suppresses Kβ without
  removing it, so that instrument's honest answer is "narrowed", not "skip".

**The neutron half needs no schema and is the cheap one.**
`identify_anode(1.5404)` returns `"CuKa"` for the BT-1 pattern
`mg090.Cu311.gsas`, because it matches the wavelength alone and consults no
source kind. `pick_peaks` already holds the `Instrument` and could hand
`flag_ghosts` the source kind today; `diagnose(data, wavelength=...)` holds no
instrument at all, so that side needs a new argument whatever is decided about
optics.

**Where the decision bites.** `Source` owns the emission lines, so "which lines
the beam carries" reads naturally there. `Geometry` owns the beam path and
already owns `mu_t`, `goniometer_radius_mm` and the aberration parameters, so
"what is in the way" reads naturally there. The polarisation precedent is
`Source`'s, and it is the one fact about the optics the package already keeps.

## Non-goals

- Modelling Kβ as an emission line. `_RADIATIONS` fences it and
  `capabilities.AnodeCapability.kbeta` says why: one |F|² cannot serve Kβ and
  Kα together.
- Retuning `GHOST_MIN_PARENTS`, `GHOST_RATIO_RANGE` or the prominence gate.
  1442 measured all three and its numbers stand.
- A filter absorption-edge term in the background (Cline et al. 2015).

## Tasks

- [x] The design call, recorded in this file with its date: a `Source` field or
      a `Geometry` one, and what its vocabulary is. "None declared" must not
      read as "no filter", since most files say nothing.
      **Decided 2026-10-03: `Source.kbeta: Literal["filter", "monochromator",
      "mirror"] | None = None`, on the X-ray `Source`.** It says what stands
      between the tube and the detector as far as Kβ goes, so it sits with the
      lines the beam carries and beside `polarization`, the one optics fact
      already kept there. `None` is *undeclared*, and the screen runs exactly
      as before. A new optional field loads every old document, and an old
      reader refuses a new one by `extra="forbid"`, the direction the
      compatibility note accepts. Behaviour per member: `monochromator` skips
      both searches (1442 measured that neither Kβ nor W Lα reaches the
      detector behind one); `filter` and `mirror` are **recorded and change
      nothing**. First draft had `filter` skip Kβ; the injection ladder
      (task 4) overturned it, since an image injected into corundum and
      zincite is flagged at r = 0.14, 0.10, 0.05 and 0.02 alike (6-8 lines at
      every rung), so a skip throws away real leaks past a working filter, and
      a narrowed ceiling would need a filtered-leak ratio nothing here
      measures. A neutron source needs no field: its
      `kind` is the declaration.
- [x] `monochromator_two_theta` is kept as well as consumed, or the new field
      subsumes it. Whichever, the fixtures that already declare one stop
      needing a second declaration to say the same thing.
      Done: it stays the one input and `bragg_brentano` also sets
      `kbeta="monochromator"` from it. No `kbeta_filter=` argument: `filter`
      changes nothing, and a preset argument would cost the import wizard a
      field and a rebuilt dist, so `"filter"` and `"mirror"` are set on the
      `Source` directly.
- [x] A source that cannot emit the line never runs the search: `neutron_cw`
      skips. Both callers, which means `diagnose` grows a way to be told.
      `identify_anode`'s docstring says a `None` is *not checked* rather than
      *clean*; a skip has to be the same kind of silence.
- [x] For `xray_cw`, a declared filter or monochromator narrows the ratio
      window or skips, with the narrowing measured against 1442's injection
      ladder rather than chosen.
      Measured 2026-10-03 on corundum and zincite (`tests/data/qarr`), an
      image of the whole pattern at the Kβ position added at r = 0.14, 0.10,
      0.05, 0.02, through `pick_peaks`: **6-8 lines flagged at every rung**
      (corundum 8, 8, 8, 7; zincite 6, 6, 7, 7). Nothing narrows, and a filter
      skip would discard real leaks. Only the monochromator and the neutron
      source skip.
- [x] The xrdml reader learns `<xRayMirror>`, `<monochromator>` and
      `<filter>`, recording what the file says and nothing more. brml and rasx
      when files exist to test them against; a reader that cannot see the
      element declares nothing rather than guessing.
      Done for xrdml as metadata `beam_optics` (element names only). brml and
      rasx are not done: no fixture shows either spelling, and the wizard does
      not yet turn `beam_optics` into `Source.kbeta`.
- [x] Manual and skill: what the field means, and that an undeclared instrument
      is not a clean one.
- [x] Tests: the neutron pattern, the demo's mirror, and a fixture whose
      declared monochromator makes the search skip.

- [ ] Follow-ups the review found: `auto_background` cannot be handed a
      source (it needs a public argument, so `api.md` and the manual
      partition move with it); the import wizard does not turn `beam_optics`
      into `Source.kbeta` (and must tell an incident monochromator from a
      diffracted-beam one); brml and rasx record no optics.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_peak_picking.py tests/test_readers.py
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- WP-1442 (the joint finding, and every number this file quotes at its close).
- WP-1102 (a renamed dot-path is migrated on the document text), for what a new
  `Source`/`Geometry` field costs a stored project.
- Cheary, Coelho & Cline (2004), *J. Res. NIST* **109**, 1-25: most
  diffractometers operate with Kβ filtering or some form of monochromatisation.
- `src/rietx/io/CLAUDE.md` for what a reader may and may not repair.

## Handover log

### 2026-10-03 — Source.kbeta, and the screen reads it

An instrument can now say what stands between the tube and the detector as far as
Kβ goes, and the ghost screen believes it. A neutron source and a diffracted-beam
monochromator skip the Kβ and tungsten searches, which they had no business
running. A filter or a mirror is recorded but changes nothing, because the screen
still finds a leak injected at 2 % of Kα on two real patterns, so skipping on a
filter would throw away real findings. Leaving the field empty means "nobody said",
and the screen runs exactly as before.

- **Done:** `Source.kbeta` (None, filter, monochromator, mirror); `bragg_brentano(monochromator_two_theta=)` sets it, so the 17 round-robin fixtures need no second declaration; `background.diagnostics.ghost_searches`; `source=` on `diagnose`, `contamination_flags_from_peaks`, `flag_ghosts`, and the two `pick_peaks` paths and the GUI splice; xrdml metadata `beam_optics` (element names only); manual row, skill bullet in `surprises.md`, help text; `tests/test_beam_optics.py` (12).
- **Measured:** injection ladder on corundum and zincite, r = 0.14, 0.10, 0.05, 0.02: 8, 8, 8, 7 and 6, 6, 7, 7 Kβ lines flagged, undeclared source. Fast selection, `[dev]`, darwin/arm64: 8072 passed, 159 skipped (one pytest process of another session may have overlapped the timing; counts are unaffected). `tests/test_acceptance_indexing.py`: 44 passed, 13:42. Full suite not run: no measured number moves.
- **Review (`/code-review high --fix`):** fixed a vacuous neutron test (its control also returned empty), replaced by one with a synthetic pattern that is flagged undeclared and silent under neutron and monochromator. Declined, with reasons: `auto_background` lacks a `source=` argument (I removed it to stay inside `api.md`'s cap; the manual now says where the skip applies); `ghost_searches` returns a tuple though only `()` or both occur (kept for tests and for a future narrowing); it reads `source` by `getattr` rather than `isinstance`; xrdml's `monochromator` does not tell incident from diffracted-beam.
- **Dropped on purpose:** a `kbeta_filter=` preset argument (would cost the wizard a field and a rebuilt dist for a value that changes nothing).
- **Gotchas:** skill caps are tight: `api.md` sits within bytes of its ceiling and `surprises.md` of its budget, so the next public name there pays with a cut. `--write-deferred` on `tests/api_surface` was run once and changed nothing. Lane trial: no item crossed 150K context with an estimate of 20 or more, so no lane was dispatched, and I did not write the `lanes: keep` lines, so the estimate comparison has no data.

Next, in order: (1) `auto_background(source=)`, since it is the one library caller that cannot reach the skip; (2) the wizard maps `beam_optics` to `kbeta` only after deciding incident versus diffracted monochromator, which is the premise 1442 measured only for the second; (3) brml and rasx when a file shows the element.

### 2026-09-22 — filed

Split out of WP-1442, whose seventh task this was. That WP made the
contamination screen joint across parents, which silenced every case this one
was filed against, so this is now about telling the screen what the optics are
rather than about a wrong answer somebody is getting. The measurements are in
§ Context and were taken on `75ac934a`.

The finding worth carrying: the fact is not merely undeclared, it is
**discarded**. `Instrument.bragg_brentano` takes `monochromator_two_theta`,
turns it into a polarisation factor and forgets it, so seventeen fixtures that
all know they sit behind a graphite monochromator cannot tell anyone.

Next: the design call first, because every other task depends on where the
field lives.
