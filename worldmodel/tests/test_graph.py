from __future__ import annotations

from worldmodel.graph import (
    HAS_CAPABILITY,
    LOCATED_AT,
    REACHABLE_FROM,
    REQUIRES,
    TARGETS,
    asset_node,
    build_graph,
    capability_node,
    location_node,
    robot_node,
    work_order_node,
)
from worldmodel.models import Asset, Location, LocationLink, MissionCapability, Robot, WorkOrder


def _fixture() -> tuple[
    list[Location], list[LocationLink], list[Asset], list[Robot], list[WorkOrder]
]:
    locations = [
        Location(id=1, name="Pump House", x=0.0, y=0.0),
        Location(id=2, name="Valve Yard", x=40.0, y=0.0),
    ]
    links = [
        LocationLink(id=1, from_location_id=1, to_location_id=2, distance_m=40.0),
        LocationLink(id=2, from_location_id=2, to_location_id=1, distance_m=40.0),
    ]
    assets = [Asset(id=10, name="Pump P-101", location_id=1)]
    robots = [
        Robot(
            id=100,
            name="amr-01",
            capabilities=[MissionCapability.INSPECT_VISUAL],
            home_location_id=1,
        )
    ]
    work_orders = [
        WorkOrder(
            id=1000,
            title="Inspect P-101",
            asset_id=10,
            required_capabilities=[MissionCapability.INSPECT_VISUAL],
            status="Draft",
        )
    ]
    return locations, links, assets, robots, work_orders


def test_location_nodes_and_reachable_from_edges() -> None:
    locations, links, assets, robots, work_orders = _fixture()
    graph = build_graph(locations, links, assets, robots, work_orders)

    assert graph.nodes[location_node(1)]["kind"] == "location"
    assert graph.has_edge(location_node(1), location_node(2))
    assert graph[location_node(1)][location_node(2)]["kind"] == REACHABLE_FROM
    assert graph[location_node(1)][location_node(2)]["distance_m"] == 40.0


def test_asset_located_at_location() -> None:
    locations, links, assets, robots, work_orders = _fixture()
    graph = build_graph(locations, links, assets, robots, work_orders)

    assert graph.has_edge(asset_node(10), location_node(1))
    assert graph[asset_node(10)][location_node(1)]["kind"] == LOCATED_AT


def test_robot_located_at_home_and_has_capability() -> None:
    locations, links, assets, robots, work_orders = _fixture()
    graph = build_graph(locations, links, assets, robots, work_orders)

    assert graph.has_edge(robot_node(100), location_node(1))
    assert graph[robot_node(100)][location_node(1)]["kind"] == LOCATED_AT

    cap = capability_node(MissionCapability.INSPECT_VISUAL)
    assert graph.has_edge(robot_node(100), cap)
    assert graph[robot_node(100)][cap]["kind"] == HAS_CAPABILITY


def test_work_order_targets_asset_and_requires_capability() -> None:
    locations, links, assets, robots, work_orders = _fixture()
    graph = build_graph(locations, links, assets, robots, work_orders)

    assert graph.has_edge(work_order_node(1000), asset_node(10))
    assert graph[work_order_node(1000)][asset_node(10)]["kind"] == TARGETS

    cap = capability_node(MissionCapability.INSPECT_VISUAL)
    assert graph.has_edge(work_order_node(1000), cap)
    assert graph[work_order_node(1000)][cap]["kind"] == REQUIRES


def test_capability_node_shared_across_robot_and_work_order() -> None:
    """A robot and a work order that both use inspect_visual should point
    at the *same* capability node -- that shared identity is what lets the
    qualification query do a plain set comparison."""
    locations, links, assets, robots, work_orders = _fixture()
    graph = build_graph(locations, links, assets, robots, work_orders)

    cap = capability_node(MissionCapability.INSPECT_VISUAL)
    assert graph.in_degree(cap) == 2
