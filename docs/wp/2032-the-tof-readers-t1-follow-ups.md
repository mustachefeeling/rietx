# WP-2032 — the TOF readers' T-1 follow-ups: a time map read as data, and names with no writer

Milestone: unscheduled · Status: ⬜
Track: The specimen is not an angle, and the neutron follow-through
Depends on: — (1927 soft, closed: the T-1 cut these come from)
Priority: P3 2026-10-23 — defects in shipped T-1 readers on a path nothing refines yet; one reads a record as data rows silently, the rest are a refusal that names no file and declared names with no writer

## Goal

The T-1 time-of-flight readers have no known defect left: a `TIME_MAP`
record is never read as data, every refusal names its file, the bank a
project opened is recorded, and every declared TOF name has a writer and a
reader or is removed.

## Context

T-1 (WP-1927, PR #911 through #961, 2026-10-13) added the TOF axis and its
readers. Its two review rounds left seven follow-ups, none blocking. At the
time, all seven were parked for the T-2 cut, which ROADMAP § v2+ holds
behind the magnetic milestone. A chain audit on 2026-10-23 found that five of
them are defects in code that has already shipped, and they need no T-2
model. They are this WP. The other two, `TOFSource` exposing `lines`,
`primary_wavelength` and `wavelength_parameters` as properties that refuse by
name, and the hand-written `capabilities()` note for `neutron_tof`, stay in
1927's Context § What T-1 leaves for T-2.

1. **A `TIME_MAP` record placed after a bank's data is read as that bank's
   rows.** `io/gsas.py:550-565` stops a bank's data only at the next `BANK`
   line. This is a silent wrong read. The fix stops at any record header, or
   refuses the file by name.
2. **`load_instrument_profile`'s refusal names the function, not the file**
   (`io/instrument_profile.py:190`). The root rule is that a reader raises
   naming the file (CLAUDE.md § Invariants, WP-1047).
3. **`Project.open` does not record the bank it chose** in the `DataRef`.
   The reader call is part of the reference (CLAUDE.md § Project), so a
   multi-bank file reopened can read a different bank with nothing saying so.
4. **`TOFSource.l1_m` has no writer** (`schemas/instrument.py:710`), though an
   `.iparm` states `FPATH1`. That is a declared name with no writer, WP-1076's
   rule: write it from the reader, or remove the field.
5. **`SPECTRUM_TYPES` is read by nothing** (`model/tof_spectrum.py:42`). Read
   it where the spectrum type is validated, or remove it.

**Tier.** Nothing here is a heuristic. Item 1 is a file-format rule, items 2
and 3 are bookkeeping, and items 4 and 5 remove or wire declared names. No
`_audit` row is expected, unless removing a name takes its row with it.
WP-2006 (the dead surface) tiers such names, so tell it if 4 or 5 removes one.

## Non-goals

- The TOF profile, spectrum and forward model (T-2/T-3) and multi-bank
  (T-5): ROADMAP § v2+.
- The two T-2 follow-ups named above, which stay in 1927's Context.

## Tasks

- [ ] `TIME_MAP` after data: a fixture with the record after a bank's rows,
      then the reader stops at it or refuses by name.
- [ ] `load_instrument_profile`'s refusal names the file. Test the message.
- [ ] `Project.open` writes the chosen bank into `DataRef`, and a reopen reads
      the same bank. Test with a two-bank file.
- [ ] `TOFSource.l1_m`: written from `FPATH1` by the `.iparm` reader, or
      removed (a schema bump if removed).
- [ ] `SPECTRUM_TYPES`: read where the type is validated, or removed.
- [ ] Skill: none expected, since nothing here changes what an agent calls.
      Say why at handover.

## Acceptance

- Each item has a test that fails on `main` and passes here.

```sh
.venv/bin/python -m pytest tests/test_tof*.py tests/test_project*.py -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1927 (T-1) and its 2026-10-13 handover entry's *Not done*; PR #911, #961.

## Handover log

- **2026-10-23** — created by the chain audit of WP-1927's close. 1927's close
  had left all seven review follow-ups for the T-2 cut. Five of them are
  defects in shipped T-1 code, and no open WP owns them. WP-2006 tiers
  declared names and does not fix readers, and no TOF WP is open.
