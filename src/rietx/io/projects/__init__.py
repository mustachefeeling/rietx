"""Readers for *refinement project* files, as distinct from pattern readers.

`io.readers` answers "what did the diffractometer record"; this package answers
"what model did someone already fit to it". A solved project carries the phases,
the instrument and the converged figures of merit, which makes it the cheapest
source of a validated reference for testing.

One module per format, mirroring `io/`'s organising rule.
"""

from .topas import TopasInpError, read_topas_inp, structure_from_topas_inp

__all__ = ["read_topas_inp", "structure_from_topas_inp", "TopasInpError"]
