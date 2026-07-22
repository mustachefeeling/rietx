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
from .store import append_record, fingerprint, read_records, write_records

HEAD = "head"


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
    def load(cls, path: str | Path) -> "RefinementTree":
        """Rebuild a tree from its JSONL log.

        Records are applied in file order — header, nodes, then annotations —
        so later annotations overlay earlier nodes without any rewriting.
        """
        header: TreeHeader | None = None
        nodes: list[HistoryNode] = []
        annotations: list[Annotation] = []
        for rec in read_records(path):
            if rec.record == "header" and rec.header is not None:
                header = rec.header
            elif rec.record == "node" and rec.node is not None:
                nodes.append(rec.node)
            elif rec.record == "annotation" and rec.annotation is not None:
                annotations.append(rec.annotation)
        if header is None:
            raise ValueError(f"{path}: no header record; not a history log")

        tree = cls(header, path=path)
        for node in nodes:
            tree.nodes[node.id] = node
            tree.order.append(node.id)
        for ann in annotations:
            tree._apply_annotation(ann)
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
        from ..params.vector import ParameterTable

        table = ParameterTable(node.state.structure, node.state.instrument)
        return {e.path: e.value for e in table.entries}

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
