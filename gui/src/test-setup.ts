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
