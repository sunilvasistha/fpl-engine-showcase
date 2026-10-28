"""Deterministic dependency graph with validation and cycle detection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import heapq


class DependencyError(ValueError):
    pass


@dataclass(frozen=True)
class Node:
    node_id: str
    kind: str = "COMPUTATION"

    def validate(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id.strip():
            raise DependencyError("node_id must be a non-empty string")

        if not isinstance(self.kind, str) or not self.kind.strip():
            raise DependencyError("kind must be a non-empty string")


@dataclass(frozen=True, order=True)
class Edge:
    upstream: str
    downstream: str


class DependencyGraph:
    def __init__(self, nodes, edges):
        self.nodes: dict[str, Node] = {}

        for node in nodes:
            if not isinstance(node, Node):
                raise DependencyError("nodes require Node objects")

            node.validate()

            if node.node_id in self.nodes:
                raise DependencyError(
                    f"duplicate node: {node.node_id}"
                )

            self.nodes[node.node_id] = node

        self.edges = tuple(sorted(edges))
        self.topological_order: tuple[str, ...] = ()

        self.validate()

    def validate(self):
        if len(set(self.edges)) != len(self.edges):
            raise DependencyError("duplicate dependency edge")

        children = {
            node_id: []
            for node_id in self.nodes
        }

        indegree = dict.fromkeys(self.nodes, 0)

        for edge in self.edges:
            if not isinstance(edge, Edge):
                raise DependencyError("edges require Edge objects")

            if edge.upstream not in self.nodes:
                raise DependencyError(
                    f"missing upstream node: {edge.upstream}"
                )

            if edge.downstream not in self.nodes:
                raise DependencyError(
                    f"missing downstream node: {edge.downstream}"
                )

            if edge.upstream == edge.downstream:
                raise DependencyError(
                    f"self dependency: {edge.upstream}"
                )

            children[edge.upstream].append(edge.downstream)
            indegree[edge.downstream] += 1

        ready = [
            node_id
            for node_id, degree in indegree.items()
            if degree == 0
        ]

        heapq.heapify(ready)
        ordered = []

        while ready:
            node_id = heapq.heappop(ready)
            ordered.append(node_id)

            for downstream in sorted(children[node_id]):
                indegree[downstream] -= 1

                if indegree[downstream] == 0:
                    heapq.heappush(ready, downstream)

        if len(ordered) != len(self.nodes):
            raise DependencyError("dependency cycle detected")

        self.topological_order = tuple(ordered)
        return self

    def to_dict(self):
        return {
            "nodes": [
                asdict(self.nodes[node_id])
                for node_id in sorted(self.nodes)
            ],
            "edges": [
                asdict(edge)
                for edge in self.edges
            ],
            "topological_order": list(self.topological_order),
        }
