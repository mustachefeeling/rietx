"""plotly.js out of the installed package — one answer, three servers.

``gui/server.py``, ``compare_app.py`` and ``watch/`` each serve a page that
draws with plotly, and each serves the library itself from the installed python
package rather than a CDN or a vendored copy in a dist. That is deliberate
twice over: a page works air-gapped, and no build step can leave a stale
plotly in a committed bundle.

The three of them had two copies of this between them and were about to have
three, which is the point at which "written once and consumed everywhere"
starts to cost something. What is *not* consolidated is the rest: the
``_send``/``_json`` helpers, the route tables and the handler factories stay
duplicated, a choice ``gui/CLAUDE.md`` records. This is one function.

The fallback is the **caller's**, because the three pages fail differently and
nothing here can guess which. The GUI sets a window flag its dist checks and
logs to the console; ``compare_app`` replaces the whole body with an install
line; ``watch`` writes its note into the plot pane it would have drawn in. A
default here would be a fourth convention, invented by the module least able to
say what the page needs.
"""

from __future__ import annotations

#: What the routes serve it as. Shared so a fourth caller cannot decide plotly
#: is ``text/plain`` and spend an afternoon on it.
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
