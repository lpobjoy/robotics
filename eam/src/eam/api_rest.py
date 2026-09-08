"""Plain REST API, for convenience alongside the OData v4 surface
(CLAUDE.md section 4.1).
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from eam.deps import DbDep
from eam.models import (
    Asset,
    Attachment,
    Location,
    Robot,
    WebhookEventType,
    WebhookSubscription,
    WebhookSubscriptionCreate,
    WorkOrder,
    WorkOrderCreate,
    WorkOrderStatus,
    WorkOrderStatusUpdate,
    is_transition_allowed,
)
from eam.webhooks import notify_work_order_released

router = APIRouter(prefix="/api")


@router.get("/locations", response_model=list[Location])
def list_locations(db: DbDep) -> list[Location]:
    return db.list_locations()


@router.get("/locations/{location_id}", response_model=Location)
def get_location(location_id: int, db: DbDep) -> Location:
    location = db.get_location(location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="location not found")
    return location


@router.get("/assets", response_model=list[Asset])
def list_assets(db: DbDep) -> list[Asset]:
    return db.list_assets()


@router.get("/assets/{asset_id}", response_model=Asset)
def get_asset(asset_id: int, db: DbDep) -> Asset:
    asset = db.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return asset


@router.get("/robots", response_model=list[Robot])
def list_robots(db: DbDep) -> list[Robot]:
    return db.list_robots()


@router.get("/robots/{robot_id}", response_model=Robot)
def get_robot(robot_id: int, db: DbDep) -> Robot:
    robot = db.get_robot(robot_id)
    if robot is None:
        raise HTTPException(status_code=404, detail="robot not found")
    return robot


@router.get("/work-orders", response_model=list[WorkOrder])
def list_work_orders(db: DbDep, status: WorkOrderStatus | None = None) -> list[WorkOrder]:
    return db.list_work_orders(status=status)


@router.get("/work-orders/{work_order_id}", response_model=WorkOrder)
def get_work_order(work_order_id: int, db: DbDep) -> WorkOrder:
    work_order = db.get_work_order(work_order_id)
    if work_order is None:
        raise HTTPException(status_code=404, detail="work order not found")
    return work_order


@router.post("/work-orders", response_model=WorkOrder, status_code=201)
def create_work_order(body: WorkOrderCreate, db: DbDep) -> WorkOrder:
    if db.get_asset(body.asset_id) is None:
        raise HTTPException(status_code=400, detail=f"asset {body.asset_id} does not exist")
    return db.create_work_order(body)


@router.patch("/work-orders/{work_order_id}/status", response_model=WorkOrder)
def update_work_order_status(
    work_order_id: int, body: WorkOrderStatusUpdate, db: DbDep
) -> WorkOrder:
    current = db.get_work_order(work_order_id)
    if current is None:
        raise HTTPException(status_code=404, detail="work order not found")
    if not is_transition_allowed(current.status, body.status):
        raise HTTPException(
            status_code=409,
            detail=(
                f"cannot transition work order from {current.status.value} "
                f"to {body.status.value}"
            ),
        )

    updated = db.set_work_order_status(work_order_id, body.status)

    if body.status == WorkOrderStatus.RELEASED:
        subscriptions = db.list_webhooks_for_event(WebhookEventType.WORK_ORDER_RELEASED)
        notify_work_order_released(subscriptions, updated)

    return updated


@router.post(
    "/work-orders/{work_order_id}/attachments", response_model=Attachment, status_code=201
)
async def upload_attachment(
    work_order_id: int, db: DbDep, file: UploadFile = File(...)
) -> Attachment:
    if db.get_work_order(work_order_id) is None:
        raise HTTPException(status_code=404, detail="work order not found")
    data = await file.read()
    return db.create_attachment(
        work_order_id=work_order_id,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )


@router.get("/work-orders/{work_order_id}/attachments", response_model=list[Attachment])
def list_attachments(work_order_id: int, db: DbDep) -> list[Attachment]:
    if db.get_work_order(work_order_id) is None:
        raise HTTPException(status_code=404, detail="work order not found")
    return db.list_attachments(work_order_id)


@router.get("/attachments/{attachment_id}")
def download_attachment(attachment_id: int, db: DbDep) -> Response:
    result = db.get_attachment_data(attachment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    attachment, data = result
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.filename}"'},
    )


@router.post("/webhooks", response_model=WebhookSubscription, status_code=201)
def create_webhook(body: WebhookSubscriptionCreate, db: DbDep) -> WebhookSubscription:
    return db.create_webhook(body)


@router.get("/webhooks", response_model=list[WebhookSubscription])
def list_webhooks(db: DbDep) -> list[WebhookSubscription]:
    return db.list_webhooks()
