# WP-1308 — The skill documents its own doors

Milestone: v1.3 · Status: ✅ 2026-08-30 — both gaps closed, and a derived gate
so neither reopens; it found two more of the same shape on its first run. The
WP's own premise was corrected on close: `read_recipe` does not read a `.inp`.
Depends on: 1304 (the skill), 1306 (the reader it omits), 1307 (which measured it)

## Goal

An agent reading only the skill can find `read_recipe` when handed another
program's input file, and an agent producing a trajectory is told the one row
that decides whether its phase fractions mean anything. A **derived gate** then
fails when the next entry point ships undocumented, so neither gap can reopen.

## Context

> **Premise corrected on close, 2026-08-30.** Everything below about Gap 1
> assumes `read_recipe` would have opened the reel episode's TOPAS `.inp`. It
> would not: it reads a PowderLine `GSASII_Rietveld` **JSON** recipe and raises
> `RecipeError: not valid JSON` on a `.inp` (verified). This package has no
> `.inp` reader at all — WP-1118 is where one would go — so hand-parsing was
> the only route and **the four agents were right on that file**. The claim
> came from `PROTOCOL.md`, which said "WP-1306 built a reader for this exact
> file" in one section and "no `.inp` reader" in another; the false half is now
> corrected there. What survives is the narrower, real gap the WP still closes:
> `read_recipe` and `write_recipe_tables` were entry points documented nowhere
> in the skill outside a diagnostic row that cannot fire until they have been
> called. The Goal's first sentence should be read as *can find the reader for
> a PowderLine recipe, and is told plainly that a `.inp` has none*.

**Both gaps were measured, not guessed** (WP-1307, round 1.1, eight cells,
$38.39; `tests/eval_agent_surface/PROTOCOL.md` § Results — round 1.1, the reel
episode holds the numbers).

**Gap 1 — the door with no sign.** `read_recipe` appears in **one** file of the
whole skill tree: `references/diagnostics.md`, inside the `RECIPE_*` rows. It is
absent from `SKILL.md` and from `references/api.md` § In, which the routing table
names for *"you are about to call rietx: entry points"*, and the routing table
has **no row** for *you were handed another program's input file*. So the only
documentation of the entry point sits behind a diagnostic family that cannot
fire until `read_recipe` has already been called. Measured consequence: four
agents of four, both models, both conditions, handed a real TOPAS `.inp` beside
the data it describes, called `read_recipe` **zero** times and mentioned the
string **zero** times. All four parsed the file by hand. Two did it well enough
to catch that its saved state is the *output* of the other program's 68-pattern
run rather than a starting model, with cells sitting on their bounds — so this
is not a competence failure, it is a signage failure.

The manual is not the fallback: `docs/manual/using/recipe.md` documents it
correctly, because `tests/api_surface.py` **partitions the public call surface**
and fails until a new public name is documented or deferred. The skill has no
such gate, which is exactly why the two artefacts disagree. `write_recipe_tables`
is missing from § Out on the same evidence.

**Gap 2 — the deliverable that omits its own decider.** §4b's **Trajectory** row
lists the four `SEQUENTIAL_*`/`PHASE_UNCONSTRAINED` codes, the 2θ-scale anchor
and the precision/accuracy split, and says nothing about background flexibility.
`references/series.md` — the file the routing table names for "an in-situ ramp, a
sweep or a tray" — contains the word **background** zero times. Both routes a
trajectory task takes therefore omit it. But a trajectory of phase fractions is
a QPA question at every point of the chain, and §4b's **QPA** row already bolds
`background.worst_absorption` as the row that outranks every statistic beside it
(measurement in `references/judging.md` § the LaB₆ case: the over-flexible
background wins on *every* agreement index, ADPs 0.958 and 0.000 Å² against a
truth of 0.5, `worst_absorption` 0.46 against 0.08, and the plot does not
separate them either).

