from __future__ import annotations

from audit.models import AuditEvent
from audit.sink import InMemoryAuditSink


def test_records_events_in_order() -> None:
    sink = InMemoryAuditSink()
    sink.record(AuditEvent(actor="router", action="mission.dispatch", work_order_id=1))
    sink.record(AuditEvent(actor="router", action="mission.abort", work_order_id=1))

    assert [e.action for e in sink.events] == ["mission.dispatch", "mission.abort"]


def test_every_event_has_an_actor_and_a_generated_id() -> None:
    sink = InMemoryAuditSink()
    sink.record(AuditEvent(actor="human:lewis", action="escalation.approve"))

    event = sink.events[0]
    assert event.actor == "human:lewis"
    assert event.id
    assert event.timestamp is not None
