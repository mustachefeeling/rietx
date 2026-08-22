# WP-1121 — the per-reflection front: what a compiled tier does not reach

Milestone: v1.1 · Status: ⬜
Depends on: 1115 (its gate reading is the decomposition this attacks)

## Goal

v1.1's cold-fit target is still missed. Close the gap, or measure why it
cannot be closed and say so — by attacking the two costs that survive
WP-1115's compiled tier: the **per-reflection scalar work** a Jacobian column
does before any plane is touched, and the **number of evaluations** the plan
asks for.

## Context

**Where the milestone stands.** The acceptance targets are in
`../milestones/v1.1.md` § Acceptance: warm-started series in the ~1 s/pattern
band (**reached**), cold trigger-shaped fit in low single-digit seconds
(**missed** — 8.86–8.99 s after 1115, from a 50 s opening baseline). Quote the
harness, never a remembered figure: `examples/bench_refinement.py`, best of
three, idle machine, venv and platform stamped.

**Why a fifth speed WP is not more of the same.** Every win so far has been on
*plane arithmetic* — 1112 batched the derivative bases, 1120 the residual, 1115
fused and threaded all three kernels. That seam is now ~2× off its numpy floor
and there is no third factor in it. What remains is a different shape of work,
and it is the reason this WP exists rather than a sixth kernel.

**The decomposition, measured before the tier landed** (1115 § Gate reading;
trigger cold fit, 17.1 s, shares stable to 0.8 pp across three runs at
different machine loads):

| seam | calls | s | ms/call | share |
|---|---|---|---|---|
| residual (forward) | 372 | 3.721 | 10.0 | 21.8 % |
| jacobian: bases | 290 | 5.833 | 20.1 | 34.1 % |
| jacobian: columns | 289 | 6.317 | 21.9 | 37.0 % |
| — of which plane accumulation | 9 788 | 3.630 | 0.37 | 21.2 % |
| — **of which perturbed `phase_peaks`** | **15 608** | **1.911** | **0.12** | **11.2 %** |
| `compile_model` | 8 | 0.175 | 21.9 | 1.0 % |
| scipy TRF + staged runner | | 1.049 | | 6.1 % |

**Those shares are stale in a specific and favourable-to-this-WP direction.**
1115 compiled the three plane rows and left the `phase_peaks` row untouched, so
its *absolute* 1.9 s is unchanged while the fit went 17.1 → 8.9 s. Its share
roughly doubles, to ~21 %, and it becomes the largest single line item that is
not plane arithmetic. **Re-measure before designing anything** — that is task 1,
and the number above is the "before", not the current state.

**What the cost actually is.** `_peak_chain_column` (`optimize/least_squares.py`)
perturbs θ_c, decodes, and calls `CompiledModel.phase_peaks` for every phase the
column touches, to finite-difference the per-reflection scalars — position,
the two widths, intensity. That is per-*reflection* work: no plane kernel
reaches it, and 1115's first projection over-read by 1.5× precisely because it
assumed the whole column seam fused like the bases.

**Three leads, none of them verified — the first task after re-measuring is to
falsify them, not to implement them.**

1. **The scalar memo is one deep.** `CompiledModel._memo` /
   `CompiledPhase.scalar_cache` holds `cache[slot] = (key, value)` — a single
   key per slot, not a map. A Jacobian walks columns in θ order, so any
   alternation between two keys evicts on every call and the memo returns
   nothing while still paying for the key build. Whether the column order
   actually alternates is measurable directly: instrument the hit rate per slot
   over one Jacobian.
2. **A column re-derives more than it perturbs.** `affected` is one phase for a
   `phases.N.…` path and *every* phase for an instrument path. For an
   instrument path that moves only positions, the widths and |F|² are
   recomputed unchanged; whether the existing memo already absorbs that is
   exactly lead 1's question.
3. **The FD is whole-`phase_peaks` where the chain is analytic in places.**
   `po_intensity_grad` and the structural columns already take analytic
   intensity derivatives (`_structural_column`, `_po_column`) instead of
   perturbing. How far that pattern extends is a scoping question, not a
   known win — and CLAUDE.md's rule holds: a new analytic branch is a claim
   about what one parameter *name* reaches, gated by `_column_extras`, and
   anything beyond its declared reach takes the whole-model FD column.

**The other unowned lead: WP-1113's preset flip, priced and unflipped.**
1113 measured intermediate stages at `ftol=1e-6` giving **1.5–1.7× fewer
whole-plan evaluations at ≤ 0.02 esd** of parameter movement, landed
`Stage.ftol` opt-in, and deliberately did **not** flip the presets — the price
is in its § Findings. That factor multiplies with anything this WP wins, and it
is a decision rather than an implementation. Nothing about it has changed;
what has changed is that it is now the cheapest remaining factor on the table.

**Fences already measured elsewhere — do not re-open.** GPU execution (46–182×
slower, launch-latency-bound, v0.4 record); `torch.compile` (2.5× slower after
38 s, WP-0605); `tr_solver='lsmr'` and the rest of the solver survey's §2 dead
ends; the peaks buffer (WP-1114, **no-go** on the numpy floor — though its
§ Findings note that a compiled *buffer* is the follow-on with the larger
algorithmic ceiling, 7.8–9× element volume on FCJ-heavy cases, if an exact
compiled kernel still misses. It does still miss. That is a real option here
and 1114 § Findings 3–4 list the three accuracy traps and the cache-keying bug
any implementation re-hits first).

