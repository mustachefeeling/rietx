# The API index

Load it when you are about to call rietx and want the name rather than a guess:
the entry points, the model objects, the four answer types and their fields, the
report, and the exports.

*A reference file of the `rietx` skill. The body it belongs to is
[`SKILL.md`](../SKILL.md). Every name here is checked against the installed
package by test, so a rename cannot leave an entry behind.*

**There is one integration surface and it is the Python API.** A caller runs a
verb, reads the typed answer, and dumps it with `model_dump(mode="json")` when a
file is wanted. A failure **raises**: there is no envelope and no error code.

**Do not quote a signature from memory.** Every name below is real and tested;
`inspect.signature(obj)` or `help(obj)` gives its arguments in one call.

**In.** `rx.read_pattern` (every format `rx.capabilities()` lists),
`rx.read_pdcif`, `rx.Structure.from_cif`, `rx.Instrument.bragg_brentano`,
`rx.Instrument.debye_scherrer`, `rx.auto_background`,
`rx.load_instrument_profile`, `rx.save_instrument_profile`. Model objects:
`rx.Structure`, `rx.Phase`, `rx.Atom`, `rx.Cell`, `rx.AnisoU`, `rx.Instrument`,
`rx.Source`, `rx.NeutronSource`, `rx.Geometry`, `rx.ProfileTCHZ`,
`rx.BackgroundChebyshev`, `rx.BackgroundPSpline`,
`rx.BackgroundFixedPlusChebyshev`, `rx.PreferredOrientation`,
`rx.StephensStrain`, `rx.Dispersion`, `rx.PatternData`.

**Refining.** `rx.Refinement` is the stateful entry point: `.fit` (with `mode=`,
`plan=`, `two_theta_limits=`, `events=`, `cancel=`, `progress=`,
`stage_reports=`), `.report`, `.summary`, `.suggest`, `.predict`, `.run_stage`;
`rx.refine` is the one-shot function form. Plans are named in `rx.PLAN_INFO` and
`rx.PLAN_PRESETS`, or built as a `rx.RefinementPlan` of `rx.Stage`s.
`ref.parameters()` lists every entry, fixed, locked and tied included, as
`rx.ParameterRow` (`.refinable`, `.held_because`, `.help_key`);
`ref.set_vary(globs, vary)` and `ref.set_values({path: value})` edit it,
`ref.tie` / `ref.tie_equal` / `ref.untie` constrain it, `ref.edit` swaps a whole
model, and each auto-commits a history node.

**The four answers are four different types.** `rx.RefinementResult` (`.status`,
`.stages`, `.statistics`, `.diagnostics`, `.parameters`, `.parameter(path)`,
`.phase_agreement`, `.qpa`, `.geometry`, `.identifiability`, `.ticks`,
`.provenance`); `rx.SeriesResult` (`.entries`, `.paths`, `.trajectory(path)`,
`.to_table`, `.write_csv`, `.summary`, `.plot`); `rx.IndexingResult`
(`.candidates`, `.best_or_none()`, `.diagnostics`, `.evidence()`), which carries
no `cell` key by design; and `rx.SuggestionResult` (`.groups`, `.non_separable`,
`.summary`). `rx.Statistics` carries `.rwp`, `.gof`, `.durbin_watson`,
`.esd_inflation`, `.max_shift_over_esd`, `.identifiability_clause`; each
`rx.RefinedParameter` `.value`, `.stderr`, `.vary`, `.at_bound` (three valued —
test `is True`); each `rx.Diagnostic` `.code`, `.level`, `.where`, `.message`,
`.suggestion`.

**The report.** `ref.report()` or `rx.build_report`, giving `rx.FitReport`:
`.regions`, `.unmatched`, `.attribution`, `.background`, `.lebail_gap`,
`.identifiability`, `.geometry`, `.texture`, `.strain`, `.summary`,
`.abstained_reason`, `.abstained_kind`. `rx.report.compare_rivals` and
`rx.report.predict_then_verify` are the two experiments §4 and §4b call for.

**Series, history, projects.** `rx.refine_sequential` and
`rx.SequentialRefinement` chain N patterns by warm start (§9b); `rx.refine_multi`
and `rx.MultiHistogramRefinement` stack patterns into one joint residual, which
is a different thing. `ref.checkout`, `.branch`, `.merge`, `.cherry_pick` and
`rx.replay` work the history DAG (§9); `rx.Project.create` / `.open` / `.save`
own a `.rex` directory; `rx.CancelToken` cancels cooperatively, between residual
evaluations.

**An unknown phase.** `rx.pick_peaks` → `rx.index_pattern` →
`rx.determine_extinction_symbol` (§7b-7f).

**Out.** `rx.write_refinement_cif`, `rx.write_qpa_table`,
`rx.write_reflection_table`, `rx.reflection_table`, `rx.format_su` (a value with
its esd, `1.2345(12)`), `rx.viz.plot_result`, `rx.viz.plot_for_vlm`,
`rietx.viz.html.write_html`.

