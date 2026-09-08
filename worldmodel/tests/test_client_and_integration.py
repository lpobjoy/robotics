"""Tests against the real eam app and its real seed data (CLAUDE.md
section 6, step 3: "Tests with the seed data"), run in-process -- no
socket, no separate server process.

fastapi.testclient.TestClient is itself an httpx.Client subclass with a
working sync-over-ASGI transport (raw httpx.ASGITransport is async-only
in the installed httpx version), so it's reused here as EamClient's
transport instead of standing up a real server thread.
"""

from __future__ import annotations

import pytest
from eam.app import create_app
from fastapi.testclient import TestClient
from worldmodel.client import EamClient
from worldmodel.graph import build_graph_from_eam
from worldmodel.query import qualify_robots_for_work_order


@pytest.fixture
def eam_client() -> EamClient:
    app = create_app(db_path=":memory:", seed=True)
    test_client = TestClient(app, base_url="http://eam.test")
    return EamClient(client=test_client)


def test_client_fetches_seeded_locations(eam_client: EamClient) -> None:
    locations = eam_client.list_locations()
    assert len(locations) == 7
    assert {loc.name for loc in locations} >= {"Pump House", "Valve Yard", "Tank Farm"}


def test_client_fetches_seeded_location_links(eam_client: EamClient) -> None:
    links = eam_client.list_location_links()
    assert len(links) == 14
    assert all(link.distance_m > 0 for link in links)


def test_client_fetches_seeded_robots_and_work_orders(eam_client: EamClient) -> None:
    robots = eam_client.list_robots()
    work_orders = eam_client.list_work_orders()
    assert len(robots) == 3
    assert len(work_orders) == 5


def test_build_graph_from_real_seed_data(eam_client: EamClient) -> None:
    graph = build_graph_from_eam(eam_client)
    # 7 locations + 20 assets + 3 robots + 5 work orders + 3 capability nodes.
    assert graph.number_of_nodes() == 7 + 20 + 3 + 5 + 3


def test_qualify_robots_for_seeded_visual_inspection_work_order(eam_client: EamClient) -> None:
    """'Visual inspect Pump P-101 for leaks' (seed.py) targets an asset in
    Pump House and needs only inspect_visual. All three seeded robots have
    that capability, so all three should qualify, with amr-01 (seeded at
    Pump House itself) cheapest at distance 0."""
    graph = build_graph_from_eam(eam_client)

    work_order = next(
        wo for wo in eam_client.list_work_orders() if wo.title.startswith("Visual inspect Pump")
    )
    result = qualify_robots_for_work_order(graph, work_order.id)

    assert len(result.qualified_robots) == 3
    cheapest = result.qualified_robots[0]
    assert cheapest.robot_name == "amr-01"
    assert cheapest.route_distance_m == 0.0


def test_qualify_robots_for_seeded_thermal_work_order(eam_client: EamClient) -> None:
    """'Thermal scan Switchgear SG-601' needs inspect_thermal, which only
    go2-01 and spot-01 have (amr-01 doesn't)."""
    graph = build_graph_from_eam(eam_client)

    work_order = next(
        wo for wo in eam_client.list_work_orders() if wo.title.startswith("Thermal scan Switchgear")
    )
    result = qualify_robots_for_work_order(graph, work_order.id)

    qualified_names = {r.robot_name for r in result.qualified_robots}
    assert qualified_names == {"go2-01", "spot-01"}
