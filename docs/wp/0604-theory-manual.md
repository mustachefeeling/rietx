# WP-0604 — Sphinx + MyST theory manual

Milestone: v0.6 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Sphinx + MyST theory manual: numbered equations cross-referenced from
  docstrings (sphinxcontrib-bibtex)

## Context pointers

- The raw material already exists by invariant: every physics function cites
  author/year/journal in its docstring. The manual organises those citations
  into numbered equations; it must not become a second, divergent source of
  the formulas.

## Inherited

From **WP-0305** (Brindley, landed 2026-07-23) — a concrete instance of the
"second, divergent source" risk this stub already names, and a warning about
*which* source to trust. 0305's own WP body wrote the microabsorption fence as
"µR ≲ 0.01–0.1", which **conflated two conventions**: the shipped fence is
`BRINDLEY_MU_R_FENCE = 0.05` in µ·R, derived from µ·D ≤ 0.1 (D = diameter,
R = radius). The handover log corrected it; the WP body was never rewritten.

The general rule that follows: **transcribe formulas and thresholds from the
code and its docstrings, never from WP prose.** WP bodies record what was
planned, handover logs record what shipped, and where they disagree the code is
authoritative. Every physics function cites author/year/journal in its
docstring by invariant, which is what makes the code the better source.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
