# WP-1117 — the compatibility promise, rewritten for the users there are

Milestone: v1.1 · Status: ⬜
Depends on: —

## Goal

Breaking a contract costs one bump comment and a version component that moves
by a rule needing no classification, instead of a classification decision, a
doc read and a hunt for the meta-tests that fire. The promise in `docs/manual/using/compatibility.md`
says what is actually true of a package whose users are a handful of friends
testing it, and stops promising a freeze the maintainer cannot afford — without
dismantling the machinery that would be expensive to rebuild.

## Context

### What the maintainer asked for, and when

**2026-08-21, during WP-1110**: *"I need a mechanism to break contract, since I
have very few users (all of whom are in direct contact with me) and need to be
very agile on development."* Then, correcting the first answer: *"currently we
don't have actual users — just friends who are testing the software. No-one has
an archive of `.rex` projects. Breaking changes are still extremely cheap."*

Two premises follow and both are load-bearing here:

1. **No `.rex` archive exists.** Backward compatibility — a new rietx opening an
   old file — currently protects nothing that exists. This is the premise that
   makes the work cheap, and it is the one that will expire first.
2. **Every user is reachable directly.** A break can be communicated in a
   message rather than through a version contract.

This supersedes the 2026-08-17 position ("no users at all, breaking changes are
free"), which is recorded in the maintainer's own memory and was revoked by its
own terms when users were first mentioned.

### The friction, measured rather than asserted

WP-1110 added one `PeakFlag` member, `no_intensity`. What that cost, step by
step, because the split matters more than the total:

| step | kind |
|---|---|
| add to the `PeakFlag` `Literal` | the change itself |
| add to `PEAK_UNUSABLE_FLAGS` | the change itself |
| write the test | the change itself |
| bump `INDEXING_THRESHOLDS_VERSION` 1.2 → 1.3 with its comment | **compatibility ceremony** |
| add to `gui/src/lib/rxt.ts`, rebuild the committed dist | **sync machinery** |
| add the row to `using/indexing.md`'s flag table | documentation |

**One of six steps is the freeze.** The GUI step exists because the vocabulary
is written down twice and `tests/test_textdoc.py` keeps the copies honest; that
is correctness machinery and it stays whatever this WP decides. The manual row
stays because the flag is user-facing. So relaxing the promise buys back one
step in six — worth doing, and **not** the thing that made that change feel
heavy. A session that expects more from this WP will be disappointed; the win
is that the remaining step stops being a *decision*.

### What exists today

**The six versioned contracts**, each a module constant, all quoted into
`capabilities()` and pinned by
`tests/test_capabilities.py::test_every_versioned_contract_is_a_live_value`
(which fails on a `*_version` field whose value is not the constant it claims
to quote):

| contract | constant | module | value at 2026-08-21 |
|---|---|---|---|
| schemas | `SCHEMA_VERSION` | `schemas/common.py` | `"0.2"` |
| report gates | `THRESHOLDS_VERSION` | `report/schemas.py` | `"1.3"` |
| event ladder | `EVENT_SCHEMA_VERSION` | `history/events.py` | `"2"` |
| `.rex` project | `PROJECT_FORMAT_VERSION` | `schemas/project.py` | `"1.1"` |
| `.rxt` textdoc | `FORMAT_VERSION` | `gui/textdoc.py` | `"1"` |
| indexing gates | `INDEXING_THRESHOLDS_VERSION` | `schemas/indexing.py` | `"1.3"` |

**The chapter** is `docs/manual/using/compatibility.md`, 155 lines, seven
sections. § "How a change is classified" is the part that costs a decision per
change: safe additions move no version, closed-vocabulary additions are minor
events in their own contract, renames/removals/threshold moves are breaking
events, plus two clauses (a changed *meaning* is always documented; consumers
must tolerate unknown fields and flags).

**The freeze machinery** is separate from the promise and is what should
survive: the derived API-surface partition (`tests/api_surface.py`, whose
docstring holds the rules), the deferred bucket
(`tests/api_surface_deferred.txt`), `PROVISIONAL_MODULES`, and `_SURFACE_FLAGS`
in `capabilities.py`. These stop a new public name shipping undocumented. They
took several WPs to build (1067, 1076, 1078) and would be expensive to rebuild;
relaxing the *promise* is reversible in an afternoon, deleting *them* is not.

### One measured contradiction in the chapter

§ "How a change is classified" ends with **"Tolerate unknown fields and flags"**
as a rule binding on consumers. The package does not follow it. Measured
2026-08-21:

```python
ObservedPeak(..., flags=["a_flag_from_the_future"])   # ValidationError
```

A closed `Literal` vocabulary rejects an unknown member outright, so an older
rietx cannot read a peak list written by a newer one. That is a *forward*
compatibility break — old code, new data — and it is the only direction a
vocabulary addition breaks at all. Backward compatibility (new code, old data)
is untouched by adding a member.

### The proposal put to the maintainer, and the parts of it withdrawn

Recorded so this WP does not re-derive it, and so the withdrawals are visible:

- **Rewrite the promise to match reality.** 1.x is a preview; anything may
  change in any release; pin an exact version for stability; the release notes
  say what moved. Delete § "How a change is classified" entirely, because it is
  the part that costs a decision. Highest friction removed per hour spent, and
  it is a docs edit.
- **Keep the six version strings, make the bump rule one sentence.** They are
  still worth having, because a client detects a mismatch cheaply and the
  friends testing this will hit exactly that. The rule, stated beside each
  constant and nowhere else: any change a consumer could observe bumps the
  last component by one, and the comment says what changed. No classification
  survives — the relaxed promise makes safe/minor/breaking meaningless, so
  the only question left is yes/no.
- **A changelog of intentional breaks**, demoted from governance to record — so
  that when there are users the history already exists rather than needing
  reconstruction. Resolved at the review: that record already exists — the
  bump comments carry it — so the task became declaring them the authority
  rather than copying them.
- **Withdrawn: making closed vocabularies tolerant on read.** Proposed and then
  retracted the same afternoon. Its value was protecting archives and avoiding
  vocabulary bumps; the first does not exist and the second is better solved by
  the one-sentence bump rule. What it would cost is real — today an unknown flag
  fails loudly, which is how a friend finds out their install is old — and with
  four testers "upgrade" is a fine answer. **Do not reinstate it without a new
  reason**; the reason it was proposed is gone.
- **Withdrawn: deriving each version from a content digest** (proposed with
  the version-strings bullet, withdrawn at the 2026-08-21 review). A digest over a
  contract's field and vocabulary set, with a meta-test failing on drift, was
  to make a bump a consequence rather than a decision. The bump histories
  refute it: `INDEXING_THRESHOLDS_VERSION` 1.2 (search driven by the
  strongest lines rather than the first N) and `THRESHOLDS_VERSION` 1.1
  (actions withdrawn on one geometry) moved no field, no vocabulary member
  and no threshold, so a digest catches neither — and a green drift test then
  reads as "no bump needed" for exactly the class the chapter calls the least
  visible break there is. Nor are the six uniformly digestible: events digest
  cleanly (the kinds), indexing and project mostly (fields plus flags), the
  report contract's emission conditions are code, `SCHEMA_VERSION`'s content
  is every field of every model (a naive digest bumps on every safe addition;
  a curated one reintroduces the decision as curation), and the `.rxt`
  grammar has no digestible representation. The decision is relocated, not
  removed. **Do not reinstate without evidence that bumps are actually being
  forgotten** — with every user reachable directly, a forgotten bump costs
  one message.

### The constraint that outlives the premises

The two premises above expire. `.rex` archives will exist the first time
someone runs a real study, and the friends become users. So the deliverable
must include **what makes the promise tightenable again** — the bump-comment
record, the six version strings, the partition — rather than only what makes
it looser. A
promise relaxed with no path back is a different and worse outcome than the one
being asked for.

## Non-goals

- **Dismantling the API-surface partition, the deferred bucket, or
  `PROVISIONAL_MODULES`.** Those are correctness machinery, not the promise.
- **Removing the duplicate-vocabulary meta-tests** (`test_textdoc.py`'s
  `rxt.ts` parity, `test_capabilities.py`'s registry membership). They cost a
  step per vocabulary addition and they are the reason two copies cannot drift.
- **`Parameter.expr`** — WP-1110 item 5, a `SCHEMA_VERSION` 0.2 → 0.3 removal
  costed both ways in that WP. This WP may make it *cheaper* to land but does
  not land it.
- **Going back to 0.x, or a 2.0.** Renaming the promise is cheaper than renaming
  the version, and 1.0.x is already on PyPI.
- **Deciding the release home of anything.** That is the maintainer's.

## Tasks

- [x] **Rewrite `docs/manual/using/compatibility.md` around what is actually
      promised.** Delete § "How a change is classified"; state the preview
      position and how to pin. Three sentences survive the deletion or join
      it: the meaning clause ("a change to what an existing value means is
      always a documented event" — the one rule no version string can see,
      kept in the preview statement); the promise's own expiry trigger (it
      tightens when the first persistent `.rex` archive exists — a condition,
      not a date); and the partition re-grounded ("documented" comes to mean
      documented, not frozen — the partition still gates an undocumented
      public name, it no longer freezes a documented one). Keep § "The JSON
      the package writes" (those two facts are normative regardless) and
      § "The name and the formats are separate promises". Check every `{ref}`
      into the chapter still resolves — root CLAUDE.md and `docs/ROADMAP.md`
      both restate the freeze ("documenting it freezes it") and need the same
      re-grounding, not only a link pass.
- [x] **State the bump rule in each of the six constants' comments — one
      sentence, identical**: any change a consumer could observe bumps the
      last component by one, and the comment beside the constant says what
      changed. No classification (the relaxed promise makes safe/minor/
      breaking meaningless) and no digest — the withdrawn item above records
      why, and what evidence would reopen it.
- [x] **Declare the bump comments the changelog.** They already carry the
      history this WP would otherwise have seeded (e.g.
      `INDEXING_THRESHOLDS_VERSION`'s 1.0/1.1/1.2/1.3 notes, `SCHEMA_VERSION`'s
      0.1 → 0.2), and a separate file would be a second authority with no test
      holding the copies together. The rewritten chapter says where the
      history lives; promoting it to a user-facing file waits for users to
      face, and is part of the tightening path rather than of this WP.
- [ ] **Audit what the relaxation actually freed**, and record it: re-run the
      six-step table above against the new rules and say which steps went. If
      the answer is still "one of six", say so — a WP that measures its own
      result at less than it hoped is worth more than one that does not look.
- [ ] Tests: the chapter's own link/reference checks via
      `tests/test_manual_api.py` and `tests/test_docs_consistency.py`, and the
      `-W` Sphinx build. No new meta-test lands. No obs/calc/diff PNGs: this
      WP touches no refinement.

## Acceptance

Adding a vocabulary member to a closed `Literal` — the WP-1110 `no_intensity`
change, replayed on paper — requires **no** compatibility decision: the only
question left is "did anything a consumer could observe change", the answer is
yes, the last component moves by one, the bump comment says what changed, and
nothing in `compatibility.md` has to be read to know whether that was correct.

```sh
.venv/bin/python -m pytest tests/test_capabilities.py tests/test_docs_consistency.py tests/test_manual_api.py -q
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m ruff check src tests examples
```

## References

- `docs/manual/using/compatibility.md` — the chapter being rewritten.
- `tests/api_surface.py` docstring — the derivation rules for the partition
  that this WP deliberately leaves alone.
- WP-1110 § the `no_intensity` flag — the measured friction this WP answers,
  and the `INDEXING_THRESHOLDS_VERSION` 1.2 → 1.3 bump that triggered the ask.
- WP-1067 (manual + freeze), WP-1076 (declared names), WP-1078 (provisional by
  declaration) — where the machinery came from, for the cost of rebuilding it.

## Handover log

- **2026-08-21** — created during WP-1110's second session, at the maintainer's
  request, so the contract question could be taken up fresh rather than
  competing with an in-flight speed-adjacent WP. Nothing implemented. The
  context above is written from that session: the two measured facts are the
  six-step cost table (one step in six is the freeze) and the
  `ObservedPeak(flags=["…"])` `ValidationError` showing the chapter's
  tolerate-unknowns rule is not implemented. **Next: the chapter rewrite**, on
  its own, because it is the largest friction reduction, needs no code, and
  makes the other two tasks optional rather than blocking.
- **2026-08-21 (later)** — critically reviewed at the maintainer's request
  ("move fast while changes are still cheap"). Three changes. The digest task
  is withdrawn on measured evidence: two of the historical bumps it was meant
  to automate moved no shape at all (indexing 1.2, report 1.1), so it would
  have automated the easy half and false-greened the hard one; its
  replacement is the one-sentence bump rule. The changelog task resolved to
  comments-as-authority: seeding a file would have made a second copy of a
  history the constants already carry. And acceptance no longer depends on
  the withdrawn meta-test — as written it required task 2 while this log
  called it optional, and both could not be true. Scope is now one docs
  session. **Next: the chapter rewrite**, unchanged.
