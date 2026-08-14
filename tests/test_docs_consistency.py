"""The planning docs' mechanical contract (WP-1031).

The session protocol (docs/ROADMAP.md § Session protocol) asks every session
for the same bookkeeping: a controlled Status line, a ROADMAP index row that
mirrors it, `### Inherited` as a mailbox that closed WPs no longer carry, and
links that resolve.  Prose asked for it for four milestones; this file asserts
it, in the same spirit as test_manual.py (the manual cannot drift from the
code) and test_compare_ui.py (the compare registry cannot drift from the
acceptance protocols).

Everything here reads documentation files only — no rietx import, no data.

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
SIZE_CAPS: dict[str, int | None] = {
    "CLAUDE.md": 600,
    "docs/ROADMAP.md": 400,
    "gui/CLAUDE.md": 580,
    "tests/CLAUDE.md": 180,
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
