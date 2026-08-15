# Literature — the local corpus, and what backs what

## There is a local paper corpus. Search it before asking for a paper.

`/Users/yue/zotero-linker/` holds converted full text for **~152 papers**:

```
derived/<ITEM_KEY>/<Author> - <Year> - <Title>.md
index.sqlite      # table `documents`, columns: title, md_path, item_key, status
```

Query it directly:

```sh
sqlite3 /Users/yue/zotero-linker/index.sqlite \
  "select title, md_path from documents where title like '%indexing%';"
sqlite3 /Users/yue/zotero-linker/index.sqlite \
  "select title from documents where title like '%profile%' or title like '%absorption%';"
```

**Why this file exists.** On 2026-08-04 a session reviewing the indexing scope
asked the user for seven papers by name. **All seven were already in the corpus.**
Worse, so was **Smith (1977)** — the source of this package's own
`SMITH_VOLUME_C1`/`SMITH_VOLUME_C2` constants *and* of a recorded open defect
("`volume_envelope` is a mean line, not an envelope") that had been carried
unresolved because nobody read the paper the constants came from.

Two rules follow, and they are in `CLAUDE.md`:

1. **Search the corpus before requesting a paper.** Asking costs a round trip; the
   query costs nothing.
2. **Search it before re-deriving a constant or arguing from first principles about
   a published method.** A constant whose paper is on disk should be read from the
   paper.

The corpus is the user's Zotero library, so it grows and is not under this repo's
control. Treat a miss as "not currently held", not "does not exist" — and say which
you mean.

## Indexing — the map established 2026-08-04

Held locally, all read except where marked:

| Paper | Item key | What it backs here |
|---|---|---|
| Louër & Louër (1972); **Boultif & Louër (1991)** *J. Appl. Cryst.* **24**, 987 | `E7ZLXSIB` | `indexing/dichotomy.py` — the monoclinic/triclinic successive-dichotomy algorithm this engine implements. **Unread** |
| **Boultif & Louër (2004)** *J. Appl. Cryst.* **37**, 724 — DICVOL04 | `I2VA3ZAB` | §3.1(ii) the reflection-pair zero-shift option (WP-1038); §4.1 per-system exploration and volume tightening (WP-1042); §3.4 impurity tolerance |
| **Coelho (2003)** *J. Appl. Cryst.* **36**, 86 — SVD-Index | `5RI7CB42` | TOPAS's indexing algorithm; the whole of WP-1040. Also its `N_c/N_o` prune and intensity weighting |
| **Le Bail (2004)** *Powder Diffr.* **19**, 249 — McMaille | `7AEVVGH6` | §III why Monte Carlo needs local refinement (WP-1040); §VI–VII solve the zeropoint before indexing (WP-1038); §IV the 2004 progress/cancel UX (WP-1037) |
| **Werner, Eriksson & Westdahl (1985)** *J. Appl. Cryst.* **18**, 367 — TREOR | `PN4KSN9S` | `indexing/trial_error.py` — base-line trial and error |
| **Visser (1969)** *J. Appl. Cryst.* **2**, 89 — ITO | `GABUYM7L` | zone finding; the dominant-zone problem. **Unread** |
| **Oishi-Tomiyasu (2013)** *J. Appl. Cryst.* **46**, 1277 | `3DEVVH8A` | `m_rev` / `m_sym` in `indexing/fom.py` (adopted WP-1030) |
| **Oishi-Tomiyasu (2014)** *J. Appl. Cryst.* **47**, 593 | `NWFJ8YEB` | §2–3 the search-line count and the missing/false-peak asymmetry (WP-1039); Table 3 the Mighell & Santoro isospectral families |
| **Oishi-Tomiyasu (2012)** *Acta Cryst.* **A68**, 525 | `5U9DD3DL` | error-stable Bravais determination — bears on `reduce.bravais_screen` and the `bravais_ambiguous` caveat. **Skimmed** |
| **Bergmann, Le Bail, Shirley & Zlokazov (2004)** *Z. Kristallogr.* **219**, 783 | `CSGZVXR2` | the bethanechol benchmark — the only externally *graded* feature in the package |
| **Dong, Wu & Chen (1999)** *J. Appl. Cryst.* **32**, 850 | `RPSYEN7Y` | the reflection-pair zero-shift method (WP-1038). **Its eq. (6) is wrong as printed** — see that WP |
| **Dong (1999)** *J. Appl. Cryst.* **32**, 838 — PowderX | `4ZBNLND9` | the program implementing the pair search |
| **Smith (1977)** *J. Appl. Cryst.* — unit-cell volume from one line, triclinic | `QA2EIDAW` | `SMITH_VOLUME_C1`/`C2` and `quality.volume_envelope`. **Unread — and there is an open defect against those constants** |
| **Grosse-Kunstleve, Sauter & Adams (2004)** — reduced unit cells | `2FSRWWUB` | `indexing/reduce.py`, `NIGGLI_EPS_RELATIVE`. **Unread** |
| **Altomare et al. (2007)** — Indexing a powder diffraction pattern | `ZZ9TPCSA` | field review. **Unread** |

## Papers held outside the corpus

**Altomare, Cascarano, Giacovazzo, Guagliardi, Moliterni, Burla & Polidori
(1995)**, *J. Appl. Cryst.* **28**, 738-744 — "On the number of statistically
independent observations in a powder diffraction pattern". The M_ind estimator
McCusker §9 names, implemented in `optimize.statistics.effective_observations`
(WP-1071). **Searched for and absent from the zotero corpus** — title, author
path and full-text grep all miss it, and the only Altomare there is the 2007
indexing review. Supplied 2026-08-15 as mineru-OCR markdown:

