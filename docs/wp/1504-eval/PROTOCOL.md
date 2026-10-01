# WP-1504: the figure round

Registered 2026-10-01, before any run. A change after the first run goes in a
dated amendment at the end, and the text above it stays as registered.
`run.py check` fails if this file stops quoting what `run.py` launches.

## The question

Can an agent given only the skill and a shell make the structure figures a
chemist asks for? The round asks it twice. The first time is on the surface
WP-1470 shipped. The second is after WP-1501 to 1503 added cuts, extents and
the figure's report on itself. It also asks which numbers of `fig.report` an
agent reads, because a field with no reader is a claim with no use.

## The conditions

Each condition is a commit, exported and installed into a venv of its own.

| condition | commit | what it is |
|---|---|---|
| before | `5304b85ab092f629a0392b43966df8fda76563dd` | WP-1470's merge (#498): `render_structure` and the dict from `build` |
| after | `97c1d9cc1344a73983fe2e1f2a6d287761e29d13` | WP-1503's merge (#583): `keep`, `select` and the cut verbs, `build(extent=)`, `fig.report`, `view="auto"`, `fig.recipe` |

No commit on `main` touched the figure surface between 97c1d9cc and this
registration.

`run.py prepare ROOT CONDITION` exports the package and its skill from the
commit (`pyproject.toml`, `README.md`, the two licence files, `src`,
`docs/skill`) to `ROOT/trees/CONDITION`. It installs that tree with `[viz]`,
not editable, into `ROOT/venvs/CONDITION` on Python 3.12, and boots
`fig_trace.py` there through a `.pth` line. `ROOT` sits outside every
checkout, so no run inherits a project's `CLAUDE.md` or skills.

A run's workspace holds two things: the task's CIF, and the skill as that
venv's `rietx skill --install WORKSPACE --copy` writes it. The agent is
launched as

```
claude -p PROMPT --model sonnet|opus --session-id ID
  --permission-mode bypassPermissions --output-format json
  --strict-mcp-config --max-budget-usd 12 --disallowedTools WebFetch WebSearch
```

with the workspace as its directory, at the default effort. Its environment is
the launching shell's, less `VIRTUAL_ENV` and that venv's `bin`, plus
`RIETX_FIG_RUN` naming the run.

### What every run inherits

- The user-level `~/.claude/CLAUDE.md` and skills. On the registration machine
  the skills are `synced`, `tufte`, `workflow-sync`, `yue-docs-style`,
  `yue-figure-style` and `yue-prose`. Two of them are about figures and prose.
  They are the same for every run, and each score records the skills the agent
  invoked.
- Claude Code 2.1.286, and whichever models `sonnet` and `opus` resolve to on
  the day. Each score records the model ids its transcript names.
- The maintainer's checkout is on the same disk. A run that goes looking for it
  shows in the score's `outside` list and in its trail.

### Where this departs from the WP

- The WP gives the before condition "the manual as it was". The hosted manual
  can only be served as it is today, and today it describes the after surface.
  So neither condition gets the web tools. Each condition's documentation is
  its skill, whose references are generated from its own package, and the
  package's docstrings. A `curl` through the shell is not blocked, and would
  show in the trail.
- MCP servers are off in both conditions. The maintainer's filesystem server
  would otherwise reach outside the workspace.
- Each prompt names the file to save and says that rietx is installed. A
  chemist handing over the job would say both. No prompt names a function.
- `--max-budget-usd 12` is a runaway guard. It is several times the dearest
  run the menu's prior allows.

## The tasks

Six tasks from the 21 phases in `tests/data/polyhedra_phases.json`. Each
CIF is written by `run.py`'s `cif_text` from the fixture row, so both
conditions read the same bytes. The CIF's first line names the row's source.

Each prompt below is followed by a blank line and this preamble, with the
paths filled in:

> rietx is installed for the python interpreter {python}. Your working directory is {workspace}.

1. **rutile**, from `rutile.cif`:
   > rutile.cif is rutile, TiO₂. Draw me its chains of edge-sharing TiO₆ octahedra, looking down c. Save the picture as figure.png.
