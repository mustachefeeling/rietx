# The agent skill

The operating protocol — what to free in what order, what to check before
believing a number, how to read an abstention — ships with the package as an
**Agent Skill**: a directory holding a `SKILL.md` an agent reads whole when the
task calls for it, and reference files it loads only when it needs one.

The format is an [open standard](https://agentskills.io/specification), not one
vendor's feature, so the same directory is read natively by Claude Code, Codex,
Cursor, Copilot, Gemini CLI, opencode, Goose, Cline, Amp, Kiro, Devin, Zed,
Junie, Qwen Code and OpenHands, among others. Nothing in it is specific to one
of them.

This chapter is the whole skill, rendered from the files the package ships, so
it cannot drift from what an agent actually reads.

:::{admonition} For agents
:class: agent
Do not read this chapter. Read the skill itself: `rietx skill --path` prints the
directory, `capabilities().skill_path` is the same answer from Python, and your
harness has probably loaded it already. This page exists so a person can see
what the machine was told.
:::

## Getting it

```
rietx skill --path              # where this build keeps it
rietx skill --print             # the body, as text
rietx skill --print diagnostics # one reference file
rietx skill --install           # into this repository, for every harness
```

`rietx skill --install [DIR]` writes one real copy to `DIR/.agents/skills/rietx/`
— the directory the specification recommends and most harnesses scan — and
points each harness that reads somewhere else at it with a relative symlink, so
the link survives the project being moved or cloned elsewhere. `--agent
NAME` (repeatable) chooses which, and `--list-agents` prints the harness table
with the source and date each row's directories were read from. `--user`
installs for the user rather than for a project; `--copy` copies instead of
linking, which is what Windows gets in any case.

The command prints, and never writes, the two lines that name the skill in a
project's `AGENTS.md` or `CLAUDE.md`. Those files are the project's own
instructions to its agents, and appending to one uninvited would be editing
something the package does not own.

For a harness that reads no skills at all, `rietx skill --print all` is the
whole tree as plain text, for a `--read` flag or a system prompt.

```{include} ../_generated/skill-body.md
```
