# WP-1047 — Vendor pattern formats: read the files labs actually have

Milestone: v1.0 · Status: ✅ 2026-08-09 — all 17 tasks. The seam (formats
package, option vocabulary, diagnostics channel, `xy` de-totalised, truncation
fuzz), `.chi`, the `.dif` refusal, and **seven vendor formats** — Rigaku `.ras`
and `.rasx`, Bruker `.uxd`, `.brml` and the binary `.raw` (v3/v4; **v1 and v2
refused**, see task 14), PANalytical `.xrdml` — plus the instrument hint, the
scan picker and the docs.
Depends on: 1005, 1007, 1014 (1009, 1028 soft) — landed before 1003, whose
`### Inherited` carries twelve points for the freeze

## Goal

`read_pattern` opens the seven formats a diffractometer actually writes —
`.xrdml`, `.ras`, `.rasx`, `.brml`, Bruker `.raw` (v2/v3/v4), `.uxd`, `.chi` —
refuses what it recognises but cannot honestly read (`.dif` peak lists, binary
junk) **by name rather than by traceback**, carries each file's anode and
wavelength into the import wizard, and selects among multi-scan files with a
recorded `scan=` option, all through a registry seam that makes the next
format one module.

## Context

### Today's readers, and the three failures that shape the design

Three formats today: pdCIF, GSAS raw (FXYE/ESD/STD), two/three-column ASCII —
every one a format a diffractionist exports *to*, none what an instrument
*writes*. A user with a Bruker D8, a Rigaku SmartLab or a PANalytical Empyrean
converts elsewhere first, and the `xy` catch-all makes the failure worse than
it needs to be:

- `_read_xy` (`io/readers.py:155`) calls `p.read_text(encoding="utf-8")` with
  no `errors=`, and it is the total fallback (`matches=lambda p: True`,
  `:271`). Opening a binary Bruker `.raw` raises a bare `UnicodeDecodeError`
  rather than a message naming the formats we *do* read.
- `.chi` (FIT2D/synchrotron) line 4 is `<npoints> [<ndatasets>]`. A two-token
  line 4 like `2000 1` parses as a data point `x=2000.0, y=1.0` and is
  appended.
- `.dif` is a **peak list** (Bruker DIFFRAC-AT; RRUFF d/I tables), not a
  profile. `xy` reads one happily and the package refines against ~30 delta
  functions.

Beside these, one latent cost: `_looks_gsas` (`io/readers.py:148`) does
`p.read_text(...)[:4000]` — it decodes the **whole file** and then slices, an
O(N) decode per dispatch on a 60 MB pattern.

Seven readers, pure stdlib + numpy, no new dependencies. Two things ride along
because the formats force them: most vendor files hold **several scans**, and
they all carry the **anode and wavelength** the GUI currently asks the user to
type. Same theme as 1028 and 1036, one layer down — files we did not author,
from instruments we do not own.

### Decisions taken

- **Seven formats**: `.xrdml`, `.ras`, Bruker `.raw` (v2/v3/v4 in one reader),
  `.brml`, `.uxd`, `.rasx`, `.chi`; plus hardening `xy` and refusing `.dif`.
- **Metadata travels to the import wizard** — the wizard pre-selects the anode
  preset from the file instead of making the user pick.
- **Multi-scan**: scan 0 by default, `scan=` recorded in `DataRef` the way
  `block=` is, `scan_count` visible in the preview — **and the default is
  never silent**: whenever `scan_count > 1` and `scan` was not explicit, the
  reader emits `PATTERN_MULTISCAN_DEFAULTED` (scan 0 of N). Reading a third of
  a measurement is a choice; only the GUI preview showing it would leave the
  API and CLI blind, and an assumed selection must never look like a
  deliberate one (the `INDEX_SHIFT_ALLOWANCE` rule, one seam over).

### Licensing — verified per repo, fenced per file

Checked against the GitHub API and the raw files, not assumed:

| Source | Licence | Use |
|---|---|---|
| FAIRmat `readers-xrd` | **Apache-2.0** (deps: `xmltodict`, `numpy`, `pint` — no nomad/pynxtools) | spec + fixtures |
| `bracerino/xrd-file-converter`, `paruch-group/xrdtools`, `garrekstemo/RigakuFiles.jl` | **MIT** | spec / fixtures |
| GSAS-II | custom Argonne BSD-like **with a grant-back clause** | **spec only** |
| xylib (LGPL-2.1), xrayutilities (GPL-2.0) | copyleft | concepts only |

Two fences that are not obvious:

1. `readers-xrd/src/fairmat_readers_xrd/ikz.py` — the file holding **both**
   its BRML and RASX readers — says it is "adapted from"
   `github.com/carichte/IKZ`, which has **no LICENSE file at all**. Apache-2.0
   on the wrapper does not cure an upstream that granted nothing. Structural
   spec only, no line-for-line port.
2. GSAS-II's licence grants the copyright holder "unrestricted permission to
   include any, or all, new and changed code in future GSAS-II releases" for
   derivative works.

**Therefore: every byte offset is treated as a format-specification fact and
all code is written from scratch**, sources credited in `ATTRIBUTION.md`. The
reason is sharper than caution: an offset, a magic string, a tag name and an
element path describe an *interface* dictated by the format — there is exactly
one number that is "the offset of nSteps". That is merger, not expression. So
the facts may be written down from any source (GSAS-II, the unlicensed `IKZ`)
and implemented independently, which side-steps both the grant-back and the
no-licence problem. Practically: extract offsets into a written table first,
noting which source each fact came from, then write the parser *with the
source file closed*, in this repo's idioms.

### Fixtures — and what each one can prove

| Format | Fixture | Nature |
|---|---|---|
| `.xrdml` | readers-xrd `XRD-918-16_10.xrdml` (25 kB) | **real**, 5027 pts, Cu 45 kV/40 mA, ships a `.json` **expected-value oracle** |
| `.rasx` | readers-xrd `TwoTheta_scan_powder.rasx` (34 kB) | **real powder**, 2726 pts, 10–119° at 0.04°; BOM and the `MesurementConditions0.xml` misspelling verified. ~~cps-scaled float intensities~~ — **wrong, corrected at task 11**: it declares `counts`, and no scale in 1/400…400 makes its values integral, so it is a *refuting* fixture, not a cps one |
| `.brml` | readers-xrd `23-012-AG_2thomegascan_long.brml` (651 kB) | **real**, thin-film 2θ-ω — and the file that settles the attenuator question for *some* format (its `AbsorptionFactor` varies) |
| `.raw` v4 | readers-xrd `TwoTheta_scan_scrambled.raw` (58 kB) | **real**; magic `RAW4.00\x00` and 7134 pts verified — but see the caveat below |
| `.ras` | RigakuFiles.jl `multiscan.ras`, `three_column.ras` | **synthetic** — 325–1217 bytes, 2–4 data rows. Good for structure (2 scans, 2-vs-3 columns, header keys); proves nothing about real data |
| `.raw` v2/v3, `.uxd`, `.chi`, `.dif` | none | synthesized from spec |

