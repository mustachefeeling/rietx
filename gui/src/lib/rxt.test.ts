/**
 * The `.rxt` highlighter — colours only, and provably no opinion about validity.
 *
 * WP-1009 put the parser on the server so there would be one grammar.  The
 * frontend still has to *colour* the document, which is a second reading of the
 * same text, so the property that keeps it honest is negative: this scanner has
 * no way to say "wrong".  There is no `error` token to emit, garbage tokenizes
 * without complaint, and every problem the pane displays arrives from a `PUT`
 * response.  Those are asserted below, because a highlighter that starts
 * underlining what it does not recognise is a second parser wearing a costume.
 *
 * The vocabulary it *does* share with Python is pinned from the other side, in
 * `tests/test_textdoc.py::test_the_highlighter_quotes_the_parsers_words`.
 */
import { describe, expect, it } from "vitest";

import { KEYWORDS, TOKENS, commentLines, spans, type Token } from "./rxt";

/** `[token, text]` pairs, which is what a colour assertion actually reads as. */
function tokens(line: string): Array<[Token, string]> {
  return spans(line).map((span) => [span.token, line.slice(span.from, span.to)]);
}

describe("the scanner", () => {
  it("colours a settings line", () => {
    expect(tokens('project "doc"')).toEqual([["keyword", "project"], ["string", '"doc"']]);
    expect(tokens("mode rietveld")).toEqual([["keyword", "mode"], ["path", "rietveld"]]);
    expect(tokens("limits 3 60")).toEqual([
      ["keyword", "limits"], ["number", "3"], ["number", "60"]]);
  });

  it("colours a parameter row, mark and annotations", () => {
    expect(tokens("  cell.a        @ 4.1606  min 0.1")).toEqual([
      ["path", "cell.a"], ["vary", "@"], ["number", "4.1606"],
      ["annotation", "min"], ["number", "0.1"]]);
  });

  it("reads a tie as one path after the operator", () => {
    // `=` runs to end of line by grammar decision (WP-1009), and the path after
    // it must not colour as six things
    expect(tokens("  cell.b          4.1606  = 1·phases.0.cell.a")).toEqual([
      ["path", "cell.b"], ["number", "4.1606"], ["operator", "="], ["number", "1"],
      ["operator", "·"], ["path", "phases.0.cell.a"]]);
  });

  it("colours the flag words and keeps the hyphen in mode-fixed", () => {
    expect(tokens("  atoms.0.biso     0.5  locked")).toEqual([
      ["path", "atoms.0.biso"], ["number", "0.5"], ["flag", "locked"]]);
    expect(tokens("  scale   1  mode-fixed  softplus")).toEqual([
      ["path", "scale"], ["number", "1"], ["flag", "mode-fixed"], ["flag", "softplus"]]);
  });

  it("colours a stage line's globs and keywords", () => {
    expect(tokens("stage cell  free phases.*.cell.*, instrument.zero_shift")).toEqual([
      ["keyword", "stage"], ["path", "cell"], ["annotation", "free"],
      ["path", "phases.*.cell.*"], ["operator", ","], ["path", "instrument.zero_shift"]]);
    expect(tokens("stage seed_it  free a  seed 0.001  max_iter 40")).toEqual([
      ["keyword", "stage"], ["path", "seed_it"], ["annotation", "free"], ["path", "a"],
      ["annotation", "seed"], ["number", "0.001"],
      ["annotation", "max_iter"], ["number", "40"]]);
  });

  it("reads an infinite bound as a number, not as a parameter called inf", () => {
    expect(tokens("  zero_shift  0  min -inf  max inf")).toEqual([
      ["path", "zero_shift"], ["number", "0"],
      ["annotation", "min"], ["number", "-inf"],
      ["annotation", "max"], ["number", "inf"]]);
    // …but a name that merely starts with those letters is still a name
    expect(tokens("  information  1")).toEqual([["path", "information"], ["number", "1"]]);
  });

  it("takes a comment to end of line, whatever it contains", () => {
    const line = 'pattern "synth.xye"   # xy · sha256 19b265… · 3–23.995° · σ from file';
    expect(tokens(line)).toEqual([
      ["keyword", "pattern"], ["string", '"synth.xye"'],
      ["comment", "# xy · sha256 19b265… · 3–23.995° · σ from file"]]);
  });

  it("only calls a keyword a keyword when it opens the line", () => {
    // there is no `instrument.mode` today, but the rule must not depend on that
    expect(tokens("  mode.x  1")).toEqual([["path", "mode.x"], ["number", "1"]]);
    expect(tokens("  plan  0.5")).toEqual([["path", "plan"], ["number", "0.5"]]);
    expect(tokens("plan mccusker_default")).toEqual([
      ["keyword", "plan"], ["path", "mccusker_default"]]);
  });

  it("emits spans in order, non-overlapping, inside the line", () => {
    const line = '  atoms.1.x       0.1993  = 0.1993 + 1·phases.0.atoms.1.dof.0   # B B';
    let at = 0;
    for (const span of spans(line)) {
      expect(span.from).toBeGreaterThanOrEqual(at);
      expect(span.to).toBeGreaterThan(span.from);
      expect(span.to).toBeLessThanOrEqual(line.length);
      at = span.to;
    }
  });
});

