# WP-1407 — The format a benchtop still writes: PANalytical `.udf`/`.rd`, and three named refusals

Milestone: unscheduled · Status: ✅ 2026-09-13 — both readers, three refusals; `.rd` reproduces a committed `.prn` oracle bit for bit
Depends on: — (1047 is the seam this extends, and is closed)

## Goal

`read_pattern` opens PANalytical `.udf` (which a benchtop sold today still
writes) and the Philips PC-APD binary `.rd` (V3 and V5), and **declines three
more things by name rather than by traceback**: a binary `.raw` that matched no
reader, and the two peak-list formats `.pks` and `.udi`. Everything rides the
`io/formats/` seam WP-1047 built, so each format is one module.

**Three, not the four this goal originally claimed.** `.sd` was scoped as a
fourth refusal and turned out to be this same format's V5 extension, so it is
*read*, not declined — see the supersession note below. Corrected here rather
than left standing, because a goal stating what the WP disproved is the first
thing a successor reads.

## Context

> **Superseded in part, 2026-09-13 (task 1).** Task 1 retired both fixture
> risks and changed three things below. (1) **`.rd` is no longer file-less**:
> the IUCr CPD kit serves a `philips.zip` of **28 original logged `.rd`
> files**, 16 of which are the originals of `.prn` patterns already committed
> here, so `.rd` ships on real files plus a value oracle in the tree rather
> than on descriptions. (2) **The stored `uint16` is √-compressed**
> (`counts = v*v // 100`) — nothing below anticipated this, and it is the
> single most important fact about the format. (3) **`.sd` is this format's
> V5 extension, not a separate format**, so the "refuse `.sd` by name" plan in
> task 4 and the acceptance bullet are wrong and are restated there. What
> stands: everything about `.udf`, Stoe, `.pks`/`.udi`, and the licensing.
> Measurements and the header table: `tests/data/README.md` § Philips.

### The request, and the naming correction that reshaped it

The ask was "PANalytical's `.raw`". **There is no PANalytical `.raw`.** `.raw`
is Bruker/Siemens DIFFRAC, which this build already reads (v3 and v4; v1 and v2
refused). PANalytical's own formats are `.xrdml` (read since 1047), the binary
`.rd`/`.sd`, the ASCII `.udf`, the `.udi` peak list, and `.csv`/`.jcp` exports.

The extension settles nothing, and this is worth stating once because it
recurs: **`.raw` is written by six unrelated vendors** (Bruker/Siemens, GSAS,
Rigaku, Scintag, Shimadzu, Stoe) and **`.rd` by two** (Philips, Scintag, for
two unrelated formats). Dispatch here is content-first and `extensions` is
informational, so this costs nothing structurally. It is why the Stoe refusal
below cannot be a Stoe detector.

This WP picks up a follow-up 1047 declared rather than overlooked
(`1047-vendor-pattern-formats.md:406`):

> **Philips/PANalytical legacy `.rd`/`.udf`, Stoe, Scintag** are probably the
> most common real-lab formats *not* on the list; declining them is a decision,
> not an oversight. The `io/formats/` seam makes each a one-module follow-up.

### `.udf` is not legacy, and that is the finding that moved its priority

Checked against real files, not assumed. `yargerlab/Data` holds about thirty
`.udf` patterns written by an **ASU PANalytical Aeris**, a benchtop still on
sale, newest dated 12 June 2025. One header, read 2026-09-13:

The file verbatim, in its own order, header only:

```
SampleIdent,2025_06_03_CeO2_3_60_8min,/
Title1,CeO2 Standard,/
Title2,,/
DiffrType,?,/
DiffrNumber,1,/
Anode,Cu,/
LabdaAlpha1, 1.540598,/
LabdaAlpha2, 1.544426,/
RatioAlpha21, 0.50000,/
DivergenceSlit,Fixed, 1/2,/
ReceivingSlit,UNDEFINED,/
MonochromatorUsed,NO,/
GeneratorVoltage,  40,/
TubeCurrent,  15,/
FileDateTime,03-jun-2025 15:55,/
DataAngleRange,   3.00043,  59.99491,/
ScanStepSize, 0.01086644000,/
ScanType,CONTINUOUS,/
ScanStepTime, 18.87,/
RawScan
   43202,   43027,   42690,   41849, ...
```

**Nineteen keys** in this file, `Key,Value,/` per line, then a `RawScan` block
of integers terminated by `/`. Three things to read off it rather than assume.
`Title2` is **present and empty**, so an empty value is legal and is not an
absent key. `DivergenceSlit` carries **two comma-separated fields**
(`Fixed, 1/2`), so a value may itself contain commas and the line cannot be
split on every comma. And the abscissa is **reconstructed** from
`DataAngleRange` and `ScanStepSize`, not stored per point, so `ascending()`
sees a synthesised axis and the step-consistency question is the reader's.