**Verify fixture licences per *file* before writing the corresponding
reader.** A repo LICENSE covers the repo's own work; several of these files
are vendor instrument outputs contributed by users, and the grant may not
convey them. If a fixture cannot be vendored, that format's whole test
strategy changes.

**Verify what "scrambled" means in the v4 fixture before asserting values
from it.** It is the only real Bruker binary, and the plausible reason for
the name is that FAIRmat anonymised it. If the scrambling touched header
fields or intensities, the fixture proves structure but not values — and the
acceptance line for `.raw` must then claim structure, not values.

### The Rigaku columns — two undecidables, one stated contract each

**The attenuator.** The `.ras`/`.rasx` **third column is an attenuator
factor**, and no source says whether column 2 is already corrected for it.
GSAS-II and FAIRmat both discard it — a convention, not a measurement. Every
obtainable fixture was checked: `three_column.ras` has column 3 identically
`0.0000` (not a physical attenuator value) and the real `.rasx` powder scan
has it constant at `1`. **No fixture we can obtain settles it.** There is a
decisive structural test if a varying column is ever found: where column 3
changes, either the raw series steps and `col2 × col3` is continuous, or the
reverse. Try it first. **That test has since run twice, on other formats, and
answered differently each time** (tasks 10 and 12): `.xrdml` stores the
attenuated counts and the factor must be applied, `.brml` stores the corrected
intensity and it must not. So the Rigaku answer cannot be borrowed from either,
and this contract stands. Absent that, ship the "absent for cause" contract:
read column 2 as the intensity (matching both other codes, so cross-code
comparison holds), and whenever column 3 is not identically 1 emit
`RAS_ATTENUATOR_PRESENT` naming the affected 2θ range, saying the correction
was not applied because the convention could not be verified, **and that σ is
affected too**. Getting this wrong silently corrupts exactly the strong peaks
Rietveld weights most, so it does not get guessed.

**The intensity scale.** Whether `.ras` column 2 is cps or counts is
**unverified on the same grounds**: the cps determination was made on the
real `.rasx` fixture — a different container — and the only `.ras` fixtures
are the synthetic ones that prove nothing. The convention ("both other codes
treat it as cps") is not evidence, and σ is wrong by √t whichever way the
guess misses. So the reader measures per file instead of quoting a
convention: derive t = step ÷ `*MEAS_SCAN_SPEED` where the header carries a
speed, then test the stored values — counts are integers, so column 2 all
near-integer ⟹ counts (σ = √y), column 2 × t all near-integer ⟹ cps
(σ = √(y/t)); at t = 1 the two coincide and there is nothing to decide. Where
neither test is decisive, supply no σ and emit the
`PATTERN_INTENSITY_SCALED` diagnostic below — the fallback is then being
applied to a quantity whose scale could not be verified, and the caveat says
so rather than the weights being silently wrong.

### Module layout — `io/formats/`

`readers.py` becomes the **front door only** (`read_pattern`,
`identify_format`, `list_scans`, and re-exports of `PatternFormat` /
`PATTERN_FORMATS` / `read_pdcif`), so **no existing call site changes**.
Parsers move to `io/formats/`, one module per format, plus `base.py` (the
`PatternFormat` dataclass, `READER_OPTIONS`, `ScanInfo`, `METADATA_KEYS`, and
the shared `head()` / `looks_binary()` / `ascending()` / `sigma_from_cps()`
helpers) and `__init__.py` (the ordered `PATTERN_FORMATS` and why that
order).

The reason is not line count: a format's spec citation, its parser, its
`sniff`/`sigma` prose, its options and its **licence fence** are one fact
each and belong adjacent. Ten fences in one file drift.

### Dispatch — strongest evidence first, one bounded head read

Order — magic bytes > zip manifest > required first line > XML root > suffix >
loose text sniff > refusal > fallback:

```
bruker_raw   magic ∈ {RAW , RAW2, RAW1.01, RAW4.00}      8 bytes
brml         PK\x03\x04 + a RawData*.xml member
rasx         PK\x03\x04 + a Data*/Profile*.txt member
xrdml        first XML element's local-name is xrdMeasurements
ras          first line == *RAS_DATA_START
uxd          first non-";" line begins _FILEVERSION
pdcif        .cif suffix                                 (unchanged)
gsas         ^BANK \d+ in the first 4 kB                  (unchanged)
chi          the four-line header shape (see below)
dif_peaklist .dif suffix AND peak-list content            → refuses
xy           text, not binary                             (last, no longer total)
```

The `.raw` collision is resolved **by construction**: `bruker_raw` tests
magic bytes, `gsas` tests `^BANK`, and the sets are disjoint — a GSAS file
named `.raw` still reaches `gsas`, a Bruker file named `.gsas` still reaches
`bruker_raw`. Test both directions. Binary still goes first so nothing
decodes it.

**`xy` stops being total**: `matches = not looks_binary(head)` (a NUL in the
first 4 kB). That is the right home for the hardening — "does this format
claim the file" already lives in `matches`, and a separate guard would be a
second place that knows about binary files. **One carve-out: a UTF-16 BOM
(`FF FE` / `FE FF`) means text, never binary** — ASCII-range UTF-16LE decodes
as *valid* UTF-8 with interleaved NULs, Windows vendor software genuinely
exports it, and "looks binary" on a text file would be the
confident-wrong-message class this WP exists to remove. `head()` reports the
BOM and `_read_xy` decodes UTF-16 when it is present; today such a file dies
with "no numeric data found", so this is strictly new reach.
`identify_format`'s terminal `raise` becomes reachable (drops its
`# pragma: no cover`) and its message is **built from the registry**: "…is
not a powder pattern this build can read (it looks binary); supported: …".
Grep the suite for tests assuming `identify_format` never raises before
landing this.

N header reads per dispatch is not worth solving (~5 × 4 kB), but
`_looks_gsas`'s whole-file decode is: route every text sniff through one
bounded `head(path, n=4096)`. Do **not** cache it: `restage` re-reads the
same path, and a path-keyed cache would be a correctness hazard for exactly
the file a user just replaced. **The bounded-head rule has exactly one stated
exemption, `.chi`'s count check** (below) — rare because it sits behind the
shape gate, and worth its O(N) because it is decisive.

### The generalised option passthrough

