from __future__ import annotations

import pytest
from audit.sink import InMemoryAuditSink
from router.fake_adapter import FakeAdapter
from router.models import Mission, MissionStatus, MissionType
from router.router import NoQualifiedRobotError, Router, UnknownMissionError
from worldmodel.graph import build_graph
from worldmodel.models import Location, LocationLink

LOCATIONS = [
    Location(id=1, name="Pump House", x=0.0, y=0.0),
    Location(id=2, name="Valve Yard", x=30.0, y=0.0),
    Location(id=3, name="Tank Farm", x=60.0, y=0.0),
]
LINKS = [
    LocationLink(id=1, from_location_id=1, to_location_id=2, distance_m=30.0),
    LocationLink(id=2, from_location_id=2, to_location_id=1, distance_m=30.0),
    LocationLink(id=3, from_location_id=2, to_location_id=3, distance_m=30.0),
    LocationLink(id=4, from_location_id=3, to_location_id=2, distance_m=30.0),
]


def _graph() -> object:
    return build_graph(LOCATIONS, LINKS, [], [], [])


def _mission(**overrides: object) -> Mission:
    defaults: dict[str, object] = {
        "work_order_id": 1,
        "type": MissionType.INSPECT_VISUAL,
        "target_locations": [1],
        "required_capabilities": [MissionType.INSPECT_VISUAL],
        "requested_by": "test",
    }
    defaults.update(overrides)
    return Mission.model_validate(defaults)


def test_released_work_order_becomes_a_dispatched_mission_on_the_fake() -> None:
    """CLAUDE.md section 6, step 4's acceptance test."""
    audit = InMemoryAuditSink()
    router = Router(_graph(), audit_sink=audit)
    fake = FakeAdapter(
        robot_id="amr-01",
        name="amr-01",
        ecosystem="vda5050_amr",
        supported_capabilities=[MissionType.INSPECT_VISUAL],
        location_id=1,
    )
    router.register_adapter(fake)

    mission = _mission()
    handle = router.dispatch(mission)

    assert handle.robot_id == "amr-01"
    report = router.status(mission.id)
    assert report.status == MissionStatus.DISPATCHED
    assert fake.capabilities().availability.value == "busy"


def test_dispatch_records_an_audit_event_before_calling_the_adapter() -> None:
    audit = InMemoryAuditSink()
    router = Router(_graph(), audit_sink=audit)
    fake = FakeAdapter("amr-01", "amr-01", "vda5050_amr", [MissionType.INSPECT_VISUAL], 1)
    router.register_adapter(fake)

    router.dispatch(_mission())

    dispatch_events = [e for e in audit.events if e.action == "mission.dispatch"]
    assert len(dispatch_events) == 1
    assert dispatch_events[0].detail["robot_id"] == "amr-01"
    assert dispatch_events[0].detail["distance_m"] == 0.0


def test_selection_picks_capability_match_over_incapable_robot() -> None:
    router = Router(_graph())
    incapable = FakeAdapter("spot-01", "spot-01", "spot", [MissionType.PATROL], 1)
    capable = FakeAdapter("amr-01", "amr-01", "vda5050_amr", [MissionType.INSPECT_VISUAL], 1)
    router.register_adapter(incapable)
    router.register_adapter(capable)

    handle = router.dispatch(_mission())

    assert handle.robot_id == "amr-01"


def test_selection_skips_busy_robot() -> None:
    router = Router(_graph())
    busy = FakeAdapter("amr-01", "amr-01", "vda5050_amr", [MissionType.INSPECT_VISUAL], 1)
    idle = FakeAdapter("go2-01", "go2-01", "unitree", [MissionType.INSPECT_VISUAL], 1)
    router.register_adapter(busy)
    router.register_adapter(idle)

    busy.dispatch(_mission(work_order_id=999))  # occupy it directly, bypassing the router

    handle = router.dispatch(_mission())

    assert handle.robot_id == "go2-01"


def test_selection_picks_cheapest_reachable_distance() -> None:
    router = Router(_graph())
    far = FakeAdapter("spot-01", "spot-01", "spot", [MissionType.INSPECT_VISUAL], 3)  # 60m
    near = FakeAdapter("amr-01", "amr-01", "vda5050_amr", [MissionType.INSPECT_VISUAL], 2)  # 30m
    router.register_adapter(far)
    router.register_adapter(near)

    handle = router.dispatch(_mission())

    assert handle.robot_id == "amr-01"


def test_no_qualified_robot_raises_and_is_audited() -> None:
    audit = InMemoryAuditSink()
    router = Router(_graph(), audit_sink=audit)
    router.register_adapter(
        FakeAdapter("spot-01", "spot-01", "spot", [MissionType.PATROL], 1)
    )

    with pytest.raises(NoQualifiedRobotError):
        router.dispatch(_mission())

    assert any(e.action == "mission.dispatch.no_candidate" for e in audit.events)


def test_status_on_unknown_mission_raises() -> None:
    router = Router(_graph())
    with pytest.raises(UnknownMissionError):
        router.status("does-not-exist")


def test_pause_resume_abort_go_through_audit_before_the_adapter() -> None:
    audit = InMemoryAuditSink()
    router = Router(_graph(), audit_sink=audit)
    fake = FakeAdapter("amr-01", "amr-01", "vda5050_amr", [MissionType.INSPECT_VISUAL], 1)
    router.register_adapter(fake)
    mission = _mission()
    router.dispatch(mission)

    router.pause(mission.id)
    assert router.status(mission.id).status == MissionStatus.PAUSED
    assert any(e.action == "mission.pause" for e in audit.events)

    router.resume(mission.id)
    assert router.status(mission.id).status == MissionStatus.IN_PROGRESS
    assert any(e.action == "mission.resume" for e in audit.events)

    router.abort(mission.id)
    assert router.status(mission.id).status == MissionStatus.ABORTED
    assert any(e.action == "mission.abort" for e in audit.events)
