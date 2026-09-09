"""Ingestion service (CLAUDE.md section 4.6): subscribes to the fleet
telemetry topics, writes robot state and fleet events to the
time-series store, and attaches inspection images to their work order
in the EAM.
"""

from __future__ import annotations

import base64
import logging
import threading

import httpx
import paho.mqtt.client as mqtt
from pydantic import ValidationError

from telemetry.eam_attachments import EamAttachmentGateway
from telemetry.models import FleetEvent, ImageEvent, RobotStateEvent
from telemetry.store import TelemetryStore
from telemetry.topics import EVENTS_WILDCARD, IMAGES_WILDCARD, STATE_WILDCARD

logger = logging.getLogger(__name__)


def _subscribe_and_wait(client: mqtt.Client, topic: str, timeout: float = 5.0) -> None:
    """Subscribe and block until the broker SUBACKs it.

    paho's subscribe() returns as soon as the SUBSCRIBE packet is queued,
    not once the broker has registered the filter. A publish that reaches
    the broker before that registration completes is simply never
    delivered -- no error raised anywhere, it just isn't there. That race
    is what made these MQTT tests flaky, including in CI: see
    telemetry/README.md and adapters/vda5050_amr/README.md.
    """
    acked = threading.Event()

    def _on_subscribe(
        client: mqtt.Client,
        userdata: object,
        mid: int,
        reason_codes: list[object],
        properties: object = None,
    ) -> None:
        acked.set()

    previous_on_subscribe = client.on_subscribe
    client.on_subscribe = _on_subscribe
    try:
        client.subscribe(topic)
        if not acked.wait(timeout):
            raise RuntimeError(f"broker did not ack subscription to {topic!r} within {timeout}s")
    finally:
        client.on_subscribe = previous_on_subscribe


class IngestionService:
    def __init__(
        self, store: TelemetryStore, eam: EamAttachmentGateway, mqtt_client: mqtt.Client
    ) -> None:
        self._store = store
        self._eam = eam
        self._client = mqtt_client
        self._client.message_callback_add(STATE_WILDCARD, self._on_state)
        self._client.message_callback_add(IMAGES_WILDCARD, self._on_image)
        self._client.message_callback_add(EVENTS_WILDCARD, self._on_event)
        _subscribe_and_wait(self._client, STATE_WILDCARD)
        _subscribe_and_wait(self._client, IMAGES_WILDCARD)
        _subscribe_and_wait(self._client, EVENTS_WILDCARD)

    def _on_state(self, client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        try:
            event = RobotStateEvent.model_validate_json(message.payload)
        except ValidationError:
            logger.warning("malformed state message on %s", message.topic, exc_info=True)
            return
        self._store.record_state(event)

    def _on_image(self, client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        try:
            event = ImageEvent.model_validate_json(message.payload)
            data = base64.b64decode(event.image_base64)
        except (ValidationError, ValueError):
            logger.warning("malformed image message on %s", message.topic, exc_info=True)
            return
        try:
            self._eam.upload_image(event.work_order_id, event.filename, event.content_type, data)
        except httpx.HTTPError:
            logger.warning(
                "failed to upload image for work order %s", event.work_order_id, exc_info=True
            )

    def _on_event(self, client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        try:
            event = FleetEvent.model_validate_json(message.payload)
        except ValidationError:
            logger.warning("malformed event message on %s", message.topic, exc_info=True)
            return
        self._store.record_event(event)
