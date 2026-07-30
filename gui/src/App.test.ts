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
import { diagnosticCount } from "@codemirror/lint";
import { EditorView } from "@codemirror/view";
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

/** LaB6: La on a fully fixed 1a site, B on 6f with one DOF along x. */
const STRUCTURE = {
  phases: [{
    name: "LaB6", space_group: "P m -3 m",
    cell: { a: { value: 4.15678, vary: true }, b: { value: 4.15678, vary: false },
            c: { value: 4.15678, vary: false }, alpha: { value: 90, vary: false },
            beta: { value: 90, vary: false }, gamma: { value: 90, vary: false } },
    scale: { value: 1.02, vary: true },
    atoms: [
      { label: "La", species: "La", x: { value: 0 }, y: { value: 0 }, z: { value: 0 },
        occ: { value: 1 }, biso: { value: 0.5 }, aniso: null },
      { label: "B", species: "B", x: { value: 0.1993 }, y: { value: 0.5 },
        z: { value: 0.5 }, occ: { value: 1 }, biso: { value: 0.4 }, aniso: null },
    ],
  }],
};

const SITES = [
  { path: "phases.0.atoms.0", phase: 0, atom: 0, site_symmetry_order: 48,
    special: true, dof_paths: [], dof_directions: [], adp_paths: [],
    adp_patterns: [[1, 1, 1, 0, 0, 0]], aniso: false },
  { path: "phases.0.atoms.1", phase: 0, atom: 1, site_symmetry_order: 8,
    special: true, dof_paths: ["phases.0.atoms.1.dof.0"], dof_directions: [[1, 0, 0]],
    adp_paths: [], adp_patterns: [], aniso: false },
];

const INSTRUMENT = {
  zero_shift: { value: 0.01, vary: false },
  source: { polarization: { value: 0.99, vary: false },
            lines: [{ wavelength: 0.413909, weight: { value: 1, vary: false } }],
            dispersion: { table: "cromer_liberman", overrides: {} } },
  profile: { shape: "tchz_pv", u: { value: 0.002, vary: false },
             v: { value: 0, vary: false }, w: { value: 0.004, vary: true },
             x: { value: 0, vary: false }, y: { value: 0, vary: false } },
  geometry: { kind: "debye_scherrer", goniometer_radius_mm: null,
              sample_displacement: { value: 0, vary: false },
              sample_transparency: { value: 0, vary: false },
              axial_sl: { value: 0.002, vary: false },
              axial_hl: { value: 0.002, vary: false },
              mu_r: null, capillary_radius_mm: null, packing_fraction: 0.6 },
  background: { kind: "chebyshev", coefficients: [{ value: 1 }, { value: 0 }, { value: 0 }] },
};

/** A history with a fork: n0003 ran from n0001, which already had n0002. */
const HISTORY = {
  tree_id: "t1",
  head: "n0003",
  root: "n0000",
  n_nodes: 4,
  nodes: [
    { id: "n0000", parents: [], children: ["n0001"], label: "", created_utc: "2026-07-30T10:00:00Z",
      kind: "root", name: "", action: { kind: "root" }, api_call: "pr.Refinement(structure, instrument)",
      status: null, n_iterations: null, rwp: null, gof: null, n_free: null,
      n_diagnostics: 0, diagnostics: [], tags: [], scores: {}, notes: {} },
    { id: "n0001", parents: ["n0000"], children: ["n0002", "n0003"], label: "",
      created_utc: "2026-07-30T10:00:01Z", kind: "stage", name: "scale+bkg",
      action: { kind: "stage", name: "scale+bkg", turn_on: ["phases.*.scale"] },
      api_call: "ref.run_stage(data, pr.Stage('scale+bkg', ['phases.*.scale'], max_iter=100))",
      status: "converged", n_iterations: 7, rwp: 0.21, gof: 1.9, n_free: 4,
      n_diagnostics: 0, diagnostics: [], tags: [], scores: {}, notes: {} },
    { id: "n0002", parents: ["n0001"], children: [], label: "",
      created_utc: "2026-07-30T10:00:02Z", kind: "stage", name: "cell",
      action: { kind: "stage", name: "cell", turn_on: ["phases.*.cell.*"] },
      api_call: "ref.run_stage(data, pr.Stage('cell', ['phases.*.cell.*'], max_iter=100))",
      status: "converged", n_iterations: 5, rwp: 0.04, gof: 0.8, n_free: 5,
      n_diagnostics: 1,
      diagnostics: [{ level: "warning", code: "HIGH_CORRELATION",
                      message: "a ~ b (ρ=+0.994)", where: ["phases.0.cell.a", "instrument.zero_shift"] }],
      tags: ["best-so-far"], scores: {}, notes: {} },
    { id: "n0003", parents: ["n0001"], children: [], label: "",
      created_utc: "2026-07-30T10:00:03Z", kind: "set_vary",
      name: "", action: { kind: "set_vary", turn_on: ["a", "b", "c"], turn_off: [] },
      api_call: "ref.set_vary(['a', 'b', 'c'], True)",
      status: null, n_iterations: null, rwp: null, gof: null, n_free: null,
      n_diagnostics: 0, diagnostics: [], tags: [], scores: {}, notes: {} },
  ],
};

/** A report with all three layers, an unindexed peak, and one of each
 *  applicability: a button, a veto, and advice. */
