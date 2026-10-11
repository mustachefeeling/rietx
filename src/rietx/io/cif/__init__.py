"""The CIF writer's shared parts (WP-1319, issue #756 § 1).

One package for what every CIF this build writes has in common: the tag
registry (:mod:`.registry`), and in later chunks the number rule and the
structure block.  The readers (``structure_from_cif``, ``read_pdcif``, the
magCIF reader) stay in ``crystallography/`` and ``io/formats/``.
"""
