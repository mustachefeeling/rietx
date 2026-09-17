# WP-1436 — `k` is the wavevector everywhere else

Milestone: unscheduled · Status: ⬜
Depends on: —

## Goal

The form-factor argument carries the symbol its own literature uses. $\sin\theta/\lambda$
is written `s` in every equation and `stol` in every identifier. No computed number moves,
and the manual's notation table states both reciprocal lengths so a reader can tell which
one a formula means.

## Context

`sinθ/λ` is currently spelled `k` throughout the scattering chain. A reader of the LinkedIn
post objected that "k should equal to 2/lambda \* sin(theta)". That quantity is the
reciprocal lattice vector length $1/d$. They were decoding a symbol that normally means the
wavevector.

### Where our `k` came from

Not from the paper we cite. `src/rietx/data/f0_WaasKirf.dat` is the ESRF DABAX file the
package ships and parses, and its preamble at lines 33 and 36 reads:

```
#UD    f0[k] = c + [SUM a_i*EXP(-b_i*(k^2)) ]
#UD  where k = sin(theta) / lambda and c, a_i and b_i
```

Line 40 of that file is `#C  The original README fime from D. Waasmaier & A. Kirfel follows
here :`. So the `k` spelling sits in DABAX's own editorial preamble, above the point where
the authors' text begins. `scattering.py:3` repeats the file's spelling while citing the
paper.

Waasmaier & Kirfel (1995) use `s`. From their introduction: "Results for distinct values of
s = sin Θ/λ obtained from atomic wavefunctions are compiled in International Tables for
Crystallography, Vol. C". Their equation (1) is $f(s) = \sum a_i \exp(-b_i s^2) + c$. The
letter `k` appears nowhere in that role.

### What the field uses (measured 2026-09-17)

| source | symbol for $\sin\theta/\lambda$ |
|---|---|
| IUCr CIF core dictionary | `s`, in the normative `_method.expression` |
| Waasmaier & Kirfel 1995 | `s` |
| cctbx | `stol` |
| pymatgen | `s`, `s2` |
| Dans_Diffraction | `s` |
| GSAS-II | `SQ`, docstring "(sin-theta/lambda)\*\*2" |
| xraylib | `q`, documented as "momentum transfer" |
| DABAX `f0_WaasKirf.dat` | `k` |
| rietx | `k` |

The dictionary evidence is the strongest of these and settles the question on its own. In
`cif_core.dic` the canonical data name is `_refln.sin_theta_over_lambda`, units
`reciprocal_angstroms`, and its evaluation method is:

```
r.sin_theta_over_lambda  =   Sqrt ( h * G * h ) / 2.
```

with `G = _cell.reciprocal_metric_tensor`. The form-factor method in the same dictionary
then binds `s = r.sin_theta_over_lambda` and writes the Cromer-Mann sum over `s*s`. So the
IUCr computes $\sqrt{h^\mathsf{T} G^* h}$, the commenter's $2\sin\theta/\lambda$, halves it,
and calls the result `s`. That is `structure_factor.py:335` exactly, `k = 1.0 / (2.0 * d)`.

Fetch the dictionary with `gh api`, since `iucr.org` 403s to curl and WebFetch:
`https://raw.githubusercontent.com/COMCIFS/cif_core/master/cif_core.dic`.

### Why the identifier and the symbol differ

`s` is already taken as a local name in both target modules. `scattering.py:66` and `:142`
bind `s = species.strip()`, and `structure_factor.py:436` binds `s = xp.asarray(astar,
...)`. A bare `s` would shadow live variables in the two files being changed.

The package also overloads `k` three further ways: the Miller index (`stephens.py`,
`qspace.py`, `lattice.py`), the Scherrer constant K, and the QPA calibration constant in
`qpa.weight_fractions(k, scales, ...)`. `stol` collides with none of them and says what it
holds. cctbx made the same call.

So: `s` in maths, where scope does not exist and the paper's letter is the right one, and
`stol` in python. Record that split in `CLAUDE.md` so a later session does not "fix" one
half into the other.

### Sites

Equations and prose:

- `docs/manual/intensities.md` lines 9, 10, 28, 29, 128
- `docs/manual/manual.md:163`, the notation table row
- `CLAUDE.md:486`, the angles-and-units convention line

Identifiers and docstrings:

