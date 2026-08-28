"""The GUI chapters' anti-divergence guards (WP-1017).

Part 2 is guarded by injected constants, Part 1 by name resolution
(`test_manual.py`, `test_manual_api.py`).  A GUI chapter is guarded by neither,
because its subject is routes and panels rather than importable names — and the
prose-drift problem is worse here than anywhere else in the manual: this WP's
own mailbox recorded "three sentences in this chapter are now wrong" eight
times over eight sessions, each time because a control moved.

So the two vocabularies a GUI chapter is *about* are partitioned the way
`tests/api_surface.py` partitions the call surface:

* every route in the server's table is named in a GUI chapter or excluded with
  a written reason — a new route fails this until one or the other is true;
* every tab in the live tab strip is named in a GUI chapter, the strip arriving
  as a committed corpus that vitest writes from the app's own `TABS`
  (`tests/data/gui/panels.json`, the `test_gui_fnmatch.py` mechanism with the
  authorities swapped: TypeScript owns the strip, python proves the manual
  states it).

What this does not measure is whether the sentence about a route is *true*.
The bar for that is review and the screenshots; this stops a route or a panel
from being silently forgotten.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rietx.gui.server import ROUTES, UPLOAD_ROUTES
from rietx.gui.session import RESERVED_ROUTES

REPO_ROOT = Path(__file__).resolve().parent.parent
USING_DIR = REPO_ROOT / "docs" / "manual" / "using"
GUI_PAGES = sorted(USING_DIR.glob("gui-*.md"))
PANELS_CORPUS = REPO_ROOT / "tests" / "data" / "gui" / "panels.json"

CODE_SPAN = re.compile(r"`([^`\n]+)`")
#: `GET /api/params` inside a code span.  The method is part of the name on
#: purpose: a GET and a PATCH on one path are two capabilities, and a chapter
#: that describes reading a thing has not thereby described writing it.
ROUTE_SPAN = re.compile(r"^(GET|POST|PUT|PATCH|DELETE)\s+(/\S+)$")

# A route a GUI chapter deliberately does not name, and why.  Same bar as
# `api_surface.EXCLUSIONS`: an empty reason is a shrug, and an entry that has
# stopped matching a live route has to fail rather than sit here.
ROUTE_EXCLUSIONS: dict[tuple[str, str], str] = {}


def _documented_routes() -> set[tuple[str, str]]:
    """Every `METHOD /path` a GUI chapter spells in a code span."""
    found: set[tuple[str, str]] = set()
    for page in GUI_PAGES:
        for span in CODE_SPAN.findall(page.read_text(encoding="utf-8")):
            match = ROUTE_SPAN.match(span.strip())
            if match:
                found.add((match.group(1), match.group(2)))
    return found


def _live_routes() -> set[tuple[str, str]]:
    return set(ROUTES) | set(UPLOAD_ROUTES) | set(RESERVED_ROUTES)


def test_the_gui_chapters_exist():
    """The partition below is vacuous if the pages moved or were renamed."""
    names = {page.name for page in GUI_PAGES}
    assert names == {"gui-quickstart.md", "gui-guide.md", "gui-power.md"}, (
        f"GUI chapters are not the three this suite guards: {sorted(names)}"
    )


def test_every_route_is_documented_or_excluded():
    """The wire surface is partitioned: named in a chapter, or excluded here.

    This is the guard the WP was written for.  A route is the one part of the
    GUI a reader cannot discover by looking at the app, so a new one that
    nobody documented is invisible until somebody needs it.
    """
    live = _live_routes()
    documented = _documented_routes() & live
    excluded = set(ROUTE_EXCLUSIONS)
    missing = sorted(live - documented - excluded)
    assert not missing, (
        f"{len(missing)} route(s) no GUI chapter names and no exclusion covers:\n"
        + "\n".join(f"  {m} {p}" for m, p in missing)
        + "\n\nDocument them in docs/manual/using/gui-power.md, or add an entry "
        "to ROUTE_EXCLUSIONS with a written reason."
    )
    both = sorted(documented & excluded)
    assert not both, f"route(s) both documented and excluded: {both}"


def test_route_exclusions_are_live_and_reasoned():
    """An exclusion for a route that no longer exists is a dead promise, and an
    empty reason is a shrug (`api_surface`'s rule, one vocabulary over)."""
    live = _live_routes()
    for route, reason in ROUTE_EXCLUSIONS.items():
        assert route in live, f"{route}: excluded but not a live route"
        assert len(reason.split()) >= 5, f"{route}: exclusion carries no real reason"


def test_no_chapter_names_a_route_that_does_not_exist():
    """The partition tightens from both sides.  A chapter naming a route the
    server does not serve is the WP-1037 bug in the other direction: the page
    is green, the reader gets a 404."""
    live = _live_routes()
    invented = sorted(_documented_routes() - live)
    assert not invented, (
        "GUI chapter names route(s) the server does not serve: "
        + ", ".join(f"{m} {p}" for m, p in invented)
    )


def test_every_panel_is_named_in_a_chapter():
    """Every tab in the live strip is named in a GUI chapter.

    The corpus is written by `gui/src/lib/tabs.test.ts` from the same `TABS`
    the app renders, so this cannot be satisfied by a stale list: a renamed tab
    rewrites the corpus, and the chapter that still uses the old word fails
    here.
    """
    assert PANELS_CORPUS.exists(), (
        f"{PANELS_CORPUS} missing — run `npm --prefix gui test` to write it"
    )
    panels = json.loads(PANELS_CORPUS.read_text(encoding="utf-8"))
    labels = [entry["label"] for entry in panels["tabs"]]
    assert labels, "the panel corpus carries no tabs"
    prose = "\n".join(page.read_text(encoding="utf-8") for page in GUI_PAGES)
    missing = [label for label in labels if not re.search(rf"\b{re.escape(label)}\b", prose)]
    assert not missing, (
        f"tab(s) the GUI chapters never name: {missing} — the strip is "
        f"{labels}"
    )
