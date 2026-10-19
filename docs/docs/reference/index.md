# Reference

Reference pages list names you look up: the API, the parameters, the plans, the diagnostic codes and the files rietx writes.

Most of them are built from the code that owns their facts, so they match the version this manual was built from.

- [API: everyday calls](api.md), [API: techniques](api-techniques.md) and [API: everything else](api-types.md) give each exported name with its signature or fields.
- [The command line](cli.md) gives each `rietx` subcommand with its options, its output and its routes.
- [Patterns and structures](data.md) gives the fields of `PatternData`, `Structure`, `Phase`, `Cell`, `Atom` and `Parameter`.
- [The instrument](instrument.md) gives the fields of `Instrument`: its constructors, the X-ray, neutron and time-of-flight sources, the geometry, the peak width, the background and declared extra peaks.
- [Parameter map](parameters.md) lists every refinable parameter, grouped by what it does.
- [Stage settings, flags and options](settings.md) lists the other names rietx uses: stage settings, peak flags, peak origins, reader options, instrument preset fields and indexing search settings.
- [Plan presets](plans.md) draws each preset's stages.
- [Diagnostic codes](diagnostics.md) lists every code with its name, and links the page that explains it.
- [Project directory](project.md) shows the files in a `.rex` project.
- [Names in other programs](foreign-names.md) gives each parameter's name in GSAS-II, GSAS, TOPAS and FullProf.
- [The GUI panel by panel](gui-guide.md) says what each panel of `rietx gui` is for.
- [The GUI as a text document and a wire](gui-power.md) gives the `.rxt` grammar, the keyboard, the command palette and the HTTP routes.
- [For agents](agents.md) says how an agent gets the rietx skill.
- [Compatibility](compatibility.md) says what a version string promises and which parts are declared provisional.

```{toctree}
:hidden:

api
api-techniques
api-types
cli
data
instrument
parameters
settings
plans
diagnostics
project
foreign-names
gui-guide
gui-power
agents
compatibility
```
