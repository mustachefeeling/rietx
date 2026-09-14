# WP-1408 — The theory manual reads like a manual

Milestone: unscheduled · Status: ✅ 2026-09-14 — all eleven reported defects
fixed, each with the guard that closes its class; four new guards, one
measurement script
Depends on: — (0604 built Part 2; 1067 built Part 1)

## Goal

Part 2 reads as a reference a stranger can transfer numbers out of: every symbol
carries the unit rietx stores it in, every displayed equation fits its column
beside its own number, every *Source:* line is a link into the code it was
transcribed from, and the bibliography renders one way instead of ten. The
defects behind each of those are a class, not an instance, so each fix lands
with the guard that keeps the class closed.

## Context

Eleven reader-reported defects, 2026-09-14, all in Part 2 (`docs/manual/*.md`,
twelve chapters, 101 labelled equations, 104 *Source:* lines). Four are
rendering faults that the `-W` build cannot see and that
`test_no_unrendered_math_survives_the_build` was written for the shape of but
does not catch. The rest are editorial, and each generalises past the instance
the reader happened to open.

**Everything below was measured on this tree before the WP was written**, by
building the manual and by driving the built HTML in a real browser
(playwright-core in the scratchpad against the cached chromium, the
`make_screenshots.py` recipe; `gui/CLAUDE.md` § Driving a real browser).

### A. A MyST substitution is not substituted inside a `{math}` directive

Two sites, both live in the shipped HTML:

| file | equation | source text | what MathJax prints |
|---|---|---|---|
| `profiles.md:67` | (3.3) `prof-strain-cap` | `f = {{ STRAIN_CAP_RANGE_FRACTION }}` | `f = STRAINCAPRANGEFRACTION`, as a product of italic letters |
| `profiles.md:125` | (3.4) `prof-size-cap` | `L_{\min} = {{ SIZE_CAP_MIN_SIZE_NM }}\ \text{nm}` | `L_min = SIZECAPMINSIZENM nm` |

`myst_enable_extensions` carries `substitution`, and the substitution is
*defined* in `conf.py`, so `-W` has nothing to warn about: the braces reach the
LaTeX and MathJax typesets the name. This is the exact failure mode
`test_no_unrendered_math_survives_the_build`'s docstring describes for `$` —
"the page builds cleanly and prints the TeX" — one delimiter over.

The fix has to keep 0604's anti-divergence rule (a fenced constant is never
typed into a chapter): the symbol stays in the equation and its **value** moves
to the prose beside it, where substitution works.

### B. The equation number sits on top of the equation

`basic.css` gives `span.eqno { float: right; }` and nothing reserves the space,
so a wide equation runs under its own number. Measured in chromium at viewport
1440 px and 1100 px — the furo content column is **736 px** at both, so the
numbers below are viewport-independent; "ink" is the `mjx-math` box, not the
centred block:

| equation | ink | clearance to the number | overflows the 736 px column by |
|---|---|---|---|
| (3.3) `prof-strain-cap` | 870 px | **−179 px** | 136 px |
| (3.4) `prof-size-cap` | 796 px | **−105 px** | 63 px |
| (4.6) `int-AB` | 686 px | **−18 px** | — |
| (3.6) `prof-tch-gamma` | 662 px | **−6 px** | — |
| (8.2) `est-indices` | 629 px | +11 px | — |
| (3.16) `prof-fcj-integral` | 614 px | +11 px | — |
| (8.3) `est-structure-r` | 589 px | +31 px | — |
| (11.3) `eng-det` | 577 px | +32 px | — |

Everything else on the twelve chapters clears by more than 40 px. The reader
reported 3.3, 3.4, 4.6 as mangled and 3.6 as "dangerously close"; 3.6 is in fact
already 6 px into the number, and the two cap equations spill out of the column
as well as under the number.

Two fixes, and both are wanted. The **layout** one makes collision structurally
impossible whatever an equation's width: `div.math` becomes a two-cell grid —
the typeset math in a cell of its own with `overflow-x: auto`, the number in a
second cell — so the worst case is a scrollbar rather than an overlap, at every
width and for every equation anyone adds later. The **editorial** one reflows
the four equations that do not fit the resulting cell (736 px less a ~45 px
number and a gutter ≈ 675 px), so nothing scrolls in practice.

