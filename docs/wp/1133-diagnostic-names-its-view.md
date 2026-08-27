# WP-1133 — A diagnostic names the view that shows it

Milestone: unscheduled · Status: ⬜
Depends on: WP-1130 (the background panel with a reference in the frame is the
first view worth pointing at, and the eval's positive condition)

## Goal

A finding says which rendered view makes it legible, the operator protocol
says which channel answers which kind of question, and the one claim still
open — that an image pays for itself on a question an agent cannot name in
advance — is measured as round trips rather than asserted.

## Context

Split out of [1130](1130-background-reference.md) at its 2026-08-27 review.
1130's Finding 8 is the full record; the load-bearing numbers are restated
here so this file stands alone.

### What the 2026-08-23 session measured about the image channel

The premise is that the package supplies information and the agent supplies
the reasoning, so which channel carries the information efficiently is a
design question, not a rendering detail. The only controlled evidence is that
session grading itself, and it is a negative followed by a qualified positive.

- **Vision did not find the error.** The maintainer's obs/calc/diff plot was
  in context from the first message; the model did not raise the background,
  the maintainer did. Told, the model matched the supplied hypothesis to
  whichever background sat highest rather than detecting anything. Its one
  unaided visual judgement was **inverted**: a background well below the
  inter-peak valleys read as sound, one at the valley level as suspect, when
  the second was the closest of five to TOPAS (0.75–0.81) and the four
  "sound" ones were at 0.50–0.59.
- **Vision found it once, from a purpose-built panel**: the anchored curve
  tracing the data floor with every fitted background ~30 counts beneath it.
  Two properties separated that panel from the standard one, and both are
  constructible. The same error, as a fraction of panel height: standard
  obs/calc/diff over 14–70°, **2.6 %**; its 18–25° zoom, **4.9 %**; y cropped
  to the background's own range with the reference overlaid, **14.0 %**. More
  decisive than the scale is **a reference inside the frame**: with only the
  fit in frame the eye's sole comparator is its prior, and the prior was
  wrong. A uniform factor of two in level leaves a smooth monotone decay,
  which has no visual signature at all.
- **Cost, for a question already known.** The per-region table carrying the
  finding is ~123 tokens; the figure at 1373×1000 is ~1830 (vision ≈ w·h/750
  after the 1568 px long-edge downscale), a factor of ~15, plus ~1 s of
  matplotlib against a numpy pass. Vision is not the cheap channel for a
  question you can name. Where it might earn its tokens is the question that
  cannot be named in advance — "what is wrong with this fit" — and there the
  comparison is against the *round trips* an agent would otherwise spend
  discovering which statistic to compute. That comparison is unmeasured and
  is this WP's third task.

Consequence: a plot presents a reference and never replaces one, and the
surface should say which channel answers which question rather than leaving an
agent to guess.

### The seams

`GuardFinding` (`strategy/staged.py`) carries `code`/`paths`/`value`/`message`
and every guard `Diagnostic` (`schemas/common.py`) carries `where` and
`value`; neither says which rendered view makes the finding legible.
`viz.plot_for_vlm` is the montage, and 1130 adds the background panel to it.
`tests/eval_report_agent/` and `tests/eval_agent_surface/PROTOCOL.md` hold the
eval discipline: register the read-out before running, enforce the condition
in a shim rather than the prompt, real subagents with model and effort as
variables, and no pooling across rounds.

## Non-goals

- **Not embedding an image in a diagnostic.** The pointer is a name; the
  caller decides whether to spend the tokens.
- **Not a new montage.** `plot_for_vlm` is the montage; a view this WP names
  must already be drawable, and the one 1130 adds is the first.
- **Not the background reference itself.** That is 1130.

## Tasks

- [ ] **The view pointer.** A field on `Diagnostic` (and the `GuardFinding`
      constructor feeding it) naming the rendered view that shows the finding —
      a member of a closed vocabulary drawn from what `plot_for_vlm` can render,
      so a name with no renderer fails a meta-test (the root CLAUDE.md's
      declared-name rule). `None` where no view helps, which is most findings,
      and honest. Manual Part 1 gains the field or the partition fails.
- [ ] **The channel rule in `AGENT_PROTOCOL.md`.** Numbers for a question you
      can name (~15× cheaper), an image for one you cannot, and never an image
      without a reference in the frame. One row, the measurements above as its
      evidence.
- [ ] **Measure the round-trip case.** Give an agent a fit and "what is wrong
      with it", with and without the montage (1130's panel in it), and count
      calls to answer as well as tokens — on 1130's trigger fit and on two
      bundled fits with a planted error each. Pre-register the read-out. The
      result may be that the image buys nothing; that is a result to record
      and act on by removing the pointer's claim, not to soften.
- [ ] Tests (the vocabulary meta-test; the field's JSON round trip; the eval's
      shim) + the montage PNGs the eval used to `tests/output/`.

## Acceptance

Every view name a diagnostic can carry has a renderer, and the round-trip
measurement is recorded with its pre-registered read-out and a decision.

```sh
.venv/bin/python -m pytest tests/test_diagnostic_views.py tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- [1130](1130-background-reference.md) § Finding 8 — the measurements
  restated above.
- `tests/eval_report_agent/` and `tests/eval_agent_surface/PROTOCOL.md` — the
  eval discipline the third task follows.

## Handover log

- **2026-08-27** — created, split out of 1130 at its review; nothing measured here yet.
