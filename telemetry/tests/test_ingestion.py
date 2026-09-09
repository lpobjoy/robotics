from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable

import paho.mqtt.client as mqtt
import pytest
from eam.app import create_app
from fastapi.testclient import TestClient
from telemetry.eam_attachments import EamAttachmentGateway
from telemetry.ingestion import IngestionService
from telemetry.store import TelemetryStore
from telemetry.topics import events_topic, images_topic, state_topic


def _wait_until(predicate: Callable[[], bool], timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not met before timeout")


@pytest.fixture
def eam_test_client() -> TestClient:
    app = create_app(db_path=":memory:", seed=True)
    return TestClient(app, base_url="http://eam.test")


@pytest.fixture
def ingestion(mqtt_client: mqtt.Client, eam_test_client: TestClient) -> IngestionService:
    store = TelemetryStore(":memory:")
    eam = EamAttachmentGateway(client=eam_test_client)
    return IngestionService(store, eam, mqtt_client)


def _publisher(mqtt_broker_port: int) -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect("127.0.0.1", mqtt_broker_port)
    client.loop_start()
    return client


def test_state_message_is_persisted(
    ingestion: IngestionService, mqtt_broker_port: int
) -> None:
    publisher = _publisher(mqtt_broker_port)
    payload = {
        "robot_id": "amr-01",
        "timestamp": "2026-01-01T00:00:00Z",
        "battery_charge": 91.0,
        "driving": True,
        "status": "in_progress",
    }
    publisher.publish(state_topic("amr-01"), json.dumps(payload), qos=1)

    _wait_until(lambda: ingestion._store.latest_for_robot("amr-01") is not None)
    latest = ingestion._store.latest_for_robot("amr-01")
    assert latest is not None
    assert latest.battery_charge == 91.0
    assert latest.status == "in_progress"

    publisher.loop_stop()
    publisher.disconnect()


def test_event_message_is_persisted(ingestion: IngestionService, mqtt_broker_port: int) -> None:
    publisher = _publisher(mqtt_broker_port)
    payload = {
        "robot_id": "amr-01",
        "timestamp": "2026-01-01T00:00:00Z",
        "event_type": "mission.completed",
        "detail": {"mission_id": "abc-123"},
    }
    publisher.publish(events_topic("amr-01"), json.dumps(payload), qos=1)

    _wait_until(lambda: len(ingestion._store.events_for_robot("amr-01")) > 0)
    events = ingestion._store.events_for_robot("amr-01")
    assert events[0].event_type == "mission.completed"

    publisher.loop_stop()
    publisher.disconnect()


def test_image_message_is_attached_to_the_work_order(
    ingestion: IngestionService, mqtt_broker_port: int, eam_test_client: TestClient
) -> None:
    work_order_id = eam_test_client.get("/api/work-orders").json()[0]["id"]
    image_bytes = b"fake-jpeg-bytes"

    publisher = _publisher(mqtt_broker_port)
    payload = {
        "robot_id": "amr-01",
        "work_order_id": work_order_id,
        "mission_id": "abc-123",
        "filename": "inspection.jpg",
        "content_type": "image/jpeg",
        "image_base64": base64.b64encode(image_bytes).decode("ascii"),
    }
    publisher.publish(images_topic("amr-01"), json.dumps(payload), qos=1)

    def _attached() -> bool:
        attachments = eam_test_client.get(f"/api/work-orders/{work_order_id}/attachments").json()
        return len(attachments) > 0

    _wait_until(_attached)

    attachments = eam_test_client.get(f"/api/work-orders/{work_order_id}/attachments").json()
    assert attachments[0]["filename"] == "inspection.jpg"
    downloaded = eam_test_client.get(f"/api/attachments/{attachments[0]['id']}")
    assert downloaded.content == image_bytes

    publisher.loop_stop()
    publisher.disconnect()


def test_malformed_state_message_does_not_crash_the_service(
    ingestion: IngestionService, mqtt_broker_port: int
) -> None:
    publisher = _publisher(mqtt_broker_port)
    publisher.publish(state_topic("amr-01"), "not valid json {{{", qos=1)
    publisher.publish(
        state_topic("amr-01"),
        json.dumps({"robot_id": "amr-01", "timestamp": "2026-01-01T00:00:00Z", "status": "ok"}),
        qos=1,
    )

    _wait_until(lambda: ingestion._store.latest_for_robot("amr-01") is not None)
    latest = ingestion._store.latest_for_robot("amr-01")
    assert latest is not None
    assert latest.status == "ok"

    publisher.loop_stop()
    publisher.disconnect()
