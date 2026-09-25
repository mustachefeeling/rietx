"""The ``lab6_capillary`` compare standard as a GUI project, for the pilot's 132 992-channel runs.

``rietx.examples.build_example`` builds only what the wheel carries, and
``11BM_LaB6_660a.fxye`` is test data. This does what it does from
``tests/data``. Usage, from the repository root:

    .venv/bin/python docs/wp/1461-uplot-spike/make_lab6.py <parent dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from rietx.project import Project
from rietx.viz.compare import STANDARDS

DATA = Path(__file__).resolve().parents[3] / "tests" / "data"

std = next(s for s in STANDARDS if s.key == "lab6_capillary")
inputs = std.build(DATA)
project = Project.create(
    Path(sys.argv[1]) / "lab6_capillary.rex", pattern=DATA / std.pattern,
    structure=inputs.structure, instrument=inputs.instrument, plan=inputs.plan,
    two_theta_limits=inputs.two_theta_limits,
    excluded_regions=list(inputs.data.excluded_regions) or None,
    reader_options=dict(std.reader_options) or None)
print(project.path)