const REPORT = {
  report: {
    thresholds_version: "0.3",
    rwp: 0.216, gof: 1.41,
    summary: "Rwp 21.6 %, 15 misfitting regions; Layer 1 on 15/15 regions",
    regions: [
      { two_theta_lo: 9.0, two_theta_hi: 9.4, local_rwp: 0.31, chi2_share: 0.42,
        max_abs_delta_over_sigma: 41, n_reflections: 1 },
      { two_theta_lo: 5.6, two_theta_hi: 5.9, local_rwp: 0.88, chi2_share: 0.02,
        max_abs_delta_over_sigma: 6, n_reflections: 0 },
    ],
    unmatched: [{ two_theta: 12.34, height_over_sigma: 19, kind: "unmatched_obs" }],
    attribution: [
      { two_theta_lo: 9.0, two_theta_hi: 9.4, n_reflections: 1, chi2_share: 0.42,
        mean_two_theta: 9.2, mean_fwhm: 0.016, r2: 0.91, gram_condition: 220,
        chi2_reduced: 30, gates_passed: true, gate_failures: [],
        coefficients: [{ kind: "position", value: -0.0024, stderr: 0.0002,
                         significant: true, share: 0.9 }] },
      { two_theta_lo: 5.6, two_theta_hi: 5.9, n_reflections: 0, chi2_share: 0.02,
        mean_two_theta: 5.7, mean_fwhm: 0.016, r2: 0.2, gram_condition: 1.2e5,
        chi2_reduced: 4, gates_passed: false,
        gate_failures: ["local_r2=0.20<0.5", "gram_condition=1.2e+05>1e+04"],
        coefficients: [] },
    ],
    trends: [
      { observable: "position", n_regions_used: 15, max_template_collinearity: 0.999,
        separability_ratio: 1.1, separable: false, misfit_share: 0.85,
        templates: [{ name: "tan_theta", coefficient: -0.0024, stderr: 0.0002, r2: 0.88 },
                    { name: "constant", coefficient: -0.0011, stderr: 0.0003, r2: 0.71 }] },
    ],
    texture: [], strain: [], restraints: null,
    layer1_available: true, abstained_reason: null,
    suggested_actions: [
      { kind: "refine_scale", confidence: 0.9, rationale: "intensities are uniformly off",
        parameter_paths: ["phases.*.scale"], expected_delta_chi2: 16.19,
        alternatives: ["refine_biso"], two_theta_range: null,
        vetoed_by: "already refined by the staged plan (phases.*.scale)" },
      { kind: "refine_cell", confidence: 0.5,
        rationale: "position error follows the tan_theta template; templates are collinear",
        parameter_paths: ["phases.*.cell.*"], expected_delta_chi2: 16.19,
        alternatives: ["refine_zero_shift"], two_theta_range: null, vetoed_by: null },
      { kind: "add_impurity_phase", confidence: 0.4,
        rationale: "1 observed peak has no calculated reflection nearby",
        parameter_paths: [], expected_delta_chi2: null,
        alternatives: ["reindex_or_recheck_cell"], two_theta_range: [12.34, 12.34],
        vetoed_by: null },
    ],
  },
  apply: [
    { kind: "refine_scale", how: "stage", note: "", can_apply: false,
      refusal: "vetoed: already refined by the staged plan (phases.*.scale)",
      paths: ["phases.*.scale"], stage: null, api_call: null },
    { kind: "refine_cell", how: "stage", note: "", can_apply: true, refusal: "",
      paths: ["phases.*.cell.*"],
      stage: { name: "apply:refine_cell", turn_on: ["phases.*.cell.*"], max_iter: 100,
               lebail_cycles: 3, seed: 0, strain_seed: 0 },
      api_call: "ref.run_stage(data, pr.Stage('apply:refine_cell', ['phases.*.cell.*'], max_iter=100))" },
    { kind: "add_impurity_phase", how: "advice",
      note: "no phase is named yet, so there is nothing to free.",
      can_apply: false,
      refusal: "not a one-click action — no phase is named yet, so there is nothing to free.",
      paths: [], stage: null, api_call: null },
  ],
};

interface Call {
  method: string;
  path: string;
  /** the path *with* its query — the report panel's zoom is a query, not a body */
  url: string;
  body: any;
  blob?: Blob | null;
}

