# WP-1544 — a model reads in a notebook

Milestone: unscheduled · Status: 🔄 2026-10-07 — claimed by @yue-here
Track: Render what the fit already knows
Depends on: —
Priority: P2 2026-10-07 — a named user's demo notebook prints megabyte one-liners, and WP-1545's tutorials wait on this

## Goal

Every rietx object a person or an agent looks at prints as something readable.
That holds in a terminal, in `print()`, in a traceback and in a Jupyter cell.
The library's plotting functions behave inside a notebook.

## Context

**The trigger.** A friend's public demo notebook (LLongley94/rietx_demo,
`example_bim.ipynb`) drives rietx from Jupyter. Most of its cells print
pydantic one-liners. No rietx class defines a `_repr_*` hook. Measured on
`89c26036`:

| Object | What a cell or `print` shows |
|---|---|
| `PatternData`, 48k points (FAP: 5.7k) | 1 405 370 chars (FAP: 79 607) |
| `RefinementResult` | 809 339 chars of repr; `print` gives the designed view (`schemas/results.py:1413`) |
| `Instrument` / `Structure` | 2 727 / 2 600-char nested one-liner |
| `rx.diagnose(...)` | 743-char one-liner |
| `ref.parameters()` | 36 `ParameterRow` one-liners of ~300 chars |
| `FitReport` / `capabilities()` | 26.6k / 21k chars |
| `Refinement` | `<rietx.refine.Refinement object at 0x…>` |

**`print()` is no workaround.** Pydantic 2.13's `BaseModel.__str__` is
`__repr_str__(' ')`, so `str(data)` is the same 79 590 chars as its repr. So
is the friend's `for k, v in instrument: print(v)` habit. The fix therefore
sits in `Base.__repr_args__` (`schemas/common.py:415`), one rank below
Jupyter's hooks. Nothing in `src` parses a model's repr.

**Text is the authority, and HTML is a projection of it.** Agents read
stdout, and WP-1302's termination views are `__str__` methods
(`schemas/results.py:1413`, `schemas/sequential.py:1061`). A single
`_repr_pretty_` on `Base` that returns `str(self)` hands every designed
`__str__` to IPython.

**Three rules for anything that renders an object.**
- **A display reads fields and never computes.** IPython builds text/plain
  and text/html on every display. `Refinement.summary()` builds a report
  (`refine.py:4831`), and layer 2 runs rival fits, so a repr calling it would
  run fits twice per displayed cell. The telemetry rule records one report
  build writing four run directories.
- **No glosses.** A display never says what a name *is*. It prints the field
  name, or `help.py`'s `HelpEntry.label` where an arm exists (WP-1202).
- **No colour of its own.** HTML uses semantic tags only, with no `<style>`
  and no inline colour. JupyterLab's and GitHub's sanitisers strip styles, and
  a colour here would be a fourth surface beside `viz/theme.py`'s three.

**Matplotlib in a notebook.** `matplotlib.use("Agg", force=False)` runs at
`viz/plots.py:305,862,971` and `viz/indexing.py:59`. On matplotlib 3.11 it
does one of two things. With pyplot already imported it calls
`plt.switch_backend("Agg")`, which may take a live notebook off its inline
backend. Without pyplot it sets `rcParams['backend']`, which may stop the
inline figure formatter from ever loading. Both branches set
`backend_fallback=False` for the process. Neither effect is measured yet,
because IPython was not in the venv. The GUI server and the CLI need Agg,
since a GUI backend off the main thread fails on macOS.

**`rx.diagnose` is fit to show from v1.6.0.** WP-1442 took the demo's Kβ
flags from 34 to 0. Its census moved from 292 to 197 between WP-1415's filing
and its fix, and WP-1415 removed the census's σ-scale dependence. `n_peaks`,
`peak_density_per_deg` and `peak_fraction` are still not counts a reader
should quote. `docs/manual/using/results.md:431-445` still glosses them the
old way: it says seventeen fields where there are eighteen, and claims that
`peak_density_per_deg` feeds the background defaults, though nothing in `src`
reads it. `background/diagnostics.py:614-618` says "dense patterns (≳2/deg)
favour stiff baselines", which needs checking against what the code does.

**The data-only plot exists.** `data.plot()` forwards to
`rx.viz.plot_pattern` (`viz/plots.py:723`), documented in `using/data.md`.
The missing piece is a pre-fit overlay of the model's reflection ticks. It
answers SKILL §1's "is the cell within about 1 % and is λ right?" before any
fit. `viz/snapshot.stage_ticks` already builds ticks from a compiled model.

## Non-goals

