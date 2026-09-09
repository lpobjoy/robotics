from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import paho.mqtt.client as mqtt
import pytest
from fake_robot import FakeRobot
from router.models import Mission, MissionStatus, MissionType, RobotAvailability
from vda5050_amr.adapter import Vda5050Adapter

LOCATIONS = {1: (0.0, 0.0), 2: (10.0, 5.0), 3: (20.0, 0.0)}


def _location_lookup(location_id: int) -> tuple[float, float]:
    return LOCATIONS[location_id]


def _wait_until(predicate: Callable[[], bool], timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not met before timeout")


@pytest.fixture
def connected_mqtt_client(mqtt_broker_port: int) -> Iterator[mqtt.Client]:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect("127.0.0.1", mqtt_broker_port)
    client.loop_start()
    yield client
    client.loop_stop()
    client.disconnect()


@pytest.fixture
def robot_side_client(mqtt_broker_port: int) -> Iterator[mqtt.Client]:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect("127.0.0.1", mqtt_broker_port)
    client.loop_start()
    yield client
    client.loop_stop()
    client.disconnect()


def _make_adapter(client: mqtt.Client) -> Vda5050Adapter:
    return Vda5050Adapter(
        robot_id="amr-01",
        name="amr-01",
        supported_capabilities=[MissionType.INSPECT_VISUAL, MissionType.PATROL],
        home_location_id=1,
        location_lookup=_location_lookup,
        mqtt_client=client,
    )


def test_offline_until_a_connection_message_is_seen(connected_mqtt_client: mqtt.Client) -> None:
    adapter = _make_adapter(connected_mqtt_client)
    assert adapter.capabilities().availability == RobotAvailability.OFFLINE


def test_becomes_idle_once_online(
    connected_mqtt_client: mqtt.Client, robot_side_client: mqtt.Client
) -> None:
    adapter = _make_adapter(connected_mqtt_client)
    fake_robot = FakeRobot(robot_side_client, "robot-router-demo", "amr-01")

    fake_robot.announce_online()
    _wait_until(lambda: adapter.capabilities().availability == RobotAvailability.IDLE)


def test_dispatch_publishes_a_real_order_and_status_progresses_to_completed(
    connected_mqtt_client: mqtt.Client, robot_side_client: mqtt.Client
) -> None:
    adapter = _make_adapter(connected_mqtt_client)
    fake_robot = FakeRobot(robot_side_client, "robot-router-demo", "amr-01")
    fake_robot.announce_online()
    _wait_until(lambda: adapter.capabilities().availability == RobotAvailability.IDLE)

    mission = Mission(
        work_order_id=1,
        type=MissionType.INSPECT_VISUAL,
        target_locations=[2],
        required_capabilities=[MissionType.INSPECT_VISUAL],
        requested_by="test",
    )
    handle = adapter.dispatch(mission)

    _wait_until(
        lambda: fake_robot.latest_order is not None
        and fake_robot.latest_order.order_id == mission.id
    )
    assert fake_robot.latest_order is not None
    node = fake_robot.latest_order.nodes[0]
    assert node.node_position.x == 10.0
    assert node.node_position.y == 5.0
    assert node.actions[0].action_type == "inspect_visual"

    fake_robot.report_driving(mission.id)
    _wait_until(lambda: adapter.status(handle).status == MissionStatus.IN_PROGRESS)
    assert adapter.capabilities().availability == RobotAvailability.BUSY

    fake_robot.report_final_action_finished()
    _wait_until(lambda: adapter.status(handle).status == MissionStatus.COMPLETED)


def test_fatal_error_reports_failed(
    connected_mqtt_client: mqtt.Client, robot_side_client: mqtt.Client
) -> None:
    adapter = _make_adapter(connected_mqtt_client)
    fake_robot = FakeRobot(robot_side_client, "robot-router-demo", "amr-01")
    fake_robot.announce_online()
    _wait_until(lambda: adapter.capabilities().availability == RobotAvailability.IDLE)

    mission = Mission(
        work_order_id=2,
        type=MissionType.PATROL,
        target_locations=[3],
        required_capabilities=[MissionType.PATROL],
        requested_by="test",
    )
    handle = adapter.dispatch(mission)
    _wait_until(lambda: fake_robot.latest_order is not None)

    fake_robot.report_fatal_error("obstacle blocking path")
    _wait_until(lambda: adapter.status(handle).status == MissionStatus.FAILED)
    assert "obstacle" in adapter.status(handle).detail


def test_pause_resume_abort_publish_instant_actions(
    connected_mqtt_client: mqtt.Client, robot_side_client: mqtt.Client
) -> None:
    adapter = _make_adapter(connected_mqtt_client)
    fake_robot = FakeRobot(robot_side_client, "robot-router-demo", "amr-01")
    fake_robot.announce_online()
    _wait_until(lambda: adapter.capabilities().availability == RobotAvailability.IDLE)

    received: list[str] = []
    robot_side_client.message_callback_add(
        "uagv/v2/robot-router-demo/amr-01/instantActions",
        lambda client, userdata, message: received.append(message.payload.decode("utf-8")),
    )
    robot_side_client.subscribe("uagv/v2/robot-router-demo/amr-01/instantActions")

    mission = Mission(
        work_order_id=3,
        type=MissionType.PATROL,
        target_locations=[2],
        required_capabilities=[MissionType.PATROL],
        requested_by="test",
    )
    handle = adapter.dispatch(mission)

    adapter.pause(handle)
    _wait_until(lambda: any("startPause" in r for r in received))

    adapter.resume(handle)
    _wait_until(lambda: any("stopPause" in r for r in received))

    adapter.abort(handle)
    _wait_until(lambda: any("cancelOrder" in r for r in received))