`project.py` already calls `read_pattern(copied, **options)` (`:131`) and
`read_pattern(path, **_reader_options(ref))` (`:215`) — only the *signature*
(`:101`) and the *guard* (`:130`) hardcode `block`. So this is smaller than
it looks. Two levels, because `scan` means the same thing in five formats:

```python
READER_OPTIONS: dict[str, ReaderOption]   # name → kind, default, UI help prose
def reader_options_for(fmt, requested) -> dict   # coerce + filter, one authority
def read_pattern(path, *, diagnostics=None, **options): ...
```

`PatternFormat.options` stays `tuple[str, ...]`, so `ReaderCapability.options`
and `Model.svelte:670`'s `options.includes("block")` keep working. A name
absent from `READER_OPTIONS` is a typo and raises; a real option this format
does not take is **dropped** — a UI carries a value across a file change and
that is normal — but the drop is **reported, not silent**: it emits
`READER_OPTION_IGNORED` on the diagnostics channel, which the GUI is free to
ignore and the agent surface is not, because an API caller who passed
`scan=2` against a single-scan format believed they selected something.
`DataRef` records the **effective** options — the ones the parse actually
used, which are what reopening must replay; the fingerprint pins their
semantics, and a requested-but-ignored key recorded there would change
nothing and mislead. Coercion lives in `reader_options_for`:
`DataRef.options` is `dict[str,str]`, so `scan` round-trips as `"2"` and must
reach the reader as `int` 2.

Sites that name `"block"` take the registry union instead (`project.py:130`,
`imports.py:218`, `server.py:294`, `session.py:275`). `Project.create(block=)`
becomes `reader_options=` — **dropped, not shimmed**: the freeze (WP-1003)
has not landed, a shim is a second authority, and every call site is in this
repo (grep the docs for `block=` too). Meta-test that makes the allowlist
real: `set(READER_OPTIONS) == ∪ fmt.options`.

### Descending 2θ — give `read_pattern` the channel that already exists

`PatternData` requires strictly increasing 2θ; several formats store a scan
measured high→low. Root CLAUDE.md says a silent correction is a reader's to
make "only where the deviation is a *report* rather than a contradiction",
recorded as a `Diagnostic`. `read_pattern` returning a bare `PatternData` is
an accident, not a design — `structure_from_cif` already has the mechanism
(`cif.py:132`, `diagnostics: list[Diagnostic] | None = None`), and its
docstring states this exact argument. So `read_pattern` grows the same
keyword, defaulted, non-breaking, no new concept. Then apply the rule's own
test in one shared `ascending()` helper every reader passes through:

| deviation | verdict | action |
|---|---|---|
| strictly descending | **report** — same measurement, stored backwards; reversal is lossless | reverse (2θ, y, σ), `PATTERN_SCAN_REVERSED` |
| duplicate 2θ, equal y | report — format artefact | drop, `PATTERN_DUPLICATE_POINTS` |
| duplicate 2θ, **different** y | **contradiction** — averaging invents a datum, dropping picks one | raise, naming the 2θ |
| non-monotone (stitched, restarts) | contradiction — concatenate, sort, or separate? | raise; name the `scan` option **only for a format that has one** |
| non-constant step | neither | nothing (SRM660c is 24 stitched regions and is legal) |

This establishes a rule worth carrying to root CLAUDE.md: **a multi-range
file's ranges are scans, selected by `scan`, never concatenated.** GSAS-II
concatenates, which silently mixes two step sizes and two counting times into
one weighting regime. Refusing also makes the touching-endpoint case
disappear.

Consumers: `preview_pattern` returns the diagnostics (the wizard is where a
human should see a repair); `cli.py` prints them; `Project.open` keeps them
in memory but adds **no** `project.json` field — they are a deterministic
function of bytes + reader + options, all three already recorded. Putting
repairs in the reader also puts them under the fingerprint check, so a later
change to a repair fires the existing "a reader change, not a corrupt
project" message (`project.py:216`).

### Two cross-cutting invariants

**(a) A reader raises `ValueError`/`OSError`, never a codec/struct/zip/XML
exception.** `preview_pattern`'s allowlist (`imports.py:221`) is
`(ValueError, OSError, RuntimeError, KeyError, IndexError)`. Six new
container parsers will raise `struct.error`, `zipfile.BadZipFile` and
`ET.ParseError` — none of which is in it, and `ET.ParseError` subclasses
`SyntaxError`, so it escapes as a 500. Each parser converts at its own
boundary, filename in the message. The test that earns its keep: truncate
each real fixture at 20 offsets and assert every failure is
`ValueError`/`OSError` naming the file.

**(b) σ is derived, never faked, wherever intensity is not raw counts** — an
addition to the Weights invariant, which today only says "use the file's esd
column when present":
- `.xrdml` raw counts → `sigma=None`; the Poisson fallback is *correct*. (The
  element name is not the evidence — the real fixture is
  `<intensities unit="counts">`; the **`unit` attribute** is.)
- cps **with** a counting time → σ = √(y·t)/t, supplied.
- cps **without** a counting time, or a scale the per-file test cannot
  decide → `PATTERN_INTENSITY_SCALED`: the fallback is being applied to a
  scaled quantity and the weights are wrong by √t.
- `beamAttenuationFactors ≠ 1` → σ = √counts · attn ≠ √y. This is the case
  GSAS-II gets wrong (`w = 1/y` regardless).

  ~~`.rasx` by fixture~~ — **corrected at task 11**: the cps determination was
  never made on `.rasx`. Two of its three real files declare `counts` and store
  values no scale rationalises, so it takes the `.ras` arithmetic
  (`base.sigma_by_arithmetic`, now shared). The trustworthy-declaration formats
  are `.uxd` (block marker) and `.xrdml`/`.brml` (a schema-enumerated attribute
  on the data element).

`METADATA_KEYS` in `base.py` is **data**, with a builder that refuses an
undeclared key — otherwise the anode pre-selection has nothing stable to
match on. `scan_count` travels in the pattern's metadata from the **single**
read, so the preview needs no second parse of a 60 MB file; `list_scans` is
for the CLI and the scan-picker fetch, not the preview path.

### `.dif` refusal, and `.chi`'s axis

`PatternFormat` gains `refuses: str | None` (prose: why this is recognised
*in order to be refused*), mirrored on `ReaderCapability`. One field, one
authority, and `capabilities()` stays honest because the field says which
entries are refusals — better than a side table, which would make
`reader_formats` mean two things. Match on **evidence, not suffix** (`.dif`
*and* peak-list content), so a real profile misnamed `.dif` still falls
through to `xy`.