- **No new public names.** An opt-in zoomable fit (`rx.viz.interactive`) was
  considered and cut. It would add API, it dies in an untrusted notebook, and
  it puts 275 KB into every committed output. A live session can already use
  `write_html` with `IPython.display.IFrame`. A `ParameterRows` list subclass
  was cut too: once item reprs are short, IPython's list printer is readable.
- **No widgets.** `DESIGN.md` keeps notebook widgets fenced until v2, and
  that covers drag-editing peaks and a live fit view.
- **No designed views yet** for `FitReport`, `ExtinctionScreen` or
  `Capabilities`. No history picture and no correlation-matrix plot. Each one
  is built when a WP-1545 notebook needs it.
- **`__repr__` stays pydantic's**, apart from the elision. Only its long
  sequences change.

## Tasks

- [ ] **Baseline probe.** Add a `notebooks` extra (`ipykernel`, `nbclient`,
  `nbformat`) that `[dev]` includes, after checking cp314 wheels for pyzmq and
  debugpy. Execute a scratchpad probe notebook with nbclient and record
  repr/str/text-plain sizes for every object in the table. Record matplotlib
  in both import orders: whether the image appears, appears once or twice, and
  whether a later `plt.plot(); plt.show()` still renders. Record the inline
  PNG size at `dpi=300`. The numbers go in this file's handover.
- [ ] **`Base.__repr_args__` elision.** A list, tuple or array longer than
  eight items renders as a count and a range (`<5753 floats 15.0…130.04>`), or
  as a count and a type for a list of models (`<212 Reflection>`).
- [ ] **A text tree for nested models.** `Base.__str__` becomes an indented
  field tree, one line per `Parameter`: value(esd) through
  `crystallography.cif.format_su`, unit through `help.UNIT_DISPLAY`, vary and
  bounds. `Base._repr_pretty_` returns `str(self)`. First grep `src` for
  `str(model)` and f-string uses whose text a message or test depends on.
- [ ] **Designed text views** where a tree is the wrong shape, reading fields
  only. `PatternData`: points, range, step, σ source, excluded regions,
  metadata. `PatternDiagnostics`: fields in its docstring's reading order.
  `IndexingResult`: `cli._print_index` (`cli.py:342-383`) moves here, and the
  CLI prints `str(result)`. `Refinement`: phases, mode, free count, last
  status, history head and the parameter table. `RefinementTree`: `summary()`.
  `StructureFigure`: `_repr_png_` from its RGBA array.
- [ ] **HTML projection for tables only.** `_repr_html_` on the result's
  parameter and diagnostic rows, `Refinement`'s parameter table and
  `IndexingResult`'s candidates. One row builder feeds both renderers, in a
  private `src/rietx/_display.py`.
- [ ] **Matplotlib in a kernel**, as the probe dictates. Skip `matplotlib.use`
  when a kernel is running or a backend is already resolved, and keep Agg for
  the GUI and CLI. One plot call gives one image. `fig.dpi` does not change
  silently.
- [ ] **Pre-fit ticks.** `plot_pattern(data, model=ref)` and
  `data.plot(model=ref)` draw the reflection ticks of a `Refinement` from
  `stage_ticks`, before any fit.
- [ ] **Docs.** Fix `results.md:431-445` and the `diagnostics.py` docstring.
  Add a short section on reading objects in a notebook or terminal to
  `using/results.md`. Document `model=` in `using/data.md`. Add a
  compatibility note for the changed `__str__` text and the backend change.
  Add the three display rules to the root CLAUDE.md Conventions.
- [ ] **Tests** (`tests/test_display.py`). The repr and str of every object in
  the table stay under a ceiling on real fixtures. The tree renders for
  `Instrument` and `Structure`. HTML escapes `<`. Displaying a fitted
  `Refinement` writes no run and runs no fit. With IPython installed, the
  `DisplayFormatter`'s text/plain stays under the ceiling. The CLI's `index`
  output is byte-identical after the move.
- [ ] Skill: one row on reading objects (`print(x)` and `x` in a notebook are
  both short now), or "none" if the body already says it.

## Acceptance

Every object in the Context table prints under a ceiling the tests set,
measured before and after in the handover. The probe notebook shows each plot
call's image exactly once in both import orders.

```sh
.venv/bin/python -m pytest tests/test_display.py tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- IPython rich display protocol: `_repr_pretty_`, `_repr_html_`, `_repr_png_`
  (IPython documentation, "Rich output").
- Pydantic v2 `BaseModel.__repr_args__`.

## Handover log

- **2026-10-07** — created. No open WP owns notebook display; the index has no
  row for notebooks, reprs or Jupyter. The plan had a fresh adversarial review
  before filing. That review moved the fix from Jupyter's hooks down to
  `__repr_args__`, and cut two new public names.
