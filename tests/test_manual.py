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
# rglob, not glob: Part 1 lives in docs/manual/using/ (WP-1067).  A doc tree's
# shape should not be set by a test's glob, and the guards below are what a
# future Part 1 page inherits by being collected here.  _build/ is a local
# sphinx output directory, not source — an rglob that walks it collects a stale
# copy of every chapter.
CHAPTERS = sorted(
    p for p in MANUAL_DIR.rglob("*.md") if "_build" not in p.relative_to(MANUAL_DIR).parts
)

# Everything on a built page that is *not* prose: a `$` inside a code block or
# a script is not a rendering failure, and MathJax's own delimiters are `\(…\)`.
MARKUP_WITHOUT_PROSE = re.compile(
    r"<(script|style|pre)\b[^>]*>.*?</\1\s*>|<code\b[^>]*>.*?</code\s*>", re.S | re.I
)

# The landing page is copied into the build verbatim through `html_extra_path`
# (WP-1331), so the output tree holds pages Sphinx never rendered and whose
# markup is nobody's MyST.  They are not this suite's to police, and one of them
# writes a shell prompt as `<span class="ps">$</span>pip install rietx` — prose
# by MARKUP_WITHOUT_PROSE's definition, and a false positive for the TeX guard.
# Derived from the directory conf.py actually copies, so the exclusion is exactly
# what was added and a new manual page stays covered.
_LANDING_SITE = MANUAL_DIR.parent / "landing" / "site"
COPIED_IN = (
    {p.relative_to(_LANDING_SITE).as_posix() for p in _LANDING_SITE.rglob("*.html")}
    if _LANDING_SITE.is_dir() else set()
)

CITE_ROLE = re.compile(r"\{cite\}`([^`]+)`")
SOURCE_LINE = re.compile(r"\*Source:\*\s+`([A-Za-z_][\w.]*)`")
BIB_KEY = re.compile(r"^@\w+\{([^,\s]+)\s*,", re.MULTILINE)


def _cited_keys() -> set[str]:
    keys: set[str] = set()
    for page in CHAPTERS:
        for role in CITE_ROLE.findall(page.read_text(encoding="utf-8")):
            keys.update(k.strip() for k in role.split(","))
    return keys


@pytest.fixture(scope="session")
def built_manual(tmp_path_factory):
    """One `-W` build, shared by every test that reads its output.

    Session-scoped, and its consumers carry the matching `xdist_group` mark:
    without it a second worker rebuilds the whole tree and the sharing costs
    more than it saved (tests/CLAUDE.md).  Returns the output directory and the
    completed process, so the build's own failure is reported by the test named
    for it rather than as a fixture error.
    """
    out = tmp_path_factory.mktemp("manual") / "html"
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-W", "-q", "-E", "-b", "html",
         str(MANUAL_DIR), str(out)],
        capture_output=True, text=True, timeout=300,
    )
    return out, result


@pytest.mark.xdist_group("manual-build")
def test_manual_builds_warning_free(built_manual):
    """sphinx-build -W: warnings (incl. undefined substitutions, missing
    citations, broken eq refs) are errors."""
    _, result = built_manual
    assert result.returncode == 0, f"sphinx-build -W failed:\n{result.stdout}\n{result.stderr}"


@pytest.mark.xdist_group("manual-build")
def test_no_unrendered_math_survives_the_build(built_manual):
    """No `$` reaches the rendered prose.  `-W` cannot see this class of bug:
    the page builds cleanly and prints the TeX.

    Both instances it was written for were live in the shipped HTML.  A
    continuation line beginning `- ` inside inline math is read as a list
    bullet, which dropped the delimiters *and* opened a spurious `<ul>` in
    `forward-model.md`; and five `references.bib` titles carried raw TeX
    (`Al$_2$O$_3$`, `$F_N$`, …) that the bibliography renders verbatim on every
    page that cites them.  Multi-line inline math is otherwise fine — nineteen
    other spans in Part 2 render correctly — so the rule is about the delimiters
    surviving, not about reflowing every equation onto one line.
    """
    out, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    stray: list[str] = []
    for page in sorted(out.rglob("*.html")):
        if page.relative_to(out).as_posix() in COPIED_IN:
            continue        # the landing page — see COPIED_IN
        text = MARKUP_WITHOUT_PROSE.sub("", page.read_text(encoding="utf-8"))
        for match in re.finditer(r".{0,60}\$.{0,60}", text, re.S):
            stray.append(f"{page.name}: …{match.group(0).strip()}…")
    assert not stray, "unrendered TeX in the built prose:\n" + "\n".join(stray[:10])


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


