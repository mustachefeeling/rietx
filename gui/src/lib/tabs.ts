/** The panel strip, as data (WP-1017).
 *
 * Lifted out of `App.svelte` for the reason `controls.ts` was: a vocabulary the
 * app renders *and* something else is held to should be one object, not a const
 * inside a component. Here the something else is the manual —
 * `tabs.test.ts` writes `tests/data/gui/panels.json` from this array and
 * `tests/test_gui_manual.py` fails when a GUI chapter does not name a tab, so a
 * renamed panel breaks the docs build rather than the reader's trust.
 *
 * The nine panels, and the reasons the strip is what it is.
 *
 * Model and Text joined the strip in WP-1034 — an edit and the fit it changes
 * are now one glance, which is what every other panel already had. WP-1013 and
 * WP-1014 had made both of them modes over the whole window on grounds that
 * were sound and are now **measured**: the atom table needs 472 px and the
 * `.rxt` document's editable columns 546 px, against a sidebar that clamps at
 * 560 and drags to 72 % of the window. So they fit at the ceiling, they do not
 * fit at the 340 px floor, and the full-window layout is what covers the
 * difference.
 *
 * `Series` is the ninth (WP-1016) and its label is one word for the reason
 * WP-1034 measured: eight already fill a 455 px strip, so a ninth costs a
 * second row at a narrow column and nothing else — the strip wraps rather than
 * shortening a label. It needs no mode of its own either: the header's
 * `Split | Full` already gives any panel the whole window.
 */
export const TABS = [
  { id: "params", label: "Parameters" },
  { id: "plan", label: "Plan" },
  { id: "peaks", label: "Peaks" },
  { id: "model", label: "Model" },
  { id: "text", label: "Text" },
  { id: "series", label: "Series" },
  { id: "report", label: "Report" },
  { id: "history", label: "History" },
  { id: "build", label: "Build" },
] as const;

export type Tab = (typeof TABS)[number]["id"];
