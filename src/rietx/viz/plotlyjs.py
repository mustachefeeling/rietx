"""plotly.js out of the installed package, for the one page still drawing with it.

``compare_app.py`` serves the library from the installed python package rather
than a CDN or a vendored copy. A page works air-gapped that way, and no build
step can leave a stale plotly in a committed bundle.

Three servers shared this once. ``watch/`` left plotly for the chart module in
WP-1461, and ``gui/server.py`` lost its route in WP-1462, when the structure
viewer took its own renderer. WP-1461's task 9 moves ``rietx compare`` too, and
this module goes with it.

The fallback is the **caller's**, because each page fails in its own way.
``compare_app`` replaces the whole body with an install line.
"""

from __future__ import annotations

#: What the route serves it as, named so a caller cannot decide plotly is
#: ``text/plain`` and spend an afternoon on it.
CONTENT_TYPE = "application/javascript; charset=utf-8"


def plotly_js(fallback: str) -> str:
    """The bundled plotly.js source, or ``fallback`` where plotly is absent.

    Read per request rather than cached, which is what the two copies this
    replaces did. The file is a few megabytes and a page fetches it once, so
    the read is not on any path that runs per stage.
    """
    try:
        from plotly.offline import get_plotlyjs
    except ImportError:  # pragma: no cover - exercised by the missing-dep path
        return fallback
    return get_plotlyjs()
