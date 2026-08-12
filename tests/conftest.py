"""Suite-wide hygiene and the fixtures that share an expensive refinement.

Three things live here, in the order they have to happen:

1. **Headless matplotlib.**  Every test refinement writes obs/calc/diff PNGs
   (CLAUDE.md's Tests convention), so ``MPLBACKEND=Agg`` is set before anything
   can import pyplot and pick an interactive backend.
2. **A jax persistent compile cache.**  The backend files are jit-compile
   bound, not arithmetic bound; jax keys its on-disk cache by a content hash of
   the computation, so it is safe to share across processes (and across xdist
   workers).  A miss costs exactly what today's run costs.  ``rm -rf
   tests/.jax_cache`` is a clean reset.
3. **Figure autoclose.**  ``result.plot()`` hands back a live figure; most
   plotting tests never close theirs.  The autouse fixture below closes them
   *only* if pyplot was imported, so the ~700 tests that never plot do not pay
   an import.

Shared expensive results (``sample1_results``, ``srm660c_baseline``) are
session-scoped: they exist because several acceptance modules were re-deriving
the *identical* fit.  A consumer must carry the matching
``@pytest.mark.xdist_group`` or a second xdist worker silently recomputes the
whole fixture — see each fixture's docstring for the group name.

The builders those fixtures call stay in their own modules on purpose:
``tests/test_compare_ui.py`` asserts the comparison UI's standards against
their locations field by field, so moving or renaming one breaks that check.
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("JAX_COMPILATION_CACHE_DIR",
                      str(Path(__file__).parent / ".jax_cache"))


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    if "matplotlib.pyplot" in sys.modules:
        import matplotlib.pyplot as plt

        plt.close("all")


@pytest.fixture(scope="session")
def sample1_results():
    """The eight IUCr round-robin sample-1 mixtures (cpd-1a..h), fitted once
    under the v0.3 QPA protocol.

    ``test_acceptance_sequential``'s unchained baseline was an exact
    re-derivation of this — same phases, instrument, ``seed_scales`` and
    ``qpa_plan()`` — so the two suites share one set of fits.  History
    recording and the per-sample plots come from the QPA suite's ``_fit``;
    history is record-only and changes no value.

    **Consumers must carry** ``@pytest.mark.xdist_group("qpa-sample1")``, or a
    second worker recomputes all eight refinements.
    """
    from tests.test_acceptance_qpa_roundrobin import (
        SAMPLE1,
        _fit,
        _require_data,
        corundum_phase,
        fluorite_phase,
        qpa_plan,
        zincite_phase,
    )

    _require_data()
    out = {}
    for sample in SAMPLE1:
        _, result = _fit(sample, [corundum_phase(), zincite_phase(),
                                  fluorite_phase()], plan=qpa_plan())
        out[sample] = result
    return out


@pytest.fixture(scope="session")
def srm660c_baseline():
    """``(data, ref, result)`` for the NIST SRM 660c protocol, fitted once.

    Three suites were running this identical refinement — the acceptance
    itself, the dispersion-off half of ``test_acceptance_dispersion``'s
    ``srm660c_pair``, and the numpy reference of the jax end-to-end test.  All
    three built it from ``build_srm_inputs()`` + ``_nist_calibrated_plan()``,
    the second and third with ``history=False``, which records nothing and
    changes no value.

    ``ref`` is live: it still holds the compiled model, so ``ref.report()``
    works and ``ref.branch().run_stage(...)`` can warm-extend the plan with a
    further stage.  Do not ``fit()`` it again — branch first.

    **Consumers must carry** ``@pytest.mark.xdist_group("srm660c")``.
    """
    import anatase as pr
    from tests.test_acceptance_srm660c import (
        _nist_calibrated_plan,
        build_srm_inputs,
    )

    data, structure, instrument = build_srm_inputs()
    ref = pr.Refinement(structure, instrument)
    result = ref.fit(data, plan=_nist_calibrated_plan())
    return data, ref, result
