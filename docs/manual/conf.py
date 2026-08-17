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

from rietx._about import DIST_NAME
from rietx.crystallography.dispersion import NEAR_EDGE_EV
from rietx.crystallography.symmetry import SYMMETRY_ANGLE_TOL_DEG
from rietx.indexing.ambiguity import MAX_AMBIGUITY_INDEX
from rietx.indexing.dichotomy import ANGLE_STEP_DEG, AXIS_STEP
from rietx.indexing.engines import (
    DEFAULT_N_UNINDEXED,
    DEFAULT_SEARCH_LINES,
    SEARCH_POOL_MULTIPLE,
)
from rietx.indexing.reduce import NIGGLI_EPS_RELATIVE
from rietx.model.absorption import CYLINDER_MU_R_MAX
from rietx.model.forward import PAWLEY_OVERLAP_FWHM_FRAC, WINDOW_FWHM_MULT
from rietx.model.geometry import (
    ANGLE_LINEARISATION_LIMIT_DEG,
    VARIANCE_CANCELLATION_FLOOR,
)
from rietx.model.profiles.fcj import NODES_PER_FWHM, SKIP_EXTENT_FWHM_RATIO
from rietx.optimize.qpa import BRINDLEY_MU_R_FENCE
from rietx.optimize.statistics import (
    EFFECTIVE_OBS_ALPHA,
    OBS_PER_PARAMETER_MIN,
    OBS_PER_PARAMETER_PREFERRED,
)
from rietx.report.layer2 import IMPURITY_SIGMA
from rietx.report.schemas import THRESHOLDS_VERSION, VALIDITY_RADIUS_FWHM
from rietx.schemas.indexing import MAX_RELATIVE_SIGMA_Q, MIN_LINES_PER_DOF
from rietx.schemas.suggest import SUGGEST_MIN_GAIN

project = "rietx manual"
author = "rietx developers"
release = _dist_version(DIST_NAME)
version = release

extensions = ["myst_parser", "sphinxcontrib.bibtex", "sphinxcontrib.mermaid"]

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

myst_enable_extensions = ["dollarmath", "amsmath", "substitution", "colon_fence"]
myst_substitutions = {
    # An angle's esd is withheld this close to 0°/180°; the raw value carries
    # fifteen digits of an arccos clamp, so it is formatted rather than typed —
    # still derived, and a retuned clamp still moves the printed number.
    "ANGLE_LINEARISATION_LIMIT_DEG": f"{ANGLE_LINEARISATION_LIMIT_DEG:.1e}",
    "BRINDLEY_MU_R_FENCE": BRINDLEY_MU_R_FENCE,
    "CYLINDER_MU_R_MAX": CYLINDER_MU_R_MAX,
    "EFFECTIVE_OBS_ALPHA": EFFECTIVE_OBS_ALPHA,
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
    "SUGGEST_MIN_GAIN": SUGGEST_MIN_GAIN,
    "SYMMETRY_ANGLE_TOL_DEG": SYMMETRY_ANGLE_TOL_DEG,
    "THRESHOLDS_VERSION": THRESHOLDS_VERSION,
    "VALIDITY_RADIUS_FWHM": VALIDITY_RADIUS_FWHM,
    "WINDOW_FWHM_MULT": WINDOW_FWHM_MULT,
    "release": release,
}

# Numbered sections and section-prefixed equation numbers ((3.2), not (2)).
numfig = True
math_numfig = True

exclude_patterns = ["_build"]

html_theme = "furo"
html_title = f"rietx {release} — manual"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
# Without this the pages emit no icon link at all, and a browser then falls
# back to the *origin* root — https://yue-here.github.io/favicon.ico, which
# belongs to the user Pages site this project's pages sit under, not to this
# project.  There is no way to ask for no favicon; the only fix is to name one.
html_favicon = "_static/favicon.svg"
