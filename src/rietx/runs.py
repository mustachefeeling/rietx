"""Finding and reading refinement runs on disk — the reader half of
``rietx watch`` (WP-1401).

A *run* is a directory holding an event log. :class:`~rietx.viz.live.LiveSession`
writes one, and so does every GUI project under its ``live/``. This module
discovers them, says whether each is still being written, and tails its log from
a byte offset. :mod:`rietx.watch` is transport over it, the split
``gui/server.py`` already declares for itself.

**The reader constructs nothing.** No ``Project.open``, which appends a head
annotation and is why there is no read-only way to open a project; no
``Refinement``; no ``read_pattern``. Everything a reader needs, a writer
captured. This is a rule and not a preference: a viewer that constructs a
project mutates what it is looking at.

**This module writes nothing at all.** ``meta.json`` and ``run.lock`` are
WP-1403's to write, and no file in the tree carries either today. Every one is
optional here, and a directory with neither resolves to a *legacy* run,
synthesized from its log's mtime. That is what every run directory in the tree
is right now, and it is what keeps them all visible forever.

The state of a run is not an event. ``history/events.py`` states that for one
process: a fit that raises emits no ``fit_end``, and ``EventKind`` is closed, so
a run's status travels beside the stream. Across a process boundary the same
rule needs a channel the operating system maintains, because a dead writer
writes nothing — see :func:`liveness_of`.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict

from ._about import LIVE_DIR_NAME, PROJECT_SUFFIX
from .schemas.common import Base

#: The log every run has, and the only file this module needs to find one.
#: Written by :class:`~rietx.history.events.EventStream` (append) and truncated
#: by :class:`~rietx.viz.live.LiveSession` on construction.
EVENTS_FILE = "events.jsonl"

#: Per-stage progress. Written by ``LiveSession.write_snapshot`` today, which
#: records ``stage``/``rwp``/``gof``/``chi2``/``n_free`` and **no** ``state``.
STATUS_FILE = "status.json"

#: The run's own description of itself. **Nothing writes this yet** — WP-1403
#: does. Absent everywhere today, which is what makes a run *legacy*.
META_FILE = "meta.json"

#: Held flock'd by the writing process for its life. **Nothing writes this
#: yet** — WP-1403 does. See :func:`liveness_of` for why a held lock is the
#: liveness channel and a pid is only the fallback.
LOCK_FILE = "run.lock"

#: The plotly page ``LiveSession.write_snapshot`` rewrites per stage. Not read
#: here; the run row reports whether it exists so a client can offer the iframe.
SNAPSHOT_FILE = "fit.html"

#: Directory names the walk never descends. Cheap to extend; each is a tree
#: that cannot hold a run and can hold a great many files.
PRUNE_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__",
                        "_build", "dist", "build", ".mypy_cache",
                        ".pytest_cache", ".ruff_cache", ".tox", "site-packages",
                        ".claude"})

#: How deep :func:`discover` walks below its root, and how many runs it returns.
#: Both are bounds on a web page's poll, not opinions about a tree's shape.
MAX_DEPTH = 8
MAX_RUNS = 500

#: States a writer declares for itself. ``running`` is the only non-terminal
#: one; :data:`TERMINAL_STATES` is the rest. An **open** vocabulary, the way a
#: ``GuardFinding.code`` is: :attr:`RunStatus.state` is typed ``str`` so a
#: newer writer's member is read rather than refused, and a value not named
#: here falls through :func:`liveness_of` to the lock and the pid.
RUN_STATES = frozenset({"running", "done", "failed", "cancelled"})
TERMINAL_STATES = frozenset({"done", "failed", "cancelled"})

#: What :func:`liveness_of` answers. ``abandoned`` is a third answer and not a
#: rounding of the other two: the writer said it was running and no longer
#: holds its lock. ``unknown`` is a claim we cannot check, which is not the
#: same as a claim that nothing is happening.
LivenessState = Literal["running", "done", "failed", "cancelled", "abandoned",
                        "unknown"]


class _ReaderBase(Base):
    """A schema read off disk, never written by this package's reader.

    ``extra="allow"`` rather than the house ``extra="forbid"``, for the reason
    ``EventRecord.data`` is an open dict: a run directory outlives the version
    that wrote it, so a reader that refuses an unknown key refuses a newer
    writer's file outright. Forbidding extras is right where *this* package is
    the writer and a typo should be loud. Here it would make every future field
    a breaking change for every older reader.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True,
                              ser_json_inf_nan="strings")


