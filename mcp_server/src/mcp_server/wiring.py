"""Builds a MissionTools instance wired to a real EAM over HTTP.

No real adapters exist yet (adapters/ starts at step 7): this registers
a FakeAdapter per robot in the EAM's seed data, so the whole pipeline --
agent, MCP tools, router, audit, identity -- is exercisable end to end
before a real robot exists. See mcp_server/README.md.
"""

from __future__ import annotations

import networkx as nx
from audit.sqlite_sink import SqliteAuditSink
from router.fake_adapter import FakeAdapter
from router.models import MissionType
from router.router import Router
from worldmodel.client import EamClient
from worldmodel.graph import build_graph, build_graph_from_eam

from mcp_server.eam_gateway import EamGateway
from mcp_server.tools import MissionTools


def build_mission_tools(eam_base_url: str, audit_db_path: str = ":memory:") -> MissionTools:
    eam_gateway = EamGateway(eam_base_url)
    eam_client = EamClient(eam_base_url)
    audit_sink = SqliteAuditSink(audit_db_path)

    def graph_provider() -> nx.DiGraph:
        # Rebuilt on every call: qualify_robots needs to see work orders
        # created after server startup, not a startup-time snapshot.
        return build_graph_from_eam(eam_client)

    # Router's own graph only needs location topology -- shortest_distance
    # never touches asset/robot/work-order nodes -- and that topology is
    # static for this demo's lifetime, so building it once here is fine.
    topology_graph = build_graph(
        locations=eam_client.list_locations(),
        location_links=eam_client.list_location_links(),
        assets=[],
        robots=[],
        work_orders=[],
    )
    router = Router(topology_graph, audit_sink=audit_sink)

    for robot in eam_client.list_robots():
        router.register_adapter(
            FakeAdapter(
                robot_id=str(robot.id),
                name=robot.name,
                ecosystem="fake",
                supported_capabilities=[MissionType(c.value) for c in robot.capabilities],
                location_id=robot.home_location_id,
            )
        )

    return MissionTools(eam_gateway, graph_provider, router, audit_sink)
