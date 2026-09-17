# WP-1437 — a formula the code does not compute

Milestone: unscheduled · Status: 🔄 2026-09-17 — claimed by @yue-here
Depends on: —

## Goal

`help.py`'s parameter descriptions agree with the code they describe. The
`instrument.polarization` entry stops telling users a formula that diverges
from the package's own by up to 2×, the other fourteen equation-bearing
descriptions are checked once and the result recorded, and the numeric
thresholds are pinned so they cannot drift again.

## Context

`src/rietx/help.py` is the declared one authority for what a name *is*
(WP-1202, root CLAUDE.md § Conventions). Its `unit` and `default` fields are
the schema's own through `UNIT_DISPLAY`. Its `description` and `typical` are
**authored**, so any formula in a description is a copy with nothing holding it
to the code. One of them is wrong.

### The defect

| | `help.py` says | the package computes |
|---|---|---|
| the Lp factor | `(1 + K·cos²2θ)/(1 + K)` (`help.py:209`) | `K + (1 − K)·cos²2θ` (`corrections.py:24`) |
| monochromated | "`cos²2θ_M` for a monochromated one" (`help.py:211`) | `K = 1/(1 + cos²2θ_m)` (`schemas/instrument.py:1879`, code at `:1901`) |

Measured 2026-09-17 by running both forms through `lorentz_polarization`. The
ratio of the help-text Lp to the computed Lp:

| K | 2θ=30° | 2θ=90° | 2θ=150° |
|---|---|---|---|
| 0.5 (unpolarised lab) | 1.048 | 1.333 | 1.048 |
| 0.556 (graphite 002, Cu) | 1.024 | 1.156 | 1.024 |
| 0.799 | 0.936 | 0.696 | 0.936 |
| 0.99 (synchrotron) | 0.878 | **0.508** | 0.878 |

Worst at K = 0.99, the value the entry itself quotes for 11-BM. **The ratio
varies with angle**, so a phase scale cannot absorb it; it biases ADPs and
phase fractions. The monochromator prescription is wrong separately: for
graphite (002) at Cu the entry's wording gives K = 0.799 where the schema gives
0.556.

### The root cause, and why it belongs beside WP-1436

Neither formula is wrong in isolation. help.py prints the *monochromator*
expression, which is exactly right when its `K` means `cos²2θ_m`. The entry
binds that letter to the package's own `K`, a different quantity. This is a
symbol collision that reached a user-facing number, so it is the expensive end
of the same story WP-1436 covers.

`help.py:1346` repeats the second error for `monochromator_two_theta`.

### Reach

Three surfaces carry it: `GET /api/help` in the GUI (`src/rietx/gui/server.py:197`),
the generated glossary (`docs/manual/conf.py:271`, body at
`docs/manual/_generated/glossary-body.md`), and `rietx.help` imported directly.

### The class, sized

Parsed 2026-09-17: **116** `description=` blocks, of which **15** carry an
equation and **6** carry a number with a unit. The defect above is one of the
15. The other fourteen have never been checked against their code.

Those six sentences quote **three** live constants between them, and all three
currently agree, so they carry drift risk only. Re-derive the six from
`help.py` before pinning: the count below is of constants, not of sentences,
and a sentence quoting a fourth constant would not appear here.

| description says | live constant |
|---|---|
| "2 nm" (`help.py:659`, `:696`) | `SIZE_CAP_MIN_SIZE_A = 20.0`, `params/vector.py:635` |
| "5 nm" (`help.py:662`) | `SIZE_FLAG_SIZE_A = 50.0`, `refine.py:4875` |
| "1.5 deg" (`help.py:681`) | `STRAIN_FLAG_WIDTH = 1.5`, `refine.py:4773` |

The manual injects these as MyST substitutions from the live package.
`help.py` imports nothing but `dataclasses` and `fnmatch`, so it has no such
mechanism and gains none here.

### The seam to extend

`tests/test_help.py` already owns this shape of check, and a new one is a
sibling rather than an invention:

- `test_units_are_the_schemas_own` (`:490`)
- `test_defaults_are_the_schemas_own` (`:524`)
- `test_search_control_defaults_are_the_schemas_own` (`:391`)

`test_every_entry_has_a_title_and_a_description` (`:633`) checks presence only,
which is why this class was unguarded.

## Non-goals

