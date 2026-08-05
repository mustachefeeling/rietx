import { describe, expect, it } from "vitest";

import { advance, consoleLine, stageProgress, type EngineEvent, type RunState } from "./stream";

const event = (seq: number, kind: string, data: Record<string, any> = {}): EngineEvent => ({
  seq,
  kind,
  t: 1750000000,
  data,
});

const state = (over: Partial<RunState["run"]> = {}, s: RunState["state"] = "running"): RunState => ({
  state: s,
  run: {
    kind: "fit",
    status: null,
    stage: null,
    stage_index: null,
    n_stages: null,
    rwp: null,
    gof: null,
    node_id: null,
    completed_stages: [],
    error: null,
    ...over,
  },
  project: "/tmp/x.pxrd",
  head: "n0003",
});

describe("cursor", () => {
  it("advances to the last seq in the batch", () => {
    const cursor = advance({ seq: 0, dropped: 0 }, { events: [event(1, "eval"), event(2, "eval")], oldest: 1 });
    expect(cursor).toEqual({ seq: 2, dropped: 0 });
  });

  it("counts frames the server's ring dropped", () => {
    // we asked from seq 5; the oldest the server still holds is 9, so 5..8 are gone
    const cursor = advance({ seq: 5, dropped: 0 }, { events: [event(9, "eval")], oldest: 9 });
    expect(cursor).toEqual({ seq: 9, dropped: 3 });
  });

  it("never moves backwards on an empty batch", () => {
    const cursor = advance({ seq: 7, dropped: 1 }, { events: [], next: 7, oldest: 8 });
    expect(cursor).toEqual({ seq: 7, dropped: 1 });
  });
});

describe("progress", () => {
  it("reads the 1-based stage index the engine emits", () => {
    expect(stageProgress(state({ stage_index: 1, n_stages: 5 }))).toBe(0);
    expect(stageProgress(state({ stage_index: 5, n_stages: 5 }))).toBeCloseTo(0.8);
  });

  it("is null before a stage has started", () => {
    expect(stageProgress(state())).toBeNull();
  });
});

describe("console lines", () => {
  it("renders whatever fields arrive, since data is an open dict", () => {
    const line = consoleLine(event(3, "stage_start", { stage: "cell", index: 3, n_stages: 5, freed: ["a", "b"] }));
    expect(line).toContain("stage_start");
    expect(line).toContain("stage=\"cell\"");
    expect(line).toContain("index=3");
    expect(line).toContain("freed=[2]");
  });

  it("survives a kind it has never seen with no data at all", () => {
    expect(consoleLine(event(4, "future_kind"))).toContain("future_kind");
  });

  it("folds a series stamp into a prefix rather than five fields", () => {
    // Found in a browser (WP-1016): a series stamps five keys onto *every*
    // event, `eval` included, and rendering them as fields pushed the cost and
    // the evaluation counter off the right edge of the console — every line read
    // `series_index=0 series_label="T300" series_n=3 series_p…`.
    const line = consoleLine(event(5, "eval", {
      series_index: 0, series_label: "T300", series_n: 3,
      series_pass: "forward", n_eval: 12, cost: 1.5 }));
    expect(line).toContain("[T300 1/3]");
    expect(line).toContain("n_eval=12");
    expect(line).toContain("cost=1.5");
    expect(line).not.toContain("series_index");
    expect(line).not.toContain("series_pass");
  });

  it("marks the verification pass and a cold restart in the prefix", () => {
    // both are second fits of a pattern already counted, so a transcript that
    // did not distinguish them would read as a restart and as a duplicate
    expect(consoleLine(event(6, "fit_start", {
      series_index: 1, series_label: "T400", series_n: 3,
      series_pass: "backward" }))).toContain("[T400 2/3 \u21a9]");
    expect(consoleLine(event(7, "fit_start", {
      series_index: 1, series_label: "T400", series_n: 3,
      series_pass: "forward", series_cold: true }))).toContain("[T400 2/3 \u2744]");
  });

  it("leaves an unstamped event exactly as it was", () => {
    const line = consoleLine(event(8, "stage_start", { stage: "cell" }));
    expect(line).not.toContain("[");
  });
});
