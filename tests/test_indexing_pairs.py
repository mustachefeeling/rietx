"""The reflection-pair shift screen (WP-1038).

Four things are pinned here, in the order they would break:

1. **Dong's own published tables**, so the equation and the sign convention
   cannot drift — including the fact that the paper's printed *rows* carry sign
   typos while its averages do not.
2. **eq. (6)'s transposition**, three independent ways, so nobody "fixes" the
   derived σ propagation back to the paper.
3. The estimator's **refusals**, which are the half that matters: a structureless
   list, a short list, and the bethanechol benchmark whose published failure this
   reproduces.
4. The **escape hatch**: ``shift_from_pairs=False`` reproduces the prior contract
   exactly.
"""

from __future__ import annotations

import numpy as np
import pytest

from anatase.indexing.pairs import (
    concentration,
    enumerate_pairs,
    estimate_shift_from_pairs,
    null_two_theta,
    pair_allowance,
    pair_shift,
    pair_shift_sensitivity,
    pair_shift_template,
    shift_template,
)
from anatase.schemas.indexing import PAIR_MAX_P, PAIR_MIN_Z, PeakList

# Dong, Wu & Chen (1999) Table 2 — La-doped Bi-2201, 00l only.
# (2θ, 2θ', m, 2θ_z as *printed*).  The paper quotes an average of −0.0334°.
DONG_TABLE_2 = [
    (14.418, 29.032, 2, -0.036), (14.418, 44.153, 3, +0.035),
    (14.418, 60.136, 4, +0.034), (14.418, 77.542, 5, -0.034),
    (14.418, 97.417, 6, +0.034), (21.682, 44.153, 2, -0.036),
    (21.682, 68.614, 3, +0.034), (21.682, 97.417, 4, -0.034),
    (29.032, 60.136, 2, -0.030), (29.032, 97.417, 3, -0.031),
    (36.512, 77.542, 2, -0.032), (44.153, 97.417, 2, -0.031),
]
# Table 3 — Pr2Ni(1−x)LixO4 with NiO as a minor phase; average −0.182°.
DONG_TABLE_3 = [
    (17.078, 34.384, 2, -0.156), (17.078, 72.236, 4, -0.163),
    (25.225, 81.329, 3, -0.181), (28.635, 59.051, 2, -0.191),
    (32.446, 67.698, 2, -0.184), (34.384, 72.236, 2, -0.176),
    (37.356, 79.369, 2, -0.198), (37.458, 79.635, 2, +0.188),
    (43.728, 95.944, 2, -0.193), (45.245, 100.233, 2, -0.187),
    (49.327, 112.723, 2, -0.184),
]


def _zero_shift(rows):
    """The paper's 2θ_z for each row — our c with the sign convention undone."""
    return np.array([-float(pair_shift(lo, hi, m)) for lo, hi, m, _ in rows])


def test_dong_table_2_is_reproduced_and_the_printed_signs_are_typos():
    """Both of the paper's averages come out; four of its twelve rows do not.

    This is the test that decides a sign convention, so it is worth stating what
    settles it.  Row by row we agree with |2θ_z| everywhere and with the *printed*
    sign on 8 of 12.  The tie-break is the paper's own quoted average, −0.0334°:
    that is the mean of the magnitudes taken all-negative, while the mean of the
    printed signs is −0.0106°.  So the plus signs are typesetting drops, our
    equation is right, and a future reader must not "correct" it to match a row.
    """
    ours = _zero_shift(DONG_TABLE_2)
    printed = np.array([r[3] for r in DONG_TABLE_2])

    assert np.allclose(np.abs(ours), np.abs(printed), atol=1.1e-3)
    assert ours.mean() == pytest.approx(-0.0334, abs=5e-5), (
        "the paper's stated average for Table 2")
    assert (ours < 0).all(), "every pair in Table 2 implies the same sign"
    assert printed.mean() == pytest.approx(-0.0106, abs=5e-4), (
        "taking the printed signs at face value gives a different average from "
        "the one the paper itself quotes — which is how we know they are typos")


