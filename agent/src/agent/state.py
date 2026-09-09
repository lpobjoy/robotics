"""Mission state persistence so the agent can resume mid-mission after
its own restart (CLAUDE.md section 4.3). Plain sqlite3, no ORM.

Scope note: this persists what the AGENT needs to resume -- which work
order, which mission id, what phase it reached. It does not make
router's own in-memory mission tracking durable. In this repo, router
and its (fake, for now) adapters live in the same MCP server process the
agent's MCP client connects to; a real deployment would run that server
as its own long-lived process so the agent can restart and reconnect to
the SAME router state. Real adapters and that persistent-service
deployment start at step 7+; for now this proves the agent side of the
resume mechanism, and MissionAgent (mission_agent.py) documents the gap
plainly rather than pretending full process-crash survival is built.
"""

from __future__ import annotations

import enum
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel


class MissionPhase(enum.StrEnum):
    PLANNING = "planning"
    DISPATCHED = "dispatched"
    AWAITING_HUMAN = "awaiting_human"
    DONE = "done"


class MissionState(BaseModel):
    work_order_id: int
    mission_id: str | None
    phase: MissionPhase
    updated_at: datetime


SCHEMA = """
CREATE TABLE IF NOT EXISTS mission_state (
    work_order_id INTEGER PRIMARY KEY,
    mission_id TEXT,
    phase TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class MissionStateStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def save(self, state: MissionState) -> None:
        self._conn.execute(
            "INSERT INTO mission_state (work_order_id, mission_id, phase, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(work_order_id) DO UPDATE SET "
            "mission_id = excluded.mission_id, "
            "phase = excluded.phase, "
            "updated_at = excluded.updated_at",
            (
                state.work_order_id,
                state.mission_id,
                state.phase.value,
                state.updated_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get(self, work_order_id: int) -> MissionState | None:
        row = self._conn.execute(
            "SELECT * FROM mission_state WHERE work_order_id = ?", (work_order_id,)
        ).fetchone()
        return _state_from_row(row) if row is not None else None

    def in_flight(self) -> list[MissionState]:
        """Missions not yet DONE -- what a restarted agent should resume."""
        rows = self._conn.execute(
            "SELECT * FROM mission_state WHERE phase != ?", (MissionPhase.DONE.value,)
        ).fetchall()
        return [_state_from_row(row) for row in rows]


def _state_from_row(row: sqlite3.Row) -> MissionState:
    return MissionState(
        work_order_id=row["work_order_id"],
        mission_id=row["mission_id"],
        phase=MissionPhase(row["phase"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def now() -> datetime:
    return datetime.now(UTC)
