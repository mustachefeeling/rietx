"""Figures of merit — a **panel**, scored in both directions, never one number.

The measured reason this is a panel and not a scalar is in this repo's own prior
art (tag ``guillemot-study``, ``studies/guillemot/out/audit_full.txt`` §D).
Screening a pattern whose answer is known, a wrong phase **ranked first on share
of observed intensity indexed — 83.7 %, with 390 predicted lines of which 9.0 %
are present** — above the truth, which indexed 79.2 % while showing 56.5 % of its
own 23 lines.  A big cell indexes everything and means nothing.  So

* :func:`predicted_seen_fraction` is a **first-class ranking member**, not a
  post-hoc validation field, and
* the ranking is Borda over the whole panel rather than a sort on any member.

That is also Oishi-Tomiyasu's (2013) argument for reversing the asymmetry in the
de Wolff figure of merit, reached independently here on this repo's own data.

**Every FoM carries its blind spot, and the blind spot travels with the number.**
:class:`~pxrdref.schemas.indexing.FigureOfMerit` has a ``blind_spot`` field and it
is filled from the same string the docstring states, so a consumer cannot see a
value without seeing what it cannot see.  Three of them matter enough to state
here: M₂₀ counts *lattice*-possible lines, so it is blind to space-group
extinctions, and its ⟨ΔQ⟩ is a plain mean, so one impurity line wrecks it; F_N
lives in 2θ, where a refined zero shift can manufacture a large value; and
``indexed_fraction`` is the exact quantity §D above showed ranking a 390-line
impostor first.
"""

from __future__ import annotations

import numpy as np

from ..schemas.indexing import FigureOfMerit, q_of_two_theta

#: How many σ_eff an observed and a predicted line may differ by and still count
#: as the same line.  Three, because σ(2θ) is *calibrated* — WP-1018's pull
#: ensemble measured mean +0.03/std 0.97 on a single line and −0.08/0.98 on a lab
#: doublet — so 3σ really is a 99.7 % window rather than a knob.  It is the one
#: number the whole panel shares, and every FoM reports which one it used.
MATCH_SIGMA = 3.0
#: Lines the classical figures of merit are defined on.  Not a round number: both
#: de Wolff's M₂₀ and Smith & Snyder's F₂₀ are defined on the first twenty, and
#: Smith's volume envelope is quoted at N = 20.
FOM_N = 20


def lattice_group(system: str, centring: str = "P") -> str:
    """The **absence-free** space-group symbol of a lattice: holohedry + centring.

    "Lattice-possible" in de Wolff's and Smith & Snyder's denominators means every
    reflection the *lattice* allows — so centring conditions count (they are
    lattice absences) and space-group conditions do not (they are not known yet,
    and determining them is WP-1025).  Passing this symbol to
    ``generate_reflections`` is what makes ``n_possible`` mean the same thing as
    in the papers.
    """
    holohedry = {
        "triclinic": "P -1", "monoclinic": "P 1 2/m 1", "orthorhombic": "P m m m",
        "tetragonal": "P 4/m m m", "trigonal": "P -3 m 1",
        "hexagonal": "P 6/m m m", "cubic": "P m -3 m",
    }
    if system not in holohedry:
        raise ValueError(f"unknown crystal system {system!r}")
    symbol = holohedry[system]
    if centring in ("", "P"):
        return symbol
    if system == "trigonal" and centring == "R":
        return "R -3 m"
    return centring + symbol[1:]


def predicted_lines(cell: tuple[float, ...], system: str, centring: str,
                    wavelength: float, two_theta_max: float,
                    two_theta_min: float = 0.0):
    """(hkl, Q) the lattice allows in range — the FoM denominators' population."""
    from ..crystallography.symmetry import generate_reflections

    refl = generate_reflections(lattice_group(system, centring), tuple(cell),
                                wavelength, two_theta_max, two_theta_min)
    q = 1.0 / np.asarray(refl.d, dtype=np.float64) ** 2
    order = np.argsort(q)
    return np.asarray(refl.hkl)[order], q[order]


def match_lines(q_obs: np.ndarray, q_esd: np.ndarray, q_pred: np.ndarray, *,
                k_sigma: float = MATCH_SIGMA):
    """(index of the matched prediction per observed line, |ΔQ| of the match).

    ``-1`` where nothing matched.  Matching is **per-line σ**, not one global
    tolerance: that is the whole contract ``schemas/indexing.py`` establishes, and
    it is why a strong sharp line and a weak shoulder are not held to the same
    window.
    """
    obs = np.asarray(q_obs, dtype=np.float64)
    pred = np.asarray(q_pred, dtype=np.float64)
    sig = np.maximum(np.asarray(q_esd, dtype=np.float64), 1e-300)
    if not len(pred):
        return np.full(len(obs), -1, dtype=np.int64), np.full(len(obs), np.inf)
    d = np.abs(obs[:, None] - pred[None, :])
    j = np.argmin(d, axis=1)
    best = d[np.arange(len(obs)), j]
    matched = best <= k_sigma * sig
    return np.where(matched, j, -1), np.where(matched, best, np.inf)


