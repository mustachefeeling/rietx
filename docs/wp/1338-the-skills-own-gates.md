# WP-1338 — the skill's own gates: the references, the private corpus, the cap race

Milestone: unscheduled · Status: ⬜
Depends on: —

## Goal

The three gates protecting the agent skill cover what they are named after: a
dotted name in a reference file is walked like one in the body, a private
`(Measured: …)` tag names the corpus its file declares, and two contributors
adding a sentence each to the same skill file do not fail on the merge with no
warning beforehand.

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
