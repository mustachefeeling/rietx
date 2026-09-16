"""WP-1210 — the GUI's colours, held apart in OKLab.

Since WP-1429 the values are :data:`rietx.viz.theme.TOKENS` — Python, because
``rietx watch`` and ``rietx compare`` ship inside the wheel and the GUI
workspace does not, and the three pages a reader has open at once must not
answer "which colour is the calculated curve" three ways.  ``gui/src/tokens.css``
is generated from them and committed, and the byte-equality test below holds the
two together, so an edit on either side fails until the other follows.  Every
other assertion here reads the module, which is the authority.

The distance that decides whether two of them are one colour is
:func:`rietx.gui.structure3d._oklab_distance`, which the phase palette already
uses.  So the assertion is here, in Python, rather than in ``plot.test.ts``: a
TypeScript port would be a second answer to "how far apart are these two
colours", and this repo has paid for that shape before.  What the vitest side
asserts is the *plumbing* — that ``curveColors`` reads each property and falls
back per property.

Why it is worth asserting at all: before this WP the peak layer had no colours
of its own, and the two it borrowed were `--plot-diff` and `--plot-calc`
**exactly** on the light theme.  Nothing failed; the picture simply drew the
picked-peak fit and the model in one red.

WP-1217 added the history graph's lanes at the bottom, which are the same
question about a different set: the rail is where two marks of one shape and
one weight mean different things, so following a line is the whole job.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from rietx.gui.structure3d import MIN_SEPARATION, _oklab, _oklab_distance, _oklab_hex
from rietx.viz.theme import TOKENS, tokens_css

ROOT = Path(__file__).resolve().parent.parent
TOKENS_CSS = ROOT / "gui" / "src" / "tokens.css"
PLOT_TS = ROOT / "gui" / "src" / "lib" / "plot.ts"

#: The colours a *curve* is drawn in — the set a reader has to tell apart.
#:
#: `--plot-zero` and `--plot-mask` are deliberately absent: both are chrome with
#: an alpha channel (a zero line, a wash over what is not fitted), and neither
#: carries a quantity.  The greys are here and are deliberately *close* — see
#: the recessive pair below.
CURVES = ("--plot-obs", "--plot-calc", "--plot-bkg", "--plot-diff",
          "--plot-peak", "--plot-peakfit", "--plot-candidate")

#: What a *layer's* colour must clear: every other curve, plus the two inks a
#: mark can otherwise be mistaken for.
NEIGHBOURS = (*CURVES, "--muted", "--fg")

#: The colours a layer drawn over the data owns — the peak layer's pair
#: (WP-1210) and the candidate overlay's one (WP-1211).  They are held to more
#: than the curve floor because a layer is drawn *on top of* the curves rather
#: than beside them: separation from the page as well, and from `--accent` and
#: `--bad`, which is the specific mistake WP-1210 was written to undo.
LAYERS = ("--plot-peak", "--plot-peakfit", "--plot-candidate")

#: The recessive set, exempt from the floor **against each other only**.
#:
#: `viz/theme.py` says why: observations and background are meant to sit below the
#: chroma a categorical palette would demand, and their identity is carried by
#: the mark — points against a dotted line.  Measured, obs/bkg is 0.086 on the
#: light theme, so a blanket all-pairs assertion would be asserting the opposite
#: of the design.
#:
#: `--muted` belongs here for a second reason worth stating, because a reviewer
#: has already flagged it once: it draws the **masked measured points**, which
#: are the same data as `--plot-obs` and are meant to read that way (WP-1033) —
#: 0.032 apart on the dark theme.  What may *not* borrow it is a mark that is
#: not the data: WP-1210 briefly drew unusable peak markers in it, sitting on
#: top of the very points it matched, and they now take the peak layer's own
#: colour with the hollow ring carrying the state.
RECESSIVE = frozenset({"--plot-obs", "--plot-bkg", "--muted"})

#: The two pairs the shipped palette misses the floor on, named rather than
#: exempted quietly.
#:
#: Both are a recessive grey against the difference curve, and both were chosen
#: in WP-1029 against their own surface: light `--plot-bkg`/`--plot-diff` is
#: **0.129** and dark `--plot-obs`/`--plot-diff` is **0.124**, against a 0.13
#: floor.  Retuning a shipped curve colour is not WP-1210's — the layer that had
#: no colours at all is — but they may not get *worse* either, which is what
#: :data:`GRANDFATHERED_FLOOR` holds them to.  A third such pair fails.
GRANDFATHERED = {
    "light": {("--plot-bkg", "--plot-diff")},
    "dark": {("--plot-diff", "--plot-obs")},
}
GRANDFATHERED_FLOOR = 0.12


def _block(name: str, css: str) -> dict[str, str]:
    """The custom properties declared in one block of the emitted stylesheet."""
    start = css.index(name)
    depth, end = 0, start
    for index in range(start, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    body = css[start:end]
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", body))


@pytest.fixture(scope="module")
def themes() -> dict[str, dict[str, str]]:
    """The authority itself — `viz/theme.py`, not a file parsed back."""
    return {name: TOKENS[name] for name in ("light", "dark")}


def test_the_committed_stylesheet_is_the_emitters_output():
    """The seam WP-1429 exists to close, and the only test that reads the file.

    `gui/src/tokens.css` is generated and committed for the same reason
    `gui/dist` is: the GUI's build cannot import Python, and the wheel cannot
    ship the GUI's sources.  A generated file nobody regenerates is a second
    authority wearing a comment that says it is not one, so this is what keeps
    the edit where the header says it goes.
    """
    assert TOKENS_CSS.read_text(encoding="utf-8") == tokens_css(), (
        "gui/src/tokens.css is stale - run "
        "`python -m rietx.viz.theme > gui/src/tokens.css` and rebuild the dist")


@pytest.mark.parametrize("name", ["light", "dark"])
def test_every_block_of_the_stylesheet_carries_the_whole_palette(name):
    """The emitter's own structure: three blocks, and the dark one twice.

    The dark palette is declared twice on purpose — the `@media` block paints
    before an app has booted, the attribute block is what an explicit choice
    sets — and before WP-1429 the two were free to drift, which is why
    `app.css` was parsed here at all.  They now come from one dict, so what is
    left to check is that the *emitter* puts every token in every block: a
    comment wrapper or an indent bug that swallowed a declaration would show as
    a missing curve rather than a wrong one.
    """
    css = tokens_css()
    blocks = [":root {"] if name == "light" else [
        ':root:not([data-theme="light"])', ':root[data-theme="dark"]']
    for block in blocks:
        assert _block(block, css) == TOKENS[name], f"{block} is short"


def test_the_typescript_fallbacks_are_the_light_tokens():
    """`curveColors` reads each property and falls back per property (plot.ts).

    The fallbacks are for a page with no stylesheet — jsdom — so they are a
    copy of the light palette in a second language, which is the shape WP-1429
    removes everywhere it reaches.  It does not reach here: a TypeScript
    literal is what a missing property falls back *to*, and generating a `.ts`
    twin of `tokens.css` would be a second generated file for ten values.  So
    the copy stays and is pinned instead.
    """
    source = PLOT_TS.read_text(encoding="utf-8")
    fallbacks = dict(re.findall(r'pick\("(--[\w-]+)",\s*"(#[0-9a-fA-F]{6,8})"\)',
                                source))
    assert fallbacks, "no `pick(token, fallback)` calls found in plot.ts"
    light = TOKENS["light"]
    assert fallbacks == {key: light[key] for key in fallbacks}


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_layer_has_its_own_colours_in_both_themes(themes, theme):
    """Not `--accent`/`--bad`, which are chrome and collide with two curves."""
    palette = themes[theme]
    for token in LAYERS:
        assert token in palette, f"{token} is missing from the {theme} theme"
        for chrome in ("--accent", "--bad"):
            assert palette[token] != palette[chrome]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_each_layer_colour_clears_the_floor_against_every_neighbour(themes, theme):
    """The phase palette's floor, applied to the plot's own set.

    Both directions matter and one of them is the reason this test exists: the
    fitted curve has to be separable from `--plot-calc` (the report), and the
    markers from everything a marker sits on.  The candidate overlay joins it
    for a sharper version of the same reason — it is drawn over the peak
    markers, on the tab that owns both, to answer which picked lines a cell
    accounts for.
    """
    palette = themes[theme]
    for token in LAYERS:
        mine = _oklab(palette[token])
        for other in NEIGHBOURS:
            if other == token:
                continue
            gap = _oklab_distance(mine, _oklab(palette[other]))
            assert gap >= MIN_SEPARATION, (
                f"{theme}: {token} {palette[token]} is {gap:.3f} from "
                f"{other} {palette[other]} — under the {MIN_SEPARATION} floor")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_chromatic_curve_pair_clears_it_too(themes, theme):
    """The floor holds across the whole curve set, the recessive greys apart.

    Which is the assertion that would have failed the day the peak layer was
    written: `--accent` against `--plot-diff` was 0.000.
    """
    palette = themes[theme]
    known = GRANDFATHERED[theme]
    for one in CURVES:
        for two in CURVES:
            if one >= two or {one, two} <= RECESSIVE:
                continue
            gap = _oklab_distance(_oklab(palette[one]), _oklab(palette[two]))
            floor = GRANDFATHERED_FLOOR if (one, two) in known else MIN_SEPARATION
            assert gap >= floor, (
                f"{theme}: {one} and {two} are {gap:.3f} apart")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_grandfathered_pairs_are_still_the_only_ones(themes, theme):
    """An exemption that outlives its reason is a lie about the palette."""
    palette = themes[theme]
    under = {
        (one, two)
        for one in CURVES for two in CURVES
        if one < two and not {one, two} <= RECESSIVE
        and _oklab_distance(_oklab(palette[one]), _oklab(palette[two])) < MIN_SEPARATION
    }
    assert under == GRANDFATHERED[theme], (
        f"{theme}: the pairs under the floor have changed — {sorted(under)}")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_layer_colour_reads_against_its_own_page(themes, theme):
    """A colour that clears every curve can still be invisible on the surface."""
    palette = themes[theme]
    page = _oklab(palette["--bg"])
    for token in LAYERS:
        gap = _oklab_distance(_oklab(palette[token]), page)
        assert gap >= 0.30, f"{theme}: {token} is {gap:.3f} from the page"


# --- the history graph's lanes (WP-1217) -----------------------------------
#
# Half a palette in each place, on purpose: `lib/history.ts` owns the hue
# *rotation* and `viz/theme.py` owns the lightness and chroma a rail is read
# at, so a lane's ink is `oklch(var(--lane-l) var(--lane-c) <hue>)` and neither
# file holds a colour.  What decides whether the rotation is fine enough is a
# distance, and this is the file that has one.

HISTORY_TS = ROOT / "gui" / "src" / "lib" / "history.ts"


def _lanes(name: str) -> list[tuple[float, float, float]]:
    """The lane inks of one theme, as OKLab — through sRGB, as a screen shows them."""
    lightness = float(TOKENS[name]["--lane-l"])
    chroma = float(TOKENS[name]["--lane-c"])
    source = HISTORY_TS.read_text(encoding="utf-8")
    hues = [float(h) for h in re.search(
        r"LANE_HUES\s*=\s*\[([^\]]+)\]", source).group(1).split(",")]
    return [_oklab(_oklab_hex((lightness,
                               chroma * math.cos(math.radians(hue)),
                               chroma * math.sin(math.radians(hue)))))
            for hue in hues]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_pair_of_lanes_clears_the_floor(themes, theme):
    """Two lanes 72° apart at this chroma; a sixth lane at 60° would not.

    The rail is the one place in this app where two marks of the same shape and
    the same weight mean different things, so following a line across ten rows
    is the whole job and the hues have to be nameable apart.  Hue-only at
    constant L and C puts a pair 2·C·sin(Δh/2) apart before the sRGB gamut has
    its say, which is why the measurement goes through the hex a browser will
    actually paint.
    """
    lanes = _lanes(theme)
    assert len(lanes) == 5
    for i, one in enumerate(lanes):
        for two in lanes[i + 1:]:
            gap = _oklab_distance(one, two)
            assert gap >= MIN_SEPARATION, f"{theme}: two lanes are {gap:.3f} apart"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_lane_reads_against_the_panel_it_is_drawn_on(themes, theme):
    """`--panel`, not `--bg`: the graph sits inside a panel's surface."""
    surface = _oklab(themes[theme]["--panel"])
    for index, lane in enumerate(_lanes(theme)):
        gap = _oklab_distance(lane, surface)
        assert gap >= 0.30, f"{theme}: lane {index} is {gap:.3f} from the panel"
