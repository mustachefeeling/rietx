import { unpack } from "rxplot";
import { describe, expect, it } from "vitest";

import { pack } from "../test-curves";
import { sameGrid, windowOf } from "./pattern";

/** A curves body as the route sends one, unpacked as the panel unpacks it. */
function body(header: Record<string, unknown>, arrays: Record<string, Float64Array | Int32Array>) {
  return unpack(pack(header, arrays));
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
    const plain = (a: ArrayLike<number> | undefined) => Array.from(a ?? []);
    expect(w.raw).toBeUndefined();
    expect(plain(w.two_theta)).toEqual([5.5, 6]);
    expect(plain(w.y_obs)).toEqual([20, 30]);
    // the model's arrays are the payload's own views: nothing of them is copied
    expect(w.y_calc).toBe(c.arrays.y_calc);
    expect(w.cumulative_chi2).toBe(c.arrays.cumulative_chi2);
    // no background in the payload is an empty curve, which is what hides its toggle
    expect(plain(w.y_background)).toEqual([]);
    expect(plain(w.excluded!.two_theta)).toEqual([5, 6.5]);
    expect(plain(w.excluded!.y_obs)).toEqual([10, 40]);
    expect(w.n_excluded).toBe(2);
    expect(w.ticks).toEqual({ a: [5.5] });
  });

  it("draws the pattern alone before a fit, split by the protocol's mask", () => {
    const w = windowOf(body({ fit: false, weighted: false }, {
      two_theta: f64(5, 6, 7), y_obs: f64(1, 2, 3), kept: i32(0, 1),
    }));
    expect(w.raw).toBe(true);
    expect(Array.from(w.two_theta)).toEqual([5, 6]);
    expect(Array.from(w.excluded!.two_theta)).toEqual([7]);
    expect(Array.from(w.excluded!.y_obs)).toEqual([3]);
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