`.chi`: store line 2 verbatim as `x_label`; recognisably 2θ → read;
recognisably **q or d → raise**, quoting the label (reading a q axis as 2θ
yields a confident wrong cell from values that parse perfectly — the exact
failure class this package refuses); unrecognisable → read as 2θ with
`CHI_X_AXIS_ASSUMED`. `matches` is two gates: the **shape** — lines 1–3
non-numeric and uncommented, line 4 one or two integers — comes from
`head()` and is bounded; only when the shape passes does the second gate read
the file once and require `int(line4[0])` to equal the number of remaining
data lines. That count is the one stated exemption to the bounded-head rule:
it is O(N), it runs only behind the shape gate, and it is what keeps an `.xy`
with a three-line text header falling through to `xy` instead of being
claimed. Decisive is worth one read; it is not "free" and the code comment
should not call it that.

### Anode pre-selection — server side

`INSTRUMENT_PRESETS` (`imports.py:382`) and `wizard.ts:18` both state the
rule: "the presets themselves are the authority on wavelengths — an anode
name resolves against the package's NIST-scale table, so no client ever
types a wavelength." Matching an anode is a physics judgement against
`_KA_DOUBLETS` (`instrument.py:758`), so
`suggest_instrument(metadata) -> dict | None` lives in `imports.py`;
client-side matching would be a second copy of the anode vocabulary in
TypeScript.

Match **wavelength first** (rtol ≈ 5e-4), against **three candidates per
anode**: Kα1, Kα2, and the intensity-weighted mean (2λ₁ + λ₂)/3 — the mean
because it is what `.uxd` and older exports actually quote (1.5418 for Cu),
and 1.5418 vs Kα1 is 7.8e-4 relative, *outside* the tolerance: without the
mean in the candidate set, the most common lab metadata value in existence
would read as "name and wavelength disagree". The mean and Kα1 both resolve
to the doublet preset; `…Ka1` only when Kα2 is absent or the ratio is 0 (a
real incident-beam-monochromator distinction `_RADIATIONS` already carries);
anode name as fallback; and **no suggestion at all** when name and wavelength
disagree — with disagreement judged *after* the mean is a candidate, so a
convention difference is never read as a contradiction. That case is a file
to look at, not to guess from. The file's own λ is recorded, never used: the
real fixtures give 1.540598 (`.xrdml`) and 1.540593 (`.ras`) against the
package's 1.5405929, a ~3 ppm spread that is real but far inside the 48 ppm
the SRM 660c acceptance allows. Where λ matches no anode, suggest
`debye_scherrer(wavelength=…)` — the synchrotron/monochromated case, and the
one where the file does know better. Seed `goniometer_radius_mm` the same way
(Bruker v3 `0x234`, `.xrdml` `incidentBeamPath/radius`): two of the four
`bragg_brentano` numbers then come from the file, which is the actual win.

### Contract versions — the bookkeeping, decided

Three of the five versioned contracts are touched; each gets a one-line
decision here so no session re-litigates it:

- **textdoc — no bump.** `textdoc.py:310` renders `block` inside a `#`
  comment and `scan` joins it there; widening a comment is not a grammar
  change. Confirm against `render()`'s grammar note when landing.
- **project format — minor bump.** `DataRef.options` gains `scan` in its
  vocabulary. An old build opening such a project dies with a bare
  `TypeError` at `project.py:215` (old `read_pattern` signature) *before*
  any versioned check fires — unfixable retroactively, and the minor bump is
  the honest record that the vocabulary grew. The major-version gate
  (`project.py:189`) still opens it, correctly.
- **schema — no bump.** `ReaderCapability` gains `refuses` (and `scans`);
  additive fields mirror the events rule (`history/events.py`): adding a
  field to a kind is not a bump, a new kind is.

## Non-goals

- **Philips/PANalytical legacy `.rd`/`.udf`, Stoe, Scintag** — probably the
  most common real-lab formats *not* on the list; declining them is a
  decision, not an oversight. The `io/formats/` seam makes each a one-module
  follow-up.
- Seeding polarization or monochromator geometry from vendor metadata — the
  preset bundles carry those; this WP seeds anode and radius only.
- Joint refinement of several scans (`multi.py` stacking) or series
  semantics (`sequential.py`) — `scan=` selects one, never combines.
- Writing any vendor format.
- The freeze itself (WP-1003) — this WP only leaves the note in its
  `### Inherited`.

## Tasks

Tasks 1–5 are the seam and form a complete, shippable state; **if this WP
becomes two sessions, the boundary is after task 5** (plus the doc slices
that belong to it), never mid-format.

- [x] 1. Split into `io/formats/`; `readers.py` becomes the front door;
      `head()` (with BOM detection) replaces `_looks_gsas`'s whole-file
      decode. Pure refactor, **zero call-site edits**, suite green.
- [x] 2. `READER_OPTIONS` / `reader_options_for` / `read_pattern(**options)`;
      thread through project, imports, series, server, session, textdoc,
      wizard; drop `Project.create(block=)`; `DataRef` records effective
      options. Meta-test on the allowlist union.
- [x] 3. Diagnostics channel + the `ascending()` monotonicity policy +
      `READER_OPTION_IGNORED` + `PATTERN_MULTISCAN_DEFAULTED` + codes in
      `docs/AGENT_PROTOCOL.md`; preview payload and CLI print.
- [x] 4. `xy` stops being total (`looks_binary`, UTF-16 BOM = text, UTF-16
      decode in `_read_xy`); `identify_format`'s message built from the
      registry; grep for tests assuming it never raises.
- [x] 5. The truncation-fuzz harness; widen `imports.py:221`.
- [x] 6. `.chi` — reader, the two-gate `matches` (shape from `head()`, count
      as the stated exemption), axis policy. Regression test that today's
      phantom point is gone.
- [x] 7. `.dif` — `PatternFormat.refuses` + `ReaderCapability.refuses`.
- [x] 8. `.ras` — reader, the `scan` option, `ScanInfo` / `list_scans` /
      `fmt.scans` with the biconditional meta-test
      (`"scan" in options ⟺ scans is not None`), `METADATA_KEYS`, the
      attenuator contract, the per-file intensity-scale test, the
      `PROJECT_FORMAT_VERSION` minor bump (first `scan` recorded).
- [x] 9. `.uxd` — all four block forms (`_COUNTS`/`_CPS` × the `_2THETA`
      prefix, read as two independent facts), multi-range. The **second**
      consumer of `scan`, which is what proves the option is generic rather
      than `.ras`-shaped.
- [x] 10. `.xrdml` — namespace-agnostic root, all three `positions` forms,
      the counts/intensities σ rule, `beamAttenuationFactors`, multi-scan.
      Tested against the JSON oracle exactly.
- [x] 11. `.rasx` — in-memory `ZipFile.open` with a **bounded read**
      (`read(cap + 1)`, refuse if over — `ZipInfo.file_size` is header
      metadata and is not trusted; never `extract()`), BOM skip, the
      misspelled conditions file.