### C. A variable arrives without the unit rietx stores it in

Thirteen unit annotations exist across the twelve chapters, and they are not
where a reader needs them. Γ is introduced in `profiles.md` § Thompson-Cox-
Hastings as "a single FWHM Γ" with no unit, though the component widths two
sections above carry `[\deg 2\theta]`; `forward-model.md` introduces
$y_\mathrm{calc}$, $I_{pk}$, $w_l$ and $\Omega_{lk}$ with none of the four
saying counts, counts·deg, dimensionless, deg⁻¹.

The generalisation is a stated convention plus per-symbol exceptions, not an
annotation on every letter: root CLAUDE.md already fixes the defaults (degrees
throughout, U/V/W in deg²(2θ), Biso in Å², λ in Å, k = sinθ/λ), and Part 2 has
never written them down for the reader.

### C2. The metric tensor is named and never written

`peak-positions.md` opens on $1/d^2 = \mathbf{h}\cdot G^*\cdot\mathbf{h}^\top$
and says only that $G$ is "the direct metric tensor built from
$(a, b, c, \alpha, \beta, \gamma)$" — the one object the whole chapter rests on,
never written down. **Missed when this file was first written and added the same
day**, from the reader's own list.

### D. ⊕ and ⊗ are used as if they were defined

`profiles.md:4` heads a section "The instrument ⊕ sample width split" and
`profiles.md:157` writes "the Voigt (Gaussian ⊗ Lorentzian)". Neither symbol is
defined anywhere in the manual. ⊗ is convolution; ⊕ is not an operator at all
but the shorthand for the combination rule the section then states (Gaussian
variances add, Lorentzian FWHMs add). Three more uses in Part 1
(`using/data.md` ×2, `using/indexing.md`) inherit the same silence.

### E. The TCH coefficients look arbitrary, and TCHZ is never expanded

(3.6) and (3.7) carry 2.69269, 2.42843, 4.47163, 0.07842 and 1.36603, −0.47719,
0.11116 with no statement of where they come from. They are a **numerical fit**,
not a derivation: TCH 1987 fitted the Voigt FWHM and the pseudo-Voigt mixing as
polynomials in Γ_L/Γ. A reader cannot tell that from the page, and the
distinction matters — it is why the pseudo-Voigt is an approximation with a
quotable error rather than an identity.

rietx can *measure* that error rather than quote it: `model/profiles/voigt.py`
is the exact convolution via Faddeeva, so the pseudo-Voigt of (3.5) can be
compared with the Voigt of (3.11) across the whole Γ_L/Γ range on this tree.
Measuring it is better evidence than a transcribed accuracy claim, and it is the
rule the repo already applies to everything else.

`TCHZ` appears as `Instrument.profile.shape`'s owning class (`ProfileTCHZ`) and
in `profiles.md:257` with no expansion. What is certain and citable: it is the
Thompson-Cox-Hastings pseudo-Voigt carrying a fourth Gaussian term in 1/cos²θ
beyond Caglioti's three — the term this manual writes $P$ in (3.1). What the
letter Z itself denotes needs a source before it goes on the page: GSAS-II's own
`Z` is a constant *Lorentzian* term, which is not this. **Verify against a
citable source (FullProf manual, GSAS-II documentation, or Denney et al. 2022,
which is in the local corpus) or write only what is certain; ask the maintainer
for TCH 1987 if the attribution cannot be pinned** (memory: ask for papers).

### F. A *Source:* line names a symbol and does not go there

104 lines of the form ``*Source:* `rietx.model.profiles.voigt` ``. The name
resolves — `test_every_source_symbol_imports` proves it — but the reader has to
go and find the file. Every one of them can be a link, resolved at build time by
`inspect`, so a rename is a build failure rather than a dead link.

`pyproject.toml` has the repository URL in `[project.urls]` and `_about.py` has
`DOCS_URL` beside where a `REPO_URL` belongs (root CLAUDE.md § Conventions: the
brand tokens are imported, never spelled). `_about` is private, so a new
constant there does not touch the API-surface partition.

### G. The bibliography renders ten ways