Nineteen is this file's count, not the format's: the key set is what task 1
tables across the whole sample, and the PyXRD fixture carries only five.

It carries more than any other format in this family, and the part that matters
is `LabdaAlpha1` + `LabdaAlpha2` + `RatioAlpha21`: `suggest_instrument` can
resolve the source **without** the three-candidate λ match (Kα1 / Kα2 /
weighted mean) every other vendor format forces on it. Check whether the hint
path can take the direct route here rather than inheriting the guess.

### The bar this WP is measured against, and what each format scores

WP-1047 set it twice and both halves are load-bearing. Bruker `.raw` **v3
shipped on three agreeing descriptions and no file at all**, behind strict
self-consistency gates. Bruker `.raw` **v2 was refused on one uncorroborated
description and no file**, because "one uncorroborated description with no file
is how a reader comes to return a plausible wrong pattern". A wrong parse does
not raise; it hands back a profile that looks right.

All rows gathered 2026-09-13 against live repositories. **Re-verify before
relying on any of it** (a negative result is the kind that quietly stops being
true):

| format | shape | independent descriptions | permissive? | real file | verdict |
|---|---|---|---|---|---|
| `.udf` | ASCII, above | PyXRD `udf_parser.py` (**BSD-2**), psidata `xrd_panalytical.py` (**Apache-2.0**), CrysFML `Read_Pattern_Panalytical_Udf` (LGPL), xylib `philips_udf.cpp` (LGPL) | **two** | one vendorable, structural; real ones unvendorable | **read** |
| `.rd` **V3** | binary, magic `V3RD` at offset 0, 250-byte header, **√-compressed** uint16 | xylib `philips_raw.cpp` (LGPL, from Martijn Fransen's vendor-supplied spec), PyXRD `rd_parser.py` (**BSD-2**, and **wrong** — it omits the √ decode, the point count and the axis origin), `Yohko/importtool` (LGPL, a port of xylib) | **two, one permissive** | **28, with 16 `.prn` value oracles already committed** | **read** |
| `.rd`/`.sd` **V5** | the same header, data at 810 | one description, copied into the other two verbatim | — | **none anywhere** | **read behind the length gate only** (below) |
| Stoe `.raw` | binary, multi-range | **none, anywhere** | n/a | none | **refuse, vendor-agnostically** |
| Stoe `.pks`, PANalytical `.udi` | peak lists | n/a | n/a | none | **refuse, like `.dif`** |
| `.csv`, `.jcp`, Scintag | ASCII / binary | one or none | no | none | Non-goal |

### Licensing, settled

`ATTRIBUTION.md` § Format specifications is the governing doctrine and it
already covers this: byte offsets, magic strings and key names are **merger,
not expression**, so they may be written down from any source and implemented
independently, with the source closed. Table first, parser second.

**The xylib fence does not need retiring.** PyXRD's `rd_parser.py` is BSD-2 and
covers V3 and V5, so a permissive description of the binary exists and xylib
need not be opened at all. Record the caveat: it cannot be proved that PyXRD's
parser is independent of xylib rather than derived from it, so treat it as one
description whose independence is assumed. **If `.rd` turns out to rest on a
single description after all, it drops to the v2 footing and is refused, not
guessed.**

Two fences found the hard way, both worth keeping:

1. **`luttero/maud` is unusable despite a BSD-3 repo LICENSE.** Its
   `PhilipsDataFile.java` (a UDF reader) carries a 1997 header reading
   "provided as it is as confidential and proprietary information ... in
   accordance with the terms of the license agreement you entered into with
   the author". Repo grant, contradictory file notice. This is
   `io/CLAUDE.md` § Adding a format step 1 earning its keep again.
2. **FAIRmat's `ikz.py` fence is unchanged** and does not reach here; none of
   the sources above is that file.

### Fixtures, and what each can prove

**`.udf` has a vendorable fixture and, separately, real files whose bytes
cannot ship.** Both are used, for different things:

- **Vendorable, structural.** `PyXRD/test_udf_parser.py` embeds a complete UDF
  file inline under BSD-2. Unlike its `.rd` sibling it is **valid as
  committed**: UDF is plain ASCII with no backslash escapes, so the Python raw
  string does it no harm. It is small and plainly a synthesised ramp
  (`Title1,Dat2rit program`, 33 points falling 8000 to 1, five header keys), so
  it proves the parse and the block structure, not values and not the key
  vocabulary.
- **Not vendorable, real.** `yargerlab/Data` (~30, Aeris), `SantiagoJulioD/LabAv2`,
  `JosetoCa/Experimental-IV`. All three declare **no licence at all**, checked
  per repo rather than inferred from one. Facts may be read off them and
  recorded in `tests/data/README.md`; bytes may not ship. This is the `.uxd`
  position, and `.udf` is better placed than `.uxd`, which had no vendorable
  fixture of any kind.

So the key table comes off the real files and is recorded; the committed test
exercises the parse.

**`.rd` has no real file anywhere.** Two things stand in:

- **PyXRD's inline `.rd` test data is a description, never a fixture.**
  `test_rd_parser.py` embeds what was once a real file (magic `V3RD`, two
  `PC-APD, Diffraction software` strings, sample name `622M001912-644 clay
  form`) inside a Python **raw** string, so every `\00` is three literal
  characters. The bytes are mangled. Its visible structure is readable and
  useful; its values are not. Same class of trap as the "scrambled" Bruker v4
  fixture, and it gets the same treatment: say in `tests/data/README.md` what
  it proves and what it does not.
- **One lead worth 20 minutes, unchecked.** `tests/data/README.md:74` records
  that every `qarr/*.prn` file already in the tree was measured on a **Philips
  3020 goniometer with a PW3710 controller**, and the IUCr CPD kit is
  documented elsewhere as distributing `.xda` files converted from RD
  originals. If those `.rd` files survive, they are the best fixture available
  anywhere: provenance this repo has already accepted, and **the committed
  `.prn` files become an independent value oracle already in the tree**. That
  would be a stronger footing than `.xrdml` got. The recovery route the repo
  used before is the Internet Archive; it could not be reached from the
  scoping session's network (ISP interception), so this is genuinely open.

If it comes to nothing, `.rd` ships the way v3 did: three descriptions, a
literal-offset writer in `tests/writers_xrd.py`, and gates strict enough that a
wrong offset refuses rather than returning a plausible pattern.

### Stoe: zero descriptions, and why the refusal is shaped the way it is

Checked against every catalogue this project already trusts and absent from all
of them. **xylib does not support Stoe** (its README lists twenty-odd formats;
Stoe is not among them), nor does CrysFML, nor GSAS-II, nor PyXRD. The only
tool reading Stoe `.raw` is **PowDLL**, a closed-source Windows .NET component;
the one MIT repository that surfaces (`herrdivad/powDLLcsEXE`) is a thirty-line
wrapper calling `powDLL.dll`, not a reimplementation. There is no description
in any licence anywhere. That is the Bruker `.raw` **v1** footing.

**So the refusal cannot claim to recognise Stoe.** With no description there is
no magic to test, and asserting "this is a Stoe file" would be exactly the
guess this WP exists to prevent. The refusal is therefore vendor-agnostic and
true: a **binary `.raw` that matched no reader** is declined with a message
naming the six vendors who write `.raw`, saying which this build reads, and
pointing at the vendor's own ASCII export. Strictly better than today's generic
binary refusal, and it claims nothing.

**Stoe is unblockable, cheaply, and the ask should go out early** because it
has a long lead time and nothing here depends on it. WinXPOW exports an ASCII
xy file from any scan it holds, so anyone with a Stoe instrument can produce,
in one sitting, a few `.raw` files **paired with the ASCII export of the same
scans**, including at least one multi-range file (PowDLL advertises Stoe
multi-range, and a single-range file would not exercise it). That pairing beats
any written description: the export is an exact oracle, so the binary can be
worked out cold and then checked point by point. Stoe would become the
best-evidenced format in the family. **The refusal is where that reader hangs
when the files arrive.**

`.pks` and `.udi` are a different matter and not near-misses: they are peak
lists, tables of positions and heights, not measured profiles. This build
already refuses Bruker `.dif` for exactly that reason, because refining against
a few dozen spikes is not a refinement.

**But copy `.dif`'s shape, not just its verdict.** `dif.py`'s docstring is
explicit that it is "matched on evidence, not suffix … a real profile that
someone named `.dif` still falls through to the ASCII reader and opens", and a
suffix-only refusal would lose that escape: a genuine two-column profile a lab
happened to name `.pks` would become unopenable with nothing to do about it.
No `.pks` or `.udi` sample exists here, so the positive test `.dif` uses (does
this *look like* a peak list?) cannot be written. The negative one can, and it
preserves the escape: refuse on the extension **unless the file parses as a
plain two-column profile**, in which case fall through. Say exactly that in the
`sniff` string, so the gate does not imply a content test it does not do, and
revisit it the day a real `.pks` appears.

### Three questions the readers answer rather than assume

`io/CLAUDE.md` already rules on each; restated because this is where a vendor
reader goes wrong quietly.

- **σ and the intensity scale.** `.rd` intensities are 16-bit and may be counts
  or a rate. Decide per file with `base.sigma_by_arithmetic`, the way `.ras`
  and `.raw` do; where neither test is decisive, **withhold σ** and emit
  `PATTERN_INTENSITY_SCALED`. The Poisson fallback is wrong by √t on a rate.
  For `.udf`, note the Aeris header pairs `ScanStepTime, 18.87` with a filename
  claiming an eight-minute scan over roughly 5250 steps. Those do not reconcile
  as seconds per step, which is unsurprising for a PIXcel-class
  position-sensitive detector where effective counting time per point is not
  the drive's dwell. **Test the stored values; do not adopt the label.**
- **The attenuator.** If either format carries one, its convention is
  **measured, never adopted from `.xrdml`**. Four formats have given three
  different answers. Find a file where the factor varies and ask which of the
  raw series and the product runs continuously through the transition.
  `base.sigma_from_scaled`'s docstring already names PANalytical as the
  per-point-scale case.
- **The axis.** `.udf` states `ScanType` and a `DataAngleRange`; `.rd` states a
  scan type too. Classify with each format's own vocabulary and pass the
  verdict to `base.check_axis`. Recognisably non-2θ raises naming what the file
  holds; unrecognisable reads as 2θ and says so. **Do not add a row to a shared
  table**: each format classifies for itself.

### Seams

`src/rietx/io/formats/base.py` already has everything a reader needs: `head()`,
`looks_binary()`, `ascending()` (the whole monotonicity repair table),
`check_axis()`, `metadata()` (refuses an undeclared key), `pattern_data()` (the
schema boundary turning a `ValidationError` into a `ValueError` naming the
file), `sigma_by_arithmetic()`, `sigma_from_scaled()`, `sigma_from_cps()`,
`multiscan_default()`.

`bruker_raw.py` is the structural model for the binary reader: `_unpack` as the
single `struct.error` boundary (`:261-270`), named offset constants, the
version-refusal message shape (`:604-609`), and the two self-consistency gates
(`:551`, `:582-594`). `dif.py` is the model for a `refuses` entry.

`capabilities()`, `cli.py`'s help string and `docs/manual/using/files.md` all
build from `PATTERN_FORMATS` and need no edit, which is why each
`PatternFormat`'s `sniff` and `sigma` strings matter: the GUI preview and the
manual quote them verbatim.

## Non-goals

- **PANalytical `.csv` and `.jcp`.** One description each (CrysFML), no file.
  `.jcp` is JCAMP-DX, a published standard with its own specification, and it
  deserves its own module rather than a PANalytical-shaped corner of this one.
- **Scintag `.raw`/`.rd`.** No open description found. Note its `.rd` is an
  unrelated format that merely shares Philips' extension.
- **A Stoe reader.** Blocked on files, not on effort; only the refusal lands
  here. See the ask above.
- **Writing any of these formats.** As 1047.
- **Retiring the xylib fence.** Not needed, and a decision that should be taken
  on its own evidence if it is ever taken at all.

## Tasks

Ordered so a session can stop cleanly. **The boundary is after task 5**, never
mid-format, mirroring 1047's own rule — task 5 is where `.rd` acquires the only
fixture it can have, since no real one exists, so a tree stopped after task 4
holds a registered binary reader nothing exercises.

- [x] 1. Retire the fixture risks. Chase the QARR `.rd` lead (Internet Archive,
      from a network that can reach it) and table the `.udf` key vocabulary off
      the real Aeris files. Record both in `tests/data/README.md` either way,
      including what each PyXRD inline fixture can and cannot prove. Licence
      checked per file first. **Both retired, both positively**: 28 real `.rd`
      files with 16 committed value oracles, and 19 `.udf` keys identical across
      56 real files. See the supersession note in Context.
- [x] 2. `ATTRIBUTION.md` § Format specifications: one row for `.udf`, one for
      `.rd`, naming which source each fact came from and which corrections are
      this project's, on the template of the three Bruker `.raw` rows
      (`:250-252`). Add the MAUD per-file contradiction as the worked example
      of step 1. Then close the sources.
- [x] 3. `.udf` reader: `src/rietx/io/formats/udf.py` exporting a
      `PatternFormat`. Text, so its writer stays inline in
      `tests/test_readers.py`. Registry position after the binary and container
      formats and before `xy`; say why in `formats/__init__.py:57-63`.
      Check whether `suggest_instrument` can take the direct route on
      `RatioAlpha21` rather than the three-candidate λ match. `anode`,
      `wavelength` and `wavelength_alpha2` are already declared; the **ratio is
      not**, and `base.metadata()` refuses an undeclared key, so the acceptance
      line below buys a new `METADATA_KEYS` entry (`base.py:164`) — declare it
      with the two consumers that match on it, or drop the ratio from the bar.
      **Dropped from the bar, and the reason is WP-1076.** The hint already
      takes the direct route without it: the header states the anode *and* both
      wavelengths exactly, so `suggest_instrument` resolves `CuKa` by
      name-and-wavelength agreement with no candidate matching. The ratio would
      then need a `METADATA_KEYS` entry, a new preset field and a consumer — and
      the `CuKa` preset already carries weight 0.5 for Kα2, which is what all 56
      real files state, so no obtainable file would exercise a value different
      from the default. A declared name with no writer fails no test.
- [x] 4. `.rd` reader: `src/rietx/io/formats/philips_rd.py`. **Restated by task
      1**: `.sd` is V5 of this same format, so the reader **claims** both by
      magic (`V3RD`/`V5RD`) rather than refusing `.sd` by name. Intensities are
      √-compressed, `counts = v*v // 100`. Gates, all measured on 28 files:
      `len == data_start + 2n`, `n == round((end-start)/step) + 1`, and
      `uint16@136 == max(v)`. V5's data start (810) rests on one description
      and no file, so the length gate — which tests the header offsets too,
      since `n` comes from them — is the whole of its evidence and a failure
      refuses by name. Magic-byte `matches`, disjoint from `bruker_raw` in both
      directions (precedent: `tests/test_readers.py:2144`).
- [x] 5. `write_philips_rd()` in `tests/writers_xrd.py`, packing offsets
      **literally** and never from the reader's table, plus the
      `SYNTHETIC_FIXTURES` arm in `tests/test_readers_robust.py:71`.
      **Reshaped by task 1**: V3 now has a real fixture, so `qarr/corundum.rd`
      joins `REAL_FIXTURES` and the writer's synthetic arm is **V5**, the
      version no file exists for — the `raw3` case exactly. The writer
      **refuses** a count the √ encoding cannot hold rather than writing the
      nearest one, so a round trip cannot assert a number the caller never
      wrote; `CORUNDUM_HEAD` is twelve real counts for callers to use.
- [x] 6. The three remaining refusals: the vendor-agnostic binary-`.raw`
      message (six vendors named, this build's readers named, the ASCII-export
      remedy), and `.pks` / `.udi` as peak lists — extension **unless the file
      parses as a two-column profile**, which keeps `.dif`'s escape — via
      `PatternFormat.refuses` +
      `ReaderCapability.refuses`, by extension, saying so in `sniff`.
- [x] 7. Tests: a `# ---- <format>` section per reader in
      `tests/test_readers.py`, the truncation arms, and the
      `tests/test_capabilities.py:222` scan-capable set if either format is
      multi-scan. **No obs/calc/diff PNGs**: this WP fits nothing, it only
      reads files. Neither format is multi-scan, so the scan-capable set is
      unchanged and that assertion needed no edit.
- [x] 8. Docs and close: `io/CLAUDE.md` § Per format rows and any new rule,
      diagnostics rows in `docs/skill/rietx/references/diagnostics.md` for any
      new code, ROADMAP row, milestone record. **No diagnostics row is owed**:
      this WP added no new code, reusing `PATTERN_INTENSITY_SCALED` only. Four
      per-format rows and three new rules landed in `io/CLAUDE.md`, which took
      its cap from 300 to 350 — the blocks were cut by a third first, and the
      cap comment says why each rule could not be demoted to this file.
- [x] 9. Skill: **one routing-table row is not owed** here, because a new
      readable format changes nothing about how an agent *drives* a fit. What
      is owed is a diagnostics row per new code (task 8) and, if the
      binary-`.raw` refusal ships, a line in the skill's file-opening guidance
      saying that a `.raw` may belong to any of six vendors so the refusal
      message is the thing to read. Confirm against root CLAUDE.md § skill at
      close and record the decision either way. **Decided**: no routing row and
      no diagnostics row. The `.raw` line went into `references/api.md` § In and
      **not** the body, because the body takes only what holds for *every* fit
      and this holds only for a fit that starts from a `.raw`. It is authored in
      the generator (`docs/skill/make_api_index.py`), since `api.md` is
      rendered and a hand edit fails `test_skill.py`; both committed copies were
      re-synced with `rietx skill --install . --copy`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_readers.py tests/test_readers_robust.py \
    tests/test_capabilities.py tests/test_project.py tests/test_gui_server.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

- A `.udf` file opens and reports the anode and **both** wavelengths its header
  carries, and the instrument hint resolves `CuKa` from them by agreement. The
  Kα2/Kα1 ratio is **not** on the bar; task 3 records why.
- **The lead paid off, so the bar is bit-identity**: `qarr/corundum.rd` opens
  and reproduces the committed `qarr/corundum.prn` **exactly on all 7251
  channels**, and `qarr/cpd-1e.rd` reproduces its own `.prn` to within the ±1
  count the kit's two converters disagree by (documented, asserted, not
  chased).
