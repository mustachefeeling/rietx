"""Spike: the manual's front page, one guide and one theory page under pydata-sphinx-theme."""
import inspect
import os
from pathlib import Path

from docutils import nodes

import rietx
from rietx.model.profiles import caglioti

project = "rietx"
# The version this build is for: "dev" for main, "1.9" for a release.
DOCS_VERSION = os.environ.get("DOCS_VERSION", "dev")
release = rietx.__version__ if DOCS_VERSION == "dev" else DOCS_VERSION
version = DOCS_VERSION

extensions = ["myst_parser", "sphinx_design", "sphinxcontrib.bibtex", "sphinx_llms_txt"]
myst_enable_extensions = ["dollarmath", "amsmath", "substitution", "colon_fence"]
myst_heading_anchors = 2
myst_substitutions = {"MIN_GAMMA_G2": f"{caglioti._MIN_GAMMA_G2:g}"}
bibtex_bibfiles = ["references.bib"]
numfig = True
math_numfig = True
exclude_patterns = ["_build"]

html_theme = "pydata_sphinx_theme"
html_title = "rietx"
html_baseurl = f"https://rietx.org/docs/{DOCS_VERSION}/"
html_theme_options = {
    "navbar_end": ["version-switcher", "theme-switcher", "navbar-icon-links"],
    "switcher": {
        # Absolute in production; the spike serves it from the site root.
        "json_url": "/docs/switcher.json",
        "version_match": DOCS_VERSION,
    },
    "show_version_warning_banner": True,
    "header_links_before_dropdown": 6,
    "navigation_with_keys": False,
}

llms_txt_summary = "rietx is a Python package for Rietveld, Le Bail and Pawley refinement."

from rietx._about import REPO_URL  # noqa: E402 — a brand token, spelled in _about only


def _source_role(name, rawtext, text, lineno, inliner, options=None, content=None):
    import importlib
    dotted = text.strip()
    module, _, attr = dotted.rpartition(".")
    obj = getattr(importlib.import_module(module), attr)
    path = Path(inspect.getsourcefile(obj)).resolve()
    rel = path.relative_to(Path(rietx.__file__).resolve().parents[2])
    line = inspect.getsourcelines(obj)[1]
    url = f"{REPO_URL}/blob/main/{rel}#L{line}"
    link = nodes.reference("", "", nodes.literal(text=dotted), refuri=url)
    return [nodes.emphasis(text="Source: "), link], []


def setup(app):
    app.add_role("source", _source_role)
    return {"parallel_read_safe": True}
