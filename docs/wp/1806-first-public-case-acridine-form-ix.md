# WP-1806 — first public case: acridine form IX

Milestone: rigid-bodies · Status: ⬜
Depends on: 1805
Priority: P3 2026-10-06 — the first real-data proof of the body; nothing waits on it but WP-1810

## Goal

A rigid body over acridine form IX's 14 non-H atoms refines against the deposited
pattern and lands every body atom within the published coordinate esds. This is chunk R4
of issue #561, sized M.

## Context

- Data: COD 2242872 (CC0; NSLS X16C, 0.6998 Å; Stephens et al. 2019). Origin and
  orientation free, no torsions.
- The deposited intensities are background-subtracted, so the test holds the background
  at zero and says so.
- **The bar stays the published esds** (re-affirmed 2026-10-06). An outside spike,
  reported on #561 on 2026-10-06, found two obstacles. This WP clears both first:
  1. The pdCIF reader refuses this file's `_pd_proc_intensity_net` with
     `_pd_proc_ls_weight` columns. The fix lands in `io/` under that subtree's rules
     (`src/rietx/io/CLAUDE.md`).
  2. With a plain profile the body landed 0.09–0.10 Å RMS from the deposited atoms. A
     start 10° and 0.3 Å off reached the same minimum to 0.04 Å. So the authors'
     profile is needed: anisotropic Stephens strain and a high-order background, read
     from the paper.
- The deposited model may not be a rigid body. Measure the best rigid superposition of
  the template onto the deposited atoms before setting the test's tolerance, and record
  it. If that floor exceeds the published esds, bring the number back to the
  maintainer before loosening anything.

## Non-goals

- Hydrogens (WP-1810), torsions (WP-1808).

## Tasks

- [ ] pdCIF reader: accept the net-intensity and weight columns, with a diagnostic where it repairs
- [ ] The data file and a provenance row in `tests/data/README.md`
- [ ] The authors' profile; the template-superposition floor, measured and recorded
- [ ] The acceptance test + obs/calc/diff PNGs to `tests/output/`
- [ ] Skill: none expected; say why at handover

## Acceptance

- Every body atom lies within the published coordinate esds, and the cell matches the
  published cell.
- An intra-body distance reports `None` (through `VARIANCE_CANCELLATION_FLOOR`), and an
  inter-body one reports a full esd.
- The provenance row exists.

## References

- Stephens et al. (2019), *Acta Cryst.* E75, 489.
- Issue #561; PR #596.

## Handover log

- **2026-10-06** — created by WP-1803's re-cut. The maintainer kept the
  published-esd bar, so the reader fix and the authors' profile are tasks here and the
  size grows from S to M.
