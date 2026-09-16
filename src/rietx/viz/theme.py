"""The colour tokens the three browser surfaces share, and the theme (WP-1429).

The GUI, ``rietx watch`` and ``rietx compare`` are three pages a reader has
open at once, and before this module each answered "which colour is the
calculated curve" for itself: the GUI's dark red ``#e56a52``, the watcher's
orange ``#ff9d4d``, and ``compare_app.py``'s own list of ten hues.  One fit in
two colour schemes on two different darks is what a second authority looks
like on a screen.

**Why the values live in Python rather than in ``app.css``.**  The two Python
pages ship inside the wheel and the GUI workspace does not — ``gui/`` is a
build input, and what reaches an installed copy is the committed ``dist/``.  A
value the wheel has to serve therefore cannot live in ``gui/src``.  The
reverse direction is a build step, which this repo already does twice:
``help.py`` generates ``docs/manual/using/glossary.md`` in ``conf.py``, and
``gui/dist`` is committed and pinned stale-or-current by a test.  So this
module owns the values and emits the stylesheet, ``gui/src/tokens.css`` is
generated and committed, and ``tests/test_gui_palette.py`` holds the two equal
byte for byte — an edit on either side fails until the other follows.

**What is not here.**  Everything in ``app.css`` that is not a colour: the type
and space scales, the radii, the control registers.  And
:data:`~rietx.viz.plots.PALETTES`, which is the *figure* palette — chosen so a
figure sits on the manual's and the landing page's warm dark panel rather than
as a brighter card on it, and a figure for print has different needs from a
live page.  Changing it would regenerate every committed manual figure pair for
a consistency nobody asked about.

**The extra roles a page needs are derived, never declared.**  The watcher wants
a row hover, a selected row, a focus ring, four grip states and six state pills,
and none of them is a new token: they are ``color-mix`` over the nine chrome
tokens, the way ``app.css`` already writes its one hover.  A token the GUI never
reads would be a declared name with no writer (root CLAUDE.md), and this file is
the one place that temptation arrives.

Regenerate the stylesheet with::

    python -m rietx.viz.theme > gui/src/tokens.css
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .._about import STATE_DIR_ENV, STATE_DIR_NAME

#: The three-way choice (WP-1029).  "Follow the system" is a *choice* and not
#: the absence of one, so it is a member rather than a null: a user on a machine
#: that switches at dusk wants the app to switch with it, and a user who has
#: decided wants it to stay decided through that switch.
THEME_CHOICES = ("system", "light", "dark")

#: What a choice resolves to.  ``system`` resolves in the *browser*, through the
#: ``prefers-color-scheme`` block :func:`tokens_css` emits — no server can see
#: the machine the page is open on, and a server that guessed would be a second
#: answer to a question CSS already answers correctly.
THEMES = ("light", "dark")

#: The custom properties, in the order they are emitted.  Both themes declare
#: exactly this set; :func:`tokens_css` asserts it.
TOKENS: dict[str, dict[str, str]] = {
    "light": {
        "--fg": "#1b1b1b",
        "--bg": "#fbfbfa",
        "--panel": "#ffffff",
        "--line": "#dcdcd6",
        "--muted": "#6b6b66",
        "--accent": "#1f5fa8",
        "--ok": "#2e8b57",
        "--warn": "#b3541e",
        "--bad": "#c23b22",
        "--plot-obs": "#8a8a8a",
        "--plot-calc": "#c23b22",
        "--plot-bkg": "#6b7280",
        "--plot-diff": "#1f5fa8",
        "--plot-zero": "#88888888",
        "--plot-peak": "#8c257e",
        "--plot-peakfit": "#c158b0",
        "--plot-candidate": "#1a8f45",
        "--plot-mask": "#1b1b1b14",
        "--lane-l": "0.58",
        "--lane-c": "0.15",
    },
    "dark": {
        "--fg": "#e6e6e2",
        "--bg": "#151515",
        "--panel": "#1e1e1e",
        "--line": "#333333",
        "--muted": "#9a9a94",
        "--accent": "#7fb2ea",
        "--ok": "#6cc08b",
        "--warn": "#e0955c",
        "--bad": "#e8776a",
        "--plot-obs": "#909090",
        "--plot-calc": "#e56a52",
        "--plot-bkg": "#6e6e66",
        "--plot-diff": "#5897dd",
        "--plot-zero": "#88888888",
        "--plot-peak": "#e687d5",
        "--plot-peakfit": "#b156a2",
        "--plot-candidate": "#4ccf8a",
        "--plot-mask": "#e6e6e214",
        "--lane-l": "0.72",
        "--lane-c": "0.15",
    },
}

#: The reasoning, keyed by the token each note precedes.  It travels with the
#: values because a palette is a set of decisions and a bare hex is none of
#: them — the notes came out of ``app.css`` with WP-1429 and are emitted into
#: the generated stylesheet, which is a file people read.
NOTES: dict[str, str] = {
    "--plot-obs": """The pattern plot's curves (WP-1029) — the Rietveld