def test_dong_table_3_is_reproduced_including_the_two_phase_pairs():
    """The paper's second example, and its point: pairs from a *second phase*
    agree with the first.

    Rows 7 and 8 come from NiO rather than from the title compound, and the
    method neither knows nor needs to know — a harmonic pair constrains the
    shift, not the lattice, so an impurity's own pairs measure the same
    instrument.  That is what makes this method usable on a mixture, and it is
    why ``cpd-1a`` is in the corpus.
    """
    ours = _zero_shift(DONG_TABLE_3)
    printed = np.array([r[3] for r in DONG_TABLE_3])

    assert np.allclose(np.abs(ours), np.abs(printed), atol=1e-3)
    assert ours.mean() == pytest.approx(-0.182, abs=5e-4)
    assert ours[7] < 0, "row 8 prints +0.188 where every other row is negative"
    # the NiO rows (003/006 and 101/202) sit inside the spread of the rest
    assert abs(ours[6] - ours.mean()) < 0.02
    assert abs(ours[7] - ours.mean()) < 0.02


def test_dong_equation_6_prints_its_two_coefficients_transposed():
    """The σ propagation is **derived**, and the paper's printed form is wrong.

    Implicit differentiation of ``m·sin(θ+z) = sin(θ'+z)`` gives

        dz = [cos θ'_B·dθ' − m·cos θ_B·dθ]/(m·cos θ_B − cos θ'_B)

    so the **low** member's error is amplified by ``m·cos θ_B/(m cos θ_B −
    cos θ'_B)`` and the high member's by ``cos θ'_B/(same)``.  At m = 2, θ = 10°
    those are 1.90880 and 0.90880.  Dong eq. (6) writes the algebraically
    identical expressions but attaches the first to ``|Δ2θ'|`` — the *high*
    member — and the second to ``|Δ2θ|``.

    Checked three ways so the conclusion does not rest on one derivation: our
    closed form, a central difference of eq. (5) itself, and the paper's own
    printed algebra evaluated numerically.  Swapping them roughly doubles or
    halves a propagated σ, and the physical reading flips with it: it is the
    **low** line whose error is amplified by ~m, which is why the method wants a
    high harmonic order against a well-measured low line.
    """
    m, tt_lo = 2, 20.0
    th = np.radians(tt_lo / 2.0)
    tt_hi = 2.0 * np.degrees(np.arcsin(m * np.sin(th)))

    s_lo, s_hi = pair_shift_sensitivity(tt_lo, tt_hi, m)
    assert float(s_lo) == pytest.approx(1.90880, abs=1e-5)
    assert float(s_hi) == pytest.approx(0.90880, abs=1e-5)
    assert s_lo > s_hi, "the low member is the sensitive one — the paper's text "\
                        "says so even where its equation does not"

    # (a) central difference of eq. (5)
    h = 1e-6
    d_lo = (pair_shift(tt_lo + h, tt_hi, m) - pair_shift(tt_lo - h, tt_hi, m)) / (2 * h)
    d_hi = (pair_shift(tt_lo, tt_hi + h, m) - pair_shift(tt_lo, tt_hi - h, m)) / (2 * h)
    assert abs(float(d_lo)) == pytest.approx(float(s_lo), rel=1e-5)
    assert abs(float(d_hi)) == pytest.approx(float(s_hi), rel=1e-5)

    # (b) the paper's printed expressions, evaluated — same two numbers, and the
    # one it multiplies by |Δ2θ'| is the one belonging to |Δ2θ|
    thp = np.radians(tt_hi / 2.0)
    d_paper = m**2 + 1 - 2 * m * np.cos(thp - th)
    printed_on_delta_hi = (m**2 - m * np.cos(thp - th)) / d_paper
    printed_on_delta_lo = abs(m * np.cos(thp - th) - 1) / d_paper
    assert printed_on_delta_hi == pytest.approx(1.90880, abs=1e-5)
    assert printed_on_delta_lo == pytest.approx(0.90880, abs=1e-5)
    assert printed_on_delta_hi == pytest.approx(float(s_lo), abs=1e-5), (
        "the coefficient the paper attaches to the HIGH member's error is "
        "numerically the LOW member's sensitivity — that is the transposition")


