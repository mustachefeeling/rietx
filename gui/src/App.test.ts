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
 * The three shell states asserted first are the three a user will spend time in:
 * no project, a project with no fit, and a run in flight (where Run must be
 * disabled off the *state frame* rather than off what the last click hoped).
 * The editors that follow are asserted through their **requests**: what the
 * parameter table sends is the whole contract with `set_vary`/`set_values`, and
 * a table that renders beautifully while PATCHing the wrong body is the bug this
 * file exists to catch.
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

/** Rows chosen to carry all three held reasons plus a plain refinable one.
 *
 * The bounds are the **strings** the server sends: `JSON.parse` rejects Python's
 * bare `Infinity` token, so `gui/server.py` spells a non-finite float the way the
 * schemas do (`ser_json_inf_nan="strings"`). Writing numbers here instead would
 * make this suite pass against a payload the browser cannot even parse. */
function param(path: string, over: Record<string, unknown> = {}) {
  const row = {
    path, value: 1, vary: false, lo: "-Infinity" as any, hi: "Infinity" as any,
    transform: "identity",
    tie: null as any, locked: false, esd: null as number | null, mode_fixed: false,
    ...over,
  };
  return {
    ...row,
    refinable: !row.locked && row.tie === null && !row.mode_fixed,
    held_because: row.locked
      ? "structurally fixed by symmetry or by the model"
      : row.tie
        ? "tied: = 1·phases.0.cell.a"
        : row.mode_fixed
          ? "force-fixed by the intensity mode (lebail/pawley)"
          : "",
  };
}

const PARAMS = {
  parameters: [
    param("phases.0.cell.a", { value: 4.15678, vary: true, esd: 0.00019, lo: 0.1 }),
    param("phases.0.cell.b", { value: 4.15678, tie: { sources: ["phases.0.cell.a"] } }),
    param("phases.0.cell.alpha", { value: 90, locked: true }),
    param("phases.0.scale", { value: 1.02, vary: true }),
    param("phases.0.atoms.0.biso", { value: 0.5, mode_fixed: true }),
    param("instrument.profile.w", { value: 0.004, lo: 0, hi: 1 }),
  ],
  n_free: 2,
  mode: "rietveld",
  head: "n0000",
  live: false,
};

const PLAN = {
  plan: {
    stages: [
      { name: "scale+bkg", turn_on: ["phases.*.scale", "instrument.background.*"],
        max_iter: 100, lebail_cycles: 3, seed: 0, strain_seed: 0 },
      { name: "cell", turn_on: ["phases.*.cell.*"], max_iter: 100, lebail_cycles: 3,
        seed: 0, strain_seed: 0 },
    ],
    correlation_guard: 0.98,
  },
  selected: true,
  preset: "mccusker_default",
  mode: "rietveld",
};

const PLANS = {
  plans: [
    { name: "mccusker_default", title: "Standard (profile only)", description: "…",
      modes: ["rietveld"], when_to_use: "The default first fit of a known structure." },
    { name: "profile_only", title: "Profile only", description: "…",
      modes: ["rietveld", "lebail"], when_to_use: "Le Bail, or a profile without a structure." },
  ],
};

interface Call {
  method: string;
  path: string;
  body: any;
}

/** A stub server that also records what was asked of it. */
function server(routes: Record<string, (call: Call) => { status?: number; body: unknown }>) {
  const calls: Call[] = [];
  const fetcher = vi.fn(async (input: any, init: any = {}) => {
    const path = String(input).split("?")[0];
    const call: Call = {
      method: init.method ?? "GET",
      path,
      body: init.body ? JSON.parse(init.body) : null,
    };
    calls.push(call);
    const handler = routes[path];
    const { status = 200, body } = handler
      ? handler(call)
      : { status: 404, body: { error: { code: "NOT_FOUND", message: path } } };
    return { ok: status < 400, status, text: async () => JSON.stringify(body) } as any;
  });
  return { fetcher, calls };
}

