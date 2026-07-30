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
 * A plotly stand-in, for the same class of reason: jsdom does not fetch
 * `<script src>`, so `Plot.svelte`'s runtime loader — which injects
 * `/plotly.js` served out of the installed Python package rather than vendoring
 * 4.8 MB into the committed dist (WP-1010) — never resolves under test, and the
 * component never reaches the line that fetches its window.
 *
 * That is not a cosmetic gap: the plot's *data* comes from
 * `/api/result/window`, so without this nothing about zooming can be asserted at
 * all — including WP-1012's report-region click-zoom, whose whole claim is that a
 * region refetches its window server-side rather than stretching the overview.
 * The stub therefore records nothing and draws nothing; the assertions are about
 * the requests the component makes.
 */
if (typeof (globalThis as any).Plotly === "undefined") {
  (globalThis as any).Plotly = {
    react: async () => {},
    purge: () => {},
  };
}