Round 1.1 measured what the omission costs. Both `opus-5` cells, unasked,
ran a background sensitivity study on the real reel and found the fit hands
**40-96 wt %** to a phase that is not present at an Rwp within 0.01 of the right
answer, with a difference curve that looks fine; one recorded a 12-term cold fit
reaching LT-ZrMo₂O₈ at 77.9 wt %, Rwp 0.0821 against 0.0822 for the correct
answer. Both named `worst_absorption` as the only report row that separated
them. They got there by **leaving their own deliverable for the QPA row**. The
fourth cell quoted the number without acting on it, which is what depending on
that leap looks like when it does not happen.

**The seams.**
- `docs/skill/rietx/references/api.md` § In (entry points, line ~25) and § Out
  (exports, line ~173) — where `read_recipe` / `write_recipe_tables` belong.
- `docs/skill/rietx/SKILL.md` routing table (§ "Load these when the task calls
  for them", line ~37) — where a foreign-input-file row belongs.
- `docs/skill/rietx/SKILL.md` § 4b Trajectory row (line ~300) and
  `docs/skill/rietx/references/series.md` — where the background check belongs.
- `tests/api_surface.py` — the precedent for the gate: a **derived** partition,
  never a curated list, on the rule a curated list cannot notice a new name.
- `tests/test_skill.py` / `tests/test_skill_cli.py` — the skill's existing
  guards (caps, frontmatter, link resolution, reachability, copy drift). None
  of them relates the skill's prose to the package's surface, which is the
  hole this WP closes.

**The caps are load-bearing and one of them is nearly full.** Measured
2026-08-29:

| file | size | cap | headroom |
| --- | --- | --- | --- |
| `SKILL.md` | 31 876 B, 465 lines | 32 000 B, 500 lines | **124 B** |
| `references/api.md` | 27 729 B | 36 000 B | 8 271 B |
| `references/series.md` | 4 703 B | 36 000 B | 31 297 B |

So the api.md and series.md edits are free and **the routing row is not**: a row
in that table costs ~150-200 B against 124 B of headroom. Do not raise the cap to
fit — it is the reason the body is one Read (`tests/test_skill.py` docstring has
the procedure for raising one, and it is a deliberate decision, not a step in
this WP). Either buy the bytes by tightening prose in the body without deleting a
fact, or route the foreign-input-file case from an existing row. The same
squeeze already blocked WP-1307 from landing a rule in `tests/CLAUDE.md`, which
sits at exactly its 253-line cap.

**The rule that was followed and was not enough.** CLAUDE.md says a WP adding a
diagnostic code or a correction adds its row to the skill. WP-1306 did exactly
that — the `RECIPE_*` rows are present and good. Nothing told it to add the
**entry point**, so the diagnostics arrived and the door did not. Whatever gate
this WP builds should be what makes that rule self-enforcing, rather than a
longer sentence in CLAUDE.md.

**Two committed copies.** `.claude/skills/rietx/` and `.agents/skills/rietx/`
are re-synced by `rietx skill --install . --copy`, and
`test_the_committed_copies_have_not_drifted` fails until they are. Verified in
sync at 2026-08-29.

## Non-goals

Raising a skill cap (a separate, deliberate decision — see above). Rewriting
`references/diagnostics.md`'s `RECIPE_*` rows, which are correct. Round 1.2's
sealed workspace, and the `tests/CLAUDE.md` consolidation pass that owes
WP-1307 a rule — both are recorded in 1307 and neither blocks this.
Re-running any eval cell: this WP acts on round 1.1's numbers and does not
produce new ones.

## Tasks

- [x] `references/api.md`: `read_recipe` in § In and `write_recipe_tables` in
      § Out, in the section's existing one-line signature form. Check the same
      way for any *other* public entry point missing from § In — the gate in the
      next task will name them, so write the gate first if that is cheaper.
      *(Done via the generator's `SECTIONS`, the file being generated. The gate
      was written first and named **four**, not two: `diagnose` and
      `estimate_mu_r` are the same shape — `estimate_mu_r` is named by a
      diagnostic message in `refine.py` and by `using/data.md`, and SKILL.md
      §"capillary µR" says µR "is computed from the specimen" without ever
      naming the call that computes it. All four documented.)*
- [x] The **gate**: a derived partition relating the skill's documented call
      surface to the package's public one, modelled on `tests/api_surface.py`
      (documented / excluded-with-a-reason / deferred), failing until a new
      public entry point is documented in the skill or explicitly excluded.
      Derived, never a curated list.
      *(`tests/test_skill.py`, two tests. Denominator: the module-level
      functions in `rietx.__all__` — 26 verbs — because a free verb is the one
      thing nothing an agent holds leads to. Documented means named in
      `references/api.md`, not anywhere in the tree: `read_recipe` was in
      `diagnostics.md` all along and a tree-wide test would have called that
      coverage. Two exclusions with reasons (`help_registry`, `help_key_for`),
      each meta-tested live, reasoned, and not also documented. Alternative
      constructors are deliberately out of the denominator, with the reason
      recorded in the file — 30 of 35 are reached another way, so a partition
      over them would be 30 shrugs.)*
- [x] `SKILL.md` routing table: a row for *you were handed another program's
      input file* → `references/api.md` + the manual's `recipe` page, within
      the 124 B headroom or by buying bytes without deleting a fact. Say in the
      commit message which, and what the file measured before and after.
      *(A dedicated row, not a merge — the "When" column is the scanning
      surface. Bytes bought, no cap raised: 31 876 → 31 968 B, 32 B headroom
      left, 465 lines both sides.)*
- [x] §4b's Trajectory row and `references/series.md`: the background-flexibility
      check, on the ground that a trajectory of phase fractions is a QPA question
      at every point. Quote round 1.1's measured numbers (40-96 wt %, Rwp within
      0.01) rather than restating the LaB₆ case that `judging.md` already holds.
      *(The row carries the pointer and the headline number in ~100 B, the
      argument goes in `series.md` where bytes are free — 4 703 → 5 887 B. Also
      fixed a rotting count there: "Three things an operator must know" stood
      above five bullets.)*
