"""A small, deliberately partial slice of OData v4: the response envelope,
$metadata, and the four query options this demo actually needs
($select, $filter, $top, $skip). This is not a spec-compliant OData
server -- $filter supports only `field eq value`, and there is no
$expand, $orderby, or $count. See CLAUDE.md section 4.1: the point is to
speak the same dialect as the target ERP suite for the entity sets this
repo touches, not to reimplement the OData spec.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request

METADATA_XML = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="4.0" xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">
  <edmx:DataServices>
    <Schema Namespace="EAM" xmlns="http://docs.oasis-open.org/odata/ns/edm">
      <EntityType Name="Location">
        <Key><PropertyRef Name="id"/></Key>
        <Property Name="id" Type="Edm.Int32" Nullable="false"/>
        <Property Name="name" Type="Edm.String"/>
        <Property Name="description" Type="Edm.String"/>
        <Property Name="x" Type="Edm.Double"/>
        <Property Name="y" Type="Edm.Double"/>
      </EntityType>
      <EntityType Name="Asset">
        <Key><PropertyRef Name="id"/></Key>
        <Property Name="id" Type="Edm.Int32" Nullable="false"/>
        <Property Name="name" Type="Edm.String"/>
        <Property Name="asset_type" Type="Edm.String"/>
        <Property Name="location_id" Type="Edm.Int32"/>
        <Property Name="x" Type="Edm.Double"/>
        <Property Name="y" Type="Edm.Double"/>
        <Property Name="criticality" Type="Edm.String"/>
      </EntityType>
      <EntityType Name="Robot">
        <Key><PropertyRef Name="id"/></Key>
        <Property Name="id" Type="Edm.Int32" Nullable="false"/>
        <Property Name="name" Type="Edm.String"/>
        <Property Name="ecosystem" Type="Edm.String"/>
        <Property Name="capabilities" Type="Collection(Edm.String)"/>
        <Property Name="status" Type="Edm.String"/>
        <Property Name="home_location_id" Type="Edm.Int32"/>
      </EntityType>
      <EntityType Name="WorkOrder">
        <Key><PropertyRef Name="id"/></Key>
        <Property Name="id" Type="Edm.Int32" Nullable="false"/>
        <Property Name="title" Type="Edm.String"/>
        <Property Name="description" Type="Edm.String"/>
        <Property Name="asset_id" Type="Edm.Int32"/>
        <Property Name="required_capabilities" Type="Collection(Edm.String)"/>
        <Property Name="status" Type="Edm.String"/>
        <Property Name="priority" Type="Edm.String"/>
        <Property Name="created_at" Type="Edm.DateTimeOffset"/>
        <Property Name="updated_at" Type="Edm.DateTimeOffset"/>
      </EntityType>
      <EntityContainer Name="Container">
        <EntitySet Name="Locations" EntityType="EAM.Location"/>
        <EntitySet Name="Assets" EntityType="EAM.Asset"/>
        <EntitySet Name="Robots" EntityType="EAM.Robot"/>
        <EntitySet Name="WorkOrders" EntityType="EAM.WorkOrder"/>
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>
"""


def apply_filter(items: list[dict[str, Any]], filter_expr: str | None) -> list[dict[str, Any]]:
    if not filter_expr:
        return items

    parts = filter_expr.split(" ", 2)
    if len(parts) != 3 or parts[1] != "eq":
        raise ValueError(
            f"unsupported $filter expression: {filter_expr!r} "
            "(only 'field eq value' is supported)"
        )
    field, _, raw_value = parts
    value = raw_value.strip("'")

    def matches(item: dict[str, Any]) -> bool:
        item_value = item.get(field)
        if isinstance(item_value, list):
            return value in item_value
        return str(item_value) == value

    return [item for item in items if matches(item)]


def apply_select(items: list[dict[str, Any]], select_expr: str | None) -> list[dict[str, Any]]:
    if not select_expr:
        return items
    fields = {f.strip() for f in select_expr.split(",")}
    return [{k: v for k, v in item.items() if k in fields} for item in items]


def paginate(items: list[dict[str, Any]], skip: int, top: int | None) -> list[dict[str, Any]]:
    sliced = items[skip:]
    if top is not None:
        sliced = sliced[:top]
    return sliced


def collection_response(
    request: Request, entity_set: str, items: list[dict[str, Any]]
) -> dict[str, Any]:
    base = str(request.base_url).rstrip("/")
    return {
        "@odata.context": f"{base}/odata/v4/$metadata#{entity_set}",
        "value": items,
    }


def entity_response(
    request: Request, entity_set: str, item: dict[str, Any]
) -> dict[str, Any]:
    base = str(request.base_url).rstrip("/")
    return {
        "@odata.context": f"{base}/odata/v4/$metadata#{entity_set}/$entity",
        **item,
    }
