from __future__ import annotations

from datetime import UTC, datetime

from telemetry.models import FleetEvent, RobotStateEvent
from telemetry.store import TelemetryStore


def test_record_and_retrieve_state() -> None:
    store = TelemetryStore(":memory:")
    store.record_state(
        RobotStateEvent(
            robot_id="amr-01",
            timestamp=datetime.now(UTC),
            battery_charge=88.5,
            driving=True,
            status="in_progress",
        )
    )

    latest = store.latest_for_robot("amr-01")
    assert latest is not None
    assert latest.battery_charge == 88.5
    assert latest.driving is True
    assert latest.status == "in_progress"


def test_history_is_ordered_most_recent_first() -> None:
    store = TelemetryStore(":memory:")
    for i, status in enumerate(["dispatched", "in_progress", "completed"]):
        store.record_state(
            RobotStateEvent(
                robot_id="amr-01",
                timestamp=datetime(2026, 1, 1, 0, 0, i, tzinfo=UTC),
                status=status,
            )
        )

    history = store.history_for_robot("amr-01")
    assert [e.status for e in history] == ["completed", "in_progress", "dispatched"]


def test_history_is_scoped_per_robot() -> None:
    store = TelemetryStore(":memory:")
    store.record_state(
        RobotStateEvent(robot_id="amr-01", timestamp=datetime.now(UTC), status="idle")
    )
    store.record_state(
        RobotStateEvent(robot_id="spot-01", timestamp=datetime.now(UTC), status="busy")
    )

    assert len(store.history_for_robot("amr-01")) == 1
    assert len(store.history_for_robot("spot-01")) == 1
    assert store.history_for_robot("does-not-exist") == []


def test_latest_for_unknown_robot_is_none() -> None:
    store = TelemetryStore(":memory:")
    assert store.latest_for_robot("nope") is None


def test_extra_fields_round_trip() -> None:
    store = TelemetryStore(":memory:")
    store.record_state(
        RobotStateEvent(
            robot_id="amr-01",
            timestamp=datetime.now(UTC),
            extra={"position": {"x": 1.0, "y": 2.0}},
        )
    )
    latest = store.latest_for_robot("amr-01")
    assert latest is not None
    assert latest.extra == {"position": {"x": 1.0, "y": 2.0}}


def test_record_and_retrieve_events() -> None:
    store = TelemetryStore(":memory:")
    store.record_event(
        FleetEvent(
            robot_id="amr-01",
            timestamp=datetime.now(UTC),
            event_type="mission.completed",
            detail={"mission_id": "abc-123"},
        )
    )

    events = store.events_for_robot("amr-01")
    assert len(events) == 1
    assert events[0].event_type == "mission.completed"
    assert events[0].detail == {"mission_id": "abc-123"}


def test_events_persist_across_connections(tmp_path: object) -> None:
    path = f"{tmp_path}/telemetry.db"
    store = TelemetryStore(path)
    store.record_state(RobotStateEvent(robot_id="amr-01", timestamp=datetime.now(UTC)))
    store.close()

    reopened = TelemetryStore(path)
    assert len(reopened.history_for_robot("amr-01")) == 1