- A **V5** file opens only if `len == 810 + 2n` holds with `n` from the header;
  otherwise it is refused by name saying no V5 file was obtainable. There is no
  separate `.sd` refusal: task 1 settled that `.sd` is V5 of this format, so it
  is claimed by magic like any other member.
- A binary `.raw` matching no reader is refused with a message naming the six
  `.raw` vendors and this build's readers; a `.pks` or `.udi` is refused as a
  peak list. Both appear in `capabilities()`;
  `test_a_binary_file_is_refused_by_name_rather_than_by_traceback` already
  asserts every `fmt.title` reaches the message.
- Every truncation of every fixture fails as `ValueError`/`OSError` naming the
  file (the 20-cut harness).
- `.rd` and Bruker `.raw` are disjoint in both directions.
- Counts quoted with venv and platform; passed+skipped moves by exactly N in
  both selections.

## References

- `docs/wp/1047-vendor-pattern-formats.md` — the seam, the evidence bar, and
  the declared non-goal this WP picks up. **Do not read it to work this WP**;
  everything load-bearing is restated above.
- PyXRD (BSD-2), `pyxrd/file_parsers/xrd_parsers/{udf,rd}_parser.py` and their
  tests — the permissive description of both formats.
- psidata (Apache-2.0), `psidata/readers/xrd_panalytical.py` — second
  permissive `.udf` description.
