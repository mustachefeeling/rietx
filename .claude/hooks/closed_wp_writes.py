#!/usr/bin/env python3
"""Lines this branch adds to WPs that were already closed (WP-1989).

No session reads a ✅/🛑 WP file again. Protocol step 1 sends a session to the
one WP it is working, and `/wp-start` never offers a closed one. So a note
written into a closed WP is a note no one will read. `/wp-handover` step 5 and
`docs/wp/TEMPLATE.md` both say so in prose, and the prose did not hold:

* WP-0406 put its joint-fit restraint deferral into WP-0308's
  `### Inherited` three days after 0308 closed. The code's refusal pointed
  readers at that closed file for 81 days, until WP-1988 took it.
* WP-1907's handover wrote "WP-1903's Inherited has both" about two tool
  defects after 1903 was marked ✅. It was read only because 1903 happened to
  be worked again the next day.

`test_docs_consistency.py` catches neither. It asks only whether a WP closed
after 2026-07-31 still carries an `### Inherited` heading. The first write
went to an older WP, and the second was prose in a handover log. Only a diff
sees either, so this compares the branch with the merge-base:

    python3 .claude/hooks/closed_wp_writes.py            # vs origin/main
    python3 .claude/hooks/closed_wp_writes.py --base REF

A WP file is reported when its Status at the base is ✅ or 🛑, it is still
closed in the working tree, and the branch adds lines to it net of the lines
it removes. A rename sweep that rewrites a line in place adds nothing, and
reopening a WP (its Status back to ⬜/🔄) is how a closed WP gets read again,
so neither is reported. Uncommitted edits count, because the check runs
before the last commit as well as after it.

A report is a question, not a refusal: correcting a closed WP's own record is
legitimate (WP-1041 superseding 1026's scoreboard). Exit 1 when anything is
reported, so a handover cannot pass it unread. Stdlib only, like every hook
here.
"""

from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_HOOKS = str(Path(__file__).resolve().parent)  # appended, never inserted: a
if _HOOKS not in sys.path:  # loose script here must not shadow a stdlib module
    sys.path.append(_HOOKS)
import wp_index  # noqa: E402  (sibling hook, not a package)

ROOT = wp_index.ROOT


@dataclass(frozen=True)
class Write:
    """One closed WP and the lines this branch adds to it."""

    file: str
    glyph: str
    lines: tuple[str, ...]


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def glyph_of(text: str) -> Optional[str]:
    """The Status glyph in a WP file's header, or None if it has none."""
    status = wp_index.STATUS_RE.search(text.split("\n## ", 1)[0])
    return status.group("glyph") if status else None


def net_added(old: str, new: str) -> list[str]:
    """Non-blank lines `new` adds to `old`, net of the lines each hunk removes.

    A hunk that rewrites k lines into k (a rename) adds none; one that rewrites
    k into k + n adds its last n. Which n lines is a guess, and only the report
    reads it.
    """
    a, b = old.splitlines(), new.splitlines()
    out: list[str] = []
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            extra = (j2 - j1) - (i2 - i1)
            if extra > 0:
                out += [line for line in b[j2 - extra:j2] if line.strip()]
    return out


def scan(root: Path, base: str) -> list[Write]:
    """Every WP file closed at `base` that the working tree adds lines to."""
    names = _git(root, "diff", "--name-only", base, "--", str(wp_index.WP_DIR))
    if names is None:
        raise SystemExit(f"closed_wp_writes: git diff against {base!r} failed")
    found = []
    for name in names.split():
        path = Path(name)
        if path.parent != wp_index.WP_DIR or not path.name[:4].isdigit():
            continue
        old = _git(root, "show", f"{base}:{name}")
        if old is None or not (root / path).exists():
            continue  # new, or deleted, on this branch
        was = glyph_of(old)
        new = (root / path).read_text(encoding="utf-8")
        now = glyph_of(new)
        if was not in wp_index.CLOSED or now not in wp_index.CLOSED:
            continue
        lines = net_added(old, new)
        if lines:
            found.append(Write(path.name, was, tuple(lines)))
    return found


def base_ref(root: Path) -> str:
    """The merge-base with ``origin/main``, or with ``main`` without a remote."""
    for ref in ("origin/main", "main"):
        mb = _git(root, "merge-base", "HEAD", ref)
        if mb:
            return mb.strip()
    raise SystemExit("closed_wp_writes: no origin/main or main to compare with")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--base", help="ref to compare with (default: the "
                                       "merge-base with origin/main)")
    args = parser.parse_args(argv)
    base = args.base or base_ref(ROOT)
    found = scan(ROOT, base)
    if not found:
        print("closed_wp_writes: this branch adds nothing to a closed WP")
        return 0
    print(f"closed_wp_writes: this branch adds lines to {len(found)} closed "
          "WP(s), which no session reads again:")
    for w in found:
        print(f"  {w.file} [{w.glyph}] +{len(w.lines)}: {w.lines[0].strip()[:100]}")
    print("A note that asks for work goes to the open WP that owns it, or to a "
          "new one (fold first: docs/wp/TEMPLATE.md's header). A correction to "
          "the closed WP's own record may stay: say so in the handover entry.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
