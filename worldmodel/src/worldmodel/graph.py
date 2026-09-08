"""Builds the world-model graph from EAM data (CLAUDE.md section 4.2):

    Asset       -LOCATED_AT->      Location
    Location    -REACHABLE_FROM->  Location
    Robot       -HAS_CAPABILITY->  Capability
    WorkOrder   -TARGETS->         Asset
    WorkOrder   -REQUIRES->        Capability

Plus one edge not listed in section 4.2 but needed to answer "what
route": Robot -LOCATED_AT-> Location, for the robot's home location. Same
relationship as the asset edge, just applied to the other entity that
needs a place in space.

Nodes are keyed "<kind>:<id>" (e.g. "location:3", "capability:patrol") so
node identity never collides across entity types that happen to reuse the
same integer id.
"""

from __future__ import annotations

import networkx as nx

from worldmodel.client import EamClient
from worldmodel.models import Asset, Location, LocationLink, Robot, WorkOrder

LOCATED_AT = "LOCATED_AT"
REACHABLE_FROM = "REACHABLE_FROM"
HAS_CAPABILITY = "HAS_CAPABILITY"
TARGETS = "TARGETS"
REQUIRES = "REQUIRES"


def location_node(location_id: int) -> str:
    return f"location:{location_id}"


def asset_node(asset_id: int) -> str:
    return f"asset:{asset_id}"


def robot_node(robot_id: int) -> str:
    return f"robot:{robot_id}"


def work_order_node(work_order_id: int) -> str:
    return f"workorder:{work_order_id}"


def capability_node(capability: str) -> str:
    return f"capability:{capability}"


def build_graph(
    locations: list[Location],
    location_links: list[LocationLink],
    assets: list[Asset],
    robots: list[Robot],
    work_orders: list[WorkOrder],
) -> nx.DiGraph:
    graph = nx.DiGraph()

    for location in locations:
        graph.add_node(location_node(location.id), kind="location", data=location)

    for link in location_links:
        graph.add_edge(
            location_node(link.from_location_id),
            location_node(link.to_location_id),
            kind=REACHABLE_FROM,
            distance_m=link.distance_m,
        )

    for asset in assets:
        graph.add_node(asset_node(asset.id), kind="asset", data=asset)
        graph.add_edge(asset_node(asset.id), location_node(asset.location_id), kind=LOCATED_AT)

    for robot in robots:
        graph.add_node(robot_node(robot.id), kind="robot", data=robot)
        graph.add_edge(
            robot_node(robot.id), location_node(robot.home_location_id), kind=LOCATED_AT
        )
        for capability in robot.capabilities:
            graph.add_node(capability_node(capability), kind="capability")
            graph.add_edge(robot_node(robot.id), capability_node(capability), kind=HAS_CAPABILITY)

    for work_order in work_orders:
        graph.add_node(work_order_node(work_order.id), kind="workorder", data=work_order)
        graph.add_edge(
            work_order_node(work_order.id), asset_node(work_order.asset_id), kind=TARGETS
        )
        for capability in work_order.required_capabilities:
            graph.add_node(capability_node(capability), kind="capability")
            graph.add_edge(
                work_order_node(work_order.id), capability_node(capability), kind=REQUIRES
            )

    return graph


def build_graph_from_eam(client: EamClient) -> nx.DiGraph:
    return build_graph(
        locations=client.list_locations(),
        location_links=client.list_location_links(),
        assets=client.list_assets(),
        robots=client.list_robots(),
        work_orders=client.list_work_orders(),
    )
