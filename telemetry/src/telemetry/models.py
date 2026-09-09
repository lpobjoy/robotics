"""Canonical fleet telemetry messages (CLAUDE.md section 4.6): robot
state, position, battery, and inspection images published on a stable
topic scheme, regardless of which adapter ecosystem the robot belongs
to. This is deliberately separate from any adapter's native protocol
(e.g. VDA 5050's own state/visualization topics) -- it is the normalized
view the rest of the fleet (and, eventually, the console) reads,
matching the "the business system never has to know which robot did it"
framing in CLAUDE.md section 3.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RobotStateEvent(BaseModel):
    robot_id: str
    timestamp: datetime
    battery_charge: float | None = None
    driving: bool | None = None
    status: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ImageEvent(BaseModel):
    robot_id: str
    work_order_id: int
    mission_id: str
    filename: str
    content_type: str = "image/jpeg"
    image_base64: str


class FleetEvent(BaseModel):
    robot_id: str
    timestamp: datetime
    event_type: str
    detail: dict[str, Any] = Field(default_factory=dict)
