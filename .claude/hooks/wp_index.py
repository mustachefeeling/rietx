"""The WP index, `docs/wp/README.md`, read off the WP files (WP-1507).

Every row is one WP file's header: the title, and the `Milestone:`, `Track:`,
`Status:`, `Priority:` and `Depends on:` lines.  The headings the rows sit
under are ROADMAP.md's `###` and `####` under § Work packages, which keep the
prose.  So filing, starting, closing or re-rating a WP edits its own file,
and this script writes the row.

    python3 .claude/hooks/wp_index.py            # write docs/wp/README.md
    python3 .claude/hooks/wp_index.py --check    # exit 1 if it is stale
    python3 .claude/hooks/wp_index.py --merge %O %A %B   # git's merge driver

**The merge driver merges the index, never the WP files.**  Git runs a driver
from the top of the tree while that tree still holds the pre-merge files
(measured 2026-09-27), so regenerating there would write the old rows.  The
index is keyed by WP number instead: each version is parsed back into rows,
each row is merged three ways, and the result is rendered.  Two branches
adding adjacent rows then merge clean, which is the conflict 7 of 17 ROADMAP
merges hit.  A row both sides changed differently falls back to `git
merge-file`, whose markers the author resolves by rerunning this script.

`tests/test_docs_consistency.py` reads the WP headers through `read_header`
here, so the index and the tests share one parser.  Stdlib only: the
SessionStart hook sets the driver, and a merge must not need the venv.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
WP_DIR = Path("docs") / "wp"
INDEX = WP_DIR / "README.md"
ROADMAP = Path("docs") / "ROADMAP.md"
COMMAND = "python3 .claude/hooks/wp_index.py"

GLYPHS = ("⬜", "🔄", "✅", "🛑")
CLOSED = ("✅", "🛑")
PRIORITIES = ("P1", "P2", "P3", "P4")
# The `Next` list: the tiers a session's tokens should go to first.
NEXT_TIERS = ("P1", "P2")

# ⬜ carries no date; every other glyph must say when.
STATUS_RE = re.compile(
    r"Status: (?P<glyph>⬜|🔄|✅|🛑)"
    r"(?: (?P<date>\d{4}-\d{2}-\d{2}))?"
    r"(?: — |$)",
    re.MULTILINE,
)
PRIORITY_RE = re.compile(
    r"^Priority: (?P<tier>P[1-4]) (?P<date>\d{4}-\d{2}-\d{2}) — \S", re.M
)
MILESTONE_RE = re.compile(r"^Milestone: (\S+) ·", re.M)
TITLE_RE = re.compile(r"^# WP-(\d{4}) — (.+)$", re.M)
TRACK_RE = re.compile(r"^Track: (.+)$", re.M)
# The Depends paragraph runs to the next header line or a blank line.
DEPENDS_RE = re.compile(r"^Depends on: (.*?)(?=\n(?:[A-Z][a-z]+: |\n)|\Z)", re.M | re.S)
SECTION_RE = re.compile(r"^(v\d+\.\d+(?:\.x)?|Unscheduled|v2\+)(?=\s|$)")

# A WP number (bare or WP-prefixed, never part of a date) or an issue/PR ref.
_REF = r"(?:(?<![\w-])(?:WP-)?\d{4}(?![\w-])|(?<![\w&])#\d+\b)"
_REF_RE = re.compile(_REF)
# "1326 soft", "1311, 1321 soft", "PR #385 soft", "1462 (soft)": every ref in
# the run is soft.
_SOFT_RE = re.compile(rf"((?:(?:PR )?{_REF}(?:, | and ))*(?:PR )?{_REF}) \(?soft\b")
_PARENS_RE = re.compile(r"\([^()]*\)")
# "1020–1022", "1301-1305", "WP-1201…WP-1217": every WP between the two.
_RANGE_RE = re.compile(r"(?<![\w-])(?:WP-)?(\d{4}) ?(?:–|-|…|\.\.\.) ?(?:WP-)?(\d{4})(?![\w-])")


@dataclass(frozen=True)
class Header:
    """What one WP file's header says, parsed strictly."""

    number: str
    file: str
    title: str
    milestone: str
    track: Optional[str]
    glyph: str
    date: Optional[str]
    tier: Optional[str]
    depends: str


