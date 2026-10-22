// The theme control (`_templates/rietx-theme.html`): the landing page's two states, on
// pydata-sphinx-theme's engine (WP-2021).
//
// pydata keeps the choice in localStorage `mode` (auto, light or dark) and `theme` (the one
// in force), mirrors both to `html[data-mode]` and `html[data-theme]`, and resolves `auto`
// against the system.  A first visit stores nothing, so the page follows the system as the
// landing page does.  A click pins the other theme by writing all four, the same keys the
// landing page writes, so one choice holds across the site.  pydata exposes no setter, so
// this writes them itself.  The header and the narrow-screen drawer each draw a button, so
// every one is labelled, and the label follows `data-theme` whoever changed it.
(() => {
  "use strict";
  const root = document.documentElement;
  const dark = () => root.dataset.theme === "dark";

  function label() {
    const to = `Switch to the ${dark() ? "light" : "dark"} theme`;
    for (const button of document.querySelectorAll(".rietx-theme")) {
      button.setAttribute("aria-label", to);
      button.setAttribute("title", to);
    }
  }

  function pin(theme) {
    root.dataset.mode = theme;
    root.dataset.theme = theme;
    try {
      localStorage.setItem("mode", theme);
      localStorage.setItem("theme", theme);
    } catch (e) {}
  }

  document.addEventListener("click", (event) => {
    if (event.target.closest(".rietx-theme")) pin(dark() ? "light" : "dark");
  });
  new MutationObserver(label).observe(root, { attributes: true, attributeFilter: ["data-theme"] });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", label);
  else label();
})();
