"""Agreement indices, defined per Toby (2006), Powder Diffraction 21, 67-70.

    R_p   = Σ|y_o − y_c| / Σ y_o
    R_wp  = √[ Σ w (y_o − y_c)² / Σ w y_o² ]
    R_exp = √[ (N − P) / Σ w y_o² ]
    χ²    = Σ w (y_o − y_c)² / (N − P)        (reduced)
    GoF   = √χ² = R_wp / R_exp

``rwp_background_subtracted`` recomputes R_wp with the background removed from
both numerator-model and denominator-observed, the variant Toby recommends
when the background carries much of the raw intensity.  The Durbin-Watson
statistic d = Σ(Δᵢ−Δᵢ₋₁)²/ΣΔᵢ² on weighted residuals (Hill & Flack, 1987,
J. Appl. Cryst. 20, 356) flags serial correlation (d ≈ 2 ⇒ uncorrelated).

When residuals *are* serially correlated the χ²·(JᵀJ)⁻¹ esds are too small:
neighbouring points do not carry independent information.  Bérar & Lelann
(1991, J. Appl. Cryst. 24, 1) sum consecutive same-sign weighted residuals
coherently, χ²' = Σ_runs (Σ_{i∈run} δᵢ)² ≥ χ², and multiply every esd by
√(χ²'/χ²) — the inflation factor reported here and applied to the esds.
"""

from __future__ import annotations

import numpy as np

from ..backend.linalg64 import require_fp64, to_host_fp64
from ..schemas.results import Statistics


def normal_covariance(jac: np.ndarray, resid: np.ndarray, n_free: int, *,
                      chi2_floor: bool = False,
                      what: str = "residual entering the covariance solve",
                      ) -> tuple[np.ndarray, float]:
    """``Cov = χ²_red · pinv(JᵀJ)`` — the one guarded normal-matrix solve.

    Returns ``(cov, chi2_red)`` with ``chi2_red`` always the *raw*
    Σr²/(N−P), even when ``chi2_floor`` has floored the factor applied to
    ``cov``: the raw value is what a caller reports, the floored one is what it
    should trust.  ``chi2_floor=True`` replaces the factor with
    ``max(χ²_red, 1)``, for a fit whose model is known to be inexact and whose
    esds must not be *deflated* by a locally-good χ² (peak profiles over a
    single line); the whole-pattern fit leaves it off, because there χ²_red < 1
    means the file's esds are pessimistic and shrinking is correct.

    **The pseudo-inverse is taken on the symmetrised matrix with
    ``hermitian=True``, and this is a correctness requirement, not a
    micro-optimisation.**  JᵀJ is positive semi-definite, so its Moore-Penrose
    inverse is too and every |ρ| ≤ 1 exactly.  But the *general* SVD path
    ``pinv`` takes by default treats the matrix as unstructured, and on a
    cond ≈ 10²⁰ normal matrix (routine here — the scale/axial/background block
    of a real fit) it returns a visibly non-symmetric, non-PSD result: measured
    |ρ| up to 1.6 × 10³ on synthetic ill-conditioning, and +2.75 for
    ``scale ~ axial_sl`` on the WP-0502 fluorite fit, which is what made that WP
    log "the correlation guard is undermined wherever conditioning is poor".
    ``hermitian=True`` routes through ``eigh``, which cannot break the symmetry,
    and caps the same cases at 1 + 4 ulp.

    The solve is fp64 unconditionally (architecture invariant 2): cond(JᵀJ) =
    cond(J)², so forming and inverting the normal matrix is the step reduced
    precision can never take.  ``to_host_fp64`` is that boundary — a Jacobian
    whose columns were computed at fp32 is upcast here before JᵀJ, while the
    residual is *required* to have been fp64 all along.

    This lives here, rather than inside :func:`covariance_estimates`, because
    two surfaces now need it — the whole-pattern fit and the per-peak profile
    fits of :mod:`rietx.indexing.peakfit` — and they must not be able to
    disagree about the pinv guarding.
    """
    require_fp64(resid, what)
    jac = to_host_fp64(jac)
    JTJ = jac.T @ jac
    JTJ = 0.5 * (JTJ + JTJ.T)  # kill the fp asymmetry before the eigensolve
    chi2_red = float(resid @ resid) / max(len(resid) - n_free, 1)
    scale = max(chi2_red, 1.0) if chi2_floor else chi2_red
    return np.linalg.pinv(JTJ, hermitian=True) * scale, chi2_red