/** A stub server that also records what was asked of it. */
function server(routes: Record<string, (call: Call) => { status?: number; body: unknown }>) {
  const calls: Call[] = [];
  const fetcher = vi.fn(async (input: any, init: any = {}) => {
    const url = String(input);
    const path = url.split("?")[0];
    const call: Call = {
      method: init.method ?? "GET",
      path,
      url,
      // an upload's body is bytes, not JSON — the only route family in the
      // surface whose body is not a JSON object (WP-1014)
      body: typeof init.body === "string" ? JSON.parse(init.body) : null,
      blob: init.body instanceof Blob ? init.body : null,
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
    "/api/history": () => ({ body: HISTORY }),
    "/api/report": () => ({ status: 409, body: { error: { code: "NO_RESULT", message: "none" } } }),
    "/api/structure": () => ({ body: { structure: STRUCTURE, sites: SITES } }),
    "/api/instrument": () => ({ body: { instrument: INSTRUMENT } }),
  } as Record<string, (call: Call) => { status?: number; body: unknown }>;
}

/** The result routes, for the tests that need a fit to exist. */
const FITTED = {
  "/api/result": () => ({ body: { result: { ...RESULT, statistics: { rwp: 0.216, gof: 1.41, chi2: 16.96 } } } }),
  "/api/result/window": () => ({ body: { two_theta: [9, 9.4], y_obs: [1, 2], y_calc: [1, 2],
                                         y_background: [], delta: [0, 0], ticks: {},
                                         window: [9, 9.4], n_total: 2, n_returned: 2,
                                         max_points: 4000 } }),
  "/api/report": () => ({ body: REPORT }),
};

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
  it("renders the no-project state as the import wizard, with its recent list", async () => {
    vi.stubGlobal("fetch", server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [{ path: "/tmp/a.pxrd", name: "a.pxrd" }] } }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();

    // the empty state *is* the wizard (WP-1014) rather than a note about it
    expect(host.textContent).toContain("New project");
    expect(host.textContent).toContain("Choose a data file");
    expect(host.textContent).toContain("a.pxrd");
    expect(button("Create project")?.disabled).toBe(true);
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
    expect(host.textContent).toContain("WP-1015");         // the panels still owed
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

// ----------------------------------------------------------------------
// the history worktree and the report panel (WP-1012)
// ----------------------------------------------------------------------
async function openTab(name: string, project: any = PROJECT,
                       extra: Record<string, any> = {}) {
  const stub = server({ ...boot(project), ...extra });
  vi.stubGlobal("fetch", stub.fetcher);
  app = mount(App, { target: host });
  await flush();
  button(name)!.click();
  await flush();
  return stub;
}

describe("the history worktree", () => {
  it("draws the DAG with a second lane for the fork, and marks HEAD", async () => {
    await openTab("History");
    // four nodes, and the fork (n0003 from n0001, which already had n0002) needs
    // a second rail — this DAG has no refs, so a lane is where it divided
    expect(host.querySelectorAll(".node").length).toBe(4);
    expect(host.querySelectorAll("svg.rail circle").length).toBe(4);
    expect(host.textContent).toContain("2 lanes");
    expect(host.querySelector("svg.rail circle.head")).not.toBeNull();

    // the action, not the id — and Rwp with its move against the first parent
    expect(host.textContent).toContain("scale+bkg");
    expect(host.textContent).toContain("free 3 paths");
    expect(host.textContent).toContain("4.00%");
    expect(host.textContent).toContain("▾17.00");           // 0.04 against 0.21
    expect(host.textContent).toContain("best-so-far");      // a tag chip
    expect(host.textContent).toContain("⚠ 1");              // a node's diagnostics
  });

  it("shows the selected node's api_call and its guard finding's paths", async () => {
    await openTab("History");
    const rows = [...host.querySelectorAll<HTMLButtonElement>(".node button.pick")];
    rows[2].click();                                        // n0002
    await flush();
    expect(host.querySelector(".call")?.textContent).toContain("pr.Stage('cell'");
    // WP-1007: `where` carries the pair, so no message needs parsing
    expect(host.textContent).toContain("HIGH_CORRELATION");
    expect(host.textContent).toContain("phases.0.cell.a instrument.zero_shift");
  });

  it("checks a node out and tells the shell the curves are gone", async () => {
    const stub = await openTab("History", PROJECT, {
      ...FITTED,
      "/api/history/checkout": () => ({ body: { head: "n0002", parameters: [], n_free: 0 } }),
    });
    [...host.querySelectorAll<HTMLButtonElement>(".node button.pick")][2].click();
    await flush();
    expect(host.textContent).toContain("Checking out discards the fitted curves");

    const before = stub.calls.filter((c) => c.path === "/api/result").length;
    button("Checkout")!.click();
    await flush();
    const post = stub.calls.find((c) => c.path === "/api/history/checkout");
    expect(post?.body).toEqual({ node_id: "n0002" });
    // …and the shell refetched: a checkout discards the result server-side, so a
    // plot of the old curves would be a plot of a state the project is not in
    expect(stub.calls.filter((c) => c.path === "/api/result").length).toBe(before + 1);
    expect(host.textContent).toContain('ref.checkout("n0002")');
  });

  it("branches by naming a fork point — checkout plus tag, not a new ref", async () => {
    const stub = await openTab("History", PROJECT, {
      ...FITTED,
      "/api/history/branch": () => ({ body: { branched_from: "n0002", name: "keeper",
                                              head: "n0002", parameters: [] } }),
    });
    [...host.querySelectorAll<HTMLButtonElement>(".node button.pick")][2].click();
    await flush();
    await type("footer input", "keeper");
    button("Branch")!.click();
    await flush();
    const post = stub.calls.find((c) => c.path === "/api/history/branch");
    expect(post?.body).toEqual({ node_id: "n0002", name: "keeper" });
  });

  it("compares two nodes through diff, ranked, with the metrics beside it", async () => {
    const stub = await openTab("History", PROJECT, {
      "/api/history/diff": () => ({ body: { a: "n0001", b: "n0002", diff: {
        "phases.0.cell.a": [4.1566, 4.1568], "instrument.profile.w": [0.00025, 0.0005] } } }),
      "/api/history/compare": () => ({ body: { rows: [
        { id: "n0001", rwp: 0.21, n_free: 4, action: "stage:scale+bkg" },
        { id: "n0002", rwp: 0.04, n_free: 5, action: "stage:cell" }] } }),
    });
    const nodes = [...host.querySelectorAll<HTMLElement>(".node")];
    nodes[1].querySelector<HTMLButtonElement>("button.pick")!.click();
    await flush();
    nodes[2].querySelector<HTMLButtonElement>("button.tiny")!.click();   // ⇄
    await flush();

    expect(stub.calls.some((c) => c.url.includes("/api/history/diff?a=n0001&b=n0002"))).toBe(true);
    expect(host.textContent).toContain("2 paths differ");
    // biggest relative move first: w doubled, a moved 5e-5
    const paths = [...host.querySelectorAll(".drow .path")].map((n) => n.textContent?.trim());
    expect(paths).toEqual(["instrument.profile.w", "phases.0.cell.a"]);
    expect(host.textContent).toContain("21.00% → 4.00%");
  });
});

describe("the report panel", () => {
  it("renders the layers, and an unapplicable suggestion keeps its reason", async () => {
    await openTab("Report", PROJECT, FITTED);
    expect(host.textContent).toContain("21.600%");
    expect(host.textContent).toContain("Layer 1 on 15/15 regions");
    expect(host.textContent).toContain("1 unindexed");
    // the gates that refused, by name, counted — the values are on the row
    expect(host.textContent).toContain("local_r2 ×1");

    const actions = [...host.querySelectorAll<HTMLElement>(".action")];
    // applicable first, then the veto, then advice — and nothing is dropped
    expect(actions.map((a) => a.querySelector(".kind")?.textContent?.trim()))
      .toEqual(["refine_cell", "refine_scale", "add_impurity_phase"]);
    expect(actions[1].textContent).toContain("already refined by the staged plan");
    expect(actions[2].textContent).toContain("no phase is named yet");
    // one Apply button: the other two are refusals with reasons, not controls
    expect(host.querySelectorAll(".action button.small").length).toBe(1);
    // 0.5 is capped by the collinear templates, so it must not read as confident
    expect(actions[0].dataset.tone).toBe("medium");
  });

  it("says the predicted Δχ² is the report's, once, not per suggestion", async () => {
    await openTab("Report", PROJECT, FITTED);
    expect(host.textContent).toContain("one estimate for the whole report");
    // the figure appears once, in the note — not in a column beside three rows
    expect(host.textContent!.split("16.19").length - 1).toBe(1);
  });

  it("zooms the plot to a region, padded, at full point budget", async () => {
    const stub = await openTab("Report", PROJECT, FITTED);
    const rows = [...host.querySelectorAll<HTMLButtonElement>(".trow")];
    // ranked by χ² share: the 9.0–9.4° region leads, not the worse local Rwp one
    expect(rows[0].textContent).toContain("9.00–9.40");
    rows[0].click();
    await flush();
    // padded by 35 % of its own width, so a one-peak region arrives with a
    // baseline; and it is a *server* fetch, not an axis range
    const zoomed = stub.calls.filter((c) => c.path === "/api/result/window").at(-1);
    expect(zoomed?.url).toContain("lo=8.86");
    expect(zoomed?.url).toContain("hi=9.54");
  });

  it("applies a suggestion and measures it, with undo as a checkout", async () => {
    const stub = await openTab("Report", PROJECT, {
      ...FITTED,
      "/api/report/apply": () => ({ body: {
        applied: { kind: "refine_cell", confidence: 0.5, rationale: "…",
                   expected_delta_chi2: 16.19,
                   stage: { name: "apply:refine_cell", turn_on: ["phases.*.cell.*"] } },
        api_call: "ref.run_stage(data, pr.Stage('apply:refine_cell', ['phases.*.cell.*'], max_iter=100))",
        undo: "n0003", chi2_before: 16.96,
        state: "running", run: { ...IDLE_RUN.run, kind: "stage" }, head: "n0003" } }),
    });
    button("Apply")!.click();
    await flush();

    const post = stub.calls.find((c) => c.path === "/api/report/apply");
    expect(post?.body).toEqual({ kind: "refine_cell", paths: ["phases.*.cell.*"] });
    // the console echoes the stage the server said it would run
    expect(host.textContent).toContain("pr.Stage('apply:refine_cell'");
    // mid-run the observed value is *absent*, not zero: `chi2` is still the one
    // the action was applied at, and subtracting it would print a confident
    // "observed 0.000" for a measurement nobody has made
    expect(host.textContent).toContain("observed running…");
    expect(host.textContent).toContain("applied refine_cell");
    // …and Undo waits for the stage: a checkout mid-run is what the server 409s
    expect(button("Undo")?.disabled).toBe(true);
  });

  it("puts the observed Δχ² beside the predicted one, and undoes by checkout", async () => {
    // The applied stage runs and finishes, and the shell learns *only* from the
    // state frame that carries the outcome — which is the case a transition test
    // ("have I seen a running frame?") misses on a stage this fast, leaving the
    // previous fit's curves and χ² on screen.
    let done = false;
    let reads = 0;
    const finished = { state: "idle", project: PROJECT.path, head: "n0004",
                       run: { ...IDLE_RUN.run, kind: "stage", status: "converged",
                              node_id: "n0004" } };
    const stub = await openTab("Report", PROJECT, {
      ...FITTED,
      "/api/result": () => ({ body: { result: { ...RESULT, statistics: {
        rwp: 0.216, gof: 1.41, chi2: reads++ ? 0.63 : 16.96 } } } }),
      "/api/events": () => ({ body: { events: [], next: 0, oldest: 1,
                                      ...(done ? finished : IDLE_RUN) } }),
      "/api/report/apply": () => {
        done = true;
        return { body: {
          applied: { kind: "refine_cell", expected_delta_chi2: 16.19,
                     stage: { name: "apply:refine_cell" } },
          api_call: "ref.run_stage(data, pr.Stage('apply:refine_cell', ['phases.*.cell.*'], max_iter=100))",
          undo: "n0003", chi2_before: 16.96,
          state: "running", run: { ...IDLE_RUN.run, kind: "stage" }, head: "n0003" } };
      },
      "/api/history/checkout": () => ({ body: { head: "n0003", parameters: [], n_free: 0 } }),
    });
    button("Apply")!.click();
    await flush();
    await new Promise((resolve) => setTimeout(resolve, 800)); // one poll interval
    await flush();

    expect(host.textContent).toContain("predicted Δχ² 16.19");
    expect(host.textContent).toContain("observed 16.33");

    // undo needs no inverse verb: the head before the apply is a history node
    button("Undo")!.click();
    await flush();
    expect(stub.calls.find((c) => c.path === "/api/history/checkout")?.body)
      .toEqual({ node_id: "n0003" });
    expect(host.textContent).not.toContain("applied refine_cell");
  });

  it("keeps the per-region coefficients behind the disclosure", async () => {
    await openTab("Report", PROJECT, FITTED);
    expect(host.textContent).not.toContain("Attribution");
    unmount(app);
    app = null;
    host.innerHTML = "";
    await openTab("Report", ADVANCED, FITTED);
    expect(host.textContent).toContain("Attribution");
    // a trend the report itself calls non-separable must say so where it is read:
    // its confidence was already capped, and the alternatives travel with it
    expect(host.textContent).toContain("not separable");
    expect(host.textContent).toContain("tan_theta");
  });

  it("renders an abstention as an abstention", async () => {
    const abstained = {
      ...REPORT,
      report: { ...REPORT.report, layer1_available: false, attribution: [], trends: [],
                abstained_reason: "fit is immature (Rwp=0.407 > 0.35); Layer 1 abstains",
                suggested_actions: [REPORT.report.suggested_actions[2]] },
      apply: [REPORT.apply[2]],
    };
    await openTab("Report", PROJECT, { ...FITTED, "/api/report": () => ({ body: abstained }) });
    expect(host.textContent).toContain("Layer 1 abstained");
    expect(host.textContent).toContain("fit is immature");
    // the model-free action survives the abstention, which is the whole point
    expect(host.textContent).toContain("add_impurity_phase");
  });

  it("says there is nothing to report on before a fit, without erroring", async () => {
    await openTab("Report");                            // /api/report 409s NO_RESULT
    expect(host.textContent).toContain("No fit to report on yet");
    expect(host.querySelector(".bad")).toBeNull();
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

/**
 * The text pane (WP-1013), driven through the real CodeMirror view.
 *
 * `EditorView.findFromDOM` is what makes these end-to-end rather than a test of
 * `lib/sync.ts` twice: a dispatch on the live view is exactly what a keystroke
 * produces, so the debounce, the transport and the state machine are all in the
 * path. The two assertions worth having are the two the WP names as risks — a
 * concurrent model change may not eat an edit, and a conflict has one exit.
 */
const TEXTDOC = 'pxt 1\nproject "lab6"\nmode rietveld\nlimits none\n';
const TEXTDOC_MOVED = 'pxt 1\nproject "lab6"\nmode rietveld\nlimits 3 60\n';

/** Mount, then enter the text mode (a mode, not a tab — the strip stays five wide). */
async function openText(extra: Record<string, any> = {}, project: any = PROJECT) {
  const stub = server({
    "/api/textdoc": () => ({ body: { text: TEXTDOC, revision: "r1", format_version: "1" } }),
    ...boot(project),
    ...extra,
  });
  vi.stubGlobal("fetch", stub.fetcher);
  app = mount(App, { target: host });
  await flush();
  button("Text")!.click();
  await waitForEditor();
  return stub;
}

/** The editor arrives on a dynamic `import()` — a real await, not a microtask.
 *
 * That is the design working rather than a test smell: `vendor-cm.js` is a
 * separate chunk fetched the first time the pane is opened, so the boot path
 * keeps the size WP-1010 measured. A `flush()` of microtasks cannot see the end
 * of a module load, so this polls for the mounted editor. */
async function waitForEditor(timeout = 4000) {
  const deadline = Date.now() + timeout;
  while (!host.querySelector(".cm-content") && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  await flush();
}

/** The live editor, and a dispatch on it is a keystroke. */
function editorView(): EditorView {
  return EditorView.findFromDOM(host.querySelector(".cm-content") as HTMLElement)!;
}

async function typeInto(text: string) {
  const view = editorView();
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
  await flush();
}

/** Past the 300 ms validate debounce — real timers, because `flush` uses one. */
const settle = async () => {
  await new Promise((resolve) => setTimeout(resolve, 360));
  await flush();
};

describe("the text pane", () => {
  it("costs nothing until it is opened, then renders the document", async () => {
    const stub = server({
      "/api/textdoc": () => ({ body: { text: TEXTDOC, revision: "r1", format_version: "1" } }),
      ...boot(),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    // the boot path is what WP-1010 measured; a document nobody asked for would
    // both re-render every parameter row and pull in the editor chunk
    expect(stub.calls.some((call) => call.path === "/api/textdoc")).toBe(false);
    expect(host.querySelector(".cm-content")).toBeNull();

    button("Text")!.click();
    await waitForEditor();
    expect(stub.calls.some((call) => call.path === "/api/textdoc")).toBe(true);
    expect(host.querySelector(".cm-content")?.textContent).toContain("mode rietveld");
    expect(host.textContent).toContain("in sync");
  });

  it("validates a debounced edit without applying it", async () => {
    const stub = await openText({
      "/api/textdoc": (call: Call) => ({
        body: call.method === "GET"
          ? { text: TEXTDOC, revision: "r1", format_version: "1" }
          : { valid: true, applied: [], delta: {}, revision: "r1", would_change: true },
      }),
    });
    await typeInto(TEXTDOC_MOVED);
    expect(host.textContent).toContain("edited");
    expect(stub.calls.some((call) => call.method === "PUT")).toBe(false);  // still debouncing

    await settle();
    const put = stub.calls.find((call) => call.method === "PUT")!;
    expect(put.body).toEqual({ text: TEXTDOC_MOVED, base_revision: "r1", validate_only: true });
    expect(host.textContent).toContain("ready to apply");
  });

  it("applies explicitly, echoes the verbs, and adopts the re-render", async () => {
    const stub = await openText({
      "/api/textdoc": (call: Call) => ({
        body: call.method === "GET"
          ? { text: TEXTDOC, revision: "r1", format_version: "1" }
          : call.body.validate_only
            ? { valid: true, applied: [], delta: {}, revision: "r1", would_change: true }
            : { valid: true, applied: ['project.set_two_theta_limits(3.0, 60.0)'],
                delta: {}, text: TEXTDOC_MOVED, revision: "r2" },
      }),
    });
    await typeInto(TEXTDOC_MOVED);
    await settle();
    button("Apply ⌘⏎")!.click();
    await flush();

    const applied = stub.calls.filter((c) => c.method === "PUT" && !c.body.validate_only);
    expect(applied).toHaveLength(1);
    expect(applied[0].body.base_revision).toBe("r1");
    // the same verbs a form calls, so the console reads the same either way
    expect(host.textContent).toContain("project.set_two_theta_limits(3.0, 60.0)");
    expect(host.textContent).toContain("applied 1 change(s)");
    // the response carried the re-render: canonical output normalises glob lines
    // away, so the buffer is replaced rather than patched — and needs no 2nd GET
    expect(editorView().state.doc.toString()).toBe(TEXTDOC_MOVED);
    expect((button("Apply ⌘⏎") as HTMLButtonElement).disabled).toBe(true);
  });

  it("never lets a model change underneath overwrite an edit", async () => {
    let moved = false;
    const stub = await openText({
      "/api/textdoc": (call: Call) => ({
        body: call.method === "GET"
          ? { text: moved ? TEXTDOC_MOVED : TEXTDOC, revision: moved ? "r2" : "r1",
              format_version: "1" }
          : { valid: true, applied: [], delta: {}, revision: "r1", would_change: true },
      }),
      // a checkout from the history panel, an applied suggestion, a form edit:
      // every one of them moves the head, which is this pane's reload signal
      "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...IDLE_RUN,
                                      head: moved ? "n0009" : "n0000" } }),
    });
    const mine = TEXTDOC + "excluded 7.5 8\n";
    await typeInto(mine);
    moved = true;
    await new Promise((resolve) => setTimeout(resolve, 800));  // one poll interval
    await flush();

    expect(editorView().state.doc.toString()).toBe(mine);       // the edit survives
    expect(host.textContent).toContain("stale");
    expect(host.textContent).toContain("There is no merge");
    expect((button("Apply ⌘⏎") as HTMLButtonElement).disabled).toBe(true);

    // one exit, and it is the same one the server's 409 recommends
    button("Re-read")!.click();
    await flush();
    expect(editorView().state.doc.toString()).toBe(TEXTDOC_MOVED);
    expect(host.textContent).toContain("in sync");
    expect(stub.calls.filter((c) => c.path === "/api/textdoc" && c.method === "GET").length)
      .toBeGreaterThan(1);
  });

  it("shows a refusal at its line, and clears it when the line is retyped", async () => {
    await openText({
      "/api/textdoc": (call: Call) => ({
        status: call.method === "GET" ? 200 : 400,
        body: call.method === "GET"
          ? { text: TEXTDOC, revision: "r1", format_version: "1" }
          : { error: { code: "TEXTDOC_INVALID",
                       message: "1 problem(s) in the document; nothing was applied",
                       where: ["mode"],
                       details: [{ line: 3, message: "unknown mode 'nonsense'",
                                   where: "mode", text: "mode nonsense" }] } },
      }),
    });
    await typeInto(TEXTDOC.replace("rietveld", "nonsense"));
    await settle();

    expect(host.textContent).toContain("1 problem(s)");
    expect(host.textContent).toContain("unknown mode 'nonsense'");
    expect(host.textContent).toContain("line 3");
    // the squiggle and the list are two views of one answer — asserted through
    // CM's own lint state, because reading `textContent` sees only the list and
    // that is exactly how the defect below hid
    expect(diagnosticCount(editorView().state)).toBe(1);
    // the highlighter said nothing about any of this: only the server can
    expect(host.querySelector(".cm-content [class*='tok-']")).not.toBeNull();

    await typeInto(TEXTDOC);
    expect(host.textContent).not.toContain("unknown mode");
    expect(diagnosticCount(editorView().state)).toBe(0);
  });

  it("keeps the squiggle when the head moves underneath an invalid buffer", async () => {
    // Found in a browser, invisible to a `textContent` assertion: `load` cleared
    // the editor's diagnostics unconditionally, so a checkout — or a form edit,
    // or an applied suggestion — wiped the squiggle and the gutter marker while
    // the problem list below still named the line. Both now derive from `sync`.
    let moved = false;
    await openText({
      "/api/textdoc": (call: Call) => ({
        status: call.method === "GET" ? 200 : 400,
        body: call.method === "GET"
          ? { text: moved ? TEXTDOC_MOVED : TEXTDOC, revision: moved ? "r2" : "r1",
              format_version: "1" }
          : { error: { code: "TEXTDOC_INVALID", message: "1 problem(s)", where: ["mode"],
                       details: [{ line: 3, message: "unknown mode 'nonsense'",
                                   where: "mode", text: "mode nonsense" }] } },
      }),
      "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...IDLE_RUN,
                                      head: moved ? "n0009" : "n0000" } }),
    });
    await typeInto(TEXTDOC.replace("rietveld", "nonsense"));
    await settle();
    expect(diagnosticCount(editorView().state)).toBe(1);

    moved = true;
    await new Promise((resolve) => setTimeout(resolve, 800));  // one poll interval
    await flush();

    expect(host.textContent).toContain("stale");
    expect(host.textContent).toContain("unknown mode 'nonsense'");  // the list
    expect(diagnosticCount(editorView().state)).toBe(1);            // …and the squiggle
  });

  it("is read-only in the way that matters while a run is in flight", async () => {
    const running = { ...IDLE_RUN, state: "running",
                      run: { ...IDLE_RUN.run, kind: "fit", stage: "cell" } };
    const stub = await openText({
      "/api/run/state": () => ({ body: running }),
      "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...running } }),
    });
    await typeInto(TEXTDOC_MOVED);
    await settle();

    // no validate is even attempted: the server would answer RUN_IN_FLIGHT, and
    // the state refusal outranking a parse complaint is only useful if the pane
    // does not ask a question it knows the answer to
    expect(stub.calls.some((call) => call.method === "PUT")).toBe(false);
    expect((button("Apply ⌘⏎") as HTMLButtonElement).disabled).toBe(true);
  });

  it("warns that comments will not survive before Apply replaces the buffer", async () => {
    await openText();
    await typeInto(TEXTDOC + "# checked against the certificate 2026-07-30\n");
    expect(host.textContent).toContain("will not survive the next render");
  });
});

// ----------------------------------------------------------------------
// the import wizard and the model editors (WP-1014)
// ----------------------------------------------------------------------
/** A `File` on a file input, which jsdom will not let you assign directly. */
function chooseFile(input: HTMLInputElement, name: string, text = "data") {
  const file = new File([text], name, { type: "application/octet-stream" });
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

const PATTERN_PREVIEW = {
  upload: "p1", kind: "pattern", filename: "nac.fxye", bytes: 12, sha256: "aa",
  format: { name: "gsas", title: "GSAS raw powder data (FXYE / ESD / STD)",
            sniff: "a BANK record in the first 4 kB — by content, not by suffix",
            sigma: "the third column (FXYE)", options: [] },
  block: null, n_points: 4200, two_theta_range: [3, 24], step: 0.005,
  has_sigma: true, metadata: {},
  curve: { two_theta: [3, 10, 24], intensity: [1, 9, 2], n_returned: 3 },
  suggested_project: "/work/nac.pxrd",
};

const CIF_PREVIEW = {
  upload: "c1", kind: "cif", filename: "lab6.cif", bytes: 40, sha256: "bb",
  structure: STRUCTURE, aniso: false, aniso_available: false, aniso_error: "",
  phases: [{ name: "LaB6", space_group: "P m -3 m",
             cell: [4.1566, 4.1566, 4.1566, 90, 90, 90], n_atoms: 2,
             species: ["B", "La"], n_aniso: 0 }],
  unknown_species: [],
};

describe("the import wizard", () => {
  it("stages each file, then commits tokens — nothing exists until Create", async () => {
    const stub = server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [] } }),
      "/api/upload/pattern": () => ({ body: PATTERN_PREVIEW }),
      "/api/upload/cif": () => ({ body: CIF_PREVIEW }),
      "/api/project/new": () => ({ body: PROJECT }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const files = [...host.querySelectorAll<HTMLInputElement>('input[type="file"]')];
    chooseFile(files[0], "nac.fxye");
    await flush();
    // the reader that claimed it, in its own words — not the extension
    expect(host.textContent).toContain("GSAS raw powder data");
    expect(host.textContent).toContain("BANK record");
    expect(host.textContent).toContain("σ from the file");
    // …and the filename went in the query, while the bytes went in the body
    const staged = stub.calls.find((c) => c.path === "/api/upload/pattern")!;
    expect(staged.url).toContain("filename=nac.fxye");
    expect(staged.body).toBeNull();
    expect(staged.blob).toBeInstanceOf(Blob);

    chooseFile(files[1], "lab6.cif");
    await flush();
    expect(host.textContent).toContain("P m -3 m");
    // the aniso checkbox is offered *disabled* when the file has no loop
    const aniso = host.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    expect(aniso.disabled).toBe(true);
    expect(host.textContent).toContain("no aniso loop in this file");

    // the project path was suggested by the pattern step, and the anode by the preset
    expect(button("Create project")?.disabled).toBe(false);
    button("Create project")!.click();
    await flush();

    const created = stub.calls.find((c) => c.path === "/api/project/new")!;
    expect(created.body.pattern).toEqual({ upload: "p1" });
    expect(created.body.structure).toEqual({ upload: "c1", aniso: false });
    expect(created.body.instrument).toEqual({ preset: "bragg_brentano", radiation: "CuKa" });
    expect(created.body.path).toBe("/work/nac.pxrd");
    // and the shell adopted it without a second GET /api/project
    expect(host.textContent).toContain("synth.xye");
  });

  it("shows the reader's refusal and stages nothing", async () => {
    const stub = server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [] } }),
      "/api/upload/cif": () => ({ status: 400, body: { error: { code: "UPLOAD_INVALID",
        message: "could not read a structure from notes.cif: ValueError: "
                 + "notes.cif:1:0(0): expected block header (data_)" } } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const files = [...host.querySelectorAll<HTMLInputElement>('input[type="file"]')];
    chooseFile(files[1], "notes.cif");
    await flush();

    expect(host.textContent).toContain("expected block header");
    expect(button("Create project")?.disabled).toBe(true);
  });
});

/** The parameter rows the model editor needs on top of the table's own fixture:
 *  the coordinate DOF that moves B, and the two atom rows it types through. */
const MODEL_PARAMS = {
  ...PARAMS,
  parameters: [
    ...PARAMS.parameters,
    param("phases.0.atoms.1.dof.0", { value: 0 }),
    param("phases.0.atoms.0.occ", { value: 1 }),
    param("phases.0.atoms.1.occ", { value: 1 }),
    param("phases.0.atoms.1.biso", { value: 0.4 }),
    param("instrument.zero_shift", { value: 0.01 }),
  ],
};

describe("the model editor", () => {
  async function openModel(extra: Record<string, any> = {}) {
    const stub = server({ ...boot(), "/api/params": () => ({ body: MODEL_PARAMS }),
                          ...extra });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Model")!.click();
    await flush();
    return stub;
  }

  function field(path: string): HTMLInputElement {
    return host.querySelector<HTMLInputElement>(`[data-field="${path}"]`)!;
  }

  it("gives a fully fixed special position no coordinate control, with the reason", async () => {
    await openModel();
    expect(field("phases.0.name").value).toBe("LaB6");
    expect(host.textContent).toContain("fully fixed special position");
    expect(host.textContent).toContain("48");
    // …while the 6f site gets the one DOF its symmetry allows, and says which way
    expect(field("phases.0.atoms.1.dof.0")).toBeTruthy();
    expect(host.textContent).toContain("[1 0 0]");
    expect(field("phases.0.atoms.0.dof.0")).toBeFalsy();
  });

  it("sends a value the parameter table owns through set_values", async () => {
    const stub = await openModel();
    field("phases.0.cell.a").value = "4.2";
    field("phases.0.cell.a").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();

    const patch = stub.calls.find((c) => c.method === "PATCH" && c.path === "/api/params")!;
    expect(patch.body).toEqual({ values: { "phases.0.cell.a": 4.2 } });
    // …and nothing was sent as a whole model: a cell edge is not a shape change
    expect(stub.calls.some((c) => c.path === "/api/structure" && c.method === "PATCH"))
      .toBe(false);
  });

  it("sends a species as a whole model, built on a freshly read one", async () => {
    const stub = await openModel();
    field("phases.0.atoms.1.species").value = "B";
    field("phases.0.atoms.1.species").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    field("phases.0.atoms.0.species").value = "La3+";
    field("phases.0.atoms.0.species").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();

    const reads = stub.calls.filter((c) => c.path === "/api/structure" && c.method === "GET");
    const patch = stub.calls.find((c) => c.path === "/api/structure" && c.method === "PATCH")!;
    // the model patched is the one read *after* the edit was made, not the one
    // rendered — a stale whole-model PATCH reverts every field it did not touch
    expect(reads.length).toBeGreaterThan(1);
    expect(patch.body.structure.phases[0].atoms[0].species).toBe("La3+");
    // the unchanged one is untouched, and typing a value back to what it was is
    // not an edit at all
    expect(patch.body.structure.phases[0].atoms[1].species).toBe("B");
    expect(stub.calls.some((c) => c.method === "PATCH" && c.path === "/api/params"))
      .toBe(false);
  });

  it("offers µR to a capillary and never both absorption fields", async () => {
    await openModel();
    expect(field("geometry.mu_r")).toBeTruthy();
    expect(field("geometry.mu_t")).toBeFalsy();
    // an absent optional renders empty, because µt = 0 is a specimen of zero
    // thickness and µR = 0 is simply off — the two "off"s disagree
    expect(field("geometry.mu_r").value).toBe("");
  });

  it("surfaces the FCJ corner rather than defaulting it away", async () => {
    await openModel();
    expect(host.textContent).toContain("S/L = H/L");
    expect(host.textContent).toContain("ρ = +1.000");
  });

  it("adds an atom to the model the shell is holding, not to a copy of it", async () => {
    // Regression, found in Chrome and not in jsdom until this existed: the model
    // lives in a `$state` rune, which is a **Proxy**, and `structuredClone`
    // throws `#<Object> could not be cloned` on one. The click did nothing and
    // the page logged an uncaught error.
    const stub = await openModel();
    const add = [...host.querySelectorAll<HTMLInputElement>(".add input")];
    const fill = (input: HTMLInputElement, value: string) => {
      input.value = value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    };
    fill(add[0], "O1");
    fill(add[1], "O");
    fill(add[2], "0.25");
    await flush();
    button("Add atom")!.click();
    await flush();

    const patch = stub.calls.find((c) => c.path === "/api/structure" && c.method === "PATCH")!;
    const atoms = patch.body.structure.phases[0].atoms;
    expect(atoms).toHaveLength(3);
    expect(atoms[2].label).toBe("O1");
    expect(atoms[2].x.value).toBe(0.25);
  });

  it("keeps a refusal on screen through the reload that follows it", async () => {
    // Also a browser finding: `apply` reloads after a failure, because a partial
    // apply leaves the server half-ahead — and `load` was clearing the same
    // variable the refusal had just been written to, so an unknown species was
    // refused and the message vanished. Two facts, two fields (WP-1013's rule).
    await openModel({
      "/api/structure": (call: Call) => call.method === "PATCH"
        ? { status: 400, body: { error: { code: "UNKNOWN_SPECIES",
            message: "1 atom(s) carry a scattering species this build has no form "
                     + "factor for: La (Xx).",
            where: ["phases.0.atoms.0.species"] } } }
        : { body: { structure: STRUCTURE, sites: SITES } },
    });
    field("phases.0.atoms.0.species").value = "Xx";
    field("phases.0.atoms.0.species").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();

    expect(host.textContent).toContain("no form factor for: La (Xx)");
  });

  it("toggles one atom's ADPs through the verb that knows the metric", async () => {
    const stub = await openModel({
      "/api/structure/aniso": () => ({ body: { node_id: "n0004", changed: true,
                                               structure: STRUCTURE, sites: SITES } }),
    });
    const checkbox = [...host.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')][0];
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();

    const call = stub.calls.find((c) => c.path === "/api/structure/aniso")!;
    expect(call.body).toEqual({ path: "phases.0.atoms.0", on: true });
  });
});