- CrysFML `Read_Pattern_Panalytical_Udf` (LGPL), xylib `philips_udf.cpp` /
  `philips_raw.cpp` (LGPL), `Yohko/importtool` (LGPL) — spec-only corroboration
  under the merger doctrine.
- Crystal Impact Match! format list — the vendor/extension catalogue behind the
  six-vendor `.raw` claim.
- `tests/data/README.md:74` — the Philips 3020/PW3710 provenance of the QARR
  patterns, which is what makes the `.prn` oracle idea possible.

## Handover log

### 2026-09-13 (2nd session) — complete; all nine tasks

This build now opens the two formats a Philips or PANalytical lab actually has
on disk, and the useful part is not that the count went up by two. The binary
one stores a **square root** of its counts, so anyone who read it the obvious
way — including the one permissively-licensed description of it in existence —
got a pattern with every peak in exactly the right place and every intensity
wrong. Nothing in a fit would reveal that. What settled it was files: the IUCr
round-robin kit still publishes the original logged `.rd` scans beside the
ASCII conversions this repository has committed since v0.3, so for once there
is an oracle rather than a second opinion, and the reader now reproduces a
committed pattern channel for channel. The scoping session had assumed those
files were gone and planned around their absence; they were one Cloudflare
challenge away.

The other half is smaller and more cheerful: `.udf` is a current format, not a
legacy one, and fifty-six real files from two labs turn out to agree on
everything a reader needs, so it ships with no guesswork at all. Three things
are refused rather than read, and the point of each is what it declines to
claim — most of all a binary `.raw`, which six unrelated vendors write and
which this build will now name all six of rather than guess between.