103 entries; 87 `@article`, 9 `@book`, 3 `@techreport`, 2 `@incollection`, 1
`@misc`, 1 `@software`. The field sets are nearly uniform already, so what the
reader sees as inconsistency is mostly **one mechanical fault**: pybtex's `alpha`
style sentence-cases a title, so any capitalised word that is not braced is
lowercased. Ten entries render with a lowercased proper noun today:

- eight read "x-ray" (brindley1945, hubbell1995, holzer1997, lebail1988,
  mcmaster1969, pitschke1993, suortti1972, thompson1987);
- srd128 renders "X-ray transition energies database, standard reference
  database 128";
- **rietx2026 renders "Rietx: python-api-first analysis and rietveld refinement
  of powder diffraction data"** — the package's own citation entry, with the
  brand capitalised and "Rietveld" not.

The rest of the unevenness is real but smaller: 23 of 87 articles carry a `doi`
and 64 do not, so some entries end in a link and most do not; 3 carry a `number`
and 84 do not.

`@software` is not a BibTeX type pybtex knows; it renders (as `@misc` would) but
nothing guarantees that.

### H. Rwp is set in prose where the chapter next to it sets it in maths

`estimation.md` defines $R_{wp}$ in (8.2) and then writes "ΔRwp" as plain text
eleven lines later. Eleven plain-text uses across five Part 2 chapters, 109
across Part 1. The rule that settles it in both parts: **the statistic is
$R_{wp}$; the field is `rwp` in code font**, and a mermaid node label — which
cannot typeset maths — stays plain.

### I. Lorentz-polarisation: keep the hyphen

Answered rather than changed. The compound joins two coordinate factors (a
Lorentz factor times a polarisation factor), and the literature hyphenates it:
in the local corpus, 13 hyphenated spellings against 2 unhyphenated (plus 5
`Lorentzpolarization`, PDF line-break artefacts). ITC C §6.2 and McCusker 1999,
both already cited here, hyphenate. **No change; record the check so the question
is not reopened.** The one thing to fix is consistency of the *ending*: the
manual is British-spelled, so `polarisation` throughout, with
`lorentz_polarization` left alone as a code name.

### G/B/A share one guard gap

`test_manual.py` guards names, constants, citations and stray `$`. It does not
guard what a page *looks* like. Two new guards are cheap and cover A, G and H
entirely; B's guard is a measurement script, not a test, for the same reason
`make_screenshots.py` is one — playwright is deliberately not a dependency.

## Non-goals

- No new physics and no new equation content. A wrong explanation is out of
  scope unless it is one of the eleven; report it, do not rewrite the chapter.
- Not a restructure of Part 2, and no chapter merges or splits.
- Part 1 is touched only where a defect is the same defect (H's `Rwp`, D's ⊕),
  never for its own polish.
- No `linkcheck` builder and no external-link CI. The source links are checked
  by resolving the symbol at build time, which is where a rename breaks.
- Not the manual's own prose register (that is `yue-docs-style`'s, and settled).

## Tasks

- [x] **A — a substitution never reaches MathJax.** Move `STRAIN_CAP_RANGE_FRACTION`
  and `SIZE_CAP_MIN_SIZE_NM` out of (3.3)/(3.4) into the prose beside them; keep
  the symbols $f$ and $L_\mathrm{min}$ in the equations. Guard:
  `test_manual.py` gains a built-HTML scan for a surviving `{{`/`}}` in rendered
  prose, sharing `MARKUP_WITHOUT_PROSE` and the landing-page exclusion with the
  `$` guard.
- [x] **B1 — the layout makes the collision impossible.** `_static/custom.css`
  lays `div.math` out as a two-cell grid, math cell `overflow-x: auto`, number
  cell its own column; checked in both themes and at 1440/1100/400 px.
- [x] **B2 — the four wide equations are reflowed** (`prof-strain-cap`,
  `prof-size-cap`, `int-AB`, `prof-tch-gamma`) so their ink fits the cell with
  clearance, using `aligned`/`split` rather than shrinking the content.
  `docs/manual/check_equations.py` lands with them: playwright, not a
  dependency, `make_screenshots.py`'s conventions, printing ink/cell/clearance
  per labelled equation so the table above is reproducible.
- [x] **C2 — the metric tensor written out** as a 3×3 matrix in
  `peak-positions.md`, dot-product form beside closed form, in Å², with its
  source line.
