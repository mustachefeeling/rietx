import { vi } from "vitest";

/** Browser APIs jsdom does not implement, stubbed for the component tests.
 *
 * Only APIs that are *baseline everywhere a browser runs* belong here — a stub
 * for something a real browser might lack would make a test pass on a page that
 * cannot work.  `ResizeObserver` qualifies: Svelte compiles `bind:clientHeight`
 * into one, and the parameter table measures its viewport that way because a
 * virtualized list has to know how many rows fit.  Without this, mounting the
 * shell throws `ResizeObserver is not defined` — a jsdom gap wearing the costume
 * of an application bug.
 *
 * It reports nothing: jsdom has no layout, so every measurement is 0 anyway, and
 * `windowSlice`'s overscan is what keeps an unmeasured viewport rendering rows
 * rather than an empty list.
 */
class NoopResizeObserver implements ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = NoopResizeObserver as unknown as typeof ResizeObserver;
}

/**
 * uPlot, for the same class of reason (WP-1461): jsdom has no canvas, and
 * uPlot's constructor draws with its context at once, so the pattern panel
 * could not mount. `test-uplot.ts` keeps uPlot's state, fires the chart
 * module's hooks and records what each pane was asked to paint, which is what
 * `App.test.ts` asserts the pattern panel on. What a browser then paints is
 * `tests/test_gui_browser.py`'s.
 */
vi.mock("uplot", async () => ({ default: (await import("./test-uplot")).StubPlot }));

/**
 * The structure viewer's WebGL2 renderer, for the same reason (WP-1462): jsdom
 * has no WebGL, so `test-gl3d.ts` records each scene and view the viewer hands
 * over, which is what `App.test.ts` asserts the viewer on.
 */
vi.mock("./lib/gl3d", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./lib/gl3d")>()),
  createRenderer: (await import("./test-gl3d")).createRenderer,
}));

/**
 * A plotly stand-in: jsdom does not fetch `<script src>`, so `lib/plotly.ts`'s
 * runtime loader — which injects `/plotly.js` served out of the installed
 * Python package rather than vendoring 4.8 MB into the committed dist
 * (WP-1010) — never resolves under test, and the Series panel and the
 * structure viewer never reach their draws. The stub records nothing and draws
 * nothing; a test that asserts traces replaces it with a recording one.
 */
if (typeof (globalThis as any).Plotly === "undefined") {
  (globalThis as any).Plotly = {
    react: async () => {},
    // `restyle` is the hover link's whole mechanism (WP-1032): a mouse move
    // moves one two-coordinate trace rather than repainting the pattern
    restyle: async () => {},
    purge: () => {},
  };
}
