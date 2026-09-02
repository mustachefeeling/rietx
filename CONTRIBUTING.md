# Contributing to rietx

This page is the mechanical half of contributing: setup, the test ladder,
the style rules a change is held to, and licensing. The design rules live
in the `CLAUDE.md` rulebooks (see [AGENTS.md](AGENTS.md)); they are written
for agents and bind humans equally.

## Setup

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"
uv pip install -e ".[dev,jax,torch]"    # + optional backends
```

A git worktree needs its own venv: the main checkout's `.venv` resolves
`rietx` to the main checkout's `src`, so tests in a worktree would measure
the wrong tree.

## Tests and lint

```sh
.venv/bin/python -m ruff check src tests examples                    # must be clean
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"    # fast suite, ~1-3 min
.venv/bin/python -m pytest -n auto --dist loadgroup                  # full suite, ~15-30 min
```

- `--dist loadgroup` is not optional: it honours the `xdist_group` marks
  that keep a shared fixture on one worker. Plain `--dist load` silently
  refits the expensive fixtures, so `tests/conftest.py` refuses a parallel
  run without it. `-n 0` is how to ask for a serial one.
- Run the fast suite before proposing a change; the full suite once, on the
  final tree, when the change can move a measured number.
- Quote any test count with the extras installed and the platform
  (`[dev]` vs `[dev,jax,torch]`; skips convert to passes with the extras).
  Quote wall clock as a range, never as a single figure.
- GUI frontend: `npm --prefix gui ci && npm --prefix gui run build`, then
  `npm --prefix gui test && npm --prefix gui run check`. The built dist
  under `src/rietx/gui/static` is committed — rebuild it in the same change
  that edits `gui/src`.

## Style essentials

The enforceable core; a test backs each of these, so a PR that skips one
fails before review reads it.

- Every physics function cites its reference (author, year, journal) in its
  docstring, and documents conventions by physics, never by letters — codes
  disagree on letter assignments (GSAS and FullProf swap the size/strain X
  and Y).
- Units: angles in degrees; Caglioti U, V, W in deg²(2θ); Biso in Å²;
  wavelengths in Å.
- Parameter paths are dot-separated and glob-matched with fnmatch — no
  brackets in paths.
- Never spell the distribution name, a format token or the state directory:
  import it from `src/rietx/_about.py`. The audit test greps only old
  names, so a freshly hardcoded current name is invisible to the suite.
- The manual is guarded: every dotted name resolves against the live
  package, every python block parses and executes or states why not, every
  bibliography entry is cited, and every displayed equation carries a
  source symbol that imports. A new public name fails the coverage
  partition until it is documented, excluded with a reason, or deferred.
- Worked examples live in `examples/`, are included verbatim by the manual
  and executed by the suite. Never write a second copy of a walkthrough.
- A new correction ships with a record field or a diagnostic stating what
  it changed — never an Rwp comparison as its evidence.

## The agent skill

`docs/skill/rietx/` is what an agent reads before driving the package on real
data: `SKILL.md`, read whole, and `references/`, one file per lookup or per
task shape, loaded when the body's routing table names it. It is the third
place a change can need to land, beside the code and the manual, and the one
that takes what you *learned running the package* rather than what you
changed in it. Two committed copies, `.agents/skills/rietx/` and
`.claude/skills/rietx/`, are regenerated from it and must stay byte-identical.

Where a rule goes:

- It holds for every fit: the body. The body is at its byte cap, so a new
  sentence there is paid for by a cut (`tests/test_skill.py` states the cap
  and why).
- It holds for a task *shape* — a series, a batch of candidates, a magnetic
  phase: that shape's file under `references/`, numbered under the body
  section it specialises (`9b` series, `9c` batch), reached by one routing
  row whose *When* column names the situation and never the feature. A new
  shape is a new file: copy the three-paragraph header of an existing one
  (the title, "Load it when …", the provenance line), which the tests pin.
- It is a measured surprise about one fit: `references/surprises.md`.
- A diagnostic code, a gate or an action: its row in the diagnostics or
  abstention tables; `tests/test_docs_consistency.py` fails until it exists.
- It is a rule for changing the package, not for running it: a `CLAUDE.md`.

**Writing a row from runs.** A reference that collects rules from runs
declares in its provenance line that every row carries its evidence, and each
row then reads: the rule as one bold imperative sentence, numbered under the
file's section; two to four sentences on what was measured — the dataset or
episode, N, the number that decides; and a closing tag,
`*(Measured: <the run a reader can find>)*` or
`*(Hypothesis: <what would decide it>)*`. `references/batch.md` § Writing a
row is the worked form. If an agent is writing the rows from your logs, hand
it that section and this one: every number in a row comes from the log, and
anything the log does not decide is a Hypothesis row, never a softer Measured
one. Before a row, ask whether it holds for one fit alone — then it is the
body's or §8's, not the shape's.

Then, in the same change:

```sh
.venv/bin/python -m pytest tests/test_skill.py tests/test_skill_cli.py tests/test_docs_consistency.py
.venv/bin/rietx skill --install . --copy      # re-sync the two committed copies
```

The first refuses a row without its tag, a reference without its header, a
link that does not resolve, a name the package does not export and a body
over its cap; the second regenerates the two copies.

## Licensing

MIT. Port code only from permissively licensed sources, and update
`ATTRIBUTION.md` in the same change. BGMN, Profex and xrayutilities are
GPL: concepts only, never code. TOPAS and FullProf are closed: papers only.

## Maintainer-only machinery

Parts of `CLAUDE.md` serve the maintainer's own workflow and do not bind an
external contribution: the ROADMAP/WP session protocol and its handover
logs, the memory conventions, and the references to a local paper corpus.
If a rule points at something you cannot have (a local corpus path, a WP
file's history), say so in the PR rather than guessing around it.

Two of those files are the maintainer's to write:

- `docs/ROADMAP.md`, which says what is scheduled and in what order.
- `docs/wp/NNNN-*.md`, a work package. Every WP file needs a matching
  ROADMAP index row, enforced by
  `test_wp_files_and_roadmap_rows_are_a_bijection`, so a new WP file cannot
  land without also scheduling the work.

Adding to the handover log of a WP whose work you did is welcome. That log
is the record of what you measured and where you stopped, and it belongs in
the same change as the code.

## Proposing something that is not scheduled

Open a [design proposal][proposal] and write the design there. A proposal
does not need an implementation, and unscheduled design does not go into a
WP file: the maintainer opens the work package and the ROADMAP row when the
work is scheduled, and links back to the proposal. The design then exists in
one place at each stage instead of two that drift apart.

Proposals are read and answered, not queued silently. The answer may be that
the work sits behind a version fence in `docs/ROADMAP.md`, in which case the
proposal records why for whoever asks next.

[proposal]: https://github.com/yue-here/rietx/issues/new?template=design-proposal.md
