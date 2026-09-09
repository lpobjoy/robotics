"""CLAUDE.md section 6, step 10: cut MQTT mid-mission; mission pauses
(here: fails, via the real connectivity-loss detection in adapter.py);
agent escalates; human resumes or aborts; audit shows it all.

Unlike test_adapter.py, this exercises the real Vda5050Adapter through
the same MissionTools surface the agent gets (mcp_server/tools.py), with
a real EAM, a real Router, and a real Mosquitto broker -- so the failure
that triggers escalation is a genuine MQTT connectivity loss, not a
forced status change on a FakeAdapter (that's what
test_escalation_path_on_forced_failure in mcp_server/tests/test_tools.py
already covers for the fake-adapter path). The escalate/resume/abort
steps are driven directly through MissionTools, the same way the
supervise agent's tool calls are -- see agent/tests/test_mission_agent.py
for the full agent-loop version of that decision logic; duplicating a
live model-driven agent run here would test pydantic_ai's orchestration
again, not this adapter's connectivity detection.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import networkx as nx
import paho.mqtt.client as mqtt
import pytest
from audit.sqlite_sink import SqliteAuditSink
from eam.app import create_app
from fake_robot import FakeRobot
from fastapi.testclient import TestClient
from mcp_server.eam_gateway import EamGateway
from mcp_server.tools import MissionTools
from router.models import MissionHandle, MissionStatus, MissionType, RobotAvailability
from router.router import Router
from vda5050_amr.adapter import Vda5050Adapter
from worldmodel.client import EamClient
from worldmodel.graph import build_graph, build_graph_from_eam

# Short enough that the test isn't sitting through the real 15s default,
# long enough that a slow scheduler tick between the "driving" message
# and the next status check can't be mistaken for a dropped link.
CONNECTIVITY_TIMEOUT_S = 2.0


def _wait_until(predicate: Callable[[], bool], timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not met before timeout")


@pytest.fixture
def adapter_mqtt_client(mqtt_broker_port: int) -> Iterator[mqtt.Client]:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect("127.0.0.1", mqtt_broker_port)
    client.loop_start()
    yield client
    client.loop_stop()
    client.disconnect()


@pytest.fixture
def robot_side_client(mqtt_broker_port: int) -> Iterator[mqtt.Client]:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect("127.0.0.1", mqtt_broker_port)
    client.loop_start()
    yield client
    client.loop_stop()
    client.disconnect()


@pytest.fixture
def eam_test_client() -> TestClient:
    app = create_app(db_path=":memory:", seed=True)
    return TestClient(app, base_url="http://eam.test")


@pytest.fixture
def mission_tools_with_real_amr(
    eam_test_client: TestClient, adapter_mqtt_client: mqtt.Client
) -> MissionTools:
    """Same wiring as mcp_server/tests/conftest.py's mission_tools fixture,
    except the seeded amr-01 robot is backed by a real Vda5050Adapter
    talking to the test broker instead of a FakeAdapter. The other seeded
    robots aren't registered at all: this test only needs amr-01, and an
    unregistered robot simply can't be selected by the router."""
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

    locations_by_id = {loc.id: (loc.x, loc.y) for loc in eam_client.list_locations()}
    amr = next(r for r in eam_client.list_robots() if r.name == "amr-01")
    # amr.name ("amr-01"), not the EAM's numeric id, is the robot's VDA
    # 5050 serial number -- it has to match what FakeRobot (standing in
    # for the real bridge) publishes and subscribes on, or no message
    # from either side ever reaches the other.
    router.register_adapter(
        Vda5050Adapter(
            robot_id=amr.name,
            name=amr.name,
            supported_capabilities=[MissionType(c.value) for c in amr.capabilities],
            home_location_id=amr.home_location_id,
            location_lookup=lambda location_id: locations_by_id[location_id],
            mqtt_client=adapter_mqtt_client,
            connectivity_timeout_s=CONNECTIVITY_TIMEOUT_S,
        )
    )

    return MissionTools(eam_gateway, graph_provider, router, audit_sink)


AMR_ROBOT_ID = "amr-01"  # the VDA 5050 serial number, matching the adapter's registration key above


