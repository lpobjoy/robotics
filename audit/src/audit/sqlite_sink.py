"""Persistent, append-only audit log backed by plain sqlite3 (no ORM,
same rationale as eam/db.py). Implements the same AuditSink protocol as
InMemoryAuditSink, so nothing that writes through a sink has to change to
get durability.

"Append-only" here means what it says: this class has no update or
delete method, and nothing else in this codebase runs UPDATE or DELETE
against the audit_events table.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from audit.models import AuditEvent

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    work_order_id INTEGER,
    mission_id TEXT,
    detail TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_events_mission_id ON audit_events(mission_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_work_order_id ON audit_events(work_order_id);
"""


class SqliteAuditSink:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def record(self, event: AuditEvent) -> None:
        self._conn.execute(
            "INSERT INTO audit_events "
            "(id, timestamp, actor, action, work_order_id, mission_id, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.id,
                event.timestamp.isoformat(),
                event.actor,
                event.action,
                event.work_order_id,
                event.mission_id,
                json.dumps(event.detail),
            ),
        )
        self._conn.commit()

    def list_events(self) -> list[AuditEvent]:
        rows = self._conn.execute("SELECT * FROM audit_events ORDER BY timestamp").fetchall()
        return [_event_from_row(row) for row in rows]

    def list_events_for_mission(self, mission_id: str) -> list[AuditEvent]:
        rows = self._conn.execute(
            "SELECT * FROM audit_events WHERE mission_id = ? ORDER BY timestamp",
            (mission_id,),
        ).fetchall()
        return [_event_from_row(row) for row in rows]

    def list_events_for_work_order(self, work_order_id: int) -> list[AuditEvent]:
        rows = self._conn.execute(
            "SELECT * FROM audit_events WHERE work_order_id = ? ORDER BY timestamp",
            (work_order_id,),
        ).fetchall()
        return [_event_from_row(row) for row in rows]


def _event_from_row(row: sqlite3.Row) -> AuditEvent:
    detail: dict[str, Any] = json.loads(row["detail"])
    return AuditEvent(
        id=row["id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        actor=row["actor"],
        action=row["action"],
        work_order_id=row["work_order_id"],
        mission_id=row["mission_id"],
        detail=detail,
    )
