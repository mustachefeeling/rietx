/**
 * Cross-language parity: this matcher against Python's, case by case.
 *
 * The corpus is written by `tests/test_gui_fnmatch.py` from
 * `fnmatch.fnmatchcase` — the function `ParameterTable.set_vary` calls — over a
 * live parameter vocabulary, and is committed so this suite can run on a machine
 * that never installed the package.  Read with `fs` rather than imported, because
 * it lives outside the vite root on purpose: one authority, in the language that
 * owns the semantics, consumed by both sides.
 *
 * A failure here is not "the test is wrong": it means the table's preview and the
 * server's `set_vary` would select different parameters.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { fnmatch, fnmatchAny } from "./fnmatch";

interface Corpus {
  paths: string[];
  patterns: Array<{ pattern: string; matches: number[] }>;
}

const corpus: Corpus = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../../tests/data/gui/fnmatch_cases.json", import.meta.url)),
    "utf-8",
  ),
);

describe("fnmatch parity with Python", () => {
  it("agrees on every (pattern, path) pair in the corpus", () => {
    const disagreements: string[] = [];
    for (const { pattern, matches } of corpus.patterns) {
      const expected = new Set(matches);
      corpus.paths.forEach((path, index) => {
        const got = fnmatch(path, pattern);
        if (got !== expected.has(index)) {
          disagreements.push(`${pattern} × ${path}: python=${expected.has(index)} ts=${got}`);
        }
      });
    }
    expect(disagreements).toEqual([]);
  });

  it("covers the corpus it claims to — a vacuous pass is the failure mode", () => {
    expect(corpus.paths.length).toBeGreaterThan(60);
    expect(corpus.patterns.length).toBeGreaterThan(20);
    const total = corpus.patterns.reduce((n, entry) => n + entry.matches.length, 0);
    expect(total).toBeGreaterThan(100);
  });

  it("crosses dot separators, because Python's `*` does", () => {
    // `phases.*` selecting every path under phase 0 is a property of the
    // package's globs, and the reason `phases.*.cell.*` has to spell the depth
    expect(fnmatch("phases.0.atoms.3.biso", "phases.*")).toBe(true);
    expect(fnmatch("phases.0.cell.a", "phases.*.cell.*")).toBe(true);
  });

  it("matches any of several globs, as set_vary's list argument does", () => {
    const globs = ["phases.*.cell.*", "instrument.profile.*"];
    expect(fnmatchAny("instrument.profile.w", globs)).toBe(true);
    expect(fnmatchAny("phases.0.scale", globs)).toBe(false);
  });
});
