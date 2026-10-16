# Diagnostic codes

This page lists every diagnostic code rietx can raise, with its level and the source files that raise it.

A `Diagnostic` carries a `level` of `info`, `warning` or `error`, a `code` and a message that names its parameters.
Where the source computes a level from a variable, the table says "set at run time".
A dash means the code is handed to a helper function, which sets the level.

```{include} ../_generated/diagnostics.md
```
