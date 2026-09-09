from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from mcp_server.tools import MissionTools
from router.models import Mission, MissionStatus, MissionType
from router.router import NoQualifiedRobotError


def _release(eam_test_client: TestClient, work_order_id: int) -> None:
    response = eam_test_client.patch(
        f"/api/work-orders/{work_order_id}/status", json={"status": "Released"}
    )
    assert response.status_code == 200


def _first_draft_work_order_id(eam_test_client: TestClient) -> int:
    drafts = eam_test_client.get("/api/work-orders", params={"status": "Draft"}).json()
    return int(drafts[0]["id"])


def test_list_released_work_orders_is_empty_before_any_release(
    mission_tools: MissionTools,
) -> None:
    assert mission_tools.list_released_work_orders() == []


def test_list_released_work_orders_after_release(
    mission_tools: MissionTools, eam_test_client: TestClient
) -> None:
    work_order_id = _first_draft_work_order_id(eam_test_client)
    _release(eam_test_client, work_order_id)

    released = mission_tools.list_released_work_orders()
    assert [wo.id for wo in released] == [work_order_id]


def test_qualify_robots_reflects_current_seed_data(mission_tools: MissionTools) -> None:
    result = mission_tools.qualify_robots(1)
    assert len(result.qualified_robots) >= 1


def test_full_lifecycle_dispatch_to_completed(
    mission_tools: MissionTools, eam_test_client: TestClient
) -> None:
    """The step-6 acceptance test: a released work order reaches Completed
    on the fake adapter, driven entirely through MissionTools -- the same
    surface the agent gets via MCP."""
    work_order_id = _first_draft_work_order_id(eam_test_client)
    _release(eam_test_client, work_order_id)

    qualification = mission_tools.qualify_robots(work_order_id)
    best = qualification.qualified_robots[0]

    handle = mission_tools.dispatch_mission(
        work_order_id,
        qualification.target_location_id,
        list(qualification.required_capabilities),
        requested_by="test-agent",
    )
    assert (
        eam_test_client.get(f"/api/work-orders/{work_order_id}").json()["status"] == "Dispatched"
    )

    mission_tools.mark_in_progress(work_order_id)
    assert (
        eam_test_client.get(f"/api/work-orders/{work_order_id}").json()["status"] == "InProgress"
    )

    status = mission_tools.get_mission_status(handle.mission_id)
    assert status.status == MissionStatus.DISPATCHED  # the fake doesn't auto-advance

    # The fake adapter has to be told the mission finished -- a real
    # adapter would report this through its own status()/telemetry.
    fake = mission_tools.router.get_adapter(str(best.robot_id))
    assert fake is not None
    fake.complete(handle)  # type: ignore[attr-defined]

    status = mission_tools.get_mission_status(handle.mission_id)
    assert status.status == MissionStatus.COMPLETED

    mission_tools.mark_completed(work_order_id)
    assert (
        eam_test_client.get(f"/api/work-orders/{work_order_id}").json()["status"] == "Completed"
    )


def test_escalation_path_on_forced_failure(
    mission_tools: MissionTools, eam_test_client: TestClient
) -> None:
    """CLAUDE.md section 6, step 6's other acceptance test: escalation on
    a forced failure. A mission that fails goes to AwaitingHuman, not
    silently to Failed -- section 4.3: 'on any uncertainty or safety
    signal escalate to a human and wait.'"""
    work_order_id = _first_draft_work_order_id(eam_test_client)
    _release(eam_test_client, work_order_id)

    qualification = mission_tools.qualify_robots(work_order_id)
    best = qualification.qualified_robots[0]

    handle = mission_tools.dispatch_mission(
        work_order_id,
        qualification.target_location_id,
        list(qualification.required_capabilities),
        requested_by="test-agent",
    )
    mission_tools.mark_in_progress(work_order_id)

    fake = mission_tools.router.get_adapter(str(best.robot_id))
    assert fake is not None
    fake.abort(handle)  # simulate a mission failure signal -- part of FleetAdapter proper

    status = mission_tools.get_mission_status(handle.mission_id)
    assert status.status == MissionStatus.ABORTED

    mission_tools.escalate_to_human(work_order_id, reason="mission aborted unexpectedly")
    assert (
        eam_test_client.get(f"/api/work-orders/{work_order_id}").json()["status"]
        == "AwaitingHuman"
    )