def berar_lelann_factor(delta: np.ndarray) -> float:
    """Esd inflation factor for serial correlation.

    Bérar & Lelann (1991), J. Appl. Cryst. 24, 1: runs of consecutive
    weighted residuals δᵢ = √wᵢ·Δᵢ sharing a sign are summed coherently,

        χ²' = Σ_runs (Σ_{i∈run} δᵢ)²

    and esds are multiplied by √(χ²'/χ²).  Same-sign cross terms are
    positive, so the factor is always ≥ 1.

    Caveat (documented, not hidden): the estimator is *conservative*.  Even
    iid Gaussian residuals form chance runs (geometric length distribution,
    mean 2), giving E[χ²']/χ² = 1 + 4/π, i.e. an expected factor ≈ 1.51 for
    perfectly white residuals — verified against simulation in the tests.
    Treat the factor as an upper bound on the serial-correlation esd damage;
    Andreev (1994, J. Appl. Cryst. 27, 288) develops a figure of merit that
    removes this bias.  The raw published factor is what FullProf applies,
    and it is reported in ``Statistics.esd_inflation`` so it can be divided
    back out.
    """
    d = np.asarray(delta, dtype=np.float64)
    if len(d) < 2:
        return 1.0
    chi2 = float(d @ d)
    if chi2 <= 0.0:
        return 1.0
    sign = np.sign(d)
    change = np.nonzero(sign[1:] != sign[:-1])[0] + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change, [len(d)]])
    cs = np.concatenate([[0.0], np.cumsum(d)])
    run_sums = cs[ends] - cs[starts]
    return max(float(np.sqrt((run_sums @ run_sums) / chi2)), 1.0)


def background_absorption(jac: np.ndarray, free_paths: list[str]) -> dict[str, float]:
    """How much of each structural parameter the background could reproduce.

    For parameter i with Jacobian column jᵢ and the background columns
    spanning B, the multiple correlation

        R²ᵢ = 1 − ‖jᵢ − P_B jᵢ‖² / ‖jᵢ‖²          (P_B = orthogonal projector)

    is the fraction of jᵢ's effect the background can imitate.  R² → 1 means
    the two are degenerate: the background absorbs Bragg intensity, biasing
    ADPs up and scales (hence QPA fractions) down *while Rwp improves* — the
    documented failure mode of over-flexible backgrounds.  Anisotropic ADP
    DOFs (``…adp.k``) are screened alongside Biso: more displacement freedom
    means more of it available to soak up a background error.

    Pairwise ρ is the wrong statistic for this: with ~100 spline coefficients
    each individual |ρ| stays small (~0.2) while the block collectively
    absorbs ~50 % of the parameter (measured).  The projection sees the block.

    ``jac`` must be the **full** Jacobian including any P-spline penalty rows
    — those rows are what makes a stiff background unable to imitate a peak,
    and dropping them overstates the risk by ~5× (measured: R² 0.46 → 0.08 at
    λ = 10⁴).
    """
    bg = [k for k, p in enumerate(free_paths) if p.startswith("instrument.background.")]
    targets = [(k, p) for k, p in enumerate(free_paths)
               if p.endswith((".biso", ".scale", ".occ")) or ".adp." in p]
    return block_projection_r2(jac, bg, targets)


def _span_basis(jac: np.ndarray, cols: list[int]) -> np.ndarray:
    """Orthonormal basis (thin QR) for the span of the selected columns.

    The one QR both :func:`block_projection_r2` and
    :func:`one_parameter_gains` build their projections from — extracted so
    the two statistics cannot disagree about how a span is orthogonalised.
    """
    q, _ = np.linalg.qr(jac[:, cols])
    return q


