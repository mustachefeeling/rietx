"""Structure solution from a verified cell (WP-1515; structure-solution), built in chunks.

Only :mod:`~rietx.solve.cost` (WP-1902) exists so far: the whole-profile χ² at a frozen
profile, written as a quadratic form in the per-reflection |F|².  Nothing here
is exported from :mod:`rietx`; the package becomes public, as a provisional
module, with the entry point that returns candidates.
"""