**Done.** All nine tasks; six commits.

1. **Task 1 retired both fixture risks, positively.** The IUCr CPD kit serves
   `philips.zip` — **28 original logged `.rd` files**, Dec 1997, of which 16 are
   the originals of `qarr/*.prn` patterns already committed here. Two are now
   committed (`qarr/corundum.rd`, `qarr/cpd-1e.rd`). And 56 real `.udf` files
   carry **19 keys in one order**, identically, across two labs and two
   instrument vintages.
2. **Task 2** put both formats in `ATTRIBUTION.md`, and the MAUD per-file
   contradiction in the section preamble, then deleted the four consulted
   sources from the scratchpad so the parsers were written with them closed.
3. **Tasks 3-5** are the two readers, the literal-offset writer and the
   fixtures. **Task 6** is the two refusal entries. **Tasks 7-9** are tests,
   `io/CLAUDE.md`, the caps diary and the skill.

**Measured.** `[dev]` venv — this worktree's own, **no jax and no torch**, so
the 132 skips include every backend row — darwin.

- Fast selection **4607 passed, 132 skipped**, against 4577/132 before:
  **+30 passed, +0 skipped**. Reconciled: 22 new test functions, plus one
  `REAL_FIXTURES` row over three parametrized tests, plus two
  `SYNTHETIC_FIXTURES` arms — 27 — plus the review pass's three regression
  tests. No new skip.