def test_dispatch_with_no_idle_robot_raises(
    mission_tools: MissionTools, eam_test_client: TestClient
) -> None:
    work_order_id = _first_draft_work_order_id(eam_test_client)
    _release(eam_test_client, work_order_id)

    # Occupy every registered robot directly (bypassing the router, the
    # way a different, already-dispatched mission would) so none is idle.
    for robot_id in ("1", "2", "3"):
        adapter = mission_tools.router.get_adapter(robot_id)
        assert adapter is not None
        adapter.dispatch(
            Mission(
                work_order_id=999,
                type=MissionType.PATROL,
                target_locations=[1],
                required_capabilities=[MissionType.PATROL],
                requested_by="test-setup",
            )
        )

    with pytest.raises(NoQualifiedRobotError):
        mission_tools.dispatch_mission(
            work_order_id,
            target_location_id=1,
            required_capabilities=[MissionType.PATROL],
            requested_by="test-agent",
        )


def test_advance_fake_mission_completed(
    mission_tools: MissionTools, eam_test_client: TestClient
) -> None:
    work_order_id = _first_draft_work_order_id(eam_test_client)
    _release(eam_test_client, work_order_id)
    qualification = mission_tools.qualify_robots(work_order_id)
    best = qualification.qualified_robots[0]
    handle = mission_tools.dispatch_mission(
        work_order_id,
        qualification.target_location_id,
        list(qualification.required_capabilities),
        requested_by="test-agent",
    )

    mission_tools.advance_fake_mission(str(best.robot_id), handle.mission_id, "completed")

    assert mission_tools.get_mission_status(handle.mission_id).status == MissionStatus.COMPLETED


def test_advance_fake_mission_rejects_unknown_status(
    mission_tools: MissionTools, eam_test_client: TestClient
) -> None:
    work_order_id = _first_draft_work_order_id(eam_test_client)
    _release(eam_test_client, work_order_id)
    qualification = mission_tools.qualify_robots(work_order_id)
    best = qualification.qualified_robots[0]
    handle = mission_tools.dispatch_mission(
        work_order_id,
        qualification.target_location_id,
        list(qualification.required_capabilities),
        requested_by="test-agent",
    )

    with pytest.raises(ValueError, match="unsupported status"):
        mission_tools.advance_fake_mission(str(best.robot_id), handle.mission_id, "in_orbit")


def test_approve_escalation_resumes_and_marks_in_progress(
    mission_tools: MissionTools, eam_test_client: TestClient
) -> None:
    work_order_id = _first_draft_work_order_id(eam_test_client)
    _release(eam_test_client, work_order_id)
    qualification = mission_tools.qualify_robots(work_order_id)
    mission_tools.dispatch_mission(
        work_order_id,
        qualification.target_location_id,
        list(qualification.required_capabilities),
        requested_by="test-agent",
    )
    mission_tools.mark_in_progress(work_order_id)
    mission_tools.escalate_to_human(work_order_id, reason="uncertain")

    updated = mission_tools.approve_escalation(work_order_id)

    assert updated.status == "InProgress"
    assert any(e.action == "mission.resume" for e in mission_tools.list_audit_events())


def test_abort_escalation_aborts_and_cancels(
    mission_tools: MissionTools, eam_test_client: TestClient
) -> None:
    work_order_id = _first_draft_work_order_id(eam_test_client)
    _release(eam_test_client, work_order_id)
    qualification = mission_tools.qualify_robots(work_order_id)
    mission_tools.dispatch_mission(
        work_order_id,
        qualification.target_location_id,
        list(qualification.required_capabilities),
        requested_by="test-agent",
    )
    mission_tools.mark_in_progress(work_order_id)
    mission_tools.escalate_to_human(work_order_id, reason="uncertain")

    updated = mission_tools.abort_escalation(work_order_id)

    assert updated.status == "Cancelled"
    assert any(e.action == "mission.abort" for e in mission_tools.list_audit_events())


def test_list_audit_events_for_work_order_is_scoped(
    mission_tools: MissionTools, eam_test_client: TestClient
) -> None:
    work_order_id = _first_draft_work_order_id(eam_test_client)
    _release(eam_test_client, work_order_id)
    qualification = mission_tools.qualify_robots(work_order_id)
    mission_tools.dispatch_mission(
        work_order_id,
        qualification.target_location_id,
        list(qualification.required_capabilities),
        requested_by="test-agent",
    )

    events = mission_tools.list_audit_events_for_work_order(work_order_id)
    assert len(events) >= 1
    assert all(e.work_order_id == work_order_id for e in events)
