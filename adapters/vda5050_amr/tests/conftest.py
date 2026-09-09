"""Tests need a real MQTT broker -- Mosquitto, run via Docker for the
test session, same image as deploy/docker-compose.yml. paho-mqtt is a
real client library talking real MQTT; there's no reasonable in-process
fake for the broker itself.
"""

from __future__ import annotations

import socket
import subprocess
import time
import uuid
from collections.abc import Iterator

import paho.mqtt.client as mqtt
import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def mqtt_broker_port(tmp_path_factory: pytest.TempPathFactory) -> Iterator[int]:
    port = _free_port()
    container_name = f"vda5050-test-mosquitto-{uuid.uuid4().hex[:8]}"

    config_dir = tmp_path_factory.mktemp("mosquitto-config")
    config_path = config_dir / "mosquitto.conf"
    config_path.write_text("listener 1883 0.0.0.0\nallow_anonymous true\npersistence false\n")

    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            container_name,
            "-p",
            f"{port}:1883",
            "-v",
            f"{config_path}:/mosquitto/config/mosquitto.conf:ro",
            "eclipse-mosquitto:2",
        ],
        check=True,
        capture_output=True,
    )

    deadline = time.monotonic() + 15.0
    connected = False
    while time.monotonic() < deadline:
        probe = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        try:
            probe.connect("127.0.0.1", port, keepalive=2)
            probe.disconnect()
            connected = True
            break
        except OSError:
            time.sleep(0.2)
    if not connected:
        subprocess.run(["docker", "logs", container_name], capture_output=False)
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        raise RuntimeError("mosquitto did not accept connections in time")

    yield port

    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)


@pytest.fixture
def mqtt_client(mqtt_broker_port: int) -> Iterator[mqtt.Client]:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect("127.0.0.1", mqtt_broker_port)
    client.loop_start()
    yield client
    client.loop_stop()
    client.disconnect()