2. **gypsum**, from `gypsum.cif`:
   > gypsum.cif is gypsum, CaSO₄·2H₂O. Draw one layer of the structure with its water molecules, seen edge-on. Save the picture as figure.png.
3. **calcite**, from `calcite.cif`:
   > calcite.cif is calcite, CaCO₃. Draw only the carbonate groups: no calcium and no polyhedra. Save the picture as figure.png.
4. **nac**, from `nac.cif`:
   > nac.cif is Na₂Ca₃Al₂F₁₄ (NAC). Draw its AlF₆ octahedra as a 2×2×1 block of unit cells. Save the picture as figure.png.
5. **lab6**, from `lab6.cif`:
   > lab6.cif is LaB₆. Draw its B₆ octahedra without the La–B bonds. Save the picture as figure.png.
6. **fap**, from `fluorapatite.cif`:
   > fluorapatite.cif is fluorapatite, Ca₅(PO₄)₃F. I need a figure for print looking down c, 17 cm wide at 300 dpi, with a legend saying which colour is which atom. Save it as figure.png.

## The grid

Six tasks, two conditions, two models (`sonnet` and `opus`) and three
repeats: 72 runs, each judged once. A run is named
`<task>-<condition>-<model>-<repeat>`. Runs go one at a time. No run starts
without the maintainer's pick from `run.py --menu`.

## The read-outs

Fixed now, before any run.

- **R1, done.** An Opus judge reads `figure.png` against the task's criteria
  and the common one below. A run is done when the judge answers yes to every
  criterion and the mechanical checks pass. An answer of unclear counts as not
  done. The maintainer looks at every figure scored done, in
  `runs/<run>/figure.png`.
- **R2, renders.** Each `render_structure` call the agent made, with the pixel
  size of the image it returned. Also each `build` call with its `extent`, and
  how often each cut verb was called. A call is the agent's when it was not
  made from inside another traced call.
- **R3, looks.** Each `Read` that returned an image, with the pixel size the
  model received. WP-1503 states a look's price as width × height / 750
  tokens as a hypothesis, and this is the evidence for it.
- **R4, tokens and wall time.** Tokens are summed once per API call, the last
  record of each winning (`tests/eval_agent_surface/trail.py`). Cost and wall
  time are what `claude -p` reports.
- **R5, the report's fields.** On the after condition, which fields of
  `fig.report` the agent read. The shim logs the first read of each field in
  each process. A `repr`, a `str` or a `__dict__` of the report counts as
  reading every field, and is logged as `whole`. The handover gives one line
  per field: read in k of n after-runs, or never read.
- **R6, where it stalled.** One line per run, written from its trail by the
  session that collects it.

Each score also records, as checks on the round rather than results: the skills
the agent invoked and the files of the rietx skill it opened (did the
condition reach the run), the tool calls that errored, and the absolute paths
it named outside its own workspace, venv and temporary directories.

## The mechanical checks

- Every task: `figure.png` exists.
- fap: the width is 2005-2011 px, since 17 cm at 300 dpi is 2007.9 px. The
  PNG's `pHYs` chunk reads 299-301 dpi.

## The judge

Each figure is copied alone into a directory of its own, and `claude -p` runs
there with `--model opus --allowedTools Read --strict-mcp-config`. The prompt
is this template, with the task's prompt and its numbered criteria filled in:

```
You are scoring a figure that an AI agent drew for a chemist. The chemist asked:

> {prompt}

The figure is figure.png in the current directory. Read it with the Read tool and look at it. Read nothing else. Judge it against each criterion below. Answer yes, no or unclear, with one short sentence saying what you saw. Judge only the criteria: do not reward effort or penalise style.

{criteria}

Reply with only a JSON object, no prose around it:
{"criteria": [{"n": 1, "verdict": "yes", "saw": "..."}, ...]}
```

The criteria, in the order the judge gets them:

- rutile
  1. Ti–O octahedra are drawn as polyhedra.
  2. The view is down c: the unit-cell outline is a square.
  3. Octahedra stand at more than one chain position in the cell, such as its corners and its centre.
- gypsum
  1. Exactly one layer is shown: the Ca and SO₄ make one band, not two or more stacked bands.
  2. Water is shown on the layer: O atoms each bonded to two H atoms.
  3. The layer is seen edge-on: it runs across the picture as a band, not face-on as a sheet.
- calcite
  1. No Ca atoms are drawn.
  2. No polyhedra are drawn.
  3. Carbonate groups are drawn: each C bonded to three O in a triangle.
- nac
  1. Al–F octahedra are drawn as polyhedra.
  2. The picture covers two unit cells along a, two along b and one along c: not a single cell, and not a larger block.
- lab6
  1. B₆ octahedra are visible: six B atoms bonded to each other, or drawn as an octahedral polyhedron.
  2. No bonds join La atoms to B atoms.
- fap
  1. The view is down c: the cell outline is a rhombus with a 120° angle, and the channels along c are seen end-on.
  2. A legend names the atom types beside the colour each is drawn in.
  3. The legend's colours match the colours of the atoms in the picture.
- every task, last: The figure is not cut off: no atom or polyhedron is clipped by the frame's edge.

### The judge is checked before it scores a run

`reference_figures.py` draws two figures per task on the after surface.
`<task>-right.png` meets every criterion, which also shows that each task can
be done. `<task>-default.png` is `render_structure` given only the CIF, and
misses at least one criterion of every task. `run.py judge-references ROOT`
puts all twelve to the judge and writes `references.json`. The round's
read-out R1 is trusted only if the judge passes every right figure and fails
every default one. A disagreement is fixed in the criteria before any run is
judged, and the fix is an amendment below.

## The instrument's own check

`prepare` draws all six CIFs in the condition's venv, through the shim, and
stops unless four things hold. There are six render rows at 160 px. The
signature of `render_structure` starts with `structure`, so the shim is
invisible to `inspect`. A report exists on the after tree and not on the
before tree. On the after tree, the read of `hidden` and the printed report
were both logged. `run.py check` runs the same draw in this repository's venv.

## What is committed

`runs/<run>/` holds `score.json`, the run's own rows of the trace, the trail
(one line per tool call, and the bill), and the final figure at most 800 px
a side. `references.json` holds the judge's check. Everything else stays in
`ROOT`: full-size figures, venvs, workspaces and transcripts.

## Amendment 1.1, 2026-10-01: the user-level skills stay out

The judge check passed first, 12 of 12 for $1.30. Pilot A then ran under the
text above, and both of its runs loaded the user-level `yue-figure-style`
skill. `gypsum-after-sonnet-1` loaded it as its first act and never imported
rietx. It drew the layer in matplotlib from the CIF's coordinates. So a
user-level skill about figures does more than add a constant. On a figure
task it can choose the route, and then the run measures that skill instead of
the rietx one. The WP's condition is the skill and a shell, and the
maintainer's own skills were never part of it.

From 1.1 every run is launched with `--setting-sources project,local` as
well. Two Haiku probes on 2026-10-01 ($0.03) checked what that changes. The
six user-level skills drop out. The workspace's `rietx` skill still loads,
and so do Claude Code's built-in skills, one of which is `dataviz`. The
user-level `~/.claude/CLAUDE.md` still loads too. It stays a declared
inheritance, constant across runs. The judge is launched as before, because
it was checked that way and its `--allowedTools Read` gives it no skill.

The two pilot runs are kept in `pilot-1.0/`, each score marked
`"protocol": "1.0"`. They pool with no run after this amendment. `run.py`
stamps each launch with its protocol version, and the menu and the table read
only runs of the current one.

| pilot run (1.0) | done | $ | minutes | API calls | renders | looks | skills invoked |
|---|---|---|---|---|---|---|---|
| gypsum-after-sonnet-1 | no (a Ca cut by the frame) | 0.21 | 0.8 | 8 | 0 | 5 | yue-figure-style |
| gypsum-after-opus-1 | yes | 1.42 | 5.3 | 21 | 11 | 5 | rietx, yue-figure-style |