def read_header(path: Path) -> Header:
    """Parse `path`'s header, raising ValueError naming the file and the line."""
    text = path.read_text(encoding="utf-8")
    head = text.split("\n## ", 1)[0]
    title = TITLE_RE.search(head)
    if not title or title.group(1) != path.name[:4]:
        raise ValueError(f"{path.name}: first heading is not '# WP-{path.name[:4]} — <title>'")
    milestone = MILESTONE_RE.search(head)
    if not milestone:
        raise ValueError(f"{path.name}: no 'Milestone: <token> ·' line")
    status = STATUS_RE.search(head)
    if not status:
        raise ValueError(f"{path.name}: no Status line matching the TEMPLATE format")
    depends = DEPENDS_RE.search(head)
    if not depends:
        raise ValueError(f"{path.name}: no 'Depends on:' line")
    if "\nPriority:" in head:
        priority = PRIORITY_RE.search(head)
        if not priority:
            raise ValueError(
                f"{path.name}: Priority line is not 'Priority: P<n> YYYY-MM-DD — <why>'"
            )
        tier: Optional[str] = priority.group("tier")
    else:
        tier = None
    track = TRACK_RE.search(head)
    return Header(
        number=path.name[:4],
        file=path.name,
        title=title.group(2).strip(),
        milestone=milestone.group(1),
        track=track.group(1).strip() if track else None,
        glyph=status.group("glyph"),
        date=status.group("date"),
        tier=tier,
        depends=" ".join(depends.group(1).split()),
    )


def wp_files(root: Path = ROOT) -> list[Path]:
    return sorted((root / WP_DIR).glob("[0-9]*.md"))


def headers(root: Path = ROOT) -> list[Header]:
    return [read_header(p) for p in wp_files(root)]


@dataclass(frozen=True)
class Group:
    """One `###` section, or one `####` track inside it, under Work packages."""

    token: str  # the milestone token the section opens with
    heading: str  # the heading's text, as ROADMAP writes it
    track: Optional[str]  # None for the section itself

    @property
    def anchor(self) -> str:
        base = _slug(self.token)
        return base if self.track is None else f"{base}-{_slug(self.track)}"


def _slug(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "-", text.lower()).strip("-")


def roadmap_groups(roadmap_text: str) -> list[Group]:
    """Every section and track under ROADMAP § Work packages, in order."""
    body = roadmap_text.split("\n## Work packages", 1)[1]
    body = re.split(r"^## ", body, maxsplit=1, flags=re.M)[0]
    groups: list[Group] = []
    section: Optional[Group] = None
    for line in body.splitlines():
        if line.startswith("### "):
            m = SECTION_RE.match(line[4:])
            if not m:
                raise ValueError(
                    f"ROADMAP section {line!r} does not open with a milestone token "
                    "(vN.N, vN.N.x, Unscheduled, v2+)"
                )
            section = Group(m.group(1), line[4:].strip(), None)
            groups.append(section)
        elif line.startswith("#### "):
            if section is None:
                raise ValueError(f"ROADMAP track {line!r} sits above any section")
            groups.append(Group(section.token, section.heading, line[5:].strip()))
    return groups


@dataclass(frozen=True)
class Row:
    """One index row: the cells, and the group it sits under."""

    number: str
    file: str
    title: str
    status: str
    priority: str
    depends: str
    token: str
    track: Optional[str]

    @property
    def glyph(self) -> str:
        return self.status[0]


def depends_cell(text: str, numbers: dict[str, str], own: str) -> str:
    """Hard dependencies, then the soft ones in brackets, as the rows wrote them.

    Hard: a WP number or `#N` outside brackets.  Soft: any ref the words
    "… soft" follow, inside brackets or not.  A range names every WP in it.
    A four-digit number that is not a WP (a year, a count) is not a ref.
    """
    text = _RANGE_RE.sub(
        lambda m: ", ".join(n for n in sorted(numbers) if m.group(1) <= n <= m.group(2)),
        text,
    )

    def refs(s: str) -> list[str]:
        out = []
        for ref in _REF_RE.findall(s):
            ref = ref.removeprefix("WP-")
            if (ref.startswith("#") or ref in numbers) and ref != own and ref not in out:
                out.append(ref)
        return out

    soft = [r for m in _SOFT_RE.finditer(text) for r in refs(m.group(1))]
    bare = text
    while _PARENS_RE.search(bare):
        bare = _PARENS_RE.sub("", bare)
    hard = [r for r in refs(_SOFT_RE.sub("", bare)) if r not in soft]
    soft = [r for i, r in enumerate(soft) if r not in hard and r not in soft[:i]]

    def link(ref: str) -> str:
        return ref if ref.startswith("#") else f"[{ref}]({numbers[ref]})"

    cell = ", ".join(map(link, hard)) or "—"
    if soft:
        cell += " (" + ", ".join(map(link, soft)) + " soft)"
    return cell


