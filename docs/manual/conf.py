# Sphinx configuration for the rietx manual: Part 1 (using/, WP-1067) and
# Part 2 (the theory chapters, WP-0604) in one tree.
#
# Anti-divergence rule (WP-0604): a threshold or fenced constant is never
# typed into a chapter.  It is injected from the live package as a MyST
# substitution, defined in `docs/sphinx_shared.py` since WP-1978 so that the
# new tree in docs/docs/ quotes the same numbers.  Part 1's own guard is name
# resolution rather than constant injection (tests/test_manual_api.py).

import re as _re
import sys as _sys
from importlib.metadata import version as _dist_version
from pathlib import Path as _Path

from rietx._about import DIST_NAME, DOCS_URL
from rietx.help import help_registry

# The parts this tree shares with the new one in docs/docs/ (WP-1978): the
# fenced constants, the citation style, the diagram theme and the `{source}`
# role.  A module both conf.py files import, so one change reaches both trees.
_sys.path.append(str(_Path(__file__).resolve().parent.parent))
import sphinx_shared as _shared  # noqa: E402

project = "rietx manual"
author = "rietx developers"
release = _dist_version(DIST_NAME)
version = release

# `myst_nb` in place of `myst_parser`: it runs myst-parser underneath, so every
# `myst_*` setting below still applies, and it adds `.ipynb` as a source.
extensions = [
    "myst_nb",
    "sphinx_design",
    "sphinxcontrib.bibtex",
    "sphinxcontrib.mermaid",
]

mermaid_light_theme = _shared.MERMAID_LIGHT_THEME
mermaid_dark_theme = _shared.MERMAID_DARK_THEME
mermaid_init_config = _shared.MERMAID_INIT_CONFIG

# The tutorial notebooks render with the outputs they were committed with.
# `examples/tutorials/build.py` writes those outputs and
# `tests/test_tutorials.py` executes every notebook on every push, so the page
# shows what the tests ran.  Executing again here would make the manual's
# numbers a second run's.
nb_execution_mode = "off"

bibtex_bibfiles = ["references.bib"]
bibtex_default_style = _shared.BIBTEX_DEFAULT_STYLE
bibtex_reference_style = _shared.BIBTEX_REFERENCE_STYLE

myst_enable_extensions = _shared.MYST_EXTENSIONS
myst_substitutions = {**_shared.MYST_SUBSTITUTIONS, "release": release}

# Numbered sections and section-prefixed equation numbers ((3.2), not (2)).
numfig = True
math_numfig = True

# `_generated/` holds the glossary body `_write_glossary()` writes below.  It
# is included by `using/glossary.md`, not a document of its own, so Sphinx
# must not read it: -W would fail on a document in no toctree.  It lives
# outside `using/` because `tests/test_manual_api.py` globs that directory,
# and a page that exists only after a build would make the suite depend on
# whether one has run.
exclude_patterns = ["_build", "_generated"]

# The manual's root document is `manual.md`, not `index.md`, because `/` on the
# published site belongs to the landing page (WP-1331) and Sphinx would
# otherwise write `index.html` over it.  Nothing in the manual references the
# root document by name — no `:doc:`, no toctree entry — so the rename cost two
# lines; the reader-visible change is that the manual's front page is
# `rietx.org/manual.html`.  `_about.DOCS_URL` is the *site* root and is
# unaffected, as are `help.py`'s `page.html#id` anchors.
root_doc = "manual"

# ...and the landing page itself, copied in verbatim beside the built manual.
# `docs/landing/site/` is a build product of `docs/landing/build.py --site`,
# which needs a payload that is not in this repository (see docs/landing/
# README.md), so it is absent from a source checkout — and `-W` turns a missing
# `html_extra_path` entry into an error, while `tests/test_manual.py` builds the
# manual on every run.  Hence the existence test: a checkout without the landing
# page builds the manual alone, which is the right answer for a fork, and the
# Pages workflow runs the landing build first so the published site has both.
_landing_site = _Path(__file__).parent.parent / "landing" / "site"
html_extra_path = [str(_landing_site)] if _landing_site.is_dir() else []

html_theme = "furo"
html_title = f"rietx {release} — manual"
html_static_path = ["_static"]
html_css_files = ["custom.css"]

# The brand at the sidebar's top left (WP-1411).  `_templates/sidebar/brand.html`
# is furo's own template with one thing changed: the link goes to the landing
# page instead of to the manual's front page, which is where furo hardcodes it
# and where `theme.conf` gives no option to move it from.  Since WP-1331 the
# manual is `/manual.html` and the landing page is `/`, so furo's default sent
# "home" to the page the reader was already on, and nothing under `docs/manual/`
# linked to the site root at all.  The fork's own comment carries the rest.
templates_path = ["_templates"]
# `_about.DOCS_URL` and `_about.DIST_NAME`, never the URL and never the word:
# both are spelled in this tree only there (root CLAUDE.md § Conventions), and
# a hardcoded one is invisible to every test in the suite.  A Jinja template
# cannot import, so they arrive through the context.
html_context = {"rietx_home": DOCS_URL, "rietx_name": DIST_NAME}
# Without this the pages emit no icon link at all, and a browser then falls
# back to the *origin* root — https://yue-here.github.io/favicon.ico, which
# belongs to the user Pages site this project's pages sit under, not to this
# project.  There is no way to ask for no favicon; the only fix is to name one.
html_favicon = "_static/favicon.svg"


