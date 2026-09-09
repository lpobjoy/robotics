from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import pytest
from fake_sport_service import FakeSportService
from router.models import Mission, MissionStatus, MissionType, RobotAvailability
from unitree.adapter import UnitreeAdapter
from unitree_sdk2py.go2.sport.sport_client import SportClient

LOCATIONS = {1: (0.0, 0.0), 2: (10.0, 0.0), 3: (20.0, 5.0)}


def _location_lookup(location_id: int) -> tuple[float, float]:
    return LOCATIONS[location_id]


@pytest.fixture
def adapter(sport_client: SportClient) -> Iterator[UnitreeAdapter]:
    instance = UnitreeAdapter(
        robot_id="go2-01",
        name="go2-01",
        supported_capabilities=[MissionType.INSPECT_VISUAL, MissionType.PATROL],
        home_location_id=1,
        location_lookup=_location_lookup,
        sport_client=sport_client,
    )
    yield instance
    # unitree_sdk2py's state topic uses reliable QoS: a reader left
    # registered after a test is done with it can make a *later* test's
    # publisher block on write() forever, waiting for an ack that will
    # never come. Closing it here is what keeps a fresh adapter safe to
    # create per test, the same way vda5050_amr gets a fresh mqtt.Client
    # per test.
    instance.close()


def _wait_until(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not met before timeout")


def test_offline_until_telemetry_is_seen(adapter: UnitreeAdapter) -> None:
    assert adapter.capabilities().availability == RobotAvailability.OFFLINE


def test_becomes_idle_once_telemetry_arrives(
    adapter: UnitreeAdapter, fake_sport_service: FakeSportService
) -> None:
    fake_sport_service.publish_state(position=(0.0, 0.0, 0.0))
    _wait_until(lambda: adapter.capabilities().availability == RobotAvailability.IDLE)


def test_dispatch_issues_real_standup_and_move_requests(
    adapter: UnitreeAdapter, fake_sport_service: FakeSportService
) -> None:
    fake_sport_service.publish_state(position=(0.0, 0.0, 0.0))
    _wait_until(lambda: adapter.capabilities().availability == RobotAvailability.IDLE)

    mission = Mission(
        work_order_id=1,
        type=MissionType.INSPECT_VISUAL,
        target_locations=[2],
        required_capabilities=[MissionType.INSPECT_VISUAL],
        requested_by="test",
    )
    handle = adapter.dispatch(mission)

    assert fake_sport_service.stand_up_calls == 1
    # Move() is a fire-and-forget DDS call (_CallNoReply) -- unlike
    # StandUp's blocking round trip, dispatch() returns before the fake
    # service's background reader thread has necessarily processed it.
    _wait_until(lambda: len(fake_sport_service.move_calls) == 1)
    vx, vy, vyaw = fake_sport_service.move_calls[0]
    assert vx > 0  # location 2 is due "east" of home in this test's coordinates
    assert vyaw == 0.0

    assert adapter.status(handle).status == MissionStatus.DISPATCHED
    assert adapter.capabilities().availability == RobotAvailability.BUSY


def test_status_progresses_to_completed_as_position_telemetry_approaches_target(
    adapter: UnitreeAdapter, fake_sport_service: FakeSportService
) -> None:
    fake_sport_service.publish_state(position=(0.0, 0.0, 0.0))
    _wait_until(lambda: adapter.capabilities().availability == RobotAvailability.IDLE)

    mission = Mission(
        work_order_id=2,
        type=MissionType.PATROL,
        target_locations=[2],
        required_capabilities=[MissionType.PATROL],
        requested_by="test",
    )
    handle = adapter.dispatch(mission)

    fake_sport_service.publish_state(position=(4.0, 0.0, 0.0))
    _wait_until(lambda: adapter.status(handle).status == MissionStatus.IN_PROGRESS)

    # within arrival_tolerance_m of location 2's (10, 0)
    fake_sport_service.publish_state(position=(10.0, 0.0, 0.0))
    _wait_until(lambda: adapter.status(handle).status == MissionStatus.COMPLETED)

    # A completed mission has to stay reported COMPLETED on a repeat
    # query, and free the robot up for its next dispatch -- not linger
    # as BUSY just because nothing ever explicitly cleared it.
    assert adapter.status(handle).status == MissionStatus.COMPLETED
    assert adapter.capabilities().availability == RobotAvailability.IDLE


def test_status_reports_failed_on_a_nonzero_error_code(
    adapter: UnitreeAdapter, fake_sport_service: FakeSportService
) -> None:
    fake_sport_service.publish_state(position=(0.0, 0.0, 0.0))
    _wait_until(lambda: adapter.capabilities().availability == RobotAvailability.IDLE)

    mission = Mission(
        work_order_id=3,
        type=MissionType.PATROL,
        target_locations=[3],
        required_capabilities=[MissionType.PATROL],
        requested_by="test",
    )
    handle = adapter.dispatch(mission)

    fake_sport_service.publish_state(position=(1.0, 0.0, 0.0), error_code=42)
    _wait_until(lambda: adapter.status(handle).status == MissionStatus.FAILED)
    assert "42" in (adapter.status(handle).detail or "")


def test_pause_and_resume_publish_real_stopmove_and_move_requests(
    adapter: UnitreeAdapter, fake_sport_service: FakeSportService
) -> None:
    fake_sport_service.publish_state(position=(0.0, 0.0, 0.0))
    _wait_until(lambda: adapter.capabilities().availability == RobotAvailability.IDLE)

    mission = Mission(
        work_order_id=4,
        type=MissionType.PATROL,
        target_locations=[2],
        required_capabilities=[MissionType.PATROL],
        requested_by="test",
    )
    handle = adapter.dispatch(mission)
    _wait_until(lambda: len(fake_sport_service.move_calls) == 1)

    adapter.pause(handle)
    _wait_until(lambda: fake_sport_service.stop_move_calls == 1)

    adapter.resume(handle)
    _wait_until(lambda: len(fake_sport_service.move_calls) == 2)


def test_abort_stops_and_clears_the_active_mission(
    adapter: UnitreeAdapter, fake_sport_service: FakeSportService
) -> None:
    fake_sport_service.publish_state(position=(0.0, 0.0, 0.0))
    _wait_until(lambda: adapter.capabilities().availability == RobotAvailability.IDLE)

    mission = Mission(
        work_order_id=5,
        type=MissionType.PATROL,
        target_locations=[2],
        required_capabilities=[MissionType.PATROL],
        requested_by="test",
    )
    handle = adapter.dispatch(mission)

    adapter.abort(handle)
    _wait_until(lambda: fake_sport_service.stop_move_calls == 1)
    assert adapter.status(handle).status == MissionStatus.ABORTED
    assert adapter.capabilities().availability == RobotAvailability.IDLE
