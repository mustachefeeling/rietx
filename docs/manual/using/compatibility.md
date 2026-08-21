# Compatibility

This chapter is the 1.x stability position: what a version string tells you,
which parts move most, and how to build something that outlives one
interactive session — a stored result, a parser for the agent envelope, a
pipeline pinned to a version — on a package that is still being reshaped.

## The preview position

**1.x is a preview, and anything may change in any release** — a name, a
shape, a threshold, an answer, including in a patch release. The package is
young and its users are few and close to its development, so it trades
stability for speed on purpose; holding every surface still would protect
almost nothing and slow everything. Three rules make the preview buildable:

- **Pin an exact version.** `rietx==1.1.0` in a lockfile is the stability
  promise. An upgrade is a decision, taken after reading what moved; what
  the preview does not offer is an upgrade that is safe unread.
- **Any observable change moves a version string.** Each data contract below
  carries one, and the rule — stated beside each constant in the source — is
  one sentence: any change a consumer could observe bumps the last component
  by one, and the comment beside the constant says what changed. No
  safe/minor/breaking classification survives; the only question left is
  whether you could have noticed.
- **A change to what an existing value means is always a documented event**,
  even when no shape changes. A field that keeps its name and type but
  answers a different question is the least visible break there is, so it is
  never silent.

The position expires by its own terms: **it tightens when the first
persistent archive of `.rex` projects exists** — a condition, not a date —
because from that point a format change destroys accumulated work rather
than a test fixture. The version strings, their bump records and the
documented-surface partition below are kept current so that tightening is a
decision, not a rebuild.

## The six version strings

A moved version string means something you could observe changed, and the
comment beside the constant says what. **Those comments are the changelog**:
each constant carries its own bump history — what moved, in which change, and
why — and no separate file restates it. Promoting that record to a hosted
page is part of tightening the promise, when there are users to face it. The
strings are the six contracts `capabilities()` reports — [](agents.md) has
the table:

- **The schemas** (`Capabilities.schema_version`) — the pydantic models
  everything else rides on: structure, pattern, instrument, plan, result,
  history node, project document.
- **The agent envelope.** `agent.refine_json`'s request union and response
  arms, and its error grammar: `ok: false` with a structured error whose
  `code` is one of the three in `agent.ERROR_CODES` — a closed list.
- **The `.rex` project directory** (`Capabilities.project_format_version`).
- **The streaming event ladder** (`Capabilities.event_schema_version`). An
  event's `data` dict is declared open on both sides, so a new key in it is
  the contract working rather than a change to it; a new event kind bumps.
- **The report gates and thresholds**
  (`Capabilities.report_thresholds_version`) and **the indexing gates**
  (`Capabilities.indexing_thresholds_version`).

Two vocabularies carry no version string because they are **open by
design**: the diagnostic and guard codes. A new code may appear in any
release, and an existing code keeps its meaning. Branch on the codes you
know; pass through the ones you do not.

## The Python surface is documented, not frozen

The public call surface — every function, class, method and field a caller
can reach — is derived from the live package rather than hand-listed, so a
new public name cannot slip past it: it fails the build until its chapter
documents it, it is deferred with the chapter still to come, or it is
excluded with a written reason. That partition gates coverage, not
stability. "Documented" means documented — the manual describes the name as
it works in this release — and a documented name may still change in the
next one, with the release notes saying so.

**Everything else is internal.** Anything importable outside the derived
surface is internal and may change without notice. A chapter that spells an
internal helper fully qualified — `rietx.viz.compare.run` and
`rietx.viz.html.write_html` are the standing examples — is pointing you at
something that works, not promoting it.

(provisional-by-declaration)=

## Provisional by declaration

Even in a preview, some parts move more than others, and the ones expected
to move are declared rather than left to be inferred:

- **The GUI as a whole ships as beta**, its HTTP routes included. Two things
  about the wire are nevertheless stated normatively below: the JSON dialect,
  and that the upload routes carry raw bytes.
- **The `.rxt` text document.** It is rendered in-session and never
  persisted, so nothing accumulates in it. If it ever becomes a saveable
  file, its `Capabilities.textdoc_format_version` starts moving.
- **A series is session-scoped.** `refine_sequential` returns its result and
  writes one history tree per pattern, but the series itself is not a saved
  document.
- **Indexing is provisional as a subsystem.** `pick_peaks`, `index_pattern`
  and `determine_extinction_symbol`, the answer types they return
  (`rietx.schemas.indexing`), and the helpers under `rietx.indexing` that the
  agent protocol's worked loop calls are documented in [](indexing.md) and
  are the names in the package most likely to change: the engines, the gates
  and the figures of merit are still being measured against real data, and
  1.0.2 is what that looks like — `determine_extinction_symbol` stopped
  refuting an extinction class on a neighbouring peak's tail, so its
  *answer* moved in a patch release. Every such change is announced in the
  release notes, and the data contracts keep their own version strings —
  `Capabilities.indexing_thresholds_version`, the engine and search-preset
  capability types, and the `indexing` arm of the agent envelope — so a
  consumer that parses an answer sees a bump when the answer's shape or
  meaning moves.

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
