# WP-1002 — CI matrix

Milestone: v1.0 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- CI: linux + macOS, Py 3.11-3.13 (+3.14 allow-fail); `[jax]`/`[torch]`
  optional jobs; nightly heavy validation with fetched data

## Inherited

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — the "fetched data" in
the scope above has a known obstacle:

- **iucr.org is behind a Cloudflare JS challenge.** Every QARR round-robin
  pattern was retrieved through the Internet Archive, URL form
  `web.archive.org/web/2020id_/…/QARR/col/<name>.prn`. A fetch-on-demand job
  needs the same route; pointing it at the live site will fail in a way that
  looks like a network flake.
- **The `slow` marker is the load-bearing runtime knob.** Full suite is ~2 min
  (was ~21 s before the real-data acceptance landed); `-m "not slow"` stays
  ~20 s. That split is what makes a per-push job viable and a nightly job
  necessary — 23 tests are currently `slow`.

From **WP-0401** (op shim, landed 2026-07-24): `tests/test_backend_shim.py`
asserts **bit-identity** against environment-pinned npz goldens in
`tests/data/backend_goldens/`. A multi-OS × multi-Python matrix is exactly the
thing that breaks bit-identity (BLAS variants, libm differences). Decide up
front whether those goldens are pinned to one canonical job or relaxed to a
tolerance elsewhere — the re-baseline rule is in `tests/data/README.md`
(regenerate via `python -m tests.test_backend_shim`, only from a green tree).

## Tasks

- [ ] Expand this stub into a full WP before starting

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
