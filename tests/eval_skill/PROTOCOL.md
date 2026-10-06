# Runner protocol — the skill eval suite (WP-1905)

**Protocol version: 1.0**, registered 2026-10-04 **before any scored round**.
Bump it on any change that alters comparability: the case set, a prompt, a
grader or its window, the conditions, the models, N, the read-outs or the
decision rule. Results are appended below the registration and the
registration is not rewritten once a cell has run; a change is a dated
amendment, made before the first run it governs, in the form of
`tests/eval_skill_placement/PROTOCOL.md` § Amendment 1.1.

This is the repository's fourth eval protocol. It pools with nothing in
`tests/eval_report_agent/`, `tests/eval_agent_surface/` or
`tests/eval_skill_placement/`, nor with WP-1904's pilot
(`docs/wp/1904-eval/pilot/`), whose cases and graders differ from these. It
borrows their discipline (`tests/CLAUDE.md` § Four eval protocols): registered
first, the condition enforced in the workspace rather than the prompt, the
read-outs fixed in advance, a cell that comes back split reported as split, and
the condition checked off each run's transcript.

The instrument is two scripts: [`build.py`](build.py) makes the plugin a round
runs, and [`readout.py`](readout.py) turns its result into the read-outs below.
`tests/test_eval_skill.py` holds this document, the cases and both scripts in
agreement, and runs no model.

## The question

> **Does a change to the skill body keep or improve what an agent does with
> rietx, at lower cost, measured against today's body and against no skill?**

The answer decides whether a body change merges: WP-1906's rewrite first, and
WP-1532's fourteen passages after it. It is asked of `SKILL.md` and the reference
files an agent opens through it, never of the package.

## The conditions — the tree handed to `build`

| condition | how a round gets it |
|---|---|
| today's body | `build.py docs/skill/rietx <out>`: the committed tree at the round's commit |
| a candidate | the same command with `--body FILE`, which swaps `SKILL.md` in the copied tree; or another tree passed as `<tree>` |
| no skill | the harness's without arm: the same cases, the same isolated runs, no plugin loaded |

The skill tree is not a plugin and does not become one (a manifest under
`.claude/skills/rietx/` would change how every session in this repository loads
the skill), so `build.py` copies the tree into a throwaway plugin. **The
condition is the tree handed to `build`, never the prompt**: every case's
prompt is identical in every condition. Two trees are two builds and two runs
of one suite. Today's body runs `--ablation with-without`, which carries the no
skill arm; a candidate runs `--ablation none`, because its without arm would
repeat the first's.

A result document names none of this, so each build writes `build.json` beside
its manifest: the tree, the body, `skill_sha256`, `tree_sha256`, the
interpreter, the commit and the cases. `readout.py` reads it from the result's
`suite.root` and prints both hashes beside every result. **One `<out>` per
condition**, kept until the round is read out: a rebuild into the same
directory replaces the stamp a result is read against.

**The condition is checked off each run's transcript, never assumed.** Each
run is a `claude -p` child in an isolated home with only the plugin loaded,
but a skill copy can still be reached: the checkout's `docs/skill/rietx`, or
the package's own copy through `rietx skill` or `skill_path()` (the checkout's
tree under an editable install). `readout.py` reads, per run, the base
directory the `Skill` tool named. A with-arm run whose skill loaded from
outside the round's plugin or its own run directory, and a without-arm run in
which a skill fired, are **void**: reported, and excluded from the decision
rule (the placement round's Amendment 1.1 rule).

## Cases

A case is a directory under [`cases/`](cases) holding `prompt.md`, its graders
under `graders/`, and, where its workspace starts with files, an `inputs.txt`
naming them. **Cases are written from failures, never from the body**: issue #661's
wrong turns, WP-1504 round B's stalls, the placement round's episode. **A
case's expected answer is a measurement** (`tests/CLAUDE.md` § An eval's
expected answer): every numeric window is read off a converged fit and the
GSAS reference, and its description carries the measurement with its date,
venv and platform. A window changed is an amendment.

Each `description` opens with the case's role (`build.ROLES`), which says what
its score is evidence of:

- **Regression guard.** Today's body passes it at 3 of 3 on both models and no
  skill fails it. A candidate that loses here has lost something today's body
  does.
