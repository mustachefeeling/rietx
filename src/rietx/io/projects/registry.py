"""The model-format registry: which project readers exist, and the one door in.

``PATTERN_FORMATS`` answers "what did the diffractometer record"; this registry
answers "what model did someone already fit to it".  They are deliberately two
registries and not one arm of a third, for the reason
:class:`~rietx.io.formats.base.PatternFormat` gives its own existence: the
*answer's shape* differs.  A pattern reader returns a
:class:`~rietx.schemas.PatternData` and a project's ``DataRef`` records which
reader claimed the file so re-opening reproduces the reader call; a project
reader returns a whole solved model and nothing re-opens it that way.

**What the registry governs, and what it does not** (WP-1118, decided
2026-09-13).  A *project format* is a file stating someone else's **refinement**
— its phases, its instrument and, the part nobody can reconstruct from a CIF
plus a pattern, its refine flags.  Three readers in this build read a foreign
file and are *not* here, each for a stated reason:

- :func:`~rietx.io.instrument_profile.read_gsas_prm` reads a GSAS-I ``.prm``,
  which carries a machine and no model at all — no phases, no sites, no fitted
  numbers.  It is the same kind of thing as
  :func:`~rietx.io.instrument_profile.load_instrument_profile`, which is where
  it lives, and admitting it here would make every field this registry declares
  about a model empty on one member.
- :func:`~rietx.io.recipe.read_recipe` reads a PowderLine recipe, which *is* a
  refinement but carries its whole pattern inline and resolves to a
  :class:`~rietx.io.recipe.Recipe` that is ready to fit.  It is a
  build-wide feature (``capabilities().features["powderline_recipe"]``), not a
  format someone hands you to translate.
- The pattern readers under ``io/formats/``, which are the other registry.

So every member here has the same shape, and the shape is honest about what it
does not know: the reader returns **what the file states** (``TopasModel``,
``FullProfModel`` — seeded with nothing, a value the file omitted arriving as
``None``), and a separate conversion builds a :class:`~rietx.schemas.Structure`
from it.  That two-step is not ceremony.  A file states more than a
``Structure`` can hold (the run's own Rwp, the data file it points at, a
magnetic phase this package cannot model), and collapsing the two would either
discard those or invent fields for them.

**Dispatch is on content**, as ``io/CLAUDE.md`` § Dispatch requires of the
pattern readers and for the same reason: a suffix is a convention, not a fact.
``.inp`` in particular is written by several unrelated programs, so a reader
that claimed it by name would return a plausible wrong model for an Abaqus deck.

**The order is behaviour.**  Strongest evidence first, exactly as
``PATTERN_FORMATS`` does.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ..formats.base import HEAD_BYTES, head
from . import fullprof, topas

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ...schemas import Diagnostic, Structure

#: How much of a ``.inp`` a sniff may read.  Bounded for ``head()``'s reason (an
#: O(N) decode per dispatch) but larger than the pattern readers' ``HEAD_BYTES``,
#: because the evidence differs in *kind*: a pattern format and a ``.pcr`` are
#: recognised by a first line, while a ``.inp`` has no required opening at all
#: and its first block opener sits behind whatever macro-and-comment preamble
#: the author wrote.  Every format that can be claimed on a first line uses
#: ``HEAD_BYTES``; this budget is asked for by name, once, and the reason is the
#: format's grammar rather than a value that looked safe.
INP_SNIFF_BYTES = 65_536


@dataclass(frozen=True)
class ProjectFormat:
    """One foreign refinement format this build reads, and how it is recognised.

    A registry rather than a chain of imports because three consumers need the
    *same* facts and each would otherwise restate them: the dispatch in
    :func:`identify_project_format`, ``capabilities()`` (which must say what
    this build can actually open — WP-1007's rule, and its meta-test fails on a
    member missing from its arm), and the agent skill's routing row, which
    names the situation and lists the formats.
    """

    #: registry key, and what ``capabilities()`` publishes
    name: str
    #: what a person calls it
    title: str
    #: conventional suffixes — informational, never dispatch
    extensions: tuple[str, ...]
    #: how the format is recognised, in words a UI can show
    sniff: str
    #: what the file carries *beyond* a structure, in words.  The honest
    #: alternative to a union answer with optional fields: a client reads this
    #: to know what to ask for rather than reading ``None`` and guessing
    #: whether the file was silent or the reader failed
    carries: tuple[str, ...]
    #: **where this format's repairs are reported.**  A real per-format
    #: difference, not an accident to be papered over: the ``.inp`` reader
    #: normalises species and translates an origin suffix while parsing, so its
    #: channel is at read; the ``.pcr`` reader's four repairs all happen while
    #: converting codewords into a ``Structure``, so its channel is at build.
    #: Pinned against the real signatures by meta-test, so a reader that grows
    #: or loses the keyword cannot leave this claiming otherwise
    reports_at: Literal["read", "build"]
    matches: Callable[[Path], bool]
    #: the format's own reader — returns what the file states
    read: Callable[..., Any]
    #: the format's own conversion to a :class:`~rietx.schemas.Structure`
    to_structure: Callable[..., Structure]
    #: why this format is recognised **in order to be refused**, or ``None`` for
    #: one that reads.  One field rather than a side table, so an entry says for
    #: itself which it is — ``PatternFormat.refuses``' reasoning, and the same
    #: filtering applies wherever a list of what the build *opens* is shown
    refuses: str | None = None


@dataclass(frozen=True)
class ProjectModel:
    """What a foreign refinement file stated, and which format stated it.

    The one type :func:`read_project_model` answers with, and deliberately
    **not** a union of every format's fields with blanks where a file was
    silent: a blank reads as an answer, and a caller cannot tell "this file
    carried none" from "the reader found none" (WP-1076's defaulted-lie trap).
    Instead this names the format and hands on the format's own model
    untouched, so every field a caller reads is one that format really has.

        model = rx.read_project_model("refined.pcr")
        model.format.name          # 'fullprof_pcr'
        model.stated.chi2          # the run's own figure, this format's field
        structure = model.to_structure()
    """

    format: ProjectFormat
    path: Path
    #: the format's own model — ``TopasModel``, ``FullProfModel``.  Named for
    #: what it is: what the file *stated*, before any conversion
    stated: Any

    def to_structure(self, *, diagnostics: list[Diagnostic] | None = None,
                     **options: Any) -> Structure:
        """Build a :class:`~rietx.schemas.Structure` from what the file stated.

        ``options`` are the format's own conversion keywords — ``dataset`` for a
        multi-dataset ``.inp``, ``nuclear_only`` for a ``.pcr`` with a magnetic
        phase — passed through, so an unknown one raises naming itself rather
        than being dropped.  They are not flattened into one vocabulary here:
        two formats' options that happen to share a name would not share a
        meaning, and a registry that pretended otherwise would be inventing the
        agreement.

        ``diagnostics`` reaches the format's channel wherever that channel is.
        A format reporting at read (``format.reports_at``) has already filled
        the list passed to :func:`read_project_model`; passing one here as well
        is harmless and collects both halves for a caller accumulating across
        several files.
        """
        if diagnostics is not None and self.format.reports_at == "build":
            options["diagnostics"] = diagnostics
        return self.format.to_structure(self.stated, **options)


def _matches_fullprof_pcr(path: Path) -> bool:
    """A ``.pcr`` opens with a ``COMM`` title line.

    The sniff and the parser agree by construction: ``read_fullprof_pcr``
    refuses any file whose first non-blank line is not ``COMM``, so a file this
    claims is one that reader will at least get past its own first check.  That
    is the strongest evidence any member of this registry has, which is why it
    is first in the order.
    """
    for line in head(path, HEAD_BYTES).text.splitlines():
        if stripped := line.strip():
            return stripped.upper().startswith("COMM")
    return False


#: Block openers and top-level directives that are TOPAS's and nobody else's,
#: anchored at the start of a line.  The openers are the grammar's
#: (``topas._BLOCK_OPENERS``, the Technical Reference § 5.1 phase tree) rather
#: than what an archive happens to contain — ``io/CLAUDE.md`` § Project readers'
#: first rule — with the top-level directives a phase-less ``.inp`` still
#: states, so a Pawley or indexing-only file is claimed too.  ``xdd`` follows
#: ``xdd_scr``/``xdd_sum`` for the alternation reason ``topas._BLOCK`` gives.
#: ``STR(`` is here although the reader refuses such a file **by name**: a
#: refusal naming the file is the answer, and declining to *recognise* it would
#: send the file to "no format claims this", which is the worse message.
_TOPAS_LINE = re.compile(
    r"^[ \t]*(?:str|hkl_Is|xo_Is|d_Is|xdd_scr|xdd_sum|xdd|fit_obj"
    r"|macro|prm|iters|continue_after_convergence)\b"
    r"|^[ \t]*STR[ \t]*\(", re.M)


def _matches_topas_inp(path: Path) -> bool:
    """A ``.inp`` is claimed on a line-start TOPAS keyword, never on its suffix.

    ``.inp`` is an extension several unrelated programs write, so the suffix
    cannot be the evidence — ``io/CLAUDE.md`` § Dispatch, and WP-1407's rule one
    rank up, that a file extension does not name a format here.

    Anchoring at line start is what keeps the test honest rather than merely
    cheap: every keyword below also occurs inside quoted paths and prose, and a
    file holding ``xdd "C:\\data\\str\\run.xy"`` states one opener and not two.
    Comments go first for the same reason — the reader's own
    :func:`~rietx.io.projects.topas.strip_comments` handles ``'`` to end of line
    *and* nesting ``/* */`` blocks, and a sniff that reimplemented either would
    be a second grammar to keep in step.
    """
    return bool(_TOPAS_LINE.search(
        topas.strip_comments(head(path, INP_SNIFF_BYTES).text)))


#: The registry, **ordered**, and the order is behaviour: the first format whose
#: ``matches`` returns True claims the file.  FullProf is first because its
#: evidence is a line the format *requires* and TOPAS's is a keyword anywhere in
#: the head, which is the weaker test — ``PATTERN_FORMATS``' "strongest evidence
#: first", applied to two members rather than sixteen.
PROJECT_FORMATS: tuple[ProjectFormat, ...] = (
        ProjectFormat(
            name="fullprof_pcr",
            title="FullProf .pcr",
            extensions=(".pcr",),
            sniff="a COMM title line, which the format requires first",
            carries=("phases", "sites", "refine flags and their ties",
                     "instrument resolution function", "the run's own chi2 "
                     "and per-phase R_Bragg", "the data file it points at"),
            reports_at="build",
            matches=_matches_fullprof_pcr,
            read=fullprof.read_fullprof_pcr,
            to_structure=fullprof.to_structure,
        ),
        ProjectFormat(
            name="topas_inp",
            title="TOPAS .inp",
            extensions=(".inp",),
            sniff="a TOPAS block opener or top-level directive at the start of "
                  "a line — never the suffix, which several unrelated programs "
                  "also write",
            carries=("phases", "sites", "refine flags", "the emission profile",
                     "the run's own Rwp and GoF", "the data files it points at"),
            reports_at="read",
            matches=_matches_topas_inp,
            read=topas.read_topas_inp,
            to_structure=topas.to_structure,
        ),
)


def identify_project_format(path: str | Path) -> ProjectFormat:
    """Which registered project format claims ``path`` — the dispatch, once.

    Raises ``ValueError`` naming the formats this build does read.  Saying
    **which** is the whole difference between a message and a traceback, and it
    is built from the registry rather than written out, so a format added
    tomorrow appears in it (``identify_format``'s reasoning, one registry over).
    """
    p = Path(path)
    for fmt in PROJECT_FORMATS:
        if fmt.matches(p):
            return fmt
    known = ", ".join(f"{f.title} [{', '.join(f.extensions)}]"
                      for f in PROJECT_FORMATS if f.refuses is None)
    raise ValueError(
        f"{p.name} is not a refinement file this build can read. "
        f"Supported: {known}. A powder *pattern* goes through read_pattern, a "
        f"GSAS-I instrument-parameter file through read_gsas_prm, and a "
        f"PowderLine recipe through read_recipe.")


def read_project_model(path: str | Path, *,
                       diagnostics: list[Diagnostic] | None = None) -> ProjectModel:
    """Read a refinement another program wrote, dispatching on *content*.

    The one door for "someone handed me a file and I do not know what wrote it".
    Returns what the file stated, tagged with the format that claimed it; call
    :meth:`ProjectModel.to_structure` for a :class:`~rietx.schemas.Structure`.

    ``diagnostics`` collects what the reader **repaired or assumed** — a rewritten
    species spelling, a translated origin suffix — the same opt-in channel
    :func:`~rietx.io.read_pattern` and
    :func:`~rietx.structure_from_cif` take.  Where a format reports at build
    rather than at read (:attr:`ProjectFormat.reports_at`), pass the list to
    :meth:`ProjectModel.to_structure` as well; passing it to both is harmless.

    A construct the reader cannot honour raises the format's own error — a
    ``ValueError`` naming the file and the line — never a bare parser
    exception, and never a half-built model.  That is ``io/CLAUDE.md``
    § Project readers' rule: a project reader refuses where a pattern reader
    would repair, because its output is a whole model and a caller cannot see
    which part of it is the file's.
    """
    p = Path(path)
    fmt = identify_project_format(p)
    if fmt.reports_at == "read":
        return ProjectModel(format=fmt, path=p,
                            stated=fmt.read(p, diagnostics=diagnostics))
    return ProjectModel(format=fmt, path=p, stated=fmt.read(p))
