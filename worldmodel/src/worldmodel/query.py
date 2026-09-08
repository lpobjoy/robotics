"""The one question this module exists to answer (CLAUDE.md section 4.2):
for this work order, which locations, which required capabilities, which
robots qualify, what route.

A robot "qualifies" if it has every required capability (not just one of
them) and a location_links path exists from its home location to the
work order's target location. Availability (idle vs busy right now) is
deliberately not checked here -- that changes in real time during
dispatch, so it belongs to the router's selection logic (CLAUDE.md
section 4.4), not to a graph built once per work order lookup.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from worldmodel.graph import asset_node, location_node, work_order_node
from worldmodel.models import Asset, MissionCapability, Robot, WorkOrder


class UnknownWorkOrderError(LookupError):
    """Raised when the graph has no work order with the given id."""


@dataclass(frozen=True)
class QualifiedRobot:
    robot_id: int
    robot_name: str
    capabilities: tuple[MissionCapability, ...]
    route: tuple[int, ...]  # location ids, home location through target location, inclusive
    route_distance_m: float


@dataclass(frozen=True)
class WorkOrderQualification:
    work_order_id: int
    asset_id: int
    target_location_id: int
    required_capabilities: tuple[MissionCapability, ...]
    qualified_robots: tuple[QualifiedRobot, ...]  # sorted by route_distance_m, cheapest first


def qualify_robots_for_work_order(graph: nx.DiGraph, work_order_id: int) -> WorkOrderQualification:
    wo_node = work_order_node(work_order_id)
    if wo_node not in graph:
        raise UnknownWorkOrderError(f"no work order with id {work_order_id} in the graph")

    work_order: WorkOrder = graph.nodes[wo_node]["data"]
    asset: Asset = graph.nodes[asset_node(work_order.asset_id)]["data"]
    target_location = location_node(asset.location_id)
    required = tuple(work_order.required_capabilities)
    required_set = set(required)

    qualified: list[QualifiedRobot] = []
    for node, node_data in graph.nodes(data=True):
        if node_data.get("kind") != "robot":
            continue
        robot: Robot = node_data["data"]
        if not required_set <= set(robot.capabilities):
            continue

        home_location = location_node(robot.home_location_id)
        try:
            path = nx.shortest_path(graph, home_location, target_location, weight="distance_m")
            distance = nx.shortest_path_length(
                graph, home_location, target_location, weight="distance_m"
            )
        except nx.NetworkXNoPath:
            continue

        route_ids = tuple(int(n.split(":", 1)[1]) for n in path)
        qualified.append(
            QualifiedRobot(
                robot_id=robot.id,
                robot_name=robot.name,
                capabilities=tuple(robot.capabilities),
                route=route_ids,
                route_distance_m=float(distance),
            )
        )

    qualified.sort(key=lambda r: r.route_distance_m)

    return WorkOrderQualification(
        work_order_id=work_order.id,
        asset_id=asset.id,
        target_location_id=asset.location_id,
        required_capabilities=required,
        qualified_robots=tuple(qualified),
    )
