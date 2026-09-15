#!/usr/bin/env python3
"""Which WP each worktree is working, so two sessions never pick the same one.

Read-only by default, stdlib-only, and independent of the project venv, for the
same reason ``session_start.py`` is: the state it reports must survive a broken
or wrong-tree venv.

**A claim is held by a worktree, and a worktree is live when a session sits in
it.**  That is the whole model, and it is chosen because every part of it is
observable.  A worktree is in ``git worktree list``; a session is a ``claude``
process with a cwd (``session_start.live_sessions``); the WP is in the tree's
name by the repo's own convention (``/wp-start`` step 3 names a tree
``wp1422-<slug>`` and ``worktree_create.py`` cuts the branch to match).  So the
answer to "is anyone on WP-1422?" needs no ledger at all in the ordinary case,
and a ledger that can be forgotten is worse than one that is never needed.

What the ledger adds is the two cases the convention cannot carry, and nothing
else:

* **A tree whose name says the wrong WP.**  Measured on this repo 2026-09-15:
  a live session sat in ``.claude/worktrees/wp1404-what-recording-every-fit-costs``
  on branch ``wp1413-snapshot-cost``, working WP-1413.  The branch happened to
  say so; had the session reused the branch too, the derivation would have
  named 1404 and the real claim would have been invisible.
* **An override.**  ``worktree_create.py`` refuses a WP another live session
  holds, and a refusal with no way past it is a trap: a session parked idle in
  a tree it has finished with would block the next one for ever.  ``release``
  is that way past, and it is one line printed in the refusal itself.

So the declaration only ever *sharpens* the derivation.  Skipping it degrades
to the branch name rather than to nothing, which is why no step of ``/wp-start``
is load-bearing for this to work.

**Where the files live.**  ``<git-common-dir>/wp-claims/``.  Git guarantees the
common dir is shared by every worktree of a repository (measured: the main
checkout, a worktree, and a worktree nested inside a worktree all resolve
``git rev-parse --git-common-dir`` to the same path), it is untracked, no
``git status`` sees it, and a fresh clone starts empty.  A tracked file could
not work: a claim has to be visible across branches that never merge.

**Staleness cannot accumulate.**  A claim whose worktree is gone is deleted on
the next read, so the ledger can never outlive the trees it describes and there
is no expiry policy to tune.  ``worktree_remove.py`` needs no cooperation, and
a claim survives exactly as long as the work does.  This matters more than it
looks: ``session_start.py``'s docstring records that a false alarm costs more
than no alarm, because it teaches the reader to skip the one line that is ever
load-bearing.

**Two states, not three.**  A claim with a live session in its tree is *held*;
one without is *dormant*.  Dormant is not a problem and is not reported at
session start — it is the ordinary state of a tree whose session has ended with
the work unfinished, and it is what ``/wp-start`` reads to find that work again.
Only *held* bears on a clash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Iterable, NamedTuple, Optional

CLAIM_DIR = "wp-claims"
# ``wp1422-slug``, ``1331-landing-page``: the repo writes both, and the four
# digits are the WP either way.  A name with no four-digit head claims nothing,
# which is how ``pr-bench`` and ``termplot`` stay out of this entirely.
_WP_NAME_RE = re.compile(r"^wp[-_]?(\d{4})(?:[-_.]|$)|^(\d{4})(?:[-_.]|$)", re.I)


class Claim(NamedTuple):
    wp: str  # four-digit WP number
    worktree: Path
    declared: str  # YYYY-MM-DD the claim was written
    by: str  # "worktree" (the create hook) or "session" (the claim verb)


class Holder(NamedTuple):
    """A worktree that is working a WP, and the live sessions inside it."""

    wp: str
    worktree: Path
    branch: Optional[str]  # None when the tree is on a detached HEAD
    source: str  # "claim", "branch" or "tree" — where the WP number came from
    sessions: tuple  # session_start.Session, live and in this tree

    @property
    def held(self) -> bool:
        return bool(self.sessions)


def wp_from_name(name: str) -> Optional[str]:
    """The four-digit WP a worktree or branch name declares, if it declares one."""
    m = _WP_NAME_RE.match(name.strip())
    if not m:
        return None
    return m.group(1) or m.group(2)


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.rstrip("\n") if proc.returncode == 0 else None


def claims_dir(root: Path) -> Optional[Path]:
    """``<git-common-dir>/wp-claims`` — the one directory every worktree shares."""
    common = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        return None
    return Path(common) / CLAIM_DIR


def _claim_file(root: Path, worktree: Path) -> Optional[Path]:
    """One file per worktree, named for the tree it belongs to.

    Keyed by the *tree* rather than by the WP, for two reasons.  Pruning is then
    a question with an observable answer ("does this path exist?"), and two
    trees claiming one WP is the clash itself, which a WP-keyed store would
    overwrite into silence rather than report.

    The path's hash keeps the name unique — worktrees nest here, so
    ``wp1402-x/.claude/worktrees/wp1403-y`` and a sibling ``wp1403-y`` share a
    basename — and the basename is kept in front so the directory can be read.
    """
    d = claims_dir(root)
    if d is None:
        return None
    digest = hashlib.sha1(str(worktree.resolve()).encode()).hexdigest()[:12]
    return d / f"{worktree.name}-{digest}.json"


def read_claims(root: Path, prune: bool = True) -> dict[Path, Claim]:
    """Every claim whose worktree still exists, keyed by resolved tree path.

    Pruning on read is what keeps the ledger from ever describing a tree that
    is gone.  It is deliberately not conditional on a hook having run: the
    remove hook, a bare ``git worktree remove``, and a directory someone
    deleted by hand all end the same way.
    """
    d = claims_dir(root)
    if d is None or not d.is_dir():
        return {}
    claims: dict[Path, Claim] = {}
    for path in sorted(d.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            tree = Path(raw["worktree"]).resolve()
            wp = str(raw["wp"])
        except (OSError, ValueError, KeyError, TypeError):
            if prune:
                path.unlink(missing_ok=True)  # unreadable is indistinguishable from absent
            continue
        if not tree.is_dir():
            if prune:
                path.unlink(missing_ok=True)
            continue
        claims[tree] = Claim(wp, tree, str(raw.get("declared", "")), str(raw.get("by", "")))
    return claims


def write_claim(root: Path, worktree: Path, wp: str, by: str = "session") -> Optional[Path]:
    """Declare that *worktree* is working *wp*, overriding what its name says."""
    path = _claim_file(root, worktree)
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "wp": wp,
        "worktree": str(worktree.resolve()),
        "declared": date.today().isoformat(),
        "by": by,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)  # atomic: two sessions may write at once
    return path


def release_claim(root: Path, worktree: Path) -> bool:
    """Drop *worktree*'s claim.  True when there was one to drop."""
    path = _claim_file(root, worktree)
    if path is None or not path.exists():
        return False
    path.unlink()
    return True


