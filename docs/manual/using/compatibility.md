# Compatibility

This chapter is the 1.0 stability promise: which surfaces are frozen, which
are still free to move, and how a change is classified when it comes. Read it
before you build anything that outlives one interactive session — a stored
result, a parser for the agent envelope, a pipeline pinned to a version.

The promise has two strengths, because the package has two kinds of consumer.
A person testing interactively recovers from a renamed argument in a minute.
An unattended pipeline — or a directory of saved projects — does not recover
from a changed file format. So the data contracts freeze hard at 1.0, and the
Python call surface freezes as it is documented.

## The data contracts are frozen

A break in any of these corrupts accumulated work or an unattended pipeline,
so none of them changes shape without its version string moving. The version
strings are the six contracts `capabilities()` reports — [](agents.md) has
the table:

- **The schemas** (`Capabilities.schema_version`) — the pydantic models
  everything else rides on: structure, pattern, instrument, plan, result,
  history node, project document.
- **The agent envelope.** `agent.refine_json`'s request union and response
  arms, and its error grammar: `ok: false` with a structured error whose
  `code` is one of the three in `agent.ERROR_CODES` — a closed list.
- **The `.rex` project directory** (`Capabilities.project_format_version`).
- **The streaming event ladder** (`Capabilities.event_schema_version`).
- **The report gates and thresholds**
  (`Capabilities.report_thresholds_version`) and **the indexing gates**
  (`Capabilities.indexing_thresholds_version`).
- **The diagnostic and guard code vocabularies**, which are open by design:
  a new code may appear in any release, and an existing code keeps its
  meaning. Branch on the codes you know; pass through the ones you do not.

## The Python surface freezes as it is documented

The public call surface — every function, class, method and field a caller
can reach — is derived from the live package rather than hand-listed, so a
new public name cannot slip past it. Every name on it is in exactly one of
three buckets:

- **Documented.** A name this manual's Part 1 documents is frozen from the
  release that documents it.
- **Deferred.** The rest of the surface is **provisional**: it works as it
  stands today, but a name in this bucket may change in a 1.0.x release.
  The 1.0.x releases are the documentation road — each chapter that lands
  promotes its names from provisional to frozen.
- **Excluded with a written reason** — documented as a protocol rather than
  as a type (the `cancel=` token), or a compile-stage internal.

In practice: if this manual names it, build on it; if not, it still works,
but check the release notes before you upgrade.

**Everything else is internal.** Anything importable outside the derived
surface is internal and may change without notice.

## Provisional by declaration

The rest of the promise is by declaration rather than by bucket:

- **The GUI as a whole ships as beta**, its HTTP routes included. Two things
  about the wire are nevertheless stated normatively below: the JSON dialect,
  and that the upload routes carry raw bytes.
- **The `.rxt` text document.** It is rendered in-session and never
  persisted, so nothing accumulates in it. If it ever becomes a saveable
  file, its `Capabilities.textdoc_format_version` starts moving.
- **A series is session-scoped.** `refine_sequential` returns its result and
  writes one history tree per pattern, but the series itself is not a saved
  document at 1.0.

## How a change is classified

The rule is hybrid: what a change *is* decides which version moves.

**Safe additions move no contract version.** A new field with a default — on
any schema, in an event's `data` dict, a new key in `capabilities().features`
— is not a break. The package version and the release notes carry it.

**Closed-vocabulary additions are minor events in their own contract.** A new
action kind, a new indexing caveat, a new node kind, a new abstention kind, a
new event kind: each moves the version string of the contract it belongs to.
The classification of actions in `rietx.report.apply.RECIPES` is part of the
report contract, so moving a kind between classes is a minor event too.

**Renames, removals and threshold moves are breaking events**, and each moves
its contract's version as one.

Two clauses complete the rule:

- **A change to what an existing value means is always a documented event**,
  even when no shape changes. A field that keeps its name and type but
  answers a different question is the least visible break there is, so it is
  never silent.
- **Tolerate unknown fields and flags.** Safe additions arrive without a
  contract version move, so validating responses against a pinned copy of
  the schema is unsupported: a pinned-copy validator breaks on exactly the
  changes this promise calls safe.

## The JSON the package writes

Two facts about the wire are normative even where the routes above are not:

- **Non-finite floats serialise as the strings `"Infinity"`, `"-Infinity"`
  and `"NaN"`**, everywhere the package writes JSON. A parameter bound of
  ±inf survives a round-trip; a consumer's JSON parser must expect the
  string form.
- **The upload routes carry raw bytes, not JSON.** A pattern file's bytes
  are the contract — the file is stored byte for byte, and the reader that
  claimed it is recorded beside it — so no upload is wrapped, encoded or
  re-serialised.

## The name and the formats are separate promises

The brand tokens — the distribution name, the state directory, the agent tool
name — track the distribution, and would move together if the package were
ever renamed. The format tokens — the `.rex` suffix, the `rxt` header word,
the instrument-profile tag — name versioned contracts, and do not move
because a brand did. A future rename is therefore not a format break: a
project written today opens under whatever the package is called when you
open it.

## What a default promises

One principle decides defaults, and it explains why the same content can
default differently on two surfaces: **a library primitive is cheap, and a
delivery surface is complete**. `Refinement.fit` is called in loops — suites,
series, parameter sweeps — so anything that costs a multiple of the fit is
opt-in there (`stage_reports=True`). The agent envelope is read once per fit
by a consumer that was not watching, so it carries the complete story by
default (`evidence` is on). A future addition lands under the same rule, on
whichever side its cost puts it.
