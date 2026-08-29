"""Score, gate, group and rank held parameters from one Jacobian (WP-1050).

The score is the Rao / Gauss-Newton one-parameter gain
(:func:`~rietx.optimize.statistics.one_parameter_gains`); both gates run
through :func:`~rietx.optimize.statistics.block_projection_r2` — absorption
of a candidate by the currently-free block directly, candidate-vs-candidate
ties on the free-block-projected columns.  This module sees only matrices,
paths and constants: enumerating candidates, seeding transform floors and
compiling the probe model are :meth:`rietx.refine.Refinement.suggest`'s
job, and the Layer-2 cross-reference arrives as already-built *objects*,
because ``strategy`` builds no ``report`` object and imports none at module
scope.

The single exception is a *number*: ΔBIC (WP-1305) is
:func:`rietx.report.layer2.delta_bic`, imported inside the call the way
``indexing/extinction.py`` reaches the same function, so the package keeps one
BIC formula instead of a second copy pinned to the first by a test.  Writing
``gain − n·ln(N)`` here would have been that copy *and* a weaker statement: it
is the exact form only where the probe's χ²/N is 1, and the noise floor one
gate over already refuses that assumption (``max(chi2_red, 1)``).
"""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ..optimize.statistics import (
    _off_span,
    _span_basis,
    block_projection_r2,
    one_parameter_gains,
)
from ..schemas.suggest import (
    SUGGEST_ABSORPTION_MAX,
    SUGGEST_GROUP_R2,
    SUGGEST_MIN_GAIN,
    CandidateGroup,
    ParameterCandidate,
    SuggestionResult,
)

#: Probe seeds, per family.  A floor candidate cannot be scored at its stored
#: value: a softplus column at p ≈ 0 comes out of the scalar-FD chain as
#: rounding noise (dp/du ≈ 1e-12 puts the chain's perturbation below the
#: model evaluation's own fp noise — and the gain statistic, being
#: scale-invariant, would amplify that noise to a measured-looking number), a
#: Stephens block at S ≡ 0 sits on √Σ's unbounded slope (an FD there returns
#: an h-dependent value, not a derivative), and Suortti roughness at b = 0 is
#: the *identity*, a column of exact zeros — for which 1e-3 is still a dead
#: correction, hence the measured 0.3 of ``_ROUGHNESS_STAGE``.  So those
#: columns are evaluated at the seed the corresponding stage would start its
#: solve from (the ``strategy/staged.py`` literals: ``seed=1e-3``, roughness
#: ``0.3``, ``strain_seed=1000.0``) and the candidate reports ``seeded=True``.
#: The seeds live in a **second** probe build whose only contribution is
#: those columns — never in the shared residual: measured on the layers
#: suite's truth fixture, seeding the shared state instead broadens every
#: peak, moves probe χ²_red from 1.01 to 7.1, and hands every width
#: parameter a spurious gain ≈ 3×10⁴ at a *converged* fit
#: (``Refinement.suggest`` implements the split and tells the same story).
SUGGEST_SEED_SOFTPLUS = 1e-3
SUGGEST_SEED_ROUGHNESS = 0.3
SUGGEST_SEED_STEPHENS = 1000.0


@dataclass(frozen=True)
class Candidate:
    """One held-but-refinable parameter as the caller enumerated it.

    ``index`` is the parameter's column in the probe Jacobian, ``dp_du`` the
    transform slope at the probe point (what converts the internal gradient
    to physical units — never zero, because a floor-dead candidate is seeded
    off the floor before the Jacobian is built and arrives here with
    ``seeded=True`` and its ``seed_value``).
    """

    path: str
    index: int
    dp_du: float
    seeded: bool = False
    seed_value: float | None = None


def _union_find_groups(n: int, linked: list[tuple[int, int]]) -> list[list[int]]:
    """Connected components over ``n`` items from pairwise links."""
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in linked:
        parent[find(a)] = find(b)
    comps: dict[int, list[int]] = {}
    for i in range(n):
        comps.setdefault(find(i), []).append(i)
    return list(comps.values())


def _matched_action_kind(path: str, actions: Sequence) -> str | None:
    """First (highest-confidence) action whose paths match this candidate.

    The two-way fnmatch mirrors :func:`rietx.report.apply_strategy_veto`:
    either side of the comparison may be the glob.
    """
    for action in actions:
        for glob in getattr(action, "parameter_paths", []):
            if fnmatch.fnmatchcase(glob, path) or fnmatch.fnmatchcase(path, glob):
                return str(action.kind)
    return None


