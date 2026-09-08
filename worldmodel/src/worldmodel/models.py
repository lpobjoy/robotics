"""Data shapes worldmodel needs from an EAM-like system.

Deliberately not imported from the eam package: worldmodel is meant to
work against anything that returns this shape over HTTP (CLAUDE.md
section 4.2 calls this "the productisable asset in the story"), not
specifically against the mock that happens to live in this repo. Fields
are kept to the minimum the graph and its query actually use.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel


class MissionCapability(enum.StrEnum):
    INSPECT_VISUAL = "inspect_visual"
    INSPECT_THERMAL = "inspect_thermal"
    PATROL = "patrol"


class Location(BaseModel):
    id: int
    name: str
    x: float
    y: float


class LocationLink(BaseModel):
    id: int
    from_location_id: int
    to_location_id: int
    distance_m: float


class Asset(BaseModel):
    id: int
    name: str
    location_id: int


class Robot(BaseModel):
    id: int
    name: str
    capabilities: list[MissionCapability]
    home_location_id: int


class WorkOrder(BaseModel):
    id: int
    title: str
    asset_id: int
    required_capabilities: list[MissionCapability]
    status: str
