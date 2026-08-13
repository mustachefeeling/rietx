# fixture_round — a two-cell synthetic record for `mine_transcripts`

Committed, tiny, and entirely made up: no refinement ran and no agent wrote
any of it.  It has the layout of a real round record (`eval-runs/README.md`)
because the miner is a reader of that layout, and a reader tested only against
a record that is gitignored and deletable is a reader with no test at all.

Each of the two transcripts is built to exercise one thing the real round
made necessary, so a regression here names its own cause:

| cell | what it pins |
|---|---|
| `both__sonnet/E2` | the clause arrives *before* the both-free overlay; the overlay is a `Write` payload (escaped JSON, unreachable by a brace scan of the serialized input); the trajectory is probed and answered under one `tool_use_id`; rung content carries a rung-only field |
| `report__haiku/E2` | the prompt's own prose naming an action kind is **not** a delivery; an overlay written by a Bash heredoc is still an overlay; one rival freed is not a ridge |

The prompt-prose line matters most.  It is the shape of the measured defect
that made `delivered` a JSON-form match: the §5/§6 excerpts inside every
report-on prompt name the whole action vocabulary, so a loose count scored
most of the round on tokens the package had not sent.
