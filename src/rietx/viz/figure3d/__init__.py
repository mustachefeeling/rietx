"""A structure figure drawn in Python, without a browser (WP-1470).

:func:`render_structure` draws one phase as the GUI's structure viewer draws
it, to an RGBA array or a PNG, with no browser, display or new dependency.
:func:`keep` and the masks :func:`select`, :func:`plane`, :func:`sphere` and
:func:`component` cut the geometry first, and :func:`recolour` paints part of
it (WP-1501).

Provisional by declaration: its look and its arguments follow the GUI's
structure viewer, which is still changing (WP-1468).
"""

from .cut import component, keep, plane, recolour, select, sphere
from .render import StructureFigure, render_structure

__all__ = ["StructureFigure", "component", "keep", "plane", "recolour",
           "render_structure", "select", "sphere"]