def _sentence_case(title: str) -> str:
    """A heading's first word capitalised when it is a plain word.

    A WP file's heading is a lowercase phrase and a table row starts with a
    capital.  A first word holding anything but letters and hyphens (a name
    such as ``rietview:``, ``fit_peaks``, ``v0.3``, code in backticks) is
    left as written.
    """
    return title[0].upper() + title[1:] if re.match(r"[a-z][a-z-]* ", title) else title


def rows_from_headers(hs: list[Header], groups: list[Group]) -> dict[str, Row]:
    """Place each header under its ROADMAP group; a group ROADMAP lacks raises."""
    numbers = {h.number: h.file for h in hs}
    shared = sorted({n for n in (h.number for h in hs) if [x.number for x in hs].count(n) > 1})
    if shared:
        raise ValueError(f"WP numbers used by more than one file: {shared}")
    by_key = {(g.token.lower(), g.track): g for g in groups}
    rows: dict[str, Row] = {}
    for h in hs:
        group = by_key.get((h.milestone.lower(), h.track))
        if group is None:
            here = [g.track for g in groups if g.token.lower() == h.milestone.lower() and g.track]
            raise ValueError(
                f"{h.file}: Milestone {h.milestone}"
                + (f", Track {h.track!r}" if h.track else ", no Track line")
                + " names no heading under ROADMAP § Work packages"
                + (f"; its tracks are {here}" if here else "")
            )
        rows[h.number] = Row(
            number=h.number,
            file=h.file,
            title=_sentence_case(h.title).replace("|", "\\|"),
            status=h.glyph if h.date is None else f"{h.glyph} {h.date}",
            priority=h.tier or "—",
            depends=depends_cell(h.depends, numbers, h.number),
            token=group.token,
            track=group.track,
        )
    return rows


_PREAMBLE = f"""\
# Work packages

<!-- Generated by .claude/hooks/wp_index.py. Edit the WP files, then rerun it. -->

Each row is read off one WP file's header: its title and its `Milestone:`,
`Track:`, `Status:`, `Priority:` and `Depends on:` lines. The headings are
[ROADMAP.md § Work packages](../ROADMAP.md#work-packages)'s, where each
section keeps its prose. To change a row, edit the WP file and run
`{COMMAND}`. A test fails while this file is stale. Depends on
names hard dependencies, and *soft* marks a preferred order.
"""

_HEAD = "| WP | Title | Status | Priority | Depends on |\n|---|---|---|---|---|\n"


def _cells(row: Row) -> str:
    return (
        f"| [{row.number}]({row.file}) | {row.title} | {row.status} | "
        f"{row.priority} | {row.depends} |\n"
    )


def render(groups: list[Group], rows: dict[str, Row]) -> str:
    """The index text: two derived lists, then every group that has rows."""
    by_group: dict[tuple[str, Optional[str]], list[Row]] = {}
    for row in rows.values():
        by_group.setdefault((row.token, row.track), []).append(row)
    anchor = {(g.token, g.track): g.anchor for g in groups}

    def where(row: Row) -> str:
        return f"[{row.token}](#{anchor[(row.token, row.track)]})"

    out = [_PREAMBLE]
    flying = sorted((r for r in rows.values() if r.glyph == "🔄"), key=lambda r: r.number)
    out.append("\n## In flight\n\n")
    if flying:
        out.append("| WP | Title | Since | Priority | Section |\n|---|---|---|---|---|\n")
        for r in flying:
            since = r.status.split(" ", 1)[1]
            out.append(
                f"| [{r.number}]({r.file}) | {r.title} | {since} | {r.priority} | {where(r)} |\n"
            )
    else:
        out.append("None.\n")
    rank = {tier: i for i, tier in enumerate(PRIORITIES)}
    queued = sorted(
        (r for r in rows.values() if r.glyph == "⬜" and r.priority in NEXT_TIERS),
        key=lambda r: (rank[r.priority], r.number),
    )
    out.append(
        "\n## Next, by priority\n\n"
        f"Not started and rated {' or '.join(NEXT_TIERS)}. The rest are in the "
        "tables below.\n\n"
    )
    if queued:
        out.append("| WP | Title | Priority | Depends on | Section |\n|---|---|---|---|---|\n")
        for r in queued:
            out.append(
                f"| [{r.number}]({r.file}) | {r.title} | {r.priority} | {r.depends} | {where(r)} |\n"
            )
    else:
        out.append("None.\n")

    sections_with_rows = {row.token for row in rows.values()}
    for g in groups:
        members = sorted(by_group.get((g.token, g.track), []), key=lambda r: r.number)
        if g.track is None:
            if g.token not in sections_with_rows:
                continue
            out.append(f'\n## <a id="{g.anchor}"></a>{g.heading}\n')
        elif not members:
            continue
        else:
            out.append(f'\n### <a id="{g.anchor}"></a>{g.track}\n')
        if members:
            out.append("\n" + _HEAD + "".join(_cells(r) for r in members))
    return "".join(out)


