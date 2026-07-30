/** Loading plotly, once, from the installed Python package.
 *
 * WP-1010 refused to vendor plotly: it is injected at runtime from `/plotly.js`,
 * which `gui/server.py` serves out of the installed wheel, so the committed dist
 * stays reviewable and the page still boots — and says so — when the `[gui]`
 * extra is not installed.  WP-1015 added a second plot, which is what turned
 * that loader into a function: two copies of a `<script>` injection is two
 * chances to disagree about the URL, and the second consumer is what makes the
 * in-flight promise matter (both panels can ask before either has an answer).
 */
let pending: Promise<any> | null = null;

export function loadPlotly(): Promise<any> {
  const existing = (globalThis as any).Plotly;
  if (existing) return Promise.resolve(existing);
  if (pending) return pending;
  pending = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "/plotly.js";
    script.onload = () => resolve((window as any).Plotly);
    script.onerror = () => {
      pending = null;   // a failed load must not poison every later attempt
      reject(new Error("could not load /plotly.js"));
    };
    document.head.appendChild(script);
  });
  return pending;
}