/** The routes a mounted shell asks for before anyone has clicked anything. */
function boot(project: any = PROJECT, run: any = IDLE_RUN) {
  return {
    "/api/version": () => ({ body: { package_version: "1.0.0.dev0", project: project?.path ?? null } }),
    "/api/capabilities": () => ({ body: CAPABILITIES }),
    "/api/project": (call: Call) =>
      project
        ? { body: call.method === "POST"
              ? { ...project, doc: { ...project.doc, ui: { ...project.doc.ui, ...(call.body.ui ?? {}) } } }
              : project }
        : { status: 409, body: { error: { code: "NO_PROJECT", message: "no project" } } },
    "/api/run/state": () => ({ body: run }),
    "/api/result": () => ({ status: 409, body: { error: { code: "NO_RESULT", message: "none" } } }),
    "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...run } }),
    "/api/params": () => ({ body: PARAMS }),
    "/api/plan": () => ({ body: PLAN }),
    "/api/plans": () => ({ body: PLANS }),
  } as Record<string, (call: Call) => { status?: number; body: unknown }>;
}

const flush = async () => {
  for (let i = 0; i < 16; i++) await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
  for (let i = 0; i < 16; i++) await Promise.resolve();
};

let host: HTMLDivElement;
let app: any;

function button(text: string): HTMLButtonElement | undefined {
  return [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === text);
}

function rowsInDom(): HTMLElement[] {
  return [...host.querySelectorAll<HTMLElement>(".row")];
}

/** The editable cell of the row whose leaf is `leaf` — by name, because the
 *  positions shift: a tied row renders a span rather than an input. */
function cell(leaf: string): HTMLInputElement {
  const row = rowsInDom().find((r) => r.querySelector(".path")?.textContent?.trim() === leaf);
  return row!.querySelector<HTMLInputElement>("input.value")!;
}