# ----------------------------------------------------------------------
# The glossary body (WP-1202)
#
# Same anti-divergence rule as the fenced constants above, one rank up: the
# entries are not typed into a chapter, they are written here from
# `rietx.help`, which is where the corpus lives.  A retuned default or a new
# vocabulary member therefore reaches the page without anyone editing it.
#
# `anchor` is deliberately not rendered as a link.  It names the page and
# heading the GUI's popover links to (WP-1203), and `tests/test_help.py` checks
# every one against the built HTML; a glossary that also linked them would need
# heading-anchor slugs turned on globally for no reader-visible gain here — the
# reader is already on the page the link would take them to a section of.
# ----------------------------------------------------------------------

GLOSSARY_BODY = _Path(__file__).parent / "_generated" / "glossary-body.md"

#: Section heading and lead sentence per arm, in the order the page shows them.
_ARMS = [
    ("stage_fields", "Stage settings",
     "One stage of a plan, as `StageSpec` serializes it. Staging is "
     "cumulative: a parameter freed in one stage keeps refining in every "
     "later one."),
    ("plans", "Plan presets",
     "The named strategies `refine(plan=...)` accepts. Each lists the "
     "intensity modes it is meaningful in."),
    ("peak_flags", "Peak flags",
     "What is known about one fitted line. Whether a flag also makes the line "
     "unusable as evidence of a lattice is served beside the vocabulary as "
     "`unusable_flags`, so no client re-derives it."),
    ("diagnostics", "Diagnostic codes",
     "What each diagnostic code means and why it fires. A finding's own "
     "message and suggestion say what this case found and what to do."),
    ("peak_origins", "Peak origins",
     "Where one line came from: detection, or a person. Provenance and not a "
     "judgement; no gate in the package branches on it."),
    ("reader_options", "Reader options",
     "Keyword arguments `read_pattern` accepts. A project records which ones "
     "claimed its file, because the same file can hold more than one pattern."),
    ("instrument_fields", "Instrument preset fields",
     "Constructor arguments for building an instrument from a geometry and an "
     "anode. These are not parameter paths and none of them is refined."),
    ("search_fields", "Indexing search settings",
     "The controls an indexing search takes, as `ProjectDoc.indexing` holds "
     "them. Several bound the search rather than describing the specimen, and "
     "each says what a negative result means once it has bitten."),
]


def _detail(entry: dict, name: str = "") -> str:
    """The chip / unit / default / typical line, omitting whatever is absent."""
    bits = []
    if entry.get("label") and entry["label"] != name:
        bits.append(f"Chip `{entry['label']}`")
    if entry.get("unit"):
        bits.append(f"Unit {entry['unit']}")
    if entry.get("default") is not None:
        bits.append(f"Default `{entry['default']}`")
    if entry.get("modes"):
        bits.append("Modes " + ", ".join(f"`{m}`" for m in entry["modes"]))
    if entry.get("typical"):
        bits.append(f"Typical {entry['typical']}")
    return " · ".join(bits)


def _definition(term: str, entry: dict, name: str = "") -> list[str]:
    lines = [term, f": {entry['title']}. {entry['description']}"]
    detail = _detail(entry, name)
    if detail:
        lines.append(f"  <br>{detail}")
    lines.append("")
    return lines


def _write_glossary() -> None:
    registry = help_registry()
    # `_ARMS` is a hand-written order and lead sentence per arm, so it is the
    # one thing here that does not derive from the registry.  Cross it, or an
    # arm added to `rietx.help` renders nowhere and nothing says so.
    missing = sorted(set(registry) - {"parameters"} - {key for key, _, _ in _ARMS})
    if missing:
        raise RuntimeError(
            f"help_registry() arms with no glossary section: {missing} — add a "
            "heading and lead sentence to _ARMS in docs/manual/conf.py")
    out = [
        "<!-- Generated by docs/manual/conf.py from rietx.help. Do not edit: "
        "edit the registry. -->",
        "",
        "## Parameters",
        "",
        "Dot-paths as a stage's `turn_on` globs spell them. Several globs share "
        "one entry where they share a meaning.",
        "",
    ]
    for entry in registry["parameters"]:
        term = ", ".join(f"`{p}`" for p in entry["paths"])
        out += _definition(term, entry)

    for key, heading, lead in _ARMS:
        out += [f"## {heading}", "", lead, ""]
        for name, entry in registry[key].items():
            out += _definition(f"`{name}`", entry, name)

    GLOSSARY_BODY.parent.mkdir(exist_ok=True)
    GLOSSARY_BODY.write_text("\n".join(out), encoding="utf-8")