- [x] `rietx skill --install . --copy` to re-sync both committed copies.
- [x] Tests: the gate above, plus its meta-test if the exclusion list is data.
      No refinement runs, so no `tests/output/` PNGs.
      *(Two tests; the exclusion list is data, so the meta-test checks each
      entry live, reasoned, and not also documented. `tests/test_skill.py`
      22 → 24 passed, both new ones passes and no new skip.)*

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_skill.py tests/test_skill_cli.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_docs_consistency.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

An agent handed a `.inp` can reach `read_recipe` from `SKILL.md` alone, in one
hop through the routing table; the new gate fails when an entry point is added
to the package and not to the skill (prove it by adding one and watching it go
red); every skill file is inside its cap with no cap raised; and the two
committed copies do not drift.

## References

- WP-1307 and `tests/eval_agent_surface/PROTOCOL.md` § Results — round 1.1, the
  reel episode: the zero-of-four measurement, the 40-96 wt % background result,
  and the skill re-read that separated a coverage failure from a discovery one.
- `tests/api_surface.py` docstring — the derived-partition rules this gate copies.
- `docs/skill/rietx/references/judging.md` § the LaB₆ case — the measurement §4b's
  QPA row already rests on.
- `docs/manual/using/recipe.md` — the manual chapter the skill should point at.

## Handover log