- The WP's own acceptance selection: **427 passed** (before the review's three;
  429 after). ruff clean.
- **The full selection deliberately did not run.** Nothing here can move a
  measured number: no physics, no default and no solver path changed, and the
  slow acceptance suites name their `qarr/*.prn` inputs explicitly rather than
  globbing the directory the two `.rd` files were added to — checked, because
  that glob is the one way this change could have reached them. `pgrep` showed
  no other suite running either way.
- `origin/main` **had not moved** since the branch was cut, re-checked
  immediately before the merge step, so the counts are the merged tree's by
  identity.

**The measurements themselves are in `tests/data/README.md` § Philips**, not
here: the 28-file offset table, the four independent confirmations of the √
rule, the 19-key `.udf` vocabulary, and what each fixture can and cannot prove.

**Three things this WP changed its own mind about, all from task 1.**

1. **`.sd` is not a separate format.** It is this format's V5 extension, so the
   planned refuse-by-name was wrong; both versions are claimed by magic.
2. **V5 is read, not refused.** Its data offset rests on one description copied
   twice — `Yohko/importtool` reproduces xylib's code tables verbatim, down to
   the `810 - 214 - 8*3` expression — and no V5 file exists anywhere, which is
   the Bruker v2 footing this project *refuses* on. It is read anyway because
   the gate is decisive in a way v2's never was: `n` comes from header fields,
   so `len == 810 + 2n` tests the header offsets and the data start **jointly**,
   and a wrong 810 cannot shift a pattern silently. A failure refuses by name
   and says no V5 file was obtainable.