def worktree_branches(root: Path) -> dict[Path, Optional[str]]:
    """Every worktree of this repository, with the branch it has checked out.

    One ``git worktree list --porcelain`` call rather than a ``rev-parse`` per
    tree: this runs before every session.
    """
    out = _git(root, "worktree", "list", "--porcelain") or ""
    trees: dict[Path, Optional[str]] = {}
    current: Optional[Path] = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            current = Path(line[9:]).resolve()
            trees[current] = None
        elif line.startswith("branch ") and current is not None:
            trees[current] = line[7:].rsplit("/", 1)[-1]
    return trees or {root.resolve(): None}


def _sessions_in(tree: Path, trees: Iterable[Path], sessions, exclude: set) -> tuple:
    """The live sessions whose cwd belongs to *tree* rather than to a deeper one.

    The same containment rule ``session_start.sessions_sharing`` applies, and
    for the same reason: worktrees nest under one another here, so a cwd goes
    to the deepest registered tree that contains it.
    """
    resolved = list(trees)
    hits = []
    for s in sessions:
        if s.pid in exclude:
            continue
        try:
            cwd = Path(s.cwd).resolve()
        except OSError:
            continue
        owners = [r for r in resolved if cwd == r or r in cwd.parents]
        if owners and max(owners, key=lambda r: len(r.parts)) == tree:
            hits.append(s)
    return tuple(hits)


def occupancy(
    trees: dict[Path, Optional[str]],
    sessions,
    exclude: set,
    claims: Optional[dict[Path, Claim]] = None,
    main: Optional[Path] = None,
) -> list[Holder]:
    """Which WP each worktree is working, and who is live in it.

    Pure: the git call, the process scan and the claim read all happen in the
    caller, so this is driven straight from fixtures.

    The WP comes from the first source that names one — the tree's declared
    claim, then its branch, then its own directory name.  Branch before tree
    name because a branch is what the session is committing to, and the tree it
    sits in may be one it resumed: measured 2026-09-15, a session in
    ``wp1404-what-recording-every-fit-costs`` on branch ``wp1413-snapshot-cost``
    was working 1413.

    The main checkout is excluded whatever it is called.  It is read-only for a
    session (``worktree_only.py``), so it claims nothing, and on this repo it
    is called ``rietx`` and would name no WP anyway.
    """
    claims = claims or {}
    holders = []
    for tree, branch in trees.items():
        if main is not None and tree == main.resolve():
            continue
        claim = claims.get(tree)
        if claim is not None:
            wp, source = claim.wp, "claim"
        elif branch and wp_from_name(branch):
            wp, source = wp_from_name(branch), "branch"
        elif wp_from_name(tree.name):
            wp, source = wp_from_name(tree.name), "tree"
        else:
            continue
        holders.append(
            Holder(wp, tree, branch, source, _sessions_in(tree, trees, sessions, exclude))
        )
    return sorted(holders, key=lambda h: (h.wp, str(h.worktree)))