#: Relative tolerance on the "up to the N-th observed line" boundary in every
#: N_poss count.  It is a **tie rule, not a fudge**: the N-th observed line is
#: itself (ideally) a predicted line, so a strictly-less-than comparison makes the
#: count depend on floating-point rounding — measured, the *same lattice* in two
#: unimodular settings gave N_poss 20 and 19 and M₂₀ 76.43 and 80.45, a 5 % swing
#: on a quantity that must be setting-invariant by construction.
_BOUNDARY_RTOL = 1e-9


def _count_possible(pred: np.ndarray, limit: float) -> int:
    """Predictions up to ``limit``, counting the boundary (see _BOUNDARY_RTOL)."""
    return int(np.count_nonzero(np.asarray(pred)
                                <= limit * (1.0 + _BOUNDARY_RTOL)))


def nearest_discrepancy(obs: np.ndarray, pred: np.ndarray) -> np.ndarray:
    """|Δ| from each observed line to its **nearest** prediction, no window.

    This is what de Wolff's and Smith & Snyder's means are taken over: every
    observed line is assigned to the closest calculated line, and a line that is
    badly missed contributes a *large* discrepancy rather than being excluded.
    Applying a matching window here instead would make both figures blind to the
    lines they are supposed to punish — which is why :func:`match_lines` (the
    windowed version) is used only by the coverage members.
    """
    o = np.asarray(obs, dtype=np.float64)
    p = np.asarray(pred, dtype=np.float64)
    if not len(p) or not len(o):
        return np.full(len(o), np.inf)
    return np.min(np.abs(o[:, None] - p[None, :]), axis=1)


def m20(q_obs: np.ndarray, q_esd: np.ndarray, q_pred: np.ndarray, *,
        n: int = FOM_N, k_sigma: float = MATCH_SIGMA) -> FigureOfMerit:
    """de Wolff's M₂₀ = Q_N / (2·⟨ΔQ⟩·N_poss).

    *Source*: de Wolff, P. M. (1968), *J. Appl. Cryst.* **1**, 108-113.  Read it
    as a signal-to-noise ratio on the *density* of possible lines: a lattice that
    explains the observed Q values with small discrepancies while allowing few
    lines up to Q_N scores high.

    **⟨ΔQ⟩ is floored at the median σ(Q)**, and that floor is this package's own
    addition rather than de Wolff's.  It is needed because the figure divides by
    the discrepancy: on synthetic data — or on any candidate that happens to fit
    within fp noise — ⟨ΔQ⟩ → 0 and M₂₀ → ∞, so an unfloored implementation
    returns either infinity or (if it guards with a zero test) **zero**, which
    ranks a perfect cell last.  Both were seen while writing this.  The floor has
    a meaning rather than being an epsilon: a discrepancy smaller than the
    measurement precision is not knowable, and per-line σ is exactly what this
    package has and 1968 did not.

    **Blind spots** (carried in the returned object): it counts *lattice*-possible
    lines, so it is blind to space-group extinctions — a cell that is a supercell
    along one axis is punished only through N_poss; and ⟨ΔQ⟩ is a plain mean, so a
    single impurity line among the first twenty wrecks it.
    """
    order = np.argsort(np.asarray(q_obs, dtype=np.float64))[:n]
    obs = np.asarray(q_obs, dtype=np.float64)[order]
    if len(obs) < 2:
        return FigureOfMerit(name="m20", value=0.0, n_lines=len(obs),
                             n_possible=0, k_sigma=k_sigma,
                             blind_spot=_BLIND["m20"])
    esd = np.asarray(q_esd, dtype=np.float64)[order]
    q_n = float(obs[-1])
    pred = np.asarray(q_pred, dtype=np.float64)
    n_poss = _count_possible(pred, q_n)
    dq = nearest_discrepancy(obs, pred)
    mean_dq = float(np.mean(dq))
    floor = float(np.median(esd))
    denom = max(mean_dq, floor)
    value = (q_n / (2.0 * denom * n_poss)
             if denom > 0.0 and n_poss > 0 and np.isfinite(denom) else 0.0)
    return FigureOfMerit(name="m20", value=float(value), n_lines=len(obs),
                         n_possible=n_poss, k_sigma=k_sigma,
                         mean_discrepancy=mean_dq if np.isfinite(mean_dq) else -1.0,
                         blind_spot=_BLIND["m20"])