def test_the_background_peak_table_agrees_with_the_refinement_that_produced_it():
    """`using/data.md`'s background-peak evidence table, against the fixture.

    That section's headline is a comparison of measured Rwp values — one
    background peak against three more Chebyshev terms, at equal parameter cost
    — and the refinements behind it are `tests/test_acceptance_si640c.py`'s
    `cheb3`/`cheb3_peak`/`cheb6` fixtures, which assert the same numbers by
    running them.  This is the *other* half of that chain: the prose cannot say
    a different number from the one the slow test pins, which is what would
    otherwise happen when a solver change moves the fit and only the test is
    updated.

    It is here rather than in the acceptance module for a scheduling reason —
    this half is a file read and belongs in the fast selection, and the half
    that needs four fits does not.

    **Both prose copies, not one.**  The same table is transcribed twice — the
    Markdown table in `using/data.md` and the reST table in the
    :class:`~rietx.schemas.instrument.BackgroundPeak` docstring — and the second
    is the one that drifted last time (7dbd27c fixed the manual's claim and left
    the docstring stating the old one).  Both are checked against `MANUAL_RWP`
    here, so neither copy can say a number no refinement produced.
    """
    sys.path.insert(0, str(MANUAL_DIR.parent.parent / "tests"))
    manual_rwp = importlib.import_module("test_acceptance_si640c").MANUAL_RWP
    page = (MANUAL_DIR / "using" / "data.md").read_text(encoding="utf-8")

    # --- the Markdown table in using/data.md, keyed by row label ---
    rows = {
        "cheb3": "| Chebyshev, 3 terms |",
        "cheb3_peak": "| Chebyshev-3 **+ one background peak** |",
        "cheb6": "| Chebyshev, 6 terms |",
        "cheb6_peak": "| Chebyshev-6 + one background peak |",
    }
    for key, prefix in rows.items():
        line = next((ln for ln in page.splitlines() if ln.startswith(prefix)),
                    None)
        assert line is not None, f"the {key} row is gone from data.md"
        cells = [c.strip() for c in line.strip("|").split("|")]
        # | background | terms | Rwp | GoF | Biso | HIGH_CORRELATION |
        assert float(cells[2]) == manual_rwp[key], (
            f"data.md's {key} row says Rwp {cells[2]}, the fixture that "
            f"produced it says {manual_rwp[key]}")

    # --- the reST table in the BackgroundPeak docstring, keyed by the `terms`
    # column (its two peak rows share the label "that **+ one peak**", so the
    # label cannot key them; the term count can) ---
    doc = importlib.import_module(
        "rietx.schemas.instrument").BackgroundPeak.__doc__
    lines = doc.splitlines()
    seps = [i for i, ln in enumerate(lines)
            if ln.strip() and set(ln.strip()) <= {"=", " "}]
    assert len(seps) >= 3, "the BackgroundPeak docstring table lost its rules"
    terms_to_key = {"3": "cheb3", "3 + 3": "cheb3_peak",
                    "6": "cheb6", "6 + 3": "cheb6_peak"}
    seen: set[str] = set()
    for ln in lines[seps[1] + 1:seps[-1]]:  # body rows, between the inner rules
        cols = re.split(r"\s{2,}", ln.strip())
        # background | terms | Rwp | Biso(Si)/Å² | HIGH_CORRELATION
        key = terms_to_key.get(cols[1]) if len(cols) >= 3 else None
        if key is None:
            continue
        assert float(cols[2]) == manual_rwp[key], (
            f"the BackgroundPeak docstring's {key} row says Rwp {cols[2]}, the "
            f"fixture that produced it says {manual_rwp[key]}")
        seen.add(key)
    assert seen == set(terms_to_key.values()), (
        f"the BackgroundPeak docstring table is missing rows: "
        f"{set(terms_to_key.values()) - seen}")
