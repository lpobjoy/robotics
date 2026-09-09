"""The AuditSink interface routes and other callers write through.

This module only has the in-memory sink -- enough for step 4's "audit
hooks" requirement (CLAUDE.md section 6). The append-only, persistent
implementation (with actor identity and correlation ids wired end to end)
is step 5's job; it will implement this same Protocol so nothing upstream
has to change.
"""

from __future__ import annotations

from typing import Protocol

from audit.models import AuditEvent


class AuditSink(Protocol):
    def record(self, event: AuditEvent) -> None: ...


class InMemoryAuditSink:
    """Keeps every recorded event in a list. Used by step 4's router
    tests, and as the default when no sink is given -- audit-ing to
    nowhere durable is still audit-ing, just not yet durable.
    """

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)
