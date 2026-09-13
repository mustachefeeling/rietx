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
# what was added and a new manual page stays covered.  Read when the guard runs,
# never at import: `tests/test_landing.py` *creates* `docs/landing/site` during
# the session, so a set frozen at collection time is empty on the checkout that
# had none — and the landing page's `$` is then scanned as the manual's prose.
_LANDING_SITE = MANUAL_DIR.parent / "landing" / "site"


def _copied_in() -> set[str]:
    if not _LANDING_SITE.is_dir():
        return set()
    return {p.relative_to(_LANDING_SITE).as_posix() for p in _LANDING_SITE.rglob("*.html")}

CITE_ROLE = re.compile(r"\{cite\}`([^`]+)`")
#: Each displayed equation's source line, as `{source}` spells it (WP-1408).
#: The role resolves the name to a repository link at build time, so `-W`
#: already fails on one that does not import; these tests keep naming the
#: symbol in the failure and keep the coverage rule that every labelled
#: equation sits beside one.
SOURCE_LINE = re.compile(r"^\{source\}`([A-Za-z_][\w.]*)`$", re.MULTILINE)
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
    copied_in = _copied_in()
    stray: list[str] = []
    for page in sorted(out.rglob("*.html")):
        if page.relative_to(out).as_posix() in copied_in:
            continue        # the landing page — see _copied_in()
        text = MARKUP_WITHOUT_PROSE.sub("", page.read_text(encoding="utf-8"))
        for match in re.finditer(r".{0,60}\$.{0,60}", text, re.S):
            stray.append(f"{page.name}: …{match.group(0).strip()}…")
    assert not stray, "unrendered TeX in the built prose:\n" + "\n".join(stray[:10])


@pytest.mark.xdist_group("manual-build")
def test_no_unsubstituted_substitution_survives_the_build(built_manual):
    """No `{{ NAME }}` reaches the rendered page.  The guard above, one
    delimiter over, and the same blind spot: `-W` sees nothing.

    A MyST substitution is expanded in prose and **not** inside a `{math}`
    directive, so a constant written into an equation reaches MathJax as its
    own name and is typeset as a product of italic letters.  Both instances
    this was written for were live in the shipped HTML — `profiles.md`'s
    strain cap printed `f = STRAINCAPRANGEFRACTION` and its size cap
    `L_min = SIZECAPMINSIZENM nm` (WP-1408) — and neither is a build warning,
    because the substitution is *defined*; it is simply never reached.

    The fix for a new one is never to define the constant somewhere else: keep
    the symbol in the equation and state its value in the prose beside it,
    which is where `conf.py`'s injection works.
    """
    out, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    copied_in = _copied_in()
    stray: list[str] = []
    for page in sorted(out.rglob("*.html")):
        if page.relative_to(out).as_posix() in copied_in:
            continue        # the landing page — see _copied_in()
        text = MARKUP_WITHOUT_PROSE.sub("", page.read_text(encoding="utf-8"))
        for match in re.finditer(r".{0,60}\{\{.{0,60}", text, re.S):
            stray.append(f"{page.name}: …{match.group(0).strip()}…")
    assert not stray, (
        "a MyST substitution reached the page unexpanded (a `{{ NAME }}` inside "
        "a {math} directive is the usual cause):\n" + "\n".join(stray[:10])
    )


def test_the_tch_coefficients_in_print_are_the_ones_the_code_runs():
    """(3.6) and (3.7) print seven literals, and they have to be the code's.

    This is the case the manual's usual anti-divergence rule cannot cover. A
    constant is normally injected as a MyST substitution, which is not expanded
    inside a `{math}` directive (WP-1408), so a coefficient that belongs
    *inside* an equation has to be typed — and then nothing holds the two
    copies together. Reading them back out of the chapter is what does.
    """
    from rietx.model.profiles.pseudovoigt import _TCH_ETA, _TCH_GAMMA

    text = (MANUAL_DIR / "profiles.md").read_text(encoding="utf-8")
    for label, expected in (("prof-tch-gamma", _TCH_GAMMA), ("prof-tch-eta", _TCH_ETA)):
        block = re.search(rf":label: {label}\n(.*?)^```", text, re.S | re.M)
        assert block, f"{label}: equation not found in profiles.md"
        printed = [float(n) for n in re.findall(r"\d+\.\d{4,}", block.group(1))]
        assert printed == [abs(c) for c in expected], (
            f"{label} prints {printed}, the code runs {list(expected)}")


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


BIB_ENTRY = re.compile(r"^@(\w+)\{([^,\s]+)\s*,\n(.*?)\n\}\s*$", re.MULTILINE | re.DOTALL)
BIB_FIELD = re.compile(r"^\s*(\w+)\s*=\s*\{(.*?)\}\s*,?\s*$", re.MULTILINE | re.DOTALL)

#: The one article with no DOI, and why (references.bib § rule 2).  A list
#: rather than a count, so adding an entry without one has to say which.
NO_DOI = {"scherrer1918": "Göttinger Nachrichten 1918 predates the DOI register"}


