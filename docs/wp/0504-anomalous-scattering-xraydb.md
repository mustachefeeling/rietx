# WP-0504 — Anomalous f′, f″ via xraydb

Milestone: v0.5 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Anomalous f′,f″ at arbitrary λ via **xraydb** (Cromer-Liberman + Chantler;
  periodictable's Henke tables cap at 30 keV — wrong tool)

## Context pointers

- Extends the Waasmaier-Kirfel f₀ machinery in
  `crystallography/scattering.py`; f = f₀ + f′ + i·f″ changes the structure
  factor to complex arithmetic on a path that currently may assume real f —
  audit before estimating.
- WP-0305 computes µ per phase; if xraydb serves both, share the dependency.

## Inherited

From **WP-0305** (Brindley, landed 2026-07-23) — the "share the dependency"
pointer above now has a decided history. **xraydb was deliberately not pulled
in**: it drags sqlalchemy, and 0305 instead bundled `data/mu_McMaster.dat`, an
energy-trimmed (2–120 keV) three-column extract of DABAX `CrossSec_McMaster.dat`
(McMaster 1969; ATTRIBUTION.md updated). 0305 explicitly deferred the decision
to this WP: "revisit the coordination when WP-0504 actually needs f′/f″." So
this WP owns the call — take the sqlalchemy dependency and possibly re-source µ
through xraydb, or keep the bundled table and add f′/f″ separately.

Two measured facts that constrain it: `crystallography/attenuation.py`
interpolates log-log and **refuses** a wavelength whose grid interval contains
an absorption edge rather than smearing it — and edges are exactly the regime
f′/f″ exists to describe, so this WP either extends or replaces that guard.
And the bundled table's accuracy vs NIST Hubbell-Seltzer at 8 keV is ≤2.5 % for
Z ≥ 9 but B −7 %, O −3.6 % (McMaster low-Z weakness), which is one argument for
switching sources rather than adding to it.

Also standing from the design record: **do not pull in periodictable's Henke
tables** — they cap at 30 keV and are the wrong tool (locked decision).

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
