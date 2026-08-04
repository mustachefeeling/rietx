"""A systematic 2θ shift measured from the peak list alone — no cell, no indices.

Two reflections form a **reflection pair** when their planes are harmonics of one
another, ``(h'k'l') = m·(hkl)`` with m an integer, so that ``d_hkl = m·d_h'k'l'``
*exactly*.  Bragg's law then gives

    m·sin θ_B = sin θ'_B

with no knowledge of the cell, the crystal system or the indices — the relation is
a property of the lattice's self-consistency, not of any particular lattice.  A
systematic shift ``2θ_B = 2θ_obs − c·T(2θ_obs)`` therefore has a solution *per
pair*, and for the constant template Dong, Wu & Chen (1999) solve it in closed
form.

This module is what lets :func:`~pxrdref.indexing.quality.assess_peak_list` stop
assuming a shift it never measured.  Read ``quality.py``'s module docstring for
the half of the story that stands: everything *else* about a shift — which
physical cause it has — still needs more than the list.

**The estimator here is not the paper's.**  Dong admits a pair when its implied
shift lands in a window and averages the survivors, and Boultif & Louër (2004)
§3.1(ii) add the false-pair rule: partition by sign, take the more populous
category, admit as soon as the difference is ≥ 2.  Measured over this package's
whole indexing corpus (WP-1038 task 0), that rule fails in both directions at
once.  It admits the 11-BM NAC list on a margin of 84 out of 1838 pairs — chance
at that count — and reports −0.09° for a pattern whose shift is zero, while
admitting SRM 660c, whose answer is right, on a binomial z of 1.15.  The rule was
written for the ~10 pairs a 12-line 00l list offers; a fixed margin of 2 is not a
test at 1838.

What replaces it is **concentration against a seeded null**.  Real harmonic pairs
agree on c; accidental ones scatter.  The statistic is the largest number of pairs
inside any window of half-width :data:`PAIR_CLUSTER_HALF_WIDTH_DEG` on c, and the
null redraws the same number of lines uniformly in sin²θ over the same range —
uniform in sin²θ rather than in 2θ because a lattice is linear in Q, and a
2θ-uniform null would understate accidental coincidences where they actually live.
Measured: every fitted list in the corpus scores z ≥ 4.2 while all ten bethanechol
position lists and the unidentified HL2 list score z ≈ 0, and z ≥ 3.5 fires on 1
of 3600 null replicates.

**What this module may and may not conclude.**  It reports an *amplitude*, and it
may refute ``sin_2theta``; it may **not** choose between ``constant`` and
``cos_theta``.  Measured per-template concentration puts those two within one pair
of each other on every dataset in the corpus (corundum k = 10 vs 10, cluster σ
0.0044 vs 0.0043°) while differing ~5 % in value — which is
:func:`~pxrdref.indexing.quality.template_collinearity`'s 0.96 arriving by a second
road.  For a search *window* that costs nothing, since 5 % of the amplitude is far
inside the window either choice opens; for naming a cause it is decisive, and the
caveat stays.

References
----------
Dong, C., Wu, F. & Chen, H. (1999). *J. Appl. Cryst.* **32**, 850-853 — the
    reflection-pair equation for the zero shift, eq. (5) here as
    :func:`pair_shift`.
Boultif, A. & Louër, D. (2004). *J. Appl. Cryst.* **37**, 724-731 — §3.1(ii)
    adopts it as DICVOL04's *a priori* option and supplies the sign-category rule
    this module measured and replaced.
Le Bail, A. (2004). *Powder Diffr.* **19**, 249-254 — §VII: "The zeropoint problem
    is really something to be solved before indexing."
Popović, S. (1971). *J. Appl. Cryst.* **4**, 240-241 — the reflection-pair idea,
    for cubic cell refinement *after* indexing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..schemas.indexing import (
    PAIR_CLUSTER_HALF_WIDTH_DEG,
    PAIR_MAX_M,
    PAIR_MAX_P,
    PAIR_MIN_CLUSTERED,
    PAIR_MIN_Z,
    PAIR_NULL_REPLICATES,
    PAIR_REFUTE_K_FRACTION,
    PAIR_WINDOW_DEG,
    SHIFT_ALLOWANCE_K_ESD,
    SHIFT_TEMPLATES,
)


def shift_template(name: str, two_theta_deg: np.ndarray) -> np.ndarray:
    """One of :data:`~pxrdref.schemas.indexing.SHIFT_TEMPLATES`, at these angles.

    Same three curves :func:`~pxrdref.indexing.quality.shift_template_basis`
    serves, evaluated here from the name alone because the pair relation needs a
    template at *two* angles that are not both in any one caller's array.  The
    physics behind each name is in ``report/layer2.py``'s ``_POSITION_ACTIONS``:
    ``constant`` is a zero-point error, ``cos_theta`` a specimen displacement,
    ``sin_2theta`` specimen transparency.
    """
    th = np.radians(np.asarray(two_theta_deg, dtype=np.float64) / 2.0)
    if name == "constant":
        return np.ones_like(th)
    if name == "cos_theta":
        return np.cos(th)
    if name == "sin_2theta":
        return np.sin(2.0 * th)
    raise ValueError(f"unknown shift template {name!r}; "
                     f"expected one of {SHIFT_TEMPLATES}")


def pair_shift(two_theta_lo: np.ndarray, two_theta_hi: np.ndarray,
               m: np.ndarray) -> np.ndarray:
    """Dong (1999) eq. (5) — the constant shift a harmonic pair implies, in degrees.

    Substituting ``2θ_B = 2θ_obs + 2θ_z`` into ``m·sin θ_B = sin θ'_B`` and solving:

        2θ_z = 2·arctan[ (sin θ' − m·sin θ) / (m·cos θ − cos θ') ]

    Returned in **this package's deviation convention** — ``c`` such that
    ``2θ_B = 2θ_obs − c·T``, i.e. observed − reference, which is what
    :func:`~pxrdref.indexing.quality.fit_shift_model` fits and what
    ``ShiftScreen.templates[].coefficient`` means.  So ``c = −2θ_z`` of the paper.

    **The paper's printed rows carry sign typos and its averages do not.**
    Reproducing Table 2 gives a mean of −0.0334° against the paper's stated
    −0.0334°, and Table 3 −0.1818° against −0.182°, while 4 of 12 and 1 of 11
    individual rows print the opposite sign; averaging the printed signs would give
    −0.0106°.  Do not "fix" this function to match a printed row
    (``tests/test_indexing_pairs.py`` pins both tables).

    *Source:* Dong, Wu & Chen (1999), *J. Appl. Cryst.* **32**, 850, eq. (5).
    """
    th = np.radians(np.asarray(two_theta_lo, dtype=np.float64) / 2.0)
    thp = np.radians(np.asarray(two_theta_hi, dtype=np.float64) / 2.0)
    m = np.asarray(m, dtype=np.float64)
    den = m * np.cos(th) - np.cos(thp)
    with np.errstate(divide="ignore", invalid="ignore"):
        c = -2.0 * np.degrees(np.arctan((np.sin(thp) - m * np.sin(th)) / den))
    return np.where(np.abs(den) < 1e-12, np.nan, c)


def pair_shift_template(two_theta_lo: np.ndarray, two_theta_hi: np.ndarray,
                        m: np.ndarray, name: str, *, iters: int = 24
                        ) -> np.ndarray:
    """The same relation for *any* shift template, solved by Newton.

    The pair relation is exact for any shift model, because it constrains the
    *corrected* angles and says nothing about how the correction was produced.
    Substituting ``2θ_B = 2θ_obs − c·T(2θ_obs)`` into ``m·sin θ_B = sin θ'_B``
    leaves one scalar equation in the amplitude ``c``:

        f(c) = m·sin(θ − ½c·T(2θ)) − sin(θ' − ½c·T(2θ'))

    which is smooth and, over the shift magnitudes this is used for, monotone in
    ``c``.  Newton from ``c = 0`` converges in a handful of steps.  For
    ``constant`` the closed form :func:`pair_shift` is exact and is used instead,
    which also makes it the reference the Newton path is pinned against.

    Generalising past a constant is the point: this package's real datasets are
    **cos θ displacement-dominated** (corundum's −0.065°, SRM 660c's geometrically
    predicted +0.0415°), so a constant-only estimator is biased — measured, ~5 %
    on corundum.  Whether that bias is *identifiable* is a separate question and
    the measured answer is no; see the module docstring.
    """
    if name == "constant":
        return pair_shift(two_theta_lo, two_theta_hi, m)
    tt_lo = np.asarray(two_theta_lo, dtype=np.float64)
    tt_hi = np.asarray(two_theta_hi, dtype=np.float64)
    m = np.asarray(m, dtype=np.float64)
    t_lo, t_hi = shift_template(name, tt_lo), shift_template(name, tt_hi)
    k = np.pi / 360.0                      # d(radians of a half-angle)/d(degrees)
    c = np.zeros(np.broadcast(tt_lo, tt_hi, m).shape, dtype=np.float64)
    for _ in range(iters):
        th = np.radians((tt_lo - c * t_lo) / 2.0)
        thp = np.radians((tt_hi - c * t_hi) / 2.0)
        f = m * np.sin(th) - np.sin(thp)
        df = -m * np.cos(th) * t_lo * k + np.cos(thp) * t_hi * k
        with np.errstate(divide="ignore", invalid="ignore"):
            step = np.where(np.abs(df) < 1e-14, np.nan, f / df)
        c = c - np.nan_to_num(step, nan=0.0, posinf=0.0, neginf=0.0)
    return c


def pair_shift_sensitivity(two_theta_lo: np.ndarray, two_theta_hi: np.ndarray,
                           m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """|∂c/∂2θ| for the low and high member of each pair — **derived, not quoted**.

    Implicit differentiation of ``m·sin(θ+z) = sin(θ'+z)``:

        dz = [cos θ'_B·dθ' − m·cos θ_B·dθ] / (m·cos θ_B − cos θ'_B)

    so the **low** line's error is amplified by ``m·cos θ_B/(m·cos θ_B − cos θ'_B)``
    and the **high** line's by ``cos θ'_B/(same)``.  The low member's coefficient is
    the larger by ≈ m, which is why the method wants a high harmonic order against a
    well-measured low line — and why a low line is the one worth measuring carefully.

    **Dong eq. (6) prints these two coefficients attached to the wrong errors.**
    The paper writes them as ``(m² − m·cos(θ'−θ))/D`` on ``|Δ2θ'|`` and
    ``(m·cos(θ'−θ) − 1)/D`` on ``|Δ2θ|``, with ``D = m² + 1 − 2m·cos(θ'−θ)``.  Those
    expressions are algebraically identical to the two derived here — using
    ``D = (m·cos θ_B − cos θ'_B)²`` and ``sin θ'_B = m·sin θ_B`` — but the first
    belongs to the **low** member and the paper attaches it to the high one.  At
    m = 2, θ = 10° they are 1.90880 and 0.90880, and swapping them roughly doubles
    or halves the propagated error.  Verified three independent ways in
    ``tests/test_indexing_pairs.py``: this derivation, a central difference of
    eq. (5) itself, and the paper's own printed algebra.

    Returned as absolute sensitivities for quadrature σ propagation.  Dong sums the
    two terms in absolute value, which is a *maximum* error rather than a σ; this
    package weights by measured per-line σ and so adds in quadrature.

    *Source:* Dong, Wu & Chen (1999), *J. Appl. Cryst.* **32**, 850, eq. (6) —
    corrected; see above.
    """
    c = pair_shift(two_theta_lo, two_theta_hi, m)
    th = np.radians((np.asarray(two_theta_lo, dtype=np.float64) - c) / 2.0)
    thp = np.radians((np.asarray(two_theta_hi, dtype=np.float64) - c) / 2.0)
    m = np.asarray(m, dtype=np.float64)
    den = m * np.cos(th) - np.cos(thp)
    den = np.where(np.abs(den) < 1e-12, np.nan, den)
    return np.abs(m * np.cos(th) / den), np.abs(np.cos(thp) / den)


@dataclass(frozen=True)
class PairSet:
    """Every harmonic pair a line list admits, with the shift each one implies."""

    #: index into the *sorted* position array, low and high member
    i: np.ndarray
    j: np.ndarray
    m: np.ndarray
    #: implied amplitude (° 2θ) and its propagated σ, per pair
    c: np.ndarray
    esd: np.ndarray
    n_lines: int
    n_candidate_triples: int
    template: str = "constant"

    def __len__(self) -> int:
        return int(self.c.size)


def enumerate_pairs(two_theta: np.ndarray,
                    two_theta_esd: np.ndarray | float | None = None, *,
                    template: str = "constant",
                    window_deg: float = PAIR_WINDOW_DEG,
                    max_m: int = PAIR_MAX_M) -> PairSet:
    """Every (i, j, m) triple whose implied shift lands inside the window.

    A *candidate triple* is any pair of lines whose sine ratio rounds to an integer
    ``2 ≤ m ≤ max_m``; it is *accepted* when the shift it implies is smaller than
    ``window_deg``.  The window is the only filter, and it is the right one: for a
    given ratio error the implied shift grows with m (see
    :func:`pair_shift_sensitivity`), so one window on ``c`` is automatically a
    tighter constraint on the ratio at high harmonic order than at low.

    ``m = 1`` is excluded because it is the line against itself, and ``max_m``
    because ``m·sin θ ≤ 1`` confines the low member of an m = 3 pair below ~39° 2θ
    and the supply above that is dominated by accidents rather than harmonics.

    Vectorised over the whole N×N grid — the loop-and-solve form costs 26 s of null
    on a 285-line list, which is the only reason to care.
    """
    tt = np.sort(np.asarray(two_theta, dtype=np.float64))
    n = len(tt)
    if two_theta_esd is None:
        esd = np.zeros(n)
    else:
        esd = np.broadcast_to(np.asarray(two_theta_esd, dtype=np.float64),
                              (n,)).astype(np.float64)
        # the caller's σ is in the caller's order; sort it the same way
        order = np.argsort(np.asarray(two_theta, dtype=np.float64))
        esd = esd[order]

    empty = np.zeros(0, dtype=np.float64)
    if n < 2:
        return PairSet(np.zeros(0, int), np.zeros(0, int), empty, empty, empty,
                       n, 0, template)

    sin_th = np.sin(np.radians(tt / 2.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = sin_th[None, :] / sin_th[:, None]
    m = np.round(ratio)
    iu = np.triu_indices(n, k=1)                  # j > i, so θ' > θ
    m_f = m[iu]
    keep = np.isfinite(m_f) & (m_f >= 2) & (m_f <= max_m)
    i_idx, j_idx = iu[0][keep], iu[1][keep]
    m_f = m_f[keep]
    n_triples = int(keep.sum())
    if n_triples == 0:
        return PairSet(np.zeros(0, int), np.zeros(0, int), empty, empty, empty,
                       n, 0, template)

    c = pair_shift_template(tt[i_idx], tt[j_idx], m_f, template)
    s_lo, s_hi = pair_shift_sensitivity(tt[i_idx], tt[j_idx], m_f)
    sigma = np.sqrt((s_lo * esd[i_idx]) ** 2 + (s_hi * esd[j_idx]) ** 2)

    inside = np.isfinite(c) & (np.abs(c) <= window_deg)
    return PairSet(i_idx[inside], j_idx[inside], m_f[inside], c[inside],
                   sigma[inside], n, n_triples, template)


def concentration(c: np.ndarray,
                  half_width_deg: float = PAIR_CLUSTER_HALF_WIDTH_DEG
                  ) -> tuple[int, float, np.ndarray]:
    """The densest cluster of implied shifts: its size, centre, and membership.

    Real harmonic pairs agree on ``c`` to within the propagated line precision;
    accidental ones are spread over the whole window.  So the number of pairs
    inside the best window of half-width ``half_width_deg`` is the evidence that
    *any* systematic is present, and its members are what the amplitude is
    estimated from.  This is the statistic that replaces the sign-category rule —
    see the module docstring for what that rule did on this corpus.
    """
    c = np.asarray(c, dtype=np.float64)
    if c.size == 0:
        return 0, float("nan"), np.zeros(0, dtype=bool)
    inside = np.abs(c[None, :] - c[:, None]) <= half_width_deg
    counts = inside.sum(axis=1)
    best = int(np.argmax(counts))
    members = inside[best]
    return int(counts[best]), float(np.median(c[members])), members


def null_two_theta(two_theta: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """N structureless lines over the same range — the null a detection is tested against.

    Uniform in **sin²θ**, which is uniform in Q up to the wavelength, because a
    lattice is linear in Q: a 2θ-uniform null would put too few lines where
    accidental harmonic coincidences actually live and would flatter the statistic.
    Carries no lattice, so any concentration it shows is chance by construction.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    s2 = np.sin(np.radians(tt / 2.0)) ** 2
    drawn = rng.uniform(float(s2.min()), float(s2.max()), size=len(tt))
    return 2.0 * np.degrees(np.arcsin(np.sqrt(np.clip(drawn, 0.0, 1.0))))


def pair_allowance(amplitude_deg: float, amplitude_esd_deg: float) -> float:
    """What a search window must span: the shift, plus how well it is known.

    The window is matched against *uncorrected* positions —
    :func:`refine_with_shift` fits the template only after a candidate survives —
    so it has to cover the shift itself.  That is the 4.3× lesson SRM 660c taught,
    where declaring the residual scatter (0.0078°) found nothing and declaring the
    amplitude (0.037°) recovered the certificate.

    **Everything beyond the amplitude is a liability, and the corpus says so
    sharply.**  A wider window is one more coincidence a wrong lattice is allowed
    to have: corundum keeps its certified lattice through σ_sys = 0.070 and loses
    it at 0.0767, and SRM 660c returns a cell 293 000 ppm wrong *at high
    confidence* at 0.060.  So the headroom is the standard error of the cluster
    **mean** — how well the amplitude is known — and never the pair-to-pair
    scatter, which is larger by the σ amplification each pair carries and would
    push corundum past its own breaking point.  See
    :data:`~pxrdref.schemas.indexing.SHIFT_ALLOWANCE_K_ESD` for the sweep.

    ``max|T|`` is 1 for all three templates over any range this is used on
    (``cos θ`` and ``sin 2θ`` both peak at 1, at low angle and at 45°
    respectively), so the amplitude *is* the largest correction the model applies
    anywhere and no range argument is needed.
    """
    esd = float(amplitude_esd_deg)
    if not np.isfinite(esd) or esd < 0.0:
        esd = 0.0
    return float(abs(amplitude_deg) + SHIFT_ALLOWANCE_K_ESD * esd)


@dataclass(frozen=True)
class PairShiftResult:
    """What the reflection-pair method concluded, and the evidence for it."""

    detected: bool
    amplitude_deg: float
    #: what a search window must span — see :func:`pair_allowance`
    allowance_deg: float
    amplitude_esd_deg: float
    scatter_deg: float
    n_pairs: int
    n_clustered: int
    n_candidate_triples: int
    z: float
    p_value: float
    null_k_mean: float
    null_k_std: float
    best: str | None = None
    #: per-template amplitude and cluster size, in ``SHIFT_TEMPLATES`` order
    per_template: dict = field(default_factory=dict)
    #: templates whose own concentration is not significant against the null —
    #: these are *refuted*, which is the one attribution the method may make
    refuted: tuple[str, ...] = ()
    seed: int = 0
    reason: str | None = None


def estimate_shift_from_pairs(two_theta: np.ndarray,
                              two_theta_esd: np.ndarray | float | None = None, *,
                              templates: tuple[str, ...] = SHIFT_TEMPLATES,
                              window_deg: float = PAIR_WINDOW_DEG,
                              max_m: int = PAIR_MAX_M,
                              half_width_deg: float = PAIR_CLUSTER_HALF_WIDTH_DEG,
                              replicates: int = PAIR_NULL_REPLICATES,
                              min_z: float = PAIR_MIN_Z,
                              seed: int = 0) -> PairShiftResult:
    """Measure a systematic 2θ shift from the peak list alone, or decline to.

    Returns ``detected = False`` with a ``reason`` whenever the evidence does not
    clear the null — which is the *normal* answer on a bare 20-line position list,
    measured: all ten sets of the bethanechol benchmark and the unidentified HL2
    list score z ≈ 0 here, independently reproducing Le Bail's (2004) §VII report
    that self-calibration on those very entries fails.  An estimator that answered
    anyway would be the confident-wrong-singleton failure this package refuses one
    rank up.

    The amplitude is the σ-weighted mean over the cluster members of the winning
    template, and ``scatter_deg`` is their scatter — the two together are what a
    search window must span, since ``refine_with_shift`` only corrects a candidate
    *after* it survives.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    rng = np.random.default_rng(seed)

    per_template: dict[str, dict] = {}
    null_k: dict[str, np.ndarray] = {}
    for name in templates:
        pairs = enumerate_pairs(tt, two_theta_esd, template=name,
                                window_deg=window_deg, max_m=max_m)
        k, centre, members = concentration(pairs.c, half_width_deg)
        ks = np.empty(replicates, dtype=np.float64)
        for r in range(replicates):
            nt = null_two_theta(tt, rng)
            npairs = enumerate_pairs(nt, template=name, window_deg=window_deg,
                                     max_m=max_m)
            ks[r] = concentration(npairs.c, half_width_deg)[0]
        null_k[name] = ks
        mu = float(ks.mean())
        sd = float(ks.std(ddof=1)) if replicates > 1 else 0.0
        z = (k - mu) / sd if sd > 0 else (np.inf if k > mu else 0.0)
        p = float((np.sum(ks >= k) + 1) / (replicates + 1))
        w = 1.0 / np.maximum(pairs.esd[members], 1e-6) ** 2 if k else np.zeros(0)
        vals = pairs.c[members]
        amp = float(np.sum(w * vals) / np.sum(w)) if k and np.sum(w) > 0 else centre
        scatter = float(np.std(vals, ddof=1)) if k > 1 else 0.0
        esd = (scatter / np.sqrt(k)) if k > 1 else float("nan")
        per_template[name] = {
            "k": k, "centre": centre, "amplitude": amp, "scatter": scatter,
            "esd": esd, "z": float(z), "p": p, "n_pairs": len(pairs),
            "null_mean": mu, "null_std": sd,
            "n_candidate_triples": pairs.n_candidate_triples}

    ranked = sorted(templates, key=lambda t: (-per_template[t]["k"],
                                              per_template[t]["scatter"]))
    best = ranked[0]
    b = per_template[best]
    # Refutation needs a margin as well as an insignificant concentration: k = 7
    # against a winner's 8 is one accidental pair, not evidence about a physical
    # cause.  Judged on p rather than z because a losing template lives in the
    # small-count regime where the null's σ collapses — see PAIR_MAX_P.
    refuted = tuple(t for t in templates
                    if per_template[t]["p"] > PAIR_MAX_P
                    and per_template[t]["k"] < PAIR_REFUTE_K_FRACTION * b["k"])

    if b["k"] < PAIR_MIN_CLUSTERED:
        reason = (f"{b['k']} pair(s) agree on a shift, below the "
                  f"{PAIR_MIN_CLUSTERED} the method needs — Dong (1999) asks for "
                  "at least three whose values are close to one another")
    elif b["z"] < min_z or b["p"] > PAIR_MAX_P:
        reason = (f"the densest agreement, {b['k']} of {b['n_pairs']} pairs, is "
                  f"z = {b['z']:.1f} (bar {min_z:g}), p = {b['p']:.3f} "
                  f"(bar {PAIR_MAX_P:g}) against a structureless null — "
                  "consistent with accidental harmonic coincidence")
    else:
        reason = None

    return PairShiftResult(
        detected=reason is None, amplitude_deg=b["amplitude"],
        allowance_deg=pair_allowance(b["amplitude"], b["esd"]),
        amplitude_esd_deg=b["esd"], scatter_deg=b["scatter"],
        n_pairs=b["n_pairs"], n_clustered=b["k"],
        n_candidate_triples=b["n_candidate_triples"], z=b["z"], p_value=b["p"],
        null_k_mean=b["null_mean"], null_k_std=b["null_std"],
        best=best if reason is None else None,
        per_template=per_template,
        refuted=refuted if reason is None else (), seed=seed, reason=reason)


__all__ = ["PairSet", "PairShiftResult", "concentration", "enumerate_pairs",
           "estimate_shift_from_pairs", "null_two_theta", "pair_allowance",
           "pair_shift", "pair_shift_sensitivity", "pair_shift_template",
           "shift_template"]
