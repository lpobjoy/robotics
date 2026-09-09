"""Time-series store for robot state and fleet events. Plain sqlite3,
no ORM, indexed on (robot_id, timestamp). TimescaleDB is the documented
production-shaped swap (CLAUDE.md section 4.6); not needed at this
demo's scale ("do not over-build").
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from telemetry.models import FleetEvent, RobotStateEvent

SCHEMA = """
CREATE TABLE IF NOT EXISTS robot_state_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    robot_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    battery_charge REAL,
    driving INTEGER,
    status TEXT,
    extra TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_robot_state_robot_time
    ON robot_state_history(robot_id, timestamp);

CREATE TABLE IF NOT EXISTS fleet_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    robot_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fleet_events_robot_time
    ON fleet_events(robot_id, timestamp);
"""


class TelemetryStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def record_state(self, event: RobotStateEvent) -> None:
        self._conn.execute(
            "INSERT INTO robot_state_history "
            "(robot_id, timestamp, battery_charge, driving, status, extra) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.robot_id,
                event.timestamp.isoformat(),
                event.battery_charge,
                None if event.driving is None else int(event.driving),
                event.status,
                json.dumps(event.extra),
            ),
        )
        self._conn.commit()

    def history_for_robot(self, robot_id: str, limit: int = 100) -> list[RobotStateEvent]:
        rows = self._conn.execute(
            "SELECT * FROM robot_state_history WHERE robot_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (robot_id, limit),
        ).fetchall()
        return [_state_from_row(row) for row in rows]

    def latest_for_robot(self, robot_id: str) -> RobotStateEvent | None:
        history = self.history_for_robot(robot_id, limit=1)
        return history[0] if history else None

    def record_event(self, event: FleetEvent) -> None:
        self._conn.execute(
            "INSERT INTO fleet_events (robot_id, timestamp, event_type, detail) "
            "VALUES (?, ?, ?, ?)",
            (
                event.robot_id,
                event.timestamp.isoformat(),
                event.event_type,
                json.dumps(event.detail),
            ),
        )
        self._conn.commit()

    def events_for_robot(self, robot_id: str, limit: int = 100) -> list[FleetEvent]:
        rows = self._conn.execute(
            "SELECT * FROM fleet_events WHERE robot_id = ? ORDER BY timestamp DESC LIMIT ?",
            (robot_id, limit),
        ).fetchall()
        return [_event_from_row(row) for row in rows]


def _state_from_row(row: sqlite3.Row) -> RobotStateEvent:
    extra: dict[str, Any] = json.loads(row["extra"])
    return RobotStateEvent(
        robot_id=row["robot_id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        battery_charge=row["battery_charge"],
        driving=None if row["driving"] is None else bool(row["driving"]),
        status=row["status"],
        extra=extra,
    )


def _event_from_row(row: sqlite3.Row) -> FleetEvent:
    detail: dict[str, Any] = json.loads(row["detail"])
    return FleetEvent(
        robot_id=row["robot_id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        event_type=row["event_type"],
        detail=detail,
    )
