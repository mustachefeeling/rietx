# WP-1017 — GUI manual, in-app help, onboarding

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1011…WP-1016 (soft — chapters can land as their panels do)

## Goal

The GUI is documented where the theory manual lives, helps from inside the
app, and onboards a first-year PhD student without a wizard that hides the
real UI.

## Context

- **Inside `docs/manual/`** — same Sphinx/MyST/furo tree, same `-W`, same
  guards (`tests/test_manual.py`); a separate doc root would need its own
  guard set for no benefit. Three layered chapters matching the audience
  gradient:
  - `gui-quickstart.md` — install (`pip install pxrd-refine[gui]`) → open →
    fit → read the report.
  - `gui-guide.md` — panel by panel, including *when to branch* (the
    history worktree is the differentiator; teach the workflow, not just
    the buttons).
  - `gui-power.md` — the **normative `.pxt` text-format spec**,
    keyboard/palette, and the console-to-script transition — the API-echo
    story as the on-ramp to the Python API.
- The manual's anti-divergence rules apply and are executable
  (`tests/test_manual.py`): fenced constants are MyST substitutions
  injected from the live package in `docs/manual/conf.py` — **the pxt
  format version becomes a fenced constant injected from
  `gui.textdoc.FORMAT_VERSION`**, so a format bump that misses the manual
  fails the build. A new fenced constant needs a `conf.py` line *and* a use
  in a chapter.
- In-app help: tooltips from `static/help.json`, each with a "learn more"
  anchor into the built manual; `tests/test_gui_help.py` asserts every
  anchor exists (dead-link guard, same spirit as `test_manual.py`).
- First run: a **non-modal progressive checklist** (Load pattern → Load
  structure → Check instrument → Run → Read the report) — never a modal
  wizard; state in `ProjectDoc.ui`.

### Inherited

From **WP-1014** (import & in-GUI editing, landed 2026-07-30): **the onboarding
path now exists and is the empty state.** With no project open the app renders the
import wizard itself (`panels/Model.svelte`, the same component that is the model
editor when a project *is* open), so "how do I start?" is answered by the screen
rather than by a manual page. What the manual owes it is the part the wizard
cannot say in a form: why the instrument step refuses to default (an anode nobody
chose becomes a wavelength in every refined cell), what the aniso opt-in actually
changes (which parameters a plan frees), and why the pattern step names a
*reader* rather than a file type.

Also: the wizard's own copy is deliberately terse and every step already carries
its "why" as a `title` or a muted line — if the manual repeats those sentences
they become two authorities. Link to them instead, or move them.

From **WP-1013** (landed 2026-07-30): the **text pane** is the surface this manual
has the most to explain, and three of its facts are not discoverable from the UI.
It is a *mode*, not a tab — the header's `Text` button and the palette's `t` — so a
chapter that walks the tabs will miss it entirely. `⌥`-drag is a **rectangular
selection**, which is the entire reason the `.pxt` format aligns its columns, and
the pane's footer says so in one line that a manual should expand rather than
repeat. And **a re-render discards the user's own comments**: the pane warns when
the buffer has gained comment lines, but the flow ("apply, then re-read") wants
stating once, properly.

