# Runner protocol — the skill-placement round (WP-1338)

**Protocol version: 1.0**, registered 2026-09-28 **before any run**; **1.1** by the amendment below, before any 1.1 run. Bump it on
any change that alters comparability: the episode, the workspace contents, the
prompt, the condition set, the models, N, the read-outs or the decision rule.
Results are appended below the registration and the registration is not
rewritten once a cell has run.

This is the repository's third eval protocol. It pools with nothing in
`tests/eval_report_agent/` or `tests/eval_agent_surface/`, and borrows their
discipline: registered first, the condition enforced in the workspace rather
than the prompt, the read-outs fixed in advance (`tests/CLAUDE.md` § Three eval
protocols).

## The question

The skill body routes an agent to its reference files through a table. Two of
its rows are keyed by something the agent already holds when it needs the row:
a `Diagnostic` code that fired, or a field that declined to answer. WP-1338
proposes replacing such rows with one standing sentence telling the agent to
grep `references/` for the name in front of it. The body is at its byte cap, and
every feature so far has added a routing row.

> **When a diagnostic fires, does an agent reach that code's row as often under
> the grep sentence as under the routing rows?**

The answer decides whether the body ships the sentence. It does not decide the
placement rule's other steps, which move no row an agent could miss.

## The episode

A colleague's refinement to judge. The workspace holds `FAP.XRA` and
`fluorapatite.cif` (the GSAS-II LabData tutorial pair, provenance in
`tests/data/README.md`), the colleague's script `fit.py`
([`colleague_fit.py`](colleague_fit.py)) and what it printed,
`fit_output.txt`, generated once by `build` and copied into every cell.

The script makes two choices a reviewer would query: the `lab_bragg_brentano`
plan, with a stage freeing the atoms inserted before its roughness stage, frees
zero shift and sample displacement together, and a 24-term Chebyshev
background is flexible enough to reach an ADP. Its output prints each
diagnostic as the body's worked default does, level, code, `where`, message and
suggestion. Six codes fire, each with its row in `references/diagnostics.md`:
`FLAT_DIRECTION`, `HIGH_CORRELATION`, `BACKGROUND_ABSORPTION`,
`RESOLUTION_UNCONSTRAINED`, `PATTERN_UNDERSAMPLED` and
`SITE_SNAPPED_TO_SPECIAL_POSITION`.

Each message carries its own suggestion, so an agent can answer well without
opening a reference file. That is deliberate. It is what a fit prints, and a
routing row that no agent needs when the suggestion is in front of it is doing
no work, which is itself an answer to the question.

## The conditions — the body, and nothing else

| condition | the body |
|---|---|
| `rows` | `SKILL.md` as it stands at registration |
| `grep` | the same body with two routing rows dropped and one paragraph added above the table |

The two dropped rows are the ones starting
``| a `Diagnostic` fired and you need its row`` and
``| §6 — something declined to answer``. The added paragraph is:

> **A name in front of you is its own index.** A `Diagnostic` code, a field or
> a verb has its row in one of these files, and `grep -rn NAME references/`
> finds it wherever it lives. A code's row says what it means, what to do and
> what you must not do.

`runner.grep_body` makes the change and refuses a body that no longer carries
either row. Every other byte is identical, the reference files included.

**The condition is installed everywhere the agent can find a body.** `build`
installs one venv per condition from a wheel of this tree, so the package's
own copy of the skill sits in site-packages, and rewrites that copy under
`grep` before `rietx skill --install` copies it into the workspace. The
maintainer's checkout is still on the machine and holds the `rows` body; a
tool call naming a path inside it is reported per cell (the `leak` column),
never assumed absent.

## The prompt

The same text in every cell, naming no module, document, code or skill:

> My colleague refined our fluorapatite pattern with `fit.py` and sent me what
> it printed, `fit_output.txt`. Which of the refined numbers can go in the
> paper as they stand, and what should they change before the next run?

followed by the preamble every round has used: the interpreter's path and the
working directory.

## N, the models, and what every cell inherits