async function type(selector: string, value: string) {
  const input = host.querySelector<HTMLInputElement>(selector)!;
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await flush();
}

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
    vi.stubGlobal("fetch", server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [{ path: "/tmp/a.pxrd", name: "a.pxrd" }] } }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();

    expect(host.textContent).toContain("No project open");
    expect(host.textContent).toContain("a.pxrd");
    // Run is disabled without a project — the control follows the state, not hope
    expect(button("Run")?.disabled).toBe(true);
  });

  it("renders a project with no fit, and offers Run", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);
    app = mount(App, { target: host });
    await flush();

    expect(host.textContent).toContain("synth.xye");
    expect(host.textContent).toContain("4200 pts");
    expect(host.textContent).toContain("σ from file");     // which weights the fit used
    expect(host.textContent).toContain("No fitted curves yet");
    expect(host.textContent).toContain("WP-1012");         // the panels still owed
    expect(button("Run")?.disabled).toBe(false);
  });

  it("shows the statistics and the stage while a run is in flight", async () => {
    const running = {
      ...IDLE_RUN,
      state: "running",
      run: { ...IDLE_RUN.run, kind: "fit", stage: "cell", stage_index: 3, n_stages: 5 },
    };
    vi.stubGlobal("fetch", server({
      ...boot(PROJECT, running),
      "/api/result": () => ({ body: { result: RESULT } }),
      "/api/result/window": () => ({ body: { two_theta: [3, 4], y_obs: [1, 2], y_calc: [1, 2],
                                             y_background: [], delta: [0, 0], ticks: {},
                                             window: [3, 4], n_total: 2, n_returned: 2,
                                             max_points: 4000 } }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();

    expect(host.textContent).toContain("cell");
    expect(host.textContent).toContain("(3/5)");           // 1-based, from stage_start
    expect(host.textContent).toContain("4.150%");          // Rwp as a percentage
    expect(button("Run")?.disabled).toBe(true);            // 409 made unclickable
    expect(button("Cancel")?.disabled).toBe(false);
  });

  it("surfaces an open refusal verbatim rather than 'could not open'", async () => {
    const message =
      "file has changed since the project was created (sha256 1a2b3c4d, recorded 9f8e7d6c)";
    vi.stubGlobal("fetch", server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [{ path: "/tmp/a.pxrd", name: "a.pxrd" }] } }),
      "/api/project/open": () => ({ status: 400, body: { error: { code: "PROJECT_ERROR", message } } }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();

    const open = [...host.querySelectorAll("button")].find((b) => b.textContent?.includes("a.pxrd"));
    open!.click();
    await flush();
    expect(host.textContent).toContain("sha256");
  });
});

// ----------------------------------------------------------------------
// the parameter table (WP-1011)
// ----------------------------------------------------------------------
const ADVANCED = { ...PROJECT, doc: { ...PROJECT.doc, ui: { simple: false } } };

describe("the parameter table", () => {
  it("groups rows and gives a held row no checkbox at all", async () => {
    vi.stubGlobal("fetch", server(boot(ADVANCED)).fetcher);
    app = mount(App, { target: host });
    await flush();

    // one heading per dot-path prefix, in the server's order
    const groups = [...host.querySelectorAll(".group")].map((g) => g.textContent?.trim());
    expect(groups?.[0]).toContain("phases.0.cell");
    expect(groups.some((g) => g?.includes("instrument.profile"))).toBe(true);

    expect(rowsInDom().length).toBe(PARAMS.parameters.length);
    // three of the six rows cannot be freed, and a checkbox that errors on click
    // is worse than no checkbox — so there are exactly three
    const boxes = host.querySelectorAll('.row input[type="checkbox"]');
    expect(boxes.length).toBe(3);
    // …and each held row says which of the three reasons holds it
    const held = rowsInDom().filter((row) => row.classList.contains("held"));
    expect(held.map((row) => row.dataset.held).sort()).toEqual(["locked", "mode", "tied"]);
    expect(host.querySelector('[data-held="tied"] .vary')?.getAttribute("title"))
      .toContain("tied: =");
  });

  it("hides held rows in Simple mode and says how many", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);   // ui.simple defaults true
    app = mount(App, { target: host });
    await flush();

    expect(rowsInDom().length).toBe(3);
    expect(host.textContent).toContain("3 held hidden");   // a count, not a silent cut
  });

  it("shows a value to the precision its esd justifies", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);
    app = mount(App, { target: host });
    await flush();

    const value = host.querySelector<HTMLInputElement>(".row input.value");
    expect(value?.value).toBe("4.1568");                   // 4.1568(2), not 4.15678
    expect(host.textContent).toContain("(2)");
  });

  it("sends the glob for a bulk free — one round trip, one history node", async () => {
    const stub = server({ ...boot(ADVANCED), "/api/params": () => ({ body: PARAMS }) });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    await type("#param-filter", "phases.*.cell.*");
    // the preview counts what set_vary could actually free: a and b and alpha
    // match, but b is tied and alpha is locked, so only `a` is freeable — and it
    // is already free, leaving one to fix and none to free
    expect(button("Fix 1")).toBeTruthy();
    button("Fix 1")!.click();
    await flush();

    const patch = stub.calls.find((call) => call.method === "PATCH");
    expect(patch?.path).toBe("/api/params");
    expect(patch?.body).toEqual({ vary: { "phases.*.cell.*": false } });
    // the console echoes the call, which is the API this GUI is a front for
    expect(host.textContent).toContain('ref.set_vary("phases.*.cell.*", False)');
  });

  it("wraps a bare word as a substring glob, so preview and apply agree", async () => {
    const stub = server(boot(ADVANCED));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    await type("#param-filter", "cell");
    expect(rowsInDom().length).toBe(3);                    // a, b, alpha
    button("Free 0")?.click();                             // disabled: none freeable
    await flush();
    expect(stub.calls.some((call) => call.method === "PATCH")).toBe(false);
  });

  it("batches value edits into one set_values call", async () => {
    const stub = server(boot(ADVANCED));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    for (const [leaf, text] of [["a", "4.157"], ["scale", "1.05"]] as const) {
      const input = cell(leaf);
      input.value = text;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    await flush();
    expect(host.textContent).toContain("2 pending edits");

    button("Apply")!.click();
    await flush();
    const patch = stub.calls.find((call) => call.method === "PATCH");
    expect(patch?.body).toEqual({
      values: { "phases.0.cell.a": 4.157, "phases.0.scale": 1.05 },
      vary: {},
    });
  });

  it("refuses an out-of-bounds value before the round trip", async () => {
    const stub = server(boot(ADVANCED));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const w = [...host.querySelectorAll<HTMLInputElement>(".row input.value")].at(-1)!;
    w.value = "2";                                          // instrument.profile.w is [0, 1]
    w.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();

    expect(w.classList.contains("bad")).toBe(true);
    expect(w.title).toContain("upper bound");
    // Apply is blocked, not silently partial — and Revert is still offered,
    // which is the affordance the bad cell most needs
    expect(button("Apply")?.disabled).toBe(true);
    expect(host.textContent).toContain("above the upper bound 1");
    button("Revert")!.click();
    await flush();
    expect(host.textContent).not.toContain("pending edit");
    expect(stub.calls.some((call) => call.method === "PATCH")).toBe(false);
  });

  it("shows the server's refusal in the server's own words", async () => {
    const message =
      "'phases.0.cell.b' follows 'phases.0.cell.a' as an affine tie; set that instead";
    const stub = server({
      ...boot(ADVANCED),
      "/api/params": (call) =>
        call.method === "PATCH"
          ? { status: 400, body: { error: { code: "INVALID_REQUEST", message,
                                            where: ["phases.0.cell.b"] } } }
          : { body: PARAMS },
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const input = host.querySelector<HTMLInputElement>(".row input.value")!;
    input.value = "4.2";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();

    expect(host.textContent).toContain("as an affine tie; set that instead");
  });
});

// ----------------------------------------------------------------------
// the plan editor and the disclosure toggle (WP-1011)
// ----------------------------------------------------------------------
describe("the plan editor", () => {
  async function openPlan(project: any = PROJECT, extra: Record<string, any> = {}) {
    const stub = server({ ...boot(project), ...extra });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Plan")!.click();
    await flush();
    return stub;
  }

  it("lists the stages the run will actually execute, and names the preset", async () => {
    await openPlan();
    const names = [...host.querySelectorAll<HTMLInputElement>(".name")].map((i) => i.value);
    expect(names).toEqual(["scale+bkg", "cell"]);
    expect(host.querySelector<HTMLSelectElement>("select")?.value).toBe("mccusker_default");
    // the preset's guidance, from PLAN_INFO through /api/plans
    expect(host.textContent).toContain("The default first fit of a known structure.");
  });

  it("runs one stage through the same machinery a whole fit uses", async () => {
    const stub = await openPlan();
    const runs = [...host.querySelectorAll<HTMLButtonElement>("li .head button")]
      .filter((b) => b.textContent?.trim() === "Run");
    runs[1].click();
    await flush();

    const post = stub.calls.find((call) => call.path === "/api/run");
    expect(post?.body.kind).toBe("stage");
    expect(post?.body.stage).toMatchObject({ name: "cell", turn_on: ["phases.*.cell.*"] });
    expect(host.textContent).toContain('ref.run_stage(Stage("cell"');
  });

  it("stores a picked preset expanded through the mode", async () => {
    const stub = await openPlan(PROJECT, {
      "/api/plan": (call: Call) =>
        call.method === "PUT"
          ? { body: { ...PLAN, preset: "profile_only" } }
          : { body: PLAN },
    });
    const select = host.querySelector<HTMLSelectElement>("select")!;
    select.value = "profile_only";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();

    const put = stub.calls.find((call) => call.method === "PUT");
    expect(put?.path).toBe("/api/plan");
    expect(put?.body).toEqual({ preset: "profile_only" });
  });

  it("keeps a stage's advanced fields behind the disclosure", async () => {
    await openPlan();
    expect(host.querySelector(".advanced")).toBeNull();
    unmount(app);
    app = null;
    host.innerHTML = "";
    await openPlan(ADVANCED);
    expect(host.querySelector(".advanced")).not.toBeNull();
    expect(host.textContent).toContain("strain");           // Stage.strain_seed
    expect(host.textContent).toContain("correlation guard");
  });

  it("reorders stages by drag, and offers to save the edited plan", async () => {
    const stub = await openPlan(PROJECT, {
      "/api/plan": (call: Call) => ({ body: call.method === "PUT" ? { ...PLAN, preset: null } : PLAN }),
    });
    // jsdom has no DragEvent; the handlers read only the indices they were
    // bound with, so a plain Event of the same type drives them identically
    const items = [...host.querySelectorAll("li")];
    items[1].dispatchEvent(new Event("dragstart", { bubbles: true }));
    items[0].dispatchEvent(new Event("drop", { bubbles: true }));
    await flush();

    const names = [...host.querySelectorAll<HTMLInputElement>(".name")].map((i) => i.value);
    expect(names).toEqual(["cell", "scale+bkg"]);
    button("Save plan")!.click();
    await flush();

    const put = stub.calls.find((call) => call.method === "PUT");
    expect(put?.body.plan.stages.map((s: any) => s.name)).toEqual(["cell", "scale+bkg"]);
    expect(put?.body.plan.correlation_guard).toBe(0.98);
  });
});

describe("disclosure and the command palette", () => {
  it("persists Simple/Advanced to the project's ui keys on the verb", async () => {
    const stub = server(boot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    button("Advanced")!.click();
    await flush();
    const post = stub.calls.find((call) => call.method === "POST" && call.path === "/api/project");
    // settings persist on the verb, not on a later save (WP-1005/1008)
    expect(post?.body).toEqual({ ui: { simple: false } });
    expect(rowsInDom().length).toBe(PARAMS.parameters.length);  // held rows are back
  });

  it("opens on Cmd-K and shows the API call behind every command", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);
    app = mount(App, { target: host });
    await flush();

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
    await flush();
    expect(host.textContent).toContain("Run the fit");
    expect(host.textContent).toContain("ref.fit(data, plan=…)");
    expect(host.textContent).toContain("ref.set_vary(glob, True)");
    // Cancel is shown greyed rather than hidden: that is how the shortcut is learnt
    const cancel = [...host.querySelectorAll("button")]
      .find((b) => b.textContent?.includes("Cancel the run"));
    expect(cancel?.disabled).toBe(true);
  });

  it("gives the console a fixed height it can be dragged out of", async () => {
    const stub = server(boot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    // sized, not flexible: sharing the sidebar with `flex: 1 1 auto` gave the
    // log half the column, which is the wrong split for a panel read in glances
    const panel = host.querySelector<HTMLElement>("section.console")!;
    expect(panel.style.flex).toBe("0 0 150px");

    // `.grip` is also the plan editor's drag handle, and `.caret` is a group
    // header's — scope to the console or the query finds a hidden panel's
    const grip = host.querySelector<HTMLElement>("section.console .grip")!;
    grip.dispatchEvent(new MouseEvent("pointerdown", { clientY: 400, bubbles: true }));
    window.dispatchEvent(new MouseEvent("pointermove", { clientY: 340, bubbles: true }));
    await flush();
    expect(panel.style.flex).toBe("0 0 210px");            // dragging up grows it

    window.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    await flush();
    // one write per drag, not one per pixel — and it lands in the project's ui
    const writes = stub.calls.filter((c) => c.method === "POST" && c.path === "/api/project");
    expect(writes).toHaveLength(1);
    expect(writes[0].body).toEqual({ ui: { console_height: 210 } });
  });

  it("collapses to its header and remembers the height to come back to", async () => {
    const tall = { ...PROJECT, doc: { ...PROJECT.doc, ui: { console_height: 260 } } };
    const stub = server(boot(tall));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const panel = host.querySelector<HTMLElement>("section.console")!;
    expect(panel.style.flex).toBe("0 0 260px");            // restored from the project

    const caret = host.querySelector<HTMLButtonElement>("section.console .caret")!;
    caret.click();
    await flush();
    expect(panel.style.flex).toBe("0 0 26px");             // header only
    expect(panel.classList.contains("shut")).toBe(true);

    caret.click();
    await flush();
    expect(panel.style.flex).toBe("0 0 260px");            // …and back to where it was
  });

  it("runs the fit on `r`, but not while a filter box has focus", async () => {
    const stub = server(boot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const filter = host.querySelector<HTMLInputElement>("#param-filter")!;
    filter.dispatchEvent(new KeyboardEvent("keydown", { key: "r", bubbles: true }));
    await flush();
    expect(stub.calls.some((call) => call.path === "/api/run")).toBe(false);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "r", bubbles: true }));
    await flush();
    expect(stub.calls.some((call) => call.path === "/api/run")).toBe(true);
  });
});
