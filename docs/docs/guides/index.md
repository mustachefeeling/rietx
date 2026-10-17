# Guides

Each guide does one task from start to finish, and its title names the task as "How to …".

Each guide's fits are a script in `examples/guides/`, run by the test suite, and the output a guide shows is what its script printed.

## Constraints and plans

- [How to keep a parameter fixed whatever the plan frees](hold.md) uses `Refinement.hold`.
- [How to tie parameters together](tie.md) makes parameters equal, or one a linear function of others.
- [How to restrain a bond length or an angle](restrain.md) adds chemistry as weighted observations.
- [How to add a stage to a refinement plan](plan.md) edits a preset or builds a plan.

```{toctree}
:hidden:

hold
tie
restrain
plan
```