convention: recessive grey observations and background, red calculated, blue
difference.  The greys are *meant* to sit below the chroma floor a categorical
palette would demand; identity there is carried by the mark (points / dotted
line).  Each theme's set is validated against its own surface, not flipped.""",
    "--plot-peak": """The picked-peak layer (WP-1210).  It had no colours of
its own: the markers took `--accent` and the fitted curve `--bad`, and on the
light theme those *are* `--plot-diff` and `--plot-calc` to the last digit — two
curves the reader has to tell apart, drawn in one red.  One hue (334° in OKLab)
and two tones, because the layer is one thing; the markers take the stronger
contrast against the page in either theme and the fitted curve sits a step in,
dashed.  Every value here clears the phase palette's 0.13 OKLab floor against
every other plot colour, asserted in `tests/test_gui_palette.py` — measured, the
free hue space is this magenta and green alone: violet lands 0.10-0.12 from
`--plot-diff` and the alert tone `--warn` 0.053 from `--plot-calc`.""",
    "--plot-candidate": """An indexing candidate's predicted lines (WP-1211) —
the last of the free hue space the note above measured, spent rather than
borrowed.  It could not take the peak layer's: these two layers are up at the
same time, on the same tab, and the whole question the picture answers is which
of the picked lines a cell accounts for.  Nor the model's tick colour, which is
plotly's own per-phase cycle and is therefore not a value this file could
quote.""",
    "--plot-mask": """What is *not* being fitted (WP-1033): a wash,
deliberately not a sixth curve colour.  It marks absence from the residual
rather than a quantity, so it carries no hue anything else could be confused
with, and it is weak enough that the recessive grey observations stay readable
through it.""",
    "--lane-l": """The history graph's lanes (WP-1217).  Not a palette but half
of one: the hues are `gui/src/lib/history.ts`'s `LANE_HUES`, rotated there, and
what lives here is the lightness and chroma each theme reads a rail at — so a
lane's ink is `oklch(var(--lane-l) var(--lane-c) <hue>)` and no module learns a
colour.  The chroma is what the 72° spacing is measured against
(`tests/test_gui_palette.py`); the lightness is the panel's, not the plot's,
because a rail is drawn on `--panel` and has to read there.""",
}

#: The route both Python pages link, and what it is served as — one spelling,
#: because two servers linking two different paths to one stylesheet is the
#: duplication this module exists to remove.  ``viz/plotlyjs.py`` is the
#: precedent for serving an asset out of the installed package; the difference
#: is that this one is *rendered*, the GUI's committed copy being the generated
#: side rather than the source.
CSS_ROUTE = "/tokens.css"
CSS_CONTENT_TYPE = "text/css; charset=utf-8"

#: What the emitted stylesheet opens with.  It names the generator, because the
#: one thing a reader of a generated file needs is where to make the edit.
_HEADER = """\
/* Generated by `python -m rietx.viz.theme` — edit `src/rietx/viz/theme.py`.

   The colour tokens of all three browser surfaces this package ships: this
   app, `rietx watch` and `rietx compare` (WP-1429).  The values live in Python
   because the two Python pages ship inside the wheel and this workspace does
   not, and `tests/test_gui_palette.py` fails while this file and the emitter
   disagree.

   `app.css` keeps everything that is not a colour — the type and space scales,
   the radii and the nine control registers — and imports this file.

   The dark palette is declared twice, on purpose: the `@media` block is what
   paints correctly before an app has booted and while nobody has chosen, and
   the attribute block is what an explicit choice sets — which has to beat the
   system in *both* directions, and one media query cannot say that. */
"""


