# WP-1338 — the skill's own gates: the references, the private corpus, the cap race

Milestone: unscheduled · Status: ⬜
Depends on: —
Priority: P4 2026-09-23 — gates on the skill's own files; a merge that fails late is the cost

## Goal

The three gates protecting the agent skill cover what they are named after: a
dotted name in a reference file is walked like one in the body, a private
`(Measured: …)` tag names the corpus its file declares, and two contributors
adding a sentence each to the same skill file do not fail on the merge with no
warning beforehand.

### Inherited

- **2026-09-16, from [1431](1431-a-caller-names-its-run.md): the api.md half
  of the cap race is settled, and `REFERENCE_MAX_BYTES` is untouched.**
  `references/api.md` is generated from the installed package, one signature
  per public name, so its size is a fact about the API rather than an
  authoring choice, and the authored cap's advice ("split it") is advice it
  cannot take. It sat at 35 942 B against 36 000 and a single new public
  keyword took it 20 B over. Raising the shared constant would have handed
  `diagnostics.md` the room this WP deliberately denied it, so the generated
  file now has its own `API_INDEX_MAX_BYTES` = 39 000 against the same 40 kB
  Bash truncation, and `test_every_reference_file_is_within_its_cap` picks
  the bar by whether the file is `API_INDEX`. **What this WP still owns is
  unchanged**: `diagnostics.md` at ~20 B free, PR #291 as the split that buys
  the next diagnostic row, and whether a per-cell byte gate belongs on the
  §4b table. What it no longer has to decide is whether a generated file
  should share an authored file's cap.

From **WP-1409** (2026-09-14), which swept the manual's register and found a
skill defect on the way.

