"""The audit event shape (CLAUDE.md section 4.7): who/what requested,
what was decided, timestamps, correlation to work order and mission.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: str
    action: str
    work_order_id: int | None = None
    mission_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
