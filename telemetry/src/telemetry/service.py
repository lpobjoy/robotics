"""Entrypoint for `uv run python -m telemetry`. Reads MQTT_HOST,
MQTT_PORT, EAM_BASE_URL, and TELEMETRY_DB_PATH from the environment.
"""

from __future__ import annotations

import os

import paho.mqtt.client as mqtt

from telemetry.eam_attachments import EamAttachmentGateway
from telemetry.ingestion import IngestionService
from telemetry.store import TelemetryStore


def run() -> None:
    mqtt_host = os.environ.get("MQTT_HOST", "localhost")
    mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))
    eam_base_url = os.environ.get("EAM_BASE_URL", "http://localhost:8000")
    db_path = os.environ.get("TELEMETRY_DB_PATH", "telemetry.db")

    store = TelemetryStore(db_path)
    eam = EamAttachmentGateway(eam_base_url)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    IngestionService(store, eam, client)

    client.connect(mqtt_host, mqtt_port)
    client.loop_forever()


if __name__ == "__main__":
    run()
