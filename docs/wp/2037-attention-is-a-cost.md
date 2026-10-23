# WP-2037 — Attention is a cost: two channels, a response per code, relevance by purpose

Milestone: generality · Status: 🔄 2026-10-23 — claimed by @yue-here
Track: The registry and the guard
Depends on: 2001
Priority: P2 2026-10-23 — a scoping WP other WPs wait on: 2003's first demotion takes the shape this WP sets, and every audit from 2003 on fills the column it installs

## Goal

The generality record carries a fifth aim beside its four: rietx must not flood a user
or an agent with noise, because attention spent on noise lowers the quality of the
refinement. Four clauses in § The rule and § Demotion give it teeth: a number lives in a
field and a diagnostic earns its place by telling fits apart; a code's level is the
response it requires, and whether it applies is derived from the caller's declared
purpose; the default view prints by level and refuses to guess a purpose; the caller may
set a code's level. The audit table has a response column with its tests, the summary
and the other three renderers share one filter, the deliverable vocabulary covers the
goals, and a batch aggregate serves pipelines and the suite metric alike.

## Context

The rule is [generality § The rule](../milestones/generality.md#the-rule) and
§ Demotion; the decision line is [DESIGN § Rules](../DESIGN.md#rules), 1. The proposal
this WP files was written 2026-10-23 in three drafts, reviewed adversarially against
both, and ruled on by the maintainer the same day (§ Decisions below). Its worked
before/after examples are in [`2037-attention/examples.md`](2037-attention/examples.md),
with every *before* block measured on `main` that day.

**Why.** DESIGN.md § Rules 1 prices a rerun ("a caller pays in tokens and a fit in
seconds") and not reading. Under-alerting costs as much as flooding: the one measurement
on agents says they stop on a stated criterion seven times in eight and never without
one (the v1.3 round, the record § The rule). This aim adds the cost of reading to the
rule and moves the decision line nowhere.

**Who reads, and for what.** The package has no single reader and no single response.
Goals: phase identification; a cell as the result; QPA; structure (coordinates,
occupancies, ADPs); microstructure; instrument calibration; a series; magnetic
structure; indexing; publication, which needs the caveats; teaching; method development.
Users: an agent over one pattern (the design's first user); an agent or script over
hundreds of fits, where the consumer is a filter; an expert who will disagree with a
level; a student who needs the explanation; a GUI user; an instrument scientist. The
same finding is nothing for one goal and fatal for another: `RESOLUTION_UNCONSTRAINED`
is irrelevant to a QPA fraction and voids a size claim; `FLOOR_HIT` on extinction is
irrelevant to a cell and matters to an ADP. So a message's level is a property of the
code *under a purpose*, and that property is physics: which result numbers depend on
the thing the diagnostic names.

**What the tree does today** (measured on `main`, 2026-10-23, the skill's worked
default on FAP, `examples/skill_worked_default.py`):

- `Diagnostic.level` (`schemas/common.py`) has three values. Raise sites: 117 `info`,
  161 `warning`, 7 `error`. Two readers act on a level: `RefinementResult.usable` reads
  `error` alone; `SeriesResult` splits `warning` from the rest. Nothing treats `info` as
  quieter.
- `Refinement.summary()` (`refine.py`) prints every diagnostic at every level under one
  header, "N unresolved", through `schemas/results._diagnostic_lines`, which
  `str(result)` shares. The skill's § 4 says "Act on each `d.suggestion`". So an `info`
  record is shown as unresolved and acted on.
- `summary(deliverable=)` knows `DELIVERABLES = ("phase_id", "qpa", "structure",
  "series")` (`schemas/results.py`) and refuses to infer a purpose, by design. Cell,
  microstructure, calibration and magnetic have no name, though the skill's § 4b table
  has a microstructure row.
- § Demotion rules (2026-10-18) that a demoted verdict becomes an `info` record that
  fires on every run it applies to. Under the readers above, every demotion from 2003 on
  adds a row the agent is told to act on.
- `rietx._audit.Row` tiers a code's statistic, threshold and action. No field says what
  a reader does on seeing it; no test holds a code's level to anything; no test holds a
  code silent where its fault is absent. No per-code override, no aggregate over a batch
  of independent fits (the series aggregate `SEQUENTIAL_PERSISTENT_FINDING` exists).
- The worked default returns four warnings and no `info` (the run's one `info`,
  `BACKGROUND_ORDER_AT_CAP`, is a `UserWarning` from `auto_background`). `summary()`
  prints 3 829 characters, `summary(deliverable="structure")` 4 114. One warning is a
  snap of 3.3e-11 in a fractional coordinate (`SITE_SNAPPED_TO_SPECIAL_POSITION`,
  `crystallography/cif.py`, no magnitude floor), the CIF's own rounding. One is
  `FLOOR_HIT` on an extinction the plan freed on a lab powder. `RESOLUTION_UNCONSTRAINED`
  is right and irrelevant to a structure. Only `PATTERN_UNDERSAMPLED` bears on what the
  worked default quotes.

The noise today is in level and relevance, not volume, and § Demotion as written adds
volume with every demotion.

### The rule: four clauses

Written into `generality.md` § The rule and § Demotion, with the fifth aim beside the
four in § Scope.

**1. Two channels.** A number lives in a result field and costs nothing until read. A
diagnostic is a message, and it earns its place by telling one fit from another: it
fires on some fits, stays silent on others, and a careful refiner does something
different when it fires. A demotion moves the statistic into a record field, with its
explanation in `rietx.help` keyed to that field, and emits no diagnostic that fires on
every run. The field channel is a structured record the CIF writer, the report and the
GUI read; never a dump.

This reverses the shape ruled on 2026-10-18 and answers the evidence that ruling cited.
GSAS-II and TOPAS print the largest shift/esd every cycle, which is tier-2 practice for
*printing a statistic*. They print it to a log; neither puts it in a list the reader is
told to resolve. A record field plus a line in the full report is the same practice in
rietx's shape, and a row under "unresolved" is not. The ruling chose its shape over
building a help seat for result fields; this clause builds the seat.

**2. Level is the required response, and relevance is derived from the purpose.** The
flight-deck definitions, one purpose at a time:

- `error`: do not read the values. `usable` reads it already. Unchanged, and never keyed
  on purpose: an unusable fit is unusable for every purpose.
- `warning`: act before quoting a result number of this purpose, or the plan did not
  reach what it asked. A result number is a cell, a fraction, a coordinate, an ADP, a
  size; an agreement index is not one.
- `info`: awareness. Nothing to do for this purpose.

Two tables carry it, and neither is authored per code per purpose. The code's audit row
gains one **response** column (`warning`, `error` or `info`) with one sentence on what
the reader does; one response per code, magnitude in the message; where two
consequences genuinely differ, two codes, never a threshold between levels. A
**purpose** declares the parameter paths its result numbers depend on, as globs in one
table of about eight rows, each citing the physics that couples the number to the path
(`cell`: `phases.*.cell.*`, `instrument.zero_shift` and the position corrections that
exchange with them, per `report.identifiability`; `qpa`: scales, occupancies, Biso,
texture, background and specimen absorption, the skill § 3 group and WP-1055;
`microstructure`: the profile and sample-broadening terms, WP-1131; and so on).

A diagnostic's level under a purpose is then **computed**: its response where any of its
`where` paths matches the purpose's globs, `info` elsewhere. A code that carries no
`where` (`PATTERN_UNDERSAMPLED`, a convergence failure) declares its scope in its audit
row: the purposes it bears on, or `all`. A code with neither is a test failure, never
`info` by default. WP-1076's rule: a pairing nobody checked must not read as "not your
concern". It is also why the tables stay small: 285 codes times eight purposes is not
written by hand, and a new purpose is one row.

**3. The default view prints by level, and with no purpose it says so.** Under a
deliverable, the text summary prints errors and the warnings for that purpose in full,
and the rows that are `info` for it as one line each, code and paths only. With no
deliverable, it prints the errors in full and for every other row one line naming the
code, its paths and the purposes it is a warning under. The header says how to see
more: *pass `deliverable=` for the rows that decide your purpose; every row is in
`result.diagnostics`*. That sentence is the reading rule, carried by the output itself
(WP-1338: a feature's guidance takes the cheapest place that holds it, the package's
own output first), so the skill names only the field. This is the summary's existing
refusal to infer a purpose, applied to its diagnostics. The GUI shows the same ordering
with the `info` rows collapsed beside their help text; nothing is hidden from the
student or the expert. The "N unresolved" header goes.

**4. The audited response is a default, and the caller may set it.** A per-code override
on `summary()` and in settings, in the compiler's allow-warn-deny form. The audited
default is one table row; the override is the audit's caller class and needs no tier.
The expert who disagrees with a response and the pipeline that treats one code as
blocking both get what they want without touching the default.

### What makes the rule survive

- **The response column** in `_audit.Row` and the purpose table beside it. A meta-test
  holds the declared response equal to every raise site of that code, fails a `warning`
  row whose sentence names no result number or plan outcome, and fails a code with no
  `where` and no declared scope.
- **A test of silence.** For each warning code, a fixture where it must fire and one
  where it must not. The mechanical ground already asks this of every flag and nothing
  enforces it; Rust's `#[expect]` is the form.
- **The help seat for result fields** (`help.py`), with both-way tests, first. Clause 1
  cannot land without it.
- **One filter function** every renderer calls: the text summary, `str(result)`, the
  HTML, the GUI panel. The GUI change means a rebuilt dist (`gui/CLAUDE.md`).
- **The deliverable vocabulary** extended: `cell`, `microstructure`, `calibration`,
  `magnetic` beside the four, each with its deciding rows in `_deliverable_lines`;
  `magnetic` kept separate because its numbers depend on different paths.
- **A batch aggregate**: one function over a list of results giving the firing rate per
  code, warnings per fit per purpose and the bad-actor Pareto. The pipeline user's
  triage and the audit's prompt, written once.
- **The two FAP bugs, separately.** The snap floor derived from the file's own printed
  precision (a shift below half the last printed digit is the file's rounding), tier 1
  beside `CIF_ANGLE_CORRECT_MAX_DEG`. `FLOOR_HIT` on a freed extinction is a plan
  question, handed to 2004.

The 248 unaudited code rows are not re-levelled here. WP-2004 to 2007 fill the response
column as they tier each code, under the tests this WP installs, so WP-2003's first
demotion already follows clause 1.

### How it is measured

- **Alarm-management metrics over the acceptance suites, as a prompt and never a
  verdict.** Firing rate per code, warnings per fit per purpose and the Pareto over the
  suites' fits, pinned in a meta-test so a change that moves them is seen. The suites
  are rietx's own data, so a code firing on every acceptance fit may mean every
  acceptance fit has the fault. A high rate sends the code to the mechanical ground's
  test, a known truth where it must fire and one where it must not. It re-levels nothing
  by itself (DESIGN.md § Rules 3: a rule whose only evidence is rietx's own test data is
  overfit in prose form).
- **Before and after on four families**: the worked default on FAP, NAC on 11-BM, a CPD
  QPA fit, a magnetic fixture. Rows by level and purpose in `result.diagnostics`, lines
  printed by `summary()` with and without a deliverable. Characters are not the metric.
- **One registered agent run** on `tests/eval_report_agent`, current view against the
  split view, a smoke check named as one (eight runs cannot tell seven of eight from five
  of eight). A worse result reverts clause 3's quiet default and keeps the ordering;
  clauses 1, 2 and 4 stand either way.

### Practice drawn on

ISA-18.2 / EEMUA 191 alarm management (an alarm is a condition requiring operator
response; a master alarm database with cause, consequence, corrective action, priority;
health measured by rate, time in flood and the bad-actor Pareto, and a person
rationalises what the metrics find). FAA AC 25.1322 (warning, caution and advisory by
required crew response; silence means normal). Google's Tricorder (a "not useful" signal
per finding; an analyser over about ten percent is switched off). Clang and Rust
(on-by-default warnings need near-zero false positives; allow/warn/deny; `#[expect]`).
PEP 565 (a deprecation warning shown by audience). checkCIF (four levels; the C level
grew into noise). Clinical decision support (overrides of 49-96 %, roughly halved by
tiering into interruptive and non-interruptive; van der Sijs 2006, Paterno 2009).

### Decisions (the maintainer, 2026-10-23)

1. The four clauses adopted; the fifth aim goes into `generality.md` beside the four.
2. Scope: the milestone's § Scope says a redesign is a follow-up WP; this one lands
   inside the milestone, before WP-2003, because § Demotion's current shape makes every
   demotion from 2003 on add a row to the view this WP changes.
3. Clause 3's quiet default lands with the ordering now; the registered agent run is the
   tripwire.
4. The deliverable vocabulary: the four names above.
5. The softening of unanimity for a recorded, cheap-to-undo default is deferred to its
   own brief, [WP-2038](2038-the-softening-a-brief-not-a-change.md); it reopens the
   fourth review for a reason unrelated to attention.

## Non-goals

- Re-levelling the 248 unaudited codes: 2004 to 2007, under this WP's column and tests.
- The chain's own demotions and the discontinuity record's shape: 2003, which follows
  clause 1 once this lands.
- The skill's rewrite: 2008. This WP changes one sentence of § 4 (Tasks).
- The softening: 2038.
- A new purpose for indexing, which is a different result type with its own summary.

## Tasks

- [x] The record: the fifth aim in `generality.md` § Scope; the four clauses in § The
      rule and § Demotion, the 2026-10-18 "fires on every run" shape reversed with the
      log-versus-list answer written beside it; the acceptance row below added to
      § Acceptance; the decisions above dated into § Decisions.
- [ ] The help seat for result fields in `help.py`, crossed both ways against the live
      result schemas (`tests/test_help.py`'s pattern), with `rx.explain("<Type>.<field>")`.
- [ ] `_audit.Row.response` and `Row.scope`, the purpose table (one module, about eight
      rows with their physics), and the three meta-tests (response equals every raise
      site; a `warning` sentence names a result number or plan outcome; no `where` and
      no scope fails). Existing rows enter with `response` unset and a shrink-only
      baseline, so 2004-2007 fill it as they tier.
- [ ] The derived level: one function `level_under(diagnostic, purpose)` in
      `schemas/results.py` (or beside `Diagnostic`), unit-tested on the four FAP codes.
- [ ] One filter function and the four renderers: `summary()`, `str(result)`, the HTML
      (`viz`), the GUI diagnostics panel (collapsed `info` beside help; rebuilt dist;
      `npm --prefix gui test`). The "N unresolved" header replaced; the no-deliverable
      line and the `deliverable=` sentence as in `2037-attention/examples.md` § 1.
- [ ] `DELIVERABLES` extended with `cell`, `microstructure`, `calibration`, `magnetic`,
      each with its deciding rows in `_deliverable_lines`, the skill § 4b table and
      `SeriesResult.summary`'s refusal text updated.
- [ ] The caller override: `summary(levels={code: "allow"|"warn"|"deny"})`, the same map
      in settings, `usable` reading a caller's `deny`; one `caller` row in the table.
- [ ] The batch aggregate: `rx.diagnostics_summary(results, deliverable=)` (firing rate
      per code, warnings per fit, Pareto); the suite metric built on it and pinned as a
      meta-test over the acceptance suites' collected diagnostics.
- [ ] A test of silence per warning code that has a fixture today, and the harness for
      the rest (a registry a code's silence fixture is added to; absence listed, not
      failed, until 2004-2007 fill it).
- [ ] The snap floor from the file's printed precision in `crystallography/cif.py`,
      tier 1, with the FAP case silent and a real snap still firing.
- [ ] Before/after counts on the four families in the handover; the agent run
      registered, run once, reported beside the v1.3 baseline.
- [ ] `FLOOR_HIT` on a freed extinction handed to 2004 as an `### Inherited` entry (done
      at filing; keep it current).
- [ ] Tests + PNGs; the fast count moved by exactly the tests added.
- [ ] Skill: § 4's "Act on each `d.suggestion`" becomes *declare your purpose with
      `ref.summary(deliverable=…)` and act on the warnings it prints under it;
      `result.diagnostics` holds every row*; the § 4b table gains the new deliverable
      names. Nothing else; the reading rule lives in the output.

## Acceptance

Every code carries a declared response held to its raise sites, a scope where it
carries no path, and a silence fixture where it is a warning; the default view prints no
row outside its purpose in full and names the purposes a row is a warning under; the
suite metrics and the four-family counts are in the handover with the agent-run rate
beside the v1.3 baseline.

```sh
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py -q
.venv/bin/python -m pytest tests/test_results.py tests/test_summary*.py -q        # the filter and the derived level
.venv/bin/python examples/skill_worked_default.py                                # the FAP before/after, by eye against 2037-attention/examples.md
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
npm --prefix gui test && npm --prefix gui run check
```

## References

- `docs/milestones/generality.md` § The rule, § Demotion, § The fourth review;
  `docs/DESIGN.md` § Rules 1, 3, 4.
- ISA-18.2 (2016), *Management of Alarm Systems for the Process Industries*; EEMUA 191.
- FAA AC 25.1322-1 (2010), flight-deck alerting.
- Sadowski et al. 2018, *Lessons from building static analysis tools at Google*, CACM.
- PEP 565; the Rust reference, lint levels and `#[expect]`.
- van der Sijs et al. 2006, JAMIA 13:138; Paterno et al. 2009, JAMIA 16:40.
- WP-1076 (a declared name is a claim), WP-1338 (the cheapest place), WP-1302 (the
  termination view), WP-1985 (the help seat for codes).

## Handover log

- **2026-10-23** — created from the proposal ruled on that day. No open WP owns the
  view: 2003 owns the chain's demotions and takes the shape this sets, 2004 the report's
  codes, 2008 the skill, none the summary's rendering, the level column or the purpose
  key. Companion: `2037-attention/examples.md`, the before blocks measured on `main`
  (5d64a86) with the skill's worked default on FAP.