class RunMeta(_ReaderBase):
    """``meta.json`` — what a run says about itself.

    **Nothing writes this file today**; WP-1403 does, and every field below is
    optional because of it. A run without one is legacy, and :func:`discover`
    synthesizes what it can from the log's mtime.
    """

    #: Human label for the run row. WP-1403's writer.
    label: str | None = None
    #: Unix time the run started. WP-1403's writer. Falls back to the event
    #: log's mtime for a legacy run.
    created: float | None = None
    #: The package version that wrote the run. WP-1403's writer.
    version: str | None = None
    #: Where the fit was launched, for a human reading a list of runs.
    cwd: str | None = None
    #: How it was launched. WP-1403's writer.
    command: str | None = None


class RunStatus(_ReaderBase):
    """``status.json`` — the writer's last word on progress and state.

    The first five fields are what ``LiveSession.write_snapshot`` writes today,
    once per stage. The rest are WP-1403's and absent from every file in the
    tree.

    :attr:`state` has **no substantive default**. A defaulted ``"running"``
    would be WP-1076's field whose empty state reads as an answer, and this one
    would read as an answer about a process that may have died months ago.
    ``None`` is the absence of a claim, and :func:`liveness_of` turns it into
    ``unknown`` rather than into ``running``.

    It is typed ``str`` and not a ``Literal`` for the reason ``extra`` is
    allowed above, and the reason matters more here than on any other field: a
    closed ``Literal`` makes a newer writer's member — a ``"paused"``, say —
    fail validation for the *whole file*, so the row would silently lose the
    stage and the Rwp it has no trouble reading. :data:`RUN_STATES` names the
    vocabulary; anything outside it reads as no claim.
    """

    # written per stage by viz.live.LiveSession.write_snapshot, today
    stage: str | None = None
    rwp: float | None = None
    gof: float | None = None
    chi2: float | None = None
    n_free: int | None = None

    # written by WP-1403's recorder; absent from every file in the tree today
    state: str | None = None
    pid: int | None = None
    host: str | None = None
    #: Unix time of the writer's last touch. **Reported, never decisive** —
    #: see :func:`liveness_of`.
    heartbeat: float | None = None


@dataclass(frozen=True)
class Liveness:
    """Whether a run is still being written, and what says so.

    :attr:`evidence` names the rule that fired, in words, because every answer
    here is an inference and the next reader deserves to know which one.
    :attr:`heartbeat_age` is reported and never decides: an alive process is
    evidence, a clock is not.
    """

    state: LivenessState
    evidence: str
    heartbeat_age: float | None = None


@dataclass(frozen=True)
class Run:
    """One discovered run directory.

    Built only from files a writer left behind. :attr:`legacy` means no
    ``meta.json``, so :attr:`created` came from the event log's mtime.
    """

    run_id: str
    path: Path
    label: str
    created: float
    legacy: bool
    size_bytes: int
    meta: RunMeta | None = None
    status: RunStatus | None = None
    has_snapshot: bool = False

    def as_dict(self) -> dict:
        """JSON-ready row, for :mod:`rietx.watch`'s routes."""
        return {
            "run_id": self.run_id,
            "path": str(self.path),
            "label": self.label,
            "created": self.created,
            "legacy": self.legacy,
            "size_bytes": self.size_bytes,
            "has_snapshot": self.has_snapshot,
            "meta": self.meta.model_dump(mode="json") if self.meta else None,
            "status": (self.status.model_dump(mode="json")
                       if self.status else None),
        }


