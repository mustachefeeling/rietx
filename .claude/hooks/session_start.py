#!/usr/bin/env python3
"""SessionStart scan: surface stale session-workflow state at the next session.

Read-only, stdlib-only, and deliberately independent of the project venv —
a missing or wrong-tree venv is one of the conditions it must survive to
report.  Run with ``python3`` from PATH; it imports nothing from the package,
touches no network, and always exits 0: the report is a *prompt to the
session, never a gate* (WP-1061).

What it prints: one line of repo state (worktree root, branch, ahead/behind
the local ``main``, uncommitted-change count, venv resolution), then one line
per flag — a missed ``/wp-handover`` (two severities, see below), a venv
whose editable ``pxrdref`` pointer resolves to a different tree, any WP whose
Status glyph is in flight.  Healthy output is one or two lines.

Known limitation, by design: handover entries are day-dated
(``- **YYYY-MM-DD**`` bullets, per docs/wp/TEMPLATE.md), so a commit followed
by a missed handover *on the same day* is invisible — the newest entry's date
already covers the commit's date.  The flag is therefore a prompt, never
proof of health, and its absence is not evidence the log is current.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, Optional

VENV_FIX = 'uv venv --python 3.12 && uv pip install -e ".[dev]"'
REPAIR_HINT = "repair first (/wp-handover, repair mode)"

_WP_COMMIT_RE = re.compile(r"^WP-(\d{4}):")
_STATUS_RE = re.compile(r"Status:\s*(⬜|🔄|✅|🛑)")
_ENTRY_DATE_RE = re.compile(r"^- \*\*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_REPAIR_GLYPHS = ("🔄", "⬜")


class Finding(NamedTuple):
    wp: str  # four-digit WP number
    glyph: Optional[str]  # Status glyph, None if the file or line is missing
    commit_date: str  # newest WP-NNNN: commit date (YYYY-MM-DD)
    entry_date: Optional[str]  # newest handover-log entry date, None if none
    severity: str  # "repair" (open WP) or "note" (closed WP / missing file)


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.rstrip("\n") if proc.returncode == 0 else None


def repo_line(root: Path) -> str:
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD") or "?"
    if branch == "main":
        position = "on main"
    else:
        ahead = _git(root, "rev-list", "--count", "main..HEAD")
        behind = _git(root, "rev-list", "--count", "HEAD..main")
        if ahead is None or behind is None:
            position = "no local main ref"
        else:
            position = f"ahead {ahead} / behind {behind} vs main"
    status = _git(root, "status", "--porcelain")
    n_dirty = len(status.splitlines()) if status else 0
    dirty = "clean" if n_dirty == 0 else f"{n_dirty} uncommitted"
    return f"{root} @ {branch} · {position} · {dirty}"


def venv_flag(root: Path) -> Optional[str]:
    """Check that .venv's editable pxrdref pointer resolves to *this* tree.

    Without importing anything: uv writes ``_editable_impl_pxrd_refine.pth``
    containing the bare src path; setuptools writes ``__editable__*.pth`` plus
    a ``__editable__*finder.py`` holding quoted paths.  Either way the target
    must live under this worktree's root, or the venv measures another tree.
    """
    venv = root / ".venv"
    if not venv.is_dir():
        return f"no .venv in this tree — fix: {VENV_FIX}"
    targets: list[str] = []
    for sp in venv.glob("lib/python*/site-packages"):
        for pth in sp.glob("*.pth"):
            if "pxrd" not in pth.name:
                continue
            for line in pth.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("import"):
                    targets.append(line)
        for finder in sp.glob("__editable__*pxrd*.py"):
            text = finder.read_text(encoding="utf-8", errors="replace")
            targets.extend(m.group(1) for m in re.finditer(r"['\"](/[^'\"]+)['\"]", text))
    if not targets:
        return f"no editable pxrdref pointer in .venv — fix: {VENV_FIX}"
    resolved_root = root.resolve()
    for target in targets:
        try:
            if Path(target).resolve().is_relative_to(resolved_root):
                return None
        except OSError:
            continue
    return f"venv resolves pxrdref to {targets[0]}, not this tree — fix: {VENV_FIX}"


def wp_commits(root: Path, limit: int = 50) -> dict[str, str]:
    """Newest ``WP-NNNN:``-prefixed commit date per WP, from the last commits."""
    out = _git(root, "log", f"-{limit}", "--format=%as\t%s")
    newest: dict[str, str] = {}
    for line in (out or "").splitlines():
        date, _, subject = line.partition("\t")
        m = _WP_COMMIT_RE.match(subject)
        if m and date > newest.get(m.group(1), ""):
            newest[m.group(1)] = date
    return newest


def wp_file_state(root: Path, wp: str) -> tuple[Optional[Path], Optional[str], Optional[str]]:
    """(path, Status glyph, newest handover-entry date) for docs/wp/NNNN-*.md."""
    matches = sorted((root / "docs" / "wp").glob(f"{wp}-*.md"))
    if not matches:
        return None, None, None
    text = matches[0].read_text(encoding="utf-8", errors="replace")
    m = _STATUS_RE.search(text)
    glyph = m.group(1) if m else None
    _, sep, log = text.partition("## Handover log")
    dates = _ENTRY_DATE_RE.findall(log) if sep else []
    return matches[0], glyph, max(dates) if dates else None


def handover_findings(root: Path, limit: int = 50) -> list[Finding]:
    findings = []
    for wp, commit_date in sorted(wp_commits(root, limit).items()):
        path, glyph, entry_date = wp_file_state(root, wp)
        if path is not None and entry_date is not None and entry_date >= commit_date:
            continue  # covered — or the same-day blind spot; see module docstring
        if path is None:
            severity = "note"  # nothing to reconstruct into; likely renumbered
        else:
            severity = "repair" if glyph in _REPAIR_GLYPHS else "note"
        findings.append(Finding(wp, glyph, commit_date, entry_date, severity))
    return findings


def in_flight_wps(root: Path) -> list[str]:
    flying = []
    for path in sorted((root / "docs" / "wp").glob("[0-9]*.md")):
        m = _STATUS_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        if m and m.group(1) == "🔄":
            flying.append(path.name[:4])
    return flying


def render(root: Path) -> str:
    lines = [repo_line(root)]
    vflag = venv_flag(root)
    if vflag is None:
        lines[0] += " · venv ok"
    else:
        lines.append(f"⚠ {vflag}")
    for f in handover_findings(root):
        entry = f"last handover entry {f.entry_date}" if f.entry_date else "no handover entry"
        if f.glyph is None:
            lines.append(f"note: WP-{f.wp} commits to {f.commit_date} but no docs/wp/{f.wp}-*.md")
        elif f.severity == "repair":
            lines.append(
                f"⚠ WP-{f.wp} ({f.glyph}): commits to {f.commit_date}, {entry} — {REPAIR_HINT}"
            )
        else:
            lines.append(
                f"note: WP-{f.wp} ({f.glyph}) post-close commits not in the log "
                f"(commits to {f.commit_date}, {entry})"
            )
    flying = in_flight_wps(root)
    if flying:
        lines.append("in flight: " + ", ".join(f"WP-{wp}" for wp in flying))
    return "\n".join(lines)


def main() -> int:
    root = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if root is None:
        print("session-start scan: not inside a git repository")
        return 0
    try:
        print(render(Path(root)))
    except Exception as exc:  # a broken scan must inform, never block the session
        print(f"session-start scan failed ({exc.__class__.__name__}: {exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