- The `k` = sinθ/λ rename and the notation table. That is WP-1436, which
  rebases onto this one because both edit `docs/manual/intensities.md`.
- Deriving descriptions from the code generally. Prose is authored on purpose,
  and a templating layer over 116 entries would cost more than it saves. The
  answer here is one audit plus a pin on the numbers.
- The other fifteen symbol findings of the 2026-09-17 audit. They are WP-1436's
  or explicitly not generalised there.

## Tasks

- [x] Correct `help.py:205-217` (`instrument.polarization`): the factor becomes
      `K + (1 − K)·cos²2θ`, the monochromator prescription becomes
      `K = 1/(1 + cos²2θ_m)` quoting 0.556 for graphite (002) at Cu. Reuse the
      wording already correct at `schemas/instrument.py:1762-1766` and
      `docs/manual/corrections.md:30`.
- [x] Correct `help.py:1342-1352` (`monochromator_two_theta`), same root cause.
- [x] `docs/manual/intensities.md:104` — the third site of the same `K`
      confusion. It says "an unpolarised neutron beam sets $K = 1$", where
      `corrections.py:17` defines K as the σ-polarised *fraction* with K = 0.5
      unpolarised. The arithmetic is right, since K = 1 gives the bare Lorentz
      factor a neutron pattern wants, but the word is attached to the wrong
      value and the same chapter's `corr-lp` defines K the other way. The skill
      is clean here: `diagnostics-gsas.md:61` states the value without
      labelling it.
- [ ] Audit the remaining fourteen equation-bearing descriptions against the
      code each describes. Record every one in the handover, checked or
      corrected. **This is the deliverable**; the two fixes above are its first
      finding.
- [ ] Pin the three numeric thresholds against their live constants, as a
      fourth `*_are_the_schemas_own` member in `tests/test_help.py`.
- [x] A review rule in `help.py`'s module docstring: a description that states
      a formula or a threshold names where the real one lives.
- [ ] Check whether the agent skill restates the polarisation factor; re-sync
      the two committed copies with `rietx skill --install . --copy` if it does.
- [ ] Skill: a row only if the skill carries the wrong formula. An agent
      driving rietx reads `polarization` as a value to set, not a formula to
      evaluate, so the body needs nothing.

## Acceptance

The corrected entry matches the code at every K the entry names, checked by
evaluating rather than by reading.

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_manual_api.py
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

Then read the entry back out of the two surfaces that ship it, because neither
is exercised by the command above: `GET /api/help` from a running
`rietx gui`, and the glossary page in the built HTML.

## References

- International Tables for Crystallography Vol. C §6.2; Azároff (1955), for the
  monochromator polarisation factor. Both already cited at
  `schemas/instrument.py:1765`.
- The correct forms in-tree: `model/corrections.py:11-19`,
  `schemas/instrument.py:1875-1880`, `docs/manual/corrections.md:26-30`.

## Handover log

- **2026-09-17 (arrival)** — every anchor in this file re-checked against the
  tree before starting (`/wp-start` step 5). Content and physics all held; six
  line numbers did not: `schemas/instrument.py`'s docstring formula and code
  (cited 1765/1787, actually 1879/1901 — a consistent 114-line offset, the
  file itself untouched since WP-1309, so the audit's own count was off from
  the start rather than drifted), the `monochromator_two_theta` HelpEntry
  (cited 1320-1330/1324, actually 1342-1352/1346), the three threshold
  citations in `help.py`/`params/vector.py`/`refine.py`, and all four
  `test_help.py` anchors (each off by 9-22 lines, file-by-file consistent).
  `docs/manual/intensities.md:104` and the two `help.py:205-217` /
  `corrections.py:24` anchors were exact. Corrected in place above; no claim
  changed, only where to find it.
- **2026-09-17** — created, out of the notation audit that also opened
  [1436](1436-k-is-the-wavevector-everywhere-else.md). A comment on a LinkedIn
  post about the package questioned one symbol; auditing the tree for its
  siblings found this, which is worse, because a symbol bound to the wrong
  quantity here reaches a number a user acts on. The divergence table in
  Context was measured by running both forms, after a first pass that read them
  and understated the effect by half. The class is sized and the guard's family
  is named, so the work needs no further investigation. Next: the two
  corrections, then the fourteen-entry audit.