- **Deciding case.** Today's body fails it: the case a rewrite is judged on.
- **Should fire.** and **Should not fire.** Tier 0, § Tier 0 below.

| case | tier | role | comparable graders (scored in both arms) | what its score is evidence of |
|---|---|---|---|---|
| `fap-judge` | 2 | Regression guard | four `llm` rubric items on the final answer | whether an agent handed a colleague's printed fit says which numbers may be quoted. WP-1904's pilot: Haiku 4 of 4 with the skill, 3 of 4 without; Sonnet 4 of 4 in every arm at N = 2, a ceiling, where it can show a candidate losing what no skill keeps but never the skill helping |
| `fap-fit` | 1 and 2 | Deciding case | `cell_a`, `cell_c` (weight 2, regex on `report.md`), `report_written`, `ran_fit`, `caveats_named` (`llm` on `report.md`) | whether the body takes an agent from two files to a converged cell quoted with its esd, and a caveat tied to this fit, inside the run's limits. The pilot's current body lost it to no skill on Sonnet, 0 of 2 against 2 of 2 |
| `fap-gsas-reproduce` | 1 | Regression guard, provisional | `cell_a`, `cell_c` (weight 2), `o7_coordinate`, `rwp` (regex on `answer.json`), `file_wavelengths` (regex on `reproduce.py`), `ran_fit` | whether an agent maps another program's refinement onto rietx's parameters: issue #661's mapping rows (wavelengths, zero against displacement, background, width units, coordinates). No body has run it; the first round decides guard or deciding case by the definitions above, and the description is changed by amendment |

`skill_fired` (all three) and `opened_reference` (`fap-judge`) are `with-only`:
indicators beside the score, never in it.

**A report promised is a report not written** (WP-1904 finding 3). A run that
ends saying it will write `report.md` or `answer.json` once a background fit
finishes scores as not written: the file graders read the workspace when the
run ends, a timed-out run is graded on what it produced, and nothing here
re-grades either.

The prompts, verbatim. `@PYTHON@` is `build.py`'s mark for the interpreter
(`--python`), substituted at build; everything else reaches the agent as
written.

### `fap-judge`

> My colleague refined our fluorapatite pattern with `fit.py` and sent me what
> it printed, `fit_output.txt`. Which of the refined numbers can go in the
> paper as they stand, and what should they change before the next run?
>
> rietx is installed for the python interpreter @PYTHON@. Your working
> directory holds fit.py, fit_output.txt, FAP.XRA and fluorapatite.cif.

### `fap-fit`

> FAP.XRA is a lab powder pattern of fluorapatite, Ca5(PO4)3F, collected on a
> Bragg-Brentano diffractometer with Cu Kα radiation (doublet, no
> monochromator). fluorapatite.cif is the starting model. Refine the structure
> against the pattern with rietx and write me a short report.md: the refined
> cell parameters a and c with their esds in value(esd) notation, as in
> 1.2345(6) Å, and a list of which refined numbers you would not yet put in a
> paper and why.
>
> rietx is installed for the python interpreter @PYTHON@. Your working
> directory holds FAP.XRA and fluorapatite.cif.

### `fap-gsas-reproduce`

> FAP.EXP is GSAS's converged Rietveld refinement of FAP.XRA, a powder pattern
> of fluorapatite, Ca5(PO4)3F, from a lab Bragg-Brentano diffractometer with Cu
> Kα radiation. I want to know whether rietx agrees with GSAS on these data, so
> reproduce that refinement with rietx: the same model, with the same
> parameters refined. Save the script you ran as reproduce.py, and write
> rietx's refined values to answer.json as {"a": ..., "c": ..., "o7_z": ...,
> "rwp": ...}: a and c in Å, o7_z the fractional z coordinate of the site
> labelled O7, and rwp as a fraction, not a percentage.
>
> rietx is installed for the python interpreter @PYTHON@. Your working
> directory holds FAP.XRA and FAP.EXP.

## Tier 0 — triggering