def held_elsewhere(holders: list[Holder], mine: Optional[Path]) -> list[Holder]:
    """The WPs a live session is working, in some tree other than *mine*."""
    mine = mine.resolve() if mine is not None else None
    return [h for h in holders if h.held and h.worktree != mine]


def clashes(holders: list[Holder]) -> list[str]:
    """Every WP that more than one live tree is working.  The thing itself."""
    seen: dict[str, int] = {}
    for h in holders:
        if h.held:
            seen[h.wp] = seen.get(h.wp, 0) + 1
    return sorted(wp for wp, n in seen.items() if n > 1)


CLOSED_GLYPHS = ("✅", "🛑")


def bears_on_a_clash(holders: list[Holder], glyphs: dict[str, Optional[str]]) -> list[Holder]:
    """The rows worth printing: everything held, plus dormant work still open.

    A **closed** WP whose tree was kept is dropped.  It is the commonest row by
    far on this repo — four of six trees on 2026-09-15 were finished work whose
    directory had simply not been removed — and it says nothing about who is
    working what.  Printing it would put the one line that matters fifth.
    """
    return [
        h for h in holders if h.held or glyphs.get(h.wp) not in CLOSED_GLYPHS
    ]


def where(holder: Holder, main: Optional[Path]) -> str:
    """The tree's path, relative to the main checkout when it is under it."""
    if main is not None:
        try:
            return str(holder.worktree.relative_to(main.resolve()))
        except ValueError:
            pass
    return str(holder.worktree)


def describe(holder: Holder, main: Optional[Path]) -> str:
    """One line naming who holds a WP, where, and for how long."""
    who = ", ".join(f"pid {s.pid} up {s.age}" for s in holder.sessions) or "no session"
    branch = f", branch {holder.branch}" if holder.branch else ""
    return (
        f"WP-{holder.wp} held by {who} in {where(holder, main)}{branch} "
        f"(from the {holder.source})"
    )


# --------------------------------------------------------------------------
# CLI — ``/wp-start`` step 2 reads ``status``; the other two verbs are the
# override the refusal in ``worktree_create.py`` names.


def sibling(name: str):
    """A sibling hook module, imported by path so this works however it is run."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import importlib

    return importlib.import_module(name)


def main_checkout(trees: dict[Path, Optional[str]]) -> Optional[Path]:
    """The shallowest registered tree.  Worktrees live *under* it here."""
    return min(trees, key=lambda p: len(p.parts)) if trees else None


def glyphs_for(root: Path, holders: list[Holder]) -> dict[str, Optional[str]]:
    """Each held WP's Status glyph, read from *this* tree's ``docs/wp/``.

    This tree and not the claiming one: a tree on an old branch may not have
    the WP file at all, and the question being asked is whether the WP is still
    open on the trunk this session will branch from.
    """
    state = sibling("session_start")
    return {h.wp: state.wp_file_state(root, h.wp)[1] for h in holders}


def _status(root: Path, here: Path) -> int:
    trees = worktree_branches(root)
    main = main_checkout(trees)
    # No exclusion: ``status`` is asked *for* the full picture, and this
    # session's own row is the one marked, never the one hidden.
    holders = occupancy(trees, sibling("session_start").live_sessions(), set(),
                        read_claims(root), main)
    rows = bears_on_a_clash(holders, glyphs_for(root, holders))
    if not rows:
        print("no worktree is working an open WP")
        return 0
    here = here.resolve()
    for h in rows:
        mark = "→" if h.worktree == here else " "
        who = ", ".join(f"pid {s.pid} up {s.age}" for s in h.sessions)
        state = f"held by {who}" if h.held else "dormant"
        branch = h.branch or "detached"
        print(f"{mark} WP-{h.wp}  {state}  in {where(h, main)} ({branch}, from the {h.source})")
    for wp in clashes(holders):
        print(f"⚠ WP-{wp} is live in more than one tree — that is the clash")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("verb", choices=("status", "claim", "release"))
    ap.add_argument("wp", nargs="?", help="four-digit WP number, for `claim`")
    ap.add_argument(
        "--worktree", type=Path, default=None, help="the tree to act on (default: this one)"
    )
    args = ap.parse_args(argv)

    root = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if root is None:
        print("wp_claim: not inside a git repository", file=sys.stderr)
        return 1
    here = (args.worktree or Path(root)).resolve()

    if args.verb == "status":
        return _status(Path(root), here)
    if args.verb == "claim":
        if not (args.wp and args.wp.isdigit() and len(args.wp) == 4):
            print("wp_claim: claim needs a four-digit WP number", file=sys.stderr)
            return 1
        path = write_claim(Path(root), here, args.wp, by="session")
        print(f"WP-{args.wp} claimed for {here}" + ("" if path else " (no claim store)"))
        return 0
    dropped = release_claim(Path(root), here)
    print(f"{'released' if dropped else 'no claim to release for'} {here}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
