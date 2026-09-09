"""http_api.py is the console's REST surface (CLAUDE.md section 4.8).
Needs a real, network-bound EAM: build_mission_tools only takes a base
URL, not an injectable client (mcp_server.eam_gateway.EamGateway does
support injection, but wiring.py's job is to build the real thing).
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn
from eam.app import create_app as create_eam_app
from fastapi.testclient import TestClient
from mcp_server.http_api import create_app as create_http_api_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def running_eam() -> Iterator[str]:
    port = _free_port()
    app = create_eam_app(db_path=":memory:", seed=True)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            httpx.get(f"{base_url}/api/locations", timeout=0.2)
            break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        raise RuntimeError("eam did not start in time")

    yield base_url

    server.should_exit = True
    thread.join(timeout=5.0)


@pytest.fixture
def client(running_eam: str) -> TestClient:
    app = create_http_api_app(running_eam, audit_db_path=":memory:")
    return TestClient(app)


def _first_draft_work_order_id(running_eam: str) -> int:
    drafts = httpx.get(f"{running_eam}/api/work-orders", params={"status": "Draft"}).json()
    return int(drafts[0]["id"])


def test_mission_status_404_before_any_dispatch(client: TestClient) -> None:
    response = client.get("/work-orders/1/mission-status")
    assert response.status_code == 404


def test_audit_list_is_empty_before_anything_happens(client: TestClient) -> None:
    response = client.get("/audit")
    assert response.status_code == 200
    assert response.json() == []


def test_approve_and_abort_transition_the_work_order(
    client: TestClient, running_eam: str
) -> None:
    work_order_id = _first_draft_work_order_id(running_eam)
    httpx.patch(
        f"{running_eam}/api/work-orders/{work_order_id}/status", json={"status": "Released"}
    ).raise_for_status()
    httpx.patch(
        f"{running_eam}/api/work-orders/{work_order_id}/status", json={"status": "Dispatched"}
    ).raise_for_status()
    httpx.patch(
        f"{running_eam}/api/work-orders/{work_order_id}/status", json={"status": "InProgress"}
    ).raise_for_status()
    httpx.patch(
        f"{running_eam}/api/work-orders/{work_order_id}/status", json={"status": "AwaitingHuman"}
    ).raise_for_status()

    approve_response = client.post(f"/work-orders/{work_order_id}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "InProgress"

    httpx.patch(
        f"{running_eam}/api/work-orders/{work_order_id}/status", json={"status": "AwaitingHuman"}
    ).raise_for_status()

    abort_response = client.post(f"/work-orders/{work_order_id}/abort")
    assert abort_response.status_code == 200
    assert abort_response.json()["status"] == "Cancelled"


def test_cors_allows_the_configured_console_origin(running_eam: str) -> None:
    app = create_http_api_app(
        running_eam, audit_db_path=":memory:", console_origin="http://localhost:5173"
    )
    client = TestClient(app)
    response = client.options(
        "/audit",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
