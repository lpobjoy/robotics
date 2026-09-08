"""Seed data: one small industrial site (a pumping station), ~20 assets
with coordinates, ~5 work orders, 3 robots with capability descriptors
(CLAUDE.md section 4.1).

Coordinates are simple site-local x/y in metres, not lat/lon -- there is no
GPS involved anywhere downstream (Nav2 in adapters/vda5050_amr works in a
local frame), so real-world coordinates would be a fiction.
"""

from __future__ import annotations

import math

from eam.db import Database
from eam.models import (
    AssetCreate,
    LocationCreate,
    LocationLinkCreate,
    MissionCapability,
    RobotCreate,
    RobotEcosystem,
    WorkOrderCreate,
    WorkOrderStatus,
)

LOCATIONS: list[tuple[str, str, float, float]] = [
    ("Pump House", "Main pump hall", 0.0, 0.0),
    ("Valve Yard", "Outdoor valve manifolds", 40.0, 5.0),
    ("Tank Farm", "Chemical storage tanks", 80.0, 0.0),
    ("Intake", "River intake structure", -30.0, 20.0),
    ("Outfall", "Treated discharge point", 120.0, 30.0),
    ("Control Room", "SCADA and electrical room", 10.0, -20.0),
    ("Perimeter", "Site fence line", 0.0, 60.0),
]

# Direct, walkable paths between locations -- worldmodel's
# Location -REACHABLE_FROM-> Location edges (CLAUDE.md section 4.2).
# Not every pair of locations is linked: a real site has corridors and
# doors, not a fully-connected point cloud. Distance is computed from the
# coordinates above rather than stated separately, so the two can't drift
# apart. Pump House is the hub; Valve Yard <-> Control Room gives one
# alternate route instead of a bare spanning tree.
LOCATION_LINKS: list[tuple[str, str]] = [
    ("Pump House", "Control Room"),
    ("Pump House", "Valve Yard"),
    ("Pump House", "Intake"),
    ("Pump House", "Perimeter"),
    ("Valve Yard", "Tank Farm"),
    ("Valve Yard", "Control Room"),
    ("Tank Farm", "Outfall"),
]

# (name, asset_type, location name, x, y, criticality) -- 20 assets.
ASSETS: list[tuple[str, str, str, float, float, str]] = [
    ("Pump P-101", "pump", "Pump House", 1.0, 1.0, "high"),
    ("Pump P-102", "pump", "Pump House", 3.0, 1.0, "high"),
    ("Pump P-103", "pump", "Pump House", 5.0, 1.0, "medium"),
    ("Motor M-101", "motor", "Pump House", 1.0, 3.0, "high"),
    ("Motor M-102", "motor", "Pump House", 3.0, 3.0, "medium"),
    ("Valve V-201", "valve", "Valve Yard", 41.0, 6.0, "medium"),
    ("Valve V-202", "valve", "Valve Yard", 43.0, 6.0, "medium"),
    ("Valve V-203", "valve", "Valve Yard", 45.0, 6.0, "low"),
    ("Manifold MF-201", "manifold", "Valve Yard", 47.0, 8.0, "medium"),
    ("Tank T-301", "tank", "Tank Farm", 81.0, 1.0, "high"),
    ("Tank T-302", "tank", "Tank Farm", 85.0, 1.0, "high"),
    ("Tank T-303", "tank", "Tank Farm", 89.0, 1.0, "medium"),
    ("Bund Wall BW-301", "containment", "Tank Farm", 83.0, -2.0, "high"),
    ("Intake Screen SC-401", "screen", "Intake", -29.0, 21.0, "medium"),
    ("Intake Pump IP-401", "pump", "Intake", -27.0, 22.0, "high"),
    ("Outfall Diffuser OD-501", "diffuser", "Outfall", 121.0, 31.0, "low"),
    ("Flow Meter FM-501", "instrument", "Outfall", 123.0, 32.0, "medium"),
    ("Switchgear SG-601", "electrical", "Control Room", 11.0, -21.0, "high"),
    ("SCADA Panel SP-601", "electrical", "Control Room", 13.0, -21.0, "medium"),
    ("Perimeter Camera Mast CM-701", "sensor", "Perimeter", 1.0, 61.0, "low"),
]