def f_n(two_theta_obs: np.ndarray, two_theta_esd: np.ndarray,
        two_theta_pred: np.ndarray, *, n: int = FOM_N,
        k_sigma: float = MATCH_SIGMA) -> FigureOfMerit:
    """Smith & Snyder's F_N = (1/⟨|Δ2θ|⟩)·(N_obs/N_poss).

    *Source*: Smith, G. S. & Snyder, R. L. (1979), *J. Appl. Cryst.* **12**,
    60-65.

    **Blind spot**: it lives in 2θ, so it is sensitive to exactly the systematic
    the shift model exists for — a refined zero shift can manufacture a large F_N
    by absorbing a mismatch that a Q-space figure would have shown.  It is kept in
    the panel *because* of that: its disagreement with M₂₀ is informative, and
    ``tests/test_indexing_core.py`` pins the non-invariance rather than papering
    over it.
    """
    order = np.argsort(np.asarray(two_theta_obs, dtype=np.float64))[:n]
    obs = np.asarray(two_theta_obs, dtype=np.float64)[order]
    if len(obs) < 2:
        return FigureOfMerit(name="f_n", value=0.0, n_lines=len(obs),
                             n_possible=0, k_sigma=k_sigma,
                             blind_spot=_BLIND["f_n"])
    esd = np.asarray(two_theta_esd, dtype=np.float64)[order]
    pred = np.asarray(two_theta_pred, dtype=np.float64)
    n_poss = _count_possible(pred, float(obs[-1]))
    d = nearest_discrepancy(obs, pred)
    mean_d = float(np.mean(d))
    # the same precision floor M₂₀ needs, in degrees this time
    denom = max(mean_d, float(np.median(esd)))
    value = (len(obs) / (denom * n_poss)
             if denom > 0.0 and n_poss > 0 and np.isfinite(denom) else 0.0)
    return FigureOfMerit(name="f_n", value=float(value), n_lines=len(obs),
                         n_possible=n_poss, k_sigma=k_sigma,
                         mean_discrepancy=mean_d if np.isfinite(mean_d) else -1.0,
                         blind_spot=_BLIND["f_n"])


def indexed_fraction(q_obs: np.ndarray, q_esd: np.ndarray, q_pred: np.ndarray, *,
                     intensity: np.ndarray | None = None,
                     k_sigma: float = MATCH_SIGMA) -> FigureOfMerit:
    """Share of the observed lines (or observed *intensity*) a lattice indexes.

    **Blind spot, and it is the measured one this whole module is arranged
    around**: a big enough cell indexes everything.  On the §D data a wrong phase
    scored 83.7 % here against the truth's 79.2 % — so this number must never be
    ranked on alone, and :func:`predicted_seen_fraction` is its other half.
    """
    obs = np.asarray(q_obs, dtype=np.float64)
    idx, _ = match_lines(obs, q_esd, q_pred, k_sigma=k_sigma)
    hit = idx >= 0
    if intensity is None:
        value = float(np.mean(hit)) if len(hit) else 0.0
        name = "indexed_fraction"
    else:
        w = np.asarray(intensity, dtype=np.float64)
        total = float(np.sum(np.abs(w)))
        value = float(np.sum(np.abs(w[hit])) / total) if total > 0 else 0.0
        name = "indexed_intensity_fraction"
    return FigureOfMerit(name=name, value=value, n_lines=len(obs),
                         n_possible=int(len(np.asarray(q_pred))),
                         k_sigma=k_sigma, blind_spot=_BLIND["indexed_fraction"])


def predicted_seen_fraction(q_obs: np.ndarray, q_esd: np.ndarray,
                            q_pred: np.ndarray, *, k_sigma: float = MATCH_SIGMA
                            ) -> FigureOfMerit:
    """Share of the lattice's *predicted* lines that are actually present.

    The reversed direction, and a **first-class** ranking member: it is what
    separates a lattice that explains the pattern from one large enough to have a
    line near everything.  On the §D data the impostor showed 9.0 % of its 390
    predicted lines against the truth's 56.5 % of 23 — the two directions
    disagree by a factor of six where the forward direction disagreed by 4 points
    in the wrong direction.

    **Blind spot**: legitimately absent reflections count against a *correct*
    cell — space-group extinctions (unknown until WP-1025) and reflections too
    weak to detect.  So a low value is not evidence of a wrong cell on its own;
    it is evidence against a cell that also indexes suspiciously much.
    """
    pred = np.asarray(q_pred, dtype=np.float64)
    if not len(pred):
        return FigureOfMerit(name="predicted_seen_fraction", value=0.0,
                            n_lines=len(np.asarray(q_obs)), n_possible=0,
                            k_sigma=k_sigma,
                            blind_spot=_BLIND["predicted_seen_fraction"])
    # reverse the roles: for each prediction, is there an observed line within
    # that *observed* line's own σ?  The σ belongs to the measurement, so it stays
    # attached to the observation even when the loop runs the other way.
    obs = np.asarray(q_obs, dtype=np.float64)
    sig = np.maximum(np.asarray(q_esd, dtype=np.float64), 1e-300)
    if not len(obs):
        seen = np.zeros(len(pred), dtype=bool)
    else:
        d = np.abs(pred[:, None] - obs[None, :])
        j = np.argmin(d, axis=1)
        seen = d[np.arange(len(pred)), j] <= k_sigma * sig[j]
    return FigureOfMerit(
        name="predicted_seen_fraction", value=float(np.mean(seen)),
        n_lines=len(obs), n_possible=len(pred), k_sigma=k_sigma,
        blind_spot=_BLIND["predicted_seen_fraction"])


