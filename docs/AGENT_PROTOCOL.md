# Refinement protocol for agents — moved

This document is now an **Agent Skill**, a directory rather than one file:
[`docs/skill/rietx/`](skill/rietx/SKILL.md), published at
<https://rietx.org/skill/rietx/SKILL.md>.

Nothing was removed. `SKILL.md` is the judgement core — the preconditions, the
turn-on order, the degeneracies, how to judge a fit, the deliverables, the
abstention rules, the worked default and the three stop conditions — and the
lookup tables it used to carry inline are reference files beside it, loaded when
a task calls for one. Section numbers are unchanged, so a citation of §7d or
§8.11 still resolves.

The skill ships inside the wheel. `rietx skill --path` prints the directory,
`rietx skill --print` prints its text for a harness that reads no skills, and
`rietx skill --install` puts it where every harness working in your repository
will find it. `capabilities().skill_path` is the same answer from Python.

Why the change: this file reached 144 427 B, 2.2× what an agent's Read tool
returns in one call, so the document written to be read was in practice never
read whole. The measurements are in
[WP-1304](wp/1304-protocol-as-skill.md).

**This pointer is kept for one release and deleted in v1.4.**