- [x] **C — units.** A short "Symbols and units" section in `manual.md`'s Part 2
  preamble stating the defaults (deg 2θ; widths as FWHM in deg 2θ; Å; Å⁻¹;
  counts; counts·deg; cm⁻¹), then a sweep of the twelve chapters annotating every
  symbol whose unit the defaults do not settle — Γ, y, I, w, Ω first.
- [x] **D — ⊕ and ⊗ defined where they are first used** (`profiles.md` § the
  split), Part 1's three uses pointed at `{ref}`ch-profiles``.
- [x] **E1 — where the TCH coefficients come from**: a paragraph saying they are
  a fit and not a derivation, with the approximation error **measured on this
  tree** against `profiles.voigt` across Γ_L/Γ ∈ [0, 1], reported in the WP and
  quoted on the page.
- [x] **E2 — TCHZ expanded** where the shape is named, to whatever a citable
  source supports (see § E); the convention note that rietx writes that
  coefficient $P$.
- [x] **F — `*Source:*` becomes a link.** `REPO_URL` in `_about.py`; a `{source}`
  role registered in `conf.py` resolving the dotted name through `inspect` to a
  blob URL with a line anchor; all 105 lines converted; `test_manual.py`'s
  `SOURCE_LINE` regex and its two consumers follow. **Landed against `main`, not
  a tag**: `pyproject.version` is the last *shipped* milestone whether or not it
  was tagged, and it reads 1.4.0 today while `git ls-remote --tags` stops at
  v1.3.0, so a tag-pinned link would 404 on every equation. `main` is also the
  tree the published manual is built from.
- [x] **G — the bibliography agrees with itself.** Brace every capital in every
  title (the ten rendered faults first, then the sweep); settle `@software`;
  add the `doi` field wherever Crossref confirms one against title, year, volume
  and first page (never a bare title match), and record the count that could not
  be confirmed. **`@software` stays**: changed to `@misc` for portability and
  changed straight back, because `tests/test_no_stale_name.py` finds this
  package's own citation record by that entry type and went red. Guards: `test_manual.py` fails on an unbraced interior capital in
  a title, on an article with no `doi` outside a named exception, and on a `doi`
  that is not lower case. **Not** a field-set check per type: the field sets were
  already uniform, and the defect was the style lowercasing a capital.
- [x] **H — `Rwp` in maths, in Part 2.** $R_{wp}$ and $\Delta R_{wp}$ in the
  eleven Part 2 lines; `rwp` in code font is the field everywhere. **Part 1 keeps
  the plain word, deliberately**: it is the label on the GUI header and in a
  console line, and its neighbours in the same tables are plain too (χ², GoF,
  Σw δ², N − P), so converting 126 lines would trade one inconsistency for
  another. `manual.md` states the split. Guard: a source-side check over Part 2,
  its page list derived from the tree, exempting code spans and fences.
- [x] **I — the hyphen check recorded** in the handover entry with its counts;
  `polarisation` spelling made uniform in prose.
- [x] Tests: the four new guards above, plus the existing manual suite green.
  No obs/calc/diff PNGs — this WP runs no refinement (the plotting rule is about
  fits, and E1's measurement is a profile-function comparison, whose plot belongs
  in the handover entry).
- [x] Skill: **none.** Nothing here changes what an agent driving rietx should
  do; the skill cites the manual by section and no section is renamed or moved.
  Confirmed at close: the skill links the manual only as
  `https://rietx.org/manual.html`, and `help.py`'s 30 deep links name no anchor
  in a heading this WP touched (the one changed heading, `method.md`'s, is
  referenced by nothing).

## Acceptance

