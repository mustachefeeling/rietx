"""Readers for *refinement project* files, as distinct from pattern readers.

`io.readers` answers "what did the diffractometer record"; this package answers
"what model did someone already fit to it". A solved project carries the phases,
the instrument and the converged figures of merit, which makes it the cheapest
source of a validated reference for testing.

One module per format, mirroring `io/`'s organising rule: a format's
specification citation, its parser, its refusals and its licence fence are one
fact each, and several fences in one file drift.
"""

from .fullprof import (
    FullProfPcrError,
    read_fullprof_pcr,
    structure_from_fullprof_pcr,
)
from .topas import TopasInpError, read_topas_inp

# The build entry point is named per format — ``structure_from_fullprof_pcr``,
# the shape of ``crystallography.cif.structure_from_cif`` — rather than a bare
# ``to_structure``. A sibling reader lands its own ``structure_from_<format>``
# beside it, so one package name never binds two different functions (which a
# bare ``to_structure`` on each would do, the second import silently winning).
__all__ = [
    "read_topas_inp", "TopasInpError",
    "read_fullprof_pcr", "structure_from_fullprof_pcr", "FullProfPcrError",
]
