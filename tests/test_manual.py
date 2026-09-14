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
#: equation sits beside one.  Leading and trailing whitespace is allowed: a
#: role indented inside a directive, or a line with a stray trailing space, is
#: a source line the reader sees, and anchoring hard would make it invisible to
#: both guards below rather than making it illegal.
SOURCE_LINE = re.compile(r"^[ \t]*\{source\}`([A-Za-z_][\w.]*)`[ \t]*$", re.MULTILINE)
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
def test_no_unrendered_markup_survives_the_build(built_manual):
    """No backtick reaches the rendered prose.  The `$` guard above, one
    delimiter over, and the same blind spot: the page builds clean and prints
    the markup.

    Every backtick in a MyST source opens a code span or a role, and both
    render as an element `MARKUP_WITHOUT_PROSE` strips, so a backtick left in
    the prose is a construct that did not close.  Both instances this was
    written for were live in the shipped HTML (WP-1409).

    `using/indexing.md`'s "Further reading" had lost the ``{doc}`` prefix and
    the opening backtick off a role, so the page printed ``the [agent skill
    <skill>`,`` as text, with `<skill>` swallowed as an HTML tag.  And the
    agent skill's `references/abstention.md` wrote ``scale × |F|² × profile``
    as a code span **inside a Markdown table cell**, where the first `|` ends
    the cell: the span never closed and the backticks rendered literally.  In a
    table the pipes are escaped and the span dropped, which is what the manual's
    own tables already do (`\\|F\\|²`).
    """
    out, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    copied_in = _copied_in()
    stray: list[str] = []
    for page in sorted(out.rglob("*.html")):
        if page.relative_to(out).as_posix() in copied_in:
            continue        # the landing page — see _copied_in()
        text = MARKUP_WITHOUT_PROSE.sub("", page.read_text(encoding="utf-8"))
        for match in re.finditer(r".{0,60}`.{0,60}", text, re.S):
            stray.append(f"{page.name}: …{match.group(0).strip()}…")
    assert not stray, (
        "a code span or role did not close, and its backtick is in the built "
        "prose:\n" + "\n".join(stray[:10])
    )


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
        # The sign is read too: `_TCH_ETA`'s middle coefficient is negative and
        # the chapter prints it as a subtraction, so comparing magnitudes would
        # let a sign flip in either copy through unseen.
        printed = [float(sign.replace("+", "") + digits)
                   for sign, digits in re.findall(r"([-+])?\s*(\d+\.\d{4,})", block.group(1))]
        assert printed == list(expected), (
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


#: One entry: `@kind{key,` down to a `}` alone at the start of a line.  The
#: closing brace is anchored with `$` rather than a literal newline, so the
#: last entry is still parsed on a file with no trailing newline — a regex
#: that needs the newline drops it silently, which is a bibliography entry
#: quietly exempt from both guards below.
BIB_ENTRY = re.compile(r"^@(\w+)\{([^,\s]+)\s*,\n(.*?)\n\}\s*$", re.MULTILINE | re.DOTALL)
BIB_FIELD = re.compile(r"^\s*(\w+)\s*=\s*\{(.*?)\}\s*,?\s*$", re.MULTILINE | re.DOTALL)

#: The one article with no DOI, and why (references.bib § rule 2).  A list
#: rather than a count, so adding an entry without one has to say which.
NO_DOI = {"scherrer1918": "Göttinger Nachrichten 1918 predates the DOI register"}


def _bib_entries() -> list[tuple[str, str, dict[str, str]]]:
    text = (MANUAL_DIR / "references.bib").read_text(encoding="utf-8")
    out = []
    for kind, key, body in BIB_ENTRY.findall(text):
        out.append((kind, key, dict(BIB_FIELD.findall(body))))
    assert out, "no bibliography entries parsed — regex or file moved?"
    return out


def _title_words(title: str) -> list[tuple[str, bool]]:
    """Every word of a title, each with whether `{...}` protects it.

    Depth is tracked so a word inside `{...}` is exempt, and the depth a word
    *started* at is what counts — reading it at the closing brace would call
    every protected word unprotected.

    A protected word stays **in** the list rather than being filtered out here,
    because the caller exempts the title's *first* word: dropping them would
    shift that exemption onto the second word of every title opening with a
    braced proper noun, and nine entries do (`{Rietveld} refinement …`).
    """
    words: list[tuple[str, bool]] = []
    depth, word, word_depth = 0, "", 0
    for char in title:
        if char.isalnum() or char in "-'’":
            if not word:
                word_depth = depth
            word += char
            continue
        if word:
            words.append((word, word_depth > 0))
            word = ""
        depth += (char == "{") - (char == "}")
    if word:
        words.append((word, word_depth > 0))
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
        for word, protected in _title_words(title)[1:]:
            if not protected and any(c.isupper() for c in word):
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
    entries = _bib_entries()
    missing, miscased = [], []
    for kind, key, fields in entries:
        doi = fields.get("doi")
        if kind == "article" and not doi and key not in NO_DOI:
            missing.append(key)
        if doi and doi != doi.lower():
            miscased.append(f"{key}: {doi}")
    assert not missing, (
        "article entries with no doi field — look it up on Crossref and verify "
        f"title, year, volume and first page, or declare it in NO_DOI: {missing}")
    assert not miscased, f"doi fields that are not lower case: {miscased}"
    stale = sorted(set(NO_DOI) - {key for _k, key, _f in entries})
    assert not stale, f"NO_DOI names entries that are gone: {stale}"


#: A citation label alpha built from one author, longer than the three letters
#: it normally takes.  `srd128`'s author is the braced corporate name `{NIST}`,
#: which pybtex keeps whole because the braces make it non-alphabetic.  A list
#: rather than a bound, so a second one has to say what it is.
LONG_SINGLE_AUTHOR_LABELS = {"srd128": "{NIST}, a braced corporate author"}

LABEL_TAIL = re.compile(r"^(.*?)(\d{2})([a-z]?)$")


def test_every_citation_label_abbreviates_its_authors():
    """references.bib § rule 5, read off the labels themselves.

    `alpha` builds a label by abbreviating each surname, and pybtex abbreviates
    a name part only where `str.isalpha()` holds for it. A LaTeX accent macro
    carries a backslash and braces, so the part is passed through whole and the
    label spells the surname out: nine entries rendered as [LouerLouer72],
    [Humlivcek82], [KvrivyG76] and their like among ninety-six that abbreviate
    (WP-1408). Write the accent in Unicode and the abbreviation works.

    The invariant is what the reader sees, so it is asserted on the rendered
    label: two or more authors give initials, which are upper case, and one
    author gives three letters.
    """
    pytest.importorskip("pybtex")
    from pybtex.database.input import bibtex
    from pybtex.plugin import find_plugin

    data = bibtex.Parser().parse_file(str(MANUAL_DIR / "references.bib"))
    style = find_plugin("pybtex.style.formatting", "alpha")()
    offenders = []
    for formatted in style.format_entries(data.entries.values()):
        entry = data.entries[formatted.key]
        people = entry.persons.get("author") or entry.persons.get("editor") or []
        match = LABEL_TAIL.match(formatted.label)
        if match is None:
            continue  # no year: the label is the entry key, not an abbreviation
        stem = match.group(1).replace("+", "")
        if len(people) > 1:
            if not stem.isupper():
                offenders.append(f"{formatted.key}: [{formatted.label}] is not initials")
        elif len(stem) > 3 and formatted.key not in LONG_SINGLE_AUTHOR_LABELS:
            offenders.append(f"{formatted.key}: [{formatted.label}] spells the surname out")
    assert not offenders, (
        "citation labels that do not abbreviate — an accented surname written "
        "as a LaTeX macro defeats pybtex's abbreviator, so write it in Unicode "
        "(references.bib § rule 5):\n" + "\n".join(offenders)
    )
    stale = sorted(set(LONG_SINGLE_AUTHOR_LABELS) - set(data.entries))
    assert not stale, f"LONG_SINGLE_AUTHOR_LABELS names entries that are gone: {stale}"


#: One rendered citation, tags stripped: `[Bergmann et al., 2004]`.
CITATION_SPAN = re.compile(r'<span class="bibtex-citation".*?</span>', re.S)
#: `et al.` ends in a period, so the character before the comma is not always
#: a letter.
YEAR_IN_CITATION = re.compile(r"[A-Za-z\u00c0-\u024f.]\s*,\s*(?:19|20)\d{2}[a-z]?")

#: The rule in `_static/custom.css` that hides the bibliography's own label.
#: Matched on the selector rather than the whole block, so reformatting the
#: stylesheet does not fail the test.
BIBLIO_LABEL_RULE = 'div.citation[role="doc-biblioentry"] > span.label'


def test_every_citation_reads_as_author_and_year(built_manual):
    """`conf.py` § bibtex: a citation names its author and year on the page.

    Three settings produce this and any one of them can be lost quietly, so
    the guard reads the built page rather than the config. `alpha` labels —
    [BLBSZ04] for a work cited once among 105 — carry no meaning the reader can
    use, and the bibliography sits on a different page from all but one
    citation, so decoding one costs a navigation (WP-1408 § G3).

    The separator is checked too. `BracketStyle.sep` defaults to a comma, which
    is also what separates an author from its year, so the fourteen citations
    naming more than one work rendered as a flat comma list of six fragments.
    A citation carrying N years must carry N-1 semicolons.
    """
    out, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    not_author_year, bad_separator = [], []
    multi = 0
    for page in sorted(out.rglob("*.html")):
        for match in CITATION_SPAN.finditer(page.read_text(encoding="utf-8")):
            text = re.sub(r"<[^>]+>", "", match.group(0)).strip()
            years = YEAR_IN_CITATION.findall(text)
            if not years:
                not_author_year.append(f"{page.name}: {text}")
                continue
            if len(years) > 1:
                multi += 1
                if text.count("; ") != len(years) - 1:
                    bad_separator.append(f"{page.name}: {text}")
    assert not not_author_year, (
        "citations that do not name an author and a year — check "
        "`bibtex_reference_style` in conf.py:\n" + "\n".join(not_author_year[:10])
    )
    assert multi, "no citation names more than one work — the separator is untested"
    assert not bad_separator, (
        "works in one citation are not separated by a semicolon — check the "
        "registered BracketStyle in conf.py:\n" + "\n".join(bad_separator[:10])
    )


#: A rendered `{eq}` reference: a link into an equation, whose own text is the
#: number in round brackets.
EQUATION_REF = re.compile(r'<a[^>]*href="[^"]*#equation-[^"]*"[^>]*>\((\d+\.\d+)\)</a>')


def test_no_reference_is_doubly_bracketed(built_manual):
    """A reference brings its own brackets, so the prose must not add a second
    pair.

    `{eq}` renders `(1.4)` and a citation renders `[Rietveld, 1969]`, and
    writing either inside a bracket of the same kind prints `((1.4))` or
    `[[Rietveld, 1969]]`. Twenty-one sites across nine chapters wrapped an
    equation reference in parentheses of their own, reaching the shipped HTML
    as `((1.4))`, `((10.7))` and `((10.8), (10.9))` (WP-1408 § G4). Neither
    `-W` nor a prose read catches it, because the source reads `({eq}`x`)`,
    which looks like ordinary punctuation.

    Brackets of the *other* kind are left alone. `(via Scherrer, (6.3) in …)`
    is ordinary English and reads correctly.
    """
    out, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    doubled, seen = [], 0
    for page in sorted(out.rglob("*.html")):
        if page.name in ("search.html", "genindex.html"):
            continue
        html_text = page.read_text(encoding="utf-8")
        for pattern, left, right in (
            (EQUATION_REF, "(", ")"),
            (CITATION_SPAN, "[", "]"),
        ):
            for match in pattern.finditer(html_text):
                rendered = re.sub(r"<[^>]+>", "", match.group(0)).strip()
                if not (rendered.startswith(left) and rendered.endswith(right)):
                    continue        # a citation style without brackets of its own
                seen += 1
                before = re.sub(r"<[^>]+>", "", html_text[max(0, match.start() - 60):match.start()])
                after = re.sub(r"<[^>]+>", "", html_text[match.end():match.end() + 60])
                if before.rstrip().endswith(left) or after.lstrip().startswith(right):
                    doubled.append(f"{page.name}: …{before.strip()[-45:]}{rendered}{after[:14]}…")
    assert seen, "no bracketed references found in the built manual — the patterns moved"
    assert not doubled, (
        "a reference sits inside a bracket of its own kind, so the page prints a "
        "doubled bracket — drop the prose brackets, the reference carries its "
        "own:\n" + "\n".join(doubled[:12])
    )


def test_the_bibliography_label_is_hidden_and_the_rule_reaches_all_of_them(built_manual):
    """The other half of § G3, which no build warning can see.

    docutils gives every citation node a label and sphinxcontrib-bibtex
    documents that it cannot remove one, so the list would print [BL91a] beside
    a citation reading [Boultif and Louër, 1991]. `custom.css` hides it. The
    selector is only safe while every label on the site belongs to the
    bibliography, so that is asserted rather than assumed: a label appearing
    anywhere else would be hidden too, silently.
    """
    out, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    css = (out / "_static" / "custom.css").read_text(encoding="utf-8")
    assert BIBLIO_LABEL_RULE in css, (
        f"the rule hiding the bibliography's own label is gone from custom.css: {BIBLIO_LABEL_RULE}"
    )
    labels = biblio_labels = 0
    for page in sorted(out.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        labels += text.count('<span class="label">')
        for entry in re.findall(r'<div class="citation"[^>]*role="doc-biblioentry".*?</div>', text, re.S):
            biblio_labels += entry.count('<span class="label">')
    assert labels, "no citation labels in the built site — the bibliography moved or vanished"
    assert labels == biblio_labels, (
        f"{labels - biblio_labels} label(s) outside the bibliography would be hidden by "
        f"`{BIBLIO_LABEL_RULE}` — narrow the selector"
    )


#: Part 2 — the theory chapters, which are the manual's top-level `.md` files
#: other than the root document.  Derived rather than listed, so a chapter
#: added to Part 2 inherits the guards below (the `using/` subdirectory is
#: Part 1 and `tests/test_manual_api.py` is its guard).
def _part_two() -> list[Path]:
    pages = [p for p in CHAPTERS
             if p.parent == MANUAL_DIR and p.name not in {"manual.md"}]
    assert len(pages) > 5, "Part 2 chapters not found — has the tree moved?"
    return pages


#: Every chapter a person wrote, both parts.  ``_generated/`` is excluded
#: because neither file in it is the manual's prose to hold: the glossary body
#: is written from ``rietx.help`` by ``conf.py`` (and guarded by
#: ``tests/test_help.py``), and the skill body is the agent skill rendered
#: whole, which is a rulebook an agent cites and may compress
#: (``tests/test_skill.py``).
def _authored_chapters() -> list[Path]:
    pages = [p for p in CHAPTERS
             if "_generated" not in p.relative_to(MANUAL_DIR).parts]
    assert len(pages) > 20, "the manual's chapters are not where this expects"
    return pages


#: A directive option (``:class:``, ``:alt:``, ``:language:``) and an ``:::``
#: admonition marker, distinguished from a MyST definition-list body (``: the
#: text``), which is prose and is kept.
_DIRECTIVE_OPTION = re.compile(r"^:(?::+|[a-z][a-z0-9-]*:)")

#: ``:::{admonition} A title`` — the marker is markup and the title after it is
#: prose a reader sees, so the two halves of the line part company here.  Without
#: this the option pattern above swallows the title with the marker.
_DIRECTIVE_MARKER = re.compile(r"^:{3,}\{[a-z][a-z0-9-]*\}\s*(.*)$")

#: The prose of a page: lines outside fenced blocks, with code spans stripped.
#: A token inside ``…`` is a field name or captured output and a fenced block is
#: TeX or a console transcript, so neither is this file's to police.
#:
#: An admonition's **body** is prose and was not covered until WP-1409: the
#: helper skipped a whole ``:::`` block, so Part 1's admonitions carried 17 em
#: dashes and 12 bold marks that the register guard below could not see.  Only
#: the markers and the option lines are dropped now, and a marker's own title
#: is kept, since it renders as the admonition's heading.  An HTML comment goes
#: too: ``<!-- api-doc: no-exec — … -->`` is a directive to `test_manual_api.py`
#: and renders nowhere, and Part 1 carries 66 em dashes inside them.  A comment
#: is tracked to its ``-->`` rather than by its first line alone, or a comment
#: written over two lines puts its second line back into the prose.
def _prose_lines(page: Path) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    fence = None
    comment = False
    for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.lstrip()
        if comment:
            comment = "-->" not in stripped
            continue
        if fence is None and stripped.startswith("```"):
            fence = "```"
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith("<!--"):
            comment = "-->" not in stripped
            continue
        marker = _DIRECTIVE_MARKER.match(stripped)
        if marker:
            stripped = marker.group(1)
            if not stripped:
                continue
        elif _DIRECTIVE_OPTION.match(stripped):
            continue
        lines.append((number, re.sub(r"`[^`]*`", "", stripped)))
    return lines


#: Two marks of the maintainer register, both invisible to `-W` because both are
#: valid Markdown.  Each carries the fix, since a failure is an editing job.
REGISTER_MARKS = (
    ("\u2014", "an em dash: give the aside its own sentence, or use parentheses"),
    ("**", "bold: the heading carries the claim, and backticks cover identifiers"),
)


def test_the_manual_keeps_its_register():
    """The manual is prose someone reads to get work done, and reads as it.

    A rulebook may compress, and `CLAUDE.md` measures ~15 em dashes per 1000
    words with the register working.  A manual's budget is 0, and the failure
    this guard exists for is leakage: the rulebook sits in the same tree, gets
    read first, and its voice arrives in the manual by default. That is how all
    twelve Part 2 chapters came to measure 6-15 per 1000 and to carry 87 bold or
    italic maxims (WP-1408), and Part 1 to carry 363 em dashes and 400 bold
    marks over 73 699 words (WP-1409, `yue-prose`).

    Both parts, since WP-1409.  Part 2 was already at zero when Part 1 was
    swept, so widening the page list and `_prose_lines`' zones cost Part 2 no
    edit — which is the evidence that the zones were a hole rather than an
    exemption.

    The two marks below are the mechanical half of that register, so they are
    the half a test can hold; the rest is `yue-prose`'s grep pass, run on the
    chapter you edited.  A page that genuinely needs bold (a UI label, a table
    header) changes this test and says why: Part 1 writes its GUI labels in
    backticks instead, which is what the majority of them already did.
    """
    offenders = []
    for page in _authored_chapters():
        for number, line in _prose_lines(page):
            for mark, fix in REGISTER_MARKS:
                if mark in line:
                    rel = page.relative_to(MANUAL_DIR).as_posix()
                    offenders.append(f"{rel}:{number}: {fix}\n    {line.strip()[:70]}")
    assert not offenders, (
        "the manual carries the maintainer register:\n" + "\n".join(offenders)
    )


def test_part_two_sets_a_statistic_as_mathematics():
    """`Rwp` in plain text, four lines under an equation that defines
    $R_{wp}$, was the reader-visible half of this (WP-1408).

    The rule is stated in `manual.md` § How to read this manual and is a
    difference between the two parts, not a global ban: Part 1 writes Rwp and
    χ² as plain text, because that is the word on the GUI header and in a
    console line. So this guard covers Part 2 only, and it exempts code spans
    and fenced blocks, where the token is a field name or captured output.
    """
    offenders = []
    for page in _part_two():
        for number, line in _prose_lines(page):
            if "Rwp" in line:
                offenders.append(f"{page.name}:{number}: {line.strip()[:70]}")
    assert not offenders, (
        "Part 2 writes the statistic as mathematics — $R_{wp}$, "
        "$\\Delta R_{wp}$ — never as plain text:\n" + "\n".join(offenders)
    )


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


def test_no_chapter_still_writes_a_source_line_by_hand():
    """The old `*Source:* \\`name\\`` spelling is gone and stays gone.

    It is the one thing about the `{source}` role (WP-1408) that no other
    guard sees: a page that writes the line by hand renders it as plain text
    beside a hundred linked ones, the name resolves against nothing, and the
    coverage test above is satisfied by the page's *other* lines. Loud here
    rather than silent on the page.
    """
    offenders = []
    for page in CHAPTERS:
        for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("*Source:*"):
                offenders.append(f"{page.name}:{number}: {line.strip()[:60]}")
    assert not offenders, (
        "write the source line as the `{source}` role, which resolves the name "
        "to a repository link at build time:\n" + "\n".join(offenders)
    )


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
        "cheb3_peak": "| Chebyshev-3 + one hump |",
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