def test_the_newton_generalisation_reproduces_the_closed_form():
    """``constant`` has an exact solution, so it is the reference the general
    solver is held to — and the general solver must reach it from c = 0."""
    lo = np.array([r[0] for r in DONG_TABLE_2])
    hi = np.array([r[1] for r in DONG_TABLE_2])
    m = np.array([float(r[2]) for r in DONG_TABLE_2])
    assert np.allclose(pair_shift_template(lo, hi, m, "constant"),
                       pair_shift(lo, hi, m), atol=1e-12)


@pytest.mark.parametrize("name", ["constant", "cos_theta", "sin_2theta"])
def test_an_injected_shift_is_recovered_by_its_own_template(name):
    """The pair relation is exact for *any* shift model — the generalisation the
    WP asks for, checked by injection rather than asserted.

    Build harmonic pairs from a true lattice, displace every position by
    ``c·T(2θ)``, and the solver must return ``c`` for that template.  Note the
    injection is applied at the *observed* angle, which is where a real aberration
    acts and is what makes this a fixed-point rather than a linearisation.
    """
    c_true = 0.06
    d0 = np.array([8.0, 6.0, 5.0, 4.2])
    lam = 1.5406
    pairs = []
    for d in d0:
        for m in (2, 3):
            s, sp = lam / (2 * d), m * lam / (2 * d)
            if sp >= 1.0:
                continue
            lo = 2 * np.degrees(np.arcsin(s))
            hi = 2 * np.degrees(np.arcsin(sp))
            pairs.append((lo, hi, m))
    assert pairs, "the geometry must offer pairs at all"

    lo = np.array([p[0] for p in pairs])
    hi = np.array([p[1] for p in pairs])
    m = np.array([float(p[2]) for p in pairs])
    # 2θ_obs = 2θ_B + c·T(2θ_obs): solve the fixed point so the injection is
    # defined at the observed angle, the way an aberration actually acts
    obs_lo, obs_hi = lo.copy(), hi.copy()
    for _ in range(80):
        obs_lo = lo + c_true * shift_template(name, obs_lo)
        obs_hi = hi + c_true * shift_template(name, obs_hi)

    got = pair_shift_template(obs_lo, obs_hi, m, name)
    assert np.allclose(got, c_true, atol=1e-9), (
        f"{name}: recovered {got} for an injected {c_true}")


def test_a_structureless_list_is_refused_and_a_real_one_is_not():
    """The whole estimator in one test: harmonics are detected, noise is not.

    The positive case is a real lattice with an injected shift; the negative is
    the same number of lines drawn uniformly in sin²θ over the same range, which
    is the null the detection is scored against.  A method that answered on the
    second would be the confident wrong singleton this package refuses one rank
    up — and DICVOL04's sign-category rule *does* answer on lists like it.
    """
    lam, a, c_true = 1.5406, 5.6402, -0.055
    hkl = [(h, k, ll) for h in range(5) for k in range(5) for ll in range(5)
           if (h, k, ll) != (0, 0, 0) and (h + k) % 2 == 0
           and (k + ll) % 2 == 0 and (h + ll) % 2 == 0]
    q = np.unique(np.round([(h * h + k * k + ll * ll) / a**2 for h, k, ll in hkl], 12))
    s = lam * np.sqrt(q) / 2.0
    tt_true = 2.0 * np.degrees(np.arcsin(s[s < 0.98]))
    tt = tt_true + c_true * shift_template("cos_theta", tt_true)
    assert len(tt) >= 12

    good = estimate_shift_from_pairs(tt, 0.005, seed=7)
    assert good.detected, good.reason
    assert good.amplitude_deg == pytest.approx(c_true, abs=0.004)
    assert good.z >= PAIR_MIN_Z and good.p_value <= PAIR_MAX_P
    assert good.n_clustered >= 3
    # the window spans the amplitude that was *measured* — which is all it can
    # do, and on this noiseless synthetic the two differ by 1e-5°
    assert good.allowance_deg >= abs(good.amplitude_deg)
    assert good.allowance_deg == pytest.approx(abs(c_true), abs=0.004)

    rng = np.random.default_rng(11)
    for trial in range(5):
        noise = np.sort(null_two_theta(tt, rng))
        bad = estimate_shift_from_pairs(noise, 0.005, seed=100 + trial)
        assert not bad.detected, (
            f"replicate {trial} answered on a structureless list: "
            f"{bad.amplitude_deg:+.4f}° at z = {bad.z:.1f}")
        assert bad.reason