def fom_panel(q_obs: np.ndarray, q_esd: np.ndarray, intensity: np.ndarray,
              two_theta_obs: np.ndarray, two_theta_esd: np.ndarray,
              cell: tuple[float, ...], system: str, centring: str,
              wavelength: float, *, k_sigma: float = MATCH_SIGMA,
              ) -> list[FigureOfMerit]:
    """Every figure of merit for one candidate, in one pass over the predictions."""
    tt_max = float(np.max(two_theta_obs)) if len(two_theta_obs) else 0.0
    _hkl, q_pred = predicted_lines(cell, system, centring, wavelength,
                                   max(tt_max, 1.0))
    tt_pred = np.degrees(2.0 * np.arcsin(np.clip(
        wavelength * np.sqrt(q_pred) / 2.0, -1.0, 1.0)))
    return [
        m20(q_obs, q_esd, q_pred, k_sigma=k_sigma),
        f_n(two_theta_obs, two_theta_esd, tt_pred, k_sigma=k_sigma),
        indexed_fraction(q_obs, q_esd, q_pred, k_sigma=k_sigma),
        indexed_fraction(q_obs, q_esd, q_pred, intensity=intensity,
                         k_sigma=k_sigma),
        predicted_seen_fraction(q_obs, q_esd, q_pred, k_sigma=k_sigma),
    ]


def borda_scores(panels: list[list[FigureOfMerit]]) -> np.ndarray:
    """Borda count over the panel: sum of each candidate's rank in every member.

    Higher is better, and every member weighs the same.  A weighted sum would
    need weights, and there is no data on which to set them — whereas the *rank*
    aggregation needs none and is invariant to each member's units and scale,
    which matters when the panel mixes a ratio (M₂₀), an inverse-degrees quantity
    (F_N) and two fractions.
    """
    if not panels:
        return np.zeros(0)
    names = [f.name for f in panels[0]]
    scores = np.zeros(len(panels))
    for k, name in enumerate(names):
        values = np.array([p[k].value if p[k].name == name else np.nan
                           for p in panels])
        order = np.argsort(np.argsort(values))     # 0 = worst
        scores += order
    return scores


def fom_panel_disagrees(panels: list[list[FigureOfMerit]]) -> bool:
    """Do the panel's members put different candidates first?

    A disagreement is not a tie-break problem, it is *information*: the members
    have different blind spots, so when they rank differently at least one blind
    spot is active.  WP-1024 turns this into a confidence statement rather than
    resolving it here.
    """
    if len(panels) < 2:
        return False
    winners = set()
    for k in range(len(panels[0])):
        values = [p[k].value for p in panels]
        winners.add(int(np.argmax(values)))
    return len(winners) > 1


#: Blind spots, stated once and attached to every value the functions return.
_BLIND: dict[str, str] = {
    "m20": ("counts lattice-possible lines, so it is blind to space-group "
            "extinctions; its ⟨ΔQ⟩ is a plain mean, so one impurity line among "
            "the first twenty wrecks it"),
    "f_n": ("lives in 2θ, so a refined zero shift can manufacture a large value "
            "by absorbing a mismatch a Q-space figure would show"),
    "indexed_fraction": ("a big enough cell indexes everything — measured, a "
                         "wrong phase scored 83.7 % against the truth's 79.2 % "
                         "with 390 predicted lines to the truth's 23"),
    "predicted_seen_fraction": ("legitimately absent reflections count against a "
                                "correct cell: space-group extinctions (unknown "
                                "until the extinction symbol is determined) and "
                                "reflections too weak to detect"),
}

__all__ = ["FOM_N", "MATCH_SIGMA", "borda_scores", "f_n",
           "fom_panel", "fom_panel_disagrees", "indexed_fraction",
           "lattice_group", "m20", "match_lines", "nearest_discrepancy",
           "predicted_lines",
           "predicted_seen_fraction", "q_of_two_theta"]