_HEADING_RE = re.compile(r'^(#{2,3}) <a id="[^"]*"></a>(.+)$')
_ROW_RE = re.compile(r"^\| \[(\d{4})\]\(([^)]+)\) \| ")


def parse(text: str) -> tuple[list[Group], dict[str, Row]]:
    """The inverse of `render`: groups in order, and every table row.

    The two derived lists at the top carry no anchor and are skipped; they
    are recomputed from the rows.
    """
    groups: list[Group] = []
    rows: dict[str, Row] = {}
    group: Optional[Group] = None
    section: Optional[Group] = None
    for line in text.splitlines():
        if line.startswith("## ") and not _HEADING_RE.match(line):
            group = None  # a derived list
            continue
        m = _HEADING_RE.match(line)
        if m:
            if m.group(1) == "##":
                token = SECTION_RE.match(m.group(2))
                if not token:
                    raise ValueError(f"index section {line!r} has no milestone token")
                section = group = Group(token.group(1), m.group(2), None)
            else:
                if section is None:
                    raise ValueError(f"index track {line!r} sits above any section")
                group = Group(section.token, section.heading, m.group(2))
            groups.append(group)
            continue
        m = _ROW_RE.match(line)
        if m and group is not None:
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if len(cells) != 5:
                raise ValueError(f"index row for {m.group(1)} has {len(cells)} cells, not 5")
            rows[m.group(1)] = Row(
                m.group(1), m.group(2), cells[1], cells[2], cells[3], cells[4],
                group.token, group.track,
            )
    return groups, rows


class Conflict(Exception):
    pass


def merge(base: str, ours: str, theirs: str) -> str:
    """Three-way merge of three index texts, row by row, keyed by WP number."""
    gb, rb = parse(base)
    go, ro = parse(ours)
    gt, rt = parse(theirs)

    def pick(b, o, t, what: str):
        if o == t or t == b:
            return o
        if o == b:
            return t
        raise Conflict(what)

    groups = pick(gb, go, gt, "the headings")
    rows: dict[str, Row] = {}
    for number in sorted(set(rb) | set(ro) | set(rt)):
        row = pick(rb.get(number), ro.get(number), rt.get(number), f"WP {number}")
        if row is not None:
            rows[number] = row
    known = {(g.token, g.track) for g in groups}
    stray = sorted(n for n, r in rows.items() if (r.token, r.track) not in known)
    if stray:
        raise Conflict(f"rows under headings the merged index lacks: {stray}")
    return render(groups, rows)


def generate(root: Path = ROOT) -> str:
    groups = roadmap_groups((root / ROADMAP).read_text(encoding="utf-8"))
    return render(groups, rows_from_headers(headers(root), groups))


def _merge_driver(base: str, ours: str, theirs: str) -> int:
    """Write the merge into `ours`, git's %A, or leave it untouched and exit 1.

    The configured command is `<this> --merge %O %A %B || git merge-file %A %O
    %B`, so a conflict here, or a branch too old to have this script, gets
    git's own markers from the second half.
    """
    read = [Path(p).read_text(encoding="utf-8") for p in (base, ours, theirs)]
    try:
        merged = merge(*read)
    except (Conflict, ValueError) as exc:
        print(f"wp_index: {exc}; resolve the markers by rerunning {COMMAND}",
              file=sys.stderr)
        return 1
    Path(ours).write_text(merged, encoding="utf-8")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--merge"] and len(args) == 4:
        return _merge_driver(*args[1:])
    text = generate()
    path = ROOT / INDEX
    current = path.read_text(encoding="utf-8") if path.is_file() else None
    if args == ["--check"]:
        if current != text:
            print(f"{INDEX} is stale: run {COMMAND}", file=sys.stderr)
            return 1
        return 0
    if args:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    if current != text:
        path.write_text(text, encoding="utf-8")
        print(f"wrote {INDEX}")
    else:
        print(f"{INDEX} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