def _bib_entries() -> list[tuple[str, str, dict[str, str]]]:
    text = (MANUAL_DIR / "references.bib").read_text(encoding="utf-8")
    out = []
    for kind, key, body in re.findall(r"@(\w+)\{([^,\s]+),\n(.*?)\n\}\n", text, re.S):
        out.append((kind, key, dict(BIB_FIELD.findall(body))))
    assert out, "no bibliography entries parsed — regex or file moved?"
    return out


def _unbraced_words(title: str) -> list[str]:
    """Words of a title that the `alpha` style is free to lowercase.

    Depth is tracked so a word inside `{...}` is exempt, and the depth a word
    *started* at is what counts — reading it at the closing brace would call
    every protected word unprotected.
    """
    words: list[str] = []
    depth, word, word_depth = 0, "", 0
    for char in title:
        if char.isalnum() or char in "-'’":
            if not word:
                word_depth = depth
            word += char
            continue
        if word:
            if word_depth == 0:
                words.append(word)
            word = ""
        depth += (char == "{") - (char == "}")
    if word and word_depth == 0:
        words.append(word)
    return words


def test_no_bibliography_title_has_an_unbraced_interior_capital():
    """references.bib § rule 1, the one the reader sees when it is broken.

    `bibtex_default_style = "alpha"` sentence-cases a title, so a capital that
    is neither braced nor the first word is lowercased on every page that
    cites the entry. It rendered ten entries as "x-ray" and this package's own
    citation as "Rietx: python-api-first analysis and rietveld refinement"
    (WP-1408). The first word is exempt: the style capitalises it and leaves
    the rest of it alone.
    """
    offenders = []
    for _kind, key, fields in _bib_entries():
        title = fields.get("title")
        if not title:
            continue
        for word in _unbraced_words(title)[1:]:
            if any(c.isupper() for c in word):
                offenders.append(f"{key}: {word!r} in {title[:60]!r}")
    assert not offenders, (
        "a capital the bibliography style will lowercase — brace the word, or "
        "the whole title if it is a proper name in title case:\n"
        + "\n".join(offenders)
    )


def test_every_article_carries_its_doi_in_the_one_case_the_file_uses():
    """references.bib § rules 2 and 3: an article has a DOI, and it is lower
    case — the form every machine source returns, so the field matches the
    only thing that can check it."""
    missing, miscased = [], []
    for kind, key, fields in _bib_entries():
        doi = fields.get("doi")
        if kind == "article" and not doi and key not in NO_DOI:
            missing.append(key)
        if doi and doi != doi.lower():
            miscased.append(f"{key}: {doi}")
    assert not missing, (
        "article entries with no doi field — look it up on Crossref and verify "
        f"title, year, volume and first page, or declare it in NO_DOI: {missing}")
    assert not miscased, f"doi fields that are not lower case: {miscased}"
    stale = sorted(set(NO_DOI) - {key for _k, key, _f in _bib_entries()})
    assert not stale, f"NO_DOI names entries that are gone: {stale}"


def test_every_source_symbol_imports():
    """Each equation's *Source:* line names a live module or attribute; a
    rename breaks this test rather than the reader's trust."""
    symbols: set[str] = set()
    for page in CHAPTERS:
        symbols.update(SOURCE_LINE.findall(page.read_text(encoding="utf-8")))
    assert symbols, "no {source} lines found — pattern or chapters moved?"
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
    at least one `{source}` line — an equation with no named source is a
    transcription with no audit trail."""
    for page in CHAPTERS:
        text = page.read_text(encoding="utf-8")
        n_labels = len(re.findall(r"^:label:", text, re.MULTILINE))
        n_sources = len(SOURCE_LINE.findall(text))
        if n_labels:
            assert n_sources > 0, f"{page.name}: {n_labels} labelled equations, no {{source}} lines"


def test_the_hump_table_agrees_with_the_refinement_that_produced_it():
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
    :class:`~rietx.schemas.instrument.HumpComponent` docstring — and the second
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
        "cheb3_peak": "| Chebyshev-3 **+ one hump** |",
        "cheb6": "| Chebyshev, 6 terms |",
        "cheb6_peak": "| Chebyshev-6 + one hump |",
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

    # --- the reST table in the HumpComponent docstring, keyed by the `terms`
    # column (its two peak rows share the label "that **+ one peak**", so the
    # label cannot key them; the term count can) ---
    doc = importlib.import_module(
        "rietx.schemas.instrument").HumpComponent.__doc__
    lines = doc.splitlines()
    seps = [i for i, ln in enumerate(lines)
            if ln.strip() and set(ln.strip()) <= {"=", " "}]
    assert len(seps) >= 3, "the HumpComponent docstring table lost its rules"
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
            f"the HumpComponent docstring's {key} row says Rwp {cols[2]}, the "
            f"fixture that produced it says {manual_rwp[key]}")
        seen.add(key)
    assert seen == set(terms_to_key.values()), (
        f"the HumpComponent docstring table is missing rows: "
        f"{set(terms_to_key.values()) - seen}")
