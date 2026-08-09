# CLAUDE.md — src/pxrdref/io/

Scope: the **pattern readers** — how a file is claimed, what a reader may
repair, where σ comes from, and the per-format rules. The clauses that change
behaviour *outside* this subtree stay in the root CLAUDE.md (§ Invariants);
everything here is detail a session working under `io/` needs and nobody else
does. Measured stories and provenance are elsewhere: `docs/wp/1047-*.md` for
the decisions, `tests/data/README.md` for what each fixture can prove,
`ATTRIBUTION.md` for the licence fences.

The organising rule: **one module per format**, because a format's spec
citation, its parser, its `sniff`/`sigma` prose, its options and its licence
fence are one fact each and ten fences in one file drift. `readers.py` is the
front door only (`read_pattern`, `identify_format`, `list_scans`), so adding a
format never moves a call site.

## Dispatch

`PATTERN_FORMATS` is an **ordered** tuple and the order is behaviour — the
first format whose `matches` returns True reads the file. Strongest evidence
first: magic bytes and container manifests, then a required first line or XML
root, then suffix, then a loose text sniff, then the ASCII catch-all **last**.
Binary-claiming formats go first so nothing tries to decode their bytes.

Every text sniff goes through `base.head()`, a bounded 4 kB read — its
predecessor decoded a whole file and then sliced, an O(N) decode per dispatch on
a 60 MB pattern. It is deliberately **not cached**: `restage` re-reads the same
path, so a path-keyed cache would be a correctness hazard for exactly the file a
user just replaced. There is **one stated exemption**, `.chi`'s count check,
which is O(N), runs only behind a bounded shape gate, and buys the one thing the
shape cannot — the difference between that format and the catch-all.

`xy` is not total (`matches = not looks_binary(head)`), so `identify_format`'s
terminal refusal is reachable and its message is **built from the registry**.

## What a reader may repair

Root CLAUDE.md's rule — a silent correction is a reader's to make, and only
where the deviation is a *report* rather than a *contradiction* — applied to 2θ
order in `base.ascending()`, the one place it lives:

| deviation | verdict | action |
|---|---|---|
| strictly descending | report — the same measurement stored backwards; reversal is lossless | reverse, `PATTERN_SCAN_REVERSED` |
| duplicate 2θ, equal y | report — a format artefact | drop the repeat, `PATTERN_DUPLICATE_POINTS` |
| duplicate 2θ, **different** y | contradiction — averaging invents a datum, dropping picks one | **raise**, naming the 2θ |
| non-monotone (stitched, restarts) | contradiction — concatenate, sort or separate are three measurements | **raise**; name `scan=` only where the format has it |
| non-constant step | neither | nothing — SRM 660c is 24 stitched regions and is legal |

`ascending(..., fmt=)` takes the format so the non-monotone refusal names
`scan=` **only** where the option exists: telling someone to select a scan in a
file that cannot hold several is a wrong instruction, not a vague one.

## Refusals

A reader raises `ValueError`/`OSError` **naming the file**, never its parser's
exception — six container parsers will otherwise raise `struct.error`,
`zipfile.BadZipFile` and `ET.ParseError`, and the last subclasses `SyntaxError`,
so it escapes `preview_pattern`'s allowlist as a 500. Each parser converts at
its own boundary, and `base.pattern_data()` is that boundary **at the schema**
too: a `PatternData` validator is the last one every reader crosses, and its
pydantic report names a field rather than a file.

`test_readers_robust.py` is what keeps this true — every real fixture truncated
at 20 offsets, plus a synthetic arm for formats with no vendorable file. It has
found two real bugs so far (both ragged-array crashes on a row cut mid-line),
which is the argument for running it before believing a new parser.

`PatternFormat.refuses` marks a format recognised **in order to be declined** —
a `.dif` peak list is not a profile. One field rather than a side table, so
`capabilities()` stays honest without `reader_formats` meaning two things.

## Options

Two levels: `READER_OPTIONS` is the build-wide vocabulary, `PatternFormat.options`
the subset a format honours, and `set(READER_OPTIONS) == ⋃ fmt.options` is a
meta-test. That split is what makes a **typo** (raises) different from an option
this format does not take (dropped, and *reported* as `READER_OPTION_IGNORED` —
a UI carrying a value across a change of file is normal, an API caller who
passed `scan=2` believed they selected something). `DataRef` records the
**effective** options, because those are what re-opening must replay.

`fmt.scans` and `"scan" in fmt.options` are held in **biconditional** by
meta-test: a format that lets a caller choose must be able to say what there is
to choose between. Reading scan 0 by default is never silent —
`base.multiscan_default()` emits `PATTERN_MULTISCAN_DEFAULTED`.

## σ, and how much a file's own word is worth

`PatternData.sigma` is the file's esds when it has them; `None` means the
Poisson fallback √max(y, 1), which is **correct** for raw counts and wrong by
√t for anything already divided by a counting time. So a rate gets a *derived*
σ — `base.sigma_from_cps()`, written √(y·t)/t rather than √(y/t) so a channel
that counted zero gets the same floor a counts channel gets.

Which of the two a file holds is decided by **what kind of declaration it
makes**, and the three cases are the whole rule:

