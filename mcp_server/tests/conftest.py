from __future__ import annotations

import networkx as nx
import pytest
from audit.sqlite_sink import SqliteAuditSink
from eam.app import create_app
from fastapi.testclient import TestClient
from mcp_server.eam_gateway import EamGateway
from mcp_server.tools import MissionTools
from router.fake_adapter import FakeAdapter
from router.models import MissionType
from router.router import Router
from worldmodel.client import EamClient
from worldmodel.graph import build_graph, build_graph_from_eam


@pytest.fixture
def eam_test_client() -> TestClient:
    app = create_app(db_path=":memory:", seed=True)
    return TestClient(app, base_url="http://eam.test")


@pytest.fixture
def mission_tools(eam_test_client: TestClient) -> MissionTools:
    eam_gateway = EamGateway(client=eam_test_client)
    eam_client = EamClient(client=eam_test_client)

    def graph_provider() -> nx.DiGraph:
        return build_graph_from_eam(eam_client)

    topology_graph = build_graph(
        locations=eam_client.list_locations(),
        location_links=eam_client.list_location_links(),
        assets=[],
        robots=[],
        work_orders=[],
    )
    audit_sink = SqliteAuditSink(":memory:")
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