`docs/skill/rietx/references/abstention.md` wrote `scale × |F|² × profile` as a
code span **inside a Markdown table cell**. The first `|` ends the cell, so the
span never closed and the backticks rendered literally wherever the file is
rendered as Markdown. It is fixed (the pipes are escaped and the span dropped,
which is what the manual's own tables do), but the gate that caught it is the
*manual's*: `tests/test_manual.py::test_no_unrendered_markup_survives_the_build`
scans the built HTML, and the skill body reaches that build only because
`using/skill.md` includes it whole.

So the class is covered for the skill body by accident of where it is rendered,
and not by `tests/test_skill.py`. That is this WP's own shape one file over: a
gate named after the thing it does cover. Whether the skill wants its own check
(a code span opened inside a table cell, in every reference file) is a question
for whoever works these gates; the manual's version is a build-time HTML scan
and cannot be lifted directly.

- **2026-09-15, from the issue triage (issues #284, #287): the cap race
  fired twice, one ruling each, and the numbers this WP's gates now guard.**
  #284 (`SKILL.md` at 7 B of headroom) was ruled 2026-09-08 and landed as
  PR #292 (2026-09-10). The ruling: a body table cell is a lookup and never
  an argument. §4b's middle column went from 417–815 B a cell to 116–232 B
  with the reasoning moved to `references/judging.md`, and `batch.md` split
  by situation into `batch.md` (deciding, 18 rows) and `batch-operating.md`
  (operating, 14 rows) behind two routing rows keyed by situation. Measured
  on this tree: `SKILL.md` 31 951 B of 33 000, `batch.md` 23 255,
  `batch-operating.md` 17 174, `judging.md` 22 873. The ruling is a rule a
  gate can hold (a per-cell byte bar on the §4b table), and whether it
  should is this WP's to decide. **#284 can close.** #287 (`diagnostics.md`
  at 34 B of headroom) was ruled 2026-09-09: the magnetic codes get one
  gated `references/magnetic.md` under § 2b (1327's Inherited has the
  shape); `RECIPE_*` moves to `diagnostics-projects.md` § 7g with that
  section's membership rule restated as *whose file you are reading*
  (PR #291, open); `REFERENCE_MAX_BYTES` stays at 36 000;
  `DISTORTION_MODE_UNSUPPORTED` is a § 7 row. Measured on this tree
  `diagnostics.md` is at 35 980 B, 20 B free, so PR #291 is what makes the
  next diagnostic row possible, and #247's merge-result race now points at
  it. Whatever gate looks for a code's row in `diagnostics.md` alone must
  learn `magnetic.md`.
- **From WP-1434, 2026-09-18: `diagnostics.md` now sits 9 bytes under
  `REFERENCE_MAX_BYTES`, so the merge-result hazard is live on that file
  rather than hypothetical.** The `BOUND_HIT` row grew by about 600 B, and
  the file carried only 615 B of headroom before it. The headroom table in
  § #247 was measured at `c79fb5df` and no longer describes that row.
  Re-measure it before acting on it, and expect the next PR adding a
  diagnostic code there to collide.

## Context

Three issues, all about `tests/test_skill.py` and the process around it
(#238, #241, #247). None has cost a wrong answer; each is a gate that reads as
covering the tree and does not. That is the WP-1037 shape — a check named
after the thing it does cover, silently not covering the rest — one document
over.

**#238 — the dotted-name walk runs on the body only.**

```python
def test_every_dotted_name_in_the_body_resolves():
    text = SKILL.read_text(encoding="utf-8")
    for root, chain in BODY_DOTTED.findall(text):
```

`RX_DOT_NAME` (`rx.X`) is checked across the whole tree, and
`test_every_dotted_name_in_the_api_index_resolves` covers the generated
`references/api.md`. Between them sit the **hand-written** reference files,
whose `report.x` / `result.x` / bare field names are not walked at all. It has
cost nothing yet; #233 adds a large number of such names to `batch.md` and
`series.md` (`entry.diagnostics`, `SeriesResult.diagnostics`,
`weight_fraction_stderr`, `background.worst_absorption`, `soft_modes`, and the
claim that `StageResult` carries no `rwp` field). All check out — checked **by
hand at review**, which does not scale and will not happen next time.

The fix is to run the walk over `[SKILL, *REFERENCES]`, parametrised per file
the way the cap and header tests already are. The `> 15` liveness assertion on
the regex needs re-siting, being a statement about the body's density. Two
decisions come with it, and they are real rather than oversights: the
reference files name **types** as well as attributes (*"`StageResult` carries
no `rwp`"*), which `BODY_DOTTED`'s four roots do not reach — widen the roots
or leave type-level claims unpinned; and a **negative** claim is the one a
walk cannot check and exactly the kind that rots when a field is added. The
gate would not catch it. (Note that 1334 proposes adding `rwp`, which would
falsify that very row.)

**#241 — nothing checks that a private tag names its declared corpus.** #239
admitted a row measured on data the project cannot ship, and put two
obligations on the private case in `CONTRIBUTING.md` § The agent skill and
`references/batch.md` § Writing a row: a file using a private tag **declares
the corpus once in its provenance line**, and every such tag **spells it the
same way**. Both are prose; neither is checked. The gate stops at the tag:

```python
_EVIDENCE_TAG = re.compile(r"\*\((Measured|Hypothesis): .+\)\*\Z", re.S)
```

`.+` is the whole contract. A row closing `*(Measured: some runs I did)*`
passes, naming nothing. A file naming one corpus three ways across
twenty-nine rows passes. A file using a private tag while declaring **no**
corpus at all passes, which is the case the rule was written to stop, since
that tag reads exactly like a citation. The header test next door is
`startswith` on the provenance paragraph plus `EVIDENCE_DECLARATION in
paras[2]`, so it does not see a corpus sentence either way.

**Blocked on #233, deliberately.** The check cannot be written before a corpus
exists: written today it would run, find no file declaring one, and pass —
the failure `test_the_evidence_gate_has_a_file_to_gate` exists to name one
document over. The new check wants a liveness guard in that same idiom.

The real decision is how a tag is sorted into "names something in this
repository" and "names the declared private corpus", and it should be taken
rather than reached for. Recognising a repo-shaped tag by pattern is the
obvious route and the weak one: `WP-\d+` is reliable, but "an eval round" and
"a dataset in `tests/data/README.md`" have no fixed spelling, so the pattern
either grows to fit each new phrasing or starts refusing honest tags.
**Requiring the complement is narrower and probably right**: every `Measured`
tag begins with `WP-` or with the declared corpus string exactly. It gives up
on validating repo tags — which the dotted-name walk and the WP files already
cover from the other side — and spends its whole budget on the case with no
other guard. A per-row marker would make this trivial and **#239 ruled it
out**, on the grounds that declaring once costs no row an edit; that is why
the classification cannot be designed away, and the reason belongs next to
whatever is chosen. Two smaller points: a file may legitimately hold both
kinds (#233 has two `WP-` tags among 29 private ones), so the check is **per
tag, never per file**; and `Hypothesis` tags name what *would* decide a
question rather than a run, so they are outside this gate entirely.

**#247 — the byte caps are checked on the merge result, so two passing PRs can
fail together.** Each PR's CI sees only its own merge with `main` as it stood
at push time. Measured on this worktree at `c79fb5df`:

| file | cap | size on main | headroom |
|---|---|---|---|
| `SKILL.md` | 33 000 | **32 978** | **+22 B** |
| `references/diagnostics.md` | 36 000 | **35 914** | **+86 B** |
| `references/diagnostics-indexing.md` | 36 000 | 30 809 | +5 191 B |
| `references/api.md` | 36 000 | 29 193 | +6 807 B |
| `references/surprises.md` | 36 000 | 20 916 | +15 084 B |

**Re-measured on `main` at `b717cc98`, after PR #111 merged (2026-09-03):**
`SKILL.md` 32 989 B (**+11 B**); `references/diagnostics.md` 32 125 B
(+3 875 B) beside the new `diagnostics-projects.md` at 10 273 B. The split
this WP names below has happened, and the whole of the pressure now sits on
`SKILL.md`, which cannot be split the same way.

**Two files were within 100 bytes of their cap** at `c79fb5df`, and one
still is, so almost any addition to
either is a merge conflict against any other addition to the same file,
including two that are individually one sentence. It already happened: #233
was green with `batch.md` at 35 570 B, `main` then grew it ~1 kB (`e06a8f54`),
and the merge came to 36 599 B against the 36 000 cap.

**The failure mode is worse than a textual conflict**, which names its lines
and either author can resolve. A cap failure names only a total, so the second
author has to find bytes somewhere in a file they may not have written — three
attempts to absorb 599 bytes produced 36 209, 36 136, then **37 083**, larger
than the start, because the author was correcting a row while trimming it.
What worked was noticing that one row was in the wrong file and moving it,
which will not always be available. **And the incentive runs the wrong way:
the cheapest way to pass is to delete someone else's prose.**

Four options; **decided 2026-09-03: warn first**, the rest when the next row
lands in a near-full file. Split the largest files, as
#111 does for `diagnostics.md` (35 914 → 32 125 + a 9 736 B
`diagnostics-projects.md`) on a real seam, import-time versus fit-time codes —
but `SKILL.md` cannot be split that way, being the routing body. Raise the
caps: they exist so an agent can read the file, and whether 36 000 is still
right for a file loaded on demand is a judgement only the maintainer can make.
**Warn before the cap binds** — a CI note at, say, 95 % — is the cheapest and
does not require deciding the others; it would have made `main`'s two near-full
files visible before anyone wrote a word. Budget per PR is probably more
machinery than the problem deserves. **Note that several other WPs in this
triage round each add a `references/diagnostics.md` row** (1332, 1336, 1340).
Until #111's split that was the 86 B spent several times over; after it the
rows fit, and the critical path runs through `SKILL.md`'s 11 B instead — any
body sentence a WP adds meets this WP first, even though none depends on it
formally.

## Non-goals

- Cutting skill content to make room. The caps question is decided here as
  policy; individual rows are their own WPs' business.
- The skill's routing structure and the per-shape references — WP-1330, closed.
- Anything in `references/api.md`, which is generated and already gated.

## Tasks

- [ ] Run the dotted-name walk over `[SKILL, *REFERENCES]`, parametrised per
      file; re-site the `> 15` liveness assertion; decide and record whether
      type-level roots widen.
- [ ] The private-corpus check, per tag, with its liveness guard, and the
      reason the chosen classification rule was preferred written beside it.
- [ ] Cap policy, decided 2026-09-03: a CI warning at 95 % of each cap lands
      now; split versus raise is decided when the next row lands in a
      near-full file, and recorded where the caps live.
- [ ] Whatever is chosen, make the near-full state visible to a contributor
      before they write, not after CI.
- [ ] Tests: all three land as tests, and are expected **green on the tree as
      it stands** — these close gaps rather than fixing breaks, so a red run
      means the gate found something real and it should be reported, not
      accommodated.
- [ ] Skill: no row changes. These protect the skill rather than being
      described by it.

## Acceptance

The three gates run over every reference file and pass on the tree; a
deliberately broken fixture of each kind fails.

```sh
.venv/bin/python -m pytest tests/test_skill.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issues #238, #241, #247. Caps read from `tests/test_skill.py`:
  `SKILL_MAX_BYTES = 33_000`, `REFERENCE_MAX_BYTES = 36_000`; sizes re-measured
  on `main` at `c79fb5df` (the table above is this worktree's measurement, not
  the issue's — `SKILL.md` had moved from 32 966 to 32 978 in between).
- `CONTRIBUTING.md` § The agent skill — the two prose obligations #241 gates.

## Handover log

- **2026-09-03** — created, from the 2026-09-03 issue triage (issues #238,
  #241, #247). The cap table was re-measured rather than copied: `SKILL.md`
  now has 22 B of headroom, not the 34 the issue reported. Decided the same
  day: warn at 95 % first, split versus raise deferred to the next row.
- **2026-09-16** — the `diagnostics-projects.md` half of the cap race is
  settled by a split, and `REFERENCE_MAX_BYTES` is still 36 000. PR #346 put
  17 `GSAS2_*` rows (10 127 B) into that file while PR #291 waited, and the two
  together came to 37 641 B against the cap, which is how a docs change fails a
  gate neither author touched. The 2026-09-09 ruling above says the constant
  stays, so the fix is the one the cap's own docstring names: the 29 GSAS and
  GSAS-II rows moved to `references/diagnostics-gsas.md` as §7h, in main's
  order, so the `.EXP` rows still sit beside the `.gpx` rows they share five
  suffixes with and the `.prm` rows beside the `.instprm` ones. The seam is a
  program rather than a file kind, and the writer rows go with it, because this
  build writes a `.EXP`, a `.prm`, an `.instprm` and a GSAS-II phase CIF and no
  other foreign format's writer has a row. Measured after:
  `diagnostics-projects.md` 10 448 B, `diagnostics-gsas.md` 21 436 B,
  `SKILL.md` 32 068 B of 33 000, `diagnostics.md` 35 963 B of 36 000. #291
  rebases onto about 17 kB of room, and #289 onto what #291 then frees in
  `diagnostics.md`. **What this does not do**: the three unticked tasks are
  untouched and Status stays ⬜, since the split executes a ruling rather than
  landing a gate. `diagnostics.md` still has 37 B of headroom until #291 lands,
  so a new engine row is blocked today exactly as it was. The count moves by
  four, one per `REFERENCES`-parametrised gate in `tests/test_skill.py`, and by
  nothing else.
