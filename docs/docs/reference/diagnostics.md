# Diagnostic codes

This page lists every diagnostic code rietx can raise.
Each code has a short name, an explanation of what it means and why it fires, its level, and the source files that raise it.

A `Diagnostic` carries a `level` of `info`, `warning` or `error`, a `code`, a `message` and a `suggestion`.
The message says what one case found, with its numbers.
The suggestion says what to do about it.
The explanation is the same for every case, so the package looks it up by code: `Diagnostic.explanation` returns the text on this page.

Where the source computes a level from a variable, the level reads "set at run time".
Where a helper function receives the code and sets the level, the level reads "set by a helper".

```{include} ../_generated/diagnostics.md
```
