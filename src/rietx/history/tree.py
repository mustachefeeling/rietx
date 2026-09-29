"""The refinement history DAG: immutable nodes, mutable named refs.

Hand-rolled parent pointers rather than a graph library — the dependency
budget is locked at numpy/scipy/pydantic/gemmi (docs/DESIGN.md), and the
operations needed here (lineage, children, leaves, best) are a few lines each
over a dict.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..schemas.common import (
    BARE_PARAMETER_ATTRS,
    Base,
    Diagnostic,
    Parameter,
    _InheritsDeclaredDefaults,
    declared_fills,
)
from ..schemas.history import (
    Annotation,
    HistoryNode,
    HistoryRecord,
    NodeAction,
    NodeMetrics,
    PlanSpec,
    RefinementState,
    TreeHeader,
)
from ..schemas.pattern import PatternData
from ..schemas.structure import Atom
from .store import append_record, fingerprint, read_records, write_records

HEAD = "head"

#: The version a header that never stamped one is read as: older than every
#: class's ``_declared_since``, which is what such a log is.
_UNSTAMPED_SCHEMA = "0.0"


def _schema_key(version: str) -> tuple[int, ...]:
    """``"0.9"`` < ``"0.17"``: schema versions compare as integers, never text."""
    return tuple(int(part) for part in version.split("."))


def _newest_declared_since() -> tuple[int, ...]:
    """The latest ``_declared_since`` of any class, read off the classes: a log
    written at or after it holds nothing to repair, so it is not walked."""
    newest, stack = (0,), list(_InheritsDeclaredDefaults.__subclasses__())
    while stack:
        cls = stack.pop()
        newest = max(newest, _schema_key(cls._declared_since))
        stack.extend(cls.__subclasses__())
    return newest


def _describe(attrs: dict) -> str:
    text = f"[{attrs['min']}, {attrs['max']}]"
    text += f" {attrs['unit']}" if attrs["unit"] else ", no unit"
    if attrs["transform"] != "identity":
        text += f", {attrs['transform']}"
    return text


def repair_declared_defaults(state: RefinementState, written: str) -> list[dict]:
    """Restore the declared range a caller's ``Parameter`` lost, in a state
    read from a document written at schema ``written``; return what moved.

    **The defect** (issue #204, the read half #209): until a class inherited
    (:class:`~rietx.schemas.common._InheritsDeclaredDefaults`, from its
    ``_declared_since``), a caller's ``Parameter(value=..., vary=...)`` for a
    field that declares a range got ``(-inf, inf)``, no unit and ``identity``,
    and ``model_dump`` wrote those out explicitly.  So such a document reloads
    with every key present, inherits nothing at construction, and refines
    unbounded again.  Fixed at construction for ``Atom`` by PR #206, for every
    other class by WP-1321; this is what reaches the documents already written.

    **The signature is a bare attribute in a document older than its class's
    inheritance**, per attribute and by :func:`declared_fills` — the same rule
    construction applies, with absence read as "holds the bare value" because
    serialization left no other trace.  Before ``_declared_since`` an explicit
    bare attribute and an omission were the same thing, so reading one as the
    other loses nothing a caller could have meant; from it on, an explicit
    ``min=-inf`` is a choice, and a document written then is left alone.  A
    bound that is merely *wider* than the declared one is never touched:
    WP-1311 made ``max=60`` on a hot specimen's ``biso`` the documented escape.

    **In the reader, with a diagnostic, never in a schema validator** (root
    CLAUDE.md: a silent correction is a reader's to make, because only the read
    path has a channel to say it did).  ``PreferredOrientation``'s silent
    floor repair is not the precedent: its licence is a pole feeding the solver
    NaNs, which a merely loose bound is not.

    **Bounds heal, values never move**: a stored value outside the declared
    range raises, naming the node, the path and both, exactly as a fresh
    construction would, because no value the defect produced there is a
    measurement to keep and choosing a replacement is the caller's.

    Mutates the ``Parameter`` objects of ``state`` in place, which are the
    reader's own (freshly parsed), and returns one record per repaired
    parameter: its dot-path, the atom label where there is one, the stored and
    the restored attributes, and the class's ``_declared_since``.
    """
    written_key = _schema_key(written)
    out: list[dict] = []

    def visit(obj: object, prefix: str, label: str | None) -> None:
        if isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                visit(item, f"{prefix}{i}.", label)
            return
        if not isinstance(obj, Base) or isinstance(obj, Parameter):
            return
        cls = type(obj)
        if isinstance(obj, Atom):
            label = obj.label  # the name a person knows the site by
        stale = (issubclass(cls, _InheritsDeclaredDefaults)
                 and written_key < _schema_key(cls._declared_since))
        for name, info in cls.model_fields.items():
            value = getattr(obj, name)
            if (stale and isinstance(value, Parameter)
                    and info.annotation is Parameter and info.default_factory is not None):
                _restore(value, info.default_factory(), f"{prefix}{name}", label,
                         cls._declared_since)
            else:
                visit(value, f"{prefix}{name}.", label)

    def _restore(param: Parameter, declared: Parameter, path: str,
                 label: str | None, since: str) -> None:
        present = {attr for attr, bare in BARE_PARAMETER_ATTRS.items()
                   if getattr(param, attr) != bare}
        fills = {attr: v for attr, v in declared_fills(declared, present).items()
                 if getattr(param, attr) != v}
        if not fills:
            return
        before = {attr: getattr(param, attr) for attr in BARE_PARAMETER_ATTRS}
        after = {**before, **fills}
        if not after["min"] <= param.value <= after["max"]:
            raise _Unrestorable(path, label, param.value, before, after, since)
        # min before max is always legal here: the old pair held the value and
        # the new pair does, so [new min, old max] holds it on the way through
        for attr in ("min", "max", "unit", "transform"):
            if attr in fills:
                setattr(param, attr, fills[attr])
        out.append({"path": path, "label": label, "before": before,
                    "after": after, "since": since})

    visit(state.structure, "", None)
    visit(state.instrument, "instrument.", None)
    return out


class _Unrestorable(ValueError):
    def __init__(self, path, label, value, before, after, since):
        self.where = path + (f" (atom {label})" if label else "")
        super().__init__(
            f"{self.where} = {value!r} is stored under {_describe(before)}, the "
            f"range a caller's own Parameter was left with before schema "
            f"{since} (issue #204), and the declared {_describe(after)} does "
            "not contain it, so the bound cannot be restored. The value is not "
            "a measurement to keep: correct it in the log, or read the log as "
            "stored with rietx.history.read_records")


def _repair_diagnostics(repairs: dict[tuple, list[str]]) -> list[Diagnostic]:
    notes = []
    for (path, label, before, after, since), nodes in repairs.items():
        before, after = dict(before), dict(after)
        bound = any(before[a] != after[a] for a in ("min", "max", "transform"))
        where = path + (f" (atom {label})" if label else "")
        span = nodes[0] if len(nodes) == 1 else f"{nodes[0]}…{nodes[-1]}"
        notes.append(Diagnostic(
            level="warning" if bound else "info",
            code="HISTORY_BOUNDS_RESTORED",
            message=(
                f"{where}: stored as {_describe(before)} — the range a "
                f"caller's own Parameter was left with before schema {since} "
                f"(issue #204) — and restored to the declared "
                f"{_describe(after)} in {len(nodes)} "
                f"node{'s' if len(nodes) != 1 else ''} ({span}). "
                "No value moved."),
            where=[path],
            suggestion=(
                "Nothing to do if the declared range is what you meant. A "
                "range of your own goes on the Parameter explicitly (e.g. "
                "max=60 for a hot specimen's biso), and wins.")))
    return notes


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class RefinementTree:
    """A record of every state a refinement passed through, and how.

    Nodes are append-only and never mutated in place except through
    :meth:`annotate`, which is itself recorded as an overlay.  ``refs`` maps
    names (``head`` and any user tags) to node ids.
    """

    def __init__(self, header: TreeHeader, *, path: str | Path | None = None):
        self.header = header
        self.path = Path(path) if path is not None else None
        self.nodes: dict[str, HistoryNode] = {}
        self.order: list[str] = []
        self.refs: dict[str, str] = {}

    # -- construction ---------------------------------------------------
    @classmethod
    def for_data(cls, data: PatternData, *, path: str | Path | None = None,
                 plan: Any = None, package_version: str = "") -> "RefinementTree":
        created = _utcnow()
        fp = fingerprint(data.two_theta, data.intensity)
        header = TreeHeader(
            tree_id=f"t{fp[:8]}",
            created_utc=created,
            data_fingerprint=fp,
            data_source=data.metadata.get("source_file", ""),
            n_points=len(data.two_theta),
            plan=PlanSpec.from_plan(plan) if plan is not None else None,
            package_version=package_version,
        )
        tree = cls(header, path=path)
        if tree.path is not None:
            append_record(tree.path, HistoryRecord(record="header", header=header))
        return tree

    @classmethod
    def load(cls, path: str | Path, *,
             diagnostics: list[Diagnostic] | None = None) -> "RefinementTree":
        """Rebuild a tree from its JSONL log.

        ``diagnostics``, when a list is passed, collects what the load
        **repaired** — the channel :func:`~rietx.io.readers.read_pattern` and
        :func:`~rietx.crystallography.cif.structure_from_cif` take, for the
        same reason: a reader may correct a document only where it can say that
        it did.  Today that is one repair, ``HISTORY_BOUNDS_RESTORED``: a
        caller's own ``Parameter`` that a release before its class inherited
        left unbounded (issue #204) gets its field's declared range back, one
        entry per parameter over every node that stored it
        (:func:`repair_declared_defaults`).  A stored value outside that range
        raises instead, naming the node.  :func:`~rietx.history.store.read_records`
        still reads such a log as stored.

        Records are applied **in file order**, replaying exactly what the
        in-memory tree did as each was appended: a node record advances HEAD
        (:meth:`add` does), an annotation's refs overlay whatever HEAD was when
        it was written.  File order is the only thing that says which of the two
        came last, and reading it wrongly cost both halves of "resume where the
        session left off" (WP-1005): nodes-then-annotations put HEAD at the node
        an old ``checkout`` had annotated rather than at the last node committed
        after it, and a log written by a plain ``fit`` — which appends nodes and
        no annotation at all — reloaded with **no HEAD**, so ``tree["head"]``
        raised and there was nothing to resume from.
        """
        header: TreeHeader | None = None
        pending: list[HistoryNode | Annotation] = []
        for rec in read_records(path):
            if rec.record == "header" and rec.header is not None:
                header = rec.header
            elif rec.record == "node" and rec.node is not None:
                pending.append(rec.node)
            elif rec.record == "annotation" and rec.annotation is not None:
                pending.append(rec.annotation)
        if header is None:
            raise ValueError(f"{path}: no header record; not a history log")

        # a header that never stamped its schema is older than any inheritance
        written = (header.schema_version if "schema_version" in header.model_fields_set
                   else _UNSTAMPED_SCHEMA)
        repairs: dict[tuple, list[str]] = {}
        stale = _schema_key(written) < _newest_declared_since()
        for item in pending:
            if not stale or not isinstance(item, HistoryNode):
                continue
            try:
                found = repair_declared_defaults(item.state, written)
            except _Unrestorable as exc:
                raise ValueError(f"{path}: node {item.id}: {exc}") from None
            for r in found:
                key = (r["path"], r["label"], tuple(r["before"].items()),
                       tuple(r["after"].items()), r["since"])
                repairs.setdefault(key, []).append(item.id)
        if diagnostics is not None:
            diagnostics.extend(_repair_diagnostics(repairs))

        tree = cls(header, path=path)
        for item in pending:
            if isinstance(item, HistoryNode):
                tree.nodes[item.id] = item
                tree.order.append(item.id)
                tree.refs[HEAD] = item.id  # committing advanced HEAD, as in add()
            else:
                tree._apply_annotation(item)
        return tree

    # -- mutation -------------------------------------------------------
    def add(self, *, parents: Sequence[str], action: NodeAction,
            state: RefinementState, metrics: NodeMetrics | None = None,
            diagnostics: Iterable = (), label: str = "") -> HistoryNode:
        node = HistoryNode(
            id=f"n{len(self.order):04d}",
            parents=list(parents),
            action=action,
            state=state,
            metrics=metrics or NodeMetrics(),
            diagnostics=list(diagnostics),
            label=label,
            created_utc=_utcnow(),
        )
        self.nodes[node.id] = node
        self.order.append(node.id)
        self.refs[HEAD] = node.id  # committing advances HEAD, as in git
        if self.path is not None:
            append_record(self.path, HistoryRecord(record="node", node=node))
        return node

    def annotate(self, node_id: str, *, label: str | None = None,
                 scores: dict[str, float] | None = None,
                 notes: dict[str, str] | None = None,
                 refs: dict[str, str] | None = None) -> None:
        ann = Annotation(node_id=self.resolve(node_id), label=label,
                         scores=scores or {}, notes=notes or {}, refs=refs or {})
        self._apply_annotation(ann)
        if self.path is not None:
            append_record(self.path, HistoryRecord(record="annotation", annotation=ann))

    def _apply_annotation(self, ann: Annotation) -> None:
        self.refs.update(ann.refs)
        node = self.nodes.get(ann.node_id)
        if node is None:
            return
        if ann.label is not None:
            node.label = ann.label
        node.scores.update(ann.scores)
        node.notes.update(ann.notes)

    def tag(self, node_id: str, name: str) -> None:
        """Name a node, so branches are addressable by intent not by index."""
        if name == HEAD:
            raise ValueError("'head' is reserved; use checkout() to move it")
        self.annotate(node_id, refs={name: self.resolve(node_id)})

    def set_head(self, node_id: str) -> None:
        self.annotate(node_id, refs={HEAD: self.resolve(node_id)})

    # -- queries --------------------------------------------------------
    def resolve(self, key: str) -> str:
        """Accept either a node id or a ref name."""
        if key in self.refs:
            return self.refs[key]
        if key in self.nodes:
            return key
        raise KeyError(f"unknown node or ref {key!r}; "
                       f"known refs: {sorted(self.refs)}")

    def __getitem__(self, key: str) -> HistoryNode:
        return self.nodes[self.resolve(key)]

    def __len__(self) -> int:
        return len(self.order)

    def __contains__(self, key: str) -> bool:
        return key in self.nodes or key in self.refs

    @property
    def head(self) -> str | None:
        return self.refs.get(HEAD)

    @property
    def root(self) -> HistoryNode | None:
        for nid in self.order:
            if not self.nodes[nid].parents:
                return self.nodes[nid]
        return None

    def children(self, node_id: str) -> list[HistoryNode]:
        target = self.resolve(node_id)
        return [self.nodes[n] for n in self.order if target in self.nodes[n].parents]

    def leaves(self) -> list[HistoryNode]:
        parented = {p for n in self.nodes.values() for p in n.parents}
        return [self.nodes[n] for n in self.order if n not in parented]

    def lineage(self, node_id: str) -> list[HistoryNode]:
        """Root → node, following first parents."""
        chain: list[HistoryNode] = []
        cur: str | None = self.resolve(node_id)
        seen: set[str] = set()
        while cur is not None and cur not in seen:
            seen.add(cur)
            node = self.nodes[cur]
            chain.append(node)
            cur = node.parent
        return list(reversed(chain))

    def ancestors(self, node_id: str) -> set[str]:
        """All ancestors (following *every* parent), including the node."""
        out: set[str] = set()
        stack = [self.resolve(node_id)]
        while stack:
            cur = stack.pop()
            if cur in out:
                continue
            out.add(cur)
            stack.extend(self.nodes[cur].parents)
        return out

    def common_ancestor(self, a: str, b: str) -> str | None:
        """The merge base: the latest node that is an ancestor of both.

        "Latest" by insertion order — ids are sequential, so the max over the
        intersection is the most recent shared state (sufficient for a DAG
        grown by append-only commits)."""
        shared = self.ancestors(a) & self.ancestors(b)
        if not shared:
            return None
        return max(shared, key=lambda nid: self.order.index(nid))

    def best(self, metric: str = "rwp", *, minimize: bool = True) -> HistoryNode:
        scored = [n for n in self.nodes.values()
                  if n.metrics.statistics is not None
                  and getattr(n.metrics.statistics, metric, None) is not None]
        if not scored:
            raise ValueError("no node carries statistics yet")
        return (min if minimize else max)(
            scored, key=lambda n: getattr(n.metrics.statistics, metric))

    def compare(self, node_ids: Sequence[str]) -> list[dict]:
        """A flat metric table for the given nodes — for humans and for agents."""
        rows = []
        for key in node_ids:
            node = self[key]
            stats = node.metrics.statistics
            rows.append({
                "id": node.id,
                "label": node.label,
                "action": f"{node.action.kind}:{node.action.name}".rstrip(":"),
                "status": node.metrics.status,
                "n_free": stats.n_free_parameters if stats else None,
                "rwp": stats.rwp if stats else None,
                "gof": stats.gof if stats else None,
                "chi2": stats.chi2 if stats else None,
            })
        return rows

    def diff(self, a: str, b: str, *, rtol: float = 1e-12) -> dict[str, tuple[float, float]]:
        """Parameter values that differ between two nodes."""
        va, vb = self._values(self[a]), self._values(self[b])
        out: dict[str, tuple[float, float]] = {}
        for path in sorted(set(va) | set(vb)):
            x, y = va.get(path), vb.get(path)
            if x is None or y is None or abs(x - y) > rtol * max(1.0, abs(x), abs(y)):
                out[path] = (x, y)  # type: ignore[assignment]
        return out

    @staticmethod
    def _values(node: HistoryNode) -> dict[str, float]:
        from ..params.vector import VAR_PREFIX, ParameterTable

        table = ParameterTable(node.state.structure, node.state.instrument)
        values = {e.path: e.value for e in table.entries}
        # a named variable (WP-1119) has no model field, so a table built from
        # the structure and instrument alone has no row for it; its value is on
        # the state, and without this a diff of two nodes a variable moved
        # between reports its dependents and never the quantity that moved them
        values.update({f"{VAR_PREFIX}{name}": prm.value
                       for name, prm in node.state.variables.items()})
        return values

    # -- rendering ------------------------------------------------------
    def summary(self) -> str:
        """An indented tree with Rwp per node; ``*`` marks HEAD."""
        head = self.head
        lines = [f"{self.header.tree_id}  {len(self.order)} nodes"
                 f"  data={self.header.data_source or self.header.data_fingerprint[:8]}"]

        def render(node: HistoryNode, prefix: str, last: bool, top: bool) -> None:
            branch = "" if top else ("└─ " if last else "├─ ")
            mark = "*" if node.id == head else " "
            rwp = node.rwp
            stat = f"Rwp {rwp:.4f}" if rwp is not None else "—"
            name = f"{node.action.kind}:{node.action.name}".rstrip(":")
            tags = [k for k, v in self.refs.items() if v == node.id and k != HEAD]
            tag = f"  [{', '.join(sorted(tags))}]" if tags else ""
            lines.append(f"{prefix}{branch}{mark}{node.id}  {name:<22} {stat}{tag}")
            kids = self.children(node.id)
            child_prefix = prefix + ("" if top else ("   " if last else "│  "))
            for i, kid in enumerate(kids):
                render(kid, child_prefix, i == len(kids) - 1, False)

        root = self.root
        if root is not None:
            render(root, "", True, True)
        return "\n".join(lines)

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        for nid in self.order:
            node = self.nodes[nid]
            rwp = node.rwp
            stat = f"<br/>Rwp {rwp:.4f}" if rwp is not None else ""
            name = f"{node.action.kind}:{node.action.name}".rstrip(":")
            lines.append(f'    {nid}["{nid}<br/>{name}{stat}"]')
            for parent in node.parents:
                lines.append(f"    {parent} --> {nid}")
        return "\n".join(lines)

    # -- persistence ----------------------------------------------------
    def records(self) -> list[HistoryRecord]:
        recs = [HistoryRecord(record="header", header=self.header)]
        recs += [HistoryRecord(record="node", node=self.nodes[n]) for n in self.order]
        if self.refs:
            recs.append(HistoryRecord(record="annotation", annotation=Annotation(
                node_id=self.refs.get(HEAD, ""), refs=dict(self.refs))))
        return recs

    def save(self, path: str | Path) -> None:
        write_records(path, self.records())
        self.path = Path(path)
