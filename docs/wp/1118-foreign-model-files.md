# WP-1118 — foreign model files: read a refinement in, write one back

Milestone: unscheduled · Status: ✅ 2026-09-16 — all four foreign formats read
and write. TOPAS `.inp` (PR #98), FullProf `.pcr` (#111), GSAS `.EXP` + `.PRM`
(#248, #103) and GSAS-II `.gpx` behind a restricted unpickler (#234), each with
a writer that is the inverse of its own reader and round-trips through it;
GSAS-II's is the `.instprm` + phase CIF pair that program imports, this build
writing no `.gpx`. Origin-choice honesty closed #101, the writers closed #148,
and the `.EXP` protocol now reaches `tests/test_acceptance_fap.py` from the
reader instead of from transcribed constants. What outlived the WP is the
`.inp` grammar the reader refuses, `STR(...)` (#107) and `#if`, which is
WP-1433; #196 (Rietica/XND) stays this family's recorded boundary
Depends on: — (WP-1110 found it; WP-1102 owns the one seam that overlaps)

## Goal

Reading a TOPAS, GSAS or FullProf control file returns the model it describes —
the `Structure`/`Instrument` pair **and the refine flags**, which are the
protocol — and says in diagnostics what it could not carry across. Writing emits
the same model back in the target's own language, naming what has no counterpart
there. Bringing an existing refinement into rietx stops being a transcription
exercise, and checking rietx against the code it came from stops being one too.

## Context

**The evidence is WP-1110's agent round, item 19.** Six agents refined a
68-pattern in-situ series transcribed by hand from a TOPAS `.inp`, and all six
named the transcription as the hardest part of the work — including having to
infer that a missing backtick means "fixed". A mistyped coordinate stays
symmetry-valid and fails silently, so the failure mode is a plausible wrong
answer rather than an error. Nothing in the package helps.

**This repo already pays the same cost.** `tests/data/FAP.EXP` is GSAS's
converged fit and `INST_XRY.PRM` its instrument file; every reference value and
the whole refine protocol of `tests/test_acceptance_fap.py` was read out of them
**by hand** and lives as constants in the test and in `tests/data/README.md`.
Same for `11bm_gsas.prm`'s wavelength. A reader would give those constants one
authority instead of a transcription, which is DESIGN.md's v0.2 lesson —
comparing against another code means adopting its *protocol*, not its numbers —
made mechanical.

**The refine flags are the payload, not the numbers.** A control file says which
parameters were free, which were held, what was excluded and in what order the
author freed things. That is the part a person cannot reconstruct from a CIF
plus a pattern, and it is the part that decides whether a cross-code comparison
means anything (DESIGN.md § "Learned in v0.2": a guessed protocol gave Rwp 16 %
and +390 ppm on fluorapatite, the mirrored one 9.73 % against GSAS's 10.05 %).
So the answer's shape is a model **plus** a vary set or a `PlanSpec`, never a
`Structure` alone.

**The write direction, sharpened by issue #148 (2026-09-01 triage).** The
writers task below gains its strongest test for free: **round-trip** — export
→ re-import must reproduce the model bit-for-bit wherever the format can
carry it, the cheapest adversarial test the readers can get, no external
fixture needed — so it belongs in this WP's acceptance, not only its tasks.
GSAS-II joins the write targets (`.instprm` + CIF-shaped structure — text,
documented, and the `Z`-term round-trip question sits on the writers task
below). Every convention the validation campaign measured (FCJ vs A_T2,
K = 1 vs 0.5 polarization, U vs B vs β, FWHM vs σ, centidegrees) becomes a
written decision with a citation on the writer. Deliberately **not** here:
an RMCProfile export (data + starting configuration, not a protocol —
issue #192's territory), and Rietica/XND in either direction — issue #196
proposes those readers as a beyond-the-majors widening of this family;
right home, deliberately unscheduled, no corpus, and the read/write
asymmetry is intentional.

**Two things arrive with the TOPAS files (issues #107, #101).** Seven
archive files open phases with the macro form `STR(R-3)` /
`STR(######, "#name#")`, which the line-based split cannot see. PR #98 took
the minimum honest fix with it, which was independent of any design:
recognise the spelling and **refuse naming it**, because a reader may decline
a construct but may not describe it as absent. So such a file now raises,
counting the phases it states, instead of parsing **zero phases** and letting
`to_structure` answer "a Pawley or indexing-only .inp is legal and has none".
What is still undone is *reading* them, and two already-fixed macro bugs hide
behind them, so **PR #98's incidence figures are floors until this is
decided**. Whether `STR(...)` is special-cased or the reader grows a general
macro pass is the registry-shape task's decision (and a general pass borders
[1119](1119-named-variables.md)'s equations scope — decide the boundary
there, not twice). Second, origin choice:
`gemmi.SpaceGroup("Pn-3m").ext` is `'1'`, so a structure transcribed from an
origin-choice-2 source gets choice 1's symmetry with nothing raised — wrong
structure factors under a healthy-looking fit — while the TOPAS spelling
`Pn-3mZ` raises, and stripping the letter inverts the meaning. The
translation table exists in the #98 draft (`normalize_space_group`: `Z`→`:2`,
`S`→`:1`, `R`→`:R`, `H`→`:H`); the **diagnostic is the load-bearing half**
and is general — it fires for any multi-origin symbol left unpinned, from
any reader, in the reader diagnostics channel where such reports belong.

**Two things the `.inp` reader met on a real workshop archive** (WP-1130, and
neither is a bug). Of the four `.inp`s in the Durham ZrMo₂O₈ archive **three
refuse** at their first `#if` — the multi-pattern reel files, which are exactly the
case WP-1110's agent round named as the hardest part of the work. The refusal is
correct (which branch was refined is unknown, and reading on would report a model
mixing both), but 1130 got its model by stripping the `#if`/`#endif` blocks in a
scratchpad, which is a workaround no user should have to invent: a `#prm`-only
integer evaluator would resolve `#if (#out pattern_count > 1)` and the `Run_Number`
guards, which is most of what these files use `#if` for. And
`TOPAS_FEATURES_NOT_IMPORTED` named the thing that mattered while nothing downstream
could act on it — the dropped `spherical_harmonics_hkl` block sat on a phase owning
**24 % of the fit's χ²**, and supplying rietx's own equivalent (Stephens
`Phase.microstrain`) took Rwp 0.1092 → 0.0878. So that gap is a *conversion*, not a
capability: rietx has the physics. If `to_structure` ever grows an hkl-strain arm, the
`.inp`'s coefficients are **fixed** (`!ahkl_c00` … `!ahkl_c44p`, taken from another
range), so importing them imports a held model — and freeing such a block can make
other phases `PHASE_UNCONSTRAINED`, so it is not a change to make silently.

**A magnetic phase stays refused in both readers until the model exists.**
`coverage.py`'s `magnetic structure` feature is `Stance.REFUSED`, and a FullProf phase
with Jbt = ±1 takes the same stance and the same sentence ("the nuclear half would
look complete") through the registry rather than a raise, so
[1328](1328-magnetic-interchange.md) lifts both by changing one table. Do not map a
Fourier-component magnetic phase onto a nuclear structure in the meantime. Still true
2026-09-13: there is no moment on `main` — WP-1343 scoped the magnetic *broadening*
term and [1327](1327-magnetic-structure.md) still owns the model itself.

### The licence fences, which are stricter here than anywhere else in `io/`

`ATTRIBUTION.md` carries the standing rows; each new format adds its own. What
they already establish:

- **TOPAS is closed — papers and its own documentation only.** The `.inp`
  language is described in the TOPAS-Academic Technical Reference (v8 § 2.17 is
  already cited by WP-1110 § "The cell window, measured"), and real `.inp` files
  are a second description. No implementation is consulted: BGMN/Profex and
  xrayutilities are GPL, so **concepts only, never code** (root CLAUDE.md §
  Licensing).
- **FullProf is closed — manual and papers only** (Rodríguez-Carvajal 1993). The
  `.pcr` layout is documented there.
- **GSAS/GSAS-II is a *spec-only* source with a grant-back clause.** The `.EXP`
  and `.PRM` layouts are documented in Larson & Von Dreele (2004) LAUR 86-748;
  GSAS-II's own importers may be read as a specification and never ported.
  `ATTRIBUTION.md`'s GSAS-II row is the standing statement of this.
- **The Bruker `.raw` v3 precedent decides what to do with a thin spec**: a
  version with one uncorroborated description and no file to check it against is
  **refused by name**, because that is how a reader comes to return a plausible
  wrong model.

### Seams to extend, and the one rule that gets harder

`src/rietx/io/CLAUDE.md` (auto-loads under `io/`) is the rulebook: one module per
format, an ordered registry whose order is behaviour, a bounded `head()` sniff,
and refusals that name the file rather than the parser's exception. Three things
are different for a *model* file and must be decided before any parser is
written:

- **A second registry, not an arm of `PATTERN_FORMATS`.** The answer's shape
  differs (a model, not a `PatternData`), and `DataRef` exists to record which
  pattern reader claimed a file. A control file *points at* a pattern; that
  pattern still goes through `read_pattern` as now.
- **"A reader may repair only where it can say that it did" binds harder here.**
  A `.inp` holds constructs this package has no model for — macros, `prm`
  expressions and their dependency graph, `fit_obj`, penalties, `local`s — and
  silently dropping one changes the model rather than the presentation. So the
  reader reports every construct it did not carry, by name, and **refuses** where
  the construct would change the answer it is about to return. `Parameter.expr`
  is refused at construction (WP-1110 item 5), so a `prm` expression that is not
  expressible as a tie has no landing site by design.
- **The writer fails in the opposite direction and needs its own rule.** A
  Stephens strain block, a P-spline background, a restraint weight schedule or a
  staged `PlanSpec` may have no counterpart in the target. Precedent from
  WP-1110 item 14: **mark, never clamp** — name what did not cross at write time
  rather than emitting a file that looks complete.

- **There are now three reader *kinds*, and the third arrived without a home.**
  `rx.read_gsas_prm` (PR #248) returns an `Instrument` and sits in
  `io/instrument_profile.py` beside the native JSON profile reader: it is neither a
  `PATTERN_FORMATS` entry nor an `io/projects/` project reader. `io/CLAUDE.md`'s "one
  module per format" is scoped by its own first line to the *pattern* readers, so
  nothing governs it — while the drift that rule exists to prevent is now real, since
  that module carries two formats' fences. Raised with the maintainer at the merge, no
  decision taken; it is this task's to settle, and the registry now has **four**
  instances to answer its shape from (`read_topas_inp`, `read_fullprof_pcr`,
  `read_gsas_prm` and `read_recipe`) rather than one.
- **A general macro pass is not blocked on an expression language, because rietx is
  not growing one** ([1119](1119-named-variables.md) § Decisions 4, which shipped
  `Refinement.add_variable` and deliberately no expression string). The object a reader
  would target now exists; the arithmetic the two readers carry privately
  (`topas.symbol_table`/`_resolve`/`_arith`, the `.pcr` codeword decoder) stays theirs.
  So if `STR(...)` needs a macro pass it is a `.inp` grammar concern living entirely in
  `io/projects/topas.py` and answering to the Technical Reference — decide it there,
  not here.
- **A bare space-group symbol now has one authority, and each format sits on a side of
  it** ([1324](1324-symmetry-silences.md)).
  `crystallography.symmetry.setting_alternatives(symbol)` returns `(taken, others)` for
  the 40 symbols the tables hold in more than one setting, and the fit-time report
  `SPACE_GROUP_SETTING_ASSUMED` fires only where a reader handed a bare symbol on. A
  reader that resolves the setting itself keeps its callers silent — which is what
  `normalize_space_group`'s trailing-`Z` → `:2` mapping buys the `.inp` route. FullProf
  writes the symbol without a suffix in the common case, so the `.pcr` route either
  establishes the setting from evidence the file carries (as `read_small_structure`
  picks R from the cell) or hands the bare symbol on; both are defensible and the choice
  should be deliberate.

`capabilities()` publishes the pattern formats `read_pattern` opens; the model formats
need their own arm — and so, on the evidence above, may the third kind — with the
meta-test that fails on a registry member missing from its arm applying unchanged. A new
format token is spelled in `_about.py`, never inline (root CLAUDE.md § Conventions).

## Non-goals

- **Not a TOPAS-compatible engine.** No macro language, no `prm` expression
  evaluator, no `fit_obj`. A construct with no model here is reported, not
  emulated.
- **GSAS-II `.gpx` is no longer fenced out — it is a task, behind a
  restricted unpickler** (decided 2026-09-03 on issue #234; the task line below
  carries the measurements). Until that day this bullet fenced it for a
  reason measured false. What stays out: any `.gpx` content the corroborating
  corpus does not cover — image, single-crystal, sequential-fit and magnetic
  projects — until the corpus widens, and a `.gpx` *writer*, which is the
  writers task like every other format. `.EXP`/`.PRM` are text and documented.
- **Not the additive component seam.** A `fit_obj` or a `.pcr` extra peak lands
  on `Instrument.extra_components`, which is [1102](1102-component-seam-humps.md)'s.
- **Not a pattern reader.** `io/`'s existing registry keeps that job.

## Tasks

- [x] Decide the answer's shape and stand up the model-format registry beside
      `PATTERN_FORMATS`. — 2026-09-13. The unit is a **refinement**, not a
      foreign file: `PROJECT_FORMATS` + `read_project_model` dispatch on
      content, the answer is `ProjectModel` (the format's own model, tagged —
      never a union with blanks), `read_gsas_prm` and `read_recipe` stay
      outside it with their reasons written down, and the readers are top-level
      `rx.` exports with a `capabilities().project_formats` arm. #107, #103 and
      [1314](1314-mfile-reader.md) are unblocked.
- [x] TOPAS `.inp` reader — the format with the evidence behind it.
- [x] GSAS `.EXP` + `.PRM` reader, and make `tests/test_acceptance_fap.py` take
      its protocol from the reader instead of from transcribed constants.
      — the `.PRM` half landed (`rx.read_gsas_prm`, PR #248, merged 2026-09-10,
      `ff69ec34`); the `.EXP` half and the acceptance rewire landed 2026-09-15
      (`rx.read_gsas_exp`, `PROJECT_FORMATS` member `gsas_exp`). `Closes #103`.
      Two follow-ups this task **did not** do, each with its numbers in the
      handover entry: the plan still frees no coordinate DOFs where GSAS freed
      twelve (measured, nearly free to close), and `read_gsas_prm` reads the
      same `ICONS` record by whitespace split rather than by column.
      **The first is decided, 2026-09-15: the suite keeps its 20 and keeps the
      assertion.** Freeing the twelve coordinate DOFs was measured cheap
      (Rwp 0.096966 → 0.096677, 0.1 ppm on the cell, no wall clock), and the
      maintainer's call is that a suite stating the difference is worth more
      than one closing it: the two recorded acceptance numbers stay where they
      are, and the parameter-count gap stays asserted rather than removed. The
      second is the task line below.
- [x] `read_gsas_prm` reads its fixed-format records **by column**, closing the
      class the `.EXP` reader's first decision opened. A `.prm`'s `INS` records
      are the `.EXP`'s `HST`/`INS` records under a different four-character
      key, and this reader splits three of them on whitespace: `ICONS`,
      the `PRCF1` header and its continuation lines. `ICONS` is where it bites
      and the corpus hides it — `11bm_gsas.prm` leaves `IREF`/`IDAMP` blank, so
      its six tokens happen to land on the right meanings, while
      `INST_XRY.PRM` writes `IDAMP` and is **refused** for having seven.
      One record read two ways by two readers in one package is the thing this
      codebase most dislikes, so the record grammar gets one authority.
      Whether the doublet `INST_XRY.PRM` also carries can then be read is the
      second half: the `KRATIO` the old reader could not locate is field 8, and
      that file states it.
      — landed 2026-09-15. `projects/gsas.py` grew `read_icons`,
      `read_prcf_header` and `split_records`, all public and all called by the
      `.prm` reader; the coefficient names come from `CW_PROFILE_COEFFICIENTS`
      rather than a second literal list. The four real calibration files read
      **bit-identically** (measured against `origin/main`'s module over the
      whole `model_dump`), `INST_XRY.PRM` is refused for its `GP` of 0.1
      rather than for a token count, and a doublet is now read: the refusal's
      stated reason had expired. `io/CLAUDE.md` takes the two rules, the cap
      368 → 383.

- [x] FullProf `.pcr` reader. — PR #111, merged 2026-09-03 (`b717cc98`)
- [x] GSAS-II `.gpx` reader behind a **restricted unpickler** (decided
      2026-09-03, issue #234). — landed 2026-09-16. `rx.read_gsas2_gpx`,
      `PROJECT_FORMATS` member `gsas2_gpx` (first, being the one binary
      member), `projects/gsas2.to_structure`, seven `GSAS2_GPX_*` diagnostics.
      **The corpus was widened first, and it moved three decisions.** The
      public GSAS-II tutorial corpus (34 projects, redistributable, unlike this
      WP's other two formats) covers every kind #234 listed as untested, and
      `Closes #234`.
      (1) The allow-list in #234 is **incomplete**: eleven globals appear and
      seven are outside it, so a list measured on one 146-file archive would
      refuse 10 of 34 real projects. `G2VarObj` and `ExpressionObj` are
      admitted as **inert stand-ins** rather than refused, which is PyTorch's
      `weights_only` shape and the reason a refusal aborts the whole file
      rather than a record.
      (2) The sniff cannot be the magic bytes — 11 of the 34 carry no pickle
      protocol header at all.
      (3) `Rvals['GOF']` is the **square root** of reduced χ², which is the
      opposite of what `projects/gsas.py` claimed about it; corrected there in
      the same branch, with the GDNFT claim itself left standing.
      Two shapes the specification never mentions are refused by name because a
      real corpus contains them: a negative `Uiso` (7 of 34) and a phase with no
      sites (GSAS-II's Le Bail extraction). 19 of the 34 build a structure and
      15 refuse, each naming its phase.
- [x] Origin-choice honesty (issue #101). — landed 2026-09-16, and the issue's
      two halves had both moved before the work started. The TOPAS suffixes
      landed with PR #98 (`topas.normalize_space_group`) and FullProf grew its
      own variant with PR #111, so nothing was left to lift. The diagnostic
      landed too, **wider than #101 asked and under another name**: WP-1324
      shipped `SPACE_GROUP_SETTING_ASSUMED` on 2026-09-02 over all 40
      multi-setting symbols — the `:1`/`:2` origin choices *and* the `:H`/`:R`
      axis choices — so there is no `SPACE_GROUP_ORIGIN_ASSUMED` and there
      should not be. What was left is where it fires and what it can see.
      **Where**: it had one consumer, `refine.py`, so a caller who converted a
      model without fitting it was told nothing; `setting_diagnostics` is now
      the one builder and the `.EXP` and `.inp` readers report at read, which
      is what the issue asked for. **What it can see**: a `.gpx` states its
      operators, so its setting is *read* rather than assumed —
      `symmetry.setting_from_operators`, `Gsas2Phase.resolved_space_group`,
      `GSAS2_GPX_SETTING_FROM_OPERATORS` — and 4 of the 46 phases in the public
      corpus needed it, every one of them origin choice 2 under a symbol
      resolving to choice 1. And the message stops quoting a composition that
      separates nothing: on Mn₃O₄ it printed `Mn12 O16` twice while asserting a
      ZMV that had not moved, so it now falls back to the site multiplicities.
      Numbers in the handover entry. `Closes #101`.
- [x] The writers, each naming what did not cross — GSAS-II included — with
      export → re-import round-trip as each format's acceptance (issue #148).
      Two obligations already banked. An exporter writes
      `get_spacegroup(sym).xhm()`, never the phase's stored string, or a
      round-trip through a foreign format launders a resolved setting back into
      an ambiguous one ([1324](1324-symmetry-silences.md)). And **a GSAS-II
      profile cannot round-trip today**: GSAS-II's CW Lorentzian is
      `γ = X/cosθ + Y·tanθ + Z` while `ProfileTCHZ` declares exactly `u, v, w,
      x, y` (verified 2026-09-13; `params/vector.py` hard-codes that five-name
      tuple twice), so an `.instprm` with a nonzero `Z` has nowhere to land.
      Carry it or refuse it by name is this WP's call, not a physics question —
      Von Dreele's own teaching slide says `X, Y, Z = 0` is normal and 11-BM has
      them zero, so `Z` earns a schema field for round-tripping and not for
      modelling ([1131](1131-sample-broadening-is-a-specimen-property.md) fenced
      it here). For the same reader: rietx's `profile.x` is the 1/cosθ (size)
      coefficient and matches GSAS-II's `X` by law, while TOPAS's `pkx`/`pky`
      map to rietx's `y`/`x` and **not** by letter (measured in WP-1130).
      **The TOPAS `.inp` writer landed 2026-09-16** (`from_structure`,
      `write_topas_inp`, `rx.write_topas_inp`, `io/projects/topas.py`): the
      inverse of `to_structure` — phase, space group, cell, every atom's
      coordinates/occupancy/displacement (isotropic or, opt-in, the full
      anisotropic tensor), and every `Parameter`'s own `vary` written as
      TOPAS's `@`/`!` grammar — round-tripped through `read_topas_inp` itself
      as the acceptance, no external fixture needed. The first obligation is
      discharged **here**: `get_spacegroup(phase.space_group).xhm()` is what
      gets written, never the stored string, checked by a test that starts
      from an ambiguous bare symbol. What does not carry, because
      `to_structure` does not build it from a `.inp` either: the emission
      profile and instrument geometry (no `Instrument` comes off a `.inp` at
      all today), cell/site bound windows, and extinction/preferred-
      orientation/sample-broadening — stated in the writer's own docstring
      rather than silently dropped.
      **The FullProf `.pcr` writer landed the same day** (`from_structure`,
      `write_fullprof_pcr`, `rx.write_fullprof_pcr`, `io/projects/fullprof.py`):
      same shape (cell, atoms, scale, refine flags via one codeword per free
      parameter — `10*n+1`, never a shared tie, since a `Structure` carries no
      record of which parameters a refinement tied), round-tripped through
      `read_fullprof_pcr` as the acceptance. Two things a `.pcr` needs that a
      `Structure` does not state at all — every control/output/pattern/cycle
      line, the background and the fitted range — get safe inert placeholders,
      because the format is positional with no keyword to resynchronise on, so
      every line the reader expects must exist regardless. `Occ` is discarded
      by `to_structure` either way (every atom always comes back fully
      occupied), so the writer computes it from each site's own multiplicity
      (`M_site/M_general`) rather than carrying a chemical occupancy the
      Structure has no field for. The `get_spacegroup(...).xhm()` obligation
      met a real limit here rather than a restatement: FullProf's grammar has
      **no origin or axis suffix at all**, so a bare symbol can only state the
      setting `normalize_space_group` already prefers (choice 2, and `:R` only
      where the cell metric says so) — a resolved origin choice 1 is refused
      by name, checked by calling `normalize_space_group` on the candidate
      output the same way the reader would rather than by a heuristic. An
      anisotropic site is refused too, mirroring `to_structure`'s own refusal
      to assume FullProf's β convention.
      **The GSAS-I pair landed 2026-09-16** (4th session): `rx.write_gsas_exp`
      (`projects/gsas.from_structure`) and `rx.write_gsas_prm`
      (`instrument_profile.from_instrument`), each round-tripped through its
      own reader, `FAP.EXP`'s converged model among them and bit-identically.
      These are the first writers here whose **columns are fixed**, and the
      four rules that fell out govern every later one, so they are in
      `io/CLAUDE.md` § Project writers rather than here. Two are worth naming:
      the field is a *budget* — `gsas.write_field` spends every column, and
      what still narrows is named once per file (`GSAS_EXP_VALUE_NARROWED`;
      a `Biso` always does, the file storing `Uiso`) — and **the decimal point
      is written explicitly**, because a Fortran `F`/`E` descriptor supplies
      one from its own `d` when the field has none, so `90` in an `F10.6`
      field is 9e-5 to GSAS while `float()` here reads 90. That last is the
      one class a round trip through this package cannot catch. A flag
      narrower than the model (GSAS states one per cell and one per site's
      coordinates) merges **free** and names the group
      (`GSAS_EXP_REFINE_FLAG_MERGED`). The `.prm` writer is the one whose
      payload is *not* the refine flags — a calibration goes out frozen — and
      it refuses a non-zero `zero_shift`, `ICONS`' `ZERO` having no unit this
      package has established and the reader refusing one on the way in.
      The review pass's open `+inf` question is closed for all five writers at
      once: refused, since `repr` spells it `inf` and no real program parses
      that.
      **GSAS-II landed 2026-09-16** (5th session) and `Closes #148`. It is the
      one format with no project file to write, so the target is the pair it
      imports: `rx.write_gsas2_instprm` (`instrument_profile.from_instrument_gsas2`)
      and `rx.write_gsas2_phase_cif` (`projects/gsas2.from_structure`). Neither
      `.instprm` end existed, so `rx.read_gsas2_instprm` was built alongside it
      and the round trip is the ordinary one. **The `Z`-term question is
      closed as the corpus had already answered it**: refused by name, no
      schema field, which is `io/recipe.py`'s decision one format over. Two
      findings the write direction produced. `Polariz.` is inert on a `PNC`
      bank in *both* packages, GSAS-II applying the factor only to an `XC` or
      `XB` type, so a neutron file's is dropped by name rather than carried.
      And the phase CIF states its **setting three times** because the two
      programs read one string opposite ways — GSAS-II resolves a bare
      two-origin symbol to origin choice 2 and answers a colon-suffixed one by
      setting the phase to `P 1`, gemmi resolves the same string to choice 1
      — so the bare symbol goes in the tag GSAS-II reads, the resolved `xhm()`
      in the one gemmi prefers, and the operations in the loop both can check.
      That makes the obligation banked here from WP-1324 met in a fourth way:
      not a spelling but a channel.
- [x] `capabilities()` arm, skill rows for the new diagnostic codes
      (`docs/skill/rietx/` — `AGENT_PROTOCOL.md` is a redirect stub since
      WP-1304), a Part 1 manual section, and an `ATTRIBUTION.md` row per
      format. The TOPAS half of the diagnostic rows and its `ATTRIBUTION.md`
      row landed, and the GSAS `.EXP` half on 2026-09-15 (arm, six
      `GSAS_EXP_*` rows in `references/diagnostics-projects.md` §7g, a Part 1
      section over the whole `GsasModel` tree, and an `ATTRIBUTION.md` row).
      **The `.gpx` half landed 2026-09-16**: the arm is derived from
      `PROJECT_FORMATS` so it needed no edit, seven `GSAS2_GPX_*` rows joined
      `references/diagnostics-projects.md` §7g (whose family prefix list in
      `tests/test_skill.py` grew with them), `rx.read_gsas2_gpx` joined
      `make_api_index.py`'s In section, a Part 1 section documents the whole
      `Gsas2Model` tree, and `ATTRIBUTION.md` has its row.
      **The writers' half landed 2026-09-16** (4th session): the arm gained
      `ProjectFormat.write` / `ProjectFormatCapability.writes`, publishing the
      *exported name* of each format's writer and `None` where there is none —
      a name so a client learns what to call, `None` so an unwired format does
      not answer a question nobody asked, and the meta-test is
      `_SURFACE_FLAGS`' (checked against `rietx.__all__` and by identity). The
      3rd session left this open against growing the arm twice; a `None`-valued
      field does not, since GSAS-II's writer will change a *value*. Four
      `GSAS_EXP_*`/`GSAS_PRM_*` writer rows joined
      `references/diagnostics-projects.md` §7g and `files.md` gained a section
      per writer. **Headroom is the constraint now**: `references/api.md` is
      35 627 B of 36 000, so GSAS-II's paragraph is paid for by a cut.
      **Superseded in part, 2026-09-13**: `references/api.md` § In
      was repaired somewhere between 2026-09-03 and 2026-09-13 and now names
      both `rietx.io.projects.read_topas_inp` and `read_fullprof_pcr`, says
      they have no top-level `rx.` entry point yet, and carries `rx.read_gsas_prm`
      — so it is no longer false.
      **Superseded again, 2026-09-15**: `SKILL.md`'s routing row is not owed
      either, and the claim that it was has never been true. Line 41 reads
      "you were handed another program's input file, not a pattern" and routes
      to `references/api.md` § In, which is the **situation** in the *When*
      column and the formats in § In, exactly as
      [1330](1330-skill-references-by-shape.md) asks. It landed 2026-08-30 in
      `7bc3e3d0` under WP-1308, before the note above it was written. No row in
      the file says "a PowderLine recipe"; the word `recipe` in that row is a
      manual page in the third column, which is how it was misread. Nothing is
      owed on the skill for the readers that have shipped. The byte-headroom
      cautions inherited from WP-1308 (27 B), PR #98 (32 B) and 1330 (36 B) are
      stale, and so are 09-13's replacements: measured 2026-09-15, `SKILL.md`
      is 31 951 B of its 33 000 cap (**1 049 B free**) and `references/api.md`
      32 796 B of 36 000 (**3 204 B free**). A body sentence is still paid for
      by a cut named in the commit; there is simply room to pay.
      **The GSAS-II pair's half landed 2026-09-16** (5th session): a Part 1
      section for the `.instprm` reader and writer and a paragraph on the
      phase CIF, nine `GSAS2_INSTPRM_*`/`GSAS2_CIF_*` rows in
      `references/diagnostics-projects.md` §7g (whose family-prefix list in
      `tests/test_skill.py` grew with them), the three verbs in
      `make_api_index.py`'s In section, and an `ATTRIBUTION.md` row of its own
      for the pair. **The arm needed no edit and that is the answer, not an
      omission**: the 4th session expected GSAS-II's writer to change
      `ProjectFormat.write`'s value, and it does not, because the writer is
      not a `.gpx` writer. This build writes no `.gpx`, so that member's
      `None` is true, and the pair is published where the `.prm` pair is —
      the manual and the skill, `capabilities()` naming neither. **Headroom is
      now the binding constraint**: paying for three entries took
      `references/api.md` to 35 942 B of 36 000 (**58 B free**), the cuts
      named in the commit, so the next addition there is a real cut rather
      than a squeeze.
- [x] A `#prm`-only integer evaluator for `.inp` `#if` guards, so the
      multi-pattern reel files read instead of refusing (§ Context; WP-1130
      measured three of four workshop files out of reach). Scope it to integer
      `#prm` comparisons — it is not the macro language, and § Non-goals still
      holds. — **moved to [1433](1433-the-inp-grammar-still-refused.md)
      2026-09-16**, with issue #107's `STR(...)` decision beside it. The two are
      one shape: both are `.inp` grammar, both live in `io/projects/topas.py`,
      and both answer to the Technical Reference. **The block recorded against
      this line is not real**: the reference is public at
      `topas-academic.com/technical_reference`, one 10.8 MB page over plain
      `curl`, and `ATTRIBUTION.md`'s TOPAS row already cites §19.3.2 with
      content. §19.1.2 specifies `#prm`/`#if`/`#out` whole, and 1433 § Context
      carries what it says, the `Rand` condition that stays refused included.
- [x] Fixtures with provenance rows in `tests/data/README.md`; tests, and the
      obs/calc/diff PNGs for any refinement one of them drives. — the GSAS
      `.EXP` half landed 2026-09-15: `FAP.EXP`'s row says it is now the
      reader's corroborating fixture, and the file also **ships in the wheel**
      (`src/rietx/data/examples/`, `LICENCES` in `test_example_projects.py`)
      because the `fap` example reads its protocol from it. The `.gpx` half
      landed 2026-09-16 — `gsas2_pbso4.gpx` and `gsas2_lacamno3_magnetic.gpx`,
      the first project-reader fixtures this WP could **vendor at all**, since
      the GSAS-II tutorials carry a redistribution grant where TOPAS's and
      FullProf's corpora are private. Nothing enters the wheel. The 34-project
      survey behind them has its own section in `tests/data/README.md`. A third
      joined them 2026-09-16 — `gsas2_mn3o4_setting.gpx`, the one corpus file
      that both states a setting its symbol does not and builds end to end.
      — closed 2026-09-16, and the two formats with no vendored fixture are
      **answered rather than owed**. A `.inp` and a `.pcr` are their owners'
      research data, so `tests/test_projects_topas.py` and
      `tests/test_projects_fullprof.py` synthesize every fixture inline, each
      with a comment naming the archive idiom it stands for and what reading it
      wrong would do (`ATTRIBUTION.md`'s TOPAS row states the fence). That is
      the licence answer and it does not expire, so no corpus is pending here.
      What a later session can still add is a *reading* of files it may not
      ship, which is [1433](1433-the-inp-grammar-still-refused.md)'s archive
      pass.

## Acceptance

The repo already holds the file that can prove it. `FAP.EXP` is GSAS's converged
fluorapatite refinement and `tests/test_acceptance_fap.py` mirrors its protocol
from hand-read constants:

```sh
.venv/bin/python -m pytest tests/test_acceptance_fap.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The bar is that the reader reproduces that protocol field for field — the free
set, the held Caglioti terms, the excluded region, the wavelengths — with the
acceptance test then reading it rather than restating it, and the measured
answer unmoved.

Issue closure rides the tasks, not the WP: the PR landing the `STR(...)`
decision carries `Closes #107`; the origin-choice task `Closes #101`; the
`.EXP`/`.PRM` task `Closes #103`; the writers task `Closes #148`. Issue
#196 (Rietica/XND) stays open — it is this family's recorded boundary, not
work this WP does.

## References

- Larson, A. C. & Von Dreele, R. B. (2004), *GSAS General Structure Analysis
  System*, LAUR 86-748 — `.EXP` and `.PRM` layouts.
- Coelho, A. A., *TOPAS-Academic Technical Reference* (v8) — the `.inp` language.
- Rodríguez-Carvajal, J. (1993), *Physica B* **192**, 55 — FullProf, and its
  manual for the `.pcr` layout.
- `ATTRIBUTION.md` — the GSAS-II spec-only row and the GPL/closed fences.
- [1110](1110-agent-surface-friction.md) § "Found by the round" item 19; DESIGN.md
  § "Learned in v0.2".

## Handover log

### 2026-09-16 (6th session) — the WP closes, and the keyword three of its PRs wrote in backticks

WP-1118 is finished. Someone holding a TOPAS, GSAS, GSAS-II or FullProf
refinement can open it here, and a model built here goes back out in any of the
four. This session wrote no code. It answered the two task lines that outlived
the work and filed them as WP-1433, and it found that three issues this WP
believed it had closed are still open. Their pull requests wrote the closing
keyword inside backticks, which GitHub renders as code and does not act on.

*Done* — three commits on `wp1118-close`, branched off `4a034414`, the merge of
PR #346.

- **`fa493f4d`, WP-1433.** The `#if` evaluator and issue #107's `STR(...)`
  decision are one shape: both are `.inp` grammar, both sit in
  `io/projects/topas.py`, and both answer to the Technical Reference. They get
  their own WP rather than holding this one open.
- **`550d3dd3`, the two task lines.** The `#if` line moves out. The fixtures
  line closes on its licence answer, which is that a `.inp` and a `.pcr` are
  their owners' research data, so both suites synthesize every fixture inline
  with the archive idiom named on it. That answer does not expire, so no corpus
  is pending.
- **`e4a9662d`, the keyword rule and WP-1314's mailbox.** `/wp-handover` step 11
  now says a closing keyword is plain text. 1314 takes the `capabilities()` gap
  the 5th session named: `ProjectFormat.write` publishes a registry member's
  writer, GSAS-II's writers write the pair that program imports rather than a
  `.gpx`, so that member's `None` is true and a GSAS-II-shaped question has no
  arm to read. The same entry had a line duplicated in place, fixed with it.

*Measured* — this worktree's `.venv`, `[dev]` only (no jax, no torch), python
3.12, darwin/arm64, on `origin/main` at `4a034414`.

- **Fast selection: 5146 passed, 133 skipped, 3:20** at a load average of 4.
  Identical to the 5th session's figure on the same tree, which is what a
  documentation change must leave. No test was added and no skip moved.
- **The closing keyword, over the last 120 merged PRs: 17 closing phrases.** 10
  written plain, and every one of their issues is closed. 7 written inside
  backticks, and every one of their issues is open. Four of those seven quote
  the keyword deliberately (#206 and #213, both declining to close #204). The
  other three are this WP's: #101 from PR #336, #148 from #346, #234 from #335.
  PR #347 re-issues all three plain.
- **The TOPAS Technical Reference is public and fetchable**: HTTP 200, 10.8 MB,
  one page, plain `curl` with a user agent. §19.1.2 specifies `#prm`, `#if`,
  `#elseif` and `#out` whole, and §19.1.4 the `#m_*` family. The 5th session
  recorded the `#if` evaluator as blocked on a document no session here had, and
  that is wrong: `ATTRIBUTION.md`'s TOPAS row has cited §19.3.2 with content
  since PR #98. WP-1433 § Context carries what the section says, including the
  `Constant(Rand(0,1))` condition that stays refused because no reader can
  decide it.

*Decided*

- **The WP closes on its own acceptance.** The four formats read, all four
  write, and `tests/test_acceptance_fap.py` takes the FAP protocol from the
  reader rather than from transcribed constants. The issue half is #103, #101,
  #148 and #234.
- **No root CLAUDE.md clause.** The rules the writers earned live in
  `io/CLAUDE.md` § Project writers, loaded with the subtree that needs them, and
  the root file sits at its 837-line cap. Root already points there for how to
  add a format.
- **The review pass does not apply.** This branch's diff is markdown only, so
  `/code-review` has no code to read. The 5th session's pass, eight findings and
  all eight taken, is what the code went through.
- **Nothing for the agent skill.** What this session measured is about this
  repo's workflow, not about driving a refinement.

*Gotchas*

- **A closing keyword in backticks is a class here, not one slip.** Every PR
  body in this repo spells identifiers in code spans, and the keyword looks like
  one. The rule now sits in `/wp-handover` step 11, where the body gets written.
  Closing an issue by hand afterwards records nothing about which PR did it,
  which is why the finalisation PR carries the keywords instead. **The trap has a second half**: prose
  about a keyword is a keyword. Writing that PRs #206 and #213 declined to close
  #204 linked #204 to PR #347, and rewording around the number left the link
  standing. Deleting the number cleared it, and
  `gh pr view N --json closingIssuesReferences` is what says so.
- **The dormant `wp1118-*` worktrees drop out by themselves.** Five branches
  besides this one are merged into `origin/main`, and `wp_claim.py status`
  filters a closed WP's kept trees, so the two dormant rows stop advertising
  work to resume once this Status line is ✅.

*Next*, in order.

1. **Merge PR #347.** Nothing else closes #101, #148 and #234.
2. **WP-1433 whenever someone wants it.** Neither half is blocked, and #107's
   filer offered the `STR(...)` fix once told which shape to write.
3. **1314 (Jana) is this family's open member**, with a mailbox holding what
   1118 learned about settings, binary sniffs, one grammar per vendor and the
   `write` arm. #196 (Rietica/XND) stays the recorded boundary.

### 2026-09-16 (5th session) — GSAS-II writes back, and the symbol two programs read opposite ways

A model built here can now be handed to GSAS-II, which is the last of the four
foreign formats and the only one with no project file to write: GSAS-II imports
a phase from a CIF and a machine from a small text file, so the writer is that
pair. Both halves are new, and one of them cuts both ways — nothing here could
read a GSAS-II `.instprm` before either, so a beamline calibration from that
program now opens as a frozen instrument. The work also found a real
interchange trap that no round trip inside this package could show. GSAS-II and
gemmi read the same bare space-group symbol as two *different* groups, and each
refuses the other's way of disambiguating it, so a CIF written for one of them
is wrong in the other unless the setting travels in a third channel that needs
no convention: the symmetry operations themselves.

*Done* — five commits on `wp1118-gsas2-writer`, branched off `eb2f6f91`.

- **`fa5d007c`, the `.instprm` pair.** `rx.read_gsas2_instprm` and
  `rx.write_gsas2_instprm` in `io/instrument_profile.py`, beside the GSAS-I
  `.prm` pair they are the sibling of; the grammar (`read_instprm`,
  `write_instprm`, `INSTPRM_CW_SINGLE`/`_DOUBLET`, `centidegree_factor`) in
  `projects/gsas2.py`, beside the `.gpx` reader that shares its vocabulary.
  Constant-wavelength X-ray and neutron both read, a `PNC` bank becoming a
  `NeutronSource`.
- **`554da8b3`, the phase CIF.** `projects/gsas2.from_structure` and
  `rx.write_gsas2_phase_cif`. GSAS-II's importer already reads every atom tag
  `write_structure_block` writes — `B_iso_or_equiv` divided by 8π², `adp_type`
  of `Uani`, the separate aniso loop keyed by label — so the block writer is
  shared and the whole of the work is the symmetry.
- **`5a7949e3`, the documentation.** A Part 1 section for the reader and the
  writer and a paragraph on the CIF, nine `GSAS2_INSTPRM_*`/`GSAS2_CIF_*` rows
  in the skill's §7g, the three verbs in `make_api_index.py`, an
  `ATTRIBUTION.md` row for the pair, two fixture rows and a corpus section in
  `tests/data/README.md`.
- **`f6470573`, `0bca117c`** — the two task lines ticked, ROADMAP's focus, and
  two gates the new files tripped (an em-dash aside in Part 1, and `encoding=`
  on a test's `tmp_path` writes).
- **`63963c8f`, `c1acf860`, the review pass** (`/code-review high --fix`):
  eight findings, **all eight taken**, each with a test reproducing the
  review's own measurement. Four in the new code — an empty `.instprm` raised
  `IndexError` where the contract is a `ValueError` naming the file; a
  triple-quoted value opened and closed on one line swallowed the rest of the
  bank; two phases of one name collided on a CIF block name (gemmi answers a
  duplicate with a bare `RuntimeError`, and `\W+` also collapses `"phase 1"`
  onto `"phase-1"`); a site label with whitespace split its own loop row.
  **Two in the siblings**, the same accident one format over: a line break in
  a phase name passes the TOPAS writer's quote check and comes back as a
  silent rename, and passes the FullProf writer's blank-and-marker checks and
  desynchronises the positional walk. One message fix
  (`GSAS2_INSTPRM_VALUE_DEFAULTED` said "no Lam" about a file stating `Lam1`).
  And the eighth, which the review reported rather than fixed and this session
  took: the `.prm` writer collected `narrowed` from every `write_field` call
  and read it nowhere, so a value written to what a fixed column holds crossed
  in silence while the `.EXP` writer beside it reported one. That is WP-1076's
  class in mirror image — a declared channel with no consumer — and it is not
  hypothetical, the 4th session's own measured case reaching it on an ordinary
  converged calibration. `GSAS_PRM_VALUE_NARROWED` is the twin's name and
  shape, with its §7g row and a manual sentence. Nothing was declined.

*Measured* — `[dev]` venv, darwin/arm64, this branch level with `origin/main`
(fetched at handover, unmoved since the branch was cut, so these are the merged
tree's numbers).

- **Fast selection: 5146 passed, 133 skipped, 2:21-2:45.** +45 tests, all of
  them new here: 34 in `tests/test_gsas2_instprm.py`, 7 added to
  `tests/test_projects_gsas2.py` (54 now), and one each to the TOPAS,
  FullProf and `.prm` writers' files for the review's findings (2 to the last).
  No new skip; the run before the review pass was 5137 and every one of the
  nine added since is a review finding's test. The full selection did
  not run: nothing this session touched can move a measured number, the
  refinement path being unchanged, and the WP's own acceptance
  (`tests/test_acceptance_fap.py`) passes in 3.25 s.
- **The corpus is 12 `.instprm` files, and 2 of them read.** 27 banks: 23
  `PNT` (time of flight), 2 `PXC`, 2 `PNC`. Both `PXC` files are **refused**,
  each having converged to `X` = −0.0978 centidegrees, which this package's
  softplus-bounded Lorentzian term cannot hold. Three files are multi-bank and
  every one of those writes `#Bank 6` twice. None states a `Diff-type`, a
  goniometer radius or a Kα doublet.
- **The writer reproduces a real file character for character.** Reading
  `gsas2_hb2a.instprm` and writing it back gives all 13 items it states, string
  for string — the check the `.EXP` writer could only make by eye against
  `FAP.EXP`, and a token format lets a test make it.
- **`references/api.md` is 35 942 B of its 36 000 cap**, 58 B free. The three
  new entries were paid for by five cuts named in `5a7949e3`, all of them
  statements the diagnostics rows or the refusal messages already carry.
  `io/CLAUDE.md`'s line cap went 473 → 485 in the commit that added its rule.

*Gotchas* — three, and the first is the one to carry out of this WP.

- **Two readers can resolve one symbol to two different groups, and each
  refuses the other's spelling of the fix.** GSAS-II reads a bare `F d -3 m` as
  origin choice **2** (its own message calls choice 1 "a space group setting
  not compatible with GSAS-II") and answers a colon-suffixed symbol by setting
  the phase to `P 1`; gemmi reads the same bare string as choice **1** and
  needs the colon to say otherwise. So the exported CIF states the setting
  three times: the bare symbol in `_symmetry_space_group_name_H-M`, which
  GSAS-II reads first; the resolved `xhm()` in `_space_group_name_H-M_alt`,
  which gemmi prefers when both are present (measured here, not read anywhere);
  and the operations in `_space_group_symop_operation_xyz`, which GSAS-II
  checks its own reading against and which `setting_from_operators` reads one
  rank over on a `.gpx`. `_space_group_IT_coordinate_system_code` is **not** an
  answer: the core dictionary says outright that it "cannot be used to define
  the coordinate system", and neither program reads it.
- **A refusal can be the common case.** Both X-ray files in the corpus carry a
  negative `X`, so the reader refuses the only two files of the radiation most
  users have. That is `io/recipe.py`'s rule, earned there for the same reason
  (both committed LaB6 references converge to a negative `Y`), and the
  alternative is silently reading ~0 where the file states a number. It does
  mean the X-ray arm has **no corroborating file that reads**: its key names
  come from the specification and from `gsas2_pbso4.gpx`, whose two histograms
  carry the two key tuples exactly.
- **The arm that did not need editing.** The 4th session expected GSAS-II's
  writer to give `ProjectFormat.write` a value on the `gsas2_gpx` member. It
  does not, and should not: this build writes no `.gpx`, so that `None` is
  true, and the pair is published where the `.prm` pair is — the manual and the
  skill, with `capabilities()` naming neither. A GSAS-II-shaped capability
  question has no arm to read today, which is a gap somebody may want to close
  deliberately rather than by attaching this writer to the wrong member.

*Next*, in order.

1. **Decide whether this WP closes.** #148 is done and #234, #103, #101 and
   #107's decision are behind it. Two task lines are open and neither is
   ordinary work: the `#prm`-only integer evaluator is still blocked on TOPAS
   Technical Reference §19, which no session here has, and the fixtures line is
   open only for formats whose corpora cannot be redistributed, which will not
   change. Closing it and filing the evaluator as its own WP is the honest
   shape; leaving it open holds a WP number against a blocked ask.
2. **PR #291 touches `references/diagnostics-projects.md` §7g**, the file this
   session appended nine rows to. It is a contributor PR on a fork, moving the
   `RECIPE_*` block into that same section, so expect a conflict at the seam
   and take both — the rows are additive and the preamble edits are not.
3. Nothing is owed on the skill or the manual for what landed here.

### 2026-09-16 (4th session) — the GSAS writers, and the decimal point no test could catch

A model or a calibration built in rietx can now be handed to GSAS-I in GSAS's
own language, both halves of it: `rx.write_gsas_exp` writes the experiment —
phases, cell, sites, and which parameters were free — and `rx.write_gsas_prm`
writes a calibrated instrument as the `.prm` a beamline ships. Three of the
four foreign formats now travel in both directions, GSAS-II being the one
left. The work also found two things the *reading* side had wrong. One record
was being read two columns short, which no file in this repo could show. And
the writers were about to produce files that real GSAS would silently
misread, because a Fortran fixed-format field supplies its own decimal point
when you leave one out — a class no test in this package can catch, since
`float()` reads what GSAS would not.

*Done* — nine commits on `wp1118-gsas-writers`, branched off `ad6085c9`.

- **`aad84802`, the reader fix that came first.** `CHMF` — a phase's
  unit-cell contents — is `2X, A8, F10.2` and was read with both fields two
  columns short. `FAP.EXP` hides it completely: every content in it ends
  `.00`, so `'  CA            5.00'` sliced at `[8:18]` is `'        5.'`,
  which floats to 5.0. A partially occupied site is where it bites, and that
  is the ordinary case for a solid solution: 5.25 arrived as 5.0. Found by
  needing the true columns in order to *write* the record, which is an
  argument for writing a writer at all.
- **`88ab6dd6`, the `.EXP` writer** (`projects/gsas.from_structure`,
  `write_gsas_exp`, `rx.write_gsas_exp`): the inverse of `to_structure` —
  cell, sites, occupancies, `Biso` back through `EIGHT_PI_SQUARED` to the
  `Uiso` the record holds, and each `Parameter.vary` as GSAS's `Y` on the cell
  record and its `X`/`U`/`F` letters on a site's. Two fields are *derived*
  rather than carried, GSAS stating them and a `Structure` not: each site's
  multiplicity from its own orbit, and the `CHMF` contents summed over those.
  `d1f9eced` adds the two-phase row, which is what exercises the `CRS<n>`
  keys and `EXPR NPHAS`' nine fields.
- **`9dbd04f3`, the `.prm` writer** (`instrument_profile.from_instrument`,
  `write_gsas_prm`, `rx.write_gsas_prm`): `BANK`, `HTYPE PXCR`, `ICONS` and a
  type-3 `PRCF` block, `u/v/w` and `x/y` multiplied back into centidegrees and
  `axial_sl`/`axial_hl` written as `S/L` and `H/L`. Named `from_instrument` to
  match the three `from_structure`s: what varies between the four writers is
  the format, not the verb.
- **`dda4affc`, the class the 3rd session's review left open.** A
  `Parameter.value` of `+inf` is legal schema-side and both writers would have
  emitted Python's `inf` token; it is now refused by all five writing
  surfaces.
- **`f5936e21`, the arm.** `ProjectFormat.write` and
  `ProjectFormatCapability.writes` publish each format's writer by its
  *exported name*, `None` where there is none.
- **`686910f9`**, the two `ATTRIBUTION.md` rows, and **`af19f3e0`**, the
  forward reference into [1328](1328-magnetic-interchange.md), whose magCIF
  writer inherits `io/CLAUDE.md` § Project writers.

*Reviewed* — `/code-review high --fix` over the branch diff, `45e9f8ba`. Four
findings, all four real and all four fixed; nothing was declined.

- **The `.prm` `PRCF` fields fused, and the writer's own reader refused the
  file.** `_read_prcf` splits those continuation records on whitespace — the
  one place either GSAS reader does — while `write_field` right-justifies into
  fifteen columns, so a coefficient whose shortest exact decimal is fifteen
  characters abuts its neighbour and the pair reads as one unparseable token.
  The multiply into centidegrees carries the product's own float noise, so a
  **converged calibration hits this routinely**; every test written for the
  writer used round values (`1.163e-4` → `1.163`) and none of them saw it.
  One column is now reserved as the separator the token read needs. This is
  the finding worth carrying: I had written "the field is the budget" as
  though the budget were a property of the field, and it is a property of the
  *reader*.
- **The new non-finite refusal missed the one number that bypasses `_tail`**:
  an anisotropic site's `beq`, spelled bare because it is forced held.
  `beq ! inf` was exactly what that refusal was added to prevent.
- **`write_record` accepted a line break in a payload**, which splits a card
  in two under keys nothing wrote — the accident `split_records`' own
  docstring names from the reading side — and **a character `latin-1` cannot
  spell** raised `UnicodeEncodeError` at the encode, naming a byte offset into
  the finished file rather than the field a caller can fix.

*Measured* — this worktree's `.venv`, `[dev]` only (no jax, no torch), python
3.12.12, darwin/arm64.

- Fast selection `-n auto --dist loadgroup -m "not slow"` on **current `main`
  merged into this branch**, which is the tree that lands: **5101 passed, 133
  skipped**, 2:48, and this run was **alone** (`ps` checked, nothing
  mid-suite). `main` moved during the session — PR #280 merged, and its seven
  new `test_neutron_cw` rows are the whole of 5094 → 5101, so the two
  parents' additions do not simply sum and the branch-only figure is not what
  merges.
- The tests this session added are **+41 collected items** against the merge
  base `ad6085c9` — 37 functions across five files (`test_projects_gsas` +22,
  `test_gsas_prm` +11, `test_projects_topas` +2, `test_projects_fullprof` +1,
  `test_projects_registry` +1), plus four extra parametrized cases on one of
  them, five of the 37 being the review pass's. **No new skip.** That puts
  the merge base at
  5053 by arithmetic rather than by measurement: this worktree branched fresh
  off `origin/main` and the first edit preceded any run, so there is no
  pre-session baseline on this tree and the per-file counts are what is
  quoted (`tests/CLAUDE.md`'s own preference).
- Wall clock on the branch alone was 3:46–7:07 across four runs of the same
  selection, and those are **not alone-figures**: a `/pr-review` session was
  running the *slow* suite in `worktrees/pr-bench` for part of it, which is
  most of the spread. The 2:48 above is the only one measured alone.
- **No full selection, deliberately.** Nothing here can move a measured
  number: the writers have no caller inside the package, the `CHMF` fix
  touches a field (`GsasPhase.formula`) no fit reads, and the registry field
  is a declaration. Rung 3 is exclusive across sessions and the `/pr-review`
  slow suite held it anyway.
- The round trip on `FAP.EXP`'s own converged model is **bit-identical**,
  displacements included — its `Uiso` values came off a `.EXP` in the first
  place, so `×8π²` and back recovers them exactly. A hand-built `biso` does
  not, and that row is asserted separately at 1e-6 relative.

*Gotchas* — three, and the first is the one to carry out of this WP.

- **A Fortran `F` or `E` edit descriptor supplies the decimal point when the
  field has none.** So `90` written into an `F10.6` field is 9e-5 to GSAS
  while `_num`'s `float()` here reads 90: a round trip through this package
  stays green about a file that says something else to the program it is for.
  Caught by comparing the written cards against `FAP.EXP`'s own spelling,
  which is the only check available. **No test in this package can catch this
  class.**
- **`ICONS`' `ZERO` is unresolved, and it is what stops a useful `.prm`
  export.** The reader refuses a non-zero one because no file in this corpus
  states one to settle its unit against, so the writer refuses it too
  (`io/CLAUDE.md`'s magnitude rule) — which means a calibration with a refined
  zero shift cannot be exported as it stands. The evidence leans centidegrees:
  `io/formats/gsas.py` measured GSAS-I's CW pattern axis in centidegrees on
  real `CONS` banks. What would close it is **one real `.prm` with a non-zero
  `ZERO`, plus the `.LST` or pattern showing the offset** — a cheap
  maintainer-only ask, the shape of the Stoe `.raw` one.
- **A written `.EXP` states `EXPR NHST` of zero** and no `AFAC`
  scattering-factor records. That is an honest shape — it is what a `.EXP`
  written before any data was loaded looks like, and the reader already has a
  sentence for one — but it has **not** been opened in real GSAS and nothing
  here can check that it would be. The claim this session makes is the round
  trip through this package's own reader, plus columns matching `FAP.EXP`'s;
  the other three writers claim no more.

*Next*, in order.

1. **The GSAS-II writer** (`.instprm` + a CIF-shaped structure), the fourth
   and last format on #148. It needs a small `.instprm` reader built alongside
   to close its own round trip — only the binary `.gpx` and GSAS-I's `.prm`
   are read today — and it is where the banked **`Z`-term question** has to be
   answered: GSAS-II's CW Lorentzian is `γ = X/cosθ + Y·tanθ + Z` while
   `ProfileTCHZ` declares exactly `u, v, w, x, y`. Carry it or refuse it by
   name is still this WP's call. `io/CLAUDE.md` § Project writers is the
   rulebook it inherits, and **`references/api.md` has 373 B of headroom**, so
   its skill paragraph is paid for by a cut named in the commit.
2. **The `#prm`-only integer evaluator for `.inp` `#if` guards** is still
   blocked on a source, unchanged from the 3rd session: the grammar is TOPAS
   Technical Reference §19, which no session here has and none should guess
   at. Ask the maintainer for those pages first.
3. Nothing is owed on fixtures for what landed here. Both writers' tests build
   their `Structure` and `Instrument` by hand, the convention the reader tests
   already follow; the WP's fixture task is about committing real corpus files
   where a redistribution grant exists, and neither GSAS corpus has one.

### 2026-09-16 (3rd session) — the writers begin: TOPAS and FullProf write back what they read

Someone can now take a rietx model and hand it back to TOPAS or FullProf in
their own language. Before this session the translation only ran one way:
rietx could read someone else's `.inp` or `.pcr` and build a Structure from
it, but there was no way back, so a model built or edited in rietx stayed
here. `rx.write_topas_inp` and `rx.write_fullprof_pcr` close that loop for
two of the four target formats, each the exact inverse of its own reader:
same phases, same cell, same atoms, and the part a CIF cannot carry at all,
which parameters were free. GSAS `.EXP`/`.PRM` and GSAS-II still have no
writer.

*Done* — three commits, `6538d91e` (TOPAS), `abea74c7` (FullProf) and
`f7d875e5` (the review pass below), on this branch. **Two PRs, not one**:
PR #339 (draft, opened after the TOPAS commit as this session's WP claim)
was marked ready and merged by the maintainer while the FullProf work was
still in progress, so `abea74c7` and `f7d875e5` were stranded on an
already-merged branch (protocol step 10's own named failure mode) until
pushed and opened as PR #342 against the now-current `main`.

- `io/projects/topas.py` gains `from_structure`/`write_topas_inp` (+101
  lines): a phase's cell and every atom's coordinates, occupancy and
  displacement (isotropic `beq`, or the full `u11`…`u23` tensor behind the
  same `aniso=True` opt-in `to_structure` takes), each `Parameter.vary`
  written as TOPAS's own `@`/`!` flag, never a bare backtick, so no symbol
  table is needed to recover it. `rx.write_topas_inp` is a top-level export;
  `from_structure` stays module-level, matching `io/projects/__init__.py`'s
  own comment, already in the tree before this session, naming this as the
  shape a `from_structure` should take.
- `io/projects/fullprof.py` gains the same pair (+184 lines). FullProf's
  `.pcr` is whitespace-tokenized like TOPAS but strictly *positional*, with
  no keyword to resynchronise on, so every control/output/pattern/cycle/
  background line the reader expects has to exist even though a `Structure`
  carries no information for most of them; the writer fills those with safe,
  inert placeholders. Every free parameter gets its own codeword (`10*n+1`,
  `n` counting up), never a shared tie, since a `Structure` carries no
  record of which parameters a refinement tied and `to_structure` only ever
  *reports* a dropped tie rather than needing one restored.
- Both writers discharge the banked obligation this WP file already named:
  space groups are written `get_spacegroup(phase.space_group).xhm()`, never
  the phase's stored string ([1324](1324-symmetry-silences.md)). FullProf's
  format has **no way to spell an origin or axis suffix at all** — a bare
  symbol can only read back as whatever `normalize_space_group` already
  prefers (choice 2, and `:R` only where the cell metric says so) — so
  `write_fullprof_pcr` refuses a phase whose resolved setting a bare symbol
  cannot reach, checked by literally calling `normalize_space_group` on the
  candidate output rather than by a heuristic. TOPAS's `Z`/`S`/`R`/`H`
  suffixes carry every setting, so no such refusal exists there.
- Both refuse an anisotropic site their own `to_structure` cannot build
  either — FullProf always, since its β_ij convention is exactly what
  `to_structure` refuses to assume on the way in; TOPAS only where the
  caller writes a `Structure` with `atom.aniso` set, since TOPAS's own
  `to_structure` *can* build one behind `aniso=True` and the writer carries
  it the same way.
- FullProf's `Occ` column is discarded by `to_structure` regardless of what
  a file states (every atom always comes back fully occupied), so the writer
  computes it from each site's own multiplicity (`M_site / M_general`), the
  only value that makes every atom's ratio equal to 1 and so passes
  `occupancy_factor`'s consistency check, rather than carrying a chemical
  occupancy the `Structure` schema has no field for.
- Round-trip acceptance for both: no committed fixture, matching the
  existing reader tests' own convention (both corpora are private research
  inputs) — every `Structure` is built by hand in the test, written,
  re-read through the real reader, and compared field by field.
  `tests/test_projects_topas.py` +8 test functions (307 collected total);
  `tests/test_projects_fullprof.py` +9 test functions / +10 collected items
  (one parametrized ×2; 147 collected total).
- Docs: `docs/manual/using/files.md` gained a "Writing one back" section
  (both formats, one code example each) and the provisional-names
  admonition now lists both writers; `docs/skill/make_api_index.py`'s
  `SECTIONS` grew a paragraph and both entry-point names, regenerated into
  `docs/skill/rietx/references/api.md` (34 502 B of 36 000, 1 498 B free)
  and synced to both committed copies with `rietx skill --install . --copy`.

*Reviewed* — `/code-review high --fix` over the branch diff plus the
uncommitted writer work. It ran five finder angles; four returned promptly
and one (a line-by-line scan) took roughly fourteen minutes, so the report
arrived in two waves — the second amending the first's counts rather than
replacing them, which is recorded here rather than silently reconciled.
Ten findings fixed, two left as notes.

- **Two real round-trip holes, one per format, both closed.** Neither
  writer checked an atom's `label`/`species` for a character the target
  format treats as structural. TOPAS: an unquoted `'` opens a line comment
  (`strip_comments`), so `"O'Brien"` would silently drop x/y/z/occ/beq for
  that site with nothing raised. FullProf: any of `!`/`#`/`<--` cuts the
  line at `_strip()`, the same class this writer already guarded on
  `phase.name` but had not extended to an atom's own fields. Both now
  refuse, naming the character.
- **A blank FullProf phase name** would strip to nothing and vanish from
  the reader's own blank-line filter, silently shifting every line after it
  up by one — refused, the same "positional format, no line may disappear"
  reasoning the placeholder-lines design already rests on.
- **Whitespace in a label/species**, for both formats — the class I had
  already caught for FullProf but had not written for TOPAS; the review
  added TOPAS's and confirmed FullProf's.
- **A negative `biso`**, for both formats: each reader's own `to_structure`
  refuses one on the way in, so writing one out would only fail later, at
  the read, with the file already on disk and the caller's error message
  pointing at the wrong function.
- **The distribution name was spelled `"rietx"` literally** in each
  writer's file-header comment line, against root CLAUDE.md's own rule
  ("never spell the distribution name … import it from `_about.py`"), which
  I missed writing it the first time. Both now import `DIST_NAME`.
- **FullProf's placeholder Cu Kα1/Kα2** were typed as separate literals
  (1.540560/1.544390) instead of the package's own canonical
  `schemas.instrument._KA_DOUBLETS["CuKa"]` (1.5405929/1.5444274) — inert
  either way (`to_structure` never reads this line into a `Structure`), but
  a second, independently-sourced copy of a number the package already
  carries once is exactly the class root CLAUDE.md's numbers rule warns
  about. The first wave noted this and deliberately left it; the second
  wave judged it cheap enough to fix and did.
- **A dead helper** (`_pair`, an unused early draft of `_free_or_held`) and
  **a comment describing an absence rather than the line it sat on**
  (`# Nex = 0: no excluded-region lines.` sitting directly above the
  *required* refined-parameter-count line) were both cleaned up.
- Two items noted and deliberately left: `capabilities()` has no field
  naming which project formats support writing, which is this WP's own
  still-open "capabilities() arm" task rather than a defect in this diff;
  and the FullProf writer's inline `dict(k=v, …)` placeholder literals
  restate field names as a second spelling of `_PHASE_FIELDS`/`_CONTROL_
  FIELDS`/etc. rather than the reader's `dict(zip(_FIELDS, values,
  strict=True))` shape — cosmetic, no observed defect.
- One thing surfaced and left for the record rather than fixed: `Parameter.
  value` may legally be `+inf` (unreachable from a converged fit — softplus
  bounds prevent it — but not schema-refused), and both writers would emit
  Python's `inf` token, which neither real program parses. A design
  question, not a one-line fix.
- I read every hunk both waves produced before accepting it, then found and
  fixed one thing the review's own docstring updates missed: FullProf's
  docstring still said "Four refusals" after the second wave added three
  more (blank name, both comment-marker checks) without updating the count
  or narrating them, and TOPAS's said "Two refusals besides the phase-name
  quote check" after gaining a third (the single quote). Both counts and
  narrations are corrected in this branch.

*Measured* — this worktree's `.venv`, `[dev]` only (no jax, no torch),
python 3.12.12, darwin/arm64.

- Fast selection `-n auto --dist loadgroup -m "not slow"`, run four times
  across the session as work landed: **5040** (TOPAS alone) → **5046**
  (+ FullProf) → **5050** (+ my own four refusal tests) → **5053** (+ the
  review's three), **133 skipped** throughout, final run 2:11. Every
  delta is exactly the collected test items the intervening edit added;
  nothing else moved. This worktree was fresh off `origin/main` at the
  session's start and the fast suite was not run before the first edit, so
  there is no true pre-session baseline on this tree; the per-file counts
  in *Done* are quoted instead (`tests/CLAUDE.md`'s own preference). Wall
  clock is quoted without a same-machine `ps aux` check at the moment each
  run fired, so these are figures rather than confirmed-alone ones.
- `tests/test_manual.py`, `tests/test_manual_api.py`, `tests/test_skill.py`,
  `tests/test_skill_cli.py`, `tests/test_docs_consistency.py`: all green on
  the final tree. One catch worth recording: the manual's zero-em-dash
  register test (`test_the_manual_keeps_its_register`) caught two em dashes
  in the first draft of the new manual section — the guard worked exactly
  as designed.
- No full selection: nothing here can move a fit result or any existing
  measured number — both commits add pure I/O functions with no caller
  inside the package, the same reasoning the GSAS-II `.gpx` reader session
  gave for skipping it.

*Gotchas* — three, each a place the next session on the writers task should
not assume.

- **The writer's refusals raise plain `ValueError`, not
  `TopasInpError`/`FullProfPcrError`.** Deliberate: those classes' own
  docstrings say "naming the file and the offending line" / "naming the
  file, never its parser's exception" — read-side semantics for a file on
  disk, and a writer has no file or line to name, only a `Structure`
  already in memory. Revisit if a caller wants to catch one error type
  across both directions.
- **FullProf's `Occ` write-back is unverifiable by round trip, on purpose**:
  `to_structure` discards the column entirely (every atom always comes back
  at `occ = 1.0`), so the value the writer computes (`M_site/M_general`) is
  never actually checked by re-reading it, only that it does not trip
  `occupancy_factor`'s consistency refusal. If a future consumer ever reads
  `FullProfModel.phases[i].atoms[j].values["occ"]` directly (bypassing
  `to_structure`), the written number should be checked against what a real
  file states for the same site, not just internal consistency.
- **Neither writer refuses `+inf`.** A `Parameter.value` of `+inf` is legal
  schema-side and unreachable from a converged fit (softplus bounds prevent
  it), but not schema-refused on an arbitrary hand-built `Structure`, and
  both writers would emit Python's `inf` token, which neither TOPAS nor
  FullProf parses. Surfaced by the review pass and left as a design
  question rather than a one-line fix — it is not clear yet whether the
  right answer is a refusal (matching the other seven) or a `NaN`/`inf`
  handling convention shared with the CIF exporter.

*Next*, in order, with what decides between them.

1. **GSAS `.EXP`/`.PRM` and GSAS-II (`.instprm` + CIF) writers**, the two
   remaining formats on the writers task (#148). GSAS `.EXP` is a fixed
   80-character-card format (`io/CLAUDE.md`'s GSAS row, Fortran `FORMAT`
   widths) rather than whitespace-tokenized like TOPAS and FullProf — a
   different and more failure-prone class of work, since a wrong column
   width corrupts silently rather than raising, and it deserves its own
   session rather than being rushed at the tail of this one. GSAS-II's
   write target was already decided in this file's Context section
   (`.instprm` text + a CIF-shaped structure via the existing
   `write_refinement_cif`), but **no `.instprm` reader exists yet** — only
   the binary `.gpx` and GSAS-I's own `.prm` are read — so that direction
   needs a small reader built alongside the writer to close its own round
   trip, which TOPAS and FullProf did not need. `capabilities()` still names
   no field for which formats support writing (raised by the review pass,
   not new this session) — worth deciding once all four writers exist
   rather than growing the arm twice.
2. **The `#prm`-only integer evaluator for `.inp` `#if` guards is blocked
   on a source, not on design.** Its grammar (`#if (#out pattern_count >
   1)`, a `Run_Number` guard) is in the TOPAS Technical Reference §19,
   which this session does not have access to and should not guess at —
   root CLAUDE.md's rule and this project's own licence fence both say the
   reference is read, not inferred from archive files a reader may not
   even see. Ask the maintainer for the §19 pages on `#if`/`#prm` before
   starting this one.
3. Fixtures with provenance rows for TOPAS and FullProf: nothing appears
   to be owed here for what landed this session. Both writer tests already
   follow the existing reader tests' own convention (inline synthetic
   fixtures, no committed file, per each module's own docstring) — the
   WP's fixture task is about committing real corpus files where a
   redistribution grant exists, which TOPAS's and FullProf's private
   archives do not have regardless of what a writer adds.


### 2026-09-16 (2nd session) — the setting a file states, and the question the issue had already answered

Hand this package a GSAS-II refinement and it now builds the phase under the
symmetry the file describes, rather than under gemmi's reading of the symbol's
name. A Hermann-Mauguin symbol such as `F d d d` names two different groups,
and which one is meant decides how many atoms each site puts in the cell. Taken
the wrong way, GSAS-II's own tutorial spinel CuCr₂O₄ imports as Cu₂CrO₄: the
quantity every weight fraction divides by is then out by 5 %, and the fit
converges regardless. GSAS-II writes the operations beside the symbol, so
nothing here needs to guess — the reader checks which setting they are. Four of
the 46 phases in the public tutorial corpus needed that, and all four were being
read the wrong way. The two formats that state a symbol and nothing else,
`.EXP` and `.inp`, cannot be read this way, so they now say **at read** that the
setting was assumed, which is what issue #101 asked for at the place it asked
for it.

The issue's own proposal had expired in both halves before the work began, and
that is the part worth carrying. The TOPAS suffixes it asked for landed with
PR #98 a fortnight earlier. The diagnostic it proposed had landed too, under
another name and covering more: WP-1324's `SPACE_GROUP_SETTING_ASSUMED` spans
all 40 multi-setting symbols rather than the origin choices alone. So there is
no `SPACE_GROUP_ORIGIN_ASSUMED` and there should not be, and the useful work was
never the work the issue described. Checking that cost an hour against a
two-line claim in this file.

*Done* — nine commits on `wp1118-origin-choice`, cut from `origin/main` at
`b48088f8`.

- `crystallography/symmetry.py` holds both halves of the answer.
  `setting_from_operators(symbol, operators)` returns the one setting whose
  tabulated operations equal the ones a file states, or `None` where none does
  or where there was nothing to choose. `operator_key`/`operator_keys` are the
  comparison, translations reduced to twelfths so `-1/4` and `3/4` are one
  operation and no tolerance enters it. `setting_diagnostics` is the
  `SPACE_GROUP_SETTING_ASSUMED` builder, lifted whole out of `refine.py` so a
  reader and a fit report one fact from one place.
- `io/projects/gsas2.py` feeds it `SGData['SGOps']` × `SGCen` × `SGInv`.
  `Gsas2Phase.space_group` still holds the file's own string,
  `.space_group_from_operators` what the operators say, and
  `.resolved_space_group` is what `to_structure` builds under.
  `GSAS2_GPX_SETTING_FROM_OPERATORS` reports the read, saying whether the
  operators overturned the bare reading or confirmed it.
- `io/projects/gsas.py` and `io/projects/topas.py` report at read through the
  shared builder. A `.inp` carrying TOPAS's origin suffix is translated as
  before and is **not** also reported as assumed.
- The message stops quoting a discriminator it has not checked. Where every
  setting implies the same contents it quotes the site multiplicities instead,
  and the suggestion stops claiming a ZMV that has not moved.
- `tests/data/gsas2_mn3o4_setting.gpx`, the third vendored `.gpx` and the only
  corpus file that both states a setting its symbol does not and builds end to
  end. `tests/data/README.md` gains the blobless-clone recipe for re-fetching
  the 34-project corpus, which took working out twice.
- `io/CLAUDE.md` 410 → 428 and `CLAUDE.md` 833 → 836, each raised in the commit
  that says why.

*Measured* — this worktree's `.venv`, `[dev]` only (no jax, no torch), python
3.12.12, darwin/arm64. Counts are the **merged** tree's: `origin/main` moved
three commits under this branch during the handover (the watch-unroll merge,
PR #337) and was merged in before the last run. Those three are **docs only**,
`docs/` and nothing else — which is why the full selection below was not
re-run after the merge and why the fast selection came back unchanged across
it. The machine was **not** idle for any of this, so every wall clock here is
a range rather than a figure: the same fast selection took 2:10 alone and
4:27 beside another session's suite.

- Fast selection `-n auto --dist loadgroup -m "not slow"`, run both sides of
  the merge and identical across it: **5030 passed, 133 skipped**. Against the 4997/133 the previous session measured on what
  is now `origin/main`, in this same worktree and venv, that is **+33 passed
  and no skip moved**. It divides exactly: 19 this session wrote
  (`test_projects_gsas2.py` +7, `test_symmetry_orbits.py` +6,
  `test_projects_gsas.py` +3, `test_projects_topas.py` +3) and 14 the review
  pass added (1 in `test_projects_gsas2.py`, 13 parametrised cases in
  `test_skill.py`). Nothing here added a skip.
- Full selection `-n auto --dist loadgroup`, run **before** the merge with
  nothing else mid-suite (checked with `ps aux | grep`): **5200 passed, 142
  skipped**, 24:22. It ran because the change touches `refine.py`, which is in
  the fit path even though only its diagnostics moved. There is **no comparable
  baseline**: the previous session ran no full selection, and the nightly's
  figures are Linux under `[dev,jax]`, so this is quoted as this tree's number
  and not as a delta.
- `tests/test_acceptance_fap.py`: 3 passed, 3.19 s — the row that would notice,
  since it reads its protocol from the `.EXP` reader this session changed.

*The measurement the work rests on* — the 34 public GSAS-II tutorial projects,
read with the finished reader.

- **4 of 46 phases state a bare symbol the tables hold in two settings**, and in
  every one the file's own operators are origin choice **2** where the bare
  symbol resolves to choice 1: `F d d d` in `AllDataStart`, `SeqFit` and
  `SingleHistFit` (all CuCr₂O₄), `I 41/a m d` in `Magnetic-V` (Mn₃O₄). The other
  42 reproduce the setting their symbol names, so reading the operators agrees
  with the symbol wherever the symbol is unambiguous and corrects it where it is
  not. After the change, 4 settled and **0 left assumed**.
- **What choice 1 costs is not uniform, and that is the interesting half.** The
  spinel's composition changes — Cu₂CrO₄ for CuCr₂O₄, ZMV 1 093 848 against
  1 041 875, 5.0 %. Mn₃O₄'s does **not**: it is Mn₁₂O₁₆ either way, because both
  cation sites are Mn. What moves there is which site carries which
  multiplicity (8c/4b against 4a/8d), and that moves **56 % of the calculated
  intensity** after the best common scale (measured against a synthetic Cu Kα
  pattern, 10–90° at 0.02°). So a composition check cannot see the second case
  at all.
- **That is also what was wrong with the message.** Its discriminator is the
  composition each setting implies, which on Mn₃O₄ printed `Mn12 O16` twice
  while the suggestion still asserted that the choice "changes ZMV and every
  weight fraction". Both settings give the same ZMV there. It now falls back to
  the site multiplicities and says what does move.
- **Nothing in the corpus reaches a wrong answer through `to_structure` today**,
  and that is luck rather than a defence: the three spinel files refuse for an
  unrelated negative `Uiso`, and Mn₃O₄'s composition is setting-blind. The
  defect was the reader discarding what the file states, and it is fixed at the
  mechanism.

*Reviewed* — `/code-review high --fix` over the branch diff. Three findings,
all three acted on rather than two.

- **The new message claimed an overturn it had not made.** `setting_from_operators`
  returns a setting whenever the operators match one, including the setting the
  bare symbol already resolved to, and the message said the phase was built
  under the operators' answer "rather than" that reading. On a hexagonal-axes R
  phase the two are the same string, so it fired asserting a change that did not
  happen. Exactly the class the root rulebook's declared-name clause covers, in
  message text rather than in a field. The message now branches on which
  happened.
- **The skill row shipped twice**, in all three committed copies, the two
  claiming slightly different things. A scripted edit added it and then an
  inline one added it again. A new meta-test over every reference
  (`test_no_code_is_listed_twice_in_one_reference`) closes the class; it is the
  only duplicated code in the references today.
- **The review declined the third and this session took it.** The new TOPAS row
  addressed its phase by index where every other row in that reader addresses it
  by name — including `TOPAS_ORIGIN_TRANSLATED`, which writes the *same field of
  the same phase*. One field reachable two ways is worse for a consumer than
  either convention, so the new row matches its siblings. Whether that reader
  should address phases by name at all, when the rest of the package uses
  index-based dot-paths, is a real question and is **not** this WP's.

*Gotchas* — three, each a place the next session should not assume.

- **The `:H`/`:R` half is decidable from the cell and is deliberately still
  reported.** An axis choice, unlike an origin choice, is settled by the metric,
  and `fullprof.normalize_space_group` already does exactly that for a `.pcr`.
  Extending it to the `.EXP` and `.inp` readers was built and then **reverted**:
  it would silence the calcite case that WP-1324 chose on purpose to report, for
  a case no corpus here contains — every R phase in every corpus available is on
  hexagonal axes. The consequence to know is that a bare `R -3 c` in a `.inp`
  now raises `SPACE_GROUP_SETTING_ASSUMED` at read as well as at fit, which is
  why `test_projects_registry.py`'s expected code set grew one member.
- **`structure_from_cif` resolves a bare multi-setting symbol two ways**, by
  which of its two paths ran: `gemmi.read_small_structure`'s own `spacegroup`
  gives `F d -3 m:2`, and the fallback's `find_spacegroup_by_name` on the raw
  H-M string gives `:1` — the two settings whose multiplicities swap. Both
  resolvers were measured; no file was built that takes the fallback, so how
  reachable it is stays open. Filed into [1319](1319-structure-interchange.md),
  which owns CIF interchange. Out of scope here deliberately: this WP's subject
  is the four foreign *project* formats, and the CIF route at least pins its
  choice into the symbol it returns.
- **The operator expansion is validated, not assumed.** `SGOps` are coset
  representatives, so the group is their product with `SGCen` and with the
  inversion — and that reconstruction reproduces a tabulated setting exactly on
  all 46 corpus phases, which is the evidence that the expansion is right. The
  `F d d d` operators in the synthetic tests are written from the tables rather
  than generated from gemmi: a fixture built from gemmi could only show the
  reader agreeing with itself (`io/CLAUDE.md` § Adding a format, rule 4).

*Next*, in order, with what decides between them.

1. **The writers** (#148), now the only substantial task left on this WP. Its
   two banked obligations both stand, and one is cheap: `Z` is zero in all 95
   constant-wavelength histograms the corpus states it on, so refusing a
   non-zero `Z` by name costs nothing a round-trip can see, and growing
   `ProfileTCHZ` a sixth coefficient would be a declared name with no writer.
   The second obligation gains a sibling from this session: an exporter writes
   `get_spacegroup(sym).xhm()` rather than the stored string
   ([1324](1324-symmetry-silences.md)), and a GSAS-II exporter should write the
   **operators** too, since that is what this session made a `.gpx` reader trust.
2. The `#prm` integer evaluator for `.inp` `#if` guards, which is what puts the
   three multi-pattern Durham reel files in reach.
3. Fixtures with provenance rows for the formats that still have none — which
   means TOPAS and FullProf, whose corpora are private, so the honest form is
   what a synthetic file can prove.


### 2026-09-16 — the GSAS-II `.gpx` reader, and the corpus that changed three answers

Someone can now hand this package a GSAS-II project file and get back the model
it describes: the phases, the sites, the instrument, and the part nobody can
rebuild from a CIF plus a pattern, which is which parameters that refinement was
free to move. A `.gpx` also carries two things the older formats have no room
for, and both come across: the constraints the run held its variables under, and
the list naming every variable it refined. None of it needs GSAS-II installed.

The obstacle was never the format. A `.gpx` is a sequence of python pickles, and
loading a pickle runs whatever it names, so opening a downloaded one would be
handing a stranger's file the keyboard. The reader resolves an allow-list and
refuses every other name, naming it, without reading the file at all.

The part worth knowing is that **the allow-list could not have been written from
one archive**. Issue #234 proposed one measured on 146 private projects; read
against the 34 public tutorial projects, seven of the eleven names that actually
occur are outside it, and two of those are GSAS-II's own classes, which appear in
10 of the 34. Refusing them by name would have refused those ten files entire.
They are admitted as inert stand-ins instead — a class with no `__reduce__` and
no `__setstate__`, which the pickle machinery can only fill with data — which is
the same shape PyTorch's `weights_only` unpickler uses, and it is why the
constraints are readable at all. Widening the corpus before writing the reader
was the whole of this session's method, and it moved two more answers: the sniff
cannot be the magic bytes, because 11 of the 34 files carry no pickle protocol
header; and GSAS-II's `GOF` is the **square root** of reduced χ², which is the
opposite of what this repo's `.EXP` reader said about it.

*Done* — six commits on `wp1118-gsas2-gpx`, cut from `origin/main` at `6d42926e`.

- `src/rietx/io/projects/gsas2.py` (1 100 lines) — the reader.
  `rx.read_gsas2_gpx` returns a `Gsas2Model`; `projects.gsas2.to_structure`
  builds a `Structure` carrying the file's own refine flags.
  `ALLOWED_GLOBALS` is the trust boundary as **data**, with a reason per entry
  and a meta-test partitioning it against the resolver both ways.
  `TREE_ITEM_STANCE` declares one stance per tree-item kind, sharing
  `coverage.Stance`'s vocabulary, so an unclassified item is reported rather
  than dropped.
- `PROJECT_FORMATS` gains `gsas2_gpx` **first**, being the registry's one binary
  member: every other sniff decodes with `errors="ignore"` and would meet a
  pickle as text with its bytes dropped. `capabilities().project_formats` needed
  no edit, being derived from the registry.
- Seven `GSAS2_GPX_*` diagnostics, rows in the skill's §7g, a Part 1 section over
  the whole `Gsas2Model` tree, and an `ATTRIBUTION.md` row naming which document
  was read as specification.
- `tests/test_projects_gsas2.py` (37 tests) and two vendored fixtures. These are
  the **first project-reader fixtures this WP could vendor at all**: the GSAS-II
  tutorials carry a redistribution grant where TOPAS's and FullProf's corpora are
  private research inputs.
- `projects/gsas.py`'s GOF corroboration corrected, in `GsasModel.reduced_chi2`,
  in `_reduced_chi2` and in the test docstring that repeated it. The GDNFT claim
  itself stands: that record states the words.
- `io/CLAUDE.md` takes three rules and the cap goes 383 → 410.

*Measured* — this worktree's `.venv`, `[dev]` only (no jax, no torch), python
3.12.12, darwin/arm64, alone on the machine (checked with `ps aux | grep`).

- Fast selection `-n auto --dist loadgroup -m "not slow"`, on **current main
  merged into this branch**, which is the only tree anything ever tests that
  resembles what lands: **4997 passed, 133 skipped**, 2:10. On the bare branch
  before the merge it was 4990/132.
  The delta is derived per file rather than by re-measuring `main`. This
  session added **45**: 39 in `test_projects_gsas2.py`, 3 in
  `test_projects_gsas.py` and 1 in `test_gsas_prm.py` (the last four from the
  review pass), plus **2** parametrised cases the new registry member adds to
  `test_projects_registry.py` (`[gsas2_gpx]` on the `reports_at` and
  declared-field rows). Against the 4951 the previous session measured on the
  branch that is now `origin/main`, that is 4996, and the merge with WP-1423's
  main accounts for the remaining +1 pass and the one new skip — **which is
  WP-1423's, not this session's**: nothing here added a skip. Two parents'
  additions do not sum, so the 4997 is quoted as the merged tree's figure and
  not as either parent's.
- `tests/test_acceptance_fap.py`: 3 passed, 3.19 s. It reads its protocol from
  the `.EXP` reader, which this session touched (comments only), so it is the
  row that would notice.
- **No full selection.** Nothing this session added is reachable from a fit: the
  new reader has no caller inside the package, and the `.EXP` edits are
  docstrings. No measured number can move.
- The corpus, read with the finished reader: 34 projects read, **0 refused**; 19
  build a structure and 15 refuse by name (7 for a negative `Uiso`, 5 for
  anisotropic sites, 2 for stating no phases, 1 for a Le Bail phase with no
  sites). The survey behind those numbers is in `tests/data/README.md`
  § GSAS-II `.gpx`.
- The centidegree convention is corroborated **across formats** by a file this
  repo already held: the tutorial `.gpx` of the 11-BM instrument states `U`, `V`,
  `W` of 1.163, −0.126, 0.063, and `read_gsas_prm` converts
  `tests/data/11bm_gsas.prm` to 1.163e-4, −1.26e-5, 6.3e-6 deg². `Zero` is the
  exception and is degrees in GSAS-II, by its own specification and by the
  magnitude of the nine non-zero values in the corpus (0.0004° to 0.0219°).

*Reviewed* — `/code-review high --fix` over the branch diff, and it found the
class this session thought it had closed. Six fixes accepted, each with the test
it was missing; the review reproduced every one before changing anything.

- **The `.EXP` reader had the same hole the `.gpx` reader was written to
  avoid.** A file stating a negative `Uiso` reached `rx.Parameter` and came back
  as a pydantic `ValidationError` naming a `Parameter` and never the file. The
  refusal and the one-guard build are now in both readers, which is what
  "generalise the fix" should have meant while writing the second one rather
  than after.
- Two in the new reader, both on malformed input: the id-resolving passes
  assumed a tree-item shape the main loop had already reported as unreadable
  (a bare `[42]` raised `TypeError` out of the reader), and an empty atom row
  reached `row[-1]`.
- `GsasHistogram.two_theta_range` could come back `(None, 129.98)` under a
  `tuple[float, float] | None` annotation, which is WP-1076's shape in a field
  nobody had looked at.
- `BANK` was the one record in `instrument_profile.py` not read by column, in a
  module whose whole argument is that they are: a record carrying a comment
  after its `I5` count was reported as an absent record.
- Two dead names removed (`seen` here, `_EIGHT_PI2` in `viz/compare.py`).

Two findings were looked at and left, both recorded here rather than silently:
the `.EXP` row's `extensions=(".exp", ".EXP")` renders a second suffix that buys
nothing when matching is content-based, and `_matches_gsas_exp`'s `lines[:-1] or
lines` drops the last complete record when the head covers the whole file, which
can only bite a `.EXP` whose one vocabulary key sits on its final card.

*Gotchas* — three, each a place the next session should not assume.

- **The excluded-region path is specification-only.** Not one of the 195
  histograms in the corpus has one, so `Limits[2:]` rests on GSAS-II's own
  statement in `GSASIIstrIO` and is exercised by a `.gpx` the test module writes
  rather than by a real file.
- **The anisotropic refusal is liftable by a measurement, not by an opinion.**
  126 of the corpus's 439 sites are anisotropic and all of them are refused,
  which follows the `.EXP` and `.pcr` readers. Whether GSAS-II's `Uij` are CIF
  `U^ij` is testable rather than arguable: feed them through
  `crystallography.wyckoff.adp_basis` and see whether they lie in the
  site-symmetry subspace, which a wrong off-diagonal convention would break.
- **A `magPhases` key makes a nuclear phase half a model.** Ten corpus phases are
  typed `nuclear` and carry one, and they build correctly; what does not come
  across is the magnetic scattering in the file's own Rwp, so the figures are not
  comparable. That is a warning rather than a refusal, and it is a different
  shape from the magnetic phase the same code refuses.

*Next*, in order, with what decides between them.

1. **Origin-choice honesty** (#101), still the cheap one:
   `normalize_space_group` is drafted in the #98 branch and the task closes an
   issue.
2. **The writers** (#148). One of its two banked obligations is now evidenced
   rather than open: `Z` is zero in **all 95** constant-wavelength histograms
   the corpus states it on, so nothing anybody writes needs the field, and
   refusing a non-zero `Z` by name costs nothing a round-trip can see. Growing
   `ProfileTCHZ` a sixth coefficient is measurable work — the five-name tuple is
   hard-coded in four places and 121 files name a profile path — and it would be
   a declared name with no writer until the forward model computed it.
3. The `#prm` integer evaluator for `.inp` `#if` guards.


### 2026-09-16 — the handover the column read never wrote, and the refusal the repair found

A session that finishes its work and never writes it down leaves the next person
reading commit messages. This is that record. The entry below reconstructs what
the column read did; this one covers the repair that wrote it.

The repair was meant to be bookkeeping. It turned up two things instead. One is
a claim in this file that had never been true. The other is a defect in the
merged reader, and it is the one worth knowing. Handed a `.prm` whose numbers
fall outside what this package's schema holds, `read_gsas_prm` did not refuse
it. Pydantic did, naming a `Parameter` and never the file, which is the one
shape `io/CLAUDE.md` forbids a reader. It refuses by name now.

*Done* — on `wp1118-prm-columns-handover`, cut fresh from `origin/main`. The
column session's branch was already merged, so a commit on it would have been
stranded where the merge could not carry it.

- The reconstructed entry below, the Status line, and WP-1314's `### Inherited`.
- `0efac867`, the refusal, with its parametrised test.
- The stale claim in the skill task, repaired in place and dated.

*Measured* — this worktree's `.venv`, `[dev]` only (no jax, no torch), python
3.12.12, darwin/arm64, alone on the machine (checked with `ps aux | grep`, not
`pgrep`).

- The four `.prm` fixtures re-read on the merged tree. They come back
  single-line at λ 0.41391, 0.41313, 0.41368 and 0.41330 Å, each weight 1.0,
  and `INST_XRY.PRM` refuses naming `GP`. That corroborates the shape of the
  answer. It does not re-verify the bit-identity claimed in the entry below,
  which needs the pre-branch module and stays that session's measurement.
- **The column session recorded no selection count. This one measured**, on
  the repair branch, alone on the machine: fast selection
  `-n auto --dist loadgroup -m "not slow"` → **4951 passed, 132 skipped**, 3:23.
  Five of those are this repair's own parametrised refusal test, so `origin/main`
  stands at 4946, derived per file rather than by re-measuring it
  (`tests/CLAUDE.md` rung 4).
- **That figure does not yield the column session's delta.** The 1st session
  measured 4925 passed on *its branch*, `7747a14e`, and the tree that became
  `origin/main` is that branch merged into a `main` which had moved under it.
  Two parents' additions do not sum (`tests/CLAUDE.md` § Quoting numbers), so
  the attributable figure here is the per-file one: `tests/test_gsas_prm.py`
  went 29 → 38 test functions.
- `tests/test_gsas_prm.py` 40 → 45 cases with the refusal test, all passing.
  `test_manual_api.py`, `test_docs_consistency.py` and `test_skill.py`: 101
  passed. `ruff check src tests examples` clean.
- No full selection. On a successful read the refusal converts nothing and
  reorders nothing, so no measured number can move.

*The review pass* — `/code-review high --fix`, run by this repair. It found
something in the merged code rather than in the repair. That is the case step 9
of the handover exists for.

Read what it is before relying on it. The diff under review was this branch's,
which is documentation, so the reader was opened as **context** and never as
reviewed scope. One defect surfaced that way. PR #332's code has had exactly one
systematic review and it is the column session's own (`2a96b536`); nothing here
re-reviewed it, and a second defect of the same kind would not have been found.

`read_gsas_prm` converts the file's numbers onto the schema by assignment, and
`Base` validates on assignment while `Parameter` carries a bounds validator. A
`.prm` stating a negative `GW` therefore raised pydantic's `ValidationError`
naming `Parameter`, with no file in it, which is the shape `io/CLAUDE.md`
§ Refusals forbids a reader. The conversion now sits in `_build_instrument`, and
a schema error at that boundary comes back as a `ValueError` naming the file and
quoting every value it converted. The same exposure ran through `LAM1`, `LAM2`,
`POLA`, `KRATIO`, `GU` and the two axial terms, so the test is parametrised over
five of them (`0efac867`).

Two smaller things came with it. The build moved above the diagnostics block.
The emission site's own comment already promised that, and the test now asserts
the caller's list is empty when a file is refused. And the manual
documented the two diagnostics in the wrong order. `GSAS_PRM_FIELD_DROPPED`
precedes `GSAS_PRM_GEOMETRY_ASSUMED`, checked on `11bm_gsas.prm`, and that error
predates the reorder.

One finding was declined as written. The patch's docstring and its test comment
both said a GSAS fit of a broad laboratory pattern lands `GW` negative
"routinely". Nothing in this session measured that. The docstring now states the
measurement that was made and says plainly that the frequency was not.

*Next*, in order, with what decides between them.

1. **The GSAS-II `.gpx` reader behind the restricted unpickler.** It is the last
   reader, and the writers task cannot be scoped until every reader's model
   exists. Its own first step is widening the corpus. That is measurement, and
   it can start before any unpickler is written.
2. **Origin-choice honesty** (#101), the cheap one. `normalize_space_group` is
   already drafted in the #98 branch and the task closes an issue.
3. The writers (#148), then the `#prm` integer evaluator for `.inp` `#if`
   guards.

One thing the WP file called owed is not owed. This repair checked `SKILL.md`
before repeating the claim, and line 41 already names the situation and routes
to `references/api.md` § In. It landed 2026-08-30 under WP-1308, before the
note calling it missing was written, and the "PowderLine recipe" the note
quotes is a manual page in the row's third column. The task text now says so,
with the byte headroom re-measured: `SKILL.md` has 1 049 B free of 33 000 and
`references/api.md` 3 204 B of 36 000, both tighter than the 09-13 figures they
replace.


### 2026-09-15 (2nd session) — `read_gsas_prm` by column, and the refusal whose reason had expired (reconstructed post hoc)

A lab `.prm` written for a copper tube states two wavelengths. rietx refused
every such file, and the reason it printed was that no file said how to weight
the second line against the first. The file did say. The reader could not find
the number because it read the record by splitting on spaces, and under that
reading the intensity ratio lands where the polarization is. Located by column
it is exactly the second emission line's weight, so a doublet now opens and
comes back with both lines.

Behind that sits the part worth carrying. A `.prm`'s `INS` records and a
`.EXP`'s `HST` records are the same GSAS records under different four-character
keys, and this package was parsing three of them two ways. The corpus hid it.
Every 11-BM file here leaves `IREF` and `IDAMP` blank, so six tokens happened to
land on the right meanings and the reader looked correct, while the one file
that writes `IDAMP` was refused for having seven. The grammar now has one home
and both readers call it.

*Reconstructed post hoc*, from `git log --stat` over the branch's four commits,
their bodies, and the state of the checklist. The session left no entry of its
own. Where the diff does not say why something was done, this entry says so
instead of supplying a reason.

*Done* — four commits on `wp1118-gsas-prm-columns`, merged as PR #332
(`3e759b54`).

- **The grammar** (`c4b20256`). `io/projects/gsas.py` grew
  `GsasIcons`/`read_icons`, `GsasPrcfHeader`/`read_prcf_header` and
  `split_records`, all public and all called by `instrument_profile.py`'s
  `.prm` reader a package away. The coefficient names come from
  `CW_PROFILE_COEFFICIENTS`, the table the `.EXP` reader was already using.
- **The docs** (`e2d2d6d2`). The reader's own docstring described six `ICONS`
  fields read by position and a doublet refused for want of a convention, and
  both had gone false. `docs/manual/using/files.md` gains the doublet and loses
  a sentence saying a GSAS `.EXP` has no reader, which the 1st session had
  already made untrue. The skill's `GSAS_PRM_FIELD_DROPPED` row names the
  fields the column layout identifies, and `references/api.md` now tells an
  agent not to add a Kα2 line after reading one. The addition is staged in the
  v1.4 record. Post-ship work goes there while no milestone is open.
- **The review pass** (`2a96b536`), over three blank fields the column read made
  reachable. A six-token split refused a record missing any field, so no field's
  absence had had an answer of its own. A blank `POLA` was the one that
  mattered. The `Instrument.debye_scherrer` constructor defaults its
  polarization to 0.99 and every real file in the corpus states 0.99, so falling
  back on the default would have put this package's number into an instrument a
  caller reads as the file's. It is refused by name. A blank
  `PRCF1` profile type reached the unrecognised-type refusal and printed `None`,
  and it now says the header states no type. Two diagnostic rows asserted `= 0`
  for fields they had not read, which is the defaulted-field lie one message
  over.
- **The claim** (`46611638`) carried the FAP-freedom decision the 1st session had
  left to the maintainer. The suite keeps its 20 free parameters and keeps
  asserting the difference against GSAS's 28.

*Measured* — the session's own numbers, in the same worktree and `.venv` as
the 1st session, `[dev]` only (no jax, no torch), python 3.12.12, darwin/arm64.

- The four real calibration files here read **bit-identically**: `11bm_gsas.prm`,
  `11bm_lab6_gsas.prm`, `11BM_LaB6_cBN_mg2044.prm` and `mg090.prm`, measured
  against `origin/main`'s module over the whole `model_dump`.
- `INST_XRY.PRM` is refused for its `GP` of 0.1, a stock GSAS placeholder, where
  before it was refused for a token count.
- `tests/test_gsas_prm.py` went 29 → 38 test functions, 12 added and 3 removed.
  The three that went asserted the split reading: the token-count refusal, the
  doublet refusal and the reserved-field refusal. The file collects 40 cases and
  all 40 pass on the merged tree, re-measured 2026-09-16 by the repair above.
- `src/rietx/io/CLAUDE.md`'s cap went 368 → 383, and the file landed at 381.

*Gotchas*

- **The `PRCF` continuation records stay a token read**, deliberately. GSAS
  prints coefficient labels inside the 15-column fields on some files, so
  `11BM_LaB6_cBN_mg2044.prm` is 61 characters where `4E15.6` is 60, and its
  second field reads `     GV -0.1260` by column. Sharpening the rest of the
  reader does not licence sharpening this.
- `tests/data/README.md` had `INST_XRY.PRM`'s `POLA` as 0.5. It is 0.7, and the
  0.5 beside it is `KRATIO`. That pair is the whole reason the file is worth
  keeping, since `FAP.EXP` states only `POLA` and the two are conventionally
  equal.
- The two rules this session put in `io/CLAUDE.md` are aimed at the next project
  reader. Staying outside the registry is about dispatch and never about
  parsing, so one vendor's several file kinds read a record through one
  function. And a refusal's reason can expire, so a parser getting sharper is a
  reason to audit its refusals too.

### 2026-09-15 (1st session) — the GSAS `.EXP` reader, and the protocol it turned out nobody had

Someone handed GSAS's own converged refinement can now open it with one call and
get back the model *and the refine flags* — which parameters that refinement was
free to move. That last part is the whole point, because a CIF carries the
converged coordinates and a raw file carries the pattern, and neither says what
was refined. This repo had been paying the cost itself: the fluorapatite
acceptance suite's cell, seven sites, wavelengths, held Caglioti terms and
excluded region were constants somebody read out of `FAP.EXP` by hand, and
`viz/compare.py` held a second copy of the same numbers. Both now read the file.

Reading the protocol instead of transcribing it immediately found something the
transcription had hidden: **GSAS refined the coordinates and this package's plan
does not**, so the suite whose docstring said "both codes refine the same
parameter set" was refining 20 parameters against GSAS's 28. That is now
asserted as a difference rather than implied as an agreement, and closing it is
measured and cheap — the decision is the maintainer's because it moves two
recorded acceptance numbers.

*Done* — seven commits, `wp1118-gsas-exp-reader`.

- **The reader** (`48c2d105`): `io/projects/gsas.py`, `rx.read_gsas_exp` and its
  `to_structure`. `GsasModel` carries phases, histograms and one entry per
  phase-and-histogram pair, which is where GSAS keeps the profile coefficients.
- **The registry member** (`1b528789`): `gsas_exp` in `PROJECT_FORMATS`, top-level
  exports, the `capabilities()` arm, a Part 1 section over the whole `GsasModel`
  tree, six `GSAS_EXP_*` skill rows, and an `ATTRIBUTION.md` row.
- **The acceptance rewire** (`e419cf4c`), the WP's own stated bar, plus
  `viz/compare.py`'s `fap` standard, which was the second transcription.
- **`FAP.EXP` ships** (`3138217d`) and **the sniff measures bytes** (`d5821955`);
  both are below.

*The three decisions, and what each rules out.*

1. **Every field is read by column, never by splitting on whitespace.** A
   fixed-format record whose optional numeric fields are blank collapses under
   `str.split()` into a shorter list whose entries then mean something else.
   `ICONS` is where it bites: the layout is `LAM1 LAM2 ZERO [IREF] [IDAMP] POLA
   IPOLA KRATIO`, so a file leaving `IREF`/`IDAMP` blank splits into six tokens
   that line up and one writing `IDAMP` splits into seven that do not. **What
   this rules out**: reading any further GSAS record positionally off a split.
2. **Profile coefficients are named per function type.** CW type 2's fourth is
   `LX` and type 3's fourth is `GP`, so one index-to-name map would mis-assign
   every width in the file. A type this build cannot name is **refused by name**
   rather than read positionally — the Bruker `.raw` v3 bar applied to a
   coefficient order. Type 4 is the refused one: the manual describes it only as
   "between 14 and 27 coefficients … `S400`, etc.", which enumerates nothing.
3. **The registry's `reports_at` gained a `"both"`.** It was a two-valued
   `Literal` because the two formats it shipped with each repair at one end. A
   `.EXP` repairs at both, so either single value would have dropped one channel
   **in silence** — the caller gets an empty list, which reads as "this file
   needed no repairs". **What this rules out**: a fourth format declaring one
   end and quietly having two, because the meta-test now partitions both ways.

*Measured* — this worktree's `.venv`, `[dev]` only (no jax, no torch, so the
cross-backend rows self-skip), python 3.12.12, darwin/arm64, nothing else
mid-suite either time (checked with `ps aux | grep`, not `pgrep`):

- Fast selection `-n auto --dist loadgroup -m "not slow"`: **4925 passed, 132
  skipped**, 2:23. The delta is **+35 passed, +0 skipped**, derived per file
  rather than by re-measuring `main` (`tests/CLAUDE.md` rung 4 says not to):
  24 from `test_projects_gsas.py`, 6 from `test_projects_registry.py` (2 dispatch
  rows, 2 new tests, and +1 each on the two meta-tests parametrised over
  `PROJECT_FORMATS`, which went from two members to three), 5 from
  `validation_matrix.py` (one new Claim × five parametrised families).
  `test_example_projects.py` gained a `LICENCES` entry and no test case, and
  the new acceptance row is `slow`-marked so it is outside this selection.
- Full selection, **once, on the final tree**: **5096 passed, 141 skipped**,
  23:28. Run because the change moves the inputs of a real-data acceptance row.
- `tests/test_acceptance_fap.py`, the WP's named acceptance: 3 passed.
- `ruff check src tests examples` clean.
- **The acceptance bar, stated as an identity rather than a tolerance.** The
  recovered protocol reproduces the file's own variable count: 21 structural
  (2 cell + 12 coordinate DOFs + 7 Biso) + 1 scale + 3 background + 3 profile =
  **28**, and `REFN GDNFT` says 28 in a record the reader never consults. The
  flags are spread over eleven records, so no single-field misreading survives
  that row.
- **The measured answer is unmoved.** Over the seven quantities the suite
  reports, the largest relative change is **5.3e-10** (`lor_size`), with Rwp at
  3.4e-14 and the cell at 2.6e-13 — solver termination noise from starting at
  the file's 9.371724 and 0.0335183 rather than the rounded 9.3717 and 0.0335.
  The Caglioti terms did not move at all: `1e-2**2 == 1e-4` exactly in IEEE754,
  so the centidegree conversion returns the same doubles the constants were.

*The review pass found ten things and the first of them was the bug this
reader exists to prevent.* `_continuation` appended only the values `_num` could
parse, so one unreadable coefficient field **compacted the list and renamed
every later coefficient**. Fortran writes a three-digit exponent with no `E`
(`0.200000-100`), which Python will not parse. Reproduced against the pre-fix
code, a six-coefficient function-2 block came back `GU=2.0, GV=5.0,
GW=3.35183, LX=2.48803, LY=0.0` — five plausible numbers, each under the wrong
name, nothing raised. Naming coefficients per function type cannot help once the
*values* have shifted under the names, so the careful part of this reader was
guarding one end of a hazard that came in at the other. Two siblings of the same
shape are now refusals too: a header declaring more coefficients than its records
carry, and a blank numeric field reaching a `float`-annotated model field as
`None`. The rest were smaller — `EXPR HTYP<n>` record numbers ignored (a file
with more than twelve histograms overwrote histogram 1 with record 2's type), the
HAP and histogram gates disagreeing about single-crystal data because `SXC`'s
third letter is `C`, `str.splitlines()` breaking on `\x85` where the
byte-measuring sniff does not, gemmi's space-group error escaping unwrapped, and
two stale docstrings plus `io/CLAUDE.md`'s `reports_at` bullet. Nothing was
declined; nine tests came with them.

*In flight*: nothing. The branch is one session's work and complete.

*Gotchas*:

- **The manual contradicts itself twice, and both would have shipped a plausible
  wrong number rather than an error.** The CW function 2 paragraph lists its
  eighteen coefficients twice, as physics symbols and as GSAS names, and the two
  are **transposed at positions 8 and 9**; GSAS's own EXPEDT listing prints
  `#8(shft)` and this file's converged sample displacement sits at index 8, and
  function 3's two tuples agree, which is what shows it to be a slip. And
  `CELVOL` is `2F15.3` in every file here against a printed `2F10.3`, which at
  the printed width reads 523.755 as **52.0**. Both are in the module docstring
  and asserted by test. `RPOWD` also carries undocumented fields past its
  declared `2F10.4`; those are **not** read, and the observation count comes
  from `REFN STATS`, which the manual does declare.
- **Polarization and a Kα2/Kα1 ratio are both conventionally 0.5, and they sit
  in adjacent fields on one record.** `FAP.EXP` states POLA and leaves KRATIO
  blank; the old test comment attributed that 0.5 to the ratio. What fixed the
  order is `INST_XRY.PRM` beside it, which states POLA 0.7 *and* KRATIO 0.5 in
  the same slots. A reader that took the wrong field would agree with the right
  one on this file and disagree on the next.
- **Adding a file to a `Standard` can remove an example project.** WP-1204's
  sentence is "adding a file adds an example", and `Standard.available` reads it
  backwards too: making the `fap` standard read `FAP.EXP` put that file in
  `Standard.files`, which is not in the wheel, so `fap` silently stopped being an
  example and **five tests went red in three suites that have nothing to do with
  this reader** — both GUI example-server rows, two example rows, a peak-picking
  panel, and the manual's indexing chapter, whose python block calls
  `build_example("fap", …)`. Shipping the file is the same licence answer
  `FAP.XRA` already has.
- **The head decode drops bytes, so the sniff measures bytes.** `head()` decodes
  UTF-8 with `errors="ignore"`, and a `.EXP` is a Latin-1 byte format whose
  `DESCR` title is whatever the experimenter typed. One accented character
  shortens that record to 79 characters in the decoded text while it is still 80
  bytes on disk, and the width half of the sniff then rejects the whole file.
  Found by reading the shared decoder, not by a failing file; the guard was
  checked the way `tests/CLAUDE.md` asks, with the byte version passing and the
  text version it replaced failing on the same fixture.
- **GSAS's `X` flag means "refine as permitted by symmetry".** Carried onto
  `x`/`y`/`z` directly it makes `ParameterTable` refuse the whole import of a
  file GSAS refined happily, because fluorapatite's F4 sits on a zero-freedom
  special position with its flag set. It goes through the site-symmetry basis
  GSAS was speaking about instead.
- **An anisotropic site reads but refuses to build.** The six `UIJ` values are on
  the model; which off-diagonal convention they follow is settled by no file
  here, and a wrong factor of two is a silently wrong Debye-Waller factor at high
  Q. Same refusal `fullprof.to_structure` makes about a `β` block, and it lifts
  the same way — with a corroborating file.
- **The `.pcr` species normaliser is imported from `fullprof`, which is the third
  caller of it.** It is not a format fact and its own docstring says it exists to
  give every project reader one spelling, so the import is deliberate rather than
  a shortcut; a shared home for it is the obvious tidy-up and was left alone to
  keep this diff on the new reader.

*Next*, in order:

1. **Decide whether this suite adopts GSAS's coordinate freedom** — the one
   question this work raised and did not answer. Measured 2026-09-15: adding a
   coordinate stage takes Rwp 0.096966 → 0.096677, moves the cell by 0.1 ppm,
   costs no wall clock and still converges. So it is nearly free and changes no
   conclusion, but it moves two recorded acceptance numbers (the headline Rwp,
   and the "20 → 18 free parameters" table in
   `test_tying_the_similar_atoms_bisos_buys_precision`), which is why it is a
   deliberate change rather than something to slip in.
2. **`read_gsas_prm` reads the same `ICONS` record by whitespace split.** It is
   correct on its corpus only because those files leave `IREF` and `IDAMP` blank,
   so the six tokens happen to line up; it **refuses `INST_XRY.PRM`**, a file in
   this repo, for having seven. The failure is safe rather than silent, which is
   good design, but the two readers now read one record two ways and that is the
   thing this codebase most dislikes. Reading it by column would fix the class.
   It would not by itself make that file readable — the reader also refuses a
   doublet, and a `.EXP` is what could now establish the intensity-weight
   convention it says no file gives it.
3. **The `STR(...)` decision** — issue #107, still offered by its filer, and 1119
   settled that it needs no expression language.

The `.gpx` reader (#234), the writers (#148) and the `#if` evaluator are all
larger and none is blocked, so they wait on someone choosing them.

### 2026-09-13 — the registry, and the question it had to answer first

Someone handed another program's refinement file can now open it with one call.
`rx.read_project_model("whatever.inp")` works out from the file's contents which
program wrote it, reads it, and hands back what the file said plus a
`.to_structure()` carrying the file's own refine flags. Before today the two
readers that could do this existed but were reachable only by importing them by
name, and `rx.capabilities()` did not mention them, so nothing could ask what
this build opens. The part that needed deciding was not the plumbing: it was what
the registry is *for*. Four readers in this package open a foreign file, they do
not answer the same question, and forcing them into one shape would have meant a
model with a blank where a file simply had nothing to say — which reads as an
answer. The decision taken is that the registry's unit is a **refinement**, and
two of the four stay outside it with the reason written down rather than left to
be inferred.

*Done* — six commits, `wp1118-model-format-registry`.

- **The mailbox pruned first** (`3a7f57a7`). Eight `### Inherited` entries folded
  into Context, Seams and Tasks and the section deleted. Three had gone stale in
  the ten days since the file was last edited, and the worst of them was stale in
  the reassuring direction: WP-1308, PR #98 and WP-1330 all warn that `SKILL.md`
  has 27, 32 or 36 bytes of headroom and that a routing row must be bought with a
  cut. Measured today it has **1 597 B** free, because WP-1103 and #284 cut the
  body after those notes were written. `references/api.md` § In had likewise
  stopped being false — it already named both readers. The third was an omission
  rather than a rot: `rx.read_gsas_prm` (PR #248) had landed as a *third reader
  kind* and the registry task did not carry it.
- **The registry** (`5ba04e58`): `io/projects/registry.py` with `ProjectFormat`,
  `ProjectModel`, an ordered `PROJECT_FORMATS`, `identify_project_format` and
  `read_project_model`; top-level exports for all of it plus `rx.read_topas_inp`
  and `rx.read_fullprof_pcr`; a `capabilities().project_formats` arm with the
  membership meta-test `reader_formats` is held to; `io/CLAUDE.md` § Project
  readers +3 rules (cap 350 → 368, argued); a Part 1 chapter; and the skill's
  routing row and § In.
- **The read's reports made durable** (`5e85b7d5`), found reviewing the commit
  before it — below.
- Two prose corrections and an encoding fix.

*The three decisions, and what each rules out.*

1. **The unit is a refinement, not a foreign file.** `read_gsas_prm` carries a
   machine and no model at all — no phases, no sites, no fitted numbers — so it
   stays beside `load_instrument_profile`, which is the argument its own merge
   made and the organising question the 09-10 entry recorded as raised and
   unanswered. `read_recipe` is a refinement but resolves to something ready to
   fit and is a build-wide feature. A pattern is the other registry's. Admitting
   any of them would empty every field this registry declares about a model, on
   one member. **What this rules out**: a future reader is placed by asking "does
   this file state a refinement" before it is written, not after it has a home.
2. **The answer is the format's own model, tagged.** `ProjectModel` names the
   format and hands on `TopasModel`/`FullProfModel` untouched. A shared shape
   would need an optional field wherever a format is silent, and a caller could
   not tell "this file carried none" from "the reader found none" — WP-1076 one
   registry over. What each format carries beyond a structure is declared in
   words (`ProjectFormat.carries`) so a client asks instead of reading `None` and
   guessing, and the conversion keywords pass through rather than being flattened
   into one vocabulary, since two formats' options sharing a name would not share
   a meaning.
3. **Dispatch is on content, never the suffix.** `.inp` is written by unrelated
   programs — WP-1407's rule one rank up, that a file extension does not name a
   format here. FullProf goes first because `COMM` is a line the format
   *requires*; TOPAS's evidence is a line-start keyword in a 64 kB head, the
   weaker test, and the order is that difference. The `.inp` sniff runs the head
   through the reader's **own** `strip_comments`, so a commented-out `xdd` is not
   a statement and the sniff is not a second grammar to keep in step.

*Measured* — worktree `.venv`, `[dev]` only (no jax, no torch, so the
cross-backend rows self-skip), python 3.12.12, darwin/arm64, `pgrep` clean both
times:

- Fast selection `-n auto --dist loadgroup -m "not slow"`: **4632 passed, 132
  skipped**, ~2:05-2:08 (three runs, 124.7 s / 127.6 s / 128.3 s; the first is
  the final tree). The delta is **+24 passed, +0 skipped** —
  `tests/test_projects_registry.py` collects 24 and every one passes; no other
  file's collection moved, `test_capabilities.py`'s edit being one assertion
  inside an existing test.
- `tests/test_acceptance_fap.py`, the WP's named acceptance: 2 passed.
- `ruff check src tests examples` clean; `sphinx -W` clean.
- **The full suite did not run**, and deliberately: `tests/CLAUDE.md`'s rung 3
  fires only when a change can move a measured number, and nothing here touches
  the forward model, the solver or the statistics. The FAP acceptance was run
  anyway because this WP names it.
- **Import cost, since `import rietx` now pulls in two ~2 500-line parsers**:
  `rietx.io.projects` is **13.1 ms cumulative** of a 535–663 ms total (three
  runs), about 2 %. `scipy.signal`, reached through `rietx.background`, is 274 ms
  of the same total. Not worth a lazy-import mechanism the package does not have
  for any other export; recorded so the next reader added knows what it costs.

*In flight*: nothing. The branch is one session's work and complete.

*Gotchas*:

- **The asymmetry in `reports_at` was very nearly a trap, and the review caught
  it two screens from a test arguing against it.** A `.inp` reports its repairs
  while parsing and a `.pcr` while codewords become a `Structure`, so the first
  design routed the caller's list on that flag — and silently dropped it when a
  caller passed one to `to_structure` on a `.inp`. They got an empty list back,
  which reads as "this file needed no repairs". The fix is `Recipe`'s: the read
  reports into a list of the front door's own, lands on
  `ProjectModel.diagnostics` whether or not anyone asked, and a caller's list is
  **extended** from it rather than handed to the reader, so it stays the caller's
  own object. The general shape to watch for: a per-format flag that routes a
  caller's channel is a place where being wrong is silent.
- **Two declared names have no writer among the members, and the review was
  right to say so out loud.** `ProjectFormat.refuses` is `None` on both, because
  neither is a recognise-in-order-to-decline format — so the `if f.refuses is
  None` filter it exists for was unreachable. `ProjectModel.diagnostics` is
  always `()` for `fullprof_pcr`, whose read has no channel at all, so a
  format-agnostic caller writing `if model.diagnostics:` is silent on every
  `.pcr` however much it repaired. Neither is WP-1076's defaulted `False` — both
  are the honest empty state — but both were claims resting on a docstring. Now:
  the docstring says which formats an empty tuple means anything about, and the
  filter is exercised against a stub member that sets `refuses`, rather than
  asserted from the table and believed.
- **`.inp` and `.pcr` fixtures cannot be vendored, so the `.pcr` ones are
  `test_projects_fullprof`'s builders imported.** A second fixture writer for one
  format is a second description of its layout, and the two would drift on
  exactly the 19-field control line that format refuses a file over — which it
  did, on the first run, against a hand-written 18-field one.
- **The WP file read at session start was three days stale.** `/wp-start` reads
  the WP file in step 2 and enters the worktree in step 3, so the read comes from
  the main checkout — which was six merges behind `origin/main`, and missing the
  09-10 entry recording PR #248. Reconciled by re-reading from the worktree. The
  cheap habit: after `EnterWorktree`, re-read the WP file.
- **The review pass found six things, four of which it fixed, and the two it
  left were both worth acting on.** The one that mattered: `_TOPAS_LINE`
  *restated* the grammar's opener tuple instead of reading it, so an opener
  added to `topas._BLOCK_OPENERS` would keep parsing through `read_topas_inp`
  while `read_project_model` answered "not a refinement file this build can
  read" — drift in one direction and in silence. The alternation is now built
  from that tuple (verified byte-identical to the literal it replaced), with
  `STR` the one member taken out and spelled `STR(`. Also fixed: the binary
  hint on the refusal, matching `identify_format`; the `diagnostics` docstring;
  and a manual sentence claiming the sniff decides "without reading" a file it
  reads 64 kB of. Of the two left to me, the partial-diagnostics one turned out
  to be a docstring claiming a parity it did not keep — `read_pattern` hands its
  list straight down, so a read that repairs and then refuses keeps what it
  repaired, and this door copied only on success. Fixed with a `finally`, and
  **no reader in this build can reach the case today** (every TOPAS diagnostic is
  appended after its last raise, and FullProf reports at build), so it is tested
  through a stub member at the door where the promise lives.
- **Two documentation gates fired on this work and both were right.**
  `test_manual_api.py` put 90 public names in no bucket, which is what made
  `rietx.io.projects` a declared-provisional module (the WP-1078 mechanism —
  honest here, since the registry landed with two formats and three queued) and
  bought the Part 1 chapter. `test_skill.py` demanded the four new verbs in
  `make_api_index.py`'s `SECTIONS`. Neither would have fired had the readers
  stayed off the top level, which is the argument for putting them there.

*Next*, in order:

1. **The GSAS `.EXP` reader** — issue #103, whose filer volunteered for it once
   the registry shape landed, and it has. They bring two spec findings for its
   docstring (GSAS-II's `Rvals['GOF']` is reduced χ² rather than its root;
   instrument parameters are `[default, current, refine_flag]` triples, current
   at index 1). It is the task with a fixture already in the repo — `FAP.EXP` is
   GSAS's converged fluorapatite fit — so it is also what lets
   `test_acceptance_fap.py` take its protocol from a reader instead of from
   transcribed constants, which is this WP's stated acceptance.
2. **The `STR(...)` decision** — issue #107, whose filer offered either fix once
   told which. 1119 settled that it needs no expression language, so it is a
   `.inp` grammar question living entirely in `io/projects/topas.py`.
3. **The `#if` evaluator**, newly a task line: three of four workshop `.inp`s
   refuse at their first `#if`, and those are the multi-pattern reel files
   WP-1110's agent round named as the hardest part of the work.

The writers (#148) and the `.gpx` reader (#234, its reporter's offer standing)
are both larger and neither is blocked, so they wait on someone choosing them
rather than on anything here.

### 2026-09-10 — the `.PRM` half of the GSAS task landed from outside (PR #248)

Merged in a `/pr-review all` pass, not a WP session; this entry exists because
an outside contributor has no reason to prefix a commit `WP-1118:` or to edit
this file, so nothing would otherwise have recorded it. PR #248
(`ff69ec34`) adds `read_gsas_prm` in `src/rietx/io/instrument_profile.py`,
a new top-level export, `docs/manual/using/files.md` prose, two diagnostic codes
with their skill rows, and 609 lines of tests.

**What it makes possible.** An `INST_XRY.PRM`-shaped GSAS-I instrument-parameter
file now becomes an `Instrument` without transcription. That is the first half of
the `.EXP`/`.PRM` task above and the half that unblocks the *protocol* argument:
`tests/data/INST_XRY.PRM` is in the repo already, so the FAP acceptance suite's
wavelength and profile constants can start coming from the reader rather than
from constants typed out of the file.

**What it deliberately does not do.** No `.EXP` reader — the converged fit,
the vary set and the excluded regions are still transcribed, so the task line
stays unticked. It is not wired into the model-format registry (which does not
exist yet, and is this WP's first unticked item), and it is neither a
`PATTERN_FORMATS` entry nor an `io/projects/` project reader: it is a third
reader kind with no registry of its own.

**What the review established, and the gotchas.**

- The io rulebook's hardest clauses are met and I verified each: every refusal
  names the file rather than leaking a `float()` exception; the unit is measured
  three independent ways against the format's own reference output rather than
  taken from LAUR 86-748's prose; and the `ZERO` field, which the format states
  two ways, is **refused rather than chosen** — the same disposition a CIF whose
  angle contradicts its symbol gets. Drift is refused (`GP`, the reserved
  coefficients, `ALAM2`, `ZERO`, the reserved `ICONS` field), identity-valued
  drops are reported (`GSAS_PRM_FIELD_DROPPED`), and everything frozen carries
  `vary=False`.
- **An organising question this raises and does not answer**: `io/CLAUDE.md`'s
  "one module per format" is scoped by its own first line to the *pattern*
  readers, so it does not govern this reader — but the reason behind it does,
  and `instrument_profile.py` now carries two formats' fences (the native JSON
  `FORMAT_KEY`/`FORMAT_VERSION` and GSAS-I's spec citation and refusal tables).
  Whether the third reader kind gets its own module rule, or its own registry
  alongside `PATTERN_FORMATS` and `io/projects/`, is open and is the thing the
  registry item above should settle. Raised with the maintainer at merge; no
  decision taken.
- Measured on the merged tree, bench venv `[dev,jax]`, macOS arm64, four cores,
  alone: `tests/test_gsas_prm.py` + `test_acceptance_wavelength.py` +
  `test_skill.py` + `test_manual_api.py` — 91 passed, ~24 s; the fast selection
  4353 passed / 78 skipped, ~2.5 min; ruff clean. The full `-m slow` suite ran
  once on a combined tree carrying this and seven other PRs.

### 2026-09-03 — the `.gpx` fence lifted, behind a restricted unpickler

The maintainer decided issue #234: a GSAS-II `.gpx` reader is in scope, built
on a `pickle.Unpickler` whose `find_class` admits an allow-list and refuses
every other name. The Non-goals bullet that fenced it out for a reason
measured false is rewritten, the task is on the list with the measured
allow-list and the corpus-widening caveat, and the reporter's offer to
implement it stands. Nothing else in this WP moved. Next action: the
contributor's PR, or the next session on this WP, builds the reader against
the widened corpus.

### 2026-09-03 — the FullProf `.pcr` reader landed (PR #111)

A FullProf `.pcr` control file now opens the same way a TOPAS `.inp` does.
`rietx.io.projects.read_fullprof_pcr` returns what the file states — phases,
cell, sites, displacement parameters, the magnetic blocks, the run's own
agreement figures — and `projects.fullprof.to_structure` builds a `Structure`
from it carrying the **file's own refine flags**, decoded out of FullProf's
`10·n + multiplier` codewords. The codeword is the whole point of the format for
this WP's purpose: it is where a `.pcr` records both *which* parameters were
refined and *which of them moved together*, and neither is recoverable from a
CIF plus a pattern. Where a tie is one rietx already carries — a single atom's
coordinates following its own site-symmetry DOF — it is reproduced; where it is
not, the reader says so by name rather than dropping it, and says whether the
reader could restore it with one `Refinement.tie_equal` call. The other format
is unmoved: `.EXP`/`.PRM` still has no reader, and there is still no writer in
any direction.

*Reviewed, not written, in this session.* PR #111 ran six review rounds on the
`/pr-review` bench between 2026-08-26 and 2026-09-03 (the PR opened 2026-08-24); this entry is written at
the merge, from those rounds and from the merged tree, and is the handover the
step-9 clause added by the 2026-09-02 repair session says a contributor's
`WP-NNNN:` commits owe.

*Done* — all of it PR #111 (`mustachefeeling/fullprof-pcr-reader`, head `a99ce2ef`), merged
2026-09-03 as `b717cc98`, +4462/−35 across 14 files:

- `src/rietx/io/projects/fullprof.py` (2326 lines) — the reader. The package
  `__init__` gains `read_fullprof_pcr` and `FullProfPcrError` and nothing else;
  `to_structure` stays module-level, which is the shape #98 chose so the two
  formats' conversions cannot shadow each other through the package export.
- The answer's shape, matching the TOPAS reader's: `FullProfModel` is *what the
  file states*, `to_structure(model, *, nuclear_only=False,
  drop_parameter_ties=False, diagnostics=None)` is the conversion. `Biso` is
  FullProf's B and rietx's `biso` is also B — no 8π² conversion — and
  `species_raw` sits beside `species` on every `FullProfAtom`, so the spelling
  repair is checkable against the file structurally, not only through a
  diagnostic.
- **53 refusals, each naming file and line** through `FullProfPcrError`
  (a `ValueError`, so `io/CLAUDE.md`'s "raise naming the file, never the
  parser's exception" holds). The reader handles the single-pattern
  constant-wavelength layout completely and refuses the rest by name.
- Four diagnostics, each with a row in all three synced skill copies:
  `FULLPROF_SPECIES_NORMALISED`, `FULLPROF_ORIGIN_CHOICE`,
  `FULLPROF_OCCUPANCY_UNCHECKED`, `FULLPROF_TIE_DROPPED`. The skill's
  `references/diagnostics.md` was over its own cap on `main` (35 914 of 36 000
  B); this PR splits the project-reader codes out into
  `references/diagnostics-projects.md`, taking that file to 32 125 B and the new
  one to 10 273 B. **That split is what buys `diagnostics.md` its next few
  years, and it is an argument for landing this PR that has nothing to do with
  FullProf.**
- `tests/test_projects_fullprof.py` (1934 lines, 85 tests) — every fixture
  synthesized inline, because no real `.pcr` may be vendored, and every line in
  them quoted in a comment from a named archive file and line.
- `tests/data/README.md` — the six-file corpus section, which is the only place
  the real-file evidence is checkable, plus **two limits recorded rather than
  smoothed over**: the corpus contains no cross-atom tie at all, and its cell
  ties are tetragonal and cubic only. Both are why the corresponding rules are
  derived from symmetry and from what a restoring call can express, rather than
  from what six files happen to contain.
- `ATTRIBUTION.md` — one row. FullProf is closed and no FullProf source was
  consulted; the format's facts come from six real archive files plus
  Rodríguez-Carvajal's manual and the ILL school notes already cited. No `.pcr`
  is vendored and nothing enters `src/rietx/data/`, so the wheel's licence fence
  is not reached.

*Measured* (merged tree `a99ce2ef` onto `origin/main` `b2ab4950`, a
fast-forward, so CI measured the same tree; `/pr-review` bench `.venv`
`[dev,jax]`, python 3.12.12, darwin/arm64, nothing else running): the **full
suite**, `-n auto --dist loadgroup` with no marker, is **4452 passed, 80
skipped** in 35m21s. `ruff check src tests examples` clean. The fast selection
was not run separately and no collection delta is quoted here — the full run
covers it, and round six's `+139` was measured against a `main` that has since
moved.

The full suite was run **once, on the final tree**, and that tree is the one
that merged: after the contributor's force-push (below) the merged commit's
tree object was compared against the tested one and they are the same object,
`b2dc6a8f22ee59ab1ff2bb89535c9a8f4d5db79f`, so no re-run was owed.

*In flight*: nothing of this WP. PR #111 was the last open contributor PR
against it.

*Gotchas*:

- **A coordinate tie is restored through the DOF path, not the column path.**
  `atom_tie_recoverability` says whether `FULLPROF_TIE_DROPPED`'s group can be
  re-declared, and the call it needs is `tie_equal` on
  `phases.i.atoms.j.dof.k` for a coordinate group but on the column path
  (`.biso`, `.occ`) for a Biso or Occ group — because a coordinate column
  already follows its own dof by site symmetry, and root `CLAUDE.md`'s
  "symmetry outranks a user tie" makes `tie_equal` on `.z` **refuse**. The
  diagnostic's message named the column spelling on both arms until round five;
  it now names the DOF spelling where that is what works, and the skill row
  carries the raising example so a driving agent meets the refusal before it
  hits it.
- **The split is derived from what a restoring call can express, never from the
  corpus.** All six archive files contain single-atom ties only, so the corpus
  reaches neither arm of the report-versus-refuse decision. A rule inferred
  from it would have been an accident. The same reasoning made
  `cell_parameter_ties` ask `crystallography.symmetry.cell_constraints` rather
  than trust incidence: the archive's cell ties are tetragonal and cubic only,
  where the space group masks the defect — exactly the limit
  `TOPAS_CELL_COUPLING_DROPPED` hit the sibling reader over, for the same
  reason.
- **A `.pcr`'s own comments lie, in two ways, and the parser trusts neither.**
  A column's `!` header text changes with `Jbt` (`Ang` and `Mom` share a
  column), so header text is discarded before the walk and the reader keys on
  position; and a phase's inline `!Phase No.` can disagree with block order, so
  the reader counts blocks. A parser keyed on the header breaks on exactly the
  magnetic phase.
- **`ATZ` and `Pr3` are quantities, not counts.** Reading the phase-control
  line with `cur.ints()` throughout would refuse every real file — hence
  `_PHASE_INTEGER_FIELDS` naming which columns are integers.
- **A negative `Biso` is a real FullProf outcome, and it is refused rather than
  repaired.** One archive file carries O1 at −0.67266 Å². rietx's zero bound
  cannot clamp it without changing every high-Q intensity, so the file is
  refused by name; this is the `io/` rule that a reader may repair only where
  it can say what it did, applied where the repair would not be sayable.
- **FullProf's `Occ` is degenerate with the phase scale**, so only the *ratio*
  between sites is recoverable and a phase whose ratios disagree is refused.
  That ratio test does double duty: it is also what *verifies* the origin-choice
  preference for a bare symbol (`F D -3 M` → `F d -3 m:2`) rather than trusting
  it.
- **A magnetic phase reads but does not build.** Present alongside nuclear
  phases, `to_structure` refuses rather than returning the nuclear subset
  silently.
- **The skill's caps are now a live constraint, and a merge can cross one that
  neither branch crossed.** `references/diagnostics.md` sat at 35 914 of 36 000
  B on `main` before this PR's split. Two additions can each be under a cap
  while their merge is over it, and branch protection here is `strict: false`,
  so nothing but a review on the merged tree ever measures that — seen for real
  on #233 the same week.

- **A contributor's commit identity is a merge gate, and nothing checks it.**
  `58efff0a` on this branch ("merge main") was authored `m <m@m>` from a
  misconfigured local `user.email`. GitHub attributes a commit to whoever owns
  the address, `m@m` is verified on a **real and unrelated account**, and that
  account was therefore listed among this PR's participants. It was caught at
  review and fixed by a rebase before the merge; `main` had never carried the
  address, and after the force-push the branch is 11 commits under one
  identity. Two things make this worth a rule rather than an anecdote. It is
  **invisible to every check we run** — CI, `ruff`, the suite and branch
  protection are all indifferent to authorship, and the GitHub UI shows the
  contributor's avatar on the PR while the commit underneath carries someone
  else. And it is **cheap before the merge and expensive after**: removing it
  from `main` would mean rewriting merged history behind the two protection
  toggles only the maintainer can operate. So a `/pr-review` pass over an
  outside PR should read `.commit.author.email` and the **resolved**
  `.author.login` per commit, not the PR's author field. A second failure mode
  sits beside it and reads the same way in the UI: an address that is not
  verified on the contributor's account resolves to **nobody**, so the work
  lands on `main` credited to no one — four commits across #111 and #233 were
  in that state, and the fix there is verifying the email, not rewriting
  anything.
- **`SKILL.md` came out of this with 11 bytes of headroom** — 32 989 B against
  `test_skill.py`'s 33 000 cap, because #242 landed in the body while this
  branch was in flight. This PR's `diagnostics.md` split fixes the *references*
  side and buys that file years; the body itself now has room for nothing, and
  the next addition to it needs the same treatment first.

*Next*: unchanged — the **registry-shape task** is still the single gate on the
`.EXP`/`.PRM` offer (#103), the `STR(...)` decision (#107) and
[1314](1314-mfile-reader.md)'s Jana reader, and still settles whether
`read_topas_inp` and `read_fullprof_pcr` become top-level exports with a
`capabilities()` arm. Two of the three readers now exist, which makes the
registry's shape a question with two real instances to answer it rather than
one.

### 2026-09-01 (2nd session) — the TOPAS `.inp` reader landed (PR #98, reconstructed post hoc)

A TOPAS `.inp` no longer has to be transcribed by hand.
`rietx.io.projects.read_topas_inp` opens one and returns what the file states —
phases, cells, sites, ADPs, the emission profile, the run's own Rwp/GoF — and
`projects.topas.to_structure` builds a `Structure` from it that carries the
**file's own refine flags**, which is the half nobody can reconstruct from a CIF
plus a pattern. What the reader will not do is guess: every construct of the
format declares a stance in a table, so a keyword nobody wrote a branch for
fails a test rather than vanishing, and a file whose phases cannot be honoured
without it is refused by name instead of returned half-built. That table is what
nine review rounds bought — each round found one more construct being dropped in
silence, which is a property of the reader's structure and not of the nine
constructs, so the tenth is now a row rather than a round. The other two formats
are unmoved: `.EXP`/`.PRM` and `.pcr` still have no merged reader, and there is
still no writer in any direction.

*Reconstructed post hoc.* Written from `git log --stat` over PR #98's 46 commits
(`a3268cd1`..`03179f2a`, merged `0576726f`) and the state of the tree they left.
The review ran on the `/pr-review` bench, which writes no handover entry, so
what follows is what the commits show; where the diff does not say why, this
entry does not invent a reason.

*Done* — all of it PR #98 (`mustachefeeling/topas-inp-reader`), merged
2026-09-01, +6078/−1 across 11 files:

- `src/rietx/io/projects/` — a package for readers of someone else's *refinement
  input*, beside `io/formats/`, one module per format. The package `__init__`
  exports `read_topas_inp` and `TopasInpError` only, out of `topas.py`'s 2668
  lines; `to_structure` stays module-level so #111's FullProf `to_structure`
  has nothing to shadow through the package export.
- The answer's shape, for this format: `TopasModel` is *what the file states*
  and seeds nothing (a site with no `beq` carries `None`, not 0.5), and
  `to_structure(model, *, cell_limits=True, aniso=False, dataset=None)` is the
  conversion, applying `TopasPhase.vary` / `TopasSite.vary` onto each
  `rx.Parameter(vary=…)`. `vary` is a **tri-state**: a key absent means the file
  said nothing, which is not "held".
- `coverage.py` (360 lines) — one declared stance per construct, `READ` /
  `IGNORED` / `REPORTED` / `REFUSED` (6 / 3 / 9 / 5, 23 `FEATURES` rows over a
  178-keyword `PHASE_SCOPE`), partitioned by test against the reference's own
  §5.1 phase tree, so a keyword with no stance fails and a stance naming a
  keyword outside the scope fails too.
- Six diagnostics, each with a row in all three synced skill copies:
  `TOPAS_SPECIES_NORMALISED`, `TOPAS_ORIGIN_TRANSLATED`, `TOPAS_BLOCK_SKIPPED`,
  `TOPAS_CELL_COUPLING_DROPPED`, `TOPAS_FEATURES_NOT_IMPORTED`,
  `TOPAS_FEATURE_REFUSED`.
- `src/rietx/io/CLAUDE.md` § Project readers (+29) — two standing rules: derive
  the obligations from the specification and use files only to corroborate (three
  of the six grammar corrections here are invisible to any archive sweep — a
  parameter's *name* is its refine flag, a block comment *nests*, a conditional
  is a token not a line); and a project reader **refuses** where a pattern
  reader would repair, four classes by name, with `to_structure(model,
  dataset=N)` following `read_pattern`'s `scan=` rather than concatenating.
- `ATTRIBUTION.md` — the `.inp` row, citing the Technical Reference section by
  section and each supported cell macro on its own line, recording that the
  606-file private archive is corroboration only and is not redistributable.
  `tests/data/README.md` (+54) holds the archive facts against the file each was
  read off.
- `tests/test_projects_topas.py` — 159 tests, every fixture synthesized inline
  because no `.inp` may be vendored.

*Measured* (this handover session, macOS darwin 25.5.0, worktree `.venv`
python 3.12, `[dev]` extras — no jax/torch, so the cross-backend rows self-skip):
`-m "not slow"` is **3919 passed, 122 skipped**, in the 2-3 min band this
selection runs in on this machine (two runs, 125 s and 156 s). That was
measured on `origin/main` itself — the branch is that commit plus
documentation, and this handover adds no test — so it is the merged tree's
count. The full selection was
not run: nothing here can move an acceptance number, and the reader carries no
physics.

*In flight*: PR #111 — the FullProf `.pcr` reader, same contributor — is open
with 9 commits, head `71fb7094`. Its review has already produced
`FULLPROF_TIE_DROPPED` and the decision to analyse a cell codeword tie against
symmetry rather than against corpus incidence. **Nothing of it is merged**, and
its commits are reachable only through the PR ref, not through any local branch.

*Gotchas*:

- **`STR(...)` is refused by name, not supported** (#107). The line-based
  split still cannot see a phase opened with the macro form, but PR #98 took
  the minimum honest fix with it (`_STR_MACRO`, `topas.py:1866`; the test
  names seven affected archive files — `rigidb`, `split_fum`, `SPODI`, `D20`
  and three `AT027-23_*`): such a file raises `TopasInpError` counting the
  phases it states, rather than returning zero. Those files therefore parse
  not at all, so PR #98's incidence figures are still **floors**, and what is
  parked at the registry-shape task is only *whether* the macro is read — a
  special case or a general macro pass. The Context section above was written
  before this merge and said the file still got the wrong diagnosis; this
  handover corrected it in place.
- **The skill now contradicts the build.** `references/api.md` § In still reads
  "a TOPAS `.inp` … has none, so those are still transcribed by hand", and
  `SKILL.md`'s routing row for *you were handed another program's input file*
  still names only a PowderLine recipe. Both are false as of this merge. The fix
  is WP-1308's Inherited note above, still unspent: SKILL.md measures 31 968 B
  against its 32 000 B cap — 32 B of headroom, not the 27 B that note quotes —
  so widening the row costs bytes bought elsewhere, and three copies
  (`docs/skill/`, `.agents/skills/`, `.claude/skills/`) must stay in sync.
- **No registry and no `capabilities()` arm.** There is no `PROJECT_FORMATS`
  beside `PATTERN_FORMATS`; the reader is found by importing it. The meta-test
  that fails on a registry member missing from its arm therefore has nothing to
  check yet.
- `read_topas_inp` is not a top-level `rx.` export, so `tests/test_skill.py`'s
  public-verb gate never fired for it and `docs/skill/make_api_index.py` carries
  no row. Whether it *should* be top-level is part of the answer's-shape task,
  not an oversight to patch.
- No Part 1 manual section for the reader.
- **This handover was owed and nothing flagged it.** 45 `WP-1118:` commits (of
  the PR's 46) merged with the WP file untouched, and `session_start.py`
  compares the newest handover-entry date against the commits' — the same
  day's issue-triage session
  had touched the file, so the date rule passed. A `/pr-review` merge writes no
  handover entry by design, so a contributor PR carrying a WP prefix is the one
  shape of work this repo can land with no record on the WP. **Closed in
  `.claude/commands/pr-review.md`** (this session, after the entry above was
  written): the triage call now reads `commits[].messageHeadline`, which is the
  only place that shape is visible at all — rank 1 batches such a PR when the WP
  is in flight, and step 9 makes the handover entry part of the merge
  disposition rather than a later session's archaeology. The scan is unchanged
  and still cannot ask for the entry; what changed is that the run holding the
  reading is now the one that writes it.
- Name audit, for the classes no test catches: all six diagnostic codes have
  skill rows, all four `Stance` members have writers in the table, the reader
  adds no physics (so no Part 2 equation is owed) and claims no Rwp comparison
  as evidence.

*Next*: the **registry-shape task**, which is now the single gate on three other
pieces of work — the `STR(...)` decision (#107), the `.EXP`/`.PRM` offer (#103)
and [1314](1314-mfile-reader.md)'s Jana reader — and which also settles whether
`read_topas_inp` becomes a top-level export with a `capabilities()` arm. Then
the skill correction above: small, independent of the registry, and currently
telling an agent to transcribe by hand a file the build can open.

### 2026-09-01 (1st session) — the issue triage folded four issues in

The issue triage folded four issues in rather than opening WPs beside this
one: #148 (write direction — round-trip as
acceptance, GSAS-II as a target), #107 (the `STR(...)` decision, parked at
the registry-shape task), #101 (the origin-choice task), #196 (Rietica/XND
named as the family's deliberate boundary). Two standing offers recorded:
the filer of #103 volunteers for the `.EXP`/`.PRM` task once the registry
shape lands, bringing two spec findings for its docstring (GSAS-II's
`Rvals['GOF']` is reduced χ², not its root; instrument parameters are
`[default, current, refine_flag]` triples, current at index 1) — and #107's
filer offers either fix once told which. The Jana reader is
[1314](1314-mfile-reader.md), gated on this WP's first task. Next: the
answer's shape, unchanged.

- **2026-08-21** — created, from WP-1110 item 19. Stub: the fences, the seams
  and the acceptance are settled; the answer's shape is the first open decision.
