"""SQLite persistence for the mock EAM.

Plain stdlib sqlite3, not an ORM: FastAPI, Pydantic, and httpx are the only
web-facing dependencies CLAUDE.md section 5 pins for this service, and at
~20 assets and ~5 work orders there is no case for anything heavier.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from eam.models import (
    Asset,
    AssetCreate,
    Attachment,
    Location,
    LocationCreate,
    LocationLink,
    LocationLinkCreate,
    MissionCapability,
    Robot,
    RobotCreate,
    WebhookEventType,
    WebhookSubscription,
    WebhookSubscriptionCreate,
    WorkOrder,
    WorkOrderCreate,
    WorkOrderStatus,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    x REAL NOT NULL,
    y REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS location_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_location_id INTEGER NOT NULL REFERENCES locations(id),
    to_location_id INTEGER NOT NULL REFERENCES locations(id),
    distance_m REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    location_id INTEGER NOT NULL REFERENCES locations(id),
    x REAL NOT NULL,
    y REAL NOT NULL,
    criticality TEXT NOT NULL DEFAULT 'medium'
);

CREATE TABLE IF NOT EXISTS robots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ecosystem TEXT NOT NULL,
    capabilities TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    home_location_id INTEGER NOT NULL REFERENCES locations(id)
);

CREATE TABLE IF NOT EXISTS work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    required_capabilities TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Draft',
    priority TEXT NOT NULL DEFAULT 'normal',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id INTEGER NOT NULL REFERENCES work_orders(id),
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    data BLOB NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- locations ---

    def create_location(self, location: LocationCreate) -> Location:
        cursor = self._conn.execute(
            "INSERT INTO locations (name, description, x, y) VALUES (?, ?, ?, ?)",
            (location.name, location.description, location.x, location.y),
        )
        self._conn.commit()
        return self.get_location(cursor.lastrowid)  # type: ignore[return-value]

    def list_locations(self) -> list[Location]:
        rows = self._conn.execute("SELECT * FROM locations ORDER BY id").fetchall()
        return [_location_from_row(row) for row in rows]

    def get_location(self, location_id: int) -> Location | None:
        row = self._conn.execute(
            "SELECT * FROM locations WHERE id = ?", (location_id,)
        ).fetchone()
        return _location_from_row(row) if row else None

    # --- location links ---

    def create_location_link(self, link: LocationLinkCreate) -> LocationLink:
        cursor = self._conn.execute(
            "INSERT INTO location_links (from_location_id, to_location_id, distance_m) "
            "VALUES (?, ?, ?)",
            (link.from_location_id, link.to_location_id, link.distance_m),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM location_links WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return _location_link_from_row(row)

    def list_location_links(self) -> list[LocationLink]:
        rows = self._conn.execute("SELECT * FROM location_links ORDER BY id").fetchall()
        return [_location_link_from_row(row) for row in rows]

    # --- assets ---

    def create_asset(self, asset: AssetCreate) -> Asset:
        cursor = self._conn.execute(
            "INSERT INTO assets (name, asset_type, location_id, x, y, criticality) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (asset.name, asset.asset_type, asset.location_id, asset.x, asset.y, asset.criticality),
        )
        self._conn.commit()
        return self.get_asset(cursor.lastrowid)  # type: ignore[return-value]

    def list_assets(self) -> list[Asset]:
        rows = self._conn.execute("SELECT * FROM assets ORDER BY id").fetchall()
        return [_asset_from_row(row) for row in rows]

    def get_asset(self, asset_id: int) -> Asset | None:
        row = self._conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        return _asset_from_row(row) if row else None

    # --- robots ---

    def create_robot(self, robot: RobotCreate) -> Robot:
        cursor = self._conn.execute(
            "INSERT INTO robots (name, ecosystem, capabilities, status, home_location_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                robot.name,
                robot.ecosystem.value,
                json.dumps([c.value for c in robot.capabilities]),
                robot.status.value,
                robot.home_location_id,
            ),
        )
        self._conn.commit()
        return self.get_robot(cursor.lastrowid)  # type: ignore[return-value]

    def list_robots(self) -> list[Robot]:
        rows = self._conn.execute("SELECT * FROM robots ORDER BY id").fetchall()
        return [_robot_from_row(row) for row in rows]

    def get_robot(self, robot_id: int) -> Robot | None:
        row = self._conn.execute("SELECT * FROM robots WHERE id = ?", (robot_id,)).fetchone()
        return _robot_from_row(row) if row else None

    # --- work orders ---

    def create_work_order(self, work_order: WorkOrderCreate) -> WorkOrder:
        now = _now_iso()
        cursor = self._conn.execute(
            "INSERT INTO work_orders "
            "(title, description, asset_id, required_capabilities, status, priority, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                work_order.title,
                work_order.description,
                work_order.asset_id,
                json.dumps([c.value for c in work_order.required_capabilities]),
                WorkOrderStatus.DRAFT.value,
                work_order.priority,
                now,
                now,
            ),
        )
        self._conn.commit()
        return self.get_work_order(cursor.lastrowid)  # type: ignore[return-value]

    def list_work_orders(self, status: WorkOrderStatus | None = None) -> list[WorkOrder]:
        if status is None:
            rows = self._conn.execute("SELECT * FROM work_orders ORDER BY id").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM work_orders WHERE status = ? ORDER BY id", (status.value,)
            ).fetchall()
        return [_work_order_from_row(row) for row in rows]

    def get_work_order(self, work_order_id: int) -> WorkOrder | None:
        row = self._conn.execute(
            "SELECT * FROM work_orders WHERE id = ?", (work_order_id,)
        ).fetchone()
        return _work_order_from_row(row) if row else None

    def set_work_order_status(self, work_order_id: int, status: WorkOrderStatus) -> WorkOrder:
        """Write a new status with no transition validation. Callers (the
        REST API) are responsible for checking is_transition_allowed first;
        this method is also used directly by seed data to plant historical
        work orders in a non-Draft state without going through the real
        state machine or firing webhooks.
        """
        self._conn.execute(
            "UPDATE work_orders SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, _now_iso(), work_order_id),
        )
        self._conn.commit()
        return self.get_work_order(work_order_id)  # type: ignore[return-value]

    # --- attachments ---

    def create_attachment(
        self, work_order_id: int, filename: str, content_type: str, data: bytes
    ) -> Attachment:
        cursor = self._conn.execute(
            "INSERT INTO attachments "
            "(work_order_id, filename, content_type, size_bytes, data, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (work_order_id, filename, content_type, len(data), data, _now_iso()),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id, work_order_id, filename, content_type, size_bytes, created_at "
            "FROM attachments WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return _attachment_from_row(row)

    def list_attachments(self, work_order_id: int) -> list[Attachment]:
        rows = self._conn.execute(
            "SELECT id, work_order_id, filename, content_type, size_bytes, created_at "
            "FROM attachments WHERE work_order_id = ? ORDER BY id",
            (work_order_id,),
        ).fetchall()
        return [_attachment_from_row(row) for row in rows]

    def get_attachment_data(self, attachment_id: int) -> tuple[Attachment, bytes] | None:
        row = self._conn.execute(
            "SELECT * FROM attachments WHERE id = ?", (attachment_id,)
        ).fetchone()
        if row is None:
            return None
        return _attachment_from_row(row), bytes(row["data"])

    # --- webhook subscriptions ---

    def create_webhook(self, subscription: WebhookSubscriptionCreate) -> WebhookSubscription:
        cursor = self._conn.execute(
            "INSERT INTO webhook_subscriptions (url, event_type, created_at) VALUES (?, ?, ?)",
            (subscription.url, subscription.event_type.value, _now_iso()),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM webhook_subscriptions WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return _webhook_from_row(row)

    def list_webhooks(self) -> list[WebhookSubscription]:
        rows = self._conn.execute("SELECT * FROM webhook_subscriptions ORDER BY id").fetchall()
        return [_webhook_from_row(row) for row in rows]

    def list_webhooks_for_event(
        self, event_type: WebhookEventType
    ) -> list[WebhookSubscription]:
        rows = self._conn.execute(
            "SELECT * FROM webhook_subscriptions WHERE event_type = ? ORDER BY id",
            (event_type.value,),
        ).fetchall()
        return [_webhook_from_row(row) for row in rows]


def _location_from_row(row: sqlite3.Row) -> Location:
    return Location(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        x=row["x"],
        y=row["y"],
    )


def _location_link_from_row(row: sqlite3.Row) -> LocationLink:
    return LocationLink(
        id=row["id"],
        from_location_id=row["from_location_id"],
        to_location_id=row["to_location_id"],
        distance_m=row["distance_m"],
    )


def _asset_from_row(row: sqlite3.Row) -> Asset:
    return Asset(
        id=row["id"],
        name=row["name"],
        asset_type=row["asset_type"],
        location_id=row["location_id"],
        x=row["x"],
        y=row["y"],
        criticality=row["criticality"],
    )


def _robot_from_row(row: sqlite3.Row) -> Robot:
    return Robot(
        id=row["id"],
        name=row["name"],
        ecosystem=row["ecosystem"],
        capabilities=[MissionCapability(v) for v in json.loads(row["capabilities"])],
        status=row["status"],
        home_location_id=row["home_location_id"],
    )


def _work_order_from_row(row: sqlite3.Row) -> WorkOrder:
    return WorkOrder(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        asset_id=row["asset_id"],
        required_capabilities=[
            MissionCapability(v) for v in json.loads(row["required_capabilities"])
        ],
        status=row["status"],
        priority=row["priority"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _attachment_from_row(row: sqlite3.Row) -> Attachment:
    return Attachment(
        id=row["id"],
        work_order_id=row["work_order_id"],
        filename=row["filename"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _webhook_from_row(row: sqlite3.Row) -> WebhookSubscription:
    return WebhookSubscription(
        id=row["id"],
        url=row["url"],
        event_type=row["event_type"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
