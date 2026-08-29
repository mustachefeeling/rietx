# Agent instructions

This repository's agent instructions live in `CLAUDE.md` files. The name is
historical; the content is vendor-neutral, and every rule in them binds any
agent — and any human — changing this code.

- Start with the root [`CLAUDE.md`](CLAUDE.md): the package map, the
  invariants, and the conventions.
- Subsystem rulebooks apply within their subtrees and do not restate the
  root: [`gui/CLAUDE.md`](gui/CLAUDE.md), [`tests/CLAUDE.md`](tests/CLAUDE.md),
  [`src/rietx/io/CLAUDE.md`](src/rietx/io/CLAUDE.md),
  [`src/rietx/indexing/CLAUDE.md`](src/rietx/indexing/CLAUDE.md).
- To *use* the package — refine someone's data rather than change the code —
  read the agent skill [`docs/skill/rietx/SKILL.md`](docs/skill/rietx/SKILL.md)
  first (it is also installed at `.agents/skills/rietx/` and
  `.claude/skills/rietx/`, so your harness may have loaded it already), then the
  manual's Part 1 (`docs/manual/using/`). Nothing in the rulebooks substitutes
  for either.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) has setup, the test ladder, and the
  style essentials a change is held to.

Maintainer-only: the ROADMAP/WP session protocol, the memory conventions
and the paper-corpus references in `CLAUDE.md` serve the maintainer's own
workflow. An external agent can ignore them and must not require them.

`docs/ROADMAP.md` and `docs/wp/NNNN-*.md` are also maintainer-only to
*write*: they schedule work, and scheduling is the maintainer's. Add to the
handover log of a WP whose work you did, and take unscheduled design to a
[design proposal](https://github.com/yue-here/rietx/issues/new?template=design-proposal.md)
instead. `CONTRIBUTING.md` has both rules in full.