1. The manual builds `-W`-clean and the manual suite is green:

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_gui_manual.py tests/test_help.py -p no:randomly
.venv/bin/python -m ruff check src tests examples
```

2. `check_equations.py` reports **no** labelled equation whose typeset ink
   exceeds its cell, on all twelve Part 2 chapters, at 1440 px and 1100 px; the
   minimum clearance is recorded in the handover entry against today's −179 px.

3. No `{{` survives into rendered prose, and no bare `Rwp` survives outside code
   spans, fences and mermaid labels, both asserted by tests rather than by
   reading.

4. The rendered bibliography carries no lowercased proper noun: the ten entries
   in § G read correctly, `rietx2026` included, checked in the built HTML.

5. Every one of the 104 *Source:* lines resolves to a URL at build time, and a
   deliberately misspelled symbol fails the build (verified once, then reverted).

## References

- Thompson, P., Cox, D. E. & Hastings, J. B. (1987) *J. Appl. Cryst.* **20**,
  79–83 — eqs 4 and 5 are (3.6) and (3.7). Not in the local corpus as of
  2026-09-14; § E says what to do about that.
- Denney, J. J. et al. (2022) — physically based pseudo-Voigt terms from the FPA;
  in the local corpus, a candidate source for the TCHZ naming convention.
- Caglioti, G., Paoletti, A. & Ricci, F. P. (1958) — the three-term Gaussian law
  the fourth term extends.
- International Tables C §6.2 and McCusker et al. (1999) — both cited already,
  both hyphenate Lorentz-polarisation (§ I).
- Crossref REST API (`api.crossref.org`), reachable from this machine, verified
  2026-09-14 — the DOI source for § G.
- `docs/manual/make_screenshots.py` — the precedent § B2's script follows:
  playwright is not a dependency, the script is the one authority for how a
  measurement was taken.

## Handover log

### 2026-09-14 (2nd session) — the manual's own defects, each closed with its guard

Part 2 now reads as a reference somebody can transfer numbers out of. Every
symbol arrives with the unit rietx stores it in, no equation is typeset on top
of its own number, the metric tensor the positions chapter rests on is written
out, ⊕ and ⊗ mean something stated rather than assumed, the TCH coefficients
say plainly that they are a fit and how good a one, every *Source:* line is a
click into the code it was transcribed from, and the bibliography stopped
rendering this package's own citation as "Rietx: python-api-first analysis and
rietveld refinement". The part that outlives the eleven fixes is that four of
them were **invisible to `-W` by construction** — a defined substitution that
is simply never reached, a CSS collision, a style that lowercases a capital, a
plain word four lines under the equation that defines it — so each landed with
a guard, and each guard was failed on purpose before it was trusted. The cost
was one working day and no package behaviour: nothing outside `docs/` changed
but a private `REPO_URL` constant.

*Done*, one commit each: the two substitutions moved out of (3.3)/(3.4) into
the prose beside them; a two-cell grid in `custom.css` that makes an equation
and its number structurally unable to collide, plus four reflows;
`docs/manual/check_equations.py`, which measures it; a "Symbols and units"
table in `manual.md` and a per-chapter sweep; ⊕/⊗ defined at first use; the
metric tensor as a 3×3 matrix, dot products beside closed form; a `{source}`
role resolving 105 dotted names to GitHub links at build time; 63 DOIs and a
brace sweep over `references.bib`; eleven Part 2 `Rwp` set as $R_{wp}$.

*Measured*, darwin/arm64, `[dev]` plus a `playwright` this session installed
into the worktree venv for the script (it adds no tests):

- **Equation width**, chromium at 1440 px and 1100 px, furo's content column
  736 px at both. Before: (3.3) ran 179 px into "(3.3)" and 136 px outside the
  column, (3.4) 105 px and 63 px, (4.6) 18 px, (3.6) — reported only as
  "dangerously close" — already 6 px in. After: 102 numbered equations, minimum
  clearance **44 px**, nothing overflowing its cell.
- **The TCH approximation**, against this package's own Faddeeva Voigt with the
  true FWHM found by bisection: the quintic reproduces the Voigt FWHM to
  **0.43 %** worst case (Olivero & Longbothum's two-term formula, run as a
  control, lands at 0.023 % — its own published bound, which is how the
  bisection was checked); the pseudo-Voigt departs from the exact shape by at
  most **1.27 %** of the peak height at q ≈ 0.56, **on the flanks** at
  x ≈ ±0.28 Γ, while the centre stays under **0.25 %** across the range.
- **The bibliography**: 103 entries, 10 rendering a lowercased proper noun
  before, 0 after; 86 now carry a DOI against 23 before — 50 accepted by
  Crossref only on title, year, volume *and* first page together, 13 confirmed
  one at a time, 1 (`scherrer1918`) declared as having none.
- **Suite**: fast selection **4639 passed / 132 skipped** in 2:09–2:11, +7
  tests over the merge base (5 in `test_manual.py`, 2 in `test_voigt.py`), all
  passes, no new skip. An eighth guard landed at handover (the old `*Source:*`
  spelling), so the final tree is +8. The full selection did **not** run: this
  WP changes `docs/`, `tests/` and one private constant, so it can move no
  measured number (`tests/CLAUDE.md` § Running, rung 3).

*Gotchas*, each one that cost time:

- **A MyST substitution is not expanded inside a `{math}` directive.** It is
  *defined*, so `-W` has nothing to say, and MathJax typesets the name as a
  product of italic letters. Put the symbol in the equation and its value in
  the prose beside it; `test_no_unsubstituted_substitution_survives_the_build`
  is now the loud version.
- **Furo pins the equation number with `position: absolute`**, over the content
  column. That is why it can sit on top of the equation, and why the number has
  to be made `static` before a grid can give it a column of its own. A float or
  a padding reserve cannot work: an equation's width is not known until MathJax
  has typeset it in the browser.
- **`pyproject.version` is the last *shipped* milestone, tagged or not.** It
  reads 1.4.0 while `git ls-remote --tags origin` stops at v1.3.0 and PyPI's
  latest is 1.3.0 — so **v1.4.0 was written, merged and released in the record
  but never tagged or published**. Found while deciding what a source link
  should point at; the links go to `main`, which is also the tree the published
  manual is built from. This is the maintainer's to act on, not this WP's.
- **`@software` in `references.bib` is load-bearing.** It was changed to
  `@misc` for portability and changed straight back:
  `tests/test_no_stale_name.py` finds this package's own citation record *by
  that entry type*. The file now says so above the entry.
- The bibliography's remaining unevenness is **the literature's**:
  `holzer1997` reads "x-ray" because Physical Review A prints it that way. The
  brace rule is about capitals the *style* destroys, never about spelling, and
  the file states the difference so nobody "fixes" it.

*Decided rather than changed*: **Lorentz-polarisation keeps its hyphen.** The
compound joins two coordinate factors, and the local corpus has 13 hyphenated
spellings against 2 unhyphenated; ITC C §6.2 and McCusker 1999, both cited
here already, hyphenate. The British ending was already uniform — all eight
`polarization` spellings in the manual are code names. And **Part 1 keeps
`Rwp` as plain text**: it is the word on the GUI header and in a console line,
and its neighbours in the same tables are plain too (χ², GoF, Σw δ²), so
converting 126 lines would have traded one inconsistency for another.
`manual.md` states the split between the parts.

*Not done, and why*: **no CLAUDE.md line.** The three things a stranger adding
a Part 2 equation must know are all mechanised instead — the substitution trap,
the width check and the `{source}` spelling each have a test or a script — and
a guard beats a rule at the same cost in nobody's attention. **No skill row**
either: the TCH accuracy numbers bear on one opt-in shape and hold for no other
fit, so neither the body nor a task-shape reference is their home (root
CLAUDE.md § skill). **No milestone-record entry**: rule 6 stages a break or a
user-facing addition, and this is documentation with no API, schema or
behaviour change; staging it under shipped v1.4 would misattribute it to
notes already written.

*Next*, in order: (1) the maintainer's call on the **missing v1.4.0 tag and
PyPI release** — `docs/RELEASING.md` is the authority and the workflow builds
from the tag, so nothing here can fix it; (2) if TCH 1987 can be supplied, the
"where those coefficients come from" section can name what the trailing **Z**
of `ProfileTCHZ` denotes, which no source to hand pins down — the page
currently says only what is verifiable, that TCH is the three authors and that
different codes attach Z to different extra width terms; (3) nothing else —
the WP is closed.

- **2026-09-14** — created. Eleven reader-reported defects in Part 2, each
  measured on this tree before the file was written: the two substitutions that
  reach MathJax as italic letters, the four equations that run under their own
  number (worst −179 px into it, and 136 px outside a 736 px column), the ten
  bibliography entries whose proper nouns are lowercased by the style, and the
  eleven plain-text `Rwp` in a part that sets it in maths four lines away. Each
  task carries the guard that closes its class, because four of the eleven are
  invisible to `-W` by construction. One question is answered rather than
  scheduled: the Lorentz-polarisation hyphen stays, 13 hyphenated spellings
  against 2 in the local corpus. Next: work the tasks in order; § E2's
  attribution is the one item that may need the maintainer.
