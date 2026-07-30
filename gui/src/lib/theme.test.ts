// @vitest-environment jsdom
/** The theme choice (WP-1029) — three-way, and the third one is not "off". */
import { describe, expect, it } from "vitest";

import { applyTheme, readChoice, resolveTheme } from "./theme";

describe("resolving a choice", () => {
  it("follows the system only when asked to", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });

  it("keeps an explicit choice through a system change", () => {
    // the reason this is three-way and not a toggle: a user who has decided
    // must stay decided when the machine switches at dusk
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
});

describe("reading the stored key", () => {
  it("treats anything it does not recognise as 'system'", () => {
    expect(readChoice("dark")).toBe("dark");
    expect(readChoice(undefined)).toBe("system");
    expect(readChoice("solarized")).toBe("system");
    expect(readChoice(1)).toBe("system");
  });
});

describe("stamping the resolved theme", () => {
  it("sets both the attribute and color-scheme", () => {
    const root = document.createElement("html");
    applyTheme("dark", root);
    expect(root.dataset.theme).toBe("dark");
    // not decoration: `color-scheme` is what makes the controls the app does
    // *not* style — select popups, checkboxes, scrollbars — follow the choice
    expect(root.style.colorScheme).toBe("dark");

    applyTheme("light", root);
    expect(root.dataset.theme).toBe("light");
    expect(root.style.colorScheme).toBe("light");
  });
});