- `src/rietx/crystallography/scattering.py` lines 3, 6, 8, 96, 163, 164, 166, 176
- `src/rietx/crystallography/structure_factor.py` lines 9, 36, 256, 335, 373, 434
- `src/rietx/crystallography/dispersion.py:5`
- `tests/test_dispersion.py:122`, a local

`f0(species, k)` at `scattering.py:163` is a public signature. Every call site found passes
the argument positionally, so the rename is safe, and it is still an observable break to
record under the preview promise (`docs/manual/using/compatibility.md`).

### Fences

`src/rietx/data/f0_WaasKirf.dat` is vendored third-party data, parsed byte-sensitively by
`scattering._load_table`, and its header records provenance under the name the extraction
was made with. Leave it alone. This is the reasoning already written into
`tests/test_no_stale_name.py`'s `ALLOWED`, which exempts the two sibling data files for the
same reason.

## Non-goals

- The quantity itself. $\sin\theta/\lambda$ is what the tabulated $b_i$ coefficients are
  fitted against, so $2\sin\theta/\lambda$ would be a factor of 4 in the exponent. Nothing
  here is a physics change, and every refined number must come back bit-identical.
- $Q = 4\pi\sin\theta/\lambda$. It is already spelled `Q` and agrees with the field.
- The Miller index `k`, the Scherrer K and the QPA `k`. Three separate overloads, none of
  them confusing in place.
- Vendored data file headers, per the fence above.

## Tasks

- [ ] `scattering.py`: `k` → `stol` in the identifier and the docstrings, `s` in the
      rendered equation. Includes the `f0` signature and the `f0(element, k=0)` prose at
      line 96.
- [ ] `structure_factor.py` and `dispersion.py`: the same pass, module docstrings included.
      Each of the three `k = 1.0 / (2.0 * d)` sites gains the `1/(2d)` gloss it already has
      at line 335.
- [ ] Manual: `intensities.md` equations to `s`, and the `manual.md:163` notation row to
      carry **both** reciprocal lengths with the factor of 2 between them, since that
      ambiguity is what the comment actually exposed. Suggested row: `$s = \sin\theta/\lambda
      = 1/2d$, $|d^*| = 1/d = 2s$, and $Q = 4\pi\sin\theta/\lambda$`.
- [ ] `CLAUDE.md:486`, and a conventions clause recording the maths/identifier split with
      its reason.
- [ ] Compatibility: record the `f0` signature change in
      `docs/manual/using/compatibility.md`, per "record every break".
- [ ] Tests: `test_dispersion.py:122`'s local, and a bit-identity check that a converged fit
      on a structural standard returns the same parameters before and after. Plot
      obs/calc/diff to `tests/output/` and look at it.
- [ ] Skill: none. An agent driving rietx never types this symbol, since it appears in no
      parameter path, no diagnostic code and no result field. Say so in the handover.

## Acceptance

Every refined number is unchanged, because this is a rename. Pin that rather than asserting
it.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_dispersion.py tests/test_manual_api.py tests/test_help.py
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
grep -rn "\bk\b" src/rietx/crystallography/scattering.py   # expect: no hits in this sense
```

The manual build is load-bearing here. `intensities.md`'s equations carry `{source}`
directives whose symbols must import, and `tests/test_manual.py` checks that every displayed
equation's `*Source:*` line resolves.

## References

- Waasmaier, D. & Kirfel, A. (1995). *Acta Cryst.* **A51**, 416-431. Local copy at
  `~/zotero-linker/derived/34WYGAJ4/s0108767394013292.md`.
- IUCr CIF core dictionary, `_refln.sin_theta_over_lambda` and
  `_refln.form_factor_table`. [COMCIFS/cif_core](https://github.com/COMCIFS/cif_core).
- *International Tables for Crystallography* Vol. C, Tables 6.1.1.1 and 6.1.1.3. These are
  the values Waasmaier & Kirfel fitted.
- DABAX, [oasys-kit/DabaxFiles](https://github.com/oasys-kit/DabaxFiles).
- cctbx `cctbx/eltbx/xray_scattering/__init__.py`, for the `stol` precedent.

## Handover log

- **2026-09-17** — created. Opened from a comment on a LinkedIn post about the project,
  which read our `k` as the wavevector and proposed `2 sinθ/λ` in its place. The commenter
  had the wrong formula and the right instinct. Chasing it found that the symbol came from
  the DABAX file we parse rather than from the paper we cite, and that the IUCr's own
  dictionary writes `s` in a normative method expression. The survey and the collision
  measurement are in Context and need no redoing. Next: work the task list top down.
