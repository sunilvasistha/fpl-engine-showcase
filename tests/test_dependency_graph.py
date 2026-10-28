import pytest

from fpl_showcase.dependency_graph import (
    DependencyError,
    DependencyGraph,
    Edge,
    Node,
)


def test_graph_orders_dependencies_deterministically():
    graph = DependencyGraph(
        nodes=[
            Node("fetch"),
            Node("normalise"),
            Node("evaluate"),
            Node("publish"),
        ],
        edges=[
            Edge("fetch", "normalise"),
            Edge("normalise", "evaluate"),
            Edge("evaluate", "publish"),
        ],
    )

    assert graph.topological_order == (
        "fetch",
        "normalise",
        "evaluate",
        "publish",
    )


def test_graph_rejects_cycle():
    with pytest.raises(
        DependencyError,
        match="cycle",
    ):
        DependencyGraph(
            nodes=[
                Node("a"),
                Node("b"),
            ],
            edges=[
                Edge("a", "b"),
                Edge("b", "a"),
            ],
        )


def test_graph_rejects_missing_node():
    with pytest.raises(
        DependencyError,
        match="missing downstream",
    ):
        DependencyGraph(
            nodes=[Node("a")],
            edges=[Edge("a", "missing")],
        )


def test_graph_rejects_duplicate_node():
    with pytest.raises(
        DependencyError,
        match="duplicate node",
    ):
        DependencyGraph(
            nodes=[
                Node("same"),
                Node("same"),
            ],
            edges=[],
        )