def _off_span(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """``v`` minus its projection onto the orthonormal columns of ``q``.

    Works for a vector or a whole matrix of columns; ``q`` must come from
    :func:`_span_basis` (orthonormal), so the projector is ``q qᵀ``.
    """
    return v - q @ (q.T @ v)


def block_projection_r2(jac: np.ndarray, block: list[int],
                        targets: list[tuple[int, str]],
                        nuisance: list[int] | None = None) -> dict[str, float]:
    """R²ᵢ of each target column on the span of ``block``, keyed by path.

    The shared core of :func:`background_absorption` and
    :func:`roughness_absorption`: a thin QR of the block gives an orthonormal
    basis, and each target column is projected onto it.  Extracted rather than
    copied because the *statistic* is the reusable idea — "can this group of
    parameters, acting together, imitate that one?" — and a second hand-rolled
    copy would be free to drift from this one's clipping and degenerate-column
    handling.

    ``nuisance`` columns, when given, are projected out of the **whole**
    Jacobian first, making the result a *partial* R²: how much of the target
    the block can still explain once those parameters have taken whatever they
    can.  That matters whenever the nuisance directions are free anyway, and it
    is what makes the roughness number mean something (see
    :func:`roughness_absorption`).

    ``block``, ``nuisance`` and the indices in ``targets`` index columns of
    ``jac``.  A zero-norm target column is skipped rather than reported as 0 or
    1: it carries no information either way.
    """
    if not block or not targets:
        return {}
    jac = np.asarray(jac)
    if nuisance:
        jac = _off_span(_span_basis(jac, nuisance), jac)
    q = _span_basis(jac, block)
    out: dict[str, float] = {}
    for k, path in targets:
        j = jac[:, k]
        denom = float(j @ j)
        if denom <= 0.0:
            continue
        resid = _off_span(q, j)
        out[path] = float(np.clip(1.0 - float(resid @ resid) / denom, 0.0, 1.0))
    return out


def one_parameter_gains(jac: np.ndarray, resid: np.ndarray, block: list[int],
                        targets: list[tuple[int | list[int], str]],
                        ) -> dict[str, float]:
    """Predicted Δχ² from freeing each target at the current point, keyed.

    The Rao score test (Rao, 1948, Proc. Camb. Phil. Soc. 44, 50) applied to
    the Gauss-Newton linearisation: with the currently-free columns ``F``
    projected out of both the candidate column and the residual
    (Frisch & Waugh, 1933, Econometrica 1, 387; Lovell, 1963,
    J. Am. Statist. Assoc. 58, 993),

        j̃ = (I − P_F) J_j,   r̃ = (I − P_F) r,
        Δχ²_j = (j̃ᵀ r̃)² / (j̃ᵀ j̃)

    is exactly the drop in Σr² that one linearised solve of ``[F | j]`` would
    achieve over ``F`` alone — the property test asserts that identity against
    an explicit lstsq.  It is scale-invariant (rescaling the column by any
    dp/du cancels), so no per-parameter finite-difference step heuristics are
    needed (contrast Toby, 2024, J. Appl. Cryst. 57, 175, which probes ±δ
    because GSAS-II's analytic derivatives are locked inside Hessian
    assembly), and at a converged minimum jᵀr ≈ 0 makes every gain ≈ 0, so no
    sign-consistency test is needed either.  Under H₀ (the parameter's true
    gain is zero) the statistic is ~χ²₁·χ²_red, which is what makes a noise
    floor of a few times χ²_red meaningful.

    A target's first element may be a *list* of column indices: the joint
    gain ‖P_{span(J̃_G)} r̃‖² of freeing the whole group at once (~χ²_k·χ²_red
    under H₀), computed by least squares so a rank-deficient group — the
    usual reason it *is* a group — never overcounts.

    ``jac`` and ``resid`` are the solver's weighted rows — penalty and
    restraint rows included, for the same reason :func:`background_absorption`
    demands the full layout.  ``block`` indexes the currently-free columns;
    empty means nothing is projected out.  A zero-norm single column is
    skipped rather than scored (no leverage at this state, same convention as
    :func:`block_projection_r2`).  A column absorbed by span(F) *to within
    projection rounding* (‖j̃‖ ≤ √m·ε·‖j‖) scores exactly 0.0: past that
    floor j̃ is noise, and (j̃ᵀr̃)²/(j̃ᵀj̃) on noise returns a number of order
    ‖r̃‖² that looks like a measured gain (measured: 0.19 on a σ ≈ 1 synthetic
    residual, against a true 0).  The floor is fp diagnosis, not policy — the
    caller's absorption gate handles merely ill-separated columns.
    """
    jac = np.asarray(jac)
    r = np.asarray(resid, dtype=np.float64)
    q = _span_basis(jac, block) if block else None
    if q is not None:
        r = _off_span(q, r)
    noise2 = len(jac) * np.finfo(np.float64).eps ** 2

    out: dict[str, float] = {}
    for cols, key in targets:
        if isinstance(cols, (int, np.integer)):
            j = jac[:, cols]
            raw = float(j @ j)
            if raw <= 0.0:
                continue
            jt = _off_span(q, j) if q is not None else j
            denom = float(jt @ jt)
            if denom <= noise2 * raw:
                out[key] = 0.0
                continue
            num = float(jt @ r)
            out[key] = num * num / denom
        else:
            jg = jac[:, list(cols)]
            raw = np.einsum("ij,ij->j", jg, jg)
            if q is not None:
                jg = _off_span(q, jg)
            proj = np.einsum("ij,ij->j", jg, jg)
            jg = jg[:, proj > noise2 * raw]  # drop absorbed/dead members
            if jg.shape[1] == 0:
                out[key] = 0.0
                continue
            beta, *_ = np.linalg.lstsq(jg, r, rcond=None)
            fitted = jg @ beta
            out[key] = float(fitted @ fitted)
    return out


def _displacement_like(path: str) -> bool:
    """Displacement freedom a low-angle intensity depression can hide in."""
    return path.endswith(".biso") or ".adp." in path


def _roughness_nuisance(path: str) -> bool:
    """Directions that are free anyway and would swamp the comparison.

    Roughness is a *multiplicative* correction, so it is trivially "scale-like":
    projected onto a block containing the phase scale it scores R² ≈ 0.95
    whatever the data (measured), which says nothing except that both rescale
    the pattern.  The scale and the background refine in every plan regardless,
    so the question worth asking is what is left of roughness *after* they have
    taken whatever they can — a partial R².
    """
    return path.endswith(".scale") or path.startswith("instrument.background.")


def roughness_absorption(jac: np.ndarray, free_paths: list[str]
                         ) -> dict[str, float]:
    """Two-way degeneracy between surface roughness and the ADPs (WP-0502).

    Surface roughness depresses low-angle intensity, which is exactly the
    signature an inflated Biso/ADP can reproduce.  Pitschke, Hermann & Mattern
    (1993) Table III is the canonical demonstration of the consequence:
    uncorrected, YBa₂Cu₃O₇ refines to Biso = −1.9 … −2.5 Å², and only the
    correction brings it back to 0.28–0.45 Å².  The degeneracy is real physics,
    so the answer is to *measure* it, not to hide it behind a good-looking Rwp.

    The phase scale and the background are treated as **nuisance** directions
    and projected out of everything first (see :func:`_roughness_nuisance`);
    without that step every number here saturates near 0.96 and the guard is
    blind.  Both remaining directions are reported, because they answer
    different questions:

    * ``instrument.geometry.surface_roughness.*`` keys — how much of the
      roughness column the displacement block can still reproduce.  High ⇒
      *roughness is not identifiable from this data* and whatever it refined to
      is arbitrary.
    * ``…biso`` / ``…adp.k`` keys — how much of that parameter the roughness
      block can reproduce.  High ⇒ *the displacement parameter is hiding in
      roughness*, so its esd understates its true uncertainty.

    Measured on a synthetic large-cell lab pattern with scale, background, both
    Biso and both Suortti parameters free, varying only the low-angle cutoff:

    ======================  =====  =====  =====  =====  =====
    lowest fitted 2θ          7°    15°    20°    30°    45°
    reflections below 40°     20     18     16     10      0
    R²(roughness b)         0.06   0.62   0.91   0.93   0.95
    ======================  =====  =====  =====  =====  =====

    i.e. the statistic tracks the thing that actually determines
    identifiability — how many *reflections* fall in the range where the
    depression has a lever arm — rather than the nominal 2θ limit.

    As for :func:`background_absorption`, pairwise ρ is the wrong statistic (a
    block of many coefficients absorbs collectively while every individual |ρ|
    stays small) and ``jac`` must be the **full** Jacobian including any
    P-spline penalty rows.
    """
    rough = [k for k, p in enumerate(free_paths)
             if p.startswith("instrument.geometry.surface_roughness.")]
    disp = [(k, p) for k, p in enumerate(free_paths) if _displacement_like(p)]
    if not rough or not disp:
        return {}
    nuisance = [k for k, p in enumerate(free_paths) if _roughness_nuisance(p)]
    out = block_projection_r2(jac, [k for k, _ in disp],
                              [(k, free_paths[k]) for k in rough], nuisance)
    out.update(block_projection_r2(jac, rough, disp, nuisance))
    return out


def compute_statistics(y_obs: np.ndarray, y_calc: np.ndarray, sigma: np.ndarray,
                       n_free: int, y_background: np.ndarray | None = None) -> Statistics:
    y_obs = np.asarray(y_obs, dtype=np.float64)
    y_calc = np.asarray(y_calc, dtype=np.float64)
    w = 1.0 / np.asarray(sigma, dtype=np.float64) ** 2
    n = len(y_obs)
    diff = y_obs - y_calc

    swyo2 = float(w @ (y_obs * y_obs))
    swd2 = float(w @ (diff * diff))
    rp = float(np.abs(diff).sum() / np.abs(y_obs).sum())
    rwp = float(np.sqrt(swd2 / swyo2))
    rexp = float(np.sqrt(max(n - n_free, 1) / swyo2))
    chi2 = swd2 / max(n - n_free, 1)

    rwp_bs = None
    if y_background is not None:
        net = y_obs - y_background
        denom = float(w @ (net * net))
        if denom > 0:
            rwp_bs = float(np.sqrt(swd2 / denom))

    delta = np.sqrt(w) * diff
    dw = float(np.sum(np.diff(delta) ** 2) / np.sum(delta ** 2)) if n > 2 else None

    return Statistics(
        rwp=rwp, rp=rp, rexp=rexp, chi2=chi2, gof=rwp / rexp,
        rwp_background_subtracted=rwp_bs, durbin_watson=dw,
        esd_inflation=berar_lelann_factor(delta) if n > 2 else None,
        n_points=n, n_free_parameters=n_free,
    )


def structure_r_factors(i_obs: np.ndarray, i_calc: np.ndarray,
                        multiplicity: np.ndarray
                        ) -> tuple[float | None, float | None, int]:
    """(R_Bragg, R_F, n) from partitioned integrated intensities.

    McCusker, Von Dreele, Cox, Louër & Scardi (1999), *J. Appl. Cryst.* **32**,
    36-50, §11:

        R_B = Σ_hkl |I(obs) − I(calc)| / Σ_hkl |I(obs)|            (14)
        R_F = Σ_hkl ||F(obs)| − |F(calc)|| / Σ_hkl |F(obs)|        (13)

    with I_hkl = m·F²_hkl, m the multiplicity — so this takes the intensities
    in exactly those units (see
    :meth:`~rietx.model.forward.CompiledModel.structure_intensity_partition`,
    which produces them) and recovers |F| = √(I/m) per reflection.  The two
    tags they carry in a CIF are ``_refine_ls_R_I_factor`` (the dictionary's
    own definition names it "R_B or R_Bragg") and ``_refine_ls_R_factor_all``.

    Both indices are **biased towards the structural model** — I(obs) is the
    observed pattern partitioned in proportion to I(calc), so a wrong model
    both predicts and receives the intensity it expects.  The paper says so
    where it defines them ("this is, of course, biased towards the structural
    model, but it gives an indication of the reliability of the structure") and
    is equally clear on what they are for: monitoring the *improvement* of a
    structural model, never judging one in isolation.

    Both are also **unweighted** — eq (14) carries no w — which is what makes a
    trace phase's value incomparable with the major phase's: a reflection the
    weighted fit barely constrains counts as much as one that dominates it, and
    a minor phase's windows sit under the major phase's peaks, so the counts the
    major phase failed to describe are handed out too.  Measured on 11-BM NAC
    with its 1.35 wt % CaF₂ (WP-1069's handover): 0.052 against 0.385, the whole
    of the impurity's misfit in four reflections at I(obs)/I(calc) ≈ 2.2, every
    one of them under a strong NAC peak.  The weighted variant that answers this
    (Cox & Papoular, 1996, *Mater. Sci. Forum* **228-231**, 233) is not computed
    here.

    Reflections whose intensity could not be partitioned arrive as NaN and are
    dropped; ``n`` reports how many were summed.  Both values are ``None`` when
    no reflection survives or the denominator is zero — a fit with no
    scattering power to compare, not a perfect one.
    """
    i_obs = np.asarray(i_obs, dtype=np.float64)
    i_calc = np.asarray(i_calc, dtype=np.float64)
    mult = np.asarray(multiplicity, dtype=np.float64)
    keep = np.isfinite(i_obs) & np.isfinite(i_calc) & (mult > 0)
    if not np.any(keep):
        return None, None, 0
    io, ic, m = i_obs[keep], i_calc[keep], mult[keep]
    n = int(keep.sum())

    den_b = float(np.abs(io).sum())
    r_b = float(np.abs(io - ic).sum() / den_b) if den_b > 0 else None

    # |F| = √(I/m).  The partition clips the net counts at zero, so I(obs) ≥ 0
    # and the root is always real; I(calc) = m|F|² is non-negative by
    # construction.
    f_obs = np.sqrt(np.maximum(io, 0.0) / m)
    f_calc = np.sqrt(np.maximum(ic, 0.0) / m)
    den_f = float(f_obs.sum())
    r_f = float(np.abs(f_obs - f_calc).sum() / den_f) if den_f > 0 else None
    return r_b, r_f, n