def _release_dispatch_and_start_driving(
    mission_tools: MissionTools, eam_test_client: TestClient, fake_robot: FakeRobot
) -> tuple[int, MissionHandle]:
    """Common setup for both scenarios below: release the seeded visual-
    inspection work order, bring the real adapter online, dispatch it to
    amr-01, and get the mission into IN_PROGRESS -- the point at which
    the CLAUDE.md step-10 scenario says to cut the link."""
    drafts = eam_test_client.get("/api/work-orders", params={"status": "Draft"}).json()
    work_order_id = int(drafts[0]["id"])
    assert "Visual inspect" in drafts[0]["title"]  # the INSPECT_VISUAL work order amr-01 covers

    response = eam_test_client.patch(
        f"/api/work-orders/{work_order_id}/status", json={"status": "Released"}
    )
    assert response.status_code == 200

    adapter = mission_tools.router.get_adapter(AMR_ROBOT_ID)
    assert adapter is not None
    fake_robot.announce_online()
    _wait_until(lambda: adapter.capabilities().availability == RobotAvailability.IDLE)

    qualification = mission_tools.qualify_robots(work_order_id)
    handle = mission_tools.dispatch_mission(
        work_order_id,
        qualification.target_location_id,
        list(qualification.required_capabilities),
        requested_by="test-agent",
    )
    mission_tools.mark_in_progress(work_order_id)

    fake_robot.report_driving(handle.mission_id)
    _wait_until(
        lambda: (
            mission_tools.get_mission_status(handle.mission_id).status == MissionStatus.IN_PROGRESS
        )
    )

    return work_order_id, handle


def test_connectivity_loss_escalates_and_human_resumes(
    mission_tools_with_real_amr: MissionTools,
    eam_test_client: TestClient,
    robot_side_client: mqtt.Client,
) -> None:
    fake_robot = FakeRobot(robot_side_client, "robot-router-demo", "amr-01")
    work_order_id, handle = _release_dispatch_and_start_driving(
        mission_tools_with_real_amr, eam_test_client, fake_robot
    )

    # Cut the link: the robot side goes dark mid-mission, exactly like a
    # real network partition -- no more state/connection messages of any
    # kind arrive at the adapter from here on.
    robot_side_client.loop_stop()
    robot_side_client.disconnect()

    _wait_until(
        lambda: (
            mission_tools_with_real_amr.get_mission_status(handle.mission_id).status
            == MissionStatus.FAILED
        ),
        timeout=6.0,
    )
    status = mission_tools_with_real_amr.get_mission_status(handle.mission_id)
    assert status.detail is not None and "connectivity lost" in status.detail

    # What the supervise agent's own loop does on a terminal failed status
    # (agent/mission_agent.py's SUPERVISE_SYSTEM_PROMPT, step 4).
    mission_tools_with_real_amr.escalate_to_human(work_order_id, reason=status.detail)
    assert (
        eam_test_client.get(f"/api/work-orders/{work_order_id}").json()["status"] == "AwaitingHuman"
    )

    updated = mission_tools_with_real_amr.approve_escalation(work_order_id)
    assert updated.status == "InProgress"

    actions = [
        e.action
        for e in mission_tools_with_real_amr.list_audit_events_for_work_order(work_order_id)
    ]
    assert "mission.dispatch" in actions
    assert "mission.resume" in actions


def test_connectivity_loss_escalates_and_human_aborts(
    mission_tools_with_real_amr: MissionTools,
    eam_test_client: TestClient,
    robot_side_client: mqtt.Client,
) -> None:
    fake_robot = FakeRobot(robot_side_client, "robot-router-demo", "amr-01")
    work_order_id, handle = _release_dispatch_and_start_driving(
        mission_tools_with_real_amr, eam_test_client, fake_robot
    )

    robot_side_client.loop_stop()
    robot_side_client.disconnect()

    _wait_until(
        lambda: (
            mission_tools_with_real_amr.get_mission_status(handle.mission_id).status
            == MissionStatus.FAILED
        ),
        timeout=6.0,
    )
    status = mission_tools_with_real_amr.get_mission_status(handle.mission_id)

    mission_tools_with_real_amr.escalate_to_human(work_order_id, reason=status.detail or "")
    assert (
        eam_test_client.get(f"/api/work-orders/{work_order_id}").json()["status"] == "AwaitingHuman"
    )

    updated = mission_tools_with_real_amr.abort_escalation(work_order_id)
    assert updated.status == "Cancelled"

    actions = [
        e.action
        for e in mission_tools_with_real_amr.list_audit_events_for_work_order(work_order_id)
    ]
    assert "mission.dispatch" in actions
    assert "mission.abort" in actions
