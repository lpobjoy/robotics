from __future__ import annotations

from audit.models import AuditEvent
from audit.sqlite_sink import SqliteAuditSink


def test_record_and_list_round_trip() -> None:
    sink = SqliteAuditSink(":memory:")
    sink.record(
        AuditEvent(
            actor="router",
            action="mission.dispatch",
            work_order_id=1,
            mission_id="m-1",
            detail={"robot_id": "amr-01", "distance_m": 0.0},
        )
    )

    events = sink.list_events()
    assert len(events) == 1
    assert events[0].actor == "router"
    assert events[0].detail == {"robot_id": "amr-01", "distance_m": 0.0}


def test_events_persist_across_connections_to_the_same_file(tmp_path: object) -> None:
    path = f"{tmp_path}/audit.db"
    sink = SqliteAuditSink(path)
    sink.record(AuditEvent(actor="router", action="mission.dispatch", mission_id="m-1"))
    sink.close()

    reopened = SqliteAuditSink(path)
    assert len(reopened.list_events()) == 1


def test_events_are_ordered_by_timestamp() -> None:
    sink = SqliteAuditSink(":memory:")
    sink.record(AuditEvent(actor="router", action="mission.dispatch", mission_id="m-1"))
    sink.record(AuditEvent(actor="router", action="mission.pause", mission_id="m-1"))
    sink.record(AuditEvent(actor="router", action="mission.abort", mission_id="m-1"))

    actions = [e.action for e in sink.list_events()]
    assert actions == ["mission.dispatch", "mission.pause", "mission.abort"]


def test_correlation_by_mission_id_end_to_end() -> None:
    """Every command in one mission's lifecycle -- dispatch, pause,
    resume, abort -- must be recoverable as a single, ordered thread by
    mission_id alone (CLAUDE.md section 6, step 5: 'correlation ids end
    to end'), and never mixed up with a different mission's events."""
    sink = SqliteAuditSink(":memory:")
    sink.record(
        AuditEvent(actor="router", action="mission.dispatch", work_order_id=1, mission_id="m-1")
    )
    sink.record(AuditEvent(actor="router", action="mission.pause", mission_id="m-1"))
    sink.record(
        AuditEvent(actor="router", action="mission.dispatch", work_order_id=2, mission_id="m-2")
    )
    sink.record(AuditEvent(actor="router", action="mission.resume", mission_id="m-1"))
    sink.record(AuditEvent(actor="router", action="mission.abort", mission_id="m-1"))

    thread = sink.list_events_for_mission("m-1")
    assert [e.action for e in thread] == [
        "mission.dispatch",
        "mission.pause",
        "mission.resume",
        "mission.abort",
    ]
    assert all(e.work_order_id in (None, 1) for e in thread)

    other_thread = sink.list_events_for_mission("m-2")
    assert [e.action for e in other_thread] == ["mission.dispatch"]


def test_correlation_by_work_order_id() -> None:
    sink = SqliteAuditSink(":memory:")
    sink.record(
        AuditEvent(actor="router", action="mission.dispatch", work_order_id=7, mission_id="m-1")
    )
    sink.record(
        AuditEvent(actor="router", action="mission.dispatch", work_order_id=8, mission_id="m-2")
    )

    events = sink.list_events_for_work_order(7)
    assert len(events) == 1
    assert events[0].mission_id == "m-1"