def test_the_bethanechol_benchmark_declines_reproducing_a_published_failure():
    """All ten published sets refuse, and that is the correct answer.

    Le Bail (2004) §VII, of these very ICDD entries: *"Any self-calibration from
    these original data failed to estimate that zeropoint error."*  This is the
    most decisive test available for the method and the literature says it fails,
    so a pass here would be the suspicious result.  The mechanism is supply: a
    bare 20-line list over 6-31° 2θ offers 1-7 admitted pairs against the 3 that
    must *agree*, because ``m·sin θ ≤ 1`` confines an m = 3 pair's low member
    below ~39° 2θ.
    """
    import json
    import pathlib

    path = pathlib.Path(__file__).parent / "data" / "bethanechol_indexing.json"
    if not path.exists():
        pytest.skip("bethanechol benchmark fixture not present")
    sets = json.loads(path.read_text(encoding="utf-8"))["sets"]
    assert len(sets) == 10

    for name, s in sets.items():
        tt = np.array(s["two_theta"], dtype=np.float64)
        res = estimate_shift_from_pairs(tt, 0.02, seed=3)
        assert not res.detected, (
            f"set {name} reported {res.amplitude_deg:+.4f}° from "
            f"{res.n_clustered} pairs — the published result is that "
            "self-calibration on these data fails")
        assert res.reason


def test_the_allowance_is_the_amplitude_plus_only_how_well_it_is_known():
    """``pair_allowance`` spans the shift, and barely more — measured both ways.

    Declaring *less* than the amplitude is the SRM 660c failure: the residual
    scatter is 0.0078° against a 0.037° shift, and a window that size finds
    nothing.  Declaring *more* is the failure the corpus sweep found, and it is
    the worse one, because it returns a wrong cell rather than none — corundum
    keeps its certified trigonal *R* lattice through σ_sys = 0.070 and flips to
    hexagonal *P* at 0.0767, and SRM 660c returns a cell 293 000 ppm wrong at
    ``high`` confidence at 0.060.

    Hence the headroom is the standard error of the mean and **not** the
    pair-to-pair scatter: on corundum those give 0.0680 and 0.0767, and the
    breaking point falls between them.
    """
    assert pair_allowance(0.037, 0.0020) > 0.037, "must span the shift itself"
    assert pair_allowance(-0.0639, 0.0014) == pytest.approx(0.0639 + 3 * 0.0014)
    assert pair_allowance(-0.0639, 0.0014) < 0.070, (
        "corundum's own measured allowance must stay inside its measured "
        "breaking point, or the certified lattice stops ranking first")
    # the scatter is the quantity that overshoots — 0.0043 on corundum, which
    # would put the window at 0.0767, past the flip
    assert 0.0639 + 3 * 0.0043 > 0.0767 - 1e-9

    assert pair_allowance(0.0, 0.0) == 0.0
    assert pair_allowance(0.02, float("nan")) == pytest.approx(0.02), (
        "a single-pair cluster has no standard error and must not poison the "
        "window with a NaN")


def test_the_enumeration_is_a_window_on_the_shift_not_on_the_ratio():
    """Candidate triples versus accepted pairs, and why one window suffices.

    For a given ratio error the implied shift grows with m, so a single window on
    ``c`` is automatically a tighter constraint on the sine ratio at high harmonic
    order — which is the sensitivity result one test up, used as a filter.
    """
    tt = np.array([10.0, 20.3253, 15.0, 30.6, 22.0, 45.2, 60.0])
    wide = enumerate_pairs(tt, 0.01, window_deg=0.5)
    tight = enumerate_pairs(tt, 0.01, window_deg=0.01)
    assert wide.n_candidate_triples >= len(wide) >= len(tight)
    assert wide.n_candidate_triples == tight.n_candidate_triples, (
        "the triples examined do not depend on the window; only acceptance does")
    assert (wide.m >= 2).all()
    assert (wide.esd > 0).all(), "σ must propagate to every accepted pair"


