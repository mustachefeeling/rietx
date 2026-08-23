# WP-1129 — the absent phase's support is a flat direction, not a number

Milestone: v1.1 · Status: ✅ 2026-08-23 — the Windows nightly's new red
diagnosed: `test_a_trace_phase_that_is_really_there_does_not_fire_it` pinned
the landing point of a flat direction against a fixed `1.0`, and that quantity
spans six orders across settings and platforms. Re-asserted as the ordering
its own docstring said it was.
Depends on: —

## Goal

The false-positive side of `PHASE_UNCONSTRAINED` is asserted as an ordering
between the real phase's support and the absent phase's, so it states the same
claim on every platform instead of pinning one machine's zero.

## Context

The 2026-08-23 nightly (`784c6670`) turned the Linux full job **green** — the
WP-1128 failure is intermittent and did not recur — and turned the **Windows
fast job red** for the first time, on a different test:

```
tests/test_absent_phase.py::test_a_trace_phase_that_is_really_there_does_not_fire_it
AssertionError: the absent one is far below it
assert 1.6415122964126485 < 1.0
```

Windows is `docs/RELEASING.md` step 4's pre-upload gate, so this blocked the
v1.1.0 tag.

**The assertion pinned a flat direction.** The fixture fits LaB6 plus a phase
that is not in the data. Such a phase reaches the pattern only through
`scale × |F|² × profile` (root CLAUDE.md § Invariants), so its scale converges
to *a* zero rather than to *the* zero, and `max(phase_component / σ)` follows
it. Measured on one macOS box, one commit, `mccusker_default`:

| schedule | `support[1]` | absent scale | absent cell *a* | Rwp |
|---|---|---|---|---|
| shipped (`intermediate_ftol=1e-6`) | 9.13e-07 | 1.555e-14 | 4.7846 Å | 0.04141 |
| `intermediate_ftol=None` (pre-1123) | **0.548** | 7.148e-09 | 4.9556 Å | 0.04140 |

With WP-1110's own recorded 0.088 and CI's Windows 1.64, the quantity spans
**six orders** — 9.1e-07, 0.088, 0.548, 1.64 — while `support[0]` stays put at
~386σ because the real phase is the part the fit determines. Both scales above
are physically zero; the ratio between them is five orders because zero has no
significant figures.

So this is the WP-1128 shape one rank over: a test asserting a **number** where
its own docstring claimed an **ordering** ("pinned as an ordering rather than
as a number", which the code did not do). The same file already gets this right
one test earlier — `test_the_absent_phases_cell_stays_in_the_physical_range`
says "the assertion is 'did not leave the physical range', not a pin on the
trajectory, which is a flat direction and therefore not reproducible to many
figures" — so the fix is to apply the file's own established rule to the
neighbouring test.

**This is not a regression, and the check that matters still fires.** The
`PHASE_UNCONSTRAINED` diagnostic and the cell window are asserted by three
other tests in the file, all green on Windows through the same nightly. A
1.64σ contribution at its strongest point is noise; 386σ is not.

## Non-goals

- Making the absent phase's scale reproducible. It is unmeasurable by
  construction, and WP-1110's design is to *name* that rather than to hide it.
- Any change to `PHASE_UNCONSTRAINED`, the per-stage cell window, or
  `phase_support`.

## Tasks

- [x] Re-assert the false-positive side as a ratio against this run's own
      `support[0]`, with both values in the failure message.
- [x] Record in the docstring why the quantity cannot be a number, with the
      four measured values.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_absent_phase.py
.venv/bin/python -m ruff check src tests examples
```

and the Windows nightly job green on the release commit
(`docs/RELEASING.md` step 4).

## References

- WP-1110 — `PHASE_UNCONSTRAINED`, the per-stage cell window, and this file.
- WP-1123 — `intermediate_ftol`, the schedule the two rows above differ by.
- WP-1128 — the same defect shape (a test pinning what the machine decides).

## Handover log

- **2026-08-23** — **The new Windows red was the test, not the package, and the
  evidence is a six-order spread in the thing it pinned.** Anyone reading a red
  Windows nightly before the v1.1.0 tag can stop treating it as a defect in the
  absent-phase work: what the fit determines (386σ of real-phase support, the
  diagnostic firing, the cell staying physical) is identical everywhere, and
  what moved is a scale of 1e-14 against 7e-09 — two spellings of zero.
  *Done*: the assertion is now `support[1] < support[0] / 20`, with both values
  and the ratio in the message so a future failure is diagnosable from the log
  alone; the docstring carries the four measured values and the reason.
  *Measured*: 9.13e-07 (shipped schedule) and 0.548 (`intermediate_ftol=None`)
  on macOS against WP-1110's 0.088 and CI's Windows 1.64; `support[0]` 385.77,
  unmoved by the schedule.
  *Gotchas*: the sibling cell test already stated this rule and was not
  followed one test later — worth checking the rest of a file when one test
  turns out to pin a flat direction.
  *Next*: none; closed. The v1.1.0 tag still wants a nightly dispatched on the
  release commit for the Windows gate.