def _declarations(theme: str, *, notes: bool) -> list[str]:
    """One theme's custom properties, as indented CSS lines."""
    out: list[str] = []
    for token, value in TOKENS[theme].items():
        if notes and token in NOTES:
            body = " ".join(NOTES[token].split())
            out.append(_wrap_comment(body))
        out.append(f"  {token}: {value};")
    return out


def _wrap_comment(text: str, width: int = 76) -> str:
    """A CSS comment wrapped at `width`, indented two spaces and continued four."""
    words, lines, line = text.split(), [], "  /* "
    for word in words:
        if len(line) + len(word) + 1 > width and line.strip() not in ("/*",):
            lines.append(line.rstrip())
            line = "     " + word + " "
        else:
            line += word + " "
    lines.append(line.rstrip() + " */")
    return "\n".join(lines)


def tokens_css() -> str:
    """The stylesheet every surface links — three blocks and a header.

    ``color-scheme`` travels with the theme and is not decoration: it is what
    makes the native controls a page does *not* style — ``select`` popups,
    checkboxes, scrollbars, the caret — follow an explicit choice.  Without it,
    choosing light on a dark system leaves a page of dark dropdowns.  The GUI
    sets it inline as well (``lib/theme.ts``), which wins and agrees; the two
    Python pages have no such code and take it from here.
    """
    if set(TOKENS["light"]) != set(TOKENS["dark"]):
        raise ValueError("the two themes declare different tokens: "
                         f"{sorted(set(TOKENS['light']) ^ set(TOKENS['dark']))}")
    light = "\n".join(_declarations("light", notes=True))
    dark = "\n".join(_declarations("dark", notes=False))
    dark_indented = "\n".join("  " + line if line.strip() else line
                              for line in dark.splitlines())
    return (
        f"{_HEADER}"
        f":root {{\n  color-scheme: light dark;\n{light}\n}}\n"
        f"\n@media (prefers-color-scheme: dark) {{\n"
        f"  :root:not([data-theme=\"light\"]) {{\n{dark_indented}\n  }}\n}}\n"
        f"\n:root[data-theme=\"light\"] {{\n  color-scheme: light;\n}}\n"
        f"\n:root[data-theme=\"dark\"] {{\n  color-scheme: dark;\n{dark}\n}}\n"
    )


def state_dir(override: str | Path | None = None) -> Path:
    """Where the person's own settings live — the recent list and the theme.

    ``$HOME/.rietx``, moved by ``$RIETX_STATE_DIR``.  **Not** the working
    directory's ``.rietx/``, which is a fit's telemetry and which no env var
    moves (``_about.py`` holds that warning; the two are the same literal and
    no test can catch them being confused).

    One expression, called by :class:`~rietx.gui.session.Session` and by the two
    Python servers, because a theme read from a different directory than the one
    the GUI wrote to is a bug that looks like the choice not sticking.
    """
    if override is not None:
        return Path(override)
    return Path(os.environ.get(STATE_DIR_ENV) or Path.home() / STATE_DIR_NAME)


def theme_choice(override: str | Path | None = None) -> str:
    """The theme the person chose, from ``settings.json``; ``system`` by default.

    Read-only, and that is the rule rather than an omission: the GUI writes the
    choice (``session.settings_patch``) and the two Python pages read it.  One
    writer per fact.  Anything unreadable, missing or hand-mangled is
    ``"system"``, never an error — the same grammar
    :meth:`~rietx.gui.session.Session.settings` uses, and for the same reason:
    no setting here is worth refusing to start over.
    """
    try:
        raw = json.loads((state_dir(override) / "settings.json")
                         .read_text(encoding="utf-8"))
        value = raw["ui"]["theme"]
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        # `RuntimeError` is `Path.home()` on a machine with no home to find:
        # a page draws in the default theme there, rather than not at all
        return "system"
    return value if value in THEME_CHOICES else "system"


if __name__ == "__main__":  # pragma: no cover - the regeneration command
    print(tokens_css(), end="")
