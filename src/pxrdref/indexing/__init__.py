"""Unit-cell determination from a powder pattern, and the peak picking it needs.

WP-1018 landed the first half: :func:`pick_peaks` turns a pattern into a
:class:`pxrdref.schemas.indexing.PeakList` whose every line carries a *fitted*
position with an esd, so the engines that follow weight each line by what it
actually determines instead of sharing one global tolerance knob.

WP-1019 adds the gate in front of the engines: :func:`assess_peak_list` judges a
list fit to index or **abstains** with a reason, and :func:`fit_shift_model`
attributes a systematic 2θ shift to one of three physical causes — or reports
that the causes are not separable over the range measured, which is the same
refusal-to-guess the FitReport makes one rank down.

WP-1020 adds everything the three search engines share and nothing that searches:
the Q-space quadratic form and its symmetry-allowed subspaces
(:func:`metric_basis`), weighted candidate refinement with an optional shift
column (:func:`refine_candidate`), reduction and two-opinion Bravais
determination (:func:`reduce_cell`, :func:`bravais_screen`), the figure-of-merit
**panel** scored in both directions (:func:`fom_panel`), and geometrical-ambiguity
enumeration (:func:`ambiguity_partners`).  After this a cell can be scored,
reduced, classified and compared — there is still no engine.

WP-1021 adds the first engine and the surface the three of them share:
:func:`search_dichotomy` is an **exhaustive** branch-and-bound over the metric
domain, whose value next to two cheaper engines is the contrapositive — a
completed search that finds nothing has said that no cell of that symmetry within
the bounds fits the list.  :class:`SearchSpec` is the one option surface, the
registry (:func:`engine_names`) is what WP-1024's agent schema quotes live, and
``EngineResult.search_complete`` is what keeps a budgeted search from looking like
a negative result.

WP-1022 adds the second engine, :func:`search_trial_error`, which is the same
linearity used from the other end: it *assumes* the indices of a few base lines and
solves the metric exactly, with no tolerance in the solve at all.  Its failure mode
is a bad base line rather than a wide domain, which is what makes the two engines'
agreement evidence — and it raises ``INDEX_DOMINANT_ZONE`` from its own experience
when the base-line indices it is allowed cannot reach the lowest observed lines.

WP-1024 closes the loop with :func:`index_pattern`, the public entry point and a
peer of :func:`pxrdref.refine`.  It merges the engines' candidates as reduced
cells, ranks them on the whole figure-of-merit panel, enumerates geometrical
ambiguity, validates the survivors against the **whole profile** by a Le Bail fit
(:func:`validate_by_lebail`), and gates confidence on **agreement** between the
engines (:mod:`pxrdref.indexing.consensus`).  The rule the whole milestone is built
around is enforced by the return type rather than by documentation:
:class:`~pxrdref.schemas.indexing.IndexingResult` has no ``.cell``, and
``best_or_none()`` is the only way to one.
"""

from .ambiguity import ambiguity_partners, derivative_cells, hnf_matrices
from .consensus import (
    ConsensusOutcome,
    apply_gate,
    bravais_opinion,
    caveats_for,
    checked_indices,
    consensus,
    grade,
)
from .diagnostics import (
    candidate_diagnostics,
    index_diagnostics,
    peak_diagnostics,
    quality_diagnostics,
)
from .dichotomy import search_dichotomy
from .engines import (
    CENTRINGS,
    SYSTEM_ORDER,
    Budget,
    EngineCandidate,
    EngineResult,
    SearchSpec,
    dedup_groups,
    engine_descriptions,
    engine_names,
    get_engine,
    predicted_reflection_count,
    rank_candidates,
    reflection_ceiling_ok,
    register_engine,
    to_cell_candidate,
)
from .fom import (
    borda_scores,
    f_n,
    fom_panel,
    fom_panel_disagrees,
    indexed_fraction,
    lattice_group,
    m20,
    predicted_seen_fraction,
)
from .peakfit import fit_group
from .peaks import Detection, PeakGroup, detect_peaks
from .pick import pick_peaks
from .qspace import (
    CandidateFit,
    af_from_cell,
    cell_from_af,
    design_matrix,
    metric_basis,
    refine_candidate,
    sigma_effective,
)
from .quality import (
    assess_peak_list,
    fit_shift_model,
    template_collinearity,
    volume_envelope,
)
from .reduce import (
    BravaisScreen,
    ReducedCell,
    bravais_screen,
    conventional_cell,
    reduce_cell,
    same_lattice,
)
from .trial_error import index_table, search_trial_error
from .workflow import (
    absent_reflections,
    index_pattern,
    structure_from_candidate,
    validate_by_lebail,
)

__all__ = [
    "CENTRINGS",
    "SYSTEM_ORDER",
    "BravaisScreen",
    "Budget",
    "CandidateFit",
    "ConsensusOutcome",
    "Detection",
    "EngineCandidate",
    "EngineResult",
    "PeakGroup",
    "ReducedCell",
    "SearchSpec",
    "absent_reflections",
    "af_from_cell",
    "ambiguity_partners",
    "apply_gate",
    "assess_peak_list",
    "borda_scores",
    "bravais_opinion",
    "bravais_screen",
    "candidate_diagnostics",
    "caveats_for",
    "cell_from_af",
    "checked_indices",
    "consensus",
    "conventional_cell",
    "dedup_groups",
    "derivative_cells",
    "design_matrix",
    "detect_peaks",
    "engine_descriptions",
    "engine_names",
    "f_n",
    "fit_group",
    "fit_shift_model",
    "fom_panel",
    "fom_panel_disagrees",
    "get_engine",
    "grade",
    "hnf_matrices",
    "index_diagnostics",
    "index_pattern",
    "indexed_fraction",
    "lattice_group",
    "m20",
    "metric_basis",
    "peak_diagnostics",
    "pick_peaks",
    "predicted_reflection_count",
    "predicted_seen_fraction",
    "quality_diagnostics",
    "rank_candidates",
    "reduce_cell",
    "reflection_ceiling_ok",
    "refine_candidate",
    "register_engine",
    "same_lattice",
    "index_table",
    "search_dichotomy",
    "search_trial_error",
    "sigma_effective",
    "structure_from_candidate",
    "template_collinearity",
    "to_cell_candidate",
    "validate_by_lebail",
    "volume_envelope",
]