Twenty prompts under `cases/trigger/`, ten that should load the skill and ten
near-misses sharing its vocabulary that should not (agentskills.io's
description recipe). Each is graded by one `tool_used: Skill` grader with
`arm: both`: `min: 1` on the ten, `min: 0, max: 0` on the near-misses, and on
all twenty an `input_match` counting only calls that load rietx
(`readout.FIRED`), so another skill firing on a near-miss is not scored as
rietx firing.
Judge-free, no fixture, `max_turns: 4`, and no shell in `allowed_tools`; a
round's `--allow-tools` grant reaches every case it runs, so the round's
command line, not the case, decides whether a near-miss can reach one.

**Tier 0 runs as its own round, `--tag trigger --ablation none`, with neither
`--scaffold` nor `--allow-tools`**: a without arm cannot fire a skill, so it
would measure nothing (the three cases above carry the tag `fap`), and with no
grant a near-miss has only the read-only tools its case lists. Its read-out is two rates per model, from
`readout.py show`: the **fire rate**, runs of the ten "Should fire." prompts in
which `Skill` was called (of 30), and the **quiet rate**, runs of the ten
"Should not fire." prompts in which it was not (of 30).

**Tier 0 waits on the maintainer's review of its twenty prompts.** No tier-0
cell runs before it; a prompt the review changes is changed, and quoted below,
in an amendment made before the first tier-0 run.

**Reviewed 2026-10-06, before any tier-0 run.** The maintainer changed two
prompts and passed eighteen as written. `quiet-bragg-law` became
`quiet-scherrer`. A textbook question repeated what `quiet-density` tests, and
the near-miss that matters is a powder-XRD task with no refinement in it.
`fire-unknown-cell` lost its contradiction: it named a peak list and then asked
for a cell "from the powder pattern". The table quotes the reviewed text.

| case | role | prompt |
|---|---|---|
| `fire-diagnostics` | Should fire. | After my rietx fit the report lists FLAT_DIRECTION and HIGH_CORRELATION. What should I change before I run it again? |
| `fire-draw-structure` | Should fire. | Draw the crystal structure in perovskite.cif as a PNG, with the octahedra shown and the view down the c axis. |
| `fire-heating-series` | Should fire. | I collected 40 powder patterns while heating from 25 to 800 °C. Refine them in sequence and plot the cell volume against temperature. |
| `fire-judge-calibration` | Should fire. | My student fitted our LaB6 standard with rietx and sent me the FitReport. Is it good enough to save as the instrument profile? |
| `fire-lebail-cell` | Should fire. | Do a Le Bail fit of my synchrotron pattern, sample.xye, so I get the lattice parameters without needing a structure model. |
| `fire-pawley-spacegroup` | Should fire. | Run a Pawley fit of pattern.xy in P6_3/m so I can check whether that space group accounts for every peak. |
| `fire-quartz-rietveld` | Should fire. | I have a lab XRD pattern of quartz, quartz.xy (Cu Kα, Bragg-Brentano), and the quartz CIF. Run a Rietveld refinement with rietx and tell me the refined cell. |
| `fire-rank-candidates` | Should fire. | We have twelve candidate structures from a crystal-structure-prediction run, as CIFs. Score each one against our measured powder pattern and rank them. |
| `fire-caco3-fractions` | Should fire. | What are the weight fractions of calcite and aragonite in my CaCO3 powder? The pattern is caco3.xye from our Bruker D8, and I have a CIF for each phase. |
| `fire-unknown-cell` | Should fire. | The pattern unknown.xy is from a phase nobody has identified. Work out its unit cell. |
| `quiet-scherrer` | Should not fire. | A powder XRD peak at 2θ = 38.2° has a FWHM of 0.25° (Cu Kα). Estimate the crystallite size with the Scherrer equation and show the arithmetic. |
| `quiet-chebyshev-numpy` | Should not fire. | Write a numpy function that fits a Chebyshev polynomial baseline to a 1D signal and returns the baseline. |
| `quiet-checkcif` | Should not fire. | Run checkCIF-style validation on my single-crystal CIF and explain what an A-level alert about ADPs means. |
| `quiet-cif-to-poscar` | Should not fire. | Convert structure.cif to a VASP POSCAR file, keeping the atom order of the CIF. |
| `quiet-concepts` | Should not fire. | In two sentences and with no code: what is the difference between a Rietveld refinement and a Le Bail extraction? |
| `quiet-density` | Should not fire. | What is the theoretical density of NaCl, given its lattice parameter of 5.640 Å? Show the arithmetic. |
| `quiet-raman-peak` | Should not fire. | Fit a Lorentzian to the Raman G band near 1580 cm⁻¹ in graphite.csv and report its centre and width. |
| `quiet-saxs-guinier` | Should not fire. | Plot the SAXS curve in saxs.dat on log-log axes and fit the Guinier region for the radius of gyration. |
| `quiet-shelxl` | Should not fire. | I'm refining a single-crystal dataset in SHELXL and R1 is stuck at 9 %. What are the usual causes, in a short list? |
| `quiet-xps-shoulder` | Should not fire. | My XPS C 1s spectrum has a shoulder at higher binding energy. How should I fit the components? |

