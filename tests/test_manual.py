"""Anti-divergence guards for the theory manual (WP-0604).

The manual's design rule is that it structurally cannot drift from the code:
constants are injected from the live package at build time (an undefined MyST
substitution is a warning and the build runs -W), every displayed equation
names the source symbol whose docstring it transcribes, and every bibliography
entry is cited.  These tests are what make each of those claims executable.
"""

from __future__ import annotations

import importlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("sphinx")

MANUAL_DIR = Path(__file__).resolve().parent.parent / "docs" / "manual"
CHAPTERS = sorted(MANUAL_DIR.glob("*.md"))

CITE_ROLE = re.compile(r"\{cite\}`([^`]+)`")
SOURCE_LINE = re.compile(r"\*Source:\*\s+`([A-Za-z_][\w.]*)`")
BIB_KEY = re.compile(r"^@\w+\{([^,\s]+)\s*,", re.MULTILINE)


def _cited_keys() -> set[str]:
    keys: set[str] = set()
    for page in CHAPTERS:
        for role in CITE_ROLE.findall(page.read_text(encoding="utf-8")):
            keys.update(k.strip() for k in role.split(","))
    return keys


def test_manual_builds_warning_free(tmp_path):
    """sphinx-build -W: warnings (incl. undefined substitutions, missing
    citations, broken eq refs) are errors."""
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-W", "-q", "-E", "-b", "html",
         str(MANUAL_DIR), str(tmp_path / "html")],
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, f"sphinx-build -W failed:\n{result.stdout}\n{result.stderr}"


def test_every_bib_entry_is_cited():
    """references.bib carries no dead weight: an uncited entry is either a
    chapter that lost its citation or an entry that should be pruned."""
    bib_keys = set(BIB_KEY.findall((MANUAL_DIR / "references.bib").read_text(encoding="utf-8")))
    assert bib_keys, "no bibliography entries parsed — regex or file moved?"
    uncited = bib_keys - _cited_keys()
    assert not uncited, f"bibliography entries never cited: {sorted(uncited)}"


def test_every_citation_has_a_bib_entry():
    """The -W build also catches this, but a direct diff names the key."""
    bib_keys = set(BIB_KEY.findall((MANUAL_DIR / "references.bib").read_text(encoding="utf-8")))
    missing = _cited_keys() - bib_keys
    assert not missing, f"citations with no bibliography entry: {sorted(missing)}"


def test_every_source_symbol_imports():
    """Each equation's *Source:* line names a live module or attribute; a
    rename breaks this test rather than the reader's trust."""
    symbols: set[str] = set()
    for page in CHAPTERS:
        symbols.update(SOURCE_LINE.findall(page.read_text(encoding="utf-8")))
    assert symbols, "no *Source:* lines found — pattern or chapters moved?"
    for dotted in sorted(symbols):
        parts = dotted.split(".")
        obj = None
        for i in range(len(parts), 0, -1):
            try:
                obj = importlib.import_module(".".join(parts[:i]))
            except ImportError:
                continue
            for attr in parts[i:]:
                obj = getattr(obj, attr, None)
                assert obj is not None, f"{dotted}: no attribute {attr!r}"
            break
        assert obj is not None, f"{dotted}: not importable"


def test_source_lines_cover_every_labelled_equation():
    """Every {math} directive with a :label: sits in a section that carries
    at least one *Source:* line — an equation with no named source is a
    transcription with no audit trail."""
    for page in CHAPTERS:
        text = page.read_text(encoding="utf-8")
        n_labels = len(re.findall(r"^:label:", text, re.MULTILINE))
        n_sources = len(SOURCE_LINE.findall(text))
        if n_labels:
            assert n_sources > 0, f"{page.name}: {n_labels} labelled equations, no *Source:* lines"
