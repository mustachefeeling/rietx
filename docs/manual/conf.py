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
from rietx.model.profiles.fcj import NODES_PER_FWHM, SKIP_EXTENT_FWHM_RATIO
from rietx.optimize.qpa import BRINDLEY_MU_R_FENCE
from rietx.report.layer2 import IMPURITY_SIGMA
from rietx.report.schemas import THRESHOLDS_VERSION
from rietx.schemas.indexing import MAX_RELATIVE_SIGMA_Q, MIN_LINES_PER_DOF
from rietx.schemas.suggest import SUGGEST_MIN_GAIN

project = "rietx manual"
author = "rietx developers"
release = _dist_version(DIST_NAME)
version = release

extensions = ["myst_parser", "sphinxcontrib.bibtex"]

bibtex_bibfiles = ["references.bib"]
bibtex_default_style = "alpha"

myst_enable_extensions = ["dollarmath", "amsmath", "substitution", "colon_fence"]
myst_substitutions = {
    "BRINDLEY_MU_R_FENCE": BRINDLEY_MU_R_FENCE,
    "CYLINDER_MU_R_MAX": CYLINDER_MU_R_MAX,
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
    "WINDOW_FWHM_MULT": WINDOW_FWHM_MULT,
    "release": release,
}

# Numbered sections and section-prefixed equation numbers ((3.2), not (2)).
numfig = True
math_numfig = True

exclude_patterns = ["_build"]

html_theme = "furo"
html_title = f"rietx {release} — manual"
