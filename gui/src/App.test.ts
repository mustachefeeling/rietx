// @vitest-environment jsdom
/**
 * Mount the real shell against a stubbed server and read the DOM.
 *
 * Not a substitute for looking at the page — it is a substitute for *shipping a
 * blank one*.  The failure mode a component test catches that no Python test
 * can is a runtime error during mount: the bundle loads, the server answers, and
 * the user sees nothing.  So this boots `App.svelte` with `fetch` stubbed,
 * waits for the boot chain, and asserts the header, the run controls and the
 * empty states are actually in the document.
 *
 * The three states asserted here are the three a user will spend time in: no
 * project, a project with no fit, and a run in flight (where Run must be
 * disabled off the *state frame* rather than off what the last click hoped).
 */
import { mount, unmount } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App.svelte";

const CAPABILITIES = {
  package_version: "1.0.0.dev0",
  features: { anisotropic_adp: true, indexing: false, cancellation: true },
  plans: [],
};

const PROJECT = {
  path: "/tmp/lab6.pxrd",
  doc: { mode: "rietveld", plan: null, ui: {} },
  data: { filename: "synth.xye", n_points: 4200, has_sigma: true, reader: "xy" },
  head: "n0000",
  n_nodes: 1,
};

const IDLE_RUN = {
  state: "idle",
  run: { kind: null, status: null, stage: null, stage_index: null, n_stages: null,
         rwp: null, gof: null, node_id: null, completed_stages: [], error: null },
  project: PROJECT.path,
  head: "n0000",
};

const RESULT = {
  statistics: { rwp: 0.0415, gof: 0.79 },
  curves: { n_points: 4200, two_theta_range: [3, 23.995] },
  ticks: { LaB6: [5.7, 8.1] },
};

function server(routes: Record<string, () => { status?: number; body: unknown }>) {
  return vi.fn(async (input: any) => {
    const path = String(input).split("?")[0];
    const handler = routes[path];
    const { status = 200, body } = handler
      ? handler()
      : { status: 404, body: { error: { code: "NOT_FOUND", message: path } } };
    return {
      ok: status < 400,
      status,
      text: async () => JSON.stringify(body),
    } as any;
  });
}

const flush = async () => {
  for (let i = 0; i < 8; i++) await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
};

let host: HTMLDivElement;
let app: any;

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
  // the shell subscribes to the stream on mount; a session with no EventSource
  // falls back to polling, and the stub below is what it polls
  (globalThis as any).EventSource = undefined;
});

afterEach(() => {
  if (app) unmount(app);
  host.remove();
  vi.restoreAllMocks();
});

describe("the shell", () => {
  it("renders the no-project state with its recent list", async () => {
    vi.stubGlobal(
      "fetch",
      server({
        "/api/version": () => ({ body: { package_version: "1.0.0.dev0", project: null } }),
        "/api/capabilities": () => ({ body: CAPABILITIES }),
        "/api/project": () => ({ status: 409, body: { error: { code: "NO_PROJECT", message: "no project" } } }),
        "/api/recent": () => ({ body: { recent: [{ path: "/tmp/a.pxrd", name: "a.pxrd" }] } }),
        "/api/run/state": () => ({ body: IDLE_RUN }),
        "/api/result": () => ({ status: 409, body: { error: { code: "NO_RESULT", message: "none" } } }),
        "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...IDLE_RUN } }),
      }),
    );
    app = mount(App, { target: host });
    await flush();

    expect(host.textContent).toContain("No project open");
    expect(host.textContent).toContain("a.pxrd");
    // Run is disabled without a project — the control follows the state, not hope
    const run = [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === "Run");
    expect(run?.disabled).toBe(true);
  });

  it("renders a project with no fit, and offers Run", async () => {
    vi.stubGlobal(
      "fetch",
      server({
        "/api/version": () => ({ body: { package_version: "1.0.0.dev0", project: PROJECT.path } }),
        "/api/capabilities": () => ({ body: CAPABILITIES }),
        "/api/project": () => ({ body: PROJECT }),
        "/api/run/state": () => ({ body: IDLE_RUN }),
        "/api/result": () => ({ status: 409, body: { error: { code: "NO_RESULT", message: "none" } } }),
        "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...IDLE_RUN } }),
      }),
    );
    app = mount(App, { target: host });
    await flush();

    expect(host.textContent).toContain("synth.xye");
    expect(host.textContent).toContain("4200 pts");
    expect(host.textContent).toContain("σ from file");     // which weights the fit used
    expect(host.textContent).toContain("No fitted curves yet");
    expect(host.textContent).toContain("WP-1011");         // the panels still owed
    const run = [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === "Run");
    expect(run?.disabled).toBe(false);
  });

  it("shows the statistics and the stage while a run is in flight", async () => {
    const running = {
      ...IDLE_RUN,
      state: "running",
      run: { ...IDLE_RUN.run, kind: "fit", stage: "cell", stage_index: 3, n_stages: 5 },
    };
    vi.stubGlobal(
      "fetch",
      server({
        "/api/version": () => ({ body: { package_version: "1.0.0.dev0", project: PROJECT.path } }),
        "/api/capabilities": () => ({ body: CAPABILITIES }),
        "/api/project": () => ({ body: PROJECT }),
        "/api/run/state": () => ({ body: running }),
        "/api/result": () => ({ body: { result: RESULT } }),
        "/api/result/window": () => ({ body: { two_theta: [3, 4], y_obs: [1, 2], y_calc: [1, 2],
                                               y_background: [], delta: [0, 0], ticks: {},
                                               window: [3, 4], n_total: 2, n_returned: 2,
                                               max_points: 4000 } }),
        "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...running } }),
      }),
    );
    app = mount(App, { target: host });
    await flush();

    expect(host.textContent).toContain("cell");
    expect(host.textContent).toContain("(3/5)");           // 1-based, from stage_start
    expect(host.textContent).toContain("4.150%");          // Rwp as a percentage
    const run = [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === "Run");
    const cancel = [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === "Cancel");
    expect(run?.disabled).toBe(true);                      // 409 made unclickable
    expect(cancel?.disabled).toBe(false);
  });

  it("surfaces an open refusal verbatim rather than 'could not open'", async () => {
    const message =
      "file has changed since the project was created (sha256 1a2b3c4d, recorded 9f8e7d6c)";
    vi.stubGlobal(
      "fetch",
      server({
        "/api/version": () => ({ body: { package_version: "1.0.0.dev0", project: null } }),
        "/api/capabilities": () => ({ body: CAPABILITIES }),
        "/api/project": () => ({ status: 409, body: { error: { code: "NO_PROJECT", message: "no project" } } }),
        "/api/recent": () => ({ body: { recent: [{ path: "/tmp/a.pxrd", name: "a.pxrd" }] } }),
        "/api/project/open": () => ({ status: 400, body: { error: { code: "PROJECT_ERROR", message } } }),
        "/api/run/state": () => ({ body: IDLE_RUN }),
        "/api/result": () => ({ status: 409, body: { error: { code: "NO_RESULT", message: "none" } } }),
        "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...IDLE_RUN } }),
      }),
    );
    app = mount(App, { target: host });
    await flush();

    const open = [...host.querySelectorAll("button")].find((b) => b.textContent?.includes("a.pxrd"));
    open!.click();
    await flush();
    expect(host.textContent).toContain("sha256");
  });
});
