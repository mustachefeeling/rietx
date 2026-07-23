# WP-0310 — v0.3 acceptance: SRM 676a corundum + IUCr QPA round robin

Milestone: v0.3 · Status: 🔶 in progress
Depends on: WP-0304, WP-0305

## Goal

The measured, committed acceptance run that closes v0.3: quantitative phase
analysis on NIST SRM 676a and the IUCr QPA round-robin mixtures, within
tolerances chosen to match what each reference actually is.

## Context

Read [../DESIGN.md](../DESIGN.md#testing--validation-policy) before choosing
any tolerance. The policy, in short: **NIST certificates are absolute anchors**
(with their stated uncertainties); **other codes are consistency checks** with
convention-aware bands, not ground truth. v0.2 learned this the hard way twice
and both lessons apply directly here:

1. *Comparing against another code means adopting its protocol.* Guessing a
   plausible protocol for the fluorapatite comparison gave Rwp 16 % and
   +390 ppm; mirroring GSAS's actual refine flags, held parameters and
   excluded regions gave 9.73 % vs its 10.05 % on a channel count matching its
   record exactly (5750). If any part of this WP compares against GSAS-II,
   mirror its protocol and check the channel count before believing anything.
2. *A disagreement's shape is evidence.* Uniform relative offsets mean a scale
   convention; structured ones mean physics. Assert the shape, don't shrug at
   the magnitude.

For QPA specifically, the honest failure modes to characterise rather than
tune away: microabsorption (WP-0305's µR fence), preferred orientation
(WP-0307 — the round-robin mixtures are notorious for it, especially the
platy phases), and the fact that fractions are of the modelled crystalline
content only. The IUCr round robin's own published spread across participants
is the realistic yardstick: matching the weighed composition better than the
round-robin participant spread would be a suspicious result, not a triumph.

Practical: datasets need provenance entries in
[`tests/data/README.md`](../../tests/data/README.md) with every reference
value, following the existing entries for `11BM_NAC.fxye`,
`nist_srm660c_100a.cif` and `FAP.XRA`. Mark the tests `@pytest.mark.slow`
(the `-m "not slow"` path must stay fast) and write obs/calc/diff PNGs to
`tests/output/` — Rwp hides locally-bad fits, and every test refinement in
this repo plots.

## Non-goals

- Amorphous / internal-standard quantification (v2 fence) — if a round-robin
  sample has an amorphous component, state it rather than fitting it.
- New physics. If the acceptance run needs physics that doesn't exist, that is
  a new WP, not a quiet extension of this one.

## Tasks

- [x] Acquire SRM 676a corundum + IUCr round-robin sample data; record
      provenance, licence and every reference value in `tests/data/README.md`
- [ ] `tests/test_acceptance_srm676a.py`: corundum QPA against the certified
      values, tolerance from the certificate's stated uncertainty
- [ ] `tests/test_acceptance_qpa_roundrobin.py`: round-robin mixtures against
      the weighed compositions, tolerance referenced to the published
      participant spread
- [ ] Both marked `slow`, both writing PNGs to `tests/output/`
- [ ] Record the measured results in `docs/milestones/v0.3.md` (create it),
      including what is **not** met and why — the v0.2 records are the model
      for how honest that section has to be
- [ ] Flip the v0.3 row in [../ROADMAP.md](../ROADMAP.md) when green

## Acceptance

QPA weight fractions within the documented tolerance of the certified/weighed
values, with any residual discrepancy characterised (microabsorption, PO, or
convention) rather than absorbed into a widened band.

```sh
.venv/bin/python -m pytest tests/test_acceptance_srm676a.py tests/test_acceptance_qpa_roundrobin.py -q
.venv/bin/python -m pytest            # full suite, incl. v0.1/v0.2 acceptance unchanged
```

## References

- NIST SRM 676a — quantitative-analysis alumina certificate.
- Madsen, Scarlett, Cranswick & Lwin (2001) J. Appl. Cryst. 34, 409 — IUCr QPA
  round robin, samples 1-4.
- Scarlett et al. (2002) J. Appl. Cryst. 35, 383 — round robin part II
  (participant spread).

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
- **2026-07-23** — **data acquired** (first checklist item done). *Done:* SRM
  676a certificate mined for certified values (a = 4.759355(80) Å, c =
  12.99231(15) Å at 22.5 °C, phase purity 99.02(1.11) %); 16 IUCr CPD
  round-robin ASCII patterns pulled into `tests/data/qarr/` (sample 1a–1h,
  sample 2, sample 4, + the six pure component phases); provenance, instrument,
  weighed compositions, participant-spread yardstick and a licence note added to
  `tests/data/README.md`. *Gotchas:* (1) the live iucr.org is behind a
  Cloudflare JS challenge — all QARR files were retrieved through the Internet
  Archive (`web.archive.org/web/2020id_/…/QARR/col/<name>.prn`); a
  fetch-on-demand script would need the same route. (2) `.prn` = plain 2-column
  ASCII (2θ°, counts), 5–150° at 0.02°, 7251 pts, Cu Kα doublet (graphite
  diffracted-beam mono; `.cpi` header λ = 1.54056 Å) — **the package has no
  reader for this format yet**, so the acceptance tests will need one (or a
  convert-to-fxye step). (3) NIST publishes **no raw 676a pattern**; the
  certified cell is an absolute anchor only — the "corundum QPA" test must lean
  on a lab corundum pattern (`qarr/corundum.prn`, provenance *not* documented as
  SRM 676a) and set a lab-realistic cell tolerance, not the 8-ppm certificate
  bound. (4) Sample 3 (amorphous) deliberately excluded per non-goals. (5)
  Licence: round-robin data was freely released for re-analysis but carries no
  explicit open licence — flagged in the README; confirm vendoring is OK before
  publishing. *Next:* write a `.prn`/`.cpi` reader, then the two acceptance
  tests (`test_acceptance_srm676a.py`, `test_acceptance_qpa_roundrobin.py`).
