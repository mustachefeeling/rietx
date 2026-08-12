"""WP-1062 — the old name is gone, and stays gone.

The rename to ``anatase`` touched ~300 files, and the thing that makes it
*finished* rather than merely done is this test: a reintroduction fails CI
instead of depending on a note in someone's mailbox.

Three things about how it is written are deliberate.

**It greps the old token, never the new one.** ``anatase`` is a phase this
software analyses — it appears zero times as vocabulary today, but ``rutile``,
the other TiO₂ polymorph, appears ~168 times in the QPA test data, and
anatase/rutile is the canonical quantitative-phase-analysis pair.  So the day a
tutorial or a test fixture gains an anatase phase, an audit written against the
*new* name starts failing on correct code.  An audit written against ``pxrd``
never does: it is not domain vocabulary, and never was — the prose consistently
writes "powder X-ray diffraction".

**It greps ``pxt`` too.** The project suffix ``.pxrd`` contains ``pxrd`` and the
first token catches it, but the textdoc magic ``pxt`` does not contain it and
nothing else would ever notice a stale one.  Both were format tokens of the old
name, and both were replaced (``.rex``, ``rxt``) rather than rebranded, because
a versioned contract must not move when a brand does.

**The allowlist is paths, with a reason each.** An allowlist of *lines* would
drift against its own files; an allowlist of paths states which files are
allowed to remember, and there are only three kinds.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: The old distribution/import name and the old textdoc magic.  Case-insensitive
#: — ``PXRDREF_STATE_DIR`` and ``__PXRDREF_NO_PLOTLY__`` were both real.
STALE = re.compile(r"pxrd|pxt", re.IGNORECASE)

#: The only files allowed to carry the old name, and why.
ALLOWED = {
    # this file: it *is* the audit, so it necessarily spells what it forbids.
    # Not discoverable by reading — the first run passed because the file was
    # still untracked and `git grep` cannot see an untracked file.
    "tests/test_no_stale_name.py",
    # documents the rename, so it names both sides throughout and cannot be
    # swept without destroying its own subject
    "docs/wp/1062-rename-to-anatase.md",
    # vendored third-party tables whose provenance header records the
    # modification under the name it was made with.  Parsed byte-sensitively by
    # crystallography/{attenuation,dispersion}.py; historical, not current.
    "src/anatase/data/mu_McMaster.dat",
    "src/anatase/data/f1f2_CromerLiberman.dat",
    # the milestone record's one line recording that the rename happened
    "docs/milestones/v1.0.md",
}


def _tracked_hits() -> dict[str, list[str]]:
    """Every tracked line matching the stale tokens, by path."""
    out = subprocess.run(
        ["git", "grep", "-nIiE", STALE.pattern],
        cwd=ROOT, capture_output=True, text=True, check=False).stdout
    hits: dict[str, list[str]] = {}
    for line in out.splitlines():
        path, _, rest = line.partition(":")
        hits.setdefault(path, []).append(rest)
    return hits


def test_no_file_outside_the_allowlist_carries_the_old_name():
    """The audit the rename is measured by.

    A failure here is nearly always one of two things: a literal that should
    have been an ``_about.py`` import, or a doc written from memory.
    """
    offenders = {p: v for p, v in _tracked_hits().items() if p not in ALLOWED}
    assert not offenders, (
        "the old name is back in " + ", ".join(sorted(offenders)) + " — import "
        "the token from anatase._about instead of spelling it")


def test_no_tracked_path_carries_the_old_name():
    """Contents are half of it; a file *named* for the old package is the other.

    ``src/pxrdref/`` and ``gui/src/lib/pxt.ts`` were both real, and a path is
    invisible to a content grep.
    """
    out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                         capture_output=True, text=True, check=False).stdout
    named = [p for p in out.splitlines() if STALE.search(p)]
    assert not named, f"tracked paths still spell the old name: {named}"


def test_every_allowlisted_file_still_exists_and_still_needs_it():
    """An allowlist that outlives its reason is an allowlist that hides a bug.

    Both halves matter: a path that no longer exists is a stale entry, and a
    path that no longer matches is one whose exemption has been earned away —
    either way the entry should go, and nothing else would ever say so.
    """
    hits = _tracked_hits()
    for path in sorted(ALLOWED):
        assert (ROOT / path).exists(), f"allowlisted file is gone: {path}"
        assert path in hits, (
            f"{path} no longer carries the old name — drop it from ALLOWED")
