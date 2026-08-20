# CLAUDE.md — src/rietx/io/

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

A **container** adds one more: nothing is extracted to disk and no member is read
whole on trust. `ZipInfo.file_size` is a number in the archive's *own* header, so
each member is read `read(cap + 1)` and refused past `rasx.MAX_MEMBER_BYTES`, and
`extract()` — which writes files, and historically wrote them outside the
destination — is never called. A 651 kB `.brml` carries a 4.5 MB member no reader
here opens, so the file's size says nothing about a member's.

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
  data block (`_2THETACOUNTS` / `_2THETACPS`) and `.xrdml` in a schema-enumerated
  attribute *on* the data element, where neither can disagree with itself.
  Verified anyway: every `COUNTS` block integral to the last of 3774 points, and
  every intensity in both real single-scan `.xrdml` fixtures.
- **Free text** — measured, not trusted, by `base.sigma_by_arithmetic`: counts
  are integers, and a rate times its counting time is. Both Rigaku formats
  declare the unit this way and real files get it wrong — a `.ras` declaring
  `counts` while storing 84.3047, and **two of the three** real `.rasx` files
  declaring counts and storing values no scale in 1/400…400 makes integral. The
  third `.rasx` declares counts and is integral, which is the same test deciding
  both ways within one format.
- **Neither settles it** — σ is **withheld** with `PATTERN_INTENSITY_SCALED`,
  never faked. The caveat says the fallback is being applied to a quantity whose
  scale could not be verified.

Deriving the counting time is part of this: `.uxd` gives `_STEPTIME` in seconds
directly, `.ras` gives a speed whose **unit** must be read (`deg/min`, so a step
÷ speed in minutes — assuming seconds would make every σ wrong by √60), and a
header that states no unit leaves the time *unknown* rather than defaulted.

The counting time is not the only scale, so a format that scales twice
**composes rather than branching**: the Poisson quantity is the raw count `c`,
the stored value is `y = c·s` for a scale the reader can *name*, and `s ≡ 1` is
raw counts and gets no σ. `base.sigma_from_scaled` is that; `.xrdml` composes an
attenuation factor with `1/t`.

**An attenuator's convention is measured, never adopted** — four formats have
one and they have given three different answers. The test is the same each time:
find a file where the factor *varies*, and ask which of the raw series and the
product runs continuously through the transition. `.xrdml` **applies** it (the
raw series dips 87 % at the attenuated point of a substrate peak); `.brml` leaves
the values alone and puts the factor into σ only (the stored series is
continuous, and `y/a` is the integral one); the two Rigaku formats **report**
without deciding, because no obtainable file has a varying column. Numbers in
`tests/data/README.md`. Whichever way it lands, σ goes through the factor —
√counts·a is not √y — and that is the case GSAS-II gets wrong by weighting 1/y
regardless.

## The axis is never trusted

Most vendor files are **not powder scans** — 4 of the 5 real `.uxd` files
obtained are pole figures or rocking curves, and one rocking curve sits under a
marker called `_2THETACOUNTS`, so a block marker is not evidence either. A
non-2θ scan parses perfectly and refines to a confidently wrong cell, so all
three formats that state an axis use the same three-way policy:

- recognisably 2θ → read, silently;
- recognisably something else → **raise**, naming what the file actually holds
  (a q or d axis, a rocking curve, a pole-figure ring);
- unrecognisable → read as 2θ **and say so** (`PATTERN_X_AXIS_ASSUMED`).

The policy is `base.check_axis()` and the **classifying is not part of it**: the
authority differs per format and is always the field that *means* the axis —
`.chi`'s line-2 label, `.ras`'s `*MEAS_SCAN_AXIS_X`, `.uxd`'s `_DRIVE`,
`.xrdml`'s `scan/@scanAxis`, `.raw`'s flagged drive record — and those are
inputs of five different shapes. So each format classifies for itself and passes
the verdict in; a sixth adds a vocabulary, never a row to a shared table. And
where a format states the axis **twice**, both statements are asked and have to
agree: `.raw`'s scanned drive is the record that is flagged *and* parked at the
range's start angle, because one real file is not enough to trust either alone.
One code rather than four because
the operator's answer is identical in every case, and four near-duplicate rows
in `AGENT_PROTOCOL.md` was the smell (factored WP-1047 at the fourth consumer,
which is where the previous session said the trigger was).

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
| `bruker_raw` | one of four magic strings at offset 0 — **first**, being the only entry whose sniff names the format *and* its version | measured by arithmetic; neither version declares a unit, and the counting time is **ms** in v4, seconds in v3 | multi-range; **nothing is located by counting and nothing is a fixed stride** — v4 is walked to EOF and strided by `datumSize` (`2Theta` occurs twice in the single-range real file; `datumSize` is 8 there), v3 by `data_record_length` past `total_size_of_extra_records`. **v1 and v2 are named and refused**: no corroborated description of either exists. v3's global gate — the declared ranges must account for the file — judges the leftover by **content, not length**: a range read at the wrong offset leaves counts behind and counts are not zeros, so a zero pad is admitted (a real 82-range VT reel pads with 3280 of them) and any non-zero tail past one datum's slack still refuses, naming its first byte's offset |
| `rasx` | a zip holding a `Data<N>/Profile<N>.txt` member | the same arithmetic as `.ras` | multi-scan; `root.xml` is the authority on order and membership, not the zip name list; every member read through a cap, because `ZipInfo.file_size` is the archive's own claim |
| `brml` | a zip holding a `DataContainer.xml` **and** a `RawData<N>.xml` | derived through the absorber, √(y/a)·a | multi-scan; **every column is located from `DataViews`, never counted** — 2θ is column 2 and the intensity column 7 in the real files, so GSAS-II's fixed `entry[2]`/`[4]` is one layout's coincidence. A `RecordedRawDataView` of `Length > 1` is a detector frame and is refused |
| `ras` | first line `*RAS_DATA_START` | measured per file (above) | multi-scan; third column is an attenuator and is **never applied** — no spec says whether column 2 is already corrected, and all five obtainable files have it constant, so `RAS_ATTENUATOR_PRESENT` names the affected 2θ range instead |
| `uxd` | first non-`;` line begins `_FILEVERSION` | marker suffix + `_STEPTIME` | multi-range; the header snapshot must be taken when the **marker opens** the block, not at close — keys persist across ranges, so otherwise a 2 s range's σ comes from a 20 s one |
| `xrdml` | the document's first element is `<xrdMeasurements>` | one composition, `y = c·s` | multi-scan; the namespace is **versioned** (1.6 and 2.1 both current), so nothing matches on it and every lookup is by local name |
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
   the synthetic arm if it cannot. A **binary** format's synthesized fixture is
   written in `tests/writers_xrd.py` and **packs its offsets literally, never
   from the reader's own table**: a writer that shares constants with the parser
   can only confirm that the parser agrees with itself. Text formats' writers
   stay inline in `test_readers.py`, where a line is self-describing and the
   circularity does not arise.
5. A new rule lands here; it earns a root CLAUDE.md clause only if it changes
   behaviour outside `io/`.
