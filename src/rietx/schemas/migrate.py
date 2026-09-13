"""Read-side repairs for documents written by an earlier release.

**One authority, and it is textual on purpose.**  A dot-path is not confined to
one schema field: it is a value in a history node's ``free_paths``, a glob in a
saved plan's ``turn_on``, a key in a tie table, a row label in an ``.rxt``.
Enumerating the fields that may hold one is how a migration misses the fifth
place, so the repair is applied to the document *text* at the three points a
stored document is read, and each is named in :data:`READ_POINTS`.

**Why the paths matter more than the field.**  The two halves of the v1.2
``background_peaks`` rename fail differently.  A stored *value* under a name the
schema no longer has fails loudly, under ``extra="forbid"``, naming the field.
A stored *glob* under the old name loads clean and then matches nothing: the
stage runs, frees nothing, and the fit returns a plausible answer with a
declared hump silently unrefined.  This module exists for the second case.
:meth:`rietx.schemas.instrument.Instrument._migrate_v1_2_background_peaks`
handles the first.
"""

from __future__ import annotations

import re

from .instrument import _LEGACY_COMPONENT_FIELD

#: Where a stored document is read and this repair is applied.  Listed so a
#: fourth read point is an edit here rather than a silent gap; a reader that
#: does not appear in this tuple does not migrate.
READ_POINTS: tuple[str, ...] = (
    "rietx.project.Project.open",
    "rietx.history.store.read_records",
    "rietx.gui.textdoc.parse",
)

#: The legacy name as a whole word: not followed by a letter, digit or
#: underscore, so ``background_peaksish`` is left alone while every spelling
#: that actually occurs is caught.
#:
#: **One rule, matching the bare name rather than a prefixed path**, because the
#: name reaches a stored document in four shapes and anchoring on any one of
#: them misses the others:
#:
#: * ``"background_peaks":`` — the JSON key, in a project or a history node;
#: * ``instrument.background_peaks.0.fwhm`` — a dot-path in ``free_paths``;
#: * ``background_peaks.0.fwhm`` — the same row in an ``.rxt``, which renders
#:   each block with its own prefix stripped (``textdoc._render_block``), so the
#:   ``instrument.`` is simply not there;
#: * ``instrument.background_peaks*`` — a glob a caller wrote without the dot,
#:   which fnmatch accepts and a dot-anchored rule would skip.
#:
#: An earlier version of this module anchored on ``instrument.`` and silently
#: missed the third, which is the same class of gap the module exists to close,
#: reintroduced inside it.
_LEGACY_NAME = re.compile(rf"\b{_LEGACY_COMPONENT_FIELD}\b")


def migrate_document_text(text: str) -> tuple[str, bool]:
    """Repair a stored document's text; return it with whether anything moved.

    **The one authority.**  There is deliberately no second entry point taking
    already-parsed paths: two functions applying "the same" rules are two
    functions that can disagree, and the disagreement would be silent in
    exactly the way this module was written to prevent.  A caller holding
    parsed paths passes them through this.

    Idempotent, and a no-op on anything written by this release: a document
    holding none of the legacy spellings is returned unchanged and ``False``,
    so a caller can apply it unconditionally on every read without paying for
    it and without a version check that would itself have to be maintained.
    """
    out = _LEGACY_NAME.sub("extra_components", text)
    return out, out != text