A tier-0 case has one grader, so one grader's worth is the whole case and the
decision rule below cannot fail on it. The two rates are therefore **reported
beside the decision, not folded into it**, which matters for a candidate whose
`SKILL.md` frontmatter changes the description the harness matches against.

## Models, N, and the command every round runs

- **The agent: Haiku and Sonnet**, `--model haiku` and `--model sonnet`, one
  round per model. **The judge: Sonnet**, `--judge-model sonnet`, for every
  `llm` grader (three votes, PASS at two).
- **N = 3 per arm** (`runs: 3` in every `prompt.md`, and `--runs 3` passed).
  A case whose runs disagree is reported with its per-run scores, never its
  mean alone.
- **Fit cases run alone.** `fap-fit` and `fap-gsas-reproduce` run `-j 1`, one
  round at a time on the machine: in the pilot four concurrent with-arm fits on
  four cores took 10-15 min each against 11 s for the same script outside the
  sandbox, and two of four cells timed out at 1 500 s (WP-1904 finding 2).
  **Before the first scored round, one fit is measured inside the sandbox**,
  alone on the machine, and both cases' `timeout_seconds` (2 400 s at
  registration, the pilot's guess) is set from it. The measurement, the value chosen and why are
  Amendment 1.1, dated, made before the first scored fit-case run; whether the
  sandbox's read-only venv defeats numba's kernel cache is read in the same
  measurement. Every round's `-j` is printed beside its wall times.

```sh
.venv/bin/python tests/eval_skill/build.py docs/skill/rietx <out> --venv <venv dir>   # outside /Users, /tmp and <out>
claude plugin eval <out> --model <haiku|sonnet> --judge-model sonnet --runs 3 \
    --scaffold --allow-tools Bash Write --trust-plugin --no-publish --keep-temp \
    --max-cost-usd <ceiling> --json <result>.json --tag fap [--ablation none] -j 1
# tier 0: the same build, --tag trigger --ablation none, without --scaffold and --allow-tools
.venv/bin/python tests/eval_skill/readout.py show <result>.json
```

### Prerequisites

- **Claude Code ≥ 2.1.289**, the first with `claude plugin eval`; each result's
  `claudeVersion` is printed with it.
- **A sandbox backend**: granted `Bash`, every command runs under Claude Code's
  OS sandbox, and with no backend each run is refused and scores about 0. On
  Linux that is `bubblewrap` and `socat`, which the pilot had to install.
