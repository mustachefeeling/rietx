# WP-1104 — Literature-grounding audit of AGENT_PROTOCOL.md

Milestone: v1.1 · Status: ✅ 2026-08-18 — audit landed; grid + reconciliation in milestones/v1.1.md § Appendix
Depends on: — (first of the agentic-report set; docs-only, may run before the
v1.1 version flip)

## Goal

Every normative claim in `docs/AGENT_PROTOCOL.md` carries its grounding — an
in-repo measurement it names, a paper that was actually read, or an explicit
house-rule label — verified against the practice literature, with Toby (2024)
read and reconciled for the first time and a dated audit grid in the milestone
record.

## Context

- **The failure mode is measured, once, in this repo.** WP-1068's manual
  second pass found `using/concepts.md` attributing three rules to McCusker
  et al. (1999) that the paper does not contain (`w` before `u,v,x,y`;
  intensity-scaling corrections last; strain freed inside the sample-broadening
  stage) — all three are house findings the manual mis-attributed during
  compression. AGENT_PROTOCOL §2 states the same three rules today, without
  attribution. The protocol itself has never had the pass the manual got.
- **The claim classes to sort into**: (i) in-repo measurement — the claim
  names its WP or record (§8's nineteen surprises are the model: "each
  measured, each ending in a Corollary"); (ii) literature-grounded — a paper
  supports it and the paper's text was read, not its abstract or a citation
  chain; (iii) house rule / inference — kept, but labeled as ours (1068's
  rule: house rules named as house rules).
- **Toby (2024) is the one named new source.** *A simple solution to the
  Rietveld refinement recipe problem*, J. Appl. Cryst. 57, 175–180 — directly
  about what §2 and §10 encode (parameter turn-on order as a recipe). It is in
  the corpus (`derived/6WJDXKUV/`), cited exactly once in the manual
  (`docs/manual/estimation.md:296`, a GSAS-II aside) and has never been read
  by a WP. Read it first; reconcile its recipe against `PLAN_PRESETS` /
  `PLAN_INFO` (`strategy/staged.py`) and §2's ordering rules. Each difference
  is a finding: adopt (a successor WP), decline with a written reason, or
  record as an open question. Do not change a preset in this WP.
- **Corpus sources held** (`/Users/yue/zotero-linker`, `index.sqlite`;
  the maintainer's memory is the pointer — the corpus is outside the repo):
  McCusker et al. 1999 (`YWSBLSIS`, read by 1068), Toby 2024 (`6WJDXKUV`,
  unread), Watkin 2008 practical strategies (`2FSHUYQK`), Schwarzenbach
  et al. 1989 statistical descriptors (`A7LFQSXQ`), Altomare et al. 1995
  (read by 1071), Tian et al. 2013 SrRietveld (automated recipes — prior art
  for the presets).
- **Papers to request from the maintainer** (bib entries exist for the first
  three in `docs/manual/references.bib`, but the audit reads papers, not bib
  entries; ask rather than working around): Toby 2006 ("R factors in Rietveld
  analysis: How good is good enough?" — §4 steps 8–9 lean on its stance);
  Hill & Flack 1987 (the Durbin–Watson statistic §4/§6's serial-correlation
  reading rests on); Bérar & Lelann 1991 (the esd inflation §4 step 5 quotes);
  Hill 1992 and Hill & Cranswick 1994 (the Rietveld refinement round robins —
  measured practitioner spread, the strongest experience-grounded class in the
  literature); Madsen et al. 2001 + Scarlett et al. 2002 (the IUCr CPD QPA
  round robins — the `qarr/` test data's own papers, which §4b's QPA rows
  should be quoting). Optional: Cox & Papoular (weighted R_B — flagged uncited
  by 1067 and in neither the bib nor the corpus).
- **Where the grid lands**: the in-flight milestone record's appendix, the
  1068 McCusker-compliance-audit format (`milestones/v1.0.md` § Appendix is
  the precedent). If this WP runs before the v1.1 opening, create
  `milestones/v1.1.md` with the appendix section only — the version flip to
  `1.1.0.dev0` stays with the first *code* WP (ROADMAP's v1.1 note).
- Amendments this audit motivates split by kind: attribution fixes and claim
  demotions execute **here**; new tables or coverage tests belong to
  [1105](1105-agent-protocol-hygiene.md); anything needing a schema field goes
  to [1106](1106-report-placement-fields.md)'s `### Inherited`.

## Non-goals

- Restructuring the protocol or adding vocabulary tables (1105).
- Schema or report changes (1106); running agent evals (1107).
- Auditing the *manual* (1067/1068 did) or physics-module citations — only
  claims the protocol makes to an operating agent.
- Changing any preset or threshold: a Toby-2024 disagreement with
  `PLAN_PRESETS` is recorded, not acted on here.

## Tasks

- [x] Read Toby 2024; write the reconciliation against §2 and
      `PLAN_PRESETS`/`PLAN_INFO` (adopt / decline-with-reason / open, per
      difference); cite it where it grounds an existing §2/§10 claim.
- [x] Classify every normative claim in §§1–10 into the three classes; the
      grid (section → claim → class → source) goes to the milestone-record
      appendix, dated.
- [x] Fix attributions in place: the three §2 house rules labeled as house
      rules (1068's fix, one document over); any claim whose named source
      does not support it corrected or demoted.
- [x] Verify §8's nineteen "measured" pointers resolve to their WP or record;
      fix any that don't.
- [x] Read the retrieved papers as the maintainer supplies them; ground or
      amend the claims that rest on each (§4 steps 5/8/9, §4b's QPA rows,
      §6's serial-correlation rows). A paper not supplied leaves its claims
      classified "house rule, literature pointer unread" — visible, not
      blocking.
- [x] Forward structural findings to 1106's `### Inherited`; handover.

## Acceptance

The audit grid exists in the milestone record, dated, covering every numbered
section with per-class counts; the protocol contains no claim attributed to a
paper whose read text does not support it; every §8 pointer resolves.

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- McCusker, Von Dreele, Cox, Louër & Scardi (1999), J. Appl. Cryst. 32, 36 —
  the guidelines; already audited for the *package* by 1068.
- Toby (2024), J. Appl. Cryst. 57, 175 — the recipe problem; the unread named
  source this WP exists to read.
- Watkin (2008), J. Appl. Cryst. 41 — refinement strategy practice.
- Schwarzenbach et al. (1989), Acta Cryst. A45, 63 — statistical descriptors.
- The retrieve list in Context (round robins, Toby 2006, Hill & Flack 1987,
  Bérar & Lelann 1991, Madsen 2001, Scarlett 2002).

## Handover log

- **2026-08-19 — Cox & Papoular addendum.** The maintainer pointed out the
  paper *is* in the corpus (`derived/V8RPPS5L`; the 2026-08-18 title search
  missed it). Read in full: the weighted R_WI / S_I claim the repo rested on
  is verified, §4 step 9 now cites it, and the one emphasis tension (R_I
  ranked above R_wp, on nearly-overlap-free synchrotron data) is recorded in
  the v1.1 appendix's addendum rather than resolved. Grid: the trace-phase
  row gains class (ii); counts 34 → 35. No claim needed demotion.
- **2026-08-18 — audit complete, WP closed** (six commits, one per checklist
  item). Toby 2024 read — the first WP to read it — and reconciled against
  §2 and `PLAN_PRESETS`/`task="suggest"`: two adopt-by-citation (the
  worst-fit mechanism is WP-1050's Gauss-Newton gain; the Δ/σ plot is
  WP-1029's invariant), two declines with reasons on record (the two-sided δ
  test answers a finite-difference problem the analytic Jacobian does not
  have; cell-before-scale loses to cumulative stages + the frozen-window
  precondition), one open question (a dynamic suggest→fit loop measured
  against the presets — for whoever follows 1107). All of it, the 79-row
  claim grid (44 rows carry an in-repo measurement, 34 a read paper, 23 a
  house label; per-section counts measured by script, recount if rows are
  added) and the §8 pointer table (all nineteen resolve, zero fixes) are in
  `milestones/v1.1.md` § Appendix — created appendix-only; the version flip
  stays with the first code WP. Every requested paper was supplied via the
  corpus and read (Toby 2006, Hill & Flack 1987, Bérar & Lelann 1991,
  Hill 1992, Hill & Cranswick 1994, Madsen 2001, Scarlett 2002; McCusker and
  Schwarzenbach re-verified at the quoted passages); Cox & Papoular is not
  in the corpus, so any claim resting on it stays "pointer unread". **Zero
  claims were attributed to a paper whose read text does not support them**
  — the defect found was *absent* attribution, fixed in place: §2's three
  rules labeled house, the ≈1.51 floor labeled a house derivation
  (√(1+4/π), absent from Bérar & Lelann), §5's benchmarks and three prior
  systems named with DESIGN.md the authority, and ~10 author-year citations
  added where claims already rested on read papers (§4 steps 5/8/9, the
  channel-count rule, §4b's QPA rules, §7's Brindley row, §2/§5/§10 for
  Toby 2024). Forwarded: a citation-resolution coverage test to 1105's
  `### Inherited`; nothing schema-shaped to 1106 (stated there, with the
  Toby-2024 leverage-vs-veto pointer for the `execution` field's docs). No
  `### Inherited` existed here on arrival — nothing to prune. Acceptance
  green: `tests/test_docs_consistency.py` 14 passed, ruff clean (`.venv`,
  `[dev]`, macOS).
- **2026-08-18** — created from the agentic-report planning session, with
  [1105](1105-agent-protocol-hygiene.md)/[1106](1106-report-placement-fields.md)/[1107](1107-eval-placement-round.md).
  The maintainer asked for this pass explicitly: check the protocol is built
  from experience, not inference from theory, before amending it.
