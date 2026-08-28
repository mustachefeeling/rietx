# WP-1217 — History: the graph and the compare table

Milestone: v1.2 · Status: ⬜
Depends on: WP-1201

## Goal

The history graph reads like a git graph (an edge runs down its lane and
crosses over exactly one row), and the compare table's numbers hold their
columns, with the difference given both absolute and as a percentage.

## Context

The user: "use a git-style graphical tree design rather than straight lines
connecting the nodes; if nodes are very far away, the shallow line is ugly
and hard to read"; "the numerical column positions can be disrupted based on
how many digits are in the number; control this somehow, perhaps with
scientific notation; the difference value should be given as both absolute
and percentage."

Findings (2026-08-25):

- The graph is a CSS row list (`.node`, `height: var(--row)`, 26 px) over an
  absolutely positioned SVG rail (`History.svelte:205-250, 373-377`); lanes
  are assigned by `layout()` in `lib/history.ts:75-108` (one forward pass;
  a node takes a parent's lane, a fork opens a lane, a merge frees one) and
  `LANE = 14`. `edgePath` (`History.svelte:173-179`) draws a straight line
  within a lane and otherwise **one cubic Bézier spanning the whole vertical
  gap** between the two rows, so a child ten rows below its parent in
  another lane gets the shallow curve the user saw. Merge edges are dashed.
- Compare fires `historyDiff` and `historyCompare` together
  (`History.svelte:137-148`); the diff is `RefinementTree.diff`
  (`history/tree.py:257-273`, only paths differing at `rtol=1e-12`, `None`
  where absent). Rows render `a.toPrecision(7)`, `b.toPrecision(7)` and a
  signed absolute `delta.toPrecision(3)` (`History.svelte:315-324`) in
  74 px columns (`:565-568`); JS picks fixed or exponential per cell, so a
  cell edge and a scale sit in one column at different widths. No
  percentage; the list is cut at 200 rows silently; ranking is by
  `|Δ|/max(|a|,|b|)` (`lib/history.ts:178-194`), which is never shown.
- The per-node Rwp delta badge is a percentage-point difference with a
  glyph for sign (`History.svelte:235-241`); `pct()` at `:181-183`.
- `formatValue(value, esd)` (`lib/table.ts:279-311`) formats to the esd's
  place; a node's params rows carry esds after a fit.

Design: `edgePath` runs vertically in the source lane to the row above the
target and crosses in the last row (or crosses in the first row when the
child's lane opens there, whichever the lane algorithm implies), so no
segment spans more than one row diagonally; lanes get colours from the
OKLab rotation. The compare table formats each side by a per-family place
count (cell 5, coordinates 5, Biso 3, scale exponential), right-aligned
tabular numerals so the decimal points line up within a family; `Δ` absolute
in the same format and `Δ %` relative to `a` (`—` when `a` is 0); "showing 200
of N, ranked by relative change" said out loud.

**No esd is reachable here** (checked 2026-08-28, which is why the design line
above lost its `formatValue` half): `RefinementTree.diff` builds a
`ParameterTable` from each node's stored `Structure`/`Instrument` and reads
`entry.value`, and neither schema carries an esd — a node stores *state*, and
the esds a fit produced live on its `RefinementResult`. Merging them in would
be a new arm on `/api/history/diff`, which is this WP's non-goal. Hence the
place count is the whole answer rather than the fallback.

The three widths this table needs are `lib/history.ts`'s `VALUE_CHARS`,
`PERCENT_CHARS` and `PATH_CHARS`, handed to the CSS as `--w-val`/`--w-pct`/
`--w-path` — WP-1216's rule at this table's scale, and the reason there is no
arithmetic to cross: the formatters *keep* the width (a rendering too long for
its family's places falls back to exponential rather than pushing the column),
which is what `history.test.ts` checks over every family against a spread of
magnitudes.

## Non-goals

- New history verbs; the tree payload's shape.

## Tasks

- [x] `lib/history.ts`: `edgeSegments(edge)` returning the vertical run and
      the one-row crossing; lane colours; `history.test.ts` pins that no
      segment is diagonal over more than one row on a fixture with a
      ten-row gap.
- [x] Compare formatting in `lib/history.ts` (`formatSide`, `formatDelta`,
      `formatPercent`, family place counts); the table on aligned columns;
      the cap notice.
- [ ] Browser pass on a tree with a branch and a merge; dist.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1012 (the panel), WP-1029 (OKLab rotation).

## Handover log

- **2026-08-25** — created from the v1.2 triage.
