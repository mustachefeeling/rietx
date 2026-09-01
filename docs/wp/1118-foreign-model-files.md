# WP-1118 — foreign model files: read a refinement in, write one back

Milestone: unscheduled · Status: ⬜
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
documented, and the `Z`-term round-trip question is already in Inherited
below). Every convention the validation campaign measured (FCJ vs A_T2,
K = 1 vs 0.5 polarization, U vs B vs β, FWHM vs σ, centidegrees) becomes a
written decision with a citation on the writer. Deliberately **not** here:
an RMCProfile export (data + starting configuration, not a protocol —
issue #192's territory), and Rietica/XND in either direction — issue #196
proposes those readers as a beyond-the-majors widening of this family;
right home, deliberately unscheduled, no corpus, and the read/write
asymmetry is intentional.

**Two things arrive with the TOPAS files (issues #107, #101).** Five archive
files open phases with the macro form `STR(R-3)` / `STR(######, "#name#")`,
which the line-based split cannot see, so they parse **zero phases** and
`to_structure` returns a confident wrong diagnosis ("a Pawley or
indexing-only .inp is legal and has none"); two already-fixed macro bugs
hide behind it, so **PR #98's incidence figures are floors until this is
decided**. The minimum honest fix is independent of any design: recognise
the spelling and refuse naming it — a reader may decline a construct, it may
not describe it as absent. Whether `STR(...)` is special-cased or the reader
grows a general macro pass is the registry-shape task's decision (and a
general pass borders [1119](1119-named-variables.md)'s equations scope —
decide the boundary there, not twice). Second, origin choice:
`gemmi.SpaceGroup("Pn-3m").ext` is `'1'`, so a structure transcribed from an
origin-choice-2 source gets choice 1's symmetry with nothing raised — wrong
structure factors under a healthy-looking fit — while the TOPAS spelling
`Pn-3mZ` raises, and stripping the letter inverts the meaning. The
translation table exists in the #98 draft (`normalize_space_group`: `Z`→`:2`,
`S`→`:1`, `R`→`:R`, `H`→`:H`); the **diagnostic is the load-bearing half**
and is general — it fires for any multi-origin symbol left unpinned, from
any reader, in the reader diagnostics channel where such reports belong.

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

`capabilities()` publishes the pattern formats `read_pattern` opens; model
formats need their own arm, and the meta-test that fails on a registry member
missing from its arm applies unchanged. A new format token is spelled in
`_about.py`, never inline (root CLAUDE.md § Conventions).

### Inherited

- **2026-08-30, from [1308](1308-skill-documents-its-doors.md): the skill now
  has a routing row for *you were handed another program's input file*, and a
  reader added here must claim it.** The row is in `SKILL.md`'s routing table
  and points at `references/api.md` § In plus the manual's `recipe` page; § In's
  own paragraph opens the case by name and currently names only `read_recipe`.
  A second such reader (TOPAS `.inp`, `.EXP`/`.PRM`, `.pcr`) therefore has two
  obligations beyond the code, and `tests/test_skill.py` enforces only the
  first: every new public verb must appear in `docs/skill/make_api_index.py`'s
  `SECTIONS` or in `SKILL_EXCLUDED_VERBS` with a reason (the gate goes red until
  it does), and — no test for this — that routing row's wording says "a
  PowderLine recipe", the only such reader that exists, and will need widening.
  § In's paragraph states the same fence the other way, that a `.inp`, an
  `.EXP`/`.PRM` and a `.pcr` have no reader and are still transcribed by hand;
  a reader landed here must delete that sentence as well as add its row, or the
  skill will keep telling an agent to transcribe a file it can now open.
  Measured caution: SKILL.md sits at **31 973 B of its 32 000 B cap**, 27 B of
  headroom, so widening the row costs bytes that must be bought elsewhere.
  WP-1308's entry records the three tightenings it used and that no cap was
  raised.

- **2026-08-23, from [1131](1131-sample-broadening-is-a-specimen-property.md):
  rietx has no constant Lorentzian instrument term, so a GSAS-II profile cannot
  round-trip.** GSAS-II's CW Lorentzian is `γ = X/cosθ + Y·tanθ + **Z**`;
  `ProfileTCHZ` declares exactly `u, v, w, x, y` and no sixth term
  (`schemas/instrument.py:507-543`, and `params/vector.py:489` and `:953` both
  hard-code that five-name tuple). An `.instprm` with a nonzero `Z` therefore has
  nowhere to land, and the honest reader behaviour — carry it or refuse it by
  name — is this WP's call, not a physics question: Von Dreele's own teaching
  slide says `X, Y, Z = 0` is normal and that 11-BM has them zero, so `Z` earns
  a schema field for round-tripping and not for modelling. 1131 fenced it here
  explicitly rather than folding it in. Note also, for the same reader, that
  rietx's `profile.x` is the 1/cosθ (size) coefficient and matches GSAS-II's `X`
  by law, while TOPAS's `pkx`/`pky` map to rietx's `y`/`x` and **not** by letter
  (measured in WP-1130).

## Non-goals

- **Not a TOPAS-compatible engine.** No macro language, no `prm` expression
  evaluator, no `fit_obj`. A construct with no model here is reported, not
  emulated.
- **Not GSAS-II `.gpx`.** It is a pickled python object graph; reading it means
  importing GSAS-II's own classes, which both the licence fence and the
  dependency policy refuse. `.EXP`/`.PRM` are text and documented.
- **Not the additive component seam.** A `fit_obj` or a `.pcr` extra peak lands
  on `Instrument.extra_components`, which is [1102](1102-component-seam-humps.md)'s.
- **Not a pattern reader.** `io/`'s existing registry keeps that job.

## Tasks

- [ ] Decide the answer's shape (model + vary set, or a `Project`) and stand up
      the model-format registry beside `PATTERN_FORMATS`, with the diagnostics
      channel and the "report or refuse, never drop" rule written down first.
- [ ] TOPAS `.inp` reader — the format with the evidence behind it.
- [ ] GSAS `.EXP` + `.PRM` reader, and make `tests/test_acceptance_fap.py` take
      its protocol from the reader instead of from transcribed constants.
- [ ] FullProf `.pcr` reader.
- [ ] Origin-choice honesty: `SPACE_GROUP_ORIGIN_ASSUMED` when a multi-origin
      symbol resolves unpinned, and the TOPAS suffixes accepted on input
      (issue #101; lift `normalize_space_group` from the #98 draft).
- [ ] The writers, each naming what did not cross — GSAS-II included — with
      export → re-import round-trip as each format's acceptance (issue #148).
- [ ] `capabilities()` arm, skill rows for the new diagnostic codes
      (`docs/skill/rietx/` — `AGENT_PROTOCOL.md` is a redirect stub since
      WP-1304), a Part 1 manual section, and an `ATTRIBUTION.md` row per
      format.
- [ ] Fixtures with provenance rows in `tests/data/README.md`; tests, and the
      obs/calc/diff PNGs for any refinement one of them drives.

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

- **2026-09-01** — the issue triage folded four issues in rather than
  opening WPs beside this one: #148 (write direction — round-trip as
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
