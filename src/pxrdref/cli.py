"""The ``pxrdref`` command-line entry point.

Deliberately tiny: the package is API-first, and the CLI exists for the few
things that are genuinely terminal-shaped — watching a running refinement,
rendering a result file, launching the settings-comparison UI, and asking "what
is the cell of this pattern I just collected?".

``pxrdref index`` prints the **candidate list**, never one cell, and carries the
verdict in its exit status (0 when a cell reached the confidence gate, 1 when the
result abstains).  The API has no ``.cell`` and the CLI must not invent one — an
exit code is the one channel a shell pipeline can branch on without parsing.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: pxrdref <command> [...]\n\n"
              "commands:\n"
              "  gui [PROJECT.pxrd] [--port N] [--no-open] [--machine]\n"
              "                                    the refinement GUI (localhost)\n"
              "  watch <dir> [--port N] [--open]   live viewer for a LiveSession directory\n"
              "  html <result.json> <out.html>     render a saved RefinementResult to HTML\n"
              "  index <pattern> --wavelength A [...]\n"
              "                                    determine the unit cell of an unknown\n"
              "                                    phase (pxrdref index --help)\n"
              "  compare [--data DIR] [--port N] [--open]\n"
              "                                    browser UI comparing refinement\n"
              "                                    settings on the bundled standards")
        return 0

    command, rest = argv[0], argv[1:]
    if command == "index":
        return _index(rest)
    if command == "gui":
        from .gui.server import main as gui_main

        return gui_main(rest)
    if command == "watch":
        from .watch import main as watch_main

        watch_main(rest)
        return 0
    if command == "compare":
        from .compare_app import main as compare_main

        return compare_main(rest)
    if command == "html":
        if len(rest) != 2:
            print("usage: pxrdref html <result.json> <out.html>", file=sys.stderr)
            return 2
        from .schemas.results import RefinementResult
        from .viz.html import write_html

        with open(rest[0], encoding="utf-8") as fh:
            result = RefinementResult.model_validate_json(fh.read())
        write_html(result, rest[1])
        print(f"wrote {rest[1]}")
        return 0

    print(f"pxrdref: unknown command {command!r} (try --help)", file=sys.stderr)
    return 2


def _index(argv: list[str]) -> int:
    """``pxrdref index`` — terminal-shaped because "what is this cell?" is a
    question you ask about a file you just collected.

    It prints the **candidate list**, never one cell: the API has no ``.cell`` and
    the CLI must not invent one.  The exit code carries the verdict so a shell
    pipeline can branch on it — 0 when ``best_or_none()`` returns a cell, 1 when
    the result abstains — which is the same statement as the diagnostics, in the
    one channel a script can read without parsing.
    """
    import argparse

    p = argparse.ArgumentParser(
        prog="pxrdref index",
        description="Determine the unit cell of an unknown phase from a powder "
                    "pattern. Prints every candidate with its confidence and the "
                    "reasons it is not higher; exits 1 if no cell reached the gate.")
    p.add_argument("pattern", help="pattern file (.xy/.xye/.fxye/.prn/.dat, or a "
                                   "pd-CIF)")
    p.add_argument("--wavelength", type=float, required=True,
                   help="primary wavelength in Å. A single line: for a lab Kα "
                        "doublet build the Instrument in python "
                        "(Instrument.bragg_brentano(radiation='CuKa')) and call "
                        "index_pattern — peak picking recognises the Kα2 alias of "
                        "each line and a one-line source cannot")
    p.add_argument("--geometry", default="debye_scherrer",
                   choices=("debye_scherrer", "bragg_brentano",
                            "flat_plate_transmission"))
    p.add_argument("--radius", type=float, default=None,
                   help="goniometer radius in mm (required for bragg_brentano)")
    p.add_argument("--systems", default=None,
                   help="comma-separated crystal systems (default: all). A "
                        "restricted search reports what it did not cover rather "
                        "than concluding anything about the specimen")
    p.add_argument("--engines", default=None,
                   help="comma-separated engines (default: all — 'high' "
                        "confidence means every engine that ran agreed)")
    p.add_argument("--max-d", type=float, default=None,
                   help="longest principal d-spacing in Å (default 25); domain "
                        "size is what an exhaustive search pays for")
    p.add_argument("--min-d", type=float, default=None,
                   help="shortest principal d-spacing in Å (default 2)")
    p.add_argument("--budget", type=float, default=None,
                   help="wall-clock seconds per (engine x crystal system) slice "
                        "of the search (default 30 — so an unbounded "
                        "three-engine, seven-system run is up to 3x7x30 s of "
                        "search, before the probe and validation; --ceiling "
                        "prints the arithmetic)")
    p.add_argument("--total-budget", type=float, default=None,
                   help="wall-clock ceiling for the WHOLE run — search, probe "
                        "and validation. The run returns what was reached and "
                        "INDEX_BUDGET_EXHAUSTED names the systems truncated or "
                        "not reached. Overrides the preset's ceiling")
    p.add_argument("--preset", default=None,
                   help="search preset (default 'quick': every engine and "
                        "system under a whole-run ceiling, truncation reported; "
                        "'full': no ceiling, the pre-1.0 behaviour)")
    p.add_argument("--ceiling", action="store_true",
                   help="print the pre-run cost ceiling for these options — "
                        "worst-case arithmetic and the measured typical range — "
                        "and exit without searching")
    p.add_argument("--shift-allowance", type=float, default=None,
                   help="a MEASURED systematic 2θ allowance in degrees — the "
                        "shift's amplitude a window must span, not the residual "
                        "scatter a template leaves; without one the engines "
                        "assume 0.05° and cap confidence, because a cell found "
                        "in a widened window absorbs the shift")
    p.add_argument("--no-validate", action="store_true",
                   help="skip the whole-profile Le Bail validation (caps every "
                        "candidate at medium)")
    p.add_argument("--json", metavar="FILE", default=None,
                   help="write the full IndexingResult as JSON")
    args = p.parse_args(argv)

    from .indexing import SearchSpec, index_pattern
    from .io.readers import read_pattern
    from .schemas.instrument import Geometry, Instrument

    data = read_pattern(args.pattern)
    instrument = Instrument.debye_scherrer(wavelength=args.wavelength)
    if args.geometry != "debye_scherrer":
        # built rather than assigned: Geometry's validator refuses a
        # bragg_brentano with no radius, and that refusal is the point
        instrument = instrument.model_copy(update={"geometry": Geometry(
            kind=args.geometry, goniometer_radius_mm=args.radius)})
    spec_kw: dict = {}
    if args.systems:
        spec_kw["systems"] = tuple(s.strip() for s in args.systems.split(","))
    for name, value in (("min_d_axis", args.min_d), ("max_d_axis", args.max_d),
                        ("budget_seconds", args.budget),
                        ("total_budget_seconds", args.total_budget),
                        ("shift_allowance_deg", args.shift_allowance)):
        if value is not None:
            spec_kw[name] = value
    spec = SearchSpec(**spec_kw)
    engine_names = (tuple(e.strip() for e in args.engines.split(","))
                    if args.engines else None)

    if args.ceiling:
        _print_ceiling(spec, engine_names, validate=not args.no_validate)
        return 0

    result = index_pattern(data=data, instrument=instrument,
                           spec=spec, preset=args.preset, engines=engine_names,
                           validate=not args.no_validate)
    _print_index(result)
    if args.json:
        from pathlib import Path

        Path(args.json).write_text(result.model_dump_json(indent=2),
                                   encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0 if result.best_or_none() is not None else 1


def _print_ceiling(spec, engine_names, *, validate: bool) -> None:
    """The pre-run cost answer, printed with its own epistemics: the search and
    probe lines are arithmetic the per-system budgets enforce, the validation
    line is a measured range, and the typical line is why the worst case is not
    an ETA (``engines.estimate_ceiling``)."""
    from .indexing.engines import estimate_ceiling

    est = estimate_ceiling(spec, engines=engine_names, validate=validate)
    lo, hi = est.validation_seconds_each
    t_lo, t_hi = est.typical_seconds
    print(f"worst case: {est.worst_case_seconds:.0f} s   "
          f"(search {est.search_seconds:.0f} + probe {est.probe_seconds:.0f}, "
          "arithmetic on the per-system budgets; "
          f"+ validation {est.validation_calls} fits x {lo:g}-{hi:g} s, "
          "a measured range — Le Bail cost is data-dependent)")
    print(f"measured typical: {t_lo:g}-{t_hi:g} s per real dataset "
          "(searches finish their systems early far more often than not)")
    print(f"a --total-budget binds within ~{est.granularity_seconds:g} s "
          "(the longest uninterruptible stretch)")
    if est.unmodelled:
        print(f"NOT modelled: engine(s) {', '.join(est.unmodelled)} — "
              "the worst case above omits their cost")


def _print_index(result) -> None:
    print(f"engines: {', '.join(result.engines_run) or 'none'}   "
          f"systems: {', '.join(result.systems_searched) or 'none'}   "
          f"lines: {result.n_usable_lines}   "
          f"validated: {'yes' if result.validated else 'no'}")
    incomplete = [s for s, done in result.search_complete.items() if not done]
    if incomplete:
        print(f"search INCOMPLETE in: {', '.join(incomplete)} — a negative "
              "result there is not evidence")
    print()
    if not result.candidates:
        print("no candidate cell in the systems searched.")
    for i, c in enumerate(result.candidates, start=1):
        a, b, cc, al, be, ga = c.cell
        print(f"{i:2}. [{c.confidence:^6}] {c.system} {c.centring}"
              f"   {a:.5f} {b:.5f} {cc:.5f} Å  {al:.3f} {be:.3f} {ga:.3f}°"
              f"   V = {c.volume:.2f} Å³")
        print(f"      found by {', '.join(c.found_by)};  indexed "
              f"{c.n_indexed}/{c.n_lines} lines;  chi2_red {c.chi2_red:.2f}"
              + (f";  Le Bail Rwp {c.lebail.rwp:.4f}, "
                 f"{c.lebail.predicted_but_absent} of "
                 f"{c.lebail.n_reflections} reflections absent"
                 if c.lebail is not None else ""))
        if c.confidence_caveats:
            print(f"      not higher because: {', '.join(c.confidence_caveats)}")
    best = result.best_or_none()
    print()
    if best is None:
        print("NO CELL: the result abstains — see the diagnostics below.")
    else:
        print(f"CELL: {best.system} {best.centring} "
              f"{best.cell[0]:.5f} {best.cell[1]:.5f} {best.cell[2]:.5f} Å "
              f"{best.cell[3]:.3f} {best.cell[4]:.3f} {best.cell[5]:.3f}°")
    for diag in result.diagnostics:
        print(f"  [{diag.level:^7}] {diag.code}: {diag.message}")
        # ``where`` is load-bearing for the run-level codes — it is the field
        # that names which systems INDEX_BUDGET_EXHAUSTED left truncated or
        # unreached, which no message prose restates
        for entry in diag.where:
            print(f"           - {entry}")
    for c in result.candidates:
        for diag in c.diagnostics:
            print(f"  [{diag.level:^7}] {diag.code} (candidate "
                  f"{c.system} {c.centring} V={c.volume:.1f}): {diag.message}")


if __name__ == "__main__":
    raise SystemExit(main())