- [x] 12. `.brml` — `DataContainer.xml` → `RawData<N>.xml`, channels located
      via `DataViews/RawDataView[@Start][@Length]`, **not** GSAS-II's
      `entry[2]`/`[4]`, which are not stable across files. Same bounded-read
      zip rule as 11.
- [x] 13. `.raw` v4 — first, establish what "scrambled" scrambled (header?
      intensities?) and record it in `tests/data/README.md`; then the TLV
      segment walker, **stride by `datumSize`** (FAIRmat's "interleaved
      float32 pairs" note is a `datumSize==8` misread; GSAS-II reads the
      field then ignores it), walk to EOF rather than counting `b'2Theta'`.
- [x] 14. `.raw` **v3** + the v1 **and v2** refusals — synthesized bytes. The
      `+40` / `int32@+256` ambiguity needed no validation scheme in the end:
      a third description (`reductus`, Unlicense — Bruker's own field names)
      names the two fields both other readers patch around,
      `data_record_length` (+252) and `total_size_of_extra_records` (+256), so
      the data offset is arithmetic. **v2 was dropped from scope**: exactly one
      uncorroborated description of it exists and no file, which is the
      confident-wrong read this WP exists to prevent — it is refused by name and
      version instead, and the `io/formats/` seam makes it a one-module
      follow-up if a real file ever appears.
- [x] 15. Instrument hint — `suggest_instrument` with the three-candidate λ
      match (Kα1 / Kα2 / weighted mean), preview payload, wizard pre-fill.
- [x] 16. Scan picker on the wire — `scans` in the preview (from the single
      read's metadata), the control (already option-gated at
      `Model.svelte:670`), `DataRef.options["scan"]` round-trip.
- [x] 17. Docs — `ATTRIBUTION.md` (four permissive rows, xylib listed
      *precisely to state it was not ported*, the GSAS-II grant-back
      reasoning, the `ikz.py` fence, and a new "Format specifications"
      subsection); `tests/data/README.md` rows; `capabilities` spot-checks;
      the `test_gui_server.py:443` dispatch matrix; `cli.py:86`'s
      already-stale help string; README; three new root CLAUDE.md rules
      (scans are never concatenated; `PatternFormat.options` is the only
      allowlist; cps gets a derived σ); ROADMAP row + focus; the v1.0
      narrative; and the note into WP-1003's `### Inherited`, since this
      changes `DataRef`'s option vocabulary the freeze will cover.

Synthesized fixtures live in a **writer module** (`tests/writers_xrd.py`,
precedent `test_project.py::_write_xye`), generated into `tmp_path` — so no
`tests/data/README.md` rows, which is the honest outcome: there is no
provenance to record. Three things keep the round-trip from being circular,
and they go in that module's docstring: the writer packs literal offsets and
must **not** share a table with the reader; the offsets are cross-checked
against a second independent description and the docstring records which two
sources agree; and the reader carries a **self-consistency gate**
(`start + step·(n−1)` equals the last 2θ; `headLen + datumSize·nSteps` lands
exactly on the next header or EOF) so it raises rather than returning
plausible garbage.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_readers.py tests/test_readers_robust.py \
    tests/test_capabilities.py tests/test_project.py tests/test_gui_server.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m ruff check src tests examples
```

Each of the seven formats opens its fixture and reports the anode and
wavelength its header carries; the `.xrdml` matches its independent oracle
exactly; a `.uxd` quoting `Cu` and `1.5418` still yields the CuKa doublet
suggestion (the weighted-mean case); a binary file and a `.dif` peak list are
each refused **by name**, not by traceback; every truncation of every fixture
fails as `ValueError`/`OSError`; opening a multi-scan file without `scan=`
carries `PATTERN_MULTISCAN_DEFAULTED`; and a `.pxrd` project created from a
multi-scan file reopens on the scan it was created from.

## Risks, in the order to retire them

1. **Fixture licences are per *file*, not per repo.** Changes the whole test
   strategy for a format if one fails. Check before writing that reader.
2. **The `.ras` attenuator question is undecidable from any fixture we
   have** — so the reader ships a stated contract rather than a guess; the
   intensity-scale question gets the per-file test for the same reason.
3. **The v4 fixture is "scrambled" and may also carry `datumSize == 4`** —
   either way the stride bug may have no real-file coverage and needs a
   synthesized 8-byte companion; establish both facts before relying on it.
4. **`.brml`'s `RawDataView[@Start][@Length]`** — the whole channel-location
   design rests on those attributes being present; verify against the real
   file (including the `xsi` namespace spelling) before committing to it.
5. **Bruker v2/v3 have no real fixture at all.** Mitigated by the
   self-consistency gate and the two-source offset cross-check — not by the
   round-trip, which proves nothing on its own.
6. **17 commits is plausibly a two-session WP.** The boundary is stated
   above (after task 5); each format after that is independent, so a session
   can stop cleanly between any two. `tests/CLAUDE.md`'s counting discipline
   applies: passed+skipped moves by exactly N in both selections, quoted
   with venv and platform.

## References

- FAIRmat `readers-xrd` (Apache-2.0) — spec + fixtures; its `ikz.py` is
  fenced (unlicensed upstream).
- `bracerino/xrd-file-converter`, `paruch-group/xrdtools`,
  `garrekstemo/RigakuFiles.jl` (MIT) — spec / fixtures.
- GSAS-II source (Argonne licence, grant-back) — **spec only**; xylib
  (LGPL), xrayutilities (GPL) — concepts only.
- `src/pxrdref/io/readers.py`, `src/pxrdref/project.py`,
  `src/pxrdref/gui/imports.py`, `src/pxrdref/capabilities.py` — the seams.

## Handover log

- **2026-08-09 (session 4)** — **tasks 10-12 landed**, the three container
  formats, on branch `wp1047-vendor-formats` (7 commits, 18 off `main` @
  `fad8a6d`). No `### Inherited` to prune — the WP has never had one.

  **Done.** (10) PANalytical `.xrdml`, (11) Rigaku `.rasx`, (12) Bruker `.brml`,
  plus one factoring that had to come first and one review pass that had to come
  last.

  **The session's through-line is one question asked of four vendors: is the
  stored intensity already corrected for the beam attenuator?** `.ras` could not
  answer it — every obtainable Rigaku file has the column constant — so its
  reader ships a contract and reports. The containers *can*, because a real file
  of each has a factor that **varies**, and the structural test is the one
  `ras.py`'s docstring had written down without being able to run: where the
  factor changes, does the raw series or the product run continuously? Run twice,
  it answered in opposite directions.

  - `.xrdml` — `panalytical_attenuator.xrdml` puts one point of the GaAs 004
    substrate peak behind a **188×** foil, and the raw series *dips* 87 % there
    (1341, 14602, **1877**, 13749). A hole in the apex of a substrate reflection
    is the attenuation, not a profile, so the factor **is applied**; FAIRmat's
    reader computes the same product independently.
  - `.brml` — the absorber engages over 29 points at **8.3×**, and there the
    *stored* series is the continuous one while `y/a` is the integral one (`y`
    is not, `y × a` is not). So Bruker stores the corrected intensity and
    **nothing is multiplied**.
  - Either way σ goes through the factor — √counts·a is not √y — which is the
    case GSAS-II gets wrong by weighting 1/y regardless.

  **A third premise of this WP was wrong and is struck in place.** It recorded
  `.rasx` cps as "verified by fixture"; it was never measured on that format.
  Two of its three real files declare `<IntensityUnit>counts</IntensityUnit>` and
  store values no scale in 1/400…400 — nor the file's own derived 2.4 s counting
  time — makes integral, while the third declares counts and *is* integral to the
  last of 7001 points. Both arms are vendored, so one format now shows the test
  deciding both ways. `.rasx` therefore takes the `.ras` arithmetic, now
  `base.sigma_by_arithmetic` and shared; the trustworthy declarations turn out to
  be exactly the **structural** ones. (A fourth, smaller correction: `.xrdml`'s
  counts/cps distinction is the `unit` *attribute*, not the element name — the
  real powder file is `<intensities unit="counts">`.)

  **Two factorings, both at triggers a previous session named.** The axis policy
  became `base.check_axis()` with one code `PATTERN_X_AXIS_ASSUMED`, because
  `.xrdml` was the fourth consumer and `src/pxrdref/io/CLAUDE.md` said the fourth
  is when — which settles point 6 of WP-1003's `### Inherited` rather than
  passing it on. What is deliberately *not* shared is the classifying: four
  formats state their axis in four shapes. And `sigma_from_scaled` /
  `sigma_by_arithmetic` / `decode` moved to `base` as their second consumers
  arrived, never before.

  **Design rules the real files forced, worth carrying:**
  - **Nothing is located by counting.** `.brml` puts 2θ at datum column 2 and the
    intensity at column **7**, so GSAS-II's fixed `entry[2]`/`entry[4]` is one
    layout's coincidence; the reader reads `DataViews`' `Start`/`Length`/
    `FieldDefinitions` instead.
  - **A manifest outranks a zip's name list.** The 801-scan `.brml` stores its
    members …20, 22, 21, `experimentCollection.xml`, 23…
  - **A `RecordedRawDataView` of `Length > 1` is a detector frame**, refused —
    and its `ScanAxes` still claims `AxisId="TwoTheta"`, so the axis check passes
    and only that length says the rows are not a profile.
  - **`ScanInformation` wins over a like-named leaf elsewhere** in a `.rasx`
    conditions XML; `Step` and `Speed` are generic enough for an optics block to
    carry one, and first-wins document-wide would derive every σ from it.

  **Counts**, `[dev,jax,torch]` venv, darwin. Fast selection 2124 → **2177
  passed, 5 skipped**: **+53** with no new skips, and every one is accounted for
  — axis factoring +1; task 10 **+22** (14 tests, 2 real fixtures × 3
  truncation-fuzz rows, 2 upload-dispatch rows); task 11 **+14** (10 tests, 1
  fixture × 3, 1 synthetic-fuzz row); task 12 **+14** (8 tests, 1 fixture × 3, 1
  synthetic-fuzz row, 2 upload rows); the review pass +2. Full selection
  **2282 passed, 6 skipped**, measured at `0a5d77a` — i.e. before the review
  pass's two (fast-selection) tests, so the final tree is **2284 + 6**. That
  closes exactly against the previous session: its full selection resolved to
  2231 + 6 = 2237, and 2237 + 51 (the fast delta at `0a5d77a`) = 2288 = 2282 + 6.
  vitest **401**, svelte-check clean, ruff clean. **No GUI dist rebuild**: no new
  reader option and no payload *shape* change, so the wizard grows each format's
  scan picker from `capabilities()` unaided.

  **Wall clock**, as a range: the fast selection ran 175-186 s on a quiet machine
  and 338 s while the full suite shared it; the full selection 32:56, one
  measurement and a *loaded* one — a fast run overlapped roughly six minutes of
  it, against the previous session's 25:44 unloaded.

  **Risks 1 and 4 retired; 3 is the one left.** Fixture licences: all four
  readers-xrd files were committed by that repo's own maintainers into an
  Apache-2.0 repo, and the unlicensed `carichte/IKZ` upstream the `ikz.py` fence
  guards holds 15 files and **no data at all** — so the fence is about code and
  does not reach these bytes. `.brml`'s `RawDataView[@Start][@Length]` is present
  in both real files, and the `xsi` prefix is read through its **namespace**
  rather than as text (a test renames it to `zz:`).

  **In flight: nothing** — tree clean, both selections green, shippable between
  any two formats.

  **Next**: task 13 `.raw` v4, then 14 `.raw` v2/v3, 15-16 the instrument hint
  and scan picker, 17 the remaining docs. The binaries are a different kind of
  work from the containers — offsets rather than manifests — and
  `tests/writers_xrd.py` (still unwritten) is for them, not for the text formats.

  **Gotchas for the successor.**
  - **Retire risk 3 before writing task 13's reader.** What "scrambled"
    scrambled in `TwoTheta_scan_scrambled.raw` decides whether `.raw`'s
    acceptance line may claim values or only structure. Nothing this session did
    touched it.
  - **The attenuator answer cannot be borrowed across vendors** — four formats,
    three answers, all measured. If `.raw` carries one, run the same test: find a
    file where the factor varies and ask which series is continuous.
  - **Part of task 17 has already landed** and should not be redone: ATTRIBUTION
    gained rows for `.xrdml`/`.rasx`/`.brml`, the `readers-xrd` + `ikz.py` fence
    and the xylib "listed precisely to state it was not ported" row;
    `tests/data/README.md` gained three sections; AGENT_PROTOCOL gained
    `XRDML_ATTENUATOR_APPLIED` and `BRML_ABSORBER_ENGAGED` and lost two axis rows
    to one; README's reader row and the root/`io` CLAUDE.md rules are current.
    What task 17 still owes: the `.raw` rows, `cli.py`'s help (already
    registry-built, so check rather than edit), and the capabilities spot-checks.
  - **`src/pxrdref/io/CLAUDE.md`'s cap went 200 → 250** with three formats still
    to land; root CLAUDE.md is back at **exactly 600** after the reader bullet
    was compressed to carry a fifth consequence. Budget for that again.
  - **`tests/test_portability.py` now skips a receiver containing `zip`** —
    `zipfile.ZipFile.open` returns bytes whatever its mode, so `encoding=` there
    is a `TypeError`. That is why the container readers name their handle
    `zip_*`; keep the convention or the meta-test fails.
  - The two large real files that were **not** vendored —
    `RSM_111_sdd=350.rasx` (401 scan groups) and `EJZ060_13_004_RSM.brml`
    (801, and the PSD frame) — have what they established recorded in
    `tests/data/README.md`. If a `.rasx`/`.brml` bug ever needs a real
    multi-scan archive, that is where to look for it.

