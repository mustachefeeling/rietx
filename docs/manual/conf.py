# Sphinx configuration for the rietx manual: Part 1 (using/, WP-1067) and
# Part 2 (the theory chapters, WP-0604) in one tree.
#
# Anti-divergence rule (WP-0604): a threshold or fenced constant is never
# typed into a chapter.  It is imported here from the live package and exposed
# as a MyST substitution ({{ BRINDLEY_MU_R_FENCE }} etc.), so a renamed or
# retuned constant fails the -W build instead of leaving a stale number in
# print.  Prose derivations stay in the module docstrings; chapters carry the
# numbered equations and point at their source symbols.  Part 1's own guard is
# name resolution rather than constant injection (tests/test_manual_api.py).

from importlib.metadata import version as _dist_version
from pathlib import Path as _Path

from rietx._about import DIST_NAME
from rietx.crystallography.dispersion import NEAR_EDGE_EV
from rietx.crystallography.symmetry import SYMMETRY_ANGLE_TOL_DEG
from rietx.help import help_registry
from rietx.indexing.ambiguity import MAX_AMBIGUITY_INDEX
from rietx.indexing.dichotomy import ANGLE_STEP_DEG, AXIS_STEP
from rietx.indexing.engines import (
    DEFAULT_N_UNINDEXED,
    DEFAULT_SEARCH_LINES,
    SEARCH_POOL_MULTIPLE,
)
from rietx.indexing.reduce import NIGGLI_EPS_RELATIVE
from rietx.model.absorption import CYLINDER_MU_R_MAX
from rietx.model.forward import PAWLEY_OVERLAP_FWHM_FRAC, WINDOW_AREA_TOL
from rietx.model.geometry import (
    ANGLE_LINEARISATION_LIMIT_DEG,
    VARIANCE_CANCELLATION_FLOOR,
)
from rietx.model.profiles.fcj import NODES_PER_FWHM, SKIP_EXTENT_FWHM_RATIO
from rietx.optimize.qpa import BRINDLEY_MU_R_FENCE
from rietx.optimize.statistics import (
    EFFECTIVE_OBS_ALPHA,
    MAX_SHIFT_CONVERGED,
    OBS_PER_PARAMETER_MIN,
    OBS_PER_PARAMETER_PREFERRED,
)
from rietx.params.vector import SIZE_CAP_MIN_SIZE_A, STRAIN_CAP_RANGE_FRACTION
from rietx.refine import SIZE_FLAG_SIZE_A, STRAIN_FLAG_WIDTH
from rietx.report.layer2 import IMPURITY_SIGMA
from rietx.report.schemas import THRESHOLDS_VERSION, VALIDITY_RADIUS_FWHM
from rietx.schemas.indexing import MAX_RELATIVE_SIGMA_Q, MIN_LINES_PER_DOF
from rietx.schemas.suggest import SUGGEST_MIN_GAIN

project = "rietx manual"
author = "rietx developers"
release = _dist_version(DIST_NAME)
version = release

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinxcontrib.bibtex",
    "sphinxcontrib.mermaid",
]

# Diagrams render in the browser (`raw` output needs no mermaid-cli at build
# time).  The extension detects the active theme from `body[data-theme]`, which
# is what furo writes, and re-renders on a MutationObserver when the toggle
# moves — so these two names are the whole light/dark story.  mermaid.js itself
# comes from a CDN when the page is *viewed*; set `mermaid_use_local` if a
# built copy of the manual has to render diagrams offline.
mermaid_light_theme = "default"
mermaid_dark_theme = "dark"
# Without the title margin, a subgraph label is drawn on the cluster border and
# collides with the first node inside it.
mermaid_init_config = {
    "startOnLoad": False,
    "flowchart": {"subGraphTitleMargin": {"top": 6, "bottom": 12}},
}

bibtex_bibfiles = ["references.bib"]
bibtex_default_style = "alpha"

myst_enable_extensions = ["dollarmath", "amsmath", "substitution", "colon_fence",
                          "deflist"]
