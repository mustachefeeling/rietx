# WP-1436 — `k` is the wavevector everywhere else

Milestone: unscheduled · Status: ⬜
Depends on: 1437 (both touch `help.py` and the manual; rebase onto it)

## Goal

Every symbol the package prints matches the source its module cites. `sinθ/λ`
is written `s` in equations and `stol` in python, the QPA `k` becomes `zmv`,
and the manual's notation table stops contradicting the package's own `q`
field. No computed number moves.

## Context

A comment on the project's LinkedIn post objected that "k should equal to
2/lambda \* sin(theta)". That quantity is the reciprocal lattice vector length
`1/d`. They were decoding a symbol that normally means the wavevector.

### Where our `k` came from

Not from the paper we cite. `src/rietx/data/f0_WaasKirf.dat` is the ESRF DABAX
file the package ships and parses, and its preamble at lines 33 and 36 reads:

```
#UD    f0[k] = c + [SUM a_i*EXP(-b_i*(k^2)) ]
#UD  where k = sin(theta) / lambda and c, a_i and b_i
```

Line 40 of that file is `#C  The original README fime from D. Waasmaier & A.
Kirfel follows here :`. So `k` sits in DABAX's own editorial preamble, above
the point where the authors' text begins. `scattering.py:3` repeats the file's
spelling while citing the paper.

Waasmaier & Kirfel (1995) use `s`: "Results for distinct values of s = sin Θ/λ
obtained from atomic wavefunctions are compiled in International Tables for
Crystallography, Vol. C". Their equation (1) is
$f(s) = \sum a_i \exp(-b_i s^2) + c$. The letter `k` appears nowhere in that
role.

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

The dictionary evidence settles it alone. In `cif_core.dic` the canonical name
is `_refln.sin_theta_over_lambda`, units `reciprocal_angstroms`, evaluated as:

```
r.sin_theta_over_lambda  =   Sqrt ( h * G * h ) / 2.
```

with `G = _cell.reciprocal_metric_tensor`. The form-factor method in the same
dictionary then binds `s = r.sin_theta_over_lambda` and sums over `s*s`. So the
IUCr computes $\sqrt{h^\mathsf{T} G^* h}$, the commenter's
$2\sin\theta/\lambda$, halves it, and calls the result `s`. That is
`structure_factor.py:335` exactly, `k = 1.0 / (2.0 * d)`.

Fetch the dictionary with `gh api`, since `iucr.org` 403s to curl and WebFetch:
`https://raw.githubusercontent.com/COMCIFS/cif_core/master/cif_core.dic`.

### Why the identifier and the symbol differ

`s` is already bound in both target modules. `scattering.py:66` and `:142` bind
`s = species.strip()`; `structure_factor.py:436` binds
`s = xp.asarray(astar, ...)`. A bare `s` would shadow live variables in the two
files being changed.

So `s` in maths, where scope does not exist and the paper's letter is right,
and `stol` in python, following cctbx. Record that split in `CLAUDE.md`, or a
later session will collapse one half into the other.

### The collision is already scheduled

`src/rietx/crystallography/magnetic/` exists today. Five queued WPs (1326,
1327, 1328, 1329, 1418) already write `k` for the magnetic propagation vector,
which is that field's standard symbol. When that track lands, `k` will mean the
propagation vector inside the same subpackage where it now means sinθ/λ.

### The rest of the audit (2026-09-17)

About 100 physics symbols across `crystallography/`, `model/`, `optimize/`,
`indexing/`, `report/`, `schemas/`, the manual and `help.py` were checked
against the source each module cites. The package is well sourced.
`optimize/statistics.py` and `model/corrections.py` are exemplary, and the
Caglioti X/Y fork is handled correctly at `caglioti.py:18`.

Five further findings are in scope here:

| Symbol | Anchor | Quantity | Why |
|---|---|---|---|
| `k` | `qpa.py:168` | per-phase Z·M·V | Hill & Howard give the product no letter, and `K` in QPA means O'Connor & Raven's calibration constant, whose method `qpa.py:22` fences to v2. Both callers already pass `[z.zmv for z in zmvs]` |
| `Q` | `manual.md:163` against `schemas/indexing.py:537` | 4π sinθ/λ against 1/d² | The notation table contradicts the package's own public `PeakLine.q` |
| `1/d` | missing from `manual.md:163` | the third reciprocal length | It is what half the manual calls `Q`, and it is what the comment named. `forward-model.md:50` and `peak-positions.md:125` both spell out "sinθ/λ = 1/2d" to defuse the same confusion |
| "F20" | `fom.py:47`, `:581` | user-facing diagnostic prose | Claims Smith & Snyder define F₂₀ on the first twenty. `f_n` and `FOM_N` are correct; the sentence overclaims |
| `gamma` | `voigt.py:40` | returns a HWHM from inputs named `gamma_g`/`gamma_l`, which are FWHMs | The docstring says so, the names do not |