```
/Users/yue/Code/mineru-app/data/output/332d1f87b5fc/Altomare et al. - 1995 - On the Number of Statistically Independent Observations in a Powder Dif/auto/Altomare et al. - 1995 - On the Number of Statistically Independent Observations in a Powder Dif.md
```

What is load-bearing in it, so a re-read can go straight there: **§2** is the
algorithm — the ±α·FWHM interval, the overlap test, and the I′_k/I_k
contribution — and **§4** carries the α = 2 → α = 4 check (6.5 % average,
13.3 % maximum) that is the estimator's own stated precision, which any
re-shaping of it has to be measured against. The tables in §3 give M_ind/M
between 0.22 and 0.50 across twenty real structures: the only external check
on an implementation without their data. OCR is clean on both; the Table 1/2
cell contents are garbled and are not needed.

## Books — held outside the corpus

**Prince, *Mathematical Techniques in Crystallography and Materials Science*
(3rd ed.)** — the whole book as one mineru-OCR markdown (~550 kB, ~6,090
lines):

```
/Users/yue/Code/mineru-app/data/output/b4c93a6aef1f/Mathematical Techniques in Crystallography and Materials/auto/Mathematical Techniques in Crystallography and Materials.md
```

How to interrogate it: `grep -n '^#'` gives a faithful chapter/section map to
line numbers — read sections by line range, never the whole file. The printed
back-of-book index also survived OCR (near the end of the file), so "does the
book treat X, and in which chapter" is one grep even when no section title
names it. **OCR caveat**: equations are OCR'd LaTeX and signs/exponents do get
mangled (the F-density's exponents are garbled; the worked projection-matrix
table drops two minus signs) — re-derive before porting any formula, per the
standing verify-equations rule.

Read 2026-08-12 (chapters 6–8), backing WP-1056:

| Section | What it backs |
|---|---|
| Ch. 7 Estimation of Uncertainty | w = 1/σ² derived as the minimum-variance linear estimator (the canonical cite for "all weighting is 1/σ²"); V = s²·H⁻¹, with Prince's own caution that the χ²-scaling argument is "sometimes questionable" (beside Schwarzenbach rec. 8) |
| Ch. 8 Correlation | ρ from the inverse Hessian; the *illusory precision* sentence (computed variance too small when correlated variables are missing from the Hessian) — the WP-1056 E2 mechanism verbatim; soft modes as "linear combinations … approximately eigenvectors of the Hessian", remedies worthwhile at \|ρ\| > 0.95 |
| Ch. 8 The F Distribution | the constrained-vs-unconstrained F ratio — the classical form of the exchangeability discriminator's significance half; F ≈ 1 read as "the data do not contain sufficient information to distinguish between the two models" |
| Ch. 8 The Projection Matrix | leverage P′ᵢᵢ, idempotency, and the per-point variance-reduction formula — the formal basis under `background_absorption`'s projection mechanic and the held-column scan |
| Ch. 6 Finding the Minimum / False Minima | Gauss–Newton/quasi-Newton context; the restrained-vs-constrained vocabulary. **No Marquardt or eigenvalue-filtering treatment in this edition** — that point stays cited to Watkin (2008) §3.8 |

Flagged, unread — come back when the feature does:

- Ch. 5 Moments and Cumulants + Ch. 9 Representing non-Gaussian Distributions —
  Gram–Charlier anharmonic ADPs (v2 fence).
- Ch. 5 Rigid Body Motion + Ch. 9 Rigid Body Thermal Motion Constraints — TLS,
  including the trace-of-S singularity and the conic-section ill-conditioning
  warnings (v2).
- Ch. 9 Shape / Chemical Constraints — if rigid-body or occupancy-sum
  constraints ever land.
- Ch. 8's repeat-measurement table (t²ᵢⱼ/(1+P′ᵢᵢ)) — a "where to spend counting
  time" advisory; design-of-experiment, pairs naturally with the report's
  regions.
- Ch. 7's subset-scaling test (σ̂²ₖ over data subsets separates
  weights-underestimated from model-deficient) — a cheap FitReport-adjacent
  statistic.
- Appendix F, Symmetry Restrictions on Second/Third/Fourth Rank Tensors — an
  independent check on `wyckoff.adp_basis` / `stephens.py` subspaces.
- Ch. 10 (FFT) and Appendix E — no consumer here (no Fourier synthesis; v2).

## Everywhere else

The package's standing rule is that **every physics function cites its reference
(author, year, journal) in its own docstring**, and the theory manual
(`docs/manual/`) requires a `*Source:*` line on every displayed equation whose
symbol must import. That is the authority for what backs a given function — this
file does not duplicate it, and must not become a second one.

What this file is for is the two things a docstring cannot say: **where the papers
physically are**, and **which ones we have not read yet**.

## Licensing fences (restated from CLAUDE.md, because it bites here)

- **BGMN / Profex / xrayutilities** are GPL — concepts only, never code.
- **TOPAS / FullProf** are closed — papers only.
- **McMaille and Conograph** are open source under GPL-family licences — same rule
  as the first group: read the papers, port nothing.

A published algorithm paper is always readable and implementable. A repository is
not, regardless of how the paper is licensed.
