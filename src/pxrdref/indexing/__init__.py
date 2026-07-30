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
"""

from .ambiguity import ambiguity_partners, derivative_cells, hnf_matrices
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

__all__ = [
    "BravaisScreen",
    "CandidateFit",
    "Detection",
    "PeakGroup",
    "ReducedCell",
    "af_from_cell",
    "ambiguity_partners",
    "assess_peak_list",
    "borda_scores",
    "bravais_screen",
    "cell_from_af",
    "conventional_cell",
    "derivative_cells",
    "design_matrix",
    "detect_peaks",
    "f_n",
    "fit_group",
    "fit_shift_model",
    "fom_panel",
    "fom_panel_disagrees",
    "hnf_matrices",
    "indexed_fraction",
    "lattice_group",
    "m20",
    "metric_basis",
    "pick_peaks",
    "predicted_seen_fraction",
    "reduce_cell",
    "refine_candidate",
    "same_lattice",
    "sigma_effective",
    "template_collinearity",
    "volume_envelope",
]