def run_id_for(path: Path) -> str:
    """Stable, URL-safe id for a run directory.

    A digest of the resolved path rather than the path itself, for one reason
    that matters: an id is never turned back into a path. A route looks the id
    up in what :func:`discover` returned, so a request cannot name a directory
    the walk did not choose to offer, and ``..`` is not a thing an id can spell.
    """
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]


def _read_json(path: Path, model):
    """Parse one optional sidecar; a broken file reads as absent.

    A run row must survive a half-written or hand-edited sidecar, because a
    truncated ``status.json`` is exactly what a crash leaves behind, and losing
    the whole run from the list is a worse answer than losing its progress.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return model.model_validate_json(text)
    except Exception:
        return None


def _label_for(run_dir: Path, root: Path) -> str:
    """A human's name for the run.

    A GUI project's log lives at ``<name>.rex/live``, where "live" names every
    project's and so names none of them. The project directory is the label
    there.
    """
    if run_dir.parent.name.endswith(PROJECT_SUFFIX):
        return run_dir.parent.name
    try:
        rel = run_dir.relative_to(root)
    except ValueError:
        return run_dir.name
    return str(rel) if str(rel) != "." else run_dir.name


def read_run(run_dir: Path, *, root: Path | None = None) -> Run | None:
    """Read one run directory, or ``None`` if it holds no event log.

    Opens **exactly two files**: ``meta.json`` and ``status.json``. The event
    log is stat'd, never opened — :func:`tail_events` opens it, on demand, from
    an offset. That budget is asserted by ``tests/test_runs.py``, because a web
    page polls this.
    """
    run_dir = Path(run_dir)
    events = run_dir / EVENTS_FILE
    meta_path = run_dir / META_FILE
    try:
        stat = events.stat()
    except OSError:
        # no log: a run only if a writer left a meta.json behind
        if not meta_path.is_file():
            return None
        stat = None

    meta = _read_json(meta_path, RunMeta)
    status = _read_json(run_dir / STATUS_FILE, RunStatus)

    created = None
    if meta is not None and meta.created is not None:
        created = float(meta.created)
    elif stat is not None:
        created = float(stat.st_mtime)
    if created is None:
        created = time.time()

    label = (meta.label if meta is not None and meta.label
             else _label_for(run_dir, root if root is not None else run_dir))
    return Run(
        run_id=run_id_for(run_dir),
        path=run_dir,
        label=label,
        created=created,
        legacy=meta is None,
        size_bytes=stat.st_size if stat is not None else 0,
        meta=meta,
        status=status,
        has_snapshot=(run_dir / SNAPSHOT_FILE).is_file(),
    )


def _is_run_dir(entry_path: Path) -> bool:
    return ((entry_path / EVENTS_FILE).is_file()
            or (entry_path / META_FILE).is_file())


def discover(root: str | Path, *, max_depth: int = MAX_DEPTH,
             max_runs: int = MAX_RUNS) -> list[Run]:
    """Every run under ``root``, newest first.

    Bounded in depth and in count, never following a symlink, pruning the
    directories in :data:`PRUNE_DIRS`. A ``*.rex`` project is descended only as
    far as its ``live/``: the rest of a project is history and exports, and
    walking it is work that can find nothing.

    A run directory is not descended either. One run is one directory, and
    anything below it belongs to that run.
    """
    root = Path(root)
    out: list[Run] = []
    # (directory, depth), walked iteratively so a deep tree cannot recurse us
    # into a stack overflow and so the count bound can stop the walk dead.
    stack: list[tuple[Path, int]] = [(root, 0)]
    seen: set[tuple[int, int]] = set()

    if _is_run_dir(root):
        run = read_run(root, root=root)
        if run is not None:
            return [run]

    while stack and len(out) < max_runs:
        current, depth = stack.pop()
        try:
            # a symlinked directory can point back up the tree; identity, not
            # the path, is what closes the loop
            st = current.stat()
            key = (st.st_dev, st.st_ino)
            if key in seen:
                continue
            seen.add(key)
            entries = list(os.scandir(current))
        except OSError:
            continue

        for entry in entries:
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            if entry.name in PRUNE_DIRS or entry.name.startswith("."):
                continue
            child = Path(entry.path)

            if _is_run_dir(child):
                run = read_run(child, root=root)
                if run is not None:
                    out.append(run)
                    if len(out) >= max_runs:
                        break
                continue

            if child.name.endswith(PROJECT_SUFFIX):
                # descend a project exactly one level, to its live/
                live = child / LIVE_DIR_NAME
                if _is_run_dir(live):
                    run = read_run(live, root=root)
                    if run is not None:
                        out.append(run)
                        if len(out) >= max_runs:
                            break
                continue

            if depth < max_depth:
                stack.append((child, depth + 1))

    out.sort(key=lambda r: r.created, reverse=True)
    return out


def _probe_lock(path: Path) -> Literal["held", "free", "unavailable"]:
    """Is another process holding ``path`` flock'd?

    ``unavailable`` is a real third answer, and conflating it with ``free`` is
    the bug worth avoiding: no lock file means no writer ever made the claim,
    while a free lock file means a writer made it and is gone.

    The probe takes a **shared** lock, and the writer's is exclusive. Two
    readers must not see each other: an exclusive probe is itself a held lock
    for as long as it runs, so two ``rietx watch`` tabs — or two threads of one
    server answering ``/api/runs`` — would each report the other's probe as a
    live writer. A shared probe conflicts with the writer and with nobody else.

    Opened read-only for the same reason it is opened at all: ``flock`` needs
    an open descriptor and not a writable one, and asking for write access
    loses the answer on a lock file this user cannot write.
    """
    if not path.is_file():
        return "unavailable"
    try:
        import fcntl
    except ImportError:      # pragma: no cover - Windows
        return "unavailable"
    try:
        # binary: the file's bytes are never read, only its lock, so there is
        # no text here to have an encoding
        fh = open(path, "rb")
    except OSError:
        return "unavailable"
    try:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError:
            # somebody holds it exclusively; the kernel releases it however
            # they die
            return "held"
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        return "free"
    finally:
        fh.close()


def _pid_alive(pid: int) -> bool | None:
    """``None`` where the question cannot be answered rather than a guess.

    Subject to pid reuse, which is why this is the fallback and the held lock
    is the rule.
    """
    if pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True      # exists, owned by somebody else
    except OSError:
        return None
    return True


def liveness_of(run: Run, *, now: float | None = None) -> Liveness:
    """Whether ``run`` is still being written, by the first rule that answers.

    The order, and why each rung is where it is:

    1. **A terminal state wins.** The writer's own last word outranks every
       inference below it.
    2. **A different host reads unknown.** A claim we cannot check is not a
       claim, and a pid on another machine names one of our own processes.
    3. **The lock decides.** The writer holds ``run.lock`` flock'd for its
       life, and the kernel releases it however the writer dies, ``kill -9``
       included. Immune to pid reuse, and needing no heartbeat contract.
    4. **A free lock under a running status reads abandoned.** A third answer,
       not a rounding of the other two.
    5. **``os.kill(pid, 0)`` is the fallback** where no lock file exists.

    The heartbeat age is carried on the answer and never decides it. An alive
    process is evidence; a clock is not.

    Opens at most one file, the lock, and only when one exists. :func:`discover`
    deliberately does not call this, so a caller that wants a list pays two
    opens a run and no more.
    """
    now = time.time() if now is None else now
    st = run.status
    age = None
    if st is not None and st.heartbeat is not None:
        age = max(0.0, now - float(st.heartbeat))

    if st is not None and st.state in TERMINAL_STATES:
        return Liveness(st.state, f"the run recorded itself {st.state}", age)

    if st is not None and st.host and st.host != socket.gethostname():
        return Liveness("unknown", f"written on {st.host}, another host", age)

    probe = _probe_lock(run.path / LOCK_FILE)
    if probe == "held":
        return Liveness("running", "a process holds the run lock", age)
    if probe == "free":
        if st is not None and st.state == "running":
            return Liveness("abandoned",
                            "the status says running and the lock is free", age)
        return Liveness("unknown", "the run lock is free and no state was "
                                   "recorded", age)

    # no lock file, or no flock on this platform
    if st is not None and st.pid is not None:
        alive = _pid_alive(int(st.pid))
        if alive is True:
            return Liveness("running", f"pid {st.pid} is alive, with no lock "
                                       f"to check it against", age)
        if alive is False:
            return Liveness("abandoned", f"pid {st.pid} is gone", age)
    if run.legacy:
        return Liveness("unknown", "a legacy run: no meta.json, and no lock or "
                                   "pid to check", age)
    return Liveness("unknown", "nothing recorded a state, a lock or a pid", age)


@dataclass(frozen=True)
class EventTail:
    """A slice of an event log, and where to ask from next.

    :attr:`reset` means the log this came from is not the one the caller's
    offset counted into — truncated, or a different inode. A client clears its
    pane on it rather than renumbering silently, which is why it is a field and
    not an exception.
    """

    events: list[dict]
    offset: int
    inode: int | None
    reset: bool = False
    bad_lines: int = 0
    size: int = 0


def tail_events(path: str | Path, offset: int = 0, *, inode: int | None = None,
                max_bytes: int = 4 << 20) -> EventTail:
    """Read an event log from a byte offset, carrying a torn line forward.

    The whole-file refetch the page does today is replaced by this. A trailing
    fragment is left **unparsed** and the returned offset stops before it, so
    the next call sees the line whole: a writer flushes per event, but a flush
    is not an atomic write and the last line on disk can be half of one. This
    is defensive today and load-bearing from WP-1403 on, when writes become
    buffered.

    A bad line is counted, never raised on. One corrupt line in a log must not
    cost a viewer the other ten thousand.
    """
    path = Path(path)
    try:
        stat = path.stat()
    except OSError:
        return EventTail([], offset, None, reset=False)

    reset = False
    if offset > stat.st_size:
        reset = True                      # truncated under us
    if inode is not None and inode != stat.st_ino:
        reset = True                      # replaced under us
    start = 0 if reset else max(0, int(offset))

    try:
        with open(path, "rb") as fh:
            fh.seek(start)
            chunk = fh.read(max_bytes)
    except OSError:
        return EventTail([], offset, stat.st_ino, reset=reset,
                         size=stat.st_size)

    cut = chunk.rfind(b"\n")
    if cut == -1:
        # nothing complete yet; hold the offset where it was
        return EventTail([], start, stat.st_ino, reset=reset, size=stat.st_size)
    complete, _fragment = chunk[:cut + 1], chunk[cut + 1:]

    events: list[dict] = []
    bad = 0
    for raw in complete.split(b"\n"):
        if not raw.strip():
            continue
        try:
            events.append(json.loads(raw.decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            bad += 1
    return EventTail(events, start + cut + 1, stat.st_ino, reset=reset,
                     bad_lines=bad, size=stat.st_size)


def _format_table(runs: list[Run], root: Path) -> str:
    rows = [("STATE", "RUN", "STAGE", "RWP", "SIZE", "ID")]
    for run in runs:
        live = liveness_of(run)
        st = run.status
        rows.append((
            live.state,
            run.label,
            (st.stage if st and st.stage else "—"),
            (f"{st.rwp:.4f}" if st and st.rwp is not None else "—"),
            f"{run.size_bytes / 1024:.0f}k",
            run.run_id,
        ))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
             for row in rows]
    head = f"scanned {root}"
    tail = f"{len(runs)} run(s)" if runs else "no runs found"
    return "\n".join([head, "", *lines, "", tail])


def main(argv: list[str] | None = None) -> int:
    """``python -m rietx.runs [DIR]`` — the walk, without a browser."""
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]).resolve() if args else Path.cwd()
    runs = discover(root)
    print(_format_table(runs, root))
    return 0


if __name__ == "__main__":       # pragma: no cover - module entry point
    raise SystemExit(main())
