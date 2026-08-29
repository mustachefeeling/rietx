# WP-1308 — The skill documents its own doors

Milestone: v1.3 · Status: ⬜
Depends on: 1304 (the skill), 1306 (the reader it omits), 1307 (which measured it)

## Goal

An agent reading only the skill can find `read_recipe` when handed another
program's input file, and an agent producing a trajectory is told the one row
that decides whether its phase fractions mean anything. A **derived gate** then
fails when the next entry point ships undocumented, so neither gap can reopen.

## Context

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
- [ ] `SKILL.md` routing table: a row for *you were handed another program's
      input file* → `references/api.md` + the manual's `recipe` page, within
      the 124 B headroom or by buying bytes without deleting a fact. Say in the
      commit message which, and what the file measured before and after.
- [ ] §4b's Trajectory row and `references/series.md`: the background-flexibility
      check, on the ground that a trajectory of phase fractions is a QPA question
      at every point. Quote round 1.1's measured numbers (40-96 wt %, Rwp within
      0.01) rather than restating the LaB₆ case that `judging.md` already holds.
- [ ] `rietx skill --install . --copy` to re-sync both committed copies.
- [ ] Tests: the gate above, plus its meta-test if the exclusion list is data.
      No refinement runs, so no `tests/output/` PNGs.

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

- **2026-08-29** — created, from WP-1307's round-1.1 findings, after the round's
  own conclusions were re-read against the skill's text in both directions. The
  round first reported both gaps the wrong way round: `read_recipe` as an agent
  discovery failure (it is a skill coverage failure — the name is in one
  reference file, behind a diagnostic that cannot fire until the door has been
  used) and `worst_absorption` as absent from §4b (it is in the **QPA** row, and
  absent from the **Trajectory** row the episode's task named). Both corrections
  are in 1307's file and in `PROTOCOL.md`; this WP is written against the
  corrected version. Not started.
