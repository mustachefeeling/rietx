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

This file is also where results shared between acceptance modules will live.
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
