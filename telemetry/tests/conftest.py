"""Ingestion tests need a real MQTT broker -- Mosquitto, run via Docker
for the test session, same image as deploy/docker-compose.yml. Same
pattern as adapters/vda5050_amr/tests/conftest.py (duplicated rather
than shared: these are separate workspace packages).
"""

from __future__ import annotations

import socket
import subprocess
import threading
import time
import uuid
from collections.abc import Iterator

import paho.mqtt.client as mqtt
import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_broker_ready(port: int, timeout: float = 30.0) -> bool:
    """A bare TCP connect only proves the listener socket is accepting
    connections -- not that Mosquitto is actually ready to process the
    MQTT protocol yet. Under a loaded CI runner there's a real window
    where the two disagree: this was diagnosed directly after
    _subscribe_and_wait (ingestion.py) started reliably timing out on
    the very first subscribe of this module, immediately after this
    fixture's old bare-connect probe had just declared the broker
    ready. Same fix as adapters/vda5050_amr/tests/conftest.py
    (duplicated, not shared -- see this file's own module docstring).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        acked = threading.Event()
        probe.on_subscribe = lambda *args: acked.set()
        try:
            probe.connect("127.0.0.1", port, keepalive=2)
        except OSError:
            time.sleep(0.2)
            continue
        probe.loop_start()
        try:
            probe.subscribe("robot-router/readiness-probe")
            if acked.wait(2.0):
                return True
        finally:
            probe.loop_stop()
            probe.disconnect()
        time.sleep(0.2)
    return False


@pytest.fixture(scope="module")
def mqtt_broker_port(tmp_path_factory: pytest.TempPathFactory) -> Iterator[int]:
    port = _free_port()
    container_name = f"telemetry-test-mosquitto-{uuid.uuid4().hex[:8]}"

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

    if not _wait_for_broker_ready(port, timeout=30.0):
        subprocess.run(["docker", "logs", container_name], capture_output=False)
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        raise RuntimeError("mosquitto did not become ready to subscribe in time")

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