## Amendment 1.2, 2026-10-01: a task across cells, and two checks no figure passed by luck

Written after the 1.1 pilot (one gypsum run per model) and before any round.
It makes four changes, and the judge is checked again before it scores a run.

### A seventh task, which one cell cannot answer

NAC was the only task that needed more than one cell, and the judge can only
count its block by eye. The seventh task needs a chain several cells long,
and one chain picked out of many.

7. **chains**, from `rutile.cif`:
   > rutile.cif is rutile, TiO₂. Draw a single chain of its edge-sharing TiO₆ octahedra from the side, four unit cells long. Save the picture as figure.png.

Its criteria:

1. Ti–O octahedra are drawn as polyhedra, each sharing an edge with the next.
2. Exactly one chain is shown, seen from the side: it runs across the picture, not end-on.
3. The chain holds four or five octahedra.

On the after surface the chain is `component(g, atom, via="edges")` over a
block four cells along c, then `keep`. That gives 4 Ti and 4 octahedra, with
no bond left dangling. Adding `complete=True` brings back 22 Ti of the
neighbouring chains, each drawn bare. The grid grows to 7 tasks and 84 runs.

### Two checks every figure now gets

After the registered "not cut off" check, the judge asks two more of every
figure:

- Every bond drawn joins two atoms that are both drawn: no bond ends in empty space.
- Polyhedra are whole: none is missing a corner, and no atom of the kind at their centres is drawn without one.

Three measurements on the after surface, all on 2026-10-01, are why.

- `render_structure(..., hidden=("Ca",))` removes the Ca but draws the O half
  of every Ca–O bond. The calcite figure is covered in these stubs, and its
  report reads `dangling_bonds = 0`. The report leaves out by design the
  halves a `hidden=` species took away. LaB₆ with `hidden=("La",)` does the
  same. So the report cannot catch a stub, and only the picture can.
- `keep` never draws part of a polyhedron. It drops a polyhedron that lost a
  corner and counts it in `cut`. So the failure a picture shows is a centre
  atom drawn bare.
- One cell already draws bare centres. The atoms brought in as the far ends
  of bonds just outside the cell carry no polyhedron. Rutile draws two Ti
  bare (above and below the body centre, at z = −½ and 1½). Fluorapatite
  draws four P bare, beyond the side faces. NAC, gypsum, calcite and LaB₆
  draw none. No verb removes them and no field of the report counts them.

The 1.1 references met neither check in every task, so three recipes in
`reference_figures.py` change. Rutile and fluorapatite drop their bare
centres with a mask read off the dict. Calcite keeps the connected pieces
holding a C once the Ca is gone: 12 C and 36 O, C–O bonds only. Two other
routes were measured and refused. `keep` of everything but Ca leaves the O
whose C lies outside the cell. `keep` of the C with `complete=True` left 16
O bonded to no C.

### The judge launches without the user-level skills too

The judge now runs with `--setting-sources project,local`, as the agents do
since 1.1. All 16 judge sessions under 1.0 and 1.1 used `Read` alone and
invoked no skill, so no verdict on record changes. But the flag changes how
the judge is launched, and the new criteria change what it is asked. So the
check of § The judge runs again, on the seven pairs drawn by the amended
`reference_figures.py`, before it scores a run. The 1.1 check is kept as
`references-1.1.json`.

### Two corrections to the text above

- `RIETX_FIG_RUN` holds `<run>@<session>` since the trace key fix on
  2026-10-01, not the run's name. The registered section says "naming the
  run".
- `fig_trace.py`'s comment on `_VALUES` now says what `_short` does: a
  rotation passed as `view` is recorded in full. Both prepared venvs were
  given the corrected file. Its code did not change.

The two 1.1 pilot runs are kept in `pilot-1.1/`, and pool with nothing after
this amendment.