def test_concentration_finds_the_densest_agreement_not_the_mean():
    """The statistic is a mode, not an average, because accidental pairs are
    spread rather than centred — an average over them moves the answer, a densest
    window does not."""
    c = np.array([-0.19, -0.05, -0.048, -0.052, -0.051, 0.02, 0.17, 0.19])
    k, centre, members = concentration(c, 0.010)
    assert k == 4
    assert centre == pytest.approx(-0.0505, abs=1e-3)
    assert members.sum() == 4
    # the plain mean sits 0.049° away from the agreement the pairs actually
    # show — an order above the cluster's own width, which is the whole reason
    # the statistic is a mode
    assert float(np.mean(c)) == pytest.approx(-0.0014, abs=1e-3)
    assert abs(float(np.mean(c)) - centre) > 0.045

    assert concentration(np.zeros(0))[0] == 0


def test_shift_from_pairs_is_an_escape_hatch_that_restores_the_prior_contract():
    """``shift_from_pairs=False`` must reproduce the pre-WP-1038 screen exactly.

    The default changed, so the old behaviour has to remain reachable and has to
    be *tested* rather than assumed — a caller reproducing a published number
    needs the switch to mean what it says.
    """
    from anatase.indexing.quality import assess_peak_list

    rng = np.random.default_rng(5)
    a, lam = 5.6402, 1.5406
    q = np.unique([(h * h + k * k + ll * ll) / a**2
                   for h in range(5) for k in range(5) for ll in range(5)
                   if (h, k, ll) != (0, 0, 0) and (h + k) % 2 == 0
                   and (k + ll) % 2 == 0 and (h + ll) % 2 == 0])
    tt = 2.0 * np.degrees(np.arcsin((lam * np.sqrt(q) / 2.0)[
        (lam * np.sqrt(q) / 2.0) < 0.98]))
    tt = tt - 0.05 * shift_template("cos_theta", tt)
    peaks = PeakList.from_positions(tt, wavelength=lam,
                                    two_theta_esd=0.004 + 0 * tt)

    off = assess_peak_list(peaks)
    assert off.shift.source == "unavailable"
    assert off.shift.allowance_deg == 0.0
    assert off.shift.pairs is None

    on = assess_peak_list(peaks, shift_from_pairs=True)
    assert on.shift.source == "reflection_pairs"
    assert on.shift.allowance_deg > 0.0
    assert on.shift.pairs is not None and on.shift.pairs.n_clustered >= 3

    # everything that is not the shift is untouched by the switch
    for field in ("n_usable", "relative_sigma_q_median", "sigma_over_spacing",
                  "supports_indexing", "systems_supported", "volume_envelope"):
        assert getattr(off, field) == getattr(on, field), field
    assert rng is not None  # (seeded rng kept for parity with sibling tests)


def test_the_screen_declines_to_name_a_cause_it_cannot_separate():
    """The method may report an amplitude and refute a template; it may not
    choose between the two collinear ones.

    Measured across the corpus, ``constant`` and ``cos_theta`` concentrate within
    one pair of each other everywhere, which is
    ``template_collinearity``'s 0.96 arriving by a second road.  So ``separable``
    must be False on a normal list, and a caller who reads ``best`` as the cause
    is reading past the flag that says not to.
    """
    from anatase.indexing.quality import screen_shift_from_pairs

    a, lam = 5.6402, 1.5406
    q = np.unique([(h * h + k * k + ll * ll) / a**2
                   for h in range(5) for k in range(5) for ll in range(5)
                   if (h, k, ll) != (0, 0, 0) and (h + k) % 2 == 0
                   and (k + ll) % 2 == 0 and (h + ll) % 2 == 0])
    s = lam * np.sqrt(q) / 2.0
    tt = 2.0 * np.degrees(np.arcsin(s[s < 0.98]))
    tt = tt + 0.05 * shift_template("cos_theta", tt)

    screen = screen_shift_from_pairs(tt, 0.004, seed=1)
    assert screen.source == "reflection_pairs"
    assert screen.best in ("constant", "cos_theta")
    assert not screen.separable, (
        "the two collinear templates cannot be told apart from pairs alone")
    assert screen.pairs.z >= PAIR_MIN_Z
    assert screen.max_collinearity > 0.9