describe("the highlighter never claims validity", () => {
  it("has no error token to emit", () => {
    // the whole vocabulary, so adding one is this assertion failing rather than
    // a pane that contradicts the server
    expect([...TOKENS]).toEqual(["keyword", "vary", "number", "string", "comment",
                                 "annotation", "flag", "operator", "path"]);
    expect(TOKENS).not.toContain("error");
  });

  it("tokenizes nonsense without complaining", () => {
    // every one of these is a document the server would refuse; none of them may
    // produce anything but ordinary colours here
    for (const line of ["??? !!! %%%", "stage", "mode", "= = =", '"unterminated',
                        "phases.0.cell.a @@@ 4.16", "\u0000\u0001"]) {
      const got = spans(line);
      expect(got.every((span) => (TOKENS as readonly string[]).includes(span.token)))
        .toBe(true);
    }
  });

  it("leaves what it does not recognise uncoloured rather than marking it", () => {
    // `!` is in no rule: the scanner walks past it and claims nothing
    expect(tokens("a ! b")).toEqual([["path", "a"], ["path", "b"]]);
  });

  it("never throws, on any line of a real document or on any prefix of one", () => {
    const document = [
      "rxt 1", 'project "doc"', "mode rietveld", "limits none", "excluded none", "",
      "plan mccusker_default", "guard 0.98",
      "stage scale_bkg  free phases.*.scale, instrument.background.*", "",
      'phase 0 "LaB6"', "  cell.a        @ 4.1606  min 0.1",
      "  cell.alpha          90  locked", "instrument",
      "  background.c0                @      0",
    ];
    for (const line of document) {
      for (let n = 0; n <= line.length; n++) {
        expect(() => spans(line.slice(0, n))).not.toThrow();
      }
    }
  });
});

describe("commentLines", () => {
  it("counts lines carrying a comment, not `#` characters", () => {
    expect(commentLines("a\nb # one\n# two\n")).toBe(2);
    expect(commentLines('project "a#b"')).toBe(0);   // inside a string, not a comment
    expect(commentLines("")).toBe(0);
  });

  it("is what tells the pane a re-render would drop the user's notes", () => {
    const base = 'rxt 1\nproject "doc"\n';
    const annotated = 'rxt 1  # my note\nproject "doc"\n# checked 2026-07-30\n';
    expect(commentLines(annotated) - commentLines(base)).toBe(2);
  });
});

describe("the vocabulary", () => {
  it("carries every block name the parser recognises, reserved ones included", () => {
    // `peaks` is reserved for WP-1027 and already parses server-side; colouring
    // it now is what makes the reservation visible rather than a 404 later
    expect(KEYWORDS).toContain("peaks");
    expect(tokens("peaks 20")).toEqual([["keyword", "peaks"], ["number", "20"]]);
  });
});
