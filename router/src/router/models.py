"""Mission schema and the FleetAdapter protocol (CLAUDE.md section 4.4).

One extension beyond what section 4.4 lists explicitly: RobotDescriptor
(the return type of FleetAdapter.capabilities()) carries availability and
current location, not just a bare capability list. The spec names
"capabilities()" as the first protocol method and separately requires
selection on "capability match first, then availability, then a trivial
cost (distance)" -- answering all three needs one descriptor richer than
a plain list, so that's what capabilities() returns here. Stated plainly
per CLAUDE.md's honesty rule, not silently assumed.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Iterator
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field


class MissionType(enum.StrEnum):
    INSPECT_VISUAL = "inspect_visual"
    INSPECT_THERMAL = "inspect_thermal"
    PATROL = "patrol"


class RobotAvailability(enum.StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


class MissionStatus(enum.StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class Mission(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    work_order_id: int
    type: MissionType
    target_locations: list[int] = Field(min_length=1)
    required_capabilities: list[MissionType] = Field(min_length=1)
    constraints: dict[str, Any] = Field(default_factory=dict)
    requested_by: str
    approval_chain: list[str] = Field(default_factory=list)

    @property
    def primary_target_location_id(self) -> int:
        return self.target_locations[0]


class RobotDescriptor(BaseModel):
    robot_id: str
    name: str
    ecosystem: str
    supported_capabilities: list[MissionType]
    availability: RobotAvailability
    location_id: int


class MissionHandle(BaseModel):
    mission_id: str
    robot_id: str
    ecosystem: str


class MissionStatusReport(BaseModel):
    mission_id: str
    status: MissionStatus
    detail: str = ""


class TelemetryEvent(BaseModel):
    robot_id: str
    timestamp: datetime
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)


class FleetAdapter(Protocol):
    """One adapter instance represents one robot. capabilities() is
    called on every dispatch decision, so it must be cheap and reflect
    current state, not a cached snapshot from startup.
    """

    def capabilities(self) -> RobotDescriptor: ...
    def dispatch(self, mission: Mission) -> MissionHandle: ...
    def status(self, handle: MissionHandle) -> MissionStatusReport: ...
    def pause(self, handle: MissionHandle) -> None: ...
    def resume(self, handle: MissionHandle) -> None: ...
    def abort(self, handle: MissionHandle) -> None: ...
    def telemetry_stream(self) -> Iterator[TelemetryEvent]: ...
