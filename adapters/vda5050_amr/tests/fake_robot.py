"""Stands in for the ROS 2 bridge + simulated robot: subscribes to
order/instantActions over real MQTT and publishes connection/state back,
the same way the real bridge (ros2_bridge/) will once it's driving a
real Nav2 stack. This lets Vda5050Adapter's own MQTT protocol logic be
tested against real messages over a real broker without needing ROS 2 or
Gazebo running. A clearly labelled test double, not a claim that this is
what adapters/vda5050_amr/ IS.
"""

from __future__ import annotations

import json
import threading
import time

import paho.mqtt.client as mqtt
from vda5050_amr.messages import (
    ActionState,
    ActionStatus,
    BatteryState,
    Connection,
    ConnectionState,
    Error,
    ErrorLevel,
    Header,
    Order,
    State,
)
from vda5050_amr.topics import Vda5050Topics


def subscribe_and_wait(client: mqtt.Client, topic: str, timeout: float = 5.0) -> None:
    """Subscribe and block until the broker SUBACKs it.

    paho's subscribe() returns as soon as the SUBSCRIBE packet is queued,
    not once the broker has registered the filter. A publish that races
    ahead of that registration -- plausible whenever the test publishes
    right after subscribing, which several tests here do -- is simply
    never delivered. That race is what made these tests flaky, including
    in CI: see adapters/vda5050_amr/README.md.
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


class FakeRobot:
    """Subscribes to `order` itself and reads the action id/type back out
    of it, the same way a real bridge would -- so tests never have to
    duplicate the adapter's own internally-generated action ids."""

    def __init__(self, client: mqtt.Client, manufacturer: str, serial_number: str) -> None:
        self._client = client
        self._manufacturer = manufacturer
        self._serial_number = serial_number
        self._topics = Vda5050Topics(manufacturer=manufacturer, serial_number=serial_number)
        self._header_id = 0
        self.latest_order: Order | None = None

        client.message_callback_add(self._topics.order, self._on_order)
        subscribe_and_wait(client, self._topics.order)

    def _on_order(self, client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        self.latest_order = Order.model_validate(json.loads(message.payload.decode("utf-8")))

    def _header(self) -> Header:
        self._header_id += 1
        return Header(
            header_id=self._header_id,
            timestamp=str(time.time()),
            version="2.0",
            manufacturer=self._manufacturer,
            serial_number=self._serial_number,
        )

    def announce_online(self) -> None:
        connection = Connection(header=self._header(), connection_state=ConnectionState.ONLINE)
        self._publish(self._topics.connection, connection)

    def report_driving(self, order_id: str) -> None:
        state = State(
            header=self._header(),
            order_id=order_id,
            driving=True,
            battery_state=BatteryState(battery_charge=80.0),
        )
        self._publish(self._topics.state, state)

    def report_final_action_finished(self) -> None:
        """Reads the last node's action out of the most recently received
        order and reports it FINISHED -- what a real robot does once it
        has physically completed the inspection at the final waypoint."""
        assert self.latest_order is not None, "no order received yet"
        final_action = self.latest_order.nodes[-1].actions[-1]
        state = State(
            header=self._header(),
            order_id=self.latest_order.order_id,
            driving=False,
            action_states=[
                ActionState(
                    action_id=final_action.action_id,
                    action_type=final_action.action_type,
                    action_status=ActionStatus.FINISHED,
                )
            ],
            battery_state=BatteryState(battery_charge=79.0),
        )
        self._publish(self._topics.state, state)

    def report_fatal_error(self, description: str) -> None:
        assert self.latest_order is not None, "no order received yet"
        state = State(
            header=self._header(),
            order_id=self.latest_order.order_id,
            driving=False,
            errors=[
                Error(
                    error_type="navigation",
                    error_level=ErrorLevel.FATAL,
                    error_description=description,
                )
            ],
            battery_state=BatteryState(battery_charge=75.0),
        )
        self._publish(self._topics.state, state)

    def _publish(self, topic: str, message: State | Connection) -> None:
        payload = message.model_dump(mode="json", by_alias=True)
        self._client.publish(topic, json.dumps(payload), qos=1)
