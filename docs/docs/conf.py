# Sphinx configuration for the new manual (WP-1978): six tabs under
# pydata-sphinx-theme, built beside docs/manual/ until each old chapter has
# been mined and retired (WP-1986).  WP-1975 § I chose the toolchain.
#
# What this tree shares with the old one (the fenced constants, the citation
# style, the diagram theme and the `{source}` role) is in
# `docs/sphinx_shared.py`, which both conf.py files import.  Versions, the
# switcher and deployment are WP-1979's; the markdown twin is WP-1980's.

import sys as _sys
from importlib.metadata import version as _dist_version
from pathlib import Path as _Path

from rietx._about import DIST_NAME, REPO_URL

_sys.path.append(str(_Path(__file__).resolve().parent.parent))
import reference_pages as _reference  # noqa: E402
import sphinx_shared as _shared  # noqa: E402

project = DIST_NAME
author = "rietx developers"
release = _dist_version(DIST_NAME)
version = release

# `myst_nb` in place of `myst_parser`: it runs myst-parser underneath, so every
# `myst_*` setting below still applies, and it adds `.ipynb` as a source for
# the Start tab's notebooks.  They render with their committed outputs, for
# the reason the old tree's conf.py gives.
extensions = [
    "myst_nb",
    "sphinx_design",
    "sphinxcontrib.bibtex",
    "sphinxcontrib.mermaid",
]
nb_execution_mode = "off"

mermaid_light_theme = _shared.MERMAID_LIGHT_THEME
mermaid_dark_theme = _shared.MERMAID_DARK_THEME
mermaid_init_config = _shared.MERMAID_INIT_CONFIG

bibtex_bibfiles = [str(_shared.BIBFILE)]
bibtex_default_style = _shared.BIBTEX_DEFAULT_STYLE
bibtex_reference_style = _shared.BIBTEX_REFERENCE_STYLE

myst_enable_extensions = _shared.MYST_EXTENSIONS
myst_substitutions = {**_shared.MYST_SUBSTITUTIONS, "release": release}
# A markdown link to `page.md#a-heading` resolves, so a Concepts or Guides page
# can point at the Theory section behind a claim (tests/test_manual.py).
myst_heading_anchors = 3

# Numbered sections and section-prefixed equation numbers ((3.2), not (2)).
numfig = True
math_numfig = True

# `_generated/` holds the Reference tab's bodies, written below from the code
# that owns each fact (WP-1981).  A committed page `{include}`s each one, so
# Sphinx must not read them as documents of their own.
exclude_patterns = ["_build", "_generated"]

_reference.write_bodies()

html_theme = "pydata_sphinx_theme"
html_title = DIST_NAME
# The old tree's mark.  Without a favicon a browser falls back to the origin
# root, which belongs to the user Pages site this project sits under.
html_favicon = "../manual/_static/favicon.svg"
html_theme_options = {
    # Six tabs, so none folds into a "More" dropdown.
    "header_links_before_dropdown": 6,
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
    "icon_links": [
        {"name": "GitHub", "url": REPO_URL, "icon": "fa-brands fa-github"},
    ],
    # The theme's arrow-key page turning takes the keys a reader scrolls with.
    "navigation_with_keys": False,
}


def setup(app):
    app.add_role("source", _shared.source_role)
    return {"version": release, "parallel_read_safe": True, "parallel_write_safe": True}