- **2026-08-09 (session 3)** — **tasks 8-9 landed**, `.ras` and `.uxd`, on
  branch `wp1047-vendor-formats` (8 commits off `main` @ `fad8a6d`). No
  `### Inherited` to prune — the WP has never had one.

  **Done.** (8) Rigaku `.ras`: reader, the `scan` option, `ScanInfo`/
  `list_scans`/`fmt.scans` with the biconditional meta-test, `METADATA_KEYS` +
  `base.metadata()` (every existing reader routed through it),
  `PROJECT_FORMAT_VERSION` 1 → **1.1**, the attenuator contract, the per-file
  intensity-scale test. (9) Bruker `.uxd`: all four block forms, multi-range,
  the second `scan` consumer — which is what it was for, and *nothing* in the
  option machinery moved to accommodate it.

  **Three of the WP's premises were wrong and are now corrected in place.**
  The WP said no real `.ras` was obtainable; three are, all MIT, and they
  showed (a) `*MEAS_SCAN_SPEED_UNIT` exists and says `deg/min`, so the planned
  `t = step ÷ speed` was 60× short and every derived σ would have been wrong by
  √60; (b) `*MEAS_SCAN_UNIT_Y` declares the unit **and can be false** — one file
  declares `counts` and stores 84.3047, which no scale in 1/1000…200 makes
  integral — so the declaration is metadata and arithmetic decides; (c)
  `*MEAS_SCAN_AXIS_X` can be `Omega`, a rocking curve, which needed the `.chi`
  axis policy generalised. `.uxd` then supplied the contrast: it declares the
  unit *structurally* (the token opening the data block) and that one holds, so
  it is trusted. **That asymmetry is the session's rule** and it is in root
  CLAUDE.md.

  **Counts**, `[dev,jax,torch]` venv, darwin. Fast selection 2094 → **2124
  passed, 5 skipped**: **+30** with no new skips, and every one is accounted
  for. Task 8 **+20** (`test_readers.py` 16, `test_project.py` 1,
  `test_readers_robust.py` one fixture row × 3 parametrized tests); task 9
  **+9** (8 tests + one parametrized synthetic-fuzz row); and **+1 that is not a
  test anyone wrote** — `test_always_loaded_docs_stay_under_their_pinned_caps`
  is parametrized over `SIZE_CAPS`, so adding `src/pxrdref/io/CLAUDE.md` to it
  added a row. Worth stating rather than absorbing: a count can move for a
  documentation-structure reason. Full selection measured mid-session at
  **2229 passed, 6 skipped + 1 failed** (the failure was the CLAUDE.md cap
  assertion, before the consolidation resolved it): 2229 + 1 = 2230 = the
  previous session's 2201 + 29, i.e. it moved by exactly the fast selection's
  then-delta, as it must with no new `slow` marks. It was **not** re-measured
  after the consolidation, which would put it at 2231. vitest **401**, svelte-check clean, ruff clean. No GUI dist
  rebuild: the wizard renders one control per reader option from
  `capabilities()`, so `.ras`/`.uxd` get their scan picker with no payload
  *shape* change.

  **Wall clock**, as a range: the fast selection ran 184-186 s across three runs
  on a quiet machine (the session-start baseline was 320 s on a busy one); the
  full selection 25:44, one measurement.

  **Three bugs the harnesses caught, not review.** (i) `.uxd`'s header snapshot
  was taken at block *close*, and keys persist across ranges — so a 2 s range's
  σ came from the next range's 20 s `_STEPTIME`. (ii) A truncation cut mid-row
  makes a ragged list and numpy's "inhomogeneous shape" `ValueError` names no
  file; fixed in both readers. (iii) **An invariant that had never held**: the
  truncation harness asserts every refusal names the file, and a `.XRA` cut past
  its `BANK` record fell through to `xy`, parsed one point and raised
  *pydantic's* report — which passed only because pydantic echoed the metadata
  dict, filename included. Adding one metadata key pushed the name past that
  echo's truncation. `base.pattern_data()` is now the schema boundary and every
  reader goes through it.

  **Structural change, decided with the user**: root CLAUDE.md was at exactly
  its 600-line cap with four vendor formats still to land, so the reader detail
  moved to **`src/pxrdref/io/CLAUDE.md`** (179 lines, capped at 200, loads under
  `io/`) and root kept only the four consequences a caller outside `io/` sees.
  Same move WP-1060 made for indexing. `SIZE_CAPS` and the link-check doc list
  in `tests/test_docs_consistency.py` both know about it.

  **In flight: nothing** — tree clean, both selections green, shippable between
  any two formats.

  **Next**: task 10 `.xrdml` (real fixture + a JSON oracle, Apache-2.0), then 11
  `.rasx`, 12 `.brml`, 13-14 Bruker `.raw`, 15-16 the instrument hint and scan
  picker, 17 the remaining docs. All four remaining formats are containers or
  binary, which is a different kind of work from these two.

  **Gotchas for the successor.**
  - **Risk 1 has now fired twice.** Fixture licences are per *file*: the best
    `.ras` found (8501 points of real integer counts, `Dinghao-Wu/xrd-toolkit`)
    is in a repo with **no LICENSE at all**, and every obtainable real `.uxd` is
    GPL or unlicensed. Check before writing the reader, because it changes the
    whole test strategy — and record what an unvendorable real file *established*
    in `tests/data/README.md`, since that becomes the only place the design is
    checkable.
  - Risk 3 is **untouched**: what "scrambled" scrambled in
    `TwoTheta_scan_scrambled.raw` still decides whether `.raw`'s acceptance line
    may claim values or only structure. Establish it before task 13.
  - **Three formats now implement the same three-way axis policy** with three
    codes (`CHI_`/`RAS_`/`UXD_X_AXIS_ASSUMED`). Left unfactored deliberately —
    the inputs are different shapes (a prose label, a header key, a drive name)
    — but a **fourth is the point at which to factor it**, and WP-1003 should
    look at whether the three codes want to be one before the freeze.
  - `has_sigma` means "σ measured, not σ present" and a **derived** σ sets it:
    a `.ras` cps export reads as "σ from file" while the same scan exported in
    counts reads as Poisson. Both are honest — the cps σ genuinely could not
    come from the fallback — but WP-1003 should decide whether that distinction
    wants a third state before the surface freezes.
  - `.ras`/`.uxd` synthetic test files are written **inline** in
    `tests/test_readers.py` (`write_ras`, `write_uxd`), not in the
    `tests/writers_xrd.py` the WP names. Both are text formats, so the
    circularity that module exists to manage — packing literal *offsets* — does
    not arise. The binary formats (13-14) should still use it.
  - `ReaderCapability` did **not** gain the `scans` field the WP's contract-
    versions section mentions in passing: the biconditional meta-test makes it
    exactly `"scan" in options`, and a second authority for one fact is what the
    root rules forbid. Smaller surface for WP-1003 too.

