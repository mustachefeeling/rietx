# WP-1314 — a Jana2020 project reader: .m50/.m40/.m41

Milestone: unscheduled · Status: ⬜
Depends on: 1118 (its first task — the model-format registry and the answer's shape)

## Goal

Reading a Jana2020 m-file triplet — `.m50` (cell, symmetry, structure
metadata), `.m40` (atomic parameters), `.m41` (powder profile/instrument
parameters) — returns the model it describes under the WP-1118 contract: the
`Structure`/`Instrument` pair plus the refine flags, carried faithfully or
refused by name, never silently defaulted. Jana is the remaining major
Rietveld code with no import route.

## Context

From issue #147 (filed in the #130 proposal channel as a list entry, scoped
here).

**The contract is WP-1118's, restated short.** The refine flags are the
payload, not the numbers: which parameters were free, which held, what was
excluded. A construct the reader does not carry is reported by name; one
that would change the answer is refused ("the stated-key rule the TOPAS
reader's five review rounds established"). The answer takes the same shape
as the sibling readers — whatever 1118's first task decides (model + vary
set, or a `Project`) — which is why that task gates this WP.

**The files are plain text and documented in Jana's own manuals.** That
makes this a spec-only format in the io/ sense: layouts written from
documentation with any source file closed, provenance in `ATTRIBUTION.md`.

**The honest difference, said at the top rather than discovered at
acceptance: validation inverts.** A bounded sweep of the archive that
grounded the TOPAS reader (606 solved `.inp`) and the FullProf reader (six
`.pcr`) found **zero** Jana m-files. So the evidence is: Jana2020's own
distributed example suite (licence checked per file before any vendoring;
synthetic fixtures otherwise), the `io/CLAUDE.md` perturbation-fuzz
discipline (`test_readers_robust.py`), and cross-code number checks against
published Jana refinements. Weaker than the siblings', and the WP says so.

**The refusal is the deliverable for Jana's speciality.** Modulated and
composite structures are what Jana is *for*, and superspace groups are a
schema rietx does not have — so an `.m50` declaring modulation is refused by
name, exactly as the TOPAS reader refuses magnetic space groups. A user with
such a file is told what they have, not handed a truncated model.

**The writer rides the reader's tables, later.** Issue #148 pairs each
writer with its reader so both land against one spec table; Jana's writer is
the lowest-priority of that family until this reader has fixed the tables.
It is this WP's final, explicitly-later task, and its consumer is the
handoff workflow (refine here, finish in Jana for modulated work / charge
flipping).

## Non-goals

- **Not single-crystal projects, not `.m90` data files.** Powder protocol
  only; the pattern goes through `read_pattern` as ever.
- **Not superspace/modulated support** — refused by name; a schema for it is
  nobody's current plan.
- **Not Rietica or XND** — issue #196 widens the family beyond the majors;
  recorded on [1118](1118-foreign-model-files.md), deliberately unscheduled.
- **Not the registry design** — 1118's first task owns the shape this
  plugs into.

## Tasks

- [ ] Spec tables for `.m50`/`.m40`/`.m41` from the Jana documentation
      (source files closed; `ATTRIBUTION.md` row), with the refusal list
      (modulation, composites, magnetic) written first.
- [ ] The reader: triplet → model + refine flags under the 1118 contract,
      every uncarried construct named in diagnostics.
- [ ] Fixtures: Jana-distributed examples licence-checked per file, else
      synthetic; perturbation fuzz in `test_readers_robust.py`'s arm;
      cross-check against at least one published Jana refinement's numbers.
- [ ] `capabilities()` model-format arm entry, skill routing-row widening
      (SKILL.md byte budget — see 1118's Inherited), manual section,
      provenance rows.
- [ ] Later, after the tables have settled: the `.m50/.m40/.m41` writer,
      naming what did not cross (issue #148's pairing).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_reader_mfile.py tests/test_readers_robust.py   # first module is new, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: a distributed-example triplet round-trips to a model whose protocol
matches its published refinement field for field; a modulated `.m50` refuses
naming modulation; fuzzed files refuse naming the file, never a parser
exception.

## References

- Issue #147; issue #148 (the writer pairing); issue #196 (the family
  boundary).
- Petříček, V., Dušek, M. & Palatinus, L. (2014), *Z. Kristallogr.* **229**,
  345 — Jana2006/2020; the m-file layouts are in its documentation.
- [1118](1118-foreign-model-files.md) — the contract, licence fences, and
  registry this reader plugs into.

## Handover log

- **2026-09-01** — created, from issue #147 (2026-09-01 triage). Settled:
  the contract and the refusal list; blocked on 1118's first task for the
  answer's shape; first own item is sourcing the distributed examples and
  their licence status.
