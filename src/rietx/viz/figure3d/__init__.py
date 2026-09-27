"""A structure figure drawn in Python, without a browser (WP-1470).

:func:`render_structure` draws one phase as the GUI's structure viewer draws
it, to an RGBA array or a PNG, with no browser, display or new dependency.

Provisional by declaration: its look and its arguments follow the GUI's
structure viewer, which is still changing (WP-1468).
"""

from .render import StructureFigure, render_structure

__all__ = ["StructureFigure", "render_structure"]