3. **The permissive description is the defective one.** PyXRD's `rd_parser.py`
   is BSD-2 — the source a port would legally start from — and it omits the √
   decode, computes one point too few, and offsets the abscissa by half a step.
   All three are refuted by the committed `.prn` files. That is now a standing
   rule in `io/CLAUDE.md`.

**The review pass found four real defects, and two of them were in the one
thing its module exists to protect.** `/code-review high --fix` raised seven
findings; six were acted on and one judged.

- **The `.pks`/`.udi` escape was broken, twice.** The gate never skipped comment
  lines although its own docstring said it did, so a genuine two-column profile
  with a `#` header — the commonest shape any ASCII export has — was refused as
  a peak list; and it dropped the bounded read's last line unconditionally, so
  an eight-row profile became seven and fell under the minimum. Fixed: the
  markers now mirror `read_xy`'s exactly, because this gate's whole job is to
  predict whether *that* reader would open the file.
- **Both new scan guards tested sign but not finiteness.** A header holding a
  denormal step or an infinite angle reached `round()` and raised
  `OverflowError`, which names neither file nor field and escapes every
  caller's allowlist — so a damaged file arrived at the GUI import route as a
  500, breaking `io/CLAUDE.md` § Refusals. Reachable from **plain text** in
  `.udf`, whose range and step are free-text fields where `nan` parses. The
  truncation harness structurally cannot find this: it shortens files, it never
  scrambles bytes.
- **Two the review declined and this session took**, both being things a person
  reads. `identify_format`'s "Supported:" list was built from the whole
  registry, so it told a user their unrecognised binary `.raw` was unreadable
  and then offered "Unrecognised binary .raw" as a supported format;
  `cli.py` already filtered `refuses is None` for the same purpose, and the test
  now asserts every reader's title **and no refusal's**, which is what it always
  meant. And this WP's own goal and title still claimed *four* named refusals
  after `.sd` turned out to be V5 and readable — corrected in place, because a
  goal stating what the WP disproved is the first thing a successor reads.
- **One finding was advice about a test this change had silently repointed**: an
  existing case used `PATTERN_FORMATS[-1]` to mean `xy`, and adding
  `RAW_UNKNOWN` below it made that a refusal entry without anything going red.
  Now looked up by name.

**Two names were deliberately *not* declared** (WP-1076): `RatioAlpha21` gets no
`METADATA_KEYS` entry, because the hint path already resolves `CuKa` by
anode-and-wavelength agreement and the preset already carries the 0.5 every real
file states — so the key would have had no consumer; and the `.rd`
diffractometer and focus codes are decoded and checked but not carried into the
pattern, for the same reason. Both decisions are recorded in the tasks.

**In flight: nothing.** Tree clean and pushed, WP ✅.

**Gotchas for whoever touches this next.**