- **Structural** — trusted. `.uxd` names the unit in the token that opens the
  data block (`_2THETACOUNTS` / `_2THETACPS`), where it cannot disagree with
  itself. Verified anyway: every `COUNTS` block integral to the last of 3774
  points.
- **Free text** — measured, not trusted. `.ras` names it in
  `*MEAS_SCAN_UNIT_Y`, and a real file declares `counts` while storing 84.3047,
  which no scale in 1/1000…200 makes integral. So arithmetic decides: counts
  are integers; a rate times its counting time is.
- **Neither settles it** — σ is **withheld** with `PATTERN_INTENSITY_SCALED`,
  never faked. The caveat says the fallback is being applied to a quantity whose
  scale could not be verified.

Deriving the counting time is part of this: `.uxd` gives `_STEPTIME` in seconds
directly, `.ras` gives a speed whose **unit** must be read (`deg/min`, so a step
÷ speed in minutes — assuming seconds would make every σ wrong by √60), and a
header that states no unit leaves the time *unknown* rather than defaulted.

## The axis is never trusted

Most vendor files are **not powder scans** — 4 of the 5 real `.uxd` files
obtained are pole figures or rocking curves, and one rocking curve sits under a
marker called `_2THETACOUNTS`, so a block marker is not evidence either. A
non-2θ scan parses perfectly and refines to a confidently wrong cell, so all
three formats that state an axis use the same three-way policy:

- recognisably 2θ → read, silently;
- recognisably something else → **raise**, naming what the file actually holds
  (a q or d axis, a rocking curve, a pole-figure ring);
- unrecognisable → read as 2θ **and say so** (`CHI_`/`RAS_`/`UXD_X_AXIS_ASSUMED`).

The authority differs per format and is always the field that *means* the axis:
`.chi`'s line-2 label, `.ras`'s `*MEAS_SCAN_AXIS_X`, `.uxd`'s `_DRIVE`. Three
implementations of one policy is deliberate for now — the inputs are different
shapes — but a fourth is the point at which to factor it.

## Metadata

`METADATA_KEYS` is **data**, and `base.metadata()` refuses an undeclared key,
because two consumers *match* on these keys — the import wizard's anode
pre-selection and a preview's scan count — and neither can match on a name each
reader spells for itself. `scan_count` travels from the **single** read, so a
preview never parses a 60 MB file twice; `list_scans` is for the CLI and the
scan picker, not the preview path.

A file's own wavelength is **recorded, never used**: the anode presets are the
authority on wavelengths, and the real fixtures give 1.540598 and 1.540593
against the package's 1.5405929 — a ~3 ppm spread that is real and far inside
what the SRM 660c acceptance allows.

## Per format

| format | claimed by | σ | notes |
|---|---|---|---|
| `ras` | first line `*RAS_DATA_START` | measured per file (above) | multi-scan; third column is an attenuator and is **never applied** — no spec says whether column 2 is already corrected, and all five obtainable files have it constant, so `RAS_ATTENUATOR_PRESENT` names the affected 2θ range instead |
| `uxd` | first non-`;` line begins `_FILEVERSION` | marker suffix + `_STEPTIME` | multi-range; the header snapshot must be taken when the **marker opens** the block, not at close — keys persist across ranges, so otherwise a 2 s range's σ comes from a 20 s one |
| `pdcif` | `.cif` suffix, through gemmi | the file's esd or weight column | `block` selects; a `_meas` and a `_calc` block are different patterns |
| `gsas` | `^BANK \d+` in the first 4 kB | ESD/FXYE column, else Poisson | disjoint from `bruker_raw`'s magic by construction, so the `.raw` collision resolves either way |
| `chi` | four-line header whose declared count matches the rows | third column when written | the count gate is the one O(N) sniff |
| `dif_peaklist` | `.dif` **and** peak-list content | — | refused; matched on evidence not suffix, so a real profile misnamed `.dif` still reaches `xy` |
| `xy` | text, not binary — **last** | third column when written | a NUL in the first 4 kB is refused by name unless behind a BOM: ASCII-range UTF-16LE is valid UTF-8 with interleaved NULs, and Windows vendor software exports it |

## Adding a format

1. **Check the fixture licence per *file*, before writing the reader.** A repo
   LICENSE covers the repo's own work, not user-contributed instrument output,
   and a repo may have none at all. This has already cost the two best fixtures
   found (`xrd-toolkit`'s real `.ras`; every real `.uxd`). If a file cannot be
   vendored, that format's whole test strategy changes — and what the real file
   established goes in `tests/data/README.md` regardless, since that is then the
   only place the design is checkable.
2. **Byte offsets, magic strings, tag names and element paths are
   specification facts** — merger, not expression — so they may be written down
   from any source, including one whose licence would bar a port. Extract them
   into a table first, then write the parser **with the source file closed**.
   `ATTRIBUTION.md` § Format specifications records which source each came from.
3. One module, exporting a `PatternFormat`; add it to `PATTERN_FORMATS` in
   dispatch order and say why the position is right.
4. Add its fixture to `test_readers_robust.py` — `REAL_FIXTURES` if it has one,
   the synthetic arm if it cannot.
5. A new rule lands here; it earns a root CLAUDE.md clause only if it changes
   behaviour outside `io/`.
