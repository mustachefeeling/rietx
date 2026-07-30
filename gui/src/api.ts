/** The HTTP surface as typed calls, and the one place an error envelope is read.
 *
 * Every route answers `{...}` on success or `{error: {code, message, where,
 * details}}` with a 4xx/5xx status, so this module turns a refusal into a thrown
 * `ApiError` carrying the *code* — which is what callers branch on.  Two codes
 * are not failures in the UI sense and are named here so panels can say so:
 * `RUN_IN_FLIGHT` (a mutating verb during a run — disable the control, do not
 * toast) and `NO_RESULT` / `NO_PROJECT` (an empty state, not an error).
 */

export class ApiError extends Error {
  code: string;
  status: number;
  where: string[];
  details: Array<{ line?: number; message: string; where?: string; text?: string }>;

  constructor(status: number, payload: any) {
    const error = payload?.error ?? {};
    super(error.message ?? `HTTP ${status}`);
    this.code = error.code ?? "HTTP_ERROR";
    this.status = status;
    this.where = error.where ?? [];
    this.details = error.details ?? [];
  }

  /** True when the refusal is "a run is in flight", not "you did it wrong". */
  get busy(): boolean {
    return this.code === "RUN_IN_FLIGHT";
  }

  /** True when there is simply nothing to show yet. */
  get empty(): boolean {
    return this.code === "NO_RESULT" || this.code === "NO_PROJECT";
  }
}

async function call(method: string, path: string, body?: unknown): Promise<any> {
  const init: RequestInit = { method, headers: {} };
  if (body !== undefined) {
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const response = await fetch(path, init);
  const text = await response.text();
  let payload: any = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { error: { code: "BAD_RESPONSE", message: text.slice(0, 200) } };
  }
  if (!response.ok) throw new ApiError(response.status, payload);
  return payload;
}

export const api = {
  capabilities: () => call("GET", "/api/capabilities"),
  version: () => call("GET", "/api/version"),
  recent: () => call("GET", "/api/recent"),

  project: () => call("GET", "/api/project"),
  openProject: (path: string) => call("POST", "/api/project/open", { path }),
  patchProject: (settings: Record<string, unknown>) => call("POST", "/api/project", settings),
  /** A flush a client may call and never must: every settings verb already
   *  saved and the model was on disk the moment its node was appended. */
  save: () => call("POST", "/api/project/save"),

  params: () => call("GET", "/api/params"),
  patchParams: (delta: { values?: Record<string, number>; vary?: Record<string, boolean> }) =>
    call("PATCH", "/api/params", delta),
  plan: () => call("GET", "/api/plan"),
  /** Either `{preset: name}` or `{plan: spec}` — a preset is stored *expanded
   *  through the mode*, so what comes back is what will actually run. */
  putPlan: (body: { preset?: string; plan?: unknown }) => call("PUT", "/api/plan", body),
  plans: () => call("GET", "/api/plans"),

  run: (body: Record<string, unknown> = { kind: "fit" }) => call("POST", "/api/run", body),
  cancel: () => call("POST", "/api/cancel"),
  runState: () => call("GET", "/api/run/state"),

  result: () => call("GET", "/api/result"),
  /** Decimated curves for a 2θ window.  Server-side on purpose: it uses the
   *  same min/max decimation the comparison UI does, so a plot here and a plot
   *  there cannot disagree about which points survive. */
  window: (lo?: number, hi?: number, maxPoints = 4000) => {
    const query = new URLSearchParams({ max_points: String(maxPoints) });
    if (lo !== undefined) query.set("lo", String(lo));
    if (hi !== undefined) query.set("hi", String(hi));
    return call("GET", `/api/result/window?${query}`);
  },
  /** The three layers **plus** an `apply` arm parallel to `suggested_actions`:
   *  whether the server would act on each one, and what it would run.  Idle-only
   *  (Layers 1-2 read the compiled model a stage would be rewriting), so this
   *  answers 409 `RUN_IN_FLIGHT` mid-run. */
  report: () => call("GET", "/api/report"),
  /** Carry out one suggestion, as one stage, through the run machinery.
   *  `paths` disambiguates when a report suggests one kind twice (two textured
   *  phases); the server refuses rather than guessing if it is omitted. */
  applyAction: (kind: string, paths?: string[]) =>
    call("POST", "/api/report/apply", paths ? { kind, paths } : { kind }),

  history: () => call("GET", "/api/history"),
  checkout: (nodeId: string) => call("POST", "/api/history/checkout", { node_id: nodeId }),
  /** Checkout **plus** a tag: this DAG has only `head` and tags, so "branch"
   *  names a fork point rather than creating a ref (WP-1008). */
  branch: (nodeId: string, name: string) =>
    call("POST", "/api/history/branch", { node_id: nodeId, name }),
  tag: (nodeId: string, name: string) =>
    call("POST", "/api/history/tag", { node_id: nodeId, name }),
  annotate: (nodeId: string, body: { label?: string; notes?: Record<string, string> }) =>
    call("POST", "/api/history/annotate", { node_id: nodeId, ...body }),
  /** Parameter values that differ between two nodes — the question a compare view
   *  actually has, and the reason a node's ~10 kB state is not in `/api/history`. */
  historyDiff: (a: string, b: string) =>
    call("GET", `/api/history/diff?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  historyCompare: (ids: string[]) =>
    call("GET", `/api/history/compare?ids=${encodeURIComponent(ids.join(","))}`),

  textdoc: () => call("GET", "/api/textdoc"),
  putTextdoc: (text: string, baseRevision?: string, validateOnly = false) =>
    call("PUT", "/api/textdoc", {
      text,
      base_revision: baseRevision,
      validate_only: validateOnly,
    }),

  export: (kind: string) => call("POST", `/api/export/${kind}`),
  events: (since: number) => call("GET", `/api/events?poll=1&since=${since}`),
};
