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

from .instrument import _LEGACY_COMPONENT_FIELD

#: Where a stored document is read and this repair is applied.  Listed so a
#: fourth read point is an edit here rather than a silent gap; a reader that
#: does not appear in this tuple does not migrate.
READ_POINTS: tuple[str, ...] = (
    "rietx.project.Project.open",
    "rietx.history.store.read_records",
    "rietx.gui.textdoc.parse",
)

#: ``(old, new)`` textual repairs, longest-first so no rule can eat another's
#: prefix.  Both entries are anchored on ``instrument.`` or on a JSON key
#: boundary: the bare word ``background_peaks`` never appears in a free-text
#: label or an annotation note in a form that either pattern matches, so a
#: false positive would need a caller to have written the dot-path itself into
#: prose, where rewriting it is the right answer anyway.
_PATH_REPAIRS: tuple[tuple[str, str], ...] = (
    (f"instrument.{_LEGACY_COMPONENT_FIELD}.", "instrument.extra_components."),
    (f'"{_LEGACY_COMPONENT_FIELD}":', '"extra_components":'),
)


def migrate_document_text(text: str) -> tuple[str, bool]:
    """Repair a stored document's text; return it with whether anything moved.

    Idempotent, and a no-op on anything written by this release: a document
    holding none of the legacy spellings is returned unchanged and ``False``,
    so a caller can apply this unconditionally on every read without paying for
    it and without a version check that would itself have to be maintained.
    """
    out = text
    for old, new in _PATH_REPAIRS:
        out = out.replace(old, new)
    return out, out != text


def migrate_paths(paths: list[str]) -> list[str]:
    """The same repair for paths already parsed out of a document.

    For a caller holding a list of dot-paths or globs rather than the document
    they came from — a plan handed in by code that read a v1.2 project itself,
    for instance.  Same rules, so the two cannot disagree.
    """
    return [p.replace(f"instrument.{_LEGACY_COMPONENT_FIELD}.",
                      "instrument.extra_components.")
            .replace(f"instrument.{_LEGACY_COMPONENT_FIELD}",
                     "instrument.extra_components")
            for p in paths]