- **An interpreter both arms can read**, built by `build.py --venv DIR` (a
  non-editable install of the checkout). The sandbox decides what a run's Bash
  can read. On Linux it hides the home directory. On macOS it denies all of
  `/Users` and `/tmp`. It allows the run's own home and the `PATH`
  directories, and the plugin root in the with-skill arm only (read off kept
  runs' `config/settings.json`, 2026-10-06). So `DIR` lies outside `/Users`,
  `/tmp` and the plugin root; on this Mac it was
  `/opt/homebrew/var/rietx-eval/venv`, which needs no sudo. The wrong place
  voided runs three times. An interpreter in Claude Code's temp directory or
  in `/Users/Shared` could not start in either arm. One in the plugin root
  served the with-skill arm and voided round B's baseline arm on both fit
  cases. Each such run ends asking for a sandbox change. `build.py` warns
  about an interpreter, or its base, that either arm cannot read.
- **The flags**: `--scaffold` (the fixtures), `--allow-tools Bash Write`,
  `--trust-plugin`, `--no-publish`, `--keep-temp` (the traces, which tokens, the
  route and leaks are read from and which the harness otherwise deletes), and
  `--json`. The target comes first: `--tag` and `--allow-tools` take a list.

## Read-outs, fixed in advance

Computed by `readout.py show` per case and arm, from the result document and
the kept trace each run's `tracePath` names:

- **R0 — the condition.** The build's `skill_sha256` and `tree_sha256`;
  `claudeVersion`, model, judge, ablation and `-j`; per run, the skill's base
  directory and whether the condition held (void runs listed under the table).
- **R1 — the score.** Each run's comparable score (next section) and their
  mean; the **pass rate**, runs at or above the threshold (1.0).
- **R2 — the price.** Per run: agent cost (`costUsd`) and judge cost
  (`judgeCostUsd`), wall time (`durationSeconds`), turns, and **tokens**, the
  assistant messages' `usage` from the trace summed once per `message.id`
  (`tests/eval_agent_surface/trail.py`'s rule): input, cache read, cache write
  and output together, and output alone.
- **R3 — the route.** Whether the skill fired (a `Skill` call naming rietx),
  and which `references/*.md` files tool calls named.
- **R4 — leak.** A tool call naming a skill copy other than the one loaded (a
  path through `docs/skill/rietx`, `data/skill/rietx` or another
  `skills/rietx`; `rietx skill`; `skill_path`), or an absolute path outside
  the run's directory, its loaded skill, the interpreter's environment and the
  system directories; in the without arm the plugin's own copy is a leak. A
  screen read off tool inputs, so a lower bound: a script that opens a path its
  command does not name is invisible to it, and a write outside the workspace
  reads as a leak too. **A run whose leak fires is reported, never dropped**,
  and read by hand before its score is quoted.
- **R5 — what ended a run.** `error` (a timeout, the turn cap), a cost ceiling
  that skipped the judge (`skippedPaidGraders`), a `partial` round. A run whose
  trace is gone reads `?` for R2-R4, never zero.

### The score a comparison reads

The harness's own `score` is not comparable across ablation modes. A two-arm
run drops every `tool_used: Skill` grader and every `arm: with-only` grader
from both arms' scores, unless a grader says `arm: both` (or every grader would
go); `--ablation none` drops nothing. Measured on the
pilot's `fap-fit`: a with-arm run in which only `ran_fit` and `skill_fired`
passed scored 0.14 in `current-sonnet-r2.json` (two-arm, 1 of 7) and the same
state scored 0.25 in `compressed-sonnet-r2.json` (`--ablation none`, 2 of 8),
both under `docs/wp/1904-eval/pilot/`. Today's body runs
two-arm and a candidate one arm, so the harness's numbers would set a 7-weight
score against an 8-weight one.

**`readout.py` scores every run over the comparable graders**, the ones a
two-arm run keeps, whichever mode the run was in, and reads `None` for a run
missing one. On every two-arm run of the pilot its score equals the harness's.

## The decision rule, fixed in advance

**A body change merges only if `readout.py compare CURRENT CANDIDATE` holds on
Haiku and on Sonnet**, where CURRENT is today's body's round and CANDIDATE the
change's, one model each:

1. **Paired per case.** For each case, Δ is the candidate's mean comparable
   with-arm score minus today's body's, over N = 3 runs a side, with the same
   comparable graders and weights on both sides.
2. **No case loses more than one grader's worth.** A case fails when
   Δ < −t, where t is the smallest comparable grader's weight over the case's
   total comparable weight.
3. **Both rounds complete.** Neither `partial`, no run with
   `skippedPaidGraders`, no void run, N = 3 scored runs on each side. A pair
   short of any of these is **undecided**, not passed, and the case is rerun.

| case | comparable graders and weights | total | t |
|---|---|---|---|
| `fap-judge` | biso_background 1, cell_accuracy 1, undersampled 1, zero_displacement 1 | 4 | 1/4 |
| `fap-fit` | caveats_named 1, cell_a 2, cell_c 2, ran_fit 1, report_written 1 | 7 | 1/7 |
| `fap-gsas-reproduce` | cell_a 2, cell_c 2, file_wavelengths 1, o7_coordinate 1, ran_fit 1, rwp 1 | 8 | 1/8 |
| each tier-0 case | its one `Skill` grader | 1 | 1/1 |

Beside each Δ, `compare` prints the **with-skill tokens and cost per run** on
both sides, because a rewrite's claim is cost at equal score: a candidate that
holds the rule at a higher token count is reported as exactly that. It prints
the candidate's score minus today's round's without arm too, the question's
other half; descriptive, never decisive.

**Suspect the judge before the skill.** Where the skill fired in every
candidate run and Δ is negative, `compare` flags the case, and the failing
`llm` graders' votes and evidence are read before the loss is put down to the
body (the harness documentation's own rule). A rule that fails is recorded
here with the cases that failed it, and the change does not merge in that form.

## Price

**Every round passes `--max-cost-usd`**, a ceiling on the run's list-price
estimate that stops new runs once spent. **A registered round is not
authorisation to run its cells**: a costed menu goes to the maintainer before
any cell runs, and what is picked runs (WP-1504's rule).

The menu prices from the pilot (WP-1904, 2026-10-04) until a round measures
its own: `fap-judge` on Haiku $0.16 for both arms at N = 1, judge included, and
$0.14-0.18 a run on Sonnet; a fit case on Haiku $0.60 for both arms, and
$0.23-0.62 a run on Sonnet. The pilot's Sonnet fit costs were measured under
two-way concurrency, so the first round at `-j 1` measures them again. Today's
body on one model is 9 with-arm and 9 without-arm runs of the three cases, a
candidate 9 with-arm runs; tier 0 is 60 one-arm runs a model, each at most four
turns.

## Assumptions the first round checks

`readout.py` was written before any trace was kept, against the Claude Code
transcript shape `tests/eval_skill_placement/runner.py` reads. Each assumption
is checked on the first round's first kept trace, before any of its numbers is
quoted, and the outcome is an amendment:

1. A trace line is a transcript row, `{"type": "assistant" | "user" | "system",
   "message": {...}}`, or a bare message, `{"role": ..., "content": [...]}`;
   `readout.py` reads both and reports a trace with no assistant message as
   `unread` rather than as zero tokens.
2. Assistant messages carry `usage`, and one `message.id` per API call.
3. A run's workspace lies under the directory holding `out/trace.jsonl` (the
   run's temporary directory), or is the `cwd` of a `system` row.
4. A loaded skill names its base directory in the trace (`Base directory for
   this skill: …`), and it lies in the round's plugin or the run's directory.
5. The harness's exclusion rule is the one documented and seen in the pilot
   (§ The score a comparison reads). `readout.py show` lists every two-arm run
   whose comparable score differs from the harness's (`SCORE` under the
   table), so a round checks it by reading its own output.

## What is not being scored

How the agent writes; whether its route was the body's worked default; the
harness's own Δ, with against without inside one round, which the decision
rule does not read (it compares body against body); anything about one model
licensed by the other's round.

## Amendments

### Amendment 1.1, 2026-10-06: the fit cases' timeout, from one run alone

Made before any scored fit-case run. One `fap-fit` run, Haiku, with-arm only
(`--ablation none --runs 1`), alone on a 10-core Mac (macOS sandbox, Claude
Code 2.1.291), its interpreter in the plugin root. It is not a scored run,
and a with-arm run is the one arm that location serves (§ Prerequisites).

- **The run took 271 s, 46 turns and $0.41.** Thirteen of its Bash calls ran
  the agent's scripts, and each full fit took 7-9 s. That matches the pilot's
  11 s outside the sandbox. So the sandbox costs a fit nothing, and the
  pilot's 10-15 min came from four fits sharing four cores.
- **The read-only venv does not defeat numba's kernel cache.** rietx caches
  kernels in the run's own home (`~/.rietx/numba-cache`, 10 files in the kept
  run), so each run compiles once, on its first fit.
- **Both fit cases' `timeout_seconds` is now 1 200 s**, 4.4 times this run.
  `max_turns` (60) bounds a run first, and at 60 turns this run's pace is
  about 350 s. The margin covers Sonnet's slower turns and fits that do more
  work. A timeout that binds would score a slow run as a failed one.
- **Two earlier attempts were void** (§ Prerequisites): their interpreter lay
  where the macOS sandbox denies reads, and neither run could start Python.
  They cost $0.20 together, and neither is a measurement.

### Assumptions 1-4 checked, 2026-10-06, on Amendment 1.1's kept trace

All four hold as written (§ Assumptions the first round checks). The trace
holds transcript rows: 96 assistant, 45 user, 43 system, 1 result. Every
assistant row carries `usage`, and the 96 rows are 45 API calls, so counting
once per `message.id` is what keeps the token read-out from doubling. The
`system` rows' `cwd` is the run's `home/cwd`, under the directory holding
`out/trace.jsonl`. The skill names its base directory, and it lies in the
plugin. Assumption 5 needs a two-arm round and is read off round B's `SCORE`
lines.

## Results

Each round appends its `readout.py show` output, the build's two hashes, its
`-j`, its cost and the date; a comparison appends its `readout.py compare`
output and the rule's verdict. Result files are kept in
`docs/wp/1905-eval/round1/`.

### Round B, 2026-10-06: today's body, Haiku, two-arm, N = 3

Build `SKILL.md` d424ccece23a, tree 604f4c2b2018, from commit eb7a0538.
Claude Code 2.1.291, judge Sonnet, `-j 1`, alone on a 10-core Mac. Two
result files make one round. `B.json` ran all three cases with the
interpreter in the plugin root, which voided both fit cases' baseline arm
(§ Prerequisites). So its `fap-judge` rows stand, and `B2.json` re-ran the
two fit cases with the interpreter in `/opt/homebrew/var/rietx-eval/venv`.
B2 reached B's $8 ceiling with one run left, so `fap-gsas-reproduce`'s
baseline arm has N = 2. Together they cost $8.29 and 1 h 40 min of wall time (58 and 42 min).

```
case                       arm     n  score per run           pass  $/run judge s/run turns  tok/run  fired refs
fap-fit                    with    3  0.43 0.43,0.43,0.43    0/3   0.270 0.012   200 18-33   1067k  3/3   -
fap-fit                    without 3  0.86 0.86,0.86,0.86    0/3   0.385 0.010   230 39-61   1898k  0/3   -
fap-gsas-reproduce         with    3  0.46 0.50,0.38,0.50    0/3   0.361 0.000   205 23-48   1726k  3/3   -
fap-gsas-reproduce         without 2  0.38 0.38,0.38         0/2   0.556 0.000   310 4-60    3424k  0/2   -
fap-judge                  with    3  0.83 1.00,0.75,0.75    1/3   0.109 0.038    60 5-7      120k  3/3   judging.md
fap-judge                  without 3  0.83 0.75,0.75,1.00    1/3   0.068 0.028    41 3-4       54k  0/3   -
```

- **`fap-fit` is a deciding case today's body fails, and the baseline arm
  passes it.** All three with-skill runs report a = 9.3683(16) Å and
  c = 6.8833(12) Å, the same numbers to the last digit. That is the
  degenerate route the case's description names: zero and displacement free
  together, and FLAT_DIRECTION. Each report names that caveat, so
  `caveats_named` passes and both cell graders fail. All three runs without
  the skill improvised a route and landed inside both windows
  (9.3709(4)-9.3728(6) Å), and none named a caveat. One of them hit 60 turns.
- **`fap-gsas-reproduce` fails both cell graders in both arms.** The skill
  adds the `rwp` grader in all three runs. `file_wavelengths` failed in one
  with-skill run.
- **`fap-judge` does not separate the arms on Haiku at N = 3** (0.83 each).
  This repeats the pilot's ceiling on Sonnet, but on Haiku.
- **No run opened a reference file** except `fap-judge`'s `judging.md`.
- **Assumption 5 holds**: `readout.py show` printed no `SCORE` line over the
  18 two-arm runs of `B.json` or the 11 of `B2.json`.
- **The `LEAK` read-out over-reports.** It reads JSON pointer strings in an
  agent's written content (`/cell/a`, `/atoms/6/z`) as paths, and `/tmp` in a
  run's Bash is the run's own. Every other `LEAK` line in `B.json` is a
  baseline run probing the plugin directory for the interpreter it could not
  start.
