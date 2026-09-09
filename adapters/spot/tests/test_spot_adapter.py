from __future__ import annotations

from bosdyn.api.graph_nav import graph_nav_pb2
from bosdyn.client.graph_nav import GraphNavClient
from fake_graph_nav_service import FakeGraphNavService
from router.models import Mission, MissionStatus, MissionType, RobotAvailability
from spot.adapter import SpotAdapter

WAYPOINTS = {1: "wp-home", 2: "wp-pump-house", 3: "wp-tank-farm"}


def _waypoint_lookup(location_id: int) -> str:
    return WAYPOINTS[location_id]


def _make_adapter(graph_nav_client: GraphNavClient) -> SpotAdapter:
    return SpotAdapter(
        robot_id="spot-01",
        name="spot-01",
        supported_capabilities=[MissionType.INSPECT_VISUAL, MissionType.INSPECT_THERMAL],
        home_location_id=1,
        waypoint_lookup=_waypoint_lookup,
        graph_nav_client=graph_nav_client,
    )


def _mission(work_order_id: int, target_location_id: int) -> Mission:
    return Mission(
        work_order_id=work_order_id,
        type=MissionType.INSPECT_VISUAL,
        target_locations=[target_location_id],
        required_capabilities=[MissionType.INSPECT_VISUAL],
        requested_by="test",
    )


def test_idle_before_any_dispatch(graph_nav_client: GraphNavClient) -> None:
    adapter = _make_adapter(graph_nav_client)
    assert adapter.capabilities().availability == RobotAvailability.IDLE


def test_dispatch_issues_a_real_navigate_to_request(
    graph_nav_client: GraphNavClient, fake_graph_nav_service: FakeGraphNavService
) -> None:
    adapter = _make_adapter(graph_nav_client)
    handle = adapter.dispatch(_mission(1, 2))

    assert fake_graph_nav_service.navigate_to_calls == ["wp-pump-house"]
    assert adapter.status(handle).status == MissionStatus.IN_PROGRESS
    assert adapter.capabilities().availability == RobotAvailability.BUSY


def test_status_reports_completed_on_reached_goal(
    graph_nav_client: GraphNavClient, fake_graph_nav_service: FakeGraphNavService
) -> None:
    adapter = _make_adapter(graph_nav_client)
    handle = adapter.dispatch(_mission(2, 2))

    fake_graph_nav_service.feedback_status = (
        graph_nav_pb2.NavigationFeedbackResponse.STATUS_REACHED_GOAL
    )
    assert adapter.status(handle).status == MissionStatus.COMPLETED

    # Stays COMPLETED on a repeat query, and frees the robot back up --
    # nothing should leave it looking BUSY forever.
    assert adapter.status(handle).status == MissionStatus.COMPLETED
    assert adapter.capabilities().availability == RobotAvailability.IDLE


def test_status_reports_failed_on_a_route_error(
    graph_nav_client: GraphNavClient, fake_graph_nav_service: FakeGraphNavService
) -> None:
    adapter = _make_adapter(graph_nav_client)
    handle = adapter.dispatch(_mission(3, 3))

    fake_graph_nav_service.feedback_status = graph_nav_pb2.NavigationFeedbackResponse.STATUS_STUCK
    status = adapter.status(handle)
    assert status.status == MissionStatus.FAILED
    assert "STATUS_STUCK" in (status.detail or "")
    assert adapter.capabilities().availability == RobotAvailability.IDLE


def test_abort_reports_aborted_and_frees_the_robot(
    graph_nav_client: GraphNavClient, fake_graph_nav_service: FakeGraphNavService
) -> None:
    adapter = _make_adapter(graph_nav_client)
    handle = adapter.dispatch(_mission(4, 2))

    adapter.abort(handle)
    assert adapter.status(handle).status == MissionStatus.ABORTED
    assert adapter.capabilities().availability == RobotAvailability.IDLE


def test_resume_issues_another_real_navigate_to_request(
    graph_nav_client: GraphNavClient, fake_graph_nav_service: FakeGraphNavService
) -> None:
    adapter = _make_adapter(graph_nav_client)
    handle = adapter.dispatch(_mission(5, 3))
    assert fake_graph_nav_service.navigate_to_calls == ["wp-tank-farm"]

    adapter.resume(handle)
    assert fake_graph_nav_service.navigate_to_calls == ["wp-tank-farm", "wp-tank-farm"]


def test_resume_after_abort_does_nothing(
    graph_nav_client: GraphNavClient, fake_graph_nav_service: FakeGraphNavService
) -> None:
    adapter = _make_adapter(graph_nav_client)
    handle = adapter.dispatch(_mission(6, 2))
    adapter.abort(handle)

    adapter.resume(handle)
    assert fake_graph_nav_service.navigate_to_calls == ["wp-pump-house"]  # no second call