`textdoc.FORMAT_VERSION` is still owed to this WP as a **fenced constant**
(WP-1009's own note says a bump that misses the manual must fail the docs build),
and the `.pxt` grammar chapter should quote `gui/src/lib/pxt.ts`'s token
vocabulary rather than restating it — that array is already pinned to
`textdoc._KEYWORDS` by `test_textdoc.py::test_the_highlighter_quotes_the_parsers_words`,
so a manual that quotes it inherits the guard.

One sentence is worth carrying verbatim into the conflict/undo chapter, because it
is the pane's whole safety story: **there is no merge and no force-apply** — a
document regenerated from state has one authority, so a stale buffer re-reads and
re-applies. The reason is sharper than "merging is hard": the loser's document also
carries the winner's *old* values for every row it did not touch, so applying it
anyway would silently revert them.

From **WP-1011** (landed 2026-07-30): **the command palette is already the
manual's index, and it is executable.** Cmd-K lists every command with the Python
call it makes (`ref.set_vary(glob, True)`, `ref.run_stage(stage)`,
`project.doc.ui["simple"]`), and the console echoes the same string when a control
is clicked — so the chapter that teaches "the GUI is a front for the API" should
quote the palette rather than restate it, and any command added later appears
without the manual being edited. The shortcut set to document is `r` run, `.` run
the selected stage, `Esc` cancel, `f`/`x` free/fix the filtered selection, `/`
focus the filter, Cmd-K palette.

Two things the onboarding path must say plainly, because both are surprising and
both are deliberate. **The filter box is the selection** — a bulk free acts on the
glob, not on ticked rows, because one glob is one history node. And **Simple mode
hides the rows nothing can free** (locked, tied, mode-fixed) along with bounds and
transforms; it reports the count it hid, and Advanced brings them back.

From **WP-1012** (history/report panels, landed 2026-07-30): the palette gained
`?` (report) and `h` (history), and there are now **five things the report panel
says that a user will misread unless the manual says them first** — every one is
the FitReport's own design showing through, so this chapter is where they get
explained rather than in tooltips:

- **A suggestion with no Apply button is not a broken button.** Four `ActionKind`s
  are advice (`report/apply.py`'s `RECIPES`), and the note beside them *is* the
  action. The two background-flexibility ones are the interesting case: they are
  advice because a more flexible background lowers Rwp *while* biasing ADPs up and
  scales down, and the statistic that catches it (`BACKGROUND_ABSORPTION`) is not
  in the report — so there is no honest one-click version.
- **A greyed suggestion with "vetoed:" is the engine agreeing with you and having
  already handled it.** Worth a sentence, because it looks like a refusal.
- **"could not rule out" is the headline, not a footnote.** Measured on the WP's own
  fixture: applying `refine_zero_shift` on a fit whose *cell* was wrong improves Rwp
  from 21.6 % to 9.3 % by putting the error in the wrong parameter, and the report
  said so in advance (confidence capped at 0.5, both templates listed,
  `separable=false`). This is the best worked example in the repo of why the
  never-a-confident-wrong-singleton rule earns its keep — use it.
- **The predicted Δχ² is one number for the whole report**, not per suggestion, and
  it is not a bound (16.19 predicted, 16.33 observed for a cell correction). The
  panel prints it once and says so; the manual should explain why it cannot rank.
- **Undo is a checkout**, and a checkout throws the fitted curves away because they
  described the values it replaced. Users will read the empty plot as a crash.

One onboarding fact: **boot-to-interactive is 104–200 ms** measured in Chrome for
Testing (load → the parameter table's first row), so "it feels instant" is a claim
this chapter may make.

From the **v1.0 GUI plan** (2026-07-29): `gui-power.md` is where the
provisional status of the HTTP routes and `.pxt` format is stated
user-facing (schemas frozen at v1.0, wire/text surfaces provisional) —
WP-1003 states it in the release notes; this chapter is the other half.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): add an
**indexing walkthrough** as an onboarding path — it is the natural entry point
for a user with a pattern and no CIF, which is the audience least served today.
`docs/manual/indexing.md` already exists from WP-1020 for the theory; this
chapter covers the panel (WP-1027). The one thing the walkthrough must teach
rather than gloss is that **a candidate list with no high-confidence entry is a
result, not a failure** — the whole module is built so that "the data cannot
distinguish these" is sayable, and a user who reads that as a bug will go
looking for a setting to force an answer.

From **WP-1009** (text document, landed 2026-07-30): `gui.textdoc.FORMAT_VERSION`
is the fenced constant this WP was asked to inject into the manual (the `pxt 1`
header line), and `gui.textdoc.VALUE_DIGITS` is worth injecting beside it — the
manual has to state that the text view renders **12 significant digits and is
lossy**, and why that is safe (a typed number is compared against the rendered
current value, so an unedited apply is a no-op). Two more things a manual chapter
should say because they are decisions, not accidents: comments in the text pane
do **not** survive a re-render, and a glob line like `profile.* @` is bulk sugar
that the next render expands into one line per parameter.

From **WP-1010** (frontend scaffold, landed 2026-07-30): the app's help text has a
home — `panels/Stubs.svelte` is where "this build can do X" is rendered from
`capabilities().features`, whose flags are derived predicates, so an in-app
capability list cannot drift from the package. Two constants worth injecting into
the manual beside the textdoc ones: the dist is **committed** (a manual chapter
should say `npm --prefix gui run build` is only for contributors, never for users)
and plotly is served from the installed package rather than bundled, which is why
`[gui]` is a plotly-only extra.

## Non-goals

- No screencasts/video, no hosted docs decisions (that is WP-1003's
  release scope).
- No autodoc API reference (0604's decision stands — a rendered API
  reference is its own document with its own failure modes).
- No restating theory — the GUI chapters link into the existing theory
  chapters rather than duplicating equations.

## Tasks

- [ ] `gui-quickstart.md` + toctree wiring; builds `-W`-clean.
- [ ] `gui-guide.md` — panel by panel, when-to-branch workflow section.
- [ ] `gui-power.md` — normative `.pxt` spec with `FORMAT_VERSION` as a
      fenced constant (conf.py line + chapter use), keyboard/palette table,
      console-to-script story.
- [ ] `static/help.json` + tooltip wiring + "learn more" anchors;
      `tests/test_gui_help.py` dead-link guard.
- [ ] First-run progressive checklist (non-modal), persisted dismissal.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_gui_help.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-0604's manual architecture (fenced constants, `*Source:*` lines,
  cited-bib guard) — the machinery these chapters extend.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.