_write_glossary()


# ----------------------------------------------------------------------
# The tutorial notebooks (WP-1916)
#
# Copied in at build by `sphinx_shared.copy_tutorials`, which the new tree
# calls too.  Here they land in `using/tutorials/`, which is gitignored, and
# `using/quickstart.md` is their toctree.  It cannot be `_generated/`, which
# `exclude_patterns` keeps out of the sources.
# ----------------------------------------------------------------------

# The count the quickstart's prose quotes, for the reason `N_EXAMPLES` exists.
myst_substitutions["N_TUTORIALS"] = _shared.copy_tutorials(
    _Path(__file__).parent / "using" / "tutorials")


# ----------------------------------------------------------------------
# The agent skill, rendered (WP-1304)
#
# The skill is a *directory* the package ships, and the chapter shows all of
# it so a person can read what the machine was told.  Written here rather
# than `{include}`d file by file for two reasons, both mechanical:
#
# * the body opens with YAML frontmatter, which is the skill's contract with
#   its harness and noise on a page; and
# * the tree's internal links are relative file paths -- correct for an agent
#   holding the directory, and nine `myst.xref_missing` warnings under `-W`
#   when the same text is rendered as one document.  They become plain code
#   spans here; the sidebar's contents list is what navigates the page.
#
# The file order is *derived* (body, then every reference alphabetically), so
# a reference file added to the skill renders without anyone editing this.
# ----------------------------------------------------------------------

SKILL_BODY = _Path(__file__).parent / "_generated" / "skill-body.md"
SKILL_TREE = _Path(__file__).parents[2] / "docs" / "skill" / "rietx"

#: ``[`references/x.md`](references/x.md)``, ``[`SKILL.md`](../SKILL.md)``
#: and a plain-text label, ``[judging](references/judging.md)``, which the
#: budgeted body uses because two backticks a link are bytes it pays for.
_SKILL_LINK = _re.compile(r"\[(`[^`]+`|[\w-]+)\]\((?:\.\./)?(?:references/)?[\w-]+\.md\)")


def _skill_label(match: _re.Match) -> str:
    """A link's label as a code span, whether or not it was written as one."""
    label = match.group(1)
    return label if label.startswith("`") else f"`{label}`"


def _demote(text: str, by: int) -> str:
    """Push every markdown heading down ``by`` levels, never a ``#`` in a fence."""
    out, fence = [], None
    for line in text.splitlines():
        stripped = line.lstrip()
        if fence is None and stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
        elif fence is not None and stripped.startswith(fence):
            fence = None
        if fence is None and line.startswith("#"):
            line = "#" * by + line
        out.append(line)
    return "\n".join(out)


def _write_skill() -> None:
    body = (SKILL_TREE / "SKILL.md").read_text(encoding="utf-8")
    if not body.startswith("---\n"):
        raise RuntimeError(f"{SKILL_TREE / 'SKILL.md'} lost its frontmatter")
    body = body.split("---\n", 2)[2].lstrip()
    # drop the skill's own H1: the chapter supplies the page title
    body = body.split("\n", 1)[1] if body.startswith("# ") else body

    parts = [
        "<!-- Generated by docs/manual/conf.py from docs/skill/rietx/. "
        "Do not edit: edit the skill. -->",
        "",
        "## The protocol",
        "",
        _demote(body.strip(), 1),
    ]
    references = list((SKILL_TREE / "references").glob("*.md"))
    if not references:
        raise RuntimeError(f"no reference files under {SKILL_TREE / 'references'}")

    def _section_order(path: _Path) -> tuple[float, str]:
        """Protocol order, from each file's own heading: 4, 5, ... 9b, then
        anything unnumbered.  Derived, so a renumbered section re-sorts
        itself."""
        heading = path.read_text(encoding="utf-8").split("\n", 1)[0]
        match = _re.match(r"#\s*(\d+)", heading)
        return (float(match.group(1)) if match else float("inf"), heading)

    for path in sorted(references, key=_section_order):
        text = path.read_text(encoding="utf-8").strip()
        heading = text.split("\n", 1)[0].lstrip("# ")
        # by 1, not 2: the file's own `#` title is dropped for the
        # `## Reference:` heading above, so its `##` sections become `###`
        parts += ["", f"## Reference: {heading}", "",
                  _demote(text.split("\n", 1)[1].strip(), 1)]

    rendered = _SKILL_LINK.sub(_skill_label, "\n".join(parts)) + "\n"
    SKILL_BODY.parent.mkdir(exist_ok=True)
    SKILL_BODY.write_text(rendered, encoding="utf-8")


_write_skill()



# The `{source}` role (WP-1408) lives in `docs/sphinx_shared.py`, which says
# why it resolves the way it does.


def setup(app):
    app.add_role("source", _shared.source_role)
    return {"version": release, "parallel_read_safe": True, "parallel_write_safe": True}
