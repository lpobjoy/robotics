"""OData v4 API surface -- see eam/odata.py for what is and is not
supported. This is the dialect the target ERP suite speaks
(CLAUDE.md section 4.1); the query-option support here is intentionally
partial.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from eam.deps import DbDep
from eam.odata import (
    METADATA_XML,
    apply_filter,
    apply_select,
    collection_response,
    entity_response,
    paginate,
)

router = APIRouter(prefix="/odata/v4")

_Select = Query(default=None, alias="$select")
_Filter = Query(default=None, alias="$filter")
_Top = Query(default=None, alias="$top", ge=0)
_Skip = Query(default=0, alias="$skip", ge=0)


@router.get("/$metadata")
def metadata() -> Response:
    return Response(content=METADATA_XML, media_type="application/xml")


def _list_entities(
    request: Request,
    entity_set: str,
    items: list[Any],
    select: str | None,
    filter_: str | None,
    top: int | None,
    skip: int,
) -> dict[str, Any]:
    dicts = [item.model_dump(mode="json") for item in items]
    try:
        dicts = apply_filter(dicts, filter_)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    dicts = paginate(dicts, skip, top)
    dicts = apply_select(dicts, select)
    return collection_response(request, entity_set, dicts)


@router.get("/Locations")
def odata_list_locations(
    request: Request,
    db: DbDep,
    select: str | None = _Select,
    filter_: str | None = _Filter,
    top: int | None = _Top,
    skip: int = _Skip,
) -> dict[str, Any]:
    return _list_entities(request, "Locations", db.list_locations(), select, filter_, top, skip)


@router.get("/Locations({location_id})")
def odata_get_location(request: Request, location_id: int, db: DbDep) -> dict[str, Any]:
    location = db.get_location(location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="location not found")
    return entity_response(request, "Locations", location.model_dump(mode="json"))


@router.get("/Assets")
def odata_list_assets(
    request: Request,
    db: DbDep,
    select: str | None = _Select,
    filter_: str | None = _Filter,
    top: int | None = _Top,
    skip: int = _Skip,
) -> dict[str, Any]:
    return _list_entities(request, "Assets", db.list_assets(), select, filter_, top, skip)


@router.get("/Assets({asset_id})")
def odata_get_asset(request: Request, asset_id: int, db: DbDep) -> dict[str, Any]:
    asset = db.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return entity_response(request, "Assets", asset.model_dump(mode="json"))


@router.get("/Robots")
def odata_list_robots(
    request: Request,
    db: DbDep,
    select: str | None = _Select,
    filter_: str | None = _Filter,
    top: int | None = _Top,
    skip: int = _Skip,
) -> dict[str, Any]:
    return _list_entities(request, "Robots", db.list_robots(), select, filter_, top, skip)


@router.get("/Robots({robot_id})")
def odata_get_robot(request: Request, robot_id: int, db: DbDep) -> dict[str, Any]:
    robot = db.get_robot(robot_id)
    if robot is None:
        raise HTTPException(status_code=404, detail="robot not found")
    return entity_response(request, "Robots", robot.model_dump(mode="json"))


@router.get("/WorkOrders")
def odata_list_work_orders(
    request: Request,
    db: DbDep,
    select: str | None = _Select,
    filter_: str | None = _Filter,
    top: int | None = _Top,
    skip: int = _Skip,
) -> dict[str, Any]:
    return _list_entities(request, "WorkOrders", db.list_work_orders(), select, filter_, top, skip)


@router.get("/WorkOrders({work_order_id})")
def odata_get_work_order(request: Request, work_order_id: int, db: DbDep) -> dict[str, Any]:
    work_order = db.get_work_order(work_order_id)
    if work_order is None:
        raise HTTPException(status_code=404, detail="work order not found")
    return entity_response(request, "WorkOrders", work_order.model_dump(mode="json"))
