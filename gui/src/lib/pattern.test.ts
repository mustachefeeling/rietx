import { unpack } from "rxplot";
import { describe, expect, it } from "vitest";

import { chartChoice } from "./plot";
import { sameGrid, windowOf } from "./pattern";

/** A curves body in `rietx.viz.packed`'s layout, as the route sends one. */
function body(header: Record<string, unknown>, arrays: Record<string, Float64Array | Int32Array>) {
  const specs: object[] = [];
  let offset = 0;
  for (const [name, a] of Object.entries(arrays)) {
    specs.push({ name, dtype: a instanceof Float64Array ? "<f8" : "<i4", offset, length: a.length });
    offset += Math.ceil(a.byteLength / 8) * 8;
  }
  let head = JSON.stringify({ ...header, arrays: specs });
  head += " ".repeat((8 - ((4 + head.length) % 8)) % 8);
  const buffer = new ArrayBuffer(4 + head.length + offset);
  new DataView(buffer).setUint32(0, head.length, true);
  new Uint8Array(buffer, 4).set(new TextEncoder().encode(head));
  let at = 4 + head.length;
  for (const a of Object.values(arrays)) {
    new Uint8Array(buffer, at).set(new Uint8Array(a.buffer));
    at += Math.ceil(a.byteLength / 8) * 8;
  }
  return unpack(buffer);
}

const f64 = (...v: number[]) => Float64Array.from(v);
const i32 = (...v: number[]) => Int32Array.from(v);

describe("the chart module's payload in the window's shape", () => {
  it("puts a fit on its channels and the masked ones on their own arm", () => {
    const c = body({ fit: true, weighted: true, stale: false, ticks: { a: [5.5] }, tick_hkl: { a: [[1, 0, 0]] } }, {
      two_theta: f64(5, 5.5, 6, 6.5), y_obs: f64(10, 20, 30, 40), kept: i32(1, 2),
      fitted: i32(1, 2), y_calc: f64(21, 29), delta: f64(-1, 1), delta_raw: f64(-1, 1),
      cumulative_chi2: f64(1, 2),
    });
    const w = windowOf(c);
    expect(w.raw).toBeUndefined();
    expect(w.two_theta).toEqual([5.5, 6]);
    expect(w.y_obs).toEqual([20, 30]);
    expect(w.y_calc).toEqual([21, 29]);
    // no background in the payload is an empty curve, which is what hides its toggle
    expect(w.y_background).toEqual([]);
    expect(w.excluded).toEqual({ two_theta: [5, 6.5], y_obs: [10, 40] });
    expect(w.n_excluded).toBe(2);
    expect(w.ticks).toEqual({ a: [5.5] });
  });

  it("draws the pattern alone before a fit, split by the protocol's mask", () => {
    const w = windowOf(body({ fit: false, weighted: false }, {
      two_theta: f64(5, 6, 7), y_obs: f64(1, 2, 3), kept: i32(0, 1),
    }));
    expect(w.raw).toBe(true);
    expect(w.two_theta).toEqual([5, 6]);
    expect(w.excluded).toEqual({ two_theta: [7], y_obs: [3] });
  });

  it("keeps the view only over the same channels", () => {
    const a = body({ fit: false }, { two_theta: f64(5, 6, 7), y_obs: f64(1, 2, 3), kept: i32(0) });
    const b = body({ fit: false }, { two_theta: f64(5, 6, 7), y_obs: f64(3, 2, 1), kept: i32(1) });
    const other = body({ fit: false }, { two_theta: f64(5, 6, 8), y_obs: f64(1, 2, 3), kept: i32(0) });
    expect(sameGrid(a, b)).toBe(true);
    expect(sameGrid(a, other)).toBe(false);
    expect(sameGrid(null, b)).toBe(false);
  });
});

describe("the renderer is chosen by the page's query string", () => {
  it("is plotly unless asked for the chart module", () => {
    expect(chartChoice("")).toEqual({ uplot: false, markers: "all" });
    expect(chartChoice("?chart=uplot")).toEqual({ uplot: true, markers: "all" });
    expect(chartChoice("?chart=uplot&markers=thin")).toEqual({ uplot: true, markers: "thin" });
  });
});
