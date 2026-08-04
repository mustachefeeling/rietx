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

/** `GET /api/structure3d` for the same LaB6: the orbit of the corner atom with
 *  one of its boundary copies, one boron, one bond, and the twelve cell edges.
 *  Trimmed by hand — the geometry itself is `tests/test_structure3d.py`'s
 *  ground, and what a mount can check is that the panel *draws* it. */
const GEOMETRY = {
  phase: 0, phases: ["LaB6"], name: "LaB6", space_group: "P m -3 m",
  cell: [4.15678, 4.15678, 4.15678, 90, 90, 90], volume: 71.82,
  lattice: [[4.15678, 0, 0], [0, 4.15678, 0], [0, 0, 4.15678]],
  corners: [[0, 0, 0], [4.15678, 0, 0], [0, 4.15678, 0], [4.15678, 4.15678, 0],
            [0, 0, 4.15678], [4.15678, 0, 4.15678], [0, 4.15678, 4.15678],
            [4.15678, 4.15678, 4.15678]],
  edges: [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3],
          [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]],
  sites: [
    { index: 0, path: "phases.0.atoms.0", label: "La", species: "La",
      element: "La", color: "#995cbc", radius: 2.07, metal: true, occ: 1,
      biso: 0.5, u_iso: 0.00633, aniso: false, multiplicity: 1, special: true,
      npd: false },
    { index: 1, path: "phases.0.atoms.1", label: "B", species: "B",
      element: "B", color: "#e0a080", radius: 0.84, metal: false, occ: 1,
      biso: 0.4, u_iso: 0.00507, aniso: false, multiplicity: 6, special: true,
      npd: false },
  ],
  atoms: [
    { site: 0, frac: [0, 0, 0], pos: [0, 0, 0], boundary: false,
      ellipsoid: [[0.08, 0, 0], [0, 0.08, 0], [0, 0, 0.08]],
      rms: [0.08, 0.08, 0.08], npd: false },
    { site: 0, frac: [1, 0, 0], pos: [4.15678, 0, 0], boundary: true,
      ellipsoid: [[0.08, 0, 0], [0, 0.08, 0], [0, 0, 0.08]],
      rms: [0.08, 0.08, 0.08], npd: false },
    { site: 1, frac: [0.1993, 0.5, 0.5], pos: [0.8284, 2.0784, 2.0784],
      boundary: false, ellipsoid: [[0.07, 0, 0], [0, 0.07, 0], [0, 0, 0.07]],
      rms: [0.07, 0.07, 0.07], npd: false },
  ],
  bonds: [{ i: 0, j: 2, a: [0, 0, 0], b: [0.8284, 2.0784, 2.0784], d: 3.058 }],
  probability: 0.5, probability_levels: { "0.5": 1.5382, "0.9": 2.5003 },
  scale: 1.5382, ball_fraction: 0.40, bond_tolerance: 1.15,
  bond_metals: false, note: "",
};

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
/** A handler may return a `gate` to hold its answer open — which is the only
 *  way to put two requests in flight at once and choose the order they land in. */
