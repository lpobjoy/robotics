from __future__ import annotations

import pytest
from worldmodel.graph import build_graph
from worldmodel.models import Asset, Location, LocationLink, MissionCapability, Robot, WorkOrder
from worldmodel.query import UnknownWorkOrderError, qualify_robots_for_work_order, shortest_distance

LOCATIONS = [
    Location(id=1, name="Pump House", x=0.0, y=0.0),
    Location(id=2, name="Valve Yard", x=30.0, y=0.0),
    Location(id=3, name="Tank Farm", x=60.0, y=0.0),
    Location(id=4, name="Isolated Shed", x=1000.0, y=1000.0),
]

# Pump House <-> Valve Yard <-> Tank Farm, both directions. "Isolated Shed"
# has no links at all.
LINKS = [
    LocationLink(id=1, from_location_id=1, to_location_id=2, distance_m=30.0),
    LocationLink(id=2, from_location_id=2, to_location_id=1, distance_m=30.0),
    LocationLink(id=3, from_location_id=2, to_location_id=3, distance_m=30.0),
    LocationLink(id=4, from_location_id=3, to_location_id=2, distance_m=30.0),
]

ASSETS = [Asset(id=10, name="Pump P-101", location_id=1)]

WORK_ORDERS = [
    WorkOrder(
        id=1000,
        title="Inspect P-101",
        asset_id=10,
        required_capabilities=[MissionCapability.INSPECT_VISUAL],
        status="Draft",
    ),
    WorkOrder(
        id=1001,
        title="Thermal and visual inspect P-101",
        asset_id=10,
        required_capabilities=[MissionCapability.INSPECT_VISUAL, MissionCapability.INSPECT_THERMAL],
        status="Draft",
    ),
]


def test_qualifies_robot_with_matching_capability_and_a_route() -> None:
    robots = [
        Robot(
            id=100,
            name="amr-01",
            capabilities=[MissionCapability.INSPECT_VISUAL],
            home_location_id=2,
        )
    ]
    graph = build_graph(LOCATIONS, LINKS, ASSETS, robots, WORK_ORDERS)

    result = qualify_robots_for_work_order(graph, 1000)

    assert result.target_location_id == 1
    assert len(result.qualified_robots) == 1
    qualified = result.qualified_robots[0]
    assert qualified.robot_id == 100
    assert qualified.route == (2, 1)
    assert qualified.route_distance_m == 30.0


def test_robot_already_at_target_has_zero_distance_route() -> None:
    robots = [
        Robot(
            id=100,
            name="amr-01",
            capabilities=[MissionCapability.INSPECT_VISUAL],
            home_location_id=1,
        )
    ]
    graph = build_graph(LOCATIONS, LINKS, ASSETS, robots, WORK_ORDERS)

    result = qualify_robots_for_work_order(graph, 1000)

    assert result.qualified_robots[0].route == (1,)
    assert result.qualified_robots[0].route_distance_m == 0.0


def test_robot_missing_a_required_capability_does_not_qualify() -> None:
    """Work order 1001 needs BOTH inspect_visual and inspect_thermal --
    superset match, not any-of."""
    robots = [
        Robot(
            id=100,
            name="amr-01",
            capabilities=[MissionCapability.INSPECT_VISUAL],
            home_location_id=1,
        ),
        Robot(
            id=200,
            name="spot-01",
            capabilities=[MissionCapability.INSPECT_VISUAL, MissionCapability.INSPECT_THERMAL],
            home_location_id=1,
        ),
    ]
    graph = build_graph(LOCATIONS, LINKS, ASSETS, robots, WORK_ORDERS)

    result = qualify_robots_for_work_order(graph, 1001)

    robot_ids = {r.robot_id for r in result.qualified_robots}
    assert robot_ids == {200}


def test_unreachable_robot_does_not_qualify() -> None:
    robots = [
        Robot(
            id=100,
            name="amr-01",
            capabilities=[MissionCapability.INSPECT_VISUAL],
            home_location_id=4,  # Isolated Shed -- no links to anywhere
        )
    ]
    graph = build_graph(LOCATIONS, LINKS, ASSETS, robots, WORK_ORDERS)

    result = qualify_robots_for_work_order(graph, 1000)

    assert result.qualified_robots == ()


def test_qualified_robots_are_ranked_cheapest_first() -> None:
    robots = [
        Robot(
            id=100,
            name="far-robot",
            capabilities=[MissionCapability.INSPECT_VISUAL],
            home_location_id=3,  # Tank Farm: distance 60 to Pump House
        ),
        Robot(
            id=200,
            name="near-robot",
            capabilities=[MissionCapability.INSPECT_VISUAL],
            home_location_id=2,  # Valve Yard: distance 30 to Pump House
        ),
    ]
    graph = build_graph(LOCATIONS, LINKS, ASSETS, robots, WORK_ORDERS)

    result = qualify_robots_for_work_order(graph, 1000)

    assert [r.robot_id for r in result.qualified_robots] == [200, 100]


def test_unknown_work_order_raises() -> None:
    graph = build_graph(LOCATIONS, LINKS, ASSETS, [], WORK_ORDERS)
    with pytest.raises(UnknownWorkOrderError):
        qualify_robots_for_work_order(graph, 99999)


def test_shortest_distance_between_reachable_locations() -> None:
    graph = build_graph(LOCATIONS, LINKS, ASSETS, [], WORK_ORDERS)
    assert shortest_distance(graph, 1, 3) == 60.0


def test_shortest_distance_same_location_is_zero() -> None:
    graph = build_graph(LOCATIONS, LINKS, ASSETS, [], WORK_ORDERS)
    assert shortest_distance(graph, 1, 1) == 0.0


def test_shortest_distance_unreachable_is_none() -> None:
    graph = build_graph(LOCATIONS, LINKS, ASSETS, [], WORK_ORDERS)
    assert shortest_distance(graph, 1, 4) is None
