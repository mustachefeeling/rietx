# WP-1516 — Stacking faults: DIFFaX in and out, then the recursion

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: 1512 (the component a diffuse curve enters as)
Priority: P3 2026-09-28 — a workaround covers it (DIFFaX by hand plus 1512's member); rated down a rung while 1512 has not landed

## Goal

A layered phase declares its layers and a transition matrix. First rung:
rietx writes the DIFFaX input for it, reads DIFFaX's output into WP-1512's
component, and scans a probability with the covariance handled. Second
rung: rietx computes the diffuse term itself by the Treacy-Newsam-Deem
recursion, with the transition probabilities as refinable parameters.

## Context

**Unfenced 2026-09-28.** "Stacking faults (DIFFaX-style recursion)" sat in
ROADMAP § v2+ with no issue. The grounds are in DESIGN.md § Locked
decisions, *Structure fence revised*.

**Source.** `solution case 1` (private corpus map § 5), described in
WP-1510. Electron diffraction showed heavy streaking along the stacking
axis, and the person asked for "the quantitative route". The agent's
pipeline:

1. **Source and build.** The DIFFaX distribution page now sits behind a
   sign-in wall, and `curl` saved the sign-in page as the `.tar.gz`. It was
   noticed only when `tar` failed. The source came from a 2010 Wayback
   snapshot, compiled with one ad hoc `gfortran` line.
2. **Layers by hand.** Two layer types from the space-group operators and
   their inversion images, with the stacking vector and layer spacing from
   the refined cell. Scattering factors, Biso and wavelength were copied by
   hand into the input text. DIFFaX's own line-broadening line was
   independent of rietx's profile.
3. **Diffuse by difference.** Faulted minus ideal, convolved with a
   hand-written Lorentzian. The difference carried spikes where Bragg peaks
   cancelled imperfectly, and the person noticed them as "weird structure"
   in the background. A 0.3° median filter removed them.
4. **Into the fit.** Through the background slot with an outer refit loop.
   WP-1512 has the details, and why that slot breaks on today's tree.
5. **Probabilities by grid.** Switch and slip probabilities scanned on
   grids (about 13 and 9 points), the minimum from a three-point parabola,
   the esd from Δχ² = 1 against the agent's own Poisson weights. All of it
   happened outside the parameter table, so nothing else's esd saw it.
6. **Findings the physics needed.** In-plane translation faults broaden only
   some reflection classes, and 00l rows are immune to any in-plane slip.
   That is why strong streaking came with no powder width anomaly. A
   random sequence of two layer configurations was preferred over
   segregated or alternating stacking.

From the request to the first joint fit took under 40 minutes, the build
included.

**Licences.** GSAS-II's LICENSE describes DIFFaX as "not copyrighted;
distributed with direct permission of M. Treacy". A review subagent read
that; re-read it before relying on it. So DIFFaX is not vendored. Writing its
input and reading its output are I/O, and the recursion itself may be
implemented from the paper. FAULTS ships with FullProf, and TOPAS's
supercell method is closed, so both are papers only (DESIGN.md § Locked
decisions). GSAS-II wraps DIFFaX rather than reimplementing it.

**A second native route.** The TOPAS approach averages explicit supercells
(Coelho, Evans & Lewis 2016). rietx's own Bragg machinery can already
evaluate a large P1 supercell: the run built a 128-atom one to test an
in-plane doubling. Averaging random stacks that way needs no new physics,
only a generator and a cost measurement. Measure it against the recursion
before building either.

**Design questions.** The layer schema. Where the calculation sits relative
to the frozen-per-stage rule (a probability is continuous; the layer list
is not). How the diffuse term is convolved with rietx's instrument profile
rather than a second broadening model. Whether a native calculation
separates Bragg and diffuse parts by construction, which removes the spike
problem. The Jacobian: FD through the component is smooth in the
probabilities.

## Non-goals

- Turbostratic disorder and total scattering (PDF, #192).
- Modulated structures (superspace, #258), still fenced.

## Tasks

- [ ] Rung 1: a layer schema; a DIFFaX input writer from a `Structure` and
      the layers; a reader for its output; the result into WP-1512's
      component; a probability scan whose esd goes through the table.
      Tested against a public DIFFaX example.
- [ ] Measure the supercell-average route against the recursion on one
      case. Record the choice.
- [ ] Rung 2: the native calculation, with DIFFaX output on the same input
      as its oracle, and probabilities as parameters.
- [ ] Manual Part 2 equation with its `*Source:*` line; Part 1 chapter;
      `help.py`.
- [ ] Skill: a `references/` shape file for a layered phase with streaks or
      a diffuse hump.

## Acceptance

Rung 1: a public DIFFaX example round-trips through the writer and reader.
Rung 2: the native diffuse term agrees with DIFFaX on the same input to a
stated tolerance, and a probability refined on a synthetic faulted pattern
recovers its value within its esd.

```sh
.venv/bin/python -m pytest tests/test_stacking*.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Treacy, M. M. J., Newsam, J. M. & Deem, M. W. (1991). *Proc. R. Soc. Lond.
  A* 433, 499–520. DIFFaX.
- Casas-Cabanas, M., Reynaud, M., Rikarte, J., Horbach, P. &
  Rodríguez-Carvajal, J. (2016). *J. Appl. Cryst.* 49, 2259–2269. FAULTS.
  Verify the citation before quoting it.
- Coelho, A. A., Evans, J. S. O. & Lewis, J. W. (2016). *J. Appl. Cryst.*
  49, 1740–1749. Supercell averaging. Verify the citation before quoting it.

## Handover log

- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1510 to 1515 and 1517. Nothing started.