### Sites for the rename

Equations and prose: `docs/manual/intensities.md` lines 9, 10, 28, 29, 128;
`docs/manual/manual.md:163`; `CLAUDE.md:486`;
`docs/skill/rietx/references/diagnostics.md:36` plus its two committed copies
under `.agents/skills/` and `.claude/skills/`.

Identifiers and docstrings: `crystallography/scattering.py` lines 3, 6, 8, 96,
163, 164, 166, 176; `crystallography/structure_factor.py` lines 9, 36, 256,
335, 373, 434; `crystallography/dispersion.py:5`; `tests/test_dispersion.py:122`.

`f0(species, k)` at `scattering.py:163` is **internal**:
`tests/api_surface.py:189` declares `rietx.crystallography` internal by
sentence, so the rename trips no partition test and needs no compatibility
entry. Every call site passes the argument positionally.

### Fences

`src/rietx/data/f0_WaasKirf.dat` is vendored third-party data, parsed
byte-sensitively by `scattering._load_table`, and its header records provenance
under the name the extraction was made with. Leave it alone. This is the
reasoning already in `tests/test_no_stale_name.py`'s `ALLOWED`, which exempts
the two sibling data files for the same reason.

## Non-goals

- The quantity itself. $\sin\theta/\lambda$ is what the tabulated $b_i$
  coefficients are fitted against, so $2\sin\theta/\lambda$ would be a factor of
  4 in the exponent. Every refined number must come back bit-identical.
- Renaming indexing's `Q = 1/d²`. It is de Wolff's letter and load-bearing in
  that literature. It gets a declaration, not a rename.
- The `help.py` polarisation defect, which is WP-1437.
- Vendored data file headers, per the fence above.

## Tasks

- [ ] `scattering.py`: `k` → `stol` in identifiers and docstrings, `s` in the
      rendered equation. Includes the `f0` signature and the `f0(element, k=0)`
      prose at line 96.
- [ ] `structure_factor.py` and `dispersion.py`: the same pass, module
      docstrings included. Each `k = 1.0 / (2.0 * d)` site gains the `1/(2d)`
      gloss line 335 already has.
- [ ] `qpa.weight_fractions(k, ...)` → `zmv`. Two call sites, both already
      passing `.zmv`.
- [ ] `manual.md:163` becomes **two** rows, because the table is keyed
      `| quantity | unit |` and 1/d² is Å⁻²:

      | a reciprocal length | Å⁻¹: `s = sinθ/λ = 1/2d`, `|d*| = 1/d = 2s`, and `Q = 4π sinθ/λ` |
      | a reciprocal length squared | Å⁻²: `Q = 1/d²`, the indexing chapters' `Q` and the `PeakLine.q` field |

- [ ] `intensities.md` equations to `s`; `CLAUDE.md:486`, plus a conventions
      clause recording the maths/identifier split with its reason.
- [ ] `docs/skill/rietx/references/diagnostics.md:36`, then re-sync the two
      committed copies with `rietx skill --install . --copy`.
- [ ] `fom.py:47` and `:581`: say F_N at N = 20 instead of claiming Smith &
      Snyder define F₂₀. One sentence, and it needs no ruling on the paper.
- [ ] `voigt.py:40`: name the returned HWHM so a caller cannot read it as the
      FWHM its inputs are.
- [ ] Tests: `test_dispersion.py:122`'s local, and a bit-identity check that a
      converged fit on a structural standard returns the same parameters before
      and after. Plot obs/calc/diff to `tests/output/` and look at it.
- [ ] Skill: the `diagnostics.md` row above is the change. The body needs
      nothing, since an agent driving rietx never types this symbol: it appears
      in no parameter path, no diagnostic code and no result field.

### Deliberately not generalised

Recorded here so a later session knows these were seen and left:

- **Sixteen letters carry two or more physics meanings** and almost every
  meaning is source-correct. `T` is both ITC's Debye-Waller factor and ITC's
  absorption path length; `M` is both Stephens' 1/d² and Dollase's
  multiplicity. The collision is unavoidable once each module follows its own
  source, and the package already defends against it correctly: public
  signatures spell the physics (`x_size`, `y_strain`, `along_mm`, `axial_sl`),
  so the ambiguous letters live only in docstring equations that define them.
  Renaming them would break the "physics not letters" rule it is meant to serve.
- **`Λ(hkl)`** at `stephens.py:20`. Package-local: FullProf writes `D_ST`
  (verified against its manual), Stephens and GSAS-II write Γ_S. It is defined
  by equation (2) at its point of use and never ambiguous inside the package.
- **`U*`** at `adp.py:14`. cctbx's letter, where the cited IUCr nomenclature
  report (Trueblood 1996) writes `β^ij`. Naming drift, definition exact.
- **`β` for FWHM** at `microstructure.md:34`, where Langford & Wilson 1978 are
  said to use `β` for the integral breadth. **Unverified**: that paper is not in
  the local corpus. Needs the paper before anyone acts on it.
- **`caglioti.apparent_size(..., k=SCHERRER_K)`** at `caglioti.py:136` and
  `:165`. A bare `k`, but every call site is positional and `SCHERRER_K`
  carries the name.
- **`stephens.py`'s missing √(8 ln 2)** against FullProf's `D²_ST`. Checked and
  cleared: `stephens.py:24-26` declares the omission and warns "Never transfer
  a literature S_HKL without checking numerically". The house convention rule
  working.

## Acceptance

Every refined number is unchanged, because this is a rename. Pin that rather
than asserting it.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_dispersion.py tests/test_help.py tests/test_gui_manual.py
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

The Sphinx build is load-bearing. `intensities.md`'s equations carry `{source}`
directives whose symbols must import, and `tests/test_manual.py:801` checks
every labelled equation has one.

## References

- Waasmaier, D. & Kirfel, A. (1995). *Acta Cryst.* **A51**, 416-431. Local copy
  at `~/zotero-linker/derived/34WYGAJ4/s0108767394013292.md`.
- IUCr CIF core dictionary, `_refln.sin_theta_over_lambda` and
  `_refln.form_factor_table`. [COMCIFS/cif_core](https://github.com/COMCIFS/cif_core).
- *International Tables for Crystallography* Vol. C, Tables 6.1.1.1 and
  6.1.1.3. These are the values Waasmaier & Kirfel fitted.
- DABAX, [oasys-kit/DabaxFiles](https://github.com/oasys-kit/DabaxFiles).
- cctbx `cctbx/eltbx/xray_scattering/__init__.py`, for the `stol` precedent.
- Hill, R. J. & Howard, C. J. (1987). *J. Appl. Cryst.* **20**, 467, for the
  QPA symbols; O'Connor, B. H. & Raven, M. D. (1988). *Powder Diffr.* **3**, 2,
  for the `K`-factor the letter is reserved for.

## Handover log

### 2026-09-17 — the audit, and what it moved

Opened from a comment on a LinkedIn post about the project, which read our `k`
as the wavevector and proposed `2 sinθ/λ` in its place. The commenter had the
wrong formula and the right instinct. What a reader of this file now knows: the
symbol came from the DABAX file the package parses rather than the paper the
docstring cites, the IUCr's own dictionary writes `s` in a normative method
expression, and the letter is scheduled to collide with the magnetic
propagation vector inside `crystallography/`.

*Measured.* Eight sources surveyed for the sinθ/λ symbol, five in the `s`
family. About 100 physics symbols audited across seven subpackages plus the
manual and `help.py`. Four differ from their cited source; sixteen letters are
ambiguous and almost all defensibly so. `s` is unavailable as a python
identifier in both target modules, which is why the split is `s` in maths and
`stol` in code.

*Gotchas.* The main checkout was two sessions stale when this WP was numbered,
so it was first written as 1434 and renumbered after `EnterWorktree` showed
1434 and 1435 already on `main`. Re-read the WP directory from the worktree.

*Next.* Land [1437](1437-a-formula-the-code-does-not-compute.md) first, since
both touch `help.py` and the manual, then rebase this branch onto it and work
the task list top down.