myst_substitutions = {
    # An angle's esd is withheld this close to 0°/180°; the raw value carries
    # fifteen digits of an arccos clamp, so it is formatted rather than typed —
    # still derived, and a retuned clamp still moves the printed number.
    "ANGLE_LINEARISATION_LIMIT_DEG": f"{ANGLE_LINEARISATION_LIMIT_DEG:.1e}",
    "BRINDLEY_MU_R_FENCE": BRINDLEY_MU_R_FENCE,
    "CYLINDER_MU_R_MAX": CYLINDER_MU_R_MAX,
    "EFFECTIVE_OBS_ALPHA": EFFECTIVE_OBS_ALPHA,
    "MAX_SHIFT_CONVERGED": MAX_SHIFT_CONVERGED,
    "OBS_PER_PARAMETER_MIN": OBS_PER_PARAMETER_MIN,
    "OBS_PER_PARAMETER_PREFERRED": OBS_PER_PARAMETER_PREFERRED,
    "VARIANCE_CANCELLATION_FLOOR": VARIANCE_CANCELLATION_FLOOR,
    "DEFAULT_N_UNINDEXED": DEFAULT_N_UNINDEXED,
    "DEFAULT_SEARCH_LINES": DEFAULT_SEARCH_LINES,
    "SEARCH_POOL_MULTIPLE": SEARCH_POOL_MULTIPLE,
    "IMPURITY_SIGMA": IMPURITY_SIGMA,
    "ANGLE_STEP_DEG": ANGLE_STEP_DEG,
    "AXIS_STEP": AXIS_STEP,
    "MAX_AMBIGUITY_INDEX": MAX_AMBIGUITY_INDEX,
    "MAX_RELATIVE_SIGMA_Q": MAX_RELATIVE_SIGMA_Q,
    "MIN_LINES_PER_DOF": MIN_LINES_PER_DOF,
    "NEAR_EDGE_EV": NEAR_EDGE_EV,
    "NIGGLI_EPS_RELATIVE": NIGGLI_EPS_RELATIVE,
    "NODES_PER_FWHM": NODES_PER_FWHM,
    "PAWLEY_OVERLAP_FWHM_FRAC": PAWLEY_OVERLAP_FWHM_FRAC,
    "SKIP_EXTENT_FWHM_RATIO": SKIP_EXTENT_FWHM_RATIO,
    "STRAIN_CAP_RANGE_FRACTION": STRAIN_CAP_RANGE_FRACTION,
    "STRAIN_FLAG_WIDTH": STRAIN_FLAG_WIDTH,
    "SIZE_CAP_MIN_SIZE_NM": SIZE_CAP_MIN_SIZE_A / 10.0,
    "SIZE_FLAG_SIZE_NM": SIZE_FLAG_SIZE_A / 10.0,
    "SUGGEST_MIN_GAIN": SUGGEST_MIN_GAIN,
    "SYMMETRY_ANGLE_TOL_DEG": SYMMETRY_ANGLE_TOL_DEG,
    "THRESHOLDS_VERSION": THRESHOLDS_VERSION,
    "VALIDITY_RADIUS_FWHM": VALIDITY_RADIUS_FWHM,
    "WINDOW_AREA_TOL": WINDOW_AREA_TOL,
    "release": release,
}

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

html_theme = "furo"
html_title = f"rietx {release} — manual"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
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
    ("peak_diagnostics", "Peak-list diagnostics",
     "Messages about the list rather than about one line. Several are the "
     "list-level summary of a flag and say how many lines carry it."),
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


def _detail(entry: dict) -> str:
    """The unit / default / typical line, omitting whatever is absent."""
    bits = []
    if entry.get("unit"):
        bits.append(f"Unit {entry['unit']}")
    if entry.get("default") is not None:
        bits.append(f"Default `{entry['default']}`")
    if entry.get("modes"):
        bits.append("Modes " + ", ".join(f"`{m}`" for m in entry["modes"]))
    if entry.get("typical"):
        bits.append(f"Typical {entry['typical']}")
    return " · ".join(bits)


def _definition(term: str, entry: dict) -> list[str]:
    lines = [term, f": {entry['title']}. {entry['description']}"]
    detail = _detail(entry)
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
            out += _definition(f"`{name}`", entry)

    GLOSSARY_BODY.parent.mkdir(exist_ok=True)
    GLOSSARY_BODY.write_text("\n".join(out), encoding="utf-8")


_write_glossary()
