/**
 * A curves body in `rietx.viz.packed`'s layout, as `/api/result/curves` sends
 * one (WP-1461, D4): a little-endian uint32 header length, the JSON header,
 * then 8-aligned arrays the header lists. Float64 unless an array is an
 * `Int32Array`, as the route's index arrays are.
 */
export function pack(header: Record<string, unknown>,
                     arrays: Record<string, ArrayLike<number>>): ArrayBuffer {
  const typed = Object.entries(arrays).map(([name, a]) =>
    [name, a instanceof Int32Array ? a : Float64Array.from(a)] as const);
  const specs: object[] = [];
  let offset = 0;
  for (const [name, a] of typed) {
    specs.push({ name, dtype: a instanceof Int32Array ? "<i4" : "<f8", offset, length: a.length });
    offset += Math.ceil(a.byteLength / 8) * 8;
  }
  let head = JSON.stringify({ ...header, arrays: specs });
  head += " ".repeat((8 - ((4 + head.length) % 8)) % 8);
  const buffer = new ArrayBuffer(4 + head.length + offset);
  new DataView(buffer).setUint32(0, head.length, true);
  new Uint8Array(buffer, 4).set(new TextEncoder().encode(head));
  let at = 4 + head.length;
  for (const [, a] of typed) {
    new Uint8Array(buffer, at).set(new Uint8Array(a.buffer, a.byteOffset, a.byteLength));
    at += Math.ceil(a.byteLength / 8) * 8;
  }
  return buffer;
}
