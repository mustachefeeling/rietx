"""v0.1 acceptance: Le Bail + Rietveld of NAC (Na2Ca3Al2F14) at APS 11-BM.

Data: GSAS-II tutorials, 11BM_NAC.fxye (λ = 0.4139090 Å from 11bm_gsas.prm).
Structure: COD 1000236 (Courbion & Ferey, 1988), cubic I2₁3, a = 10.257 Å.
"""

from pathlib import Path

import pxrdref as pr

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"
WAVELENGTH = 0.4139090  # from 11bm_gsas.prm (INS 1 ICONS)


def main() -> None:
    data = pr.read_pattern(DATA / "11BM_NAC.fxye")
    print(f"pattern: {len(data.two_theta)} points, "
          f"{data.two_theta[0]:.2f}-{data.two_theta[-1]:.2f} deg, "
          f"sigma from file: {data.sigma is not None}")

    structure = pr.Structure.from_cif(str(DATA / "cod_1000236.cif"))
    phase = structure.phases[0]
    print(f"phase: {phase.name}, {phase.space_group}, a={phase.cell.a.value} A, "
          f"{len(phase.atoms)} asymmetric atoms")

    instrument = pr.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    # starting profile guesses in the right decade for 11-BM resolution
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    from pxrdref.schemas.instrument import BackgroundChebyshev
    instrument.background = BackgroundChebyshev.with_terms(6)

    limits = (2.0, 24.0)

    # --- Le Bail first: cell + profile without the structure
    ref_lb = pr.Refinement(structure, instrument)
    lebail = ref_lb.fit(data, mode="lebail", two_theta_limits=limits)
    a_lb = ref_lb.fitted_structure.phases[0].cell.a.value
    print(f"\nLe Bail:  status={lebail.status}  Rwp={lebail.statistics.rwp:.4f}  "
          f"GoF={lebail.statistics.gof:.2f}  a={a_lb:.6f} A")

    # --- Rietveld seeded with the Le Bail cell/profile
    # The Le Bail FitReport flags unmatched observed peaks at 7.5, 12.3, 14.4
    # and 21.3 deg — exactly the fluorite 111/220/311/422 positions at this
    # wavelength: the classic CaF2 impurity in NAC synthesis.  Add it.
    structure2 = ref_lb.fitted_structure.model_copy(deep=True)
    instrument2 = ref_lb.fitted_instrument.model_copy(deep=True)
    structure2.phases[0].scale.value = 1e-6
    structure2.phases.append(pr.Phase(
        name="CaF2",
        space_group="F m -3 m",
        cell=pr.Cell.cubic(5.4631),
        atoms=[
            pr.Atom(label="Ca", species="Ca2+", x=pr.Parameter(value=0.0),
                    y=pr.Parameter(value=0.0), z=pr.Parameter(value=0.0),
                    biso=pr.Parameter(value=0.6, min=0.0, max=25.0)),
            pr.Atom(label="F", species="F1-", x=pr.Parameter(value=0.25),
                    y=pr.Parameter(value=0.25), z=pr.Parameter(value=0.25),
                    biso=pr.Parameter(value=0.9, min=0.0, max=25.0)),
        ],
        scale=pr.Parameter(value=1e-7, min=0.0, transform="softplus"),
    ))
    ref = pr.Refinement(structure2, instrument2)
    plan = pr.RefinementPlan.mccusker_default()
    plan.stages.append(pr.Stage("biso", ["phases.*.atoms.*.biso"]))
    result = ref.fit(data, plan=plan, two_theta_limits=limits)
    a = ref.fitted_structure.phases[0].cell.a.value
    a_err = result.parameter("phases.0.cell.a").stderr
    print(f"Rietveld: status={result.status}  Rwp={result.statistics.rwp:.4f}  "
          f"GoF={result.statistics.gof:.2f}")
    print(f"          a = {a:.6f} +/- {a_err if a_err else float('nan'):.6f} A "
          f"(COD reference 10.257(1); high-accuracy powder ~10.2497-10.2506)")
    for d in result.diagnostics:
        print(f"          [{d.level}] {d.code}: {d.message}")

    report = pr.build_report(result)
    print("\nFitReport:", report.summary)
    for r in report.regions[:5]:
        print(f"  region {r.two_theta_lo:6.2f}-{r.two_theta_hi:6.2f} deg  "
              f"localRwp={r.local_rwp:.3f}  chi2share={r.chi2_share:.1%}  "
              f"max|d/sig|={r.max_abs_delta_over_sigma:.1f}")

    try:
        result.plot(path=str(Path(__file__).parent / "nac_fit.png"),
                    two_theta_range=(2.0, 12.0))
        print("\nplot written to examples/nac_fit.png")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