- **2026-08-30** — closed. An agent handed another program's input file now gets
  a straight answer in the skill's routing table: `read_recipe` if it is a
  PowderLine recipe, and *this build has no reader, transcribe it by hand* if it
  is a TOPAS `.inp`, a GSAS `.EXP`/`.PRM` or a FullProf `.pcr`. An agent whose
  job is a trajectory of phase fractions is now told, in its own row, that the
  background check decides whether those fractions mean anything — the thing
  three of four agents last round only found by wandering into someone else's
  deliverable. Behind both is a test that fails when a public entry point ships
  without a door.

  **The correction that matters most is to the premise.** This WP was written
  to make an agent handed a `.inp` reach `read_recipe`, and that goal was
  wrong: `read_recipe` reads PowderLine **JSON** and raises `RecipeError: not
  valid JSON` on a `.inp` (verified this session). There is no `.inp` reader in
  this package. The first routing row I wrote said "a TOPAS `.inp`" and would
  have sent an agent in exactly the measured episode at a door that does not
  open — worse than the silence it replaced. `/code-review` caught it; I had
  not. The source is `PROTOCOL.md`, which asserted "WP-1306 built a reader for
  this exact file" in one section while stating "no `.inp` reader" in another,
  and I carried the quotable half into this WP's Context without checking it.
  Both are now corrected in place, and the round's own record says plainly that
  **on that file the four agents were right to parse by hand**. This is the
  third correction this one finding has needed, which is itself the lesson: it
  was re-read twice for *framing* and never once against the code.

  The gate was worth more than the two names it was built for. Run against the
  package before anything was fixed, it named **four**: `read_recipe` and
  `write_recipe_tables` as expected, plus `diagnose` and `estimate_mu_r` — both
  the identical failure, a concept documented and its door unnamed. SKILL.md's
  degeneracy table has said for a long time that capillary µR "is computed from
  the specimen and never refined" without ever naming the call that computes it,
  and `refine.py`'s own diagnostic message says "rietx.estimate_mu_r() shows …"
  to an agent whose skill has never heard of it. Neither was suspected. That is
  the argument for a derived denominator over a careful reading.

  **Done.** All six tasks. (1) The api index gains four rows, edited in
  `make_api_index.py`'s `SECTIONS` because the file is generated; both § In and
  § Out gained a sentence of prose signage as well as rows, so the routing
  reads in passing. (2) The gate, `tests/test_skill.py`, two tests. (3) A
  dedicated routing row for the foreign-input-file case. (4) The
  background-flexibility check in §4b's Trajectory row and, at length, in
  `references/series.md`. (5) Copies re-synced. (6) The exclusion table is data,
  so it has a meta-test.

  **The gate's three design decisions**, all in the file's own comment block.
  *The denominator is the free verbs* — the module-level functions in
  `rietx.__all__`, 26 of them — not the whole call surface, which
  `tests/api_surface.py` already partitions against the manual, whose job is
  coverage. The skill is a protocol, and the only names it owes a reader are the
  ones nothing leads to: a type is returned by a verb, or constructed from a
  class the index renders with its signature, so an agent holding an
  `Instrument` reaches its constructors through `help()`. Nothing an agent holds
  leads to `read_recipe`. *Documented means named in `references/api.md`*, not
  anywhere in the tree — `read_recipe` sat in `diagnostics.md` all along, and a
  tree-wide test would have called that coverage and stayed green straight
  through the failure this WP exists to fix. *Alternative constructors are out*,
  and that is recorded in the file as a gap rather than a decision: 30 of the 35
  are reached another way, so a partition over them would be 30 shrugs.

  **Measured.** SKILL.md 31 876 → 31 973 B, 465 lines both sides: **no cap
  raised**, the routing row and the Trajectory clause bought with three
  tightenings that delete no fact (§ The API was restating the routing table's
  own enumeration of what api.md holds; that row dropped ", the exports", which
  the § Out row already routes; "will not infer your purpose for you" → "will
  not infer yours"). **27 B of headroom left.** api.md 27 729 → 29 093 B (cap
  36 000), series.md 4 703 → 6 240 B. The acceptance experiment: a public verb
  added to `__all__` and not to the skill sends the gate red naming it;
  reverted. `tests/test_skill.py` 22 → 24 passed, both new tests passes, no new
  skip — measured at file granularity, which is the exact form of the "say
  which numbers moved" check; no pre-change fast-suite baseline was taken on
  this tree. Fast suite on the final tree 3556 passed, 122 skipped in 2:06,
  `[dev]` venv (no jax/torch), darwin/arm64, Python 3.12.12, nothing else
  mid-suite. Rung 3 not run and not owed: docs and tests only.

  **The review pass** (`/code-review medium --fix`) found five and changed the
  work in four places, none of them declined. Two HIGH were the one premise
  error above, in the routing row and in § In's prose; § In now names the
  PowderLine recipe *and* fences the other way, so an agent holding a `.inp` is
  told it has no reader here rather than left to infer one. One MEDIUM: the
  `series.md` bullet said to read `background.worst_absorption` per pattern and
  named no route, and `SeriesResult` does not carry one — it now gives the class
  form, `rx.SequentialRefinement(...)` → `.fit(...)` →
  `rx.build_report(sr.results_[i])`, which I verified against
  `sequential.py:562` (`results_: list[RefinementResult]`). One LOW worth more
  than its rank: my gate matched `` `rx.name` `` **anywhere** in api.md, so a
  verb named only in a section's introductory sentence would have satisfied it —
  the prose loophole is the gate's own thesis turned against it. It now matches
  entry rows only (`API_INDEX_ENTRY`); same verdict today, 0 undocumented. The
  last LOW corrected the note pushed to WP-1118.

  **Gotchas for whoever is next.** CLAUDE.md's skill bullet still states half
  the rule — "a WP adding a diagnostic code or a correction adds its row there"
  — which is exactly the half WP-1306 followed. Adding the entry-point clause
  was written, measured at +1 line against a file sitting at **exactly** its
  906-line cap, and reverted: fitting it in four lines needed ~32 characters of
  real deletion, and this WP's brief says the gate should be what makes the rule
  self-enforcing rather than a longer sentence there. The gate's failure message
  names `SECTIONS` and the re-sync command, which is where a stranger needs to
  be sent. `series.md` also had "Three things an operator must know" standing
  above five bullets; the count is dropped rather than corrected, per v1.2's
  rule that a count in prose rots like a retuned threshold. And one sentence was
  drafted and cut — that a chain should hold its background's flexibility fixed
  across patterns. It sounds right, no measurement showed it, and the term count
  does not vary down a warm-started chain anyway.

  **A second rule is now owed to `tests/CLAUDE.md`'s consolidation pass**, which
  this WP's Non-goals already record as owing WP-1307 one, and which cannot take
  either while the file sits at its 253-line cap: *an eval finding that asserts
  something about the package is checked against the package before it is quoted
  into a WP.* § "An eval's expected answer is a measurement, not a definition"
  is the neighbouring rule and does not cover this — that one guards a scored
  row's expected answer, this one guards a **result** on its way out. Round
  1.1's `read_recipe` finding was re-read twice, both times for framing, and
  reached a WP file, a milestone record and ROADMAP before anyone ran it.

  **Next:** v1.3 ships. The milestone's acceptance block, ROADMAP's v1.3 row and
  the version are the remaining work, and nothing in this WP blocks them. Two
  items stay recorded and unowned, neither a blocker: round 1.2 owes a sealed
  workspace before any `bare` cell can be read as an access claim (WP-1307), and
  `Instrument.flat_plate_transmission` is a real door outside this gate's
  denominator — the one alternative constructor that gave me pause, since an
  agent must know the geometry exists before it can ask for it.

- **2026-08-29** — created, from WP-1307's round-1.1 findings, after the round's
  own conclusions were re-read against the skill's text in both directions. The
  round first reported both gaps the wrong way round: `read_recipe` as an agent
  discovery failure (it is a skill coverage failure — the name is in one
  reference file, behind a diagnostic that cannot fire until the door has been
  used) and `worst_absorption` as absent from §4b (it is in the **QPA** row, and
  absent from the **Trajectory** row the episode's task named). Both corrections
  are in 1307's file and in `PROTOCOL.md`; this WP is written against the
  corrected version. Not started.