### Inherited

- **From WP-1123 (2026-08-22), the tolerance flip — your baseline moved.**
  Every staged fit now stops its intermediate stages at ftol 1e-6
  (`RefinementPlan.intermediate_ftol`), so the harness numbers this WP starts
  from are **not** the ones in 1115's or 1120's handovers: on this branch's
  `[dev]` venv, darwin/arm64, cpd-1a 408 → **272** nfev (2.20-2.26 → 1.64-1.75 s),
  cpd-2 540 → **315** (3.63-3.69 → 2.23-2.25 s), trigger 358 → **232**
  (8.84-9.14 → **5.71-5.73 s**), nac 47 → 39 (0.40 → 0.35-0.36 s). Re-measure
  before quoting a "before"; the two effects multiply, so a per-evaluation win
  is now worth ~1.5× less in absolute seconds than the older tables imply.
- **What the flip did *not* change**, and it matters for what you attack next:
  the per-stage *shape* is the same — the trigger's `lines_axial` is still its
  worst stage (93 of 232 nfev, was 182 of 358) and `sample_broadening` second.
  The 15 608 perturbed `phase_peaks` this WP is about are unaffected by a
  tolerance; there are simply fewer evaluations asking for them.
- **A fit that must not be loosened declares it**, and one already does:
  `indexing.workflow.validation_plan` names the schedule in its docstring, and
  a bit-identity golden sets `intermediate_ftol=None`. If a measurement here
  needs the fully-converged path, that is the switch — not a new flag.

- **From the 2026-08-22 session that opened 1122** (maintainer-directed):
  the compiled peaks buffer this file's fences call "a real option here"
  now has its own WP, [1122](1122-compiled-peaks-buffer.md), gated on this
  WP's closing measurement — do not build the buffer here. If the cold
  target is still missed after this WP's leads and the preset decision,
  close by pushing the measured remainder — which seams survive, at what
  absolute cost per evaluation — into 1122's `### Inherited`; its task 1
  starts from exactly that.

## Non-goals

A fourth backend; GPU; a sixth plane kernel (that seam is done — 1115 § The
decision); re-opening 1114's no-go on its original numpy terms; anything that
moves a converged fit without a stated and asserted equivalence bar.

## Tasks

- [ ] **Re-measure the decomposition on the shipped tier** — the table above is
      the pre-1115 state and every share in it has moved. Same method
      (`bench_compiled_kernel.py --seams`), shares not absolutes, and record
      what fraction the compiled path now leaves on the table.
- [ ] **Instrument the scalar-memo hit rate** per slot over one trigger
      Jacobian, and settle lead 1 with a number. A depth-1 cache that never
      hits is a different fix from one that hits 90 % of the time.
- [ ] Attack whichever lead the measurement supports; equivalence bar stated
      and asserted per 1112/1115's pattern (bit-identity where no library call
      enters, the rounding bar where one does).
- [ ] **The preset flip is a decision, not a task** — put 1113's priced
      numbers to the user with this WP's own result beside them, since the two
      multiply.
- [ ] Tests (unit/property; the cross-backend configs grow whenever a
      derivative path does) + obs/calc/diff PNGs to `tests/output/`.
- [ ] If the cold target is still missed after all of it, **say so with the
      measured remainder** and name what would be needed. A milestone target
      missed and explained is a result; missed and quietly re-scoped is not.

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py                    # the before/after
RIETX_COMPILED=0 .venv/bin/python examples/bench_refinement.py   # …and the numpy floor
.venv/bin/python examples/bench_compiled_kernel.py --seams       # where the time is now
.venv/bin/python -m pytest -n auto --dist loadgroup              # full: this moves numbers
.venv/bin/python -m ruff check src tests examples
```

Before/after as harness ranges with venv and platform, the equivalence bar
stated per landed change, and never an Rwp comparison as evidence.

## References

- WP-1115 § Gate reading and § The decision — the decomposition this WP
  attacks, and the three traps building the tier produced.
- WP-1113 § Findings — the priced preset flip.
- WP-1114 § Findings 3–4 — the peaks buffer's accuracy traps, if that option
  is re-opened on compiled terms.
- Coelho (2018), *J. Appl. Cryst.* **51**, 210 — the two papers the v1.1 set
  is built on.

## Handover log

- **2026-08-22** — created, at the maintainer's direction, to give WP-1115's
  strongest forward finding an owner. 1115 shipped the compiled tier and took
  the cold trigger fit from 17.6 s to 8.9 s, which reached v1.1's warm-series
  target and left the cold one missed by about 2×. Its closing measurement says
  the next front is **not** another plane kernel — that seam is now ~2× off its
  numpy floor with no third factor in it — but the 15 608 perturbed
  `phase_peaks` calls a trigger Jacobian makes, which are per-reflection
  scalars no plane kernel reaches. That finding was recorded in three places
  (1115's handover, the ROADMAP focus line, the v1.1 record) and forwarded to
  no WP, because every v1.1 WP had closed; this file is the repair. Nothing is
  started. **Next**: task 1, because every share in the § Context table
  predates the tier that changed them.