- **2026-08-08 (session 2)** — **tasks 1-7 of 17 landed**, on branch
  `wp1047-vendor-formats` (6 commits off `main` @ `fad8a6d`). No `### Inherited`
  to prune: this WP was created the same day and nothing had been mailed to it.

  **Done.** (1) `io/formats/`, one module per format; `readers.py` the front
  door; `head()` replaces `_looks_gsas`'s whole-file decode — a pure refactor
  measured at *zero* test movement. (2) `READER_OPTIONS`/`reader_options_for`/
  `read_pattern(**options)`, threaded through project, imports, series, server,
  session, textdoc and the wizard; `Project.create(block=)` → `reader_options=`;
  `DataRef` records **effective** options; allowlist meta-test. (3) the
  `diagnostics=` channel + `ascending()` + `READER_OPTION_IGNORED` +
  `multiscan_default`, with codes in AGENT_PROTOCOL, the preview payload, the
  CLI print and `Project.data_diagnostics` (in memory, no `project.json`
  field). (4) `xy` de-totalised; `identify_format`'s message from the registry;
  UTF-16 BOM = text. (5) `tests/test_readers_robust.py`. (6) `.chi`. (7) `.dif`
  + `PatternFormat.refuses`/`ReaderCapability.refuses`.

  **Counts**, `[dev,jax,torch]` venv, darwin. Fast selection (`-m "not slow"`):
  2039 → **2094 passed, 5 skipped**, +55 with no new skips, and the +55 is the
  file arithmetic exactly — `test_readers.py` 35, `test_readers_robust.py` 16,
  `test_capabilities.py` 1, `test_gui_server.py` 3 (one plain + one
  parametrized ×2). Per task: +1, +22, +18, +12, +2. Task 1 moved it by
  **zero**, which is what "pure refactor" had to mean. Full selection:
  **2201 passed, 6 skipped** — green including every real-data acceptance row.
  The full selection's *before* count was not measured (only the fast one was
  taken at session start), so its +55 is **inferred**, not observed: no new
  test carries `@pytest.mark.slow` (checked) and the fast delta is exactly 55.
  The five fast skips are unchanged in kind — four `test_cross_backend.py`
  "no axial columns in this config", one `test_structure3d.py` multi-block CIF;
  the sixth in the full selection is a slow-only row that skips on `main` too.
  vitest **401**, svelte-check clean, ruff clean, dist rebuilt.

  **Wall clock**, as a range and not a figure: the fast selection ran 170-190 s
  on a quiet machine and 485 s while other work shared it; the full selection
  27:45, one measurement.

  **One loose end, named rather than buried.** A fast-selection run that
  *overlapped* the full suite (four concurrent pytest processes, 895 s against
  a normal ~190 s) reported **1 failed**; the test's name was lost because that
  invocation was piped through a `grep` for skip lines. Two clean runs before
  and after it are green at 2094/5, and the full suite is green, so nothing is
  known to be broken — but the failure was not identified, and the load
  condition is precisely the one `tests/CLAUDE.md` documents as making a
  wall-clock budget behave as a load sensor. If a successor sees an unexplained
  failure under `-n auto`, check what else was running before believing it.

  **In flight: nothing** — the tree is clean, pushed, and shippable at the WP's
  own stated boundary (after task 5).

  **Next**: task 8 `.ras`, which also introduces `scan` and carries the
  `PROJECT_FORMAT_VERSION` minor bump; then 9-14 the remaining formats, 15-16
  the instrument hint and scan picker, 17 the rest of the docs. Docs already
  done for what landed: three root-CLAUDE.md rules compressed into one bullet
  (the file sat at **exactly** its 600-line cap afterwards — budget for that),
  ATTRIBUTION's new "Format specifications" section, AGENT_PROTOCOL rows for
  five codes, README's reader row, `cli.py`'s help built from the registry,
  ROADMAP focus + glyph, the v1.0 narrative, the four-point note in WP-1003's
  `### Inherited` (which also supersedes the stale `block=` sentence in its own
  body), and a note to WP-1017 that the import wizard's pattern step changed
  shape — one control per reader option, plus a reader-diagnostics strip.

  **Gotchas for the successor.**
  - **Retire the WP's risks in its stated order before writing any vendor
    reader.** Fixture licences are per *file*, not per repo, and what
    "scrambled" scrambled in `TwoTheta_scan_scrambled.raw` decides whether the
    `.raw` acceptance line may claim values or only structure. GitHub was
    reachable from this session, so the fixtures are obtainable.
  - `multiscan_default` exists and is unit-tested but has **no caller yet** —
    `.ras` is its first. Same for the `scan` entry in `READER_OPTIONS`, which
    is deliberately *absent* until then: the allowlist meta-test
    (`set(READER_OPTIONS) == ⋃ fmt.options`) fails if you add one without the
    other, in either order.
  - `ascending(..., fmt=)` takes the format so the non-monotone refusal names
    `scan=` **only** where the option exists; a multi-scan reader gets that
    sentence for free by declaring `options=("scan", …)`.
  - The GUI wizard renders **one control per reader option** from
    `capabilities().reader_options`, so `.ras` gets its scan picker with no
    frontend change — but the dist is committed, so rebuild it
    (`npm --prefix gui run build`) whenever server-side payloads change shape.
  - `git add -p` **hangs** in this harness (no interactive stdin). It cost two
    minutes; use explicit paths.


- **2026-08-08** — created from the reviewed plan; the review's amendments
  folded in place: the Kα weighted mean in the λ match, the
  `PATTERN_MULTISCAN_DEFAULTED` default-scan diagnostic, the `.ras`
  intensity-scale per-file test (cps was overclaimed on `.rasx`-only
  evidence), the `.chi` count check named as the one bounded-head exemption,
  UTF-16 BOMs read as text, `READER_OPTION_IGNORED` + effective-options
  recording, the three contract-version decisions, the "scrambled"-fixture
  check, format-aware non-monotone messages, bounded zip reads, the
  single-parse preview, `.rd` declared a non-goal, and the task-5 session
  boundary.
