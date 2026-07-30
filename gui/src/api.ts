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

  params: () => call("GET", "/api/params"),
  patchParams: (delta: { values?: Record<string, number>; vary?: Record<string, boolean> }) =>
    call("PATCH", "/api/params", delta),
  plan: () => call("GET", "/api/plan"),
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
  report: () => call("GET", "/api/report"),

  history: () => call("GET", "/api/history"),
  checkout: (nodeId: string) => call("POST", "/api/history/checkout", { node_id: nodeId }),

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