- **`archive.org` is unreachable from this network** (TLS interception on
  `curl`; Claude Code's WebFetch declines `web.archive.org` by policy), and
  several fixture rows here are documented as "recovered via the Internet
  Archive". The live IUCr site is the better route and its Cloudflare challenge
  clears for a *headed persistent* browser profile — plain headless Chromium
  does not clear it, and `ctx.request.get` 403s while **writing the 5.8 kB
  challenge page into your output file**, which looks like a successful
  download. Fetch from inside the page.
- **`qarr/cpd-1e.rd` is committed because it is the exception.** Its `.prn` was
  made by the rounding converter where the other fifteen truncate, so it is off
  by exactly one count on 2108 channels. That is asserted. Do not "fix" the
  reader to chase it.
- **The `.rd` writer refuses a count the √ encoding cannot hold** rather than
  writing the nearest one, so a round-trip test cannot assert a number the
  caller never wrote. Use `CORUNDUM_HEAD`. The first version of its inverse used
  `isqrt` where the encoder rounds *up*, and every test failed loudly — which is
  what the refusal is for.
- **`docs/skill/rietx/references/api.md` is generated.** A hand edit fails
  `test_skill.py`; author in `docs/skill/make_api_index.py`, regenerate, then
  `rietx skill --install . --copy`.

**Next**, and none of it is owed by this WP:

1. **The Stoe ask is the one thing worth sending.** It is cheap, has a long lead
   time and nothing depends on it: a few `.raw` files paired with the WinXPOW
   ASCII export of the *same* scans, including one multi-range file. The export
   is an exact oracle, so the binary could be worked out cold. The
   `raw_unclaimed` refusal is where that reader hangs.
2. If a real `.pks` or `.udi` ever turns up, `peaklist.py` can stop matching on
   the suffix and match on content like `.dif` does; its whole reason for being
   a separate module disappears that day.
3. `.csv`, `.jcp` (JCAMP-DX, which deserves its own module) and Scintag remain
   the declared non-goals.

- **2026-09-13** — **created; no implementation.** A request to support
  "PANalytical's `.raw`" turned out to name a file that does not exist, and
  scoping it properly changed what is worth building. `.raw` belongs to six
  unrelated vendors and PANalytical is not among them; what the request meant
  is the Philips family, which WP-1047 declined on purpose. The useful result
  is that one member of that family is not a legacy format at all: a
  PANalytical Aeris, a benchtop on sale today, writes `.udf`, and its header
  carries enough to seed the instrument outright. The other useful result is
  negative and saves someone a week: **Stoe cannot be written at all**, because
  no description of it exists in any licence anywhere, so it is scoped here as
  a refusal that claims nothing plus a cheap, specific ask. Nothing was
  implemented; this session produced the WP and its evidence.

  **Done.** The WP file and its ROADMAP row, under a new Unscheduled group
  ("The formats a lab still has"). One commit, `be096979`, branch
  `wp1344-benchtop-formats`.

  **Measured.** Evidence gathered 2026-09-13 against live repositories, and the
  per-format scoring against WP-1047's own bar is the table in Context.
  Headlines: `.udf` has **two permissive descriptions** (PyXRD BSD-2, psidata
  Apache-2.0) plus two LGPL ones; `.rd` has **three descriptions, one
  permissive** (PyXRD's `rd_parser.py`, V3 and V5), which is the same footing
  Bruker `.raw` v3 shipped on; `.sd` has one and no file, which is the footing
  v2 was **refused** on; Stoe has **zero** (absent from xylib, CrysFML, GSAS-II
  and PyXRD alike; only the closed PowDLL reads it), which is Bruker v1.

  **Counts.** `[dev]` venv (this worktree's own — it has neither jax nor torch
  installed, so the 132 skips include every backend row), darwin. Fast selection
  **4577 passed, 132 skipped**, unchanged, which is the right answer: this
  session added no test.
  ruff clean. The **full selection deliberately did not run** — the only
  non-documentation change is one integer in `SIZE_CAPS`, which moves no
  measured number, and protocol rule 6 fires the full suite only when a change
  could.

  **The review pass changed the WP, which is worth knowing before trusting
  it.** `/code-review high --fix` raised eleven findings; seven were applied
  and four judged here. Two were plain wrong references. Three were defects in
  the plan itself and would each have cost a successor real work: the
  acceptance bar demanded a Kα2/Kα1 ratio that no `METADATA_KEYS` member
  declares, so `base.metadata()` would have refused at the acceptance step; the
  declared stop boundary sat at task 4, one task before the writer that builds
  the **only** fixture `.rd` can ever have, so stopping there would have
  shipped a registered binary reader with no coverage; and the counts were
  labelled `[dev,jax,torch]`, copied from 1047's handover, when this worktree's
  venv has neither. The numbers were right and the label was not, which is the
  failure `tests/CLAUDE.md` § Quoting numbers exists to catch. One finding was
  **declined**: backfilling `docs/milestones/process.md`'s caps diary, because
  the three preceding ROADMAP bumps are missing there too and adding only this
  one would misrepresent the record. That backfill is unowned and still owed.

  **`origin/main` had not moved** since this worktree was created, so the
  branch tip already sits on current main and no merge was needed; the counts
  above are the merged tree's by identity rather than by re-measurement.

  **In flight: nothing.** Tree clean, pushed, WP at ⬜ because no task landed.

  **Gotchas for a successor.**
  - **Two risks are unretired and both are task 1.** Whether the IUCr CPD kit
    still carries the Philips `.rd` originals that would turn the committed
    `qarr/*.prn` into a value oracle already in the tree — this could not be
    checked here because the network intercepted `archive.org`, so it is
    genuinely open rather than answered. And whether a real `.udf` can be
    licensed rather than only read from.
  - **Two inline fixtures, one usable and one not, and they look alike.**
    PyXRD's `.udf` test data is valid as committed; its `.rd` test data is the
    same idea mangled by a Python raw-string prefix. Do not assume the second
    from the first.
  - **The Stoe refusal must not claim to detect Stoe.** With no description
    there is no magic to test. The message is about a binary `.raw` that
    matched no reader, which is true and useful; anything sharper would be the
    guess this WP exists to prevent.
  - **The number is 1407, not 1344.** An unscheduled WP takes the newest block
    and 1344 was taken on `origin/main` during scoping, so the next free number
    is not what the main checkout's listing shows.

  **Next**: task 1, because it decides what the acceptance line may claim for
  both formats, and it is the only task whose answer can still change the
  design. Task 3 (`.udf`) is unblocked regardless and is the cheaper half; the
  stated stop boundary is after task 5.
