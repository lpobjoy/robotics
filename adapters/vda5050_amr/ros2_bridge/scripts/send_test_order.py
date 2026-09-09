"""One-off manual script for the Nav2-through-the-bridge feasibility
check (not part of the package, not installed, not run by any test):
publishes a real VDA 5050 order to the running bridge_node over MQTT
and prints back state updates until the order finishes or a timeout.
Usage: python3 send_test_order.py <mqtt_host> <mqtt_port> <target_x> <target_y>
"""

from __future__ import annotations

import json
import sys
import time
import uuid

import paho.mqtt.client as mqtt

MANUFACTURER = "robot-router-demo"
SERIAL = "amr-01"


def topic(name: str) -> str:
    return f"uagv/v2/{MANUFACTURER}/{SERIAL}/{name}"


def main() -> None:
    mqtt_host = sys.argv[1]
    mqtt_port = int(sys.argv[2])
    x, y = float(sys.argv[3]), float(sys.argv[4])
    order_id = str(uuid.uuid4())

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_message(c: mqtt.Client, u: object, message: mqtt.MQTTMessage) -> None:
        payload = json.loads(message.payload.decode("utf-8"))
        print(f"[state] driving={payload.get('driving')} actions={payload.get('actionStates')}")

    client.on_message = on_message
    client.connect(mqtt_host, mqtt_port)
    client.subscribe(topic("state"))
    client.loop_start()

    order = {
        "headerId": 1,
        "timestamp": str(time.time()),
        "version": "2.0",
        "manufacturer": MANUFACTURER,
        "serialNumber": SERIAL,
        "orderId": order_id,
        "orderUpdateId": 0,
        "nodes": [
            {
                "nodeId": "target",
                "sequenceId": 0,
                "nodePosition": {"x": x, "y": y, "theta": 0.0},
                "actions": [
                    {
                        "actionId": str(uuid.uuid4()),
                        "actionType": "inspect_visual",
                        "blockingType": "HARD",
                    }
                ],
            }
        ],
        "edges": [],
    }
    print(f"publishing order {order_id} -> ({x}, {y})")
    client.publish(topic("order"), json.dumps(order), qos=1)

    time.sleep(60)
    client.loop_stop()


if __name__ == "__main__":
    main()