def build_suggestion(jac: np.ndarray, resid: np.ndarray, free: list[int],
                     candidates: Sequence[Candidate], *, chi2_red: float,
                     top_n: int = 5, actions: Sequence = (),
                     ) -> SuggestionResult:
    """Rank ``candidates`` by predicted Δχ², gated so a tie is never a winner.

    ``jac``/``resid`` are the solver's weighted rows for the **combined**
    table (free ∪ candidates — penalty and restraint rows included, or
    absorption is overstated); ``free`` indexes the currently-free columns.
    ``actions`` are FitReport Layer-2 ``SuggestedAction``s (duck-typed:
    ``.kind`` and ``.parameter_paths``), already confidence-sorted, used only
    to annotate agreement between the two methods.
    """
    jac = np.asarray(jac)
    resid = np.asarray(resid, dtype=np.float64)
    targets = [(c.index, c.path) for c in candidates]
    gains = one_parameter_gains(jac, resid, free, targets)
    absorption = block_projection_r2(jac, free, targets) if free else {}
    skipped = [c.path for c in candidates if c.path not in gains]

    scored: list[tuple[Candidate, ParameterCandidate]] = []
    for c in candidates:
        if c.path not in gains:
            continue
        gradient = 2.0 * float(jac[:, c.index] @ resid) / c.dp_du
        scored.append((c, ParameterCandidate(
            path=c.path, gain=gains[c.path], gradient=gradient,
            absorption=absorption.get(c.path, 0.0), seeded=c.seeded,
            seed_value=c.seed_value,
            action_kind=_matched_action_kind(c.path, actions))))

    non_separable = [pc for _, pc in scored
                     if pc.absorption > SUGGEST_ABSORPTION_MAX]
    floor = SUGGEST_MIN_GAIN * max(chi2_red, 1.0)
    survivors = [(c, pc) for c, pc in scored
                 if pc.absorption <= SUGGEST_ABSORPTION_MAX and pc.gain > floor]

    # candidate-vs-candidate ties, measured on the free-block-projected
    # columns (one shared projection, then ρ² per pair through the same
    # block_projection_r2 every other collinearity statistic uses)
    proj = _off_span(_span_basis(jac, free), jac) if free else jac
    links: list[tuple[int, int]] = []
    for a in range(len(survivors)):
        ca = survivors[a][0]
        others = [(survivors[b][0].index, str(b)) for b in range(a + 1, len(survivors))]
        if not others:
            continue
        rho2 = block_projection_r2(proj, [ca.index], others)
        links += [(a, int(key)) for key, r2 in rho2.items()
                  if r2 > SUGGEST_GROUP_R2]

    # the restricted model's own weighted SSR and row count: what ΔBIC below
    # compares the predicted freed model against (the residual carries every
    # block — penalty and restraint rows included — because the gain does)
    chi2_state = float(resid @ resid)
    n_rows = len(resid)

    groups: list[CandidateGroup] = []
    for comp in _union_find_groups(len(survivors), links):
        members = sorted((survivors[i][1] for i in comp),
                         key=lambda pc: (-pc.gain, pc.path))
        if len(members) == 1:
            gain = members[0].gain
        else:
            cols = [survivors[i][0].index for i in comp]
            gain = one_parameter_gains(jac, resid, free, [(cols, "g")])["g"]
        groups.append(CandidateGroup(
            members=members, gain=gain, resolved=len(members) == 1,
            delta_bic=_predicted_delta_bic(gain, len(members),
                                           chi2_state, n_rows)))
    groups.sort(key=lambda g: (-g.gain, g.members[0].path))
    groups = groups[:top_n]

    return SuggestionResult(
        groups=groups, non_separable=non_separable,
        skipped=skipped, n_evaluated=len(scored), chi2_red=chi2_red,
        noise_floor=floor,
        summary=_summary(groups, floor, len(scored), len(non_separable),
                         len(skipped), n_rows))


def _predicted_delta_bic(gain: float, n_added: int, chi2_state: float,
                         n_rows: int) -> float:
    """Schwarz's ΔBIC for freeing ``n_added`` parameters, predicted not fitted.

    The package's one BIC form (:func:`rietx.report.layer2.delta_bic`,
    positive favouring the fuller model) evaluated at the Gauss-Newton answer:
    the freed model is predicted to reach ``chi2_state - gain``.  Imported
    inside the call — see this module's docstring on the one edge to
    ``report``.
    """
    from ..report.layer2 import delta_bic

    return delta_bic(chi2_state, chi2_state - gain, n_rows, n_added)


def _summary(groups: list[CandidateGroup], floor: float, n_evaluated: int,
             n_non_separable: int, n_skipped: int, n_rows: int) -> str:
    """One deterministic sentence a human or agent can quote.

    The sentence carries both numbers because they answer different questions
    and can disagree: ``Δχ²`` is the leverage that ranks, ΔBIC is whether the
    leverage pays for the parameter at this ``N`` (WP-1305).
    """
    tail = (f"{n_evaluated} candidate(s) evaluated, {n_non_separable} "
            f"non-separable from the free set, {n_skipped} without leverage; "
            f"noise floor {floor:.4g}")
    if not groups:
        return ("nothing clears the noise floor — the fit is converged for "
                f"every separable held parameter ({tail})")
    top = groups[0]
    if top.resolved:
        head = (f"free {top.members[0].path} next: predicted "
                f"Δχ² {top.gain:.4g}, ΔBIC {top.delta_bic:+.4g}")
        if top.members[0].action_kind:
            head += f" (Layer 2 agrees: {top.members[0].action_kind})"
    else:
        paths = ", ".join(pc.path for pc in top.members)
        head = (f"the data cannot separate {paths}: joint predicted "
                f"Δχ² {top.gain:.4g}, ΔBIC {top.delta_bic:+.4g} — free one, "
                "not on this evidence alone")
    if top.delta_bic <= 0.0:
        head += (f"; ΔBIC refuses it — the predicted gain does not pay for "
                 f"{len(top.members)} parameter(s) at N={n_rows}")
    return f"{head} ({tail})"
