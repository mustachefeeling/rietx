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
    "CLAUDE.md": 736,
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
    "docs/ROADMAP.md": 439,
    "gui/CLAUDE.md": 580,
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
    "tests/CLAUDE.md": 223,
    # 250 at the WP-1060 split; raised once, for WP-1046's two standing rules
    # (which layer may apply a cap, and that agreement outranks the panel) —
    # both measured, and every number behind them is in the v1.0 appendix
    "src/rietx/indexing/CLAUDE.md": 280,
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
