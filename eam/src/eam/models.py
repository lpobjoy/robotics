"""Pydantic models for the mock EAM: locations, assets, robots, work orders,
attachments, and webhook subscriptions. See CLAUDE.md section 4.1.
"""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class MissionCapability(enum.StrEnum):
    """The three mission types the rest of the system (router, adapters)
    knows about. A work order's required_capabilities and a robot's
    capabilities are both drawn from this vocabulary so they can be
    matched directly.
    """

    INSPECT_VISUAL = "inspect_visual"
    INSPECT_THERMAL = "inspect_thermal"
    PATROL = "patrol"


class RobotEcosystem(enum.StrEnum):
    VDA5050_AMR = "vda5050_amr"
    UNITREE = "unitree"
    SPOT = "spot"


class RobotStatus(enum.StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


class WorkOrderStatus(enum.StrEnum):
    DRAFT = "Draft"
    RELEASED = "Released"
    DISPATCHED = "Dispatched"
    IN_PROGRESS = "InProgress"
    AWAITING_HUMAN = "AwaitingHuman"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


TERMINAL_STATUSES: frozenset[WorkOrderStatus] = frozenset(
    {WorkOrderStatus.COMPLETED, WorkOrderStatus.FAILED, WorkOrderStatus.CANCELLED}
)

# CLAUDE.md section 4.1: Draft -> Released -> Dispatched -> InProgress ->
# AwaitingHuman -> Completed | Failed | Cancelled. AwaitingHuman can also
# resume back into InProgress. Any non-terminal state can be cancelled.
ALLOWED_TRANSITIONS: dict[WorkOrderStatus, frozenset[WorkOrderStatus]] = {
    WorkOrderStatus.DRAFT: frozenset({WorkOrderStatus.RELEASED, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.RELEASED: frozenset(
        {WorkOrderStatus.DISPATCHED, WorkOrderStatus.CANCELLED}
    ),
    WorkOrderStatus.DISPATCHED: frozenset(
        {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED}
    ),
    WorkOrderStatus.IN_PROGRESS: frozenset(
        {
            WorkOrderStatus.AWAITING_HUMAN,
            WorkOrderStatus.COMPLETED,
            WorkOrderStatus.FAILED,
            WorkOrderStatus.CANCELLED,
        }
    ),
    WorkOrderStatus.AWAITING_HUMAN: frozenset(
        {
            WorkOrderStatus.IN_PROGRESS,
            WorkOrderStatus.FAILED,
            WorkOrderStatus.CANCELLED,
        }
    ),
    WorkOrderStatus.COMPLETED: frozenset(),
    WorkOrderStatus.FAILED: frozenset(),
    WorkOrderStatus.CANCELLED: frozenset(),
}


def is_transition_allowed(current: WorkOrderStatus, target: WorkOrderStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


class WebhookEventType(enum.StrEnum):
    WORK_ORDER_RELEASED = "work_order.released"


class LocationCreate(BaseModel):
    name: str
    description: str = ""
    x: float
    y: float


class Location(LocationCreate):
    id: int


class AssetCreate(BaseModel):
    name: str
    asset_type: str
    location_id: int
    x: float
    y: float
    criticality: str = "medium"


class Asset(AssetCreate):
    id: int


class RobotCreate(BaseModel):
    name: str
    ecosystem: RobotEcosystem
    capabilities: list[MissionCapability]
    home_location_id: int
    status: RobotStatus = RobotStatus.IDLE


class Robot(RobotCreate):
    id: int


class WorkOrderCreate(BaseModel):
    title: str
    description: str = ""
    asset_id: int
    required_capabilities: list[MissionCapability] = Field(min_length=1)
    priority: str = "normal"


class WorkOrder(WorkOrderCreate):
    id: int
    status: WorkOrderStatus = WorkOrderStatus.DRAFT
    created_at: datetime
    updated_at: datetime


class WorkOrderStatusUpdate(BaseModel):
    status: WorkOrderStatus


class Attachment(BaseModel):
    id: int
    work_order_id: int
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


class WebhookSubscriptionCreate(BaseModel):
    url: str
    event_type: WebhookEventType = WebhookEventType.WORK_ORDER_RELEASED


class WebhookSubscription(WebhookSubscriptionCreate):
    id: int
    created_at: datetime