function server(routes: Record<string, (call: Call) =>
                { status?: number; body: unknown; gate?: Promise<void> }>) {
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
    const { status = 200, body, gate } = handler
      ? handler(call)
      : { status: 404, body: { error: { code: "NOT_FOUND", message: path } },
          gate: undefined };
    if (gate) await gate;
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
    "/api/structure3d": () => ({ body: GEOMETRY }),
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
    // the panels still owed — and the viewer WP-1015 shipped is not one of them
    expect(host.textContent).toContain("WP-1016");
    expect(host.textContent).not.toContain("WP-1015");
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

  it("does not present a hopeless fit in the register of a good one", async () => {
    // WP-1029 item (c). The judgement is the *report's* — `maturity` quotes
    // MATURITY_MAX_RWP, the Rwp past which Layer 1 refuses to speak about
    // individual parameters — and `status` still says `converged`, because
    // that vocabulary is WP-1028's and two owners would disagree.
    const hopeless = {
      ...RESULT,
      status: "converged",
      statistics: { rwp: 0.963, gof: 18.4 },
      maturity: { immature: true, max_rwp: 0.35,
                  message: "Rwp 96.3% is past the point where the report will "
                    + "speak about individual parameters … the structure and the "
                    + "pattern are of the same specimen" },
    };
    vi.stubGlobal("fetch", server({
      ...boot(),
      "/api/result": () => ({ body: { result: hopeless } }),
      "/api/result/window": () => ({ body: { two_theta: [3, 4], y_obs: [1, 2],
        y_calc: [1, 2], y_background: [], delta: [0, 0], delta_raw: [0, 0],
        cumulative_chi2: [0, 0], weighted: true, ticks: {}, window: [3, 4],
        n_total: 2, n_returned: 2, max_points: 4000 } }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();

    expect(host.querySelector(".stats")?.classList.contains("immature")).toBe(true);
    const flag = button("⚠ not a fit yet")!;
    expect(flag).toBeTruthy();
    expect(flag.title).toContain("same specimen");
    // the calm pill is still there and still says `converged` — untouched
    expect(host.querySelector(".pill")?.textContent?.trim()).toBe("idle");

    // …and it is a route to the panel that explains it, not just a badge
    flag.click();
    await flush();
    expect(host.textContent).toContain("No fit to report on yet");
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

  it("selects the top-level view from one segmented control", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);
    app = mount(App, { target: host });
    await flush();

    const group = host.querySelector<HTMLElement>('[aria-label="view"]')!;
    const labels = [...group.querySelectorAll("button")].map((b) => b.textContent?.trim());
    expect(labels).toEqual(["Plot", "Model", "Text"]);
    expect(group.querySelector("button.on")?.textContent?.trim()).toBe("Plot");

    button("Model")!.click();
    await flush();
    expect(group.querySelector("button.on")?.textContent?.trim()).toBe("Model");
    // …and clicking Model again stays on Model.  The old pair toggled, so the
    // same click meant two different things depending on where you already were
    button("Model")!.click();
    await flush();
    expect(group.querySelector("button.on")?.textContent?.trim()).toBe("Model");

    // leaving is a button named for where you land, not a Close inside the pane
    expect([...host.querySelectorAll("button")].some((b) => b.textContent?.trim() === "Close"))
      .toBe(false);
    button("Plot")!.click();
    await flush();
    expect(group.querySelector("button.on")?.textContent?.trim()).toBe("Plot");
  });

  it("stamps an explicit theme on the root and persists the choice", async () => {
    const stub = server(boot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    // no choice stored → "system", and jsdom's matchMedia stub reports light
    expect(document.documentElement.dataset.theme).toBe("light");

    const dark = [...host.querySelectorAll("button")].find((b) => b.getAttribute("aria-label") === "dark");
    dark!.click();
    await flush();
    expect(document.documentElement.dataset.theme).toBe("dark");
    // …and `color-scheme` with it, which is what the unstyled native controls read
    expect(document.documentElement.style.colorScheme).toBe("dark");

    const post = stub.calls.find((call) => call.method === "POST" && call.path === "/api/project");
    expect(post?.body).toEqual({ ui: { theme: "dark" } });
  });

  it("repaints the plot on a theme change — new ink, no refetch", async () => {
    // The canvas keeps whatever colours it was painted with, so a draw effect
    // that does not depend on the theme leaves the old theme's text on the new
    // theme's page — light grey on white, found by use within hours of the
    // toggle landing (WP-1029 q).  The colours themselves come from the
    // `--plot-*` custom properties, sampled at *paint* time; jsdom loads no
    // stylesheet, so the un-set ones are the fallbacks and a set one is ours.
    const drawn: any[] = [];
    vi.stubGlobal("Plotly", {
      react: async (_node: any, traces: any[], layout: any) => {
        drawn.push({ traces, layout });
      },
      purge: () => {},
    });
    document.body.style.setProperty("--plot-obs", "#112233");
    try {
      const stub = server({ ...boot(), ...FITTED });
      vi.stubGlobal("fetch", stub.fetcher);
      app = mount(App, { target: host });
      await flush();

      const first = drawn.at(-1)!;
      expect(first.traces.find((t: any) => t.name === "observed").marker.color)
        .toBe("#112233");
      expect(first.traces.find((t: any) => t.name === "Δ/σ").line.color).toBe("#1f5fa8");
      expect(first.layout.yaxis2.zerolinecolor).toBe("#88888888");

      const fetched = stub.calls.filter((c) => c.path === "/api/result/window").length;
      const painted = drawn.length;
      // what the dark stylesheet does in a browser, done by hand here
      document.body.style.setProperty("--plot-obs", "#445566");
      [...host.querySelectorAll("button")]
        .find((b) => b.getAttribute("aria-label") === "dark")!.click();
      await flush();

      // a repaint with the new colours — and *not* a refetch: the numbers did
      // not move, only the ink did
      expect(drawn.length).toBeGreaterThan(painted);
      expect(drawn.at(-1)!.traces.find((t: any) => t.name === "observed").marker.color)
        .toBe("#445566");
      expect(stub.calls.filter((c) => c.path === "/api/result/window").length).toBe(fetched);
    } finally {
      document.body.style.removeProperty("--plot-obs");
    }
  });

  it("does not repaint curves a checkout discarded when the theme changes", async () => {
    // A checkout clears the result server-side and the plot purges — but the
    // payload `held` for knob repaints survived, so the theme buttons (always
    // in the header) could redraw a state the project is no longer in onto the
    // purged canvas.  WP-1012's rule, applied to the copy in hand: when the
    // result goes, the held window goes with it.
    const drawn: any[] = [];
    let purged = 0;
    vi.stubGlobal("Plotly", {
      react: async (_node: any, traces: any[], layout: any) => { drawn.push({ traces, layout }); },
      purge: () => { purged += 1; },
    });
    let fitted = true;
    const stub = server({
      ...boot(),
      ...FITTED,
      "/api/result": () =>
        fitted
          ? { body: { result: { ...RESULT, statistics: { rwp: 0.216, gof: 1.41, chi2: 16.96 } } } }
          : { status: 409, body: { error: { code: "NO_RESULT", message: "none" } } },
      "/api/history/checkout": () => {
        fitted = false;
        return { body: { head: "n0002", parameters: [], n_free: 0 } };
      },
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    expect(drawn.length).toBeGreaterThan(0);   // the fitted curves were painted

    button("History")!.click();
    await flush();
    [...host.querySelectorAll<HTMLButtonElement>(".node button.pick")][2].click();
    await flush();
    button("Checkout")!.click();
    await flush();
    expect(purged).toBeGreaterThan(0);          // the canvas was cleared

    const painted = drawn.length;
    [...host.querySelectorAll("button")]
      .find((b) => b.getAttribute("aria-label") === "dark")!.click();
    await flush();
    expect(drawn.length).toBe(painted);         // nothing to repaint, so no repaint
  });

  it("drags the panel column wider and persists the width once", async () => {
    // the sidebar starts on the CSS clamp — `null`, so a fresh project is
    // responsive rather than frozen at the first window it was opened in
    const sized = { ...PROJECT, doc: { ...PROJECT.doc, ui: { side_width: 420 } } };
    const stub = server(boot(sized));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const side = host.querySelector<HTMLElement>(".side")!;
    expect(side.style.flex).toBe("0 0 420px");

    const grip = side.querySelector<HTMLElement>(':scope > .grip[data-grow="left"]')!;
    grip.dispatchEvent(new MouseEvent("pointerdown", { clientX: 900, bubbles: true }));
    window.dispatchEvent(new MouseEvent("pointermove", { clientX: 820, bubbles: true }));
    await flush();
    expect(side.style.flex).toBe("0 0 500px");              // dragging left grows it

    window.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    await flush();
    const writes = stub.calls.filter((c) => c.method === "POST" && c.path === "/api/project");
    expect(writes).toHaveLength(1);
    expect(writes[0].body).toEqual({ ui: { side_width: 500 } });
  });

  it("lays the cell out as one row of six, in crystallography's letters", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Model")!.click();
    await flush();

    const labels = [...host.querySelectorAll(".cellrow .cell > span:first-child")]
      .map((s) => s.textContent?.trim());
    expect(labels).toEqual(["a", "b", "c", "α", "β", "γ"]);
    // the *path* keeps the spelled-out name: a glyph in one would be a second
    // vocabulary for the same field
    expect(host.querySelector('[data-field="phases.0.cell.alpha"]')
      ?? host.querySelector(".cellrow .fixed")).toBeTruthy();
  });

  it("drags a model column and persists both widths together", async () => {
    const stub = server(boot({ ...PROJECT,
      doc: { ...PROJECT.doc, ui: { model_columns: [400, 380] } } }));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Model")!.click();
    await flush();

    const columns = [...host.querySelectorAll<HTMLElement>(".column")];
    expect(columns[0].style.flex).toBe("0 0 400px");
    expect(columns[1].style.flex).toBe("0 0 380px");

    // the grips are flex items *between* the columns, not absolute children of
    // them: a column scrolls, and an absolute edge inside `overflow: auto`
    // scrolls away from the edge it is supposed to be
    const grip = host.querySelector<HTMLElement>('.editors > .grip[data-flow="inline"]')!;
    grip.dispatchEvent(new MouseEvent("pointerdown", { clientX: 400, bubbles: true }));
    window.dispatchEvent(new MouseEvent("pointermove", { clientX: 460, bubbles: true }));
    window.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    await flush();

    expect(columns[0].style.flex).toBe("0 0 460px");
    expect(columns[1].style.flex).toBe("0 0 380px");        // untouched, not reset
    const writes = stub.calls.filter((c) => c.method === "POST" && c.path === "/api/project");
    expect(writes.at(-1)!.body).toEqual({ ui: { model_columns: [460, 380] } });
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

// ----------------------------------------------------------------------
// the structure viewer (WP-1015)
// ----------------------------------------------------------------------
describe("the structure viewer", () => {
  /** plotly is injected at runtime and stubbed globally in `test-setup.ts`; the
   *  viewer's assertions are about the *traces it hands over*, so this replaces
   *  the stub with a recording one for the duration of a test. */
  function recorder(live?: any) {
    const drawn: any[] = [];
    vi.stubGlobal("Plotly", {
      react: async (node: any, traces: any[], layout: any) => {
        drawn.push({ traces, layout });
        // what a real gl3d plot leaves behind: the scene object whose
        // `getCamera()` is the only honest reading of the view
        if (live) node._fullLayout = { scene: { _scene: { getCamera: () => live } } };
      },
      purge: () => {},
    });
    return drawn;
  }

  async function openViewer(extra: Record<string, any> = {}) {
    const stub = server({ ...boot(), "/api/params": () => ({ body: MODEL_PARAMS }),
                          ...extra });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Model")!.click();
    await flush();
    return stub;
  }

  /** The drawing knobs are behind a disclosure since WP-1029 — every one of
   *  them used to be on screen at once under a 300 px plot. */
  async function openKnobs() {
    [...host.querySelectorAll("button")]
      .find((b) => b.textContent?.includes("drawing"))!.click();
    await flush();
  }

  /** by name, not by index: the trace list grows, the names do not move. */
  function trace(drawn: any[], name: string): any {
    return drawn[drawn.length - 1].traces.find((t: any) => t.name === name);
  }

  it("draws the cell, the bonds and one mesh per species", async () => {
    const drawn = recorder();
    await openViewer();
    const { traces, layout } = drawn[drawn.length - 1];
    expect(traces.map((t: any) => t.name))
      .toEqual(["cell", "axes", "bonds:La", "bonds:B", "La", "La", "B"]);
    expect(trace(drawn, "La").type).toBe("mesh3d");
    // a stick is in Å like everything else, so it is a mesh and not a 4 px line
    expect(trace(drawn, "bonds:La").type).toBe("mesh3d");
    expect(trace(drawn, "axes").text).toEqual(["a", "b", "c"]);
    // a crystal, not a plot: parallel projection and no Cartesian box
    expect(layout.scene.camera.projection.type).toBe("orthographic");
    expect(layout.scene.xaxis.visible).toBe(false);
    // one Å is one Å on every axis, or a monoclinic cell is drawn orthogonal
    expect(layout.scene.aspectmode).toBe("data");
    // …and every draw supplies the *same* camera under a scene revision, which
    // is what plotly needs to keep a rotation the user made (see `lib/layout`)
    expect(layout.scene.uirevision).toBe("structure3d");
    for (const d of drawn) expect(d.layout.scene.camera).toEqual(layout.scene.camera);
  });

  it("says what it drew and at which thresholds", async () => {
    recorder();
    await openViewer();
    expect(host.textContent).toContain("2 atoms in the cell + 1 image outside it");
    expect(host.textContent).toContain("1 bond segment at 1.15×");
    expect(host.textContent).toContain("metal–metal contacts not bonded");
    expect(host.textContent).toContain("balls at 0.40× the covalent radius");
  });

  it("rescales the ellipsoids without asking the server again", async () => {
    // the payload carries k(p) for every level it offers, so a probability
    // change is a client multiply — a refetch would be a round trip for a
    // number already on the page
    const drawn = recorder();
    const stub = await openViewer();
    button("ellipsoids")!.click();
    await openKnobs();
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    // the sphere's first vertex is its +z pole, and La sits at the origin, so
    // this is the semi-axis itself: 0.08 · k(p)
    const at50 = trace(drawn, "La").z[0];
    expect(at50).toBeCloseTo(0.08 * 1.5382, 6);

    const select = [...host.querySelectorAll("select")]
      .find((s) => [...s.options].some((o) => o.textContent?.trim() === "90 %"))!;
    select.value = "0.9";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();

    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length).toBe(before);
    expect(trace(drawn, "La").z[0]).toBeCloseTo(0.08 * 2.5003, 6);
    expect(host.textContent).toContain("ellipsoids at 90 %");

    // …and the level survives a reload.  Found in Chrome: the payload carries
    // the server's default probability, so every refetch quietly put the
    // ellipsoids back to 50 % — a choice undone by the next cell edit.
    field("phases.0.cell.a").value = "4.2";
    field("phases.0.cell.a").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();
    expect(host.textContent).toContain("ellipsoids at 90 %");
    expect(trace(drawn, "La").z[0]).toBeCloseTo(0.08 * 2.5003, 6);
  });

  it("calls an exaggeration an exaggeration, never a probability", async () => {
    // WP-1029's one design question. A probability cannot exceed 1 — k(p) =
    // √χ²₃(p) diverges as p → 1 and `probability_scale(1.0)` raises — so
    // "bigger so I can see it" is a drawing scale, and a viewer that drew
    // 1.5·k(0.5) under a "50 %" label would be claiming a surface it is not
    // drawing.
    const drawn = recorder();
    await openViewer();
    button("ellipsoids")!.click();
    await openKnobs();
    const at50 = trace(drawn, "La").z[0];

    const size = [...host.querySelectorAll<HTMLInputElement>('input[type="range"]')]
      .find((i) => i.max === "4")!;
    size.value = "2";
    size.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();

    expect(trace(drawn, "La").z[0]).toBeCloseTo(at50 * 2, 6);
    // the probability is still the probability…
    expect(host.textContent).toContain("ellipsoids at 50 % (k = 1.538)");
    // …and the factor is stated beside it, as what it is
    expect(host.textContent).toContain("× 2.00 exaggeration");
    expect(host.textContent).toContain("not a probability");
    expect(host.textContent).not.toContain("ellipsoids at 100 %");
  });

  it("thins the stick for the mode it is drawn in", async () => {
    // WP-1015's justification for an uncapped cylinder — "the far end is buried
    // inside its own atom, whose ball is larger than the stick for every
    // element there is" — is true in ball mode and overclaims in ellipsoid
    // mode, where an atom's size is √U·k(p) and not a covalent radius.
    const drawn = recorder();
    await openViewer();
    const ball = trace(drawn, "bonds:La");
    const ballRadius = Math.max(...ball.x) - Math.min(...ball.x);

    button("ellipsoids")!.click();
    await flush();
    const thin = trace(drawn, "bonds:La");
    expect(Math.max(...thin.x) - Math.min(...thin.x)).toBeLessThan(ballRadius);
    expect(host.textContent).toContain("sticks 0.0");
  });

  it("re-supplies the view the user rotated to, read from the scene", async () => {
    // Every redraw builds new trace objects, and replacing a `mesh3d` rebuilds
    // the gl3d scene from the layout — so the view has to be handed back in.
    // Where it is read from is the whole question: `layout.scene.camera` reports
    // what was passed *in*, and `plotly_relayout` does not fire for a gl3d drag
    // at all (measured in Chrome, and true of the shipped build too).
    const rotated = { up: { x: 0, y: 0, z: 1 }, center: { x: 0, y: 0, z: 0 },
                      eye: { x: -0.62, y: -1.41, z: -1.47 },
                      projection: { type: "orthographic" } };
    const drawn = recorder(rotated);
    await openViewer();
    button("ellipsoids")!.click();
    await flush();
    expect(drawn[drawn.length - 1].layout.scene.camera.eye).toEqual(rotated.eye);
  });

  it("lets a view button outrank what is on screen", async () => {
    // …but not the other way round: a camera the user *chose* must survive the
    // read-back, or pressing "down c" would draw whatever the scene already had
    const drawn = recorder({ eye: { x: -0.62, y: -1.41, z: -1.47 },
                             projection: { type: "orthographic" } });
    await openViewer();
    button("c")!.click();
    await flush();
    const eye = drawn[drawn.length - 1].layout.scene.camera.eye;
    expect(eye.x).toBeCloseTo(0, 12);
    expect(eye.y).toBeCloseTo(0, 12);
    expect(eye.z).toBeGreaterThan(0);
  });

  it("looks down a lattice vector without asking the server anything", async () => {
    const drawn = recorder();
    const stub = await openViewer();
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    const opening = drawn[drawn.length - 1].layout.scene.camera;

    button("c")!.click();
    await flush();
    const down = drawn[drawn.length - 1].layout.scene.camera;
    // LaB6 is cubic, so c is exactly ẑ — the case turntable would have made a
    // degenerate lookAt, and the reason `dragmode` is "orbit"
    expect(down.eye.x).toBeCloseTo(0, 12);
    expect(down.eye.y).toBeCloseTo(0, 12);
    expect(down.up).toEqual({ x: 0, y: 1, z: 0 });     // b is up
    // …and the zoom the user had is kept
    expect(Math.hypot(down.eye.x, down.eye.y, down.eye.z))
      .toBeCloseTo(Math.hypot(opening.eye.x, opening.eye.y, opening.eye.z), 12);

    button("reset")!.click();
    await flush();
    expect(drawn[drawn.length - 1].layout.scene.camera).toEqual(opening);
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length)
      .toBe(before);
  });

  it("refetches when the bond threshold moves, because the server owns the rule", async () => {
    recorder();
    const stub = await openViewer();
    await openKnobs();
    const slider = host.querySelector<HTMLInputElement>('input[type="range"]')!;
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;

    // the *label* follows the drag — one fetch per pixel would be a flood, but
    // showing a number is not a fetch, and tying the cheap one to the expensive
    // one is the whole of item (n)
    slider.value = "1.05";
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    expect(host.textContent).toContain("1.05×");
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length).toBe(before);

    // …and the *fetch* waits for the release, because the server owns the rule
    slider.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();
    const last = stub.calls.filter((c) => c.path === "/api/structure3d").pop()!;
    expect(last.url).toContain("bond_tolerance=1.05");
  });

  /** A promise plus the button that resolves it. */
  function gate(): { promise: Promise<void>; open: () => void } {
    let open = () => {};
    const promise = new Promise<void>((resolve) => { open = () => resolve(); });
    return { promise, open };
  }

  it("drops an answer a later request has already overtaken", async () => {
    // WP-1013's rule, one panel over: two quick releases of the bond slider put
    // two requests in flight, and the picture must agree with the control that
    // asked for it rather than with whichever answer landed last
    const held: Array<() => void> = [];
    recorder();
    await openViewer({
      "/api/structure3d": (call: Call) => {
        const asked = new URL(call.url, "http://x").searchParams
          .get("bond_tolerance");
        const body = { ...GEOMETRY, bond_tolerance: Number(asked) };
        if (asked === "1.15") return { body };      // the opening load
        const g = gate();
        held.push(g.open);
        return { body, gate: g.promise };
      },
    });
    await openKnobs();
    const slider = host.querySelector<HTMLInputElement>('input[type="range"]')!;
    for (const value of ["1.05", "1.25"]) {
      slider.value = value;
      slider.dispatchEvent(new Event("change", { bubbles: true }));
      await flush();
    }
    expect(held.length).toBe(2);
    held[1]();                 // the newer answer lands first…
    await flush();
    held[0]();                 // …and the older one is dropped rather than drawn
    await flush();
    // the caption quotes the payload's own echo, so this is what the server said
    expect(host.textContent).toContain("at 1.25×");
    expect(host.textContent).not.toContain("at 1.05×");
  });

  it("says it is loading until the first answer settles", async () => {
    // "no structure yet" was a false statement for the whole 605–1447 ms the
    // first paint takes — one `geo === null` cannot say both "not fetched" and
    // "fetched, and there is nothing here"
    recorder();
    const g = gate();
    await openViewer({
      "/api/structure3d": () => ({ body: GEOMETRY, gate: g.promise }),
    });
    expect(host.textContent).toContain("loading the structure");
    expect(host.textContent).not.toContain("no structure yet");
    g.open();
    await flush();
    expect(host.textContent).not.toContain("loading the structure");
  });

  it("switches a species off from the legend without a round trip", async () => {
    const drawn = recorder();
    const stub = await openViewer();
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    const chip = [...host.querySelectorAll("button")]
      .find((b) => b.className.includes("chip") && b.textContent?.trim() === "La")!;
    chip.click();
    await flush();
    // La's half-sticks go with it: a half belongs to its atom
    expect(drawn[drawn.length - 1].traces.map((t: any) => t.name))
      .toEqual(["cell", "axes", "bonds:B", "B"]);
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length).toBe(before);
  });

  it("offers the draw mode as one segmented control with one side on", async () => {
    // two plain buttons wore the primary (filled) register, so both read as
    // pressed — a control that answers no question (found by use, 2026-07-31)
    recorder();
    await openViewer();
    const group = host.querySelector('.viewer .segmented[aria-label="draw mode"]')!;
    const on = () => [...group.querySelectorAll("button.on")].map((b) => b.textContent!.trim());
    expect([...group.querySelectorAll("button")].map((b) => b.textContent!.trim()))
      .toEqual(["balls", "ellipsoids"]);
    expect(on()).toEqual(["balls"]);
    button("ellipsoids")!.click();
    await flush();
    expect(on()).toEqual(["ellipsoids"]);
  });

  it("redraws on a theme change, without asking the server", async () => {
    // the cell frame samples `--accent` and the labels sample the body colour
    // at draw time, so the redraw is what lets a theme change reach the canvas
    // at all (WP-1029 q) — and the geometry did not move, so refetching it
    // would be a round trip for numbers already in hand
    const drawn = recorder();
    const stub = await openViewer();
    const fetched = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    const painted = drawn.length;
    [...host.querySelectorAll("button")]
      .find((b) => b.getAttribute("aria-label") === "dark")!.click();
    await flush();
    expect(drawn.length).toBeGreaterThan(painted);
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length).toBe(fetched);
  });

  it("redraws as soon as the pane around it re-reads, not one frame later", async () => {
    // A cell edit goes through `PATCH /api/params`, and the model pane re-reads
    // the moment that returns — while the head reaches the *shell* only on the
    // next SSE frame.  Following the pane is what keeps the picture and the atom
    // table showing the same structure.
    const drawn = recorder();
    const stub = await openViewer();
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    field("phases.0.cell.a").value = "4.2";
    field("phases.0.cell.a").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length)
      .toBeGreaterThan(before);
    expect(drawn.length).toBeGreaterThan(1);
  });

  it("can be closed, and asks for nothing while it is", async () => {
    recorder();
    const stub = await openViewer();
    button("3D")!.click();
    await flush();
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    expect(host.querySelector('input[type="range"]')).toBeNull();
    field("phases.0.cell.a").value = "4.3";
    field("phases.0.cell.a").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length).toBe(before);
  });

  function field(path: string): HTMLInputElement {
    return host.querySelector<HTMLInputElement>(`[data-field="${path}"]`)!;
  }
});

// ----------------------------------------------------------------------
// WP-1027 — the peaks tab and the candidate table's gate
// ----------------------------------------------------------------------
import Peaks from "./panels/Peaks.svelte";

const PEAK = (index: number, tt: number, extra: Record<string, unknown> = {}) => ({
  index, two_theta: tt, two_theta_esd: 0.0011, d: 4.4, intensity: 1234,
  intensity_esd: 20, q: 0.05, q_esd: 1e-4, fwhm: 0.08, eta: 0.5, group: index,
  n_in_group: 1, chi2_red: 1.1, flags: [], origin: "fitted", usable: true,
  ...extra,
});

const PEAKS_PAYLOAD = {
  peaks: [
    PEAK(0, 10.0),
    PEAK(1, 12.0, { flags: ["not_separable"], usable: false }),
    PEAK(2, 14.0, { origin: "manual" }),
  ],
  pattern: { two_theta: [9, 10, 11, 12, 13, 14], y_obs: [1, 5, 2, 3, 1, 4], n_total: 6 },
  groups: [],
  diagnostics: [{ level: "warning", code: "PEAK_LIST_TOO_SHORT", message: "3 usable lines" }],
  flag_vocabulary: ["ghost_kbeta", "excluded", "not_separable", "sigma_assumed"],
  unusable_flags: ["ghost_kbeta", "excluded", "not_separable"],
  n_total: 3, n_usable: 2, source: "fitted", wavelength: 1.5406,
};

const MEDIUM_CANDIDATE = {
  cell: [4.7594, 4.7594, 12.992, 90, 90, 120], cell_esd: [0, 0, 0, 0, 0, 0],
  system: "hexagonal", centring: "R", lattice_group: "R -3 m", volume: 254.9,
  n_indexed: 20, n_lines: 20,
  fom: [{ name: "M20", value: 43.1, n_lines: 20, blind_spot: "" }],
  found_by: ["dichotomy", "trial_error"], confidence: "medium",
  confidence_caveats: ["shift_allowance_assumed"], ambiguity: [], lebail: null,
  diagnostics: [],
};

describe("the peaks tab (WP-1027)", () => {
  it("lists every line, the fitter's exclusions distinguished, diagnostics inline", async () => {
    vi.stubGlobal("fetch", server({
      ...boot(),
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    expect(host.textContent).toContain("2 of 3 lines usable");
    // the fitter's own explanation of a strong peak's shape stays visible…
    expect(host.textContent).toContain("not_separable");
    // …a hand-placed line says so, and the diagnostics render as a strip
    expect(host.textContent).toContain("manual");
    expect(host.textContent).toContain("PEAK_LIST_TOO_SHORT");
  });

  it("sends the overrule verb from the use-for-indexing checkbox", async () => {
    const stub = server({
      ...boot(),
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
      "/api/peaks/flag": (call: Call) => ({ body: { ...PEAKS_PAYLOAD, api_call:
        `session.set_peak_flags(${call.body.index}, use_for_indexing=${call.body.use_for_indexing})` } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    const boxes = [...host.querySelectorAll<HTMLInputElement>('td.acts input[type="checkbox"]')];
    expect(boxes.length).toBe(3);
    boxes[1].dispatchEvent(new Event("change", { bubbles: true }));
    await flush();
    const sent = stub.calls.find((c) => c.path === "/api/peaks/flag");
    // the unusable line's checkbox asks to *use* it — the overrule, not a toggle blind
    expect(sent?.body).toEqual({ index: 1, use_for_indexing: true });
  });

  it("disables Adopt for a medium candidate and quotes the server's why", async () => {
    vi.stubGlobal("fetch", server({}).fetcher);
    app = mount(Peaks, { target: host, props: {
      peaks: PEAKS_PAYLOAD as any,
      indexAnswer: {
        result: { candidates: [MEDIUM_CANDIDATE], diagnostics: [], quality: null },
        adopt: [{ allowed: false, why: "confidence is 'medium' (shift_allowance_assumed); only the one candidate best_or_none() returns can be adopted" }],
        refuting_caveats: ["predicted_but_absent"], running: false,
      },
      run: IDLE_RUN as any, busy: false,
    } });
    await flush();

    const adopt = button("Adopt")!;
    // the gate does not leak into the UI: the button follows the server's arm
    expect(adopt.disabled).toBe(true);
    expect(adopt.title).toContain("medium");
    expect(host.textContent).toContain("the list below is ranked, not chosen");
  });

  it("enables Adopt only when the server's arm allows, and sends the candidate", async () => {
    const stub = server({
      "/api/index/adopt": (call: Call) => ({ body: { node_id: "n0007", mode: "lebail",
        api_call: `session.adopt_candidate(${call.body.candidate})` } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(Peaks, { target: host, props: {
      peaks: PEAKS_PAYLOAD as any,
      indexAnswer: {
        result: { candidates: [{ ...MEDIUM_CANDIDATE, confidence: "high",
                                 confidence_caveats: [] }],
                  diagnostics: [], quality: null },
        adopt: [{ allowed: true, why: "" }],
        refuting_caveats: [], running: false,
      },
      run: IDLE_RUN as any, busy: false,
    } });
    await flush();

    const adopt = button("Adopt")!;
    expect(adopt.disabled).toBe(false);
    expect(host.textContent).toContain("best_or_none()");
    adopt.click();
    await flush();
    expect(stub.calls.find((c) => c.path === "/api/index/adopt")?.body)
      .toEqual({ candidate: 0 });
  });
});

// ----------------------------------------------------------------------
// WP-1027 — the extinction screen (WP-1025 served)
// ----------------------------------------------------------------------
const SCREEN_CLASS = (extra: Record<string, unknown> = {}) => ({
  symbol: "P 63/m - -", representative: "P 63/m", space_groups: ["P 63", "P 63/m"],
  conditions: ["00l: l = 2n"], conditions_complete: true, n_lines: 40,
  n_absent: 6, n_testable: 4, n_present: 0, forbidden_hkl: [], forbidden_two_theta: [],
  rwp: 0.09, gof: 1.2, chi2: 100, delta_bic: -14.2, absences_rejected: false,
  screened: true, refuted: false, refuted_reason: null, diagnostics: [],
  ...extra,
});

const EXTINCTION = (best: number | null) => ({
  result: {
    candidates: [
      SCREEN_CLASS(),
      SCREEN_CLASS({ symbol: "P - - -", representative: "P 6/m", n_absent: 0,
                     n_testable: 0, space_groups: ["P 6/m", "P 6/m m m"], delta_bic: 0 }),
      SCREEN_CLASS({ symbol: "P 63/m c m", representative: "P 63/m c m",
                     space_groups: ["P 63 c m"], refuted: true, screened: false,
                     refuted_reason: "intensity at 2 forbidden positions",
                     n_present: 2, forbidden_hkl: [[0, 0, 1], [0, 0, 3]],
                     forbidden_two_theta: [10.51, 31.72] }),
      // unrefuted but never fitted (a max_classes cap): the unasked question
      SCREEN_CLASS({ symbol: "P 63/m m c", representative: "P 63/m m c",
                     space_groups: ["P 63 m c"], screened: false, delta_bic: 0 }),
    ],
    lattice_group: "P 6/m m m", cell: [3, 3, 5, 90, 90, 120], system: "hexagonal",
    centring: "P", wavelength: 1.5406, two_theta_range: [5.0, 90.0],
    n_classes: 4, n_screened: 2, status: "converged",
    diagnostics: [{ level: "info", code: "EXTINCTION_GROUPS_NOT_SEPARABLE",
                    message: "the class members produce identical patterns" }],
  },
  candidate: 0,
  best,
  running: false,
});

describe("the extinction screen table (WP-1027)", () => {
  it("ranks classes, lists every space group, and keeps chips inert without the adopt verdict", async () => {
    vi.stubGlobal("fetch", server({}).fetcher);
    app = mount(Peaks, { target: host, props: {
      peaks: PEAKS_PAYLOAD as any,
      indexAnswer: {
        result: { candidates: [MEDIUM_CANDIDATE], diagnostics: [], quality: null },
        adopt: [{ allowed: false, why: "confidence is 'medium'" }],
        refuting_caveats: [], running: false,
      },
      extinction: EXTINCTION(null),
      run: IDLE_RUN as any, busy: false,
    } });
    await flush();

    // the gate's abstention is the headline, not an error
    expect(host.textContent).toContain("No class is singled out");
    // every class row: the symbol, the refutation with its hkl, the unfitted cap
    expect(host.textContent).toContain("P 63/m - -");
    expect(host.textContent).toContain("refuted");
    expect(host.textContent).toContain("(001) 10.51°");
    expect(host.textContent).toContain("not screened");
    // both members of the class render — the singleton is unmeasurable…
    expect(host.textContent).toContain("P 63/m");
    expect(host.textContent).toContain("P 63");
    // …and with the candidate not adoptable, no space-group chip is a button
    expect(button("P 63")).toBeFalsy();
    // the not-separable info must be shown (it is information, not a footnote)
    expect(host.textContent).toContain("EXTINCTION_GROUPS_NOT_SEPARABLE");
  });

  it("adopts in a chosen space group when the server's arm allows", async () => {
    const stub = server({
      "/api/index/adopt": (call: Call) => ({ body: { node_id: "n0009", mode: "lebail",
        api_call: `session.adopt_candidate(${call.body.candidate}, space_group=${call.body.space_group})` } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(Peaks, { target: host, props: {
      peaks: PEAKS_PAYLOAD as any,
      indexAnswer: {
        result: { candidates: [{ ...MEDIUM_CANDIDATE, confidence: "high",
                                 confidence_caveats: [] }],
                  diagnostics: [], quality: null },
        adopt: [{ allowed: true, why: "" }],
        refuting_caveats: [], running: false,
      },
      extinction: EXTINCTION(0),
      run: IDLE_RUN as any, busy: false,
    } });
    await flush();

    expect(host.textContent).toContain("best_or_none()");
    const chip = button("P 63/m")!;
    expect(chip).toBeTruthy();
    chip.click();
    await flush();
    expect(stub.calls.find((c) => c.path === "/api/index/adopt")?.body)
      .toEqual({ candidate: 0, space_group: "P 63/m" });
    // a refuted class's members never act, whatever the verdict
    expect(button("P 63 c m")).toBeFalsy();
  });
});
