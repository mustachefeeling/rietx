"""The planning docs' mechanical contract (WP-1031).

The session protocol (docs/ROADMAP.md § Session protocol) asks every session
for the same bookkeeping: a controlled Status line, a ROADMAP index row that
mirrors it, `### Inherited` as a mailbox that closed WPs no longer carry, and
links that resolve.  Prose asked for it for four milestones; this file asserts
it, in the same spirit as test_manual.py (the manual cannot drift from the
code) and test_compare_ui.py (the compare registry cannot drift from the
acceptance protocols).

Everything here reads documentation files only — no data, and no rietx import
except in the AGENT_PROTOCOL coverage tests (WP-1105), which import the closed
vocabularies on purpose: quoting the live registry instead of restating it is
the point (the ``capabilities()`` idiom).

Size caps: SIZE_CAPS pins each always-loaded document to its measured size
plus headroom.  A cap of None means "not yet pinned" (the consolidation pass
that measures it also pins it); the failure message names the demotion
destination, because the fix is to move narrative, never to delete facts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WP_DIR = ROOT / "docs" / "wp"
ROADMAP = ROOT / "docs" / "ROADMAP.md"
TEMPLATE = WP_DIR / "TEMPLATE.md"

GLYPHS = {"⬜", "🔄", "✅", "🛑"}
# ⬜ carries no date; every other glyph must say when.
_STATUS_RE = re.compile(
    r"Status: (?P<glyph>⬜|🔄|✅|🛑)"
    r"(?: (?P<date>\d{4}-\d{2}-\d{2}))?"
    r"(?: — |$)",
    re.MULTILINE,
)
# The prune rule lands with WP-1031; WPs closed after this date must have
# consumed (deleted) their ### Inherited mailbox on the way out.
_INHERITED_PRUNE_EPOCH = "2026-07-31"

# Always-loaded documents: measured size + headroom, pinned by the pass that
# achieved it.  Raising a cap is a decision about every future session's fixed
# cost — make it in a commit that says so, not as a side effect.  Do not
# delete facts to fit a cap: move narrative to the WP file or the milestone
# record (the assertion message says where).
#
# History: WP-1031 (2026-07-31) landed CLAUDE.md at 601 and ROADMAP at 494;
# 2026-08-05 raised 700 -> 720 with the written warning that it bought twelve
# lines, not a habit, and that the next WP needing room should consolidate.
# WP-1060 (2026-08-06) was that consolidation: the indexing dossier moved to
# src/rietx/indexing/CLAUDE.md (auto-loads with its subtree), ROADMAP's
# closed-WP narratives moved to the milestone record, Current numbers became
# a measurement recipe — CLAUDE.md landed at 553, ROADMAP at 337 — and every
# always-loaded rulebook is now capped at landed + headroom.  The admission
# rule the caps enforce: a line enters one of these files only as a standing
# rule a stranger needs in six months, evidence compressed to one clause plus
# a pointer (protocol rule 4); a new indexing rule lands in the indexing
# rulebook and earns a root clause only if it changes behavior outside
# indexing/.  WP-1047 (2026-08-09) is the same move for the readers: root
# CLAUDE.md was at exactly 600 with four vendor formats still to land, so the
# reader detail went to src/rietx/io/CLAUDE.md (loads under io/) and root
# kept only the four consequences a caller outside io/ sees.  Landed at 165,
# capped at 200 — the headroom is the remaining formats' per-format rows.
# WP-1067 (2026-08-17) is the same move for ROADMAP, and the cap does NOT move:
# the file was at exactly 400 with 1076's index row still to add, and the
# session before it recorded that a raise was the only fix left because the
# narrative had no second copy.  Measured, two paragraphs had one already — the
# guillemot-study prior art is in v1.0.md § "Indexing joined v1.0" with the
# `git show` recipe, and the vmap sizing note is in v0.4.md twice — so those
# were deleted and the five post-2026-08-05 close narratives moved to v1.0.md
# § "The WP-table narratives, second pass", which is what protocol rule 5 asks
# for on close and this assertion's own message prescribes.  400 -> 355.
# The deletions also exposed what the narrative was hiding: three of the four
# tables under "### v1.0 — indexing" are not indexing WPs, and only the prose
# between them made the splits look deliberate.  They now carry their own
# headings, which is why the saving is 45 lines rather than the 64 removed.
SIZE_CAPS: dict[str, int | None] = {
    # 600 -> 620 for WP-1067 (2026-08-14): the manual became two parts with
    # two different guards, and the operating detail did go down a rank as
    # this comment requires — the derivation's three rules live in
    # tests/api_surface.py's docstring, the chapters' own rules in the WP.
    # What could not go down a rank is the one clause a session that never
    # opens docs/manual/ still needs: adding a public method or field fails
    # the manual's coverage partition until it is documented or deferred.
    # Net +11 lines after the theory-manual bullet was rewritten to cover both.
    # 620 -> 625 for WP-1068 (2026-08-14): the manual bullet gains the clause a
    # session that never opens docs/manual/ still needs — a green sphinx build
    # is not a rendered page, and Part 1's figures are committed artefacts with
    # a generator, so touching either means regenerating and *looking*.  The
    # operating detail went down a rank as this comment requires: the figure
    # recipes are in make_figures.py's docstring, the chapters' own rules in
    # the WP.
    # 625 -> 644 for WP-1070 (2026-08-15): the constraint verbs, and the rule
    # underneath them.  The operating detail went down a rank as this comment
    # requires — the refusal wording, the FAP numbers and the two open freeze
    # asymmetries are in the WP, the narrative in the v1.0 record.  What cannot
    # go down a rank is what a session touching the Jacobian never reads:
    # `_make_jacobian` dispatches on a parameter's *name*, so a branch is a
    # claim about that name's reach, and a constraint that reaches further
    # leaves the column short instead of raising.
    # 648 -> 656 for WP-1071 (2026-08-15): the observation count.  The
    # operating detail went down a rank as this comment requires — the
    # estimator, its three caveats and the one measured deviation from the
    # paper are in `optimize.statistics.effective_observations`' docstring, the
    # sampling floor's evidence in `background.diagnostics`, the acceptance
    # numbers in the WP.  What cannot go down a rank is the shortcut a session
    # adding any support statistic will otherwise take: `n_points` is the
    # algorithm's N and not the number of observations, and the two bands set a
    # diagnostic's level rather than gating a fit.
    # 656 -> 670 for WP-1072 (2026-08-15): the geometry table, and the two
    # rules under it.  The operating detail went down a rank as this comment
    # requires — the listing convention, the cutoffs, the CIF tag check and
    # the NAC numbers are in `model/geometry.py`'s docstring and the WP, the
    # narrative in the v1.0 record.  What cannot go down a rank is what a
    # session adding *any* derived quantity will otherwise get wrong twice:
    # its esd needs the whole covariance (and the diagonal number beside it is
    # not the conservative choice, it is wrong in either direction), and an
    # esd that cannot be measured is absent rather than zero.  The orbit-count
    # clause rides with it because it is the only check that saw the bug.
    # 670 -> 683 for WP-1073 (2026-08-15): a position correction belongs to a
    # geometry.  The operating detail went down a rank as this comment
    # requires — the derivation that fixes eq (4)'s signs is in
    # `capillary_displacement_shift_deg`'s docstring, the two 11-BM
    # measurements and the premises they overturned are in the WP, the
    # narrative in the v1.0 record.  What cannot go down a rank is what a
    # session adding *any* aberration will otherwise get wrong: the template
    # and the action are geometry-scoped (a blind map suggests a force-fixed
    # parameter), a parameter the forward branch skips must be force-fixed
    # rather than merely unfree, and the evidence for a position correction is
    # a stage rung rather than the converged report.
    # 683 -> 700 for WP-1074 (2026-08-16): the restraint weight schedule.  The
    # operating detail went down a rank as this comment requires — the c_w
    # measurements are in the WP and the manual, the seam's own reasoning in
    # `CompiledModel.restraint_weight_scale`'s field comment.  What cannot go
    # down a rank is the constraint on a file a session edits for other
    # reasons: `model/restraints.py` has a second consumer that is not a
    # restraint, so anything weighting a restraint row belongs at the row build
    # and not in the shared partials function — the geometry esds are built
    # from that function's output at unit weight, and no distance-value test
    # in the package would notice them all moving by a constant factor.
    # 700 -> 720 for WP-1076 (2026-08-18): a declared name is a claim, and an
    # absent writer fails no test.  It earns a clause because it governs core
    # work — adding a schema field or a Literal member — rather than manual
    # work: 1067's near-miss rule was about mis-attributing a type in prose and
    # went into a docstring instead, and the cap was what sent it there.
    # 720 -> 736 for WP-1109 (2026-08-20): the structural-freeze question.
    # The operating detail went down a rank as this comment requires — the
    # memo's contract is in `CompiledModel._memo`'s docstring, the profile
    # numbers and the cumulative before/after in the WP, the narrative in the
    # v1.1 record.  What cannot go down a rank is the clause a session adding
    # any compile-time freeze never reads: `free_paths` is the narrower
    # question and a tie defeats it, so a freeze asks `moving_paths` and then
    # verifies its own claim where the claim is used.
    # 736 -> 752 for WP-1110 (2026-08-20): the default cell window and the two
    # diagnostics beside it.  The operating detail went down a rank as this
    # comment requires — TOPAS's Table 2-1, the per-stage-vs-per-iteration
    # translation and the 51-stage-transition measurement are all in
    # `params.vector.cell_window`'s docstring, the episode and the equivalence
    # numbers in the WP.  What cannot go down a rank is the clause a session
    # that never opens params/ still needs: a construction site passes no cell
    # floor rather than a nonsense one, or it silently suppresses the default.
    # 752 -> 759 for WP-1110 (2026-08-21): the plan mirror is crossed at the two
    # authorities that own it.  The operating detail went down a rank as this
    # comment requires — which validator, which converter and why the crossing
    # is by isinstance are in `PlanSpec._accept_the_dataclass` and
    # `resolve_plan`, the friction it closes in the WP.  What cannot go down a
    # rank is the clause a session adding *any* mirror needs before it writes
    # one: two types sharing every field name make a structural test certify an
    # accident, so the crossing tests the class.
    # 759 -> 771 for WP-1110 item 14 (2026-08-21): the covariance is
    # equilibrated, and a direction the data cannot see reports no esd.  The
    # operating detail went down a rank as this comment requires — the cutoff
    # arithmetic, the van der Sluis result and the 0 × inf propagation are in
    # `normal_covariance` and `ParameterTable._cov_free`, the measurements in
    # the WP.  What cannot go down a rank is the pair a session touching *any*
    # statistic will otherwise get wrong: a badly-scaled column silently zeroes
    # a variance rather than raising, and the honest empty state for an
    # unmeasured direction is absence, which every consumer must mark rather
    # than clamp.
    # 771 -> 784 for WP-1120 (2026-08-22): the numpy forward moved onto the
    # batched planes, and three facts about it cannot go down a rank because a
    # session touching *any* profile or accumulation code will otherwise get
    # them wrong — Ω has two spellings that differ by design, the scalar loop
    # is an oracle rather than dead code, and the phase scatter's grouping is
    # observable.  The operating detail did go down: the ratios and the
    # equivalence measurements are in the WP's § Findings, the method notes in
    # the v1.1 record, and the bars are executable in tests/test_batched_forward.py.
    # 784 -> 804 for WP-1115 (2026-08-22): the numpy path now has a compiled
    # tier and it is what a default install runs, which no other line in this
    # file implies and which a session touching any residual, Jacobian or
    # packaging code will get wrong without it — that the tier is not a
    # backend, that its numpy fallback is mandatory *and* must stay exercised
    # (numba is required because an extra cannot subtract a dependency, so the
    # way out is a runtime switch), what shape a new kernel takes, and what bar
    # it is held to.  The measurements, the `prange` comparison and the three
    # traps stayed down a rank: § The decision in the WP, the v1.1 record's
    # narrative, and the bars executable in tests/test_compiled_kernels.py.
    # 804 -> 817 for WP-1121 (2026-08-22): how to *verify* an analytic Jacobian
    # branch, which the clause above it only says how to *scope*.  It earns a
    # clause because the trap is silent and points the wrong way: the
    # whole-model FD is the branch's own fallback, so a session reaches for it
    # as the oracle, and on a transformed parameter it certifies the column
    # being replaced while condemning the exact one that replaces it (measured
    # at 2e-11 agreement with a column 4.6e-6 from the truth).  The operating
    # detail went down a rank as this comment requires — the step sweep, the
    # per-state golden diff and the seam decomposition are in the WP, the
    # column's own reasoning in `_scale_column`'s docstring.
    # 817 -> 833 for WP-1123 (2026-08-22): a staged plan stops its intermediate
    # stages early by default, which changes what every fit in the package
    # returns and is not implied by any other line here.  A session that never
    # opens strategy/ still needs three of its clauses: the schedule is the
    # plan's and is applied by one authority (a runner reading Stage.ftol
    # reintroduces the second opinion), cumulative staging is what bounds the
    # cost so the bound is a property of the runner rather than of the presets,
    # and a record must say what a stage RAN at or a cherry-pick replays what
    # never happened.  The measurements went down a rank as this comment
    # requires: the harness table and the esd shifts are in the WP's handover
    # and the v1.1 record, the trade in docs/manual/using/refining.md, the
    # decision beside the numbers it produced in tests/validation_matrix.py.
    # 833 -> 834 for WP-1122 (2026-08-22): one line, extending a fence that is
    # already here.  The peaks buffer is now behind FPA rather than merely
    # unbuilt, and the clause carries the measured reason a session cannot
    # re-derive cheaply — shape reuse needs more FCJ images a window point than
    # any symmetric family has, so a re-attempt without FPA repeats 1114's and
    # 1122's no-go.  The measurements went down a rank as rule 4 requires: the
    # break-even table, the Amdahl share and the two ways to mis-measure it are
    # in the WP's § Findings and the v1.1 record's narrative.
    # 834 -> 845 for WP-1125 (2026-08-22): a fence, like 1122's, and for the
    # same reason — the idea behind it is attractive enough to be re-proposed
    # by anyone who notices that the background is linear.  What cannot go
    # down a rank is the one sentence that settles it without re-deriving
    # anything: the profiled Gauss-Newton step IS the joint one, so variable
    # projection asks this solver for the step it already takes.  The
    # measurements went down a rank as rule 4 requires: the 70-stage table,
    # the trust-radius mechanism and the two gates that failed for reasons
    # unrelated to their names are in the WP's § Findings, the survey's §2.A1
    # and E5 notes, and the v1.1 record's narrative.
    # 845 -> 855 for WP-1127 (2026-08-22): the ladder's first-rung bound, and
    # like the two fences above it is here because the *wrong* version of it is
    # the attractive one.  Two clauses cannot go down a rank without being
    # re-derived by whoever proposes the next bound: what a bound may be
    # derived from (only a rung that did the same job and converged — the cold
    # fit reads as free evidence and is false), and the two places a bound
    # would otherwise reach the answer, neither of which is where it is
    # applied.  The measurements went down a rank as rule 4 requires: the
    # cold-9-warm-14 refutation, the per-case tables and the pre-registered
    # clause that fired are in the WP's § Findings and the v1.1 record.  The
    # last two lines are the third such trap and the one that cost a CI round:
    # a threshold set for effect rather than for margin, which two of four
    # python versions on the other platform caught and a green local full suite
    # did not.
    # 855 -> 869 for WP-1204 (2026-08-25): developer mode and the shipped
    # example projects.  Two clauses cannot go down a rank.  The first is a
    # property of the *project format*, not of the GUI: there is no read-only
    # way to open one, because every verb writes into the directory as it runs
    # and `Project.open` appends a head annotation before any verb is called —
    # a session that never opens gui/ still has to know that opening a checked-
    # in project dirties it, and what to reach for instead.  The second is
    # where an example's protocol comes from: an example IS a `compare.py`
    # standard, so a WP tempted to write a project builder has to know the
    # registry is the authority.  The third is the data licence fence, which
    # belongs in the Licensing invariant beside the code one because the two
    # are asked at the same moment and only one of them existed.  The operating
    # detail went down a rank as rule 4 requires: the routes, the state-dir
    # placement and the traversal refusal are in gui/CLAUDE.md, the per-file
    # licence table is `tests/test_example_projects.py`'s, and the measured
    # wheel sizes are in the WP's handover.
    # 869 -> 882 for WP-1202 (2026-08-25): the help corpus.  The operating
    # detail went down a rank as this comment requires — the registry's own
    # rules are in `help.py`'s docstring, the entries are the corpus, the
    # measurements are in the WP.  What cannot go down a rank is the one clause
    # a session adding a parameter, a flag or a stage field will otherwise miss:
    # the description goes in `rietx.help`, not in a `title=` beside a control
    # or a second `Field(description=)`, and the row carries the family key
    # rather than the entry.
    # 882 -> 890 for the one-session-per-tree tooling (2026-08-27): the rule a
    # session must read before its first edit, and nothing else — the gate's
    # own rationale is its docstring, the ritual is /wp-start.
    "CLAUDE.md": 890,
    # 400 -> 416 for the agentic-report planning session (2026-08-18): four
    # v1.1 WP rows (1104-1107) plus their focus bullet.  Index rows cannot go
    # down a rank — the WP-file/row bijection test in this file requires one
    # per WP — so the cap grows with the WP count and with nothing else; the
    # sets' narratives live in the WP files.
    # 416 -> 438 for the refinement-speed planning session (2026-08-20): the
    # v1.1 speed set (1109 moved + five new rows and its intro) and the v1.1
    # Milestones row.  Same rule as the bump above: rows cannot go down a
    # rank, so the cap grows with the WP count and with nothing else.
    # 438 -> 439 for WP-1116 (2026-08-20): its own index row, and only that.
    # The same WP also rewrote § Session protocol's rule 3, which is two lines
    # longer — prose, so by the rule above it earns no bump and was paid for
    # by compressing Current focus instead.  That is the rule working: the
    # cap is a budget on narrative, and a row is not narrative.
    # 439 -> 455 for WP-1110 (2026-08-21): one section and two rows for the work
    # the agent round found and no milestone owns yet — 1118 (foreign model
    # files) and 1119 (the named variable a foreign equation refers to).  The
    # rows are not narrative and the prose is eight lines for both, because the
    # fences, the measured behaviour and the acceptance live in the WP files.
    # Current focus was rewritten in the same pass and paid part of it back.
    # 455 -> 457 (2026-08-22): the two probe rows the solver-survey
    # re-assessment opened — 1124 (warm-series continuation, survey B8) and
    # 1125 (variable-projection probe, survey A1/E5).  Rows only: the
    # motivation and disposition live in solver-survey.md §5 and the WP
    # files, and the Current focus mention replaced text inside an existing
    # line.  Same rule as the bumps above: a row is not narrative.
    # 457 -> 458 for WP-1126 (2026-08-22): its own index row, and only that.
    # The manual style pass touches no always-loaded file: the review's rules
    # went into the yue-docs-style skill and the chapters, and the WP file
    # carries the measurements.
    # 458 -> 459 for WP-1127 (2026-08-22): its own index row, and only that.
    # The row is required rather than chosen — test_wp_files_and_roadmap_rows_
    # are_a_bijection makes an index row the one line a new WP cannot demote —
    # and Current focus was not touched at the opening, because the front it
    # takes over is already named there in WP-1124's closing sentence.
    # 459 -> 473 for WP-1131 (2026-08-23): its index row, and the section that
    # had to come with it — the bumps above buy a row inside an existing table,
    # and there was no table for this one.  The five prose lines are the part a
    # row cannot carry: that the defect is *size* and not strain, that the two
    # are distinguished by the wavelength and nothing else, and the measured
    # size of it.  Without them the row reads as a reporting feature, which is
    # the half of the WP that is not a correctness bug.
    # 473 -> 480 for the v1.2 opening (2026-08-25): a milestone section with
    # eighteen index rows (1201-1217 and 1017 moved in), which the bijection
    # test requires one line each, net +7 after Current focus was rewritten
    # from 30 lines to 12 and the peaks section was retitled v1.3 in place.
    # The per-note assessment went down a rank into milestones/v1.2.md.
    # 473 -> 474 for WP-1132 (2026-08-24): its own index row, and only that.
    # The row is required rather than chosen (the bijection test again), and
    # every line of the WP's reasoning stays in its own file — unlike 1131 it
    # needs no section here, because nothing about it has to be read before
    # someone opens it.
    # 474 -> 475 for WP-1134 (2026-08-25): its own index row, and only that.
    # The row is required rather than chosen (the bijection test).  This WP
    # exists because the number did not: the neutron/harmonics/wavelength work
    # was committed under WP-1128, which is the shipped v1.1 indexing WP cited
    # from indexing/svd.py -- two meanings of one number costs more than a
    # renumber, so the in-code citations moved to 1134 and this file names it.
    # 480 -> 482 merging PR #108 into the v1.2 opening (2026-08-25):
    # the two caps above were measured against different parents, so
    # neither survives the merge; 482 is the merged file, both index
    # rows on top of the v1.2 section.
    "docs/ROADMAP.md": 482,
    # 580 -> 612 for WP-1201 (2026-08-25): the house style — one token layer
    # and the nine control registers, as a table of one rule each.  This file
    # grows for a rule nothing else in it carried, same as the bumps above: a
    # panel's `<style>` block was the authority on its own controls, so six
    # button geometries and three chip geometries were all locally correct.
    # The vocabulary has to be here because every later v1.2 panel WP writes
    # markup against it, and a table is the compressed form — the inventory,
    # the measurements and the three misuses it exposed are in the WP.
    # 612 -> 628 for WP-1204 (2026-08-25): the examples surface.  Here rather
    # than in root because it is the *empty state's* second list and its rules
    # are the GUI's own — where a built example lives and why, that the open
    # verb ends in `project_open` so nothing downstream can tell an example
    # from a project, and that `name` is checked against the list rather than
    # sanitised.  The last of the five is a house-style consequence the WP-1201
    # table above could not have carried: `.pick` gives up its box because the
    # row is the target, so a list that gives the row no hover reads as prose.
    # The operating detail went down a rank as rule 4 requires — the licence
    # table is `tests/test_example_projects.py`'s, the protocol-quoting rule is
    # root's, and the browser session that found the missing hover is the WP's.
    # 645 -> 663 for WP-1205 (2026-08-26): the filesystem browser. A stranger
    # touching `App.svelte`'s layout needs the invariant this WP's own bug
    # was found under — `Model` is mounted exactly once, never one instance
    # per branch of `{#if project}` — because the failure mode (a stale
    # `wizardOpen` painting the wizard over a freshly-opened project) is
    # invisible until the *next* session recreates the split and re-derives
    # the same bug from nothing. `GET /api/fs`'s containment shape and the
    # settle-on-open convention (`openPath()`) are the other two facts no
    # test alone would tell a reader to preserve.
    # 628 -> 645 for WP-1203 (2026-08-26): the help popover, replacing the
    # `title=` paragraph WP-1201 wrote as a placeholder.  It belongs here for
    # the reason the register table does: every later v1.2 panel WP writes
    # markup against it, and there are five rules a stranger cannot read off
    # the code — why a key carries its arm, when a field inventory derives its
    # key and when it carries one, what `<Help text=>` is for, what may still
    # be a `title=`, and why a term is a span with a role.  Compressed to one
    # clause each: the 151-attribute inventory, the two decisions taken against
    # this WP's own written design, and the flex-minimum defect the browser
    # pass measured are in `docs/wp/1203-help-popover.md`.  One rule *left*
    # this file in the same pass — WP-1032's "`title=` is these forms' only
    # help mechanism" is no longer true, and its no-mute-fields half stayed.
    # 663 -> 687 for WP-1206 (2026-08-26): a project without a CIF.  Four rules
    # a later panel WP cannot read off the code — that `structure` now has four
    # forms told apart by disjoint keys, that a constrained cell is *offered*
    # rather than validated (which is where the free/determined split has to be
    # decided, and it is a crystallography call, not a form's), that a mode is
    # refused rather than overridden here while Adopt does override, and the two
    # form-drawing facts a browser found: a register's width belongs to the call
    # site, and a numeric placeholder reads as a filled value.  The measured
    # detail — the fit, the four browser defects, TOPAS's macro shape — is in
    # `docs/wp/1206-typed-cell-project.md`.  687 -> 691 in the same WP's review
    # round: the mode clause had to name **both** routes `_as_structure` serves,
    # because a new form added at that one boundary reaches every verb crossing
    # it — the typed cell was accepted by `PATCH /api/structure` too, where it
    # would leave a rietveld project refining a dummy carbon.  That is the
    # generalisable half, and it is what a later WP adding a third form needs.
    # 691 -> 710 for WP-1207 (2026-08-26): the third answer to step 2, whose
    # four rules a later panel WP cannot read off the code.  Two of them are
    # the earlier clause's own shape one turn further — the `structure` forms
    # are told apart at one boundary, so the fifth (`null`) had to be decided
    # *ahead* of the inline branch it used to fall through; and null is an
    # answer where an absent key is not, which `dict.get` cannot express.  The
    # other two are where the refusal lives (the verb, never the model — so
    # peak picking and indexing keep working) and why `n_phases` rides on the
    # project document, which is what lets a client disable Run rather than
    # offer a click whose only outcome is a 400.
    # 710 -> 733 for WP-1208 (2026-08-27): the plan resolved against the live
    # table.  The operating detail went down a rank as this comment requires —
    # the three-bucket partition, how the dynamic held-reason is reached
    # without spelling its sentence twice, and the node-to-rung alignment are
    # in `GuiSession.plan_resolve`'s docstring, the panel's own rules in
    # `Plan.svelte`'s header comment, the measurements in the WP.  What cannot
    # go down a rank is the one a later panel WP will otherwise get wrong: a
    # plan does not continue the vary flags a person set, it replaces them, so
    # `Run all` and `Run this stage` start from different tables — and the
    # per-stage Rwp already exists on the history node, which is why the run
    # verb did not have to grow a trajectory to show it.
    # 733 -> 753 for WP-1209 (2026-08-27): the peak table's numbers and chips.
    # Two of its four rules reach past the panel — an esd that has swallowed
    # its value is not a precision (every caller of formatValue), and a chip's
    # words are the corpus's label — and the fourth is a browser-only trap: a
    # `td` that is not `display: table-cell` merges with its flex neighbour
    # into one anonymous cell, which jsdom cannot see and a shared class name
    # triggered.
    # 753 -> 774 for WP-1210 (2026-08-27): the peak layer.  Its four rules all
    # reach past the panel — where a layer may be drawn at all (and that the
    # tab is therefore a drawing input, not a fact about the payload), that an
    # undrawable curve is listed with its reason rather than dropped, that
    # chrome tokens are not a palette (`--accent` *is* `--plot-diff` on the
    # light theme, which is the reported defect), and that a mark's state is
    # carried by its shape rather than by spending a colour.  The hex values,
    # the hue search and the two grandfathered pairs are a rank down, in
    # `app.css`'s own comment and `tests/test_gui_palette.py`.  774 -> 778 in
    # the same WP's review: the state-on-the-mark rule needed its corollary,
    # because that is where it was broken — a mark that is not the data may not
    # borrow the recessive ink of the data it sits on.
    # 778 -> 808 for WP-1211 (2026-08-27): the candidate overlay, whose five
    # rules are each about a *different* thing a later panel will meet — which
    # of two shifts belongs on a drawn position, how a cap admits it capped, why
    # a layer selected from a row gets no toggle, why a preview and a selection
    # have to be two props, and what "full height" costs in plotly.  None of
    # them generalises from another, and the two the drawing depends on are
    # browser findings.  The operating detail went a rank down as this comment
    # requires: the shift algebra and the enumeration counts are in
    # `GuiSession.index_ticks`'s docstring, the drawing order and the axis in
    # `Plot.svelte`'s, and the measured numbers in the WP's handover.
    # 808 -> 838 for WP-1212 (2026-08-27): a redraw never moves the axes.  Six
    # rules, four of them browser findings that no reading of the code reaches
    # and none derivable from another — what `autorange === false` stopped
    # meaning, which field carries the range plotly is *drawing* with, that a
    # layout key is a relayout rather than a repaint, that a `$derived` off the
    # project arrives new-but-equal on every settings PATCH, that two `$state`
    # assignments either side of an `await` are two flushes, and that an empty
    # `scattergl` trace has no index in the scene its peers share.  The first
    # two rewrite what the WP-1044 section above claims, so they cannot live
    # only in a WP file.  Operating detail went a rank down as this comment
    # requires: the pin's mechanics are `pinPatch`'s and `drawnRange`'s
    # docstrings, the gesture's ink is the `.select-outline` rule's comment,
    # and every measured number is in the WP's handover table.  840 after the
    # review pass added the seventh: an axis with nothing on it is not pinned.
    # 840 -> 874 for WP-1213 (2026-08-27): the hover readout.  Seven rules, and
    # the first of them rewrites what a stranger would otherwise try — the
    # unified box has no positioning, so it is deleted and `hoverinfo: "none"`
    # is what keeps the spike; a WP file cannot hold that, because the next
    # session's instinct is to move the box.  Three are browser findings no
    # reading of the code reaches (the strip must not reflow, the spike's ink
    # collided with the mask edge, two spellings of minus in one row), one is a
    # svelte trap the whole app can hit (`$state.raw` for a payload that is
    # replaced whole), and none derives from another.  Operating detail went a
    # rank down as this comment requires: the field list and the resting state
    # are `readout`'s docstring, the strip's widths are the `.readout` rule's
    # comment, and every measured number is in the WP's handover.  879 after
    # the peaks-tab pass added the eighth: a curve is read at the nearest drawn
    # channel and a nearby thing is hit-tested against the pointer, because the
    # drawn pattern is decimated and the two are not the same position.
    # 879 -> 902 for WP-1214: the refine flag in the model editor, and with it
    # the fourth held reason (`needs_held_cell`) that WP-1011's three-mark
    # sentence had been wrong about since it arrived.  Four rules and one width
    # trap; the measurements are in the WP's handover.
    # 902 -> 938 for WP-1215: the atom table becomes one row per atom, and the
    # coordinate becomes a cell in it.  Four rules, and the third and fourth are
    # the ones no reading of this subtree reaches — a memoised answer changes
    # *who may ask* without changing which route it is on (with the three client
    # rules that come with fetching it beside another fetch rather than after
    # it), and a width written in three places had a test on one of them.  The
    # operating detail went a rank down as this comment requires: the refusal
    # wording is `position_values`' docstring, the per-state pixel measurements
    # are `MODEL_MIN`'s and the WP's handover.
    "gui/CLAUDE.md": 938,
    # 180 -> 198 for WP-1070 (2026-08-15): the running ladder.  It is a rule
    # about *cadence*, which nothing else in this file carried — the sections
    # below all say how to run or read one suite, none said how often the
    # expensive one should fire.  Measured occasion: one session's ~80 min of
    # test time against ~43 min earned, the whole difference being a full run
    # launched mid-edit and therefore repeated.
    # 198 -> 205 for WP-1003 (2026-08-16): the budget section's numeric twin —
    # a cross-fit agreement tolerance needs the measured cross-platform
    # spread.  The section covered wall-clock budgets only, and the weekly CI
    # failure that taught the rule was numeric.
    # 205 -> 223 for WP-1110 (2026-08-20): a second eval protocol exists
    # (tests/eval_agent_surface/), and a session under tests/ that does not
    # know it will either miss it or pool its cells with the first one's.  The
    # clause is a rule about comparability and about what a shim owes its
    # subject, not a record of the round — that lives in the WP and the
    # protocol.  Same rule as the bumps above: this file grows for a rule that
    # nothing else in it carried.
    # 223 -> 232 for WP-1115 (2026-08-22): a test that pins a number must
    # declare its *path*, not only its settings.  Nothing else in this file
    # carried it — the dispersion clause one rank up is about a schema default,
    # and this is about which implementation computed the double — and the
    # failure has a signature worth naming, because it is otherwise read as
    # flakiness: green alone, red under `-n auto`.  The tier itself, its bars
    # and its measurements are all a rank down (root CLAUDE.md, the WP).
    # 232 -> 246 (2026-08-26): rung 3 is exclusive across the sessions sharing
    # this machine.  Nothing here carried it — the budget rules below say load
    # breaks an assertion, not that a second session is what supplies the load —
    # and it could not go down a rank, being about *running* the suite, which no
    # other always-loaded file governs.  It is a look (`pgrep`) and not a lock
    # on purpose, which is what kept the raise to fourteen lines: reserving
    # would have needed a script, a release to forget and a staleness rule,
    # while observing needs one command and can state its own evidence.
    "tests/CLAUDE.md": 246,
    # 250 at the WP-1060 split; raised once, for WP-1046's two standing rules
    # (which layer may apply a cap, and that agreement outranks the panel) —
    # both measured, and every number behind them is in the v1.0 appendix
    # 280 -> 296 for WP-1110 item 14 (2026-08-21): a component at its zero
    # intensity bound is not a line.  The operating detail went down a rank as
    # this comment requires — the flag's semantics are on `PeakFlag` and
    # `PEAK_UNUSABLE_FLAGS`, the mechanism in `peaks_of_group`, the numbers in
    # the WP.  What cannot go down a rank is that this class of phantom was
    # *invisible* until the covariance was equilibrated, so a session reading
    # the peak list's history will otherwise assume the not_separable fix
    # cleared it.
    "src/rietx/indexing/CLAUDE.md": 296,
    # 200 at the .ras/.uxd consolidation; raised once with three container
    # formats still to land, each of which is a row in its per-format table
    "src/rietx/io/CLAUDE.md": 250,
}
CURRENT_FOCUS_CAP: int | None = 60  # lines within ROADMAP's Current focus (WP-1031 landed at 33; the 1060 rewrite at 44)


def _wp_files() -> list[Path]:
    return sorted(p for p in WP_DIR.glob("[0-9]*.md"))


def _status_of(path: Path) -> tuple[str, str | None]:
    text = path.read_text(encoding="utf-8")
    m = _STATUS_RE.search(text)
    assert m, f"{path.name}: no Status line matching the TEMPLATE format"
    return m.group("glyph"), m.group("date")


def _index_rows() -> dict[str, tuple[str, str]]:
    """WP id -> (linked filename, status cell) from every ROADMAP index row."""
    rows: dict[str, tuple[str, str]] = {}
    row_re = re.compile(r"^\| \[(\d{4})\]\((wp/[^)]+\.md)\) \|")
    for line in ROADMAP.read_text(encoding="utf-8").splitlines():
        m = row_re.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.split("|")]
        # cells[0] is '' before the leading pipe; status is the third column
        assert len(cells) >= 5, f"ROADMAP row for {m.group(1)} has too few cells"
        assert m.group(1) not in rows, f"ROADMAP indexes WP {m.group(1)} twice"
        rows[m.group(1)] = (m.group(2), cells[3])
    return rows


def test_template_declares_the_vocabulary_this_file_enforces():
    """TEMPLATE.md and this test must name the same glyphs — neither may drift."""
    text = TEMPLATE.read_text(encoding="utf-8")
    for glyph in GLYPHS:
        assert glyph in text, f"TEMPLATE.md does not declare {glyph}"
    assert "🔶" not in text, "TEMPLATE.md declares 🔶, which practice replaced with 🔄"


def test_every_wp_status_line_is_controlled():
    for path in _wp_files():
        glyph, date = _status_of(path)
        assert glyph in GLYPHS, f"{path.name}: glyph {glyph!r} not in {GLYPHS}"
        if glyph != "⬜":
            assert date, f"{path.name}: {glyph} requires a YYYY-MM-DD date"


def test_wp_files_and_roadmap_rows_are_a_bijection():
    rows = _index_rows()
    files = {p.name[:4]: p for p in _wp_files()}
    missing_rows = sorted(set(files) - set(rows))
    missing_files = sorted(set(rows) - set(files))
    assert not missing_rows, f"WP files with no ROADMAP index row: {missing_rows}"
    assert not missing_files, f"ROADMAP rows with no WP file: {missing_files}"
    for wp_id, (link, _cell) in rows.items():
        assert (ROOT / "docs" / link).is_file(), f"row {wp_id} links {link}, not a file"
        assert link == f"wp/{files[wp_id].name}", (
            f"row {wp_id} links {link}, file is wp/{files[wp_id].name}"
        )


def test_roadmap_glyph_mirrors_the_wp_status_line():
    rows = _index_rows()
    for wp_id, path in ((p.name[:4], p) for p in _wp_files()):
        file_glyph, _ = _status_of(path)
        cell = rows[wp_id][1]
        cell_glyphs = [g for g in cell if g in GLYPHS]
        assert cell_glyphs, f"ROADMAP row {wp_id}: status cell {cell!r} has no glyph"
        assert cell_glyphs[0] == file_glyph, (
            f"WP {wp_id}: file says {file_glyph}, ROADMAP row says {cell_glyphs[0]}"
        )


def test_inherited_is_h3_and_closed_wps_have_consumed_theirs():
    """`## Inherited` (H2) is a format drift; a mailbox outliving its WP is a leak.

    The section is a channel to work that has not finished: pruned on every
    session start, deleted (fully consumed) when the WP closes.  WPs closed
    before the rule existed keep theirs as frozen archive.
    """
    for path in _wp_files():
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^## Inherited\b", text, re.M), (
            f"{path.name}: '## Inherited' must be '### Inherited' (H3)"
        )
        glyph, date = _status_of(path)
        if glyph in {"✅", "🛑"} and date and date > _INHERITED_PRUNE_EPOCH:
            # heading-anchored like the H2 check above: a WP that *mentions*
            # the section name in prose (1061 is about the handover protocol)
            # is not carrying a mailbox
            assert not re.search(r"^### Inherited\b", text, re.M), (
                f"{path.name}: closed {date} but still carries '### Inherited' — "
                "fold what was consumed into Context and delete the section "
                "(protocol step 1)"
            )


# The two entry forms TEMPLATE.md sanctions and .claude/hooks/session_start.py
# parses.  Kept as literal source here rather than imported from the hook: the
# point is that the two agree, and a shared constant could not fail.
_ENTRY_BULLET_RE = re.compile(r"^- \*\*\d{4}-\d{2}-\d{2}", re.M)
_ENTRY_HEADING_RE = re.compile(r"^#{3,4} \d{4}-\d{2}-\d{2}", re.M)


def _handover_log(path: Path) -> str | None:
    """The `## Handover log` section, bounded at the next H2 — several WPs put
    `## References` after it."""
    _, sep, log = path.read_text(encoding="utf-8").partition("\n## Handover log")
    if not sep:
        return None
    return re.split(r"^## ", log, maxsplit=1, flags=re.M)[0]


def test_every_handover_entry_is_in_a_form_the_session_hook_can_read():
    """A handover the SessionStart scan cannot see is a handover that did not
    happen — it reports the WP as owing one at the next session, and a false
    alarm teaches the reader to skip the one line that is ever load-bearing.

    Measured 2026-08-20: WP-1109 and WP-1110 had adopted `### YYYY-MM-DD`
    headings, which multi-session days need and a date bullet cannot express,
    and the hook read only bullets — so it flagged both as un-handed-over on
    the morning after three handed-over sessions.
    """
    for path in _wp_files():
        log = _handover_log(path)
        assert log is not None, f"{path.name}: no '## Handover log' section"
        assert _ENTRY_BULLET_RE.search(log) or _ENTRY_HEADING_RE.search(log), (
            f"{path.name}: the handover log has no entry in either sanctioned "
            "form — '- **YYYY-MM-DD** — …' or '### YYYY-MM-DD — …' "
            "(docs/wp/TEMPLATE.md § Handover log)"
        )
        for line in log.splitlines():
            if line.startswith("#") and not re.match(r"^#{3,4} \d{4}-\d{2}-\d{2}", line):
                raise AssertionError(
                    f"{path.name}: heading in the handover log does not open "
                    f"with a date, so the scan cannot see it: {line!r}"
                )


def test_template_declares_both_handover_entry_forms():
    """TEMPLATE.md is where a session learns the format; the hook and this test
    both depend on it saying the same thing."""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "- **YYYY-MM-DD**" in text
    assert "### YYYY-MM-DD" in text
    assert "session_start.py" in text, (
        "TEMPLATE.md must name the hook that reads these entries — the format "
        "is a contract with it, not a house style"
    )


_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _planning_docs() -> list[Path]:
    docs = [ROOT / "CLAUDE.md"]
    for extra in ("gui/CLAUDE.md", "tests/CLAUDE.md", "src/rietx/gui/CLAUDE.md",
                  "src/rietx/io/CLAUDE.md", "src/rietx/indexing/CLAUDE.md"):
        if (ROOT / extra).is_file():
            docs.append(ROOT / extra)
    docs += sorted((ROOT / "docs").glob("*.md"))
    docs += sorted((ROOT / "docs" / "wp").glob("*.md"))
    docs += sorted((ROOT / "docs" / "milestones").glob("*.md"))
    return docs  # docs/manual/ is excluded: MyST links are sphinx's to check (-W)


def test_every_relative_link_resolves():
    broken: list[str] = []
    for doc in _planning_docs():
        for target in _LINK_RE.findall(doc.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            rel = target.split("#", 1)[0]
            if not rel:
                continue
            if not (doc.parent / rel).exists():
                broken.append(f"{doc.relative_to(ROOT)} -> {target}")
    assert not broken, "broken relative links:\n" + "\n".join(broken)


def test_every_shipped_milestone_row_names_its_record():
    """A ✅ milestone row must link a record file; the link test resolves it."""
    text = ROADMAP.read_text(encoding="utf-8")
    section = text.split("## Milestones", 1)[1].split("## Work packages", 1)[0]
    for line in section.splitlines():
        if not line.startswith("|") or "✅" not in line:
            continue
        assert re.search(r"\(milestones/v[\d.]+\.md\)", line), (
            f"shipped milestone row without a record link: {line[:80]}"
        )


@pytest.mark.parametrize("relpath", sorted(SIZE_CAPS))
def test_always_loaded_docs_stay_under_their_pinned_caps(relpath: str):
    cap = SIZE_CAPS[relpath]
    if cap is None:
        pytest.skip("cap pinned by the consolidation pass that measures it (WP-1031)")
    n_lines = len((ROOT / relpath).read_text(encoding="utf-8").splitlines())
    assert n_lines <= cap, (
        f"{relpath} is {n_lines} lines (cap {cap}).  Do not delete facts to fit: "
        "move narrative to the WP file or the in-flight milestone record "
        "(docs/milestones/, § 'How vX.Y is getting here') per protocol rule 4/5."
    )


def test_current_focus_stays_a_focus_not_a_diary():
    if CURRENT_FOCUS_CAP is None:
        pytest.skip("cap pinned by the consolidation pass that measures it (WP-1031)")
    text = ROADMAP.read_text(encoding="utf-8")
    section = text.split("## Current focus", 1)[1]
    for heading in ("\n## ",):
        idx = section.find(heading)
        if idx != -1:
            section = section[:idx]
    n_lines = len(section.splitlines())
    assert n_lines <= CURRENT_FOCUS_CAP, (
        f"Current focus is {n_lines} lines (cap {CURRENT_FOCUS_CAP}).  On WP close "
        "it is rewritten, and the outgoing narrative MOVES to the in-flight "
        "milestone record (protocol rule 5) — it does not accumulate here."
    )


# ----------------------------------------------------------------------
# AGENT_PROTOCOL.md coverage (WP-1105)
#
# Root CLAUDE.md's rule — "a WP that adds a diagnostic code or a correction
# adds its row there" — was enforced by nothing, and the drift it permits is
# silent: two engine codes shipped without a row and no test went red.  These
# three tests give the rule teeth.  They deliberately import the closed
# vocabularies rather than restating them, so a new member fails coverage the
# day it lands.
# ----------------------------------------------------------------------

AGENT_PROTOCOL = ROOT / "docs" / "AGENT_PROTOCOL.md"
SRC = ROOT / "src" / "rietx"
REFERENCES_BIB = ROOT / "docs" / "manual" / "references.bib"

#: Diagnostic codes the AST walk below cannot see statically, each mapped to a
#: comment naming its emitter.  Empty today: every engine code is a
#: ``code="..."`` keyword literal.  A code built dynamically (f-string,
#: constant indirection) goes here — never silently uncovered.
STATIC_INVISIBLE_CODES: dict[str, str] = {}


def _protocol_text() -> str:
    return AGENT_PROTOCOL.read_text(encoding="utf-8")


def _engine_codes() -> set[str]:
    """Every UPPER_SNAKE ``code="..."`` keyword literal under src/rietx.

    ``gui/`` is excluded on purpose: the GUI server's session codes
    (NOT_FOUND, RUN_IN_FLIGHT, ...) share the shape but are a separate
    namespace with no protocol rows — §9c's namespace note declares the
    split.  The lowercase ``GateFailure`` codes fall out of the shape filter
    and are covered by the vocabulary test instead.
    """
    import ast

    codes: set[str] = set()
    for py in sorted(SRC.rglob("*.py")):
        if "gui" in py.relative_to(SRC).parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if (kw.arg == "code" and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                        and re.fullmatch(r"[A-Z][A-Z0-9_]+", kw.value.value)):
                    codes.add(kw.value.value)
    return codes


def test_every_vocabulary_member_appears_in_the_protocol():
    """Every ``GateCode`` and ``ActionKind`` member has protocol coverage.

    WP-1003 promoted gate failures to typed codes precisely so a consumer can
    branch on the name; a member the protocol never names is a branch the
    consumer cannot learn.  The §6 gate table and the §5 action table are the
    rows this asserts exist (as backticked mentions, so a passing rename
    cannot hide in prose).
    """
    from typing import get_args

    from rietx.report.schemas import ActionKind, GateCode

    members = (*get_args(GateCode), *get_args(ActionKind))
    assert len(members) >= 22, "vocabulary import broke — Literals moved?"
    text = _protocol_text()
    missing = [m for m in members if f"`{m}`" not in text]
    assert not missing, (
        f"vocabulary members with no AGENT_PROTOCOL mention: {missing} — "
        "add the row to §6's gate table or §5's action table"
    )


def test_every_engine_diagnostic_code_has_a_protocol_row():
    """Root CLAUDE.md: a WP that adds a diagnostic code adds its row there.

    Collector liveness was proven the required way round (WP-1105): run
    against the tree before the rows landed, it failed on exactly the two
    codes known to be missing (EXTINCTION_SCREEN_FAILED,
    INDEX_VALIDATION_FAILED) out of 79 collected.
    """
    from rietx.agent import ERROR_CODES

    codes = _engine_codes() | set(ERROR_CODES) | set(STATIC_INVISIBLE_CODES)
    assert len(codes) >= 60, (
        f"only {len(codes)} codes collected — the AST walk broke, it does not "
        "mean the protocol got shorter"
    )
    text = _protocol_text()
    missing = sorted(c for c in codes if f"`{c}`" not in text)
    assert not missing, (
        f"engine diagnostic codes with no AGENT_PROTOCOL row: {missing} — "
        "add each to the §7 table its family lives in (root CLAUDE.md's rule)"
    )


_WP_REF = re.compile(r"\bWP-(\d{4})\b")
_CITE_NAME = r"[A-Z][A-Za-zöëüéèçå'-]+"
# an author chain ("Hill", "Hill & Flack", "Madsen et al.", "Dreele, Cox,
# Louër & Scardi") followed by a year that is not part of a date
_CITATION = re.compile(
    rf"({_CITE_NAME}(?:'s)?(?:,? (?:&|and) {_CITE_NAME}|, {_CITE_NAME}"
    rf"|,? et al\.?)*),? \(?((?:18|19|20)\d{{2}})(?![-\d])")


def test_every_wp_and_citation_the_protocol_names_resolves():
    """WP-1104 verified both halves by hand; this is what stops the redrift.

    Every ``WP-NNNN`` named inline exists as a WP file, and every author-year
    citation resolves where the protocol's See-also says it does: in the
    manual's bibliography, or inline (its journal follows the year at first
    mention — ``1992, *J. Appl. Cryst.* ...``).  The chain's *whole* author
    list is consulted against the bib, so a partial regex match ("Scardi,
    1999" out of the five-author McCusker reference) still resolves to the
    right entry.
    """
    text = _protocol_text()

    missing_wps = sorted({n for n in set(_WP_REF.findall(text))
                          if not list(WP_DIR.glob(f"{n}-*.md"))})
    assert not missing_wps, f"WPs named with no docs/wp file: {missing_wps}"

    bib = REFERENCES_BIB.read_text(encoding="utf-8")
    entries = []  # (author field lowercased, year) per entry
    for block in bib.split("\n@"):
        author = re.search(r"author\s*=\s*\{([^}]*)\}", block)
        year = re.search(r"year\s*=\s*\{(\d{4})\}", block)
        if author and year:
            entries.append((author.group(1).lower(), year.group(1)))
    assert len(entries) > 50, "references.bib parse broke"

    unresolved: list[str] = []
    for m in _CITATION.finditer(text):
        chain, year = m.group(1), m.group(2)
        surnames = [s[:-2] if s.endswith("'s") else s
                    for s in re.findall(_CITE_NAME, chain) if s != "Von"]
        in_bib = any(y == year and any(s.lower() in a for s in surnames)
                     for a, y in entries)
        inline = any(
            re.search(rf"{re.escape(s)}[^\n]*?\(?{year}[a-z]?,\s*\*", text)
            for s in surnames)
        if not (in_bib or inline):
            unresolved.append(f"{chain}, {year}")
    assert not unresolved, (
        "author-year citations resolving neither in docs/manual/references.bib "
        f"nor inline: {sorted(set(unresolved))}"
    )