# (name, ecosystem, capabilities, home location name)
ROBOTS: list[tuple[str, RobotEcosystem, list[MissionCapability], str]] = [
    (
        "amr-01",
        RobotEcosystem.VDA5050_AMR,
        [MissionCapability.INSPECT_VISUAL, MissionCapability.PATROL],
        "Pump House",
    ),
    (
        "go2-01",
        RobotEcosystem.UNITREE,
        [
            MissionCapability.INSPECT_VISUAL,
            MissionCapability.INSPECT_THERMAL,
            MissionCapability.PATROL,
        ],
        "Valve Yard",
    ),
    (
        "spot-01",
        RobotEcosystem.SPOT,
        [MissionCapability.INSPECT_VISUAL, MissionCapability.INSPECT_THERMAL],
        "Tank Farm",
    ),
]

# (title, asset name, required capabilities, priority, initial status).
# Four sit in Draft, ready to be released by whoever is driving the demo;
# one is seeded as historical Completed data so the API has something to
# show beyond a pile of Drafts.
WORK_ORDERS: list[
    tuple[str, str, list[MissionCapability], str, WorkOrderStatus]
] = [
    (
        "Visual inspect Pump P-101 for leaks",
        "Pump P-101",
        [MissionCapability.INSPECT_VISUAL],
        "high",
        WorkOrderStatus.DRAFT,
    ),
    (
        "Thermal scan Switchgear SG-601",
        "Switchgear SG-601",
        [MissionCapability.INSPECT_THERMAL],
        "high",
        WorkOrderStatus.DRAFT,
    ),
    (
        "Routine patrol of Valve Yard",
        "Valve V-201",
        [MissionCapability.PATROL],
        "normal",
        WorkOrderStatus.DRAFT,
    ),
    (
        "Visual inspect Tank T-301 bund wall",
        "Bund Wall BW-301",
        [MissionCapability.INSPECT_VISUAL],
        "normal",
        WorkOrderStatus.DRAFT,
    ),
    (
        "Thermal scan Intake Pump IP-401",
        "Intake Pump IP-401",
        [MissionCapability.INSPECT_THERMAL],
        "normal",
        WorkOrderStatus.COMPLETED,
    ),
]


def seed_if_empty(db: Database) -> None:
    if db.list_locations():
        return

    location_ids: dict[str, int] = {}
    location_coords: dict[str, tuple[float, float]] = {}
    for name, description, x, y in LOCATIONS:
        location = db.create_location(LocationCreate(name=name, description=description, x=x, y=y))
        location_ids[name] = location.id
        location_coords[name] = (x, y)

    for from_name, to_name in LOCATION_LINKS:
        from_x, from_y = location_coords[from_name]
        to_x, to_y = location_coords[to_name]
        distance_m = math.dist((from_x, from_y), (to_x, to_y))
        # Paths are walkable both ways.
        db.create_location_link(
            LocationLinkCreate(
                from_location_id=location_ids[from_name],
                to_location_id=location_ids[to_name],
                distance_m=distance_m,
            )
        )
        db.create_location_link(
            LocationLinkCreate(
                from_location_id=location_ids[to_name],
                to_location_id=location_ids[from_name],
                distance_m=distance_m,
            )
        )

    asset_ids: dict[str, int] = {}
    for name, asset_type, location_name, x, y, criticality in ASSETS:
        asset = db.create_asset(
            AssetCreate(
                name=name,
                asset_type=asset_type,
                location_id=location_ids[location_name],
                x=x,
                y=y,
                criticality=criticality,
            )
        )
        asset_ids[name] = asset.id

    for name, ecosystem, capabilities, home_location_name in ROBOTS:
        db.create_robot(
            RobotCreate(
                name=name,
                ecosystem=ecosystem,
                capabilities=capabilities,
                home_location_id=location_ids[home_location_name],
            )
        )

    for title, asset_name, required_capabilities, priority, status in WORK_ORDERS:
        work_order = db.create_work_order(
            WorkOrderCreate(
                title=title,
                asset_id=asset_ids[asset_name],
                required_capabilities=required_capabilities,
                priority=priority,
            )
        )
        if status != WorkOrderStatus.DRAFT:
            db.set_work_order_status(work_order.id, status)