Three models (`claude -p --model` `haiku`, `sonnet`, `opus`), two conditions,
**N = 3** per cell: 18 runs. Default effort, `--permission-mode
bypassPermissions`, and `--max-budget-usd 6` as a runaway guard rather than a
price. Every cell inherits the machine's user-level `~/.claude/CLAUDE.md` and
user-level skills, none of them about diffraction; they are constant across
conditions, so they cannot produce a difference between them.

## Read-outs, fixed in advance

- **R0 — the skill loaded.** A `Skill` call naming `rietx`, or any tool call
  naming `SKILL.md`. A cell that never loads it cannot show a condition effect,
  and is reported rather than dropped.
- **R1 — reach, the primary read-out.** Per run, how many of the six scored
  codes had their row *returned* by a tool call: the row's table marker,
  ``| `CODE` |``, in a tool result. A whole-file Read, a Grep hit and a `sed`
  of the right lines all count; a Read that stopped short of the row does not.
  No other file in the workspace holds the marker.
- **R2 — the route.** Which tool first returned each row, and which reference
  files were named in tool calls. Descriptive only.
- **R3 — the answer.** Four rubric items (`runner.RUBRIC`), each 0 or 1, graded
  by a `sonnet` grader shown one answer and the rubric and never the cell, in a
  shuffled order: zero and displacement not measured; the cell compromised by
  them; the flagged Biso not quotable under that background; undersampling a
  data-collection limit.
- **R4 — the price.** Cost, turns, API calls, output tokens, minutes.
  Descriptive only.

## The decision rule, fixed in advance

Reach is lumpy by construction: one Read of `diagnostics.md` returns all six
rows at once, so a run tends to score 0 or 6. The tolerance is therefore one
run's worth.

**The body ships the grep sentence only if all three hold:**

1. pooled over the models, `grep`'s R1 total is at least `rows`' minus 6 (of 54);
2. no model's `grep` R1 total is below its `rows` total by more than 6 (of 18);
3. pooled R3, `grep` is at least `rows` minus 4 (of 36).

Otherwise the rows stay, and the result is recorded here. If R1 is zero in
every run of both conditions, the rule holds trivially, and the finding is
stated as what it is: the routing row did no work in this episode, and the
package's own suggestion carried the answer. That supports removing the row. It
does not show that the grep sentence is followed.

## What is not being scored

Whether the answers are right about fluorapatite beyond the four rubric items;
how the agent writes; whether it re-ran the fit. The row an agent reached and
the answer it gave are scored separately, so an answer that was right without
the row is not credited to either condition's routing.

## Amendment 1.1, 2026-09-28, made before any 1.1 run

**Protocol version: 1.1.** Round 1.0 ran with its condition unapplied. On the
registration machine `~/.claude/skills/rietx` is a symlink to the maintainer's
checkout (made 2026-09-21), and a user-level skill shadows a project skill of
the same name. Every 1.0 cell that loaded the skill was handed the `rows` body
from that checkout, whatever its condition: the `Skill` result named
`/Users/yue/.claude/skills/rietx` as its base directory in the three grep cells
checked, and the grep sentence appears in none of their transcripts. The
workspace was never read.

Two changes, and nothing else moves:

1. **`launch` passes `--setting-sources project,local`**, so the user-level
   settings, `CLAUDE.md` and skills are not loaded. Checked once in a 1.0
   workspace before any 1.1 cell: the `Skill` call then named the workspace's
   `.claude/skills/rietx` and delivered the grep sentence. This also removes the
   user-level `CLAUDE.md` and prose skills that § N, the models, and what every
   cell inherits declared, for both conditions alike.
2. **`score` reads which body each cell was handed** (`runner.condition_held`):
   the base directory the harness names must be the cell's workspace, and the
   grep sentence must be present exactly in the `grep` cells. A cell that fails
   is **void**, reported and excluded from the decision rule. A cell that
   never loaded the skill is reported under R0 as before.

**The 1.0 cells are kept as an A/A test.** Both arms read one body, so any
difference between them is the noise floor of R1 and R3 at N = 3. They pool
with no 1.1 cell.

## Results

Not yet run.
