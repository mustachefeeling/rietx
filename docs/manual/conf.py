# Sphinx configuration for the pxrd-refine theory manual.
#
# Anti-divergence rule (WP-0604): a threshold or fenced constant is never
# typed into a chapter.  It is imported here from the live package and exposed
# as a MyST substitution ({{ BRINDLEY_MU_R_FENCE }} etc.), so a renamed or
# retuned constant fails the -W build instead of leaving a stale number in
# print.  Prose derivations stay in the module docstrings; chapters carry the
# numbered equations and point at their source symbols.

from importlib.metadata import version as _dist_version

from pxrdref.crystallography.dispersion import NEAR_EDGE_EV
from pxrdref.indexing.ambiguity import MAX_AMBIGUITY_INDEX
from pxrdref.indexing.reduce import NIGGLI_EPS_RELATIVE
from pxrdref.model.absorption import CYLINDER_MU_R_MAX
from pxrdref.model.forward import PAWLEY_OVERLAP_FWHM_FRAC, WINDOW_FWHM_MULT
from pxrdref.model.profiles.fcj import NODES_PER_FWHM, SKIP_EXTENT_FWHM_RATIO
from pxrdref.optimize.qpa import BRINDLEY_MU_R_FENCE
from pxrdref.report.layer2 import IMPURITY_SIGMA
from pxrdref.report.schemas import THRESHOLDS_VERSION
from pxrdref.schemas.indexing import MAX_RELATIVE_SIGMA_Q, MIN_LINES_PER_DOF

project = "pxrd-refine theory manual"
author = "pxrd-refine developers"
release = _dist_version("pxrd-refine")
version = release

extensions = ["myst_parser", "sphinxcontrib.bibtex"]

bibtex_bibfiles = ["references.bib"]
bibtex_default_style = "alpha"

myst_enable_extensions = ["dollarmath", "amsmath", "substitution", "colon_fence"]
myst_substitutions = {
    "BRINDLEY_MU_R_FENCE": BRINDLEY_MU_R_FENCE,
    "CYLINDER_MU_R_MAX": CYLINDER_MU_R_MAX,
    "IMPURITY_SIGMA": IMPURITY_SIGMA,
    "MAX_AMBIGUITY_INDEX": MAX_AMBIGUITY_INDEX,
    "MAX_RELATIVE_SIGMA_Q": MAX_RELATIVE_SIGMA_Q,
    "MIN_LINES_PER_DOF": MIN_LINES_PER_DOF,
    "NEAR_EDGE_EV": NEAR_EDGE_EV,
    "NIGGLI_EPS_RELATIVE": NIGGLI_EPS_RELATIVE,
    "NODES_PER_FWHM": NODES_PER_FWHM,
    "PAWLEY_OVERLAP_FWHM_FRAC": PAWLEY_OVERLAP_FWHM_FRAC,
    "SKIP_EXTENT_FWHM_RATIO": SKIP_EXTENT_FWHM_RATIO,
    "THRESHOLDS_VERSION": THRESHOLDS_VERSION,
    "WINDOW_FWHM_MULT": WINDOW_FWHM_MULT,
    "release": release,
}

# Numbered sections and section-prefixed equation numbers ((3.2), not (2)).
numfig = True
math_numfig = True

exclude_patterns = ["_build"]

html_theme = "furo"
html_title = f"pxrd-refine {release} — theory manual"
