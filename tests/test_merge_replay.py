"""The merge replay WP-1507 closes on (``tests/merge_replay.py``).

Driven against a tmp git repository, because what it counts is what git does.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.merge_replay import header_changes, replay


def _git(root: Path, *args: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_DATE": "2026-10-01T12:00:00",
           "GIT_COMMITTER_DATE": "2026-10-01T12:00:00"}
    subprocess.run(
        ["git", "-c", "user.email=r@t", "-c", "user.name=r", "-c", "commit.gpgsign=false",
         *args], cwd=root, env=env, check=True, capture_output=True,
    )


def _write(root: Path, path: str, text: str) -> None:
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _write(root, ".gitattributes", "docs/wp/README.md merge=wpindex\n")
    _write(root, "docs/wp/README.md", "a\nb\n")
    _write(root, "docs/ROADMAP.md", "prose\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


def test_a_conflict_the_driver_resolves_counts_only_as_text(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _git(root, "checkout", "-qb", "side")
    _write(root, "docs/wp/README.md", "a\nb\nside\n")
    _git(root, "commit", "-qam", "side")
    _git(root, "checkout", "-q", "main")
    _write(root, "docs/wp/README.md", "a\nb\nmain\n")
    _git(root, "commit", "-qam", "main")
    _git(root, "merge", "-q", "-X", "ours", "side", "-m", "merge")
    got = replay(root, "2000-01-01", driver="cp %B %A")
    assert got["merges"][0] == 1
    assert got["text"] == (1, {"docs/wp/README.md": 1})
    assert got["driver"][0] == 0


def test_edits_apart_on_both_sides_merge_clean_as_text(tmp_path: Path) -> None:
    """The text merge must run: a driver git cannot start also reports a conflict."""
    root = _repo(tmp_path)
    _write(root, "docs/wp/README.md", "a\nb\nc\nd\ne\nf\n")
    _git(root, "commit", "-qam", "longer")
    _git(root, "checkout", "-qb", "side")
    _write(root, "docs/wp/README.md", "A\nb\nc\nd\ne\nf\n")
    _git(root, "commit", "-qam", "side")
    _git(root, "checkout", "-q", "main")
    _write(root, "docs/wp/README.md", "a\nb\nc\nd\ne\nF\n")
    _git(root, "commit", "-qam", "main")
    _git(root, "merge", "-q", "side", "-m", "merge")
    got = replay(root, "2000-01-01", driver="cp %B %A")
    assert got["merges"][0] == 1
    assert got["text"][0] == 0


def test_a_header_change_that_also_edits_roadmap_is_flagged(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write(root, "docs/wp/README.md", "a\nb\nfiled\n")
    _git(root, "commit", "-qam", "file a WP")
    _write(root, "docs/wp/README.md", "a\nb\nfiled\nclosed\n")
    _write(root, "docs/ROADMAP.md", "prose\na row by habit\n")
    _git(root, "commit", "-qam", "close a WP")
    _write(root, "docs/ROADMAP.md", "prose\nmore prose\n")
    _git(root, "commit", "-qam", "prose only")
    got = header_changes(root, "2000-01-01", ref="main")
    assert [(subject, touched) for _sha, subject, touched in got] == [
        ("base", ["docs/ROADMAP.md"]),
        ("file a WP", []),
        ("close a WP", ["docs/ROADMAP.md"]),
    ]
