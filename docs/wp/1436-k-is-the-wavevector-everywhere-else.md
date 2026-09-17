# WP-1436 — `k` is the wavevector everywhere else

Milestone: unscheduled · Status: 🔄 2026-09-17 — claimed by @yue-here
Depends on: 1437, **merged 2026-09-17** (PR #371). This branch is cut from
`main` above it, so the rebase is done and its edit to `docs/manual/intensities.md`
is in the tree. No line of `help.py` writes sinθ/λ, and none of the names renamed
here appears there either (checked 2026-09-17), so this WP never opens that file.

## Goal

Every symbol the package prints matches the source its module cites. `sinθ/λ`
is written `s` in equations and `stol` in python, the QPA `k` becomes `zmv`,
and the manual's notation table stops contradicting the package's own `q`
field. No computed number moves.

## Context

A comment on the project's LinkedIn post objected that "k should equal to
2/lambda \* sin(theta)". That quantity is the reciprocal lattice vector length
`1/d`. They were decoding a symbol that normally means the wavevector.

This is not only a readability question. The same collision reached a number a
user can act on: [1437](1437-a-formula-the-code-does-not-compute.md) measured
`help.py`'s Lp against the Lp the code computes and found them 0.508× apart at
2θ = 90° for K = 0.99, with the ratio varying across the range, because the help
text's `K` was bound to a different quantity from the code's.

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

`s` is already bound in both target modules, in one of them in the same scope.
`structure_factor.py:436` binds `s = xp.asarray(astar, ...)` two lines below
the `k` at `:434`, inside `d_f2_d_uaniso`, so a bare `s` there would shadow a
live variable. `scattering.py:66` and `:142` bind `s = species.strip()` in
`normalize_species` and `detect_fallback`, other functions than `f0`, so in
that file the cost is one letter meaning two things in one module rather than
a shadowed name.

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

Six further findings are in scope here. Bare file names below resolve to
`src/rietx/optimize/qpa.py`, `src/rietx/indexing/fom.py` and
`src/rietx/model/profiles/{voigt,caglioti}.py`:

| Symbol | Anchor | Quantity | Why |
|---|---|---|---|
| `k` | `qpa.py:168` | per-phase Z·M·V | Hill & Howard give the product no letter, and `K` in QPA means O'Connor & Raven's calibration constant, whose method `qpa.py:22` fences to v2. Both callers already pass `[z.zmv for z in zmvs]` |
| `Q` | `manual.md:163` against `schemas/indexing.py:537` | 4π sinθ/λ against 1/d² | The notation table contradicts the package's own public `ObservedPeak.q` (`schemas/indexing.py:576`) |
| `1/d` | missing from `manual.md:163` | the third reciprocal length | It is what half the manual calls `Q`, and it is what the comment named. `forward-model.md:50` and `peak-positions.md:125` both spell out "sinθ/λ = 1/2d" to defuse the same confusion |
| "F20" | `fom.py:47`, `:583` | user-facing diagnostic prose | Claims Smith & Snyder define F₂₀ on the first twenty. **Settled against the paper**, below |
| `β` | `microstructure.md` 29, 34, 50 | FWHM in radians | Langford & Wilson write `β` for the *integral breadth* and `2w` for the FWHM. **Settled against the paper**, below |
| `gamma` | `voigt.py:40` | returns a HWHM from inputs named `gamma_g`/`gamma_l`, which are FWHMs | The docstring says so, the names do not |

### How the papers were searched, because they are OCR

The local corpus is OCR'd from PDFs and the damage is heavy in **tables and
maths**, light in **running prose**. Measured on these three: 422
`digit-hyphen-digit` runs in Langford & Wilson, because the journal sets
decimals as a middle dot and `0·8340` comes out `0-8340`; 45 places where the
digit 0 became the letter C; LaTeX scrambled past parsing. Smith & Snyder gives
`|Δ2θ|` as `| A 2 \theta |` and the page range `60-65` as `6065`.

Two rules for anyone re-checking this work:

- **Flatten whitespace before matching.** Subscripts are set as `F _ { 2 0 }`,
  so a pattern anchored on `F_` matches nothing and returns a clean, false
  zero. `re.sub(r"\s+", "", text)` first, then match.
- **A zero hit on a number the code cites is a search bug until proven
  otherwise.** Searching raw text for `1.0747` returns nothing; flattened it is
  there, in the Sphere row, and `0.8859` beside it. `caglioti.py:94-95` quotes
  that pair as 0.89 against 1.0747, the first rounded.

Every conclusion below rests on running prose, never on a table or an equation
image.

### Two findings settled against the papers (2026-09-17)

Both were opened as an agent's reading and closed by reading the source. In
each case **the code is right and only the prose drifted**, which bounds the
work to a comment and a sentence.

**Smith & Snyder (1979)** define F_N generally, as equation (1):
`F_N = (1/|Δ2θ|)·(N/N_poss)`. Their § *Recommendations for usage of F_N*,
subsection 1, says "it is recommended that **N be taken as 30**, or as the last
line if there are fewer than 30 lines in the entire pattern". Their worked
example happens to be `F₂₀ = 101 (0.009, 22)` for Cr₃Rh, because that pattern
had twenty lines reported. The string "F30" appears nowhere in the paper, so do
not write that it does.

`f_n` at `fom.py:372` is correct: the right formula, the right citation, `n` a
parameter, and `n_lines`/`n_possible` returned, which is exactly the paper's
recommended reporting format. What is wrong is the comment at `fom.py:47` and
the message it feeds at `:583`, which present N = 20 as the paper's definition.
N = 20 is in fact this package's own choice, aliased to
`PEAK_MIN_USABLE_LINES` so the scoring precondition cannot drift from the
figures it scores (`fom.py:48-51`). That reason is good and the value stays.
Only the attribution changes.

**Langford & Wilson (1978)** set their notation explicitly, warning it "does
not necessarily conform with that used previously in the literature". Their
list gives `2w` for "Full width at half maximum intensity (half-width)" and
`β` for "Integral breadth", and the text defines the integral breadth as "the
total area under the diffraction maximum divided by the peak intensity".

So `microstructure.md` does borrow their `β` for the quantity they call
`2w`, at lines 29, 34 and 50. The scope is the manual alone. `caglioti.py:88-97` is already exemplary:
it labels `SCHERRER_K` "Scherrer constant for a **FWHM**", cites Langford &
Wilson, and quotes 0.89 for the FWHM of a sphere against 1.0747 for its
integral breadth. The code therefore pairs the right constant with the right
breadth measure, and no computed size is wrong.

### Sites for the rename

These lists are complete as of 2026-09-17, scanned for the bare token `k`
rather than read off, in the three modules and every test that calls `f0`.
**A binding and its uses move together**: in `structure_factor.py` the
assignment at 335 is consumed at 337, 373 at 381 and 434 at 443, and in
`tests/test_dispersion.py` the local at 109 is consumed at 122 and 124.
Renaming a subset leaves a `NameError` that the suite catches and the rename
pass should not have written.

Equations and prose: `docs/manual/intensities.md` lines 9, 10, 28, 29, 64, 70,
115, 132 (the last two moved down four by 1437's neutron paragraph);
`docs/manual/manual.md:163`; `CLAUDE.md:497`;
`docs/skill/rietx/references/diagnostics.md:36` plus its two committed copies
under `.agents/skills/` and `.claude/skills/`.

Identifiers and docstrings: `crystallography/scattering.py` lines 3, 6, 8, 96,
113, 163, 164, 166, 175, 176, 177 (175 and 177 are `k2`, the squared local);
`crystallography/structure_factor.py` lines 3, 9, 15, 36, 89, 91, 228, 256,
260, 265, 267, 276, 286, 293, 335, 337, 373, 381, 434, 443 — 228 and 286 are
the `_orbit_terms` / `_structure_factors_ab` signatures and 293, 337, 381, 443
their call sites; `crystallography/dispersion.py:5`; `tests/test_dispersion.py`
lines 109, 122, 124, 215, 227, 228.

Three more tests bind a local `k` for sinθ/λ and hand it to `f0`
positionally, so the rename cannot break them and the goal's "`stol` in
python" still reaches them: `tests/test_crystallography.py` lines 126, 127,
151, 153 and 154; `tests/test_neutron_cw.py` lines 146, 147 and the comment at
149. And
`tests/test_species_fallback.py:7` writes the same quantity as `f0(Q=0)`, a
third letter for it in the tree, which becomes `f0(s=0)` in that docstring.

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
- [ ] `qpa.weight_fractions(k, ...)` → `zmv`, body and docstring included
      (`qpa.py:168`, `:171`, `:184`, `:186`, `:197`). Two callers in `src`
      (`qpa.py:388`, `:495`), both already passing `[z.zmv for z in zmvs]`, and
      five in `tests/test_qpa.py` (112, 120, 127, 134, 474), all positional —
      so nothing breaks, but `:474`'s local is itself named `k`.
- [ ] `manual.md:163` becomes **two** rows, because the table is keyed
      `| quantity | unit |` and 1/d² is Å⁻²:

      | a reciprocal length | Å⁻¹: `s = sinθ/λ = 1/2d`, `|d*| = 1/d = 2s`, and `Q = 4π sinθ/λ` |
      | a reciprocal length squared | Å⁻²: `Q = 1/d²`, the indexing chapters' `Q` and the `ObservedPeak.q` field |

- [ ] `intensities.md` equations to `s`; `CLAUDE.md:486`, plus a conventions
      clause recording the maths/identifier split with its reason.
- [ ] `docs/skill/rietx/references/diagnostics.md:36`, then re-sync the two
      committed copies with `rietx skill --install . --copy`.
- [ ] `fom.py:47` and `:583`: say F_N at N = 20, name `PEAK_MIN_USABLE_LINES`
      as the reason for the twenty, and record that Smith & Snyder recommend
      N = 30. Keep the value; change only the attribution.
- [ ] `microstructure.md`: stop calling the FWHM `β`, which is Langford &
      Wilson's integral breadth. Their FWHM symbol is `2w`. The manual's own
      notation table already forbids the integral breadth as a width measure
      (`manual.md:160`), so this row contradicts it. **Three sites, not one**
      (re-grepped 2026-09-17): the Scherrer equation at line 29, the sentence
      binding it at 34, and the ΔQ equation at 50. Line 140's `β*` is
      FullProf's own symbol for its apparent strain and stays.
- [ ] `voigt.py:40`: name the returned HWHM so a caller cannot read it as the
      FWHM its inputs are.
- [ ] Tests: the locals bound at `test_dispersion.py:109` and `:215`, the
      three other test files named under § Sites, and a bit-identity check that a
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
- **`caglioti.apparent_size(..., k=SCHERRER_K)`** at `caglioti.py:136` and
  `:165`. A bare `k`, but it is the Scherrer constant rather than sinθ/λ, and
  `SCHERRER_K` carries the name at every call site that names it. Two sites do
  pass it by keyword — `tests/test_profile_size.py:157` and `:158` — so a later
  session that reopens this decision has those to change as well.
- **`stephens.py`'s missing √(8 ln 2)** against FullProf's `D²_ST`. Checked and
  cleared: `stephens.py:24-27` declares the omission, and `:39-40` warns "Never
  transfer a literature S_HKL without checking numerically". The house
  convention rule working.

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

- Waasmaier, D. & Kirfel, A. (1995). *Acta Cryst.* **A51**, 416-431. Two local
  copies, `~/zotero-linker/derived/86VUZT8W/` and `34WYGAJ4/`, checked
  independently. Both give "s = sin Θ/λ" and neither writes `k` in that role.
- Langford, J. I. & Wilson, A. J. C. (1978). *J. Appl. Cryst.* **11**, 102-113,
  "Scherrer after sixty years". Local copy at
  `~/zotero-linker/derived/9X843RS3/`. Its notation list is the authority for
  `2w` against `β`.
- Smith, G. S. & Snyder, R. L. (1979). *J. Appl. Cryst.* **12**, 60-65. Local
  copy at `~/zotero-linker/derived/J9E3EMAM/`. Equation (1) and
  § *Recommendations for usage of F_N* are the two places to read.
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

### 2026-09-17 (2nd session) — a second reading of the two files, before merge

A fresh session re-resolved every anchor and claim in this file and in 1437
against the tree, as the maintainer asked before merging. The physics and the
numbers held. What a successor now has is a pair of files whose line numbers,
paths and stated reasons can be followed without a detour, and a site list
that reaches the whole tree rather than the four files the audit scanned.
Nothing on the checklist landed and nothing computed moved.

*Done.* Six corrections, one commit. The site list gained three tests outside
the four files that bind a local `k` for sinθ/λ, and the docstring writing it
as `f0(Q=0)`. The shadowing reason now says it holds in `structure_factor.py`
and not in `scattering.py`. One path in 1437 gained its `src/rietx/` prefix.
Four anchors moved by one or two lines. "Five" over a six-row table became
six. The dependency on 1437 now names `intensities.md`, the file both edit,
since no line of `help.py` writes sinθ/λ.

*Measured.* The Lp divergence table reproduces to three decimals by running
both forms; graphite (002) at Cu gives cos²2θ_m = 0.800 and K = 0.556. The
twenty `k` anchors in the three modules and the eight in `intensities.md` are
exact. Lower-case `s` is free in the manual's maths, since the phase scale is
`S_p`. `crystallography/magnetic/` writes `k` today only as a loop index, so
the collision is still scheduled and not present. `test_docs_consistency.py`
22 passed, worktree `.venv`, `[dev]`, darwin/arm64. No test was added, so no
count can move; the full suite did not run, this being documentation.

*Declined.* The diff review was not re-run on the fix commit, at the
maintainer's instruction; the branch's earlier `/code-review high --fix` pass
is recorded in the entry below.

*Gotchas.* One reading worth carrying: GSAS-II's polarisation routine at zero
azimuth is `(1 − Pola)·cos²2θ + Pola`, the package's own form, and it is where
11-BM's 0.99 comes from. That is from memory and unverified this session;
1437 may cite it once checked against `GSASIIpwd.Polarization`.

*Next.* Unchanged from the entry below: land 1437 first, then rebase and work
the task list top down.

### 2026-09-17 — the audit, and what it moved

Opened from a comment on a LinkedIn post about the project, which read our `k`
as the wavevector and proposed `2 sinθ/λ` in its place. The commenter had the
wrong formula and the right instinct. What a reader of this file now knows: the
symbol came from the DABAX file the package parses rather than the paper the
docstring cites, the IUCr's own dictionary writes `s` in a normative method
expression, and the letter is scheduled to collide with the magnetic
propagation vector inside `crystallography/`.

*Done.* **No task on this checklist landed, by design.** The session bought the
audit that makes the checklist executable, and wrote it down. What exists now
is this file, [1437](1437-a-formula-the-code-does-not-compute.md), their two
ROADMAP rows, and the forward reference in the `### Inherited` of all five
magnetic WPs (1326, 1327, 1328, 1329, 1418) — 1326 above all, since it is the
first rung and the one that introduces `Phase.propagation_vector`. No source
file was touched, so every acceptance number below is still unmeasured.

*Measured.* Eight sources surveyed for the sinθ/λ symbol, five in the `s`
family. About 100 physics symbols audited across seven subpackages plus the
manual and `help.py`. Beside sinθ/λ, six further findings are tabled under
§ The rest of the audit, three of them a symbol drifted from the paper its
module cites (`k`, F₂₀, `β`); sixteen letters are ambiguous and almost all
defensibly so. `s` is unavailable as a python
identifier in both target modules, which is why the split is `s` in maths and
`stol` in code. The `help.py` polarisation defect that became 1437 diverges
from the code by up to **2.0×** in Lp, measured by running both forms; a first
pass that read them instead reported half that.

*Settled the same day.* The maintainer supplied the three papers the audit had
fenced out. All three confirm the finding and each narrows the work, because in
every case the code was right and only prose had drifted. A second Waasmaier &
Kirfel copy gives "s = sin Θ/λ" with no `k`. Langford & Wilson's notation list
gives `2w` for the FWHM and `β` for the integral breadth, while
`caglioti.py:88-97` already pairs the FWHM with the FWHM constant, so the scope
is `microstructure.md:34` alone. Smith & Snyder define F_N generally and
recommend N = 30; `f_n` is correct and only its surrounding comment overclaims.

*Gotchas.* Two agent claims did not survive the papers, so check any that
matter. "Smith & Snyder's reporting instance is F30" is wrong: the string F30
is absent from the paper and their worked example is F₂₀. And the
`qpa.weight_fractions` `k` is the per-phase ZMV, never a calibration constant.

The corpus is OCR and two of this session's searches were invalid, both
returning a clean false zero. § *How the papers were searched* above carries
the two rules; read it before re-checking any claim here.

The main checkout was two sessions stale when this WP was numbered, so it was
first written as 1434 and renumbered after `EnterWorktree` showed 1434 and 1435
already on `main`. Re-read the WP directory from the worktree. The branch was
also opened as `wp1434-…` and renamed at handover, because until then it was
telling every other session that WP-1434 was claimed.

*Next.* Land [1437](1437-a-formula-the-code-does-not-compute.md) first, since
both edit `intensities.md` and 1437 fixes a wrong number a user can act on.
Then rebase this branch onto it and work the task list top down. The
first task decides the rest: once `scattering.py` is renamed, tasks 2 to 5 are
mechanical, and tasks 6 to 8 are independent of all of them and could be taken
by anyone in any order.
