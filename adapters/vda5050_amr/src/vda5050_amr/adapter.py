"""The FleetAdapter side of adapters/vda5050_amr/ (CLAUDE.md section 4.5):
speaks only VDA 5050 over MQTT to the robot. It must not reach into ROS
directly -- that separation is the point, and this module has no ROS
imports at all. The ROS 2 side (subscribing to order/instantActions,
driving Nav2, publishing state/visualization/connection) is a separate
ROS 2 package; see ros2_bridge/ and the adapter's README for what that
side is and isn't.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable, Iterator

import paho.mqtt.client as mqtt
from router.models import (
    Mission,
    MissionHandle,
    MissionStatus,
    MissionStatusReport,
    MissionType,
    RobotAvailability,
    RobotDescriptor,
    TelemetryEvent,
)

from vda5050_amr.messages import (
    Action,
    ActionBlockingType,
    ActionStatus,
    Connection,
    ConnectionState,
    Edge,
    Header,
    InstantActions,
    Node,
    NodePosition,
    Order,
    State,
)
from vda5050_amr.topics import Vda5050Topics

LocationLookup = Callable[[int], tuple[float, float]]


class Vda5050Adapter:
    """One instance represents one AMR. `location_lookup` resolves a
    location id to (x, y) -- VDA 5050 nodes need real coordinates, and
    those live in the world model, not here, so it's injected rather
    than duplicated.
    """

    def __init__(
        self,
        robot_id: str,
        name: str,
        supported_capabilities: list[MissionType],
        home_location_id: int,
        location_lookup: LocationLookup,
        mqtt_client: mqtt.Client,
        manufacturer: str = "robot-router-demo",
    ) -> None:
        self._robot_id = robot_id
        self._name = name
        self._supported_capabilities = supported_capabilities
        self._current_location_id = home_location_id
        self._location_lookup = location_lookup
        self._manufacturer = manufacturer
        self._topics = Vda5050Topics(manufacturer=manufacturer, serial_number=robot_id)

        self._latest_state: State | None = None
        self._latest_connection: Connection | None = None
        self._header_id = 0

        self._client = mqtt_client
        self._client.on_message = self._on_message
        self._client.subscribe(self._topics.state)
        self._client.subscribe(self._topics.connection)

    def _next_header(self) -> Header:
        self._header_id += 1
        return Header(
            header_id=self._header_id,
            timestamp=str(time.time()),
            version="2.0",
            manufacturer=self._manufacturer,
            serial_number=self._robot_id,
        )

    def _on_message(self, client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        payload = json.loads(message.payload.decode("utf-8"))
        if message.topic == self._topics.state:
            self._latest_state = State.model_validate(payload)
        elif message.topic == self._topics.connection:
            self._latest_connection = Connection.model_validate(payload)

    # --- FleetAdapter protocol ---

    def capabilities(self) -> RobotDescriptor:
        return RobotDescriptor(
            robot_id=self._robot_id,
            name=self._name,
            ecosystem="vda5050_amr",
            supported_capabilities=self._supported_capabilities,
            availability=self._availability(),
            location_id=self._current_location_id,
        )

    def _availability(self) -> RobotAvailability:
        if (
            self._latest_connection is None
            or self._latest_connection.connection_state != ConnectionState.ONLINE
        ):
            return RobotAvailability.OFFLINE
        if self._latest_state is not None and (
            self._latest_state.driving
            or any(
                a.action_status == ActionStatus.RUNNING for a in self._latest_state.action_states
            )
        ):
            return RobotAvailability.BUSY
        return RobotAvailability.IDLE

    def dispatch(self, mission: Mission) -> MissionHandle:
        nodes: list[Node] = []
        for sequence_id, location_id in enumerate(mission.target_locations):
            x, y = self._location_lookup(location_id)
            actions: list[Action] = []
            if sequence_id == len(mission.target_locations) - 1:
                actions.append(
                    Action(
                        action_type=mission.type.value,
                        action_id=str(uuid.uuid4()),
                        blocking_type=ActionBlockingType.HARD,
                        action_description=f"{mission.type.value} at location {location_id}",
                    )
                )
            nodes.append(
                Node(
                    node_id=f"location-{location_id}",
                    sequence_id=sequence_id * 2,
                    node_position=NodePosition(x=x, y=y),
                    actions=actions,
                )
            )

        edges = [
            Edge(
                edge_id=f"edge-{a.node_id}-{b.node_id}",
                sequence_id=a.sequence_id + 1,
                start_node_id=a.node_id,
                end_node_id=b.node_id,
            )
            for a, b in zip(nodes, nodes[1:], strict=False)
        ]

        order = Order(
            header=self._next_header(),
            order_id=mission.id,
            nodes=nodes,
            edges=edges,
        )
        self._publish(self._topics.order, order)

        return MissionHandle(
            mission_id=mission.id, robot_id=self._robot_id, ecosystem="vda5050_amr"
        )

    def status(self, handle: MissionHandle) -> MissionStatusReport:
        state = self._latest_state
        if state is None or state.order_id != handle.mission_id:
            return MissionStatusReport(
                mission_id=handle.mission_id, status=MissionStatus.DISPATCHED
            )

        if any(error.error_level.value == "FATAL" for error in state.errors):
            return MissionStatusReport(
                mission_id=handle.mission_id,
                status=MissionStatus.FAILED,
                detail="; ".join(e.error_description for e in state.errors),
            )

        if state.action_states and all(
            a.action_status == ActionStatus.FINISHED for a in state.action_states
        ):
            return MissionStatusReport(
                mission_id=handle.mission_id, status=MissionStatus.COMPLETED
            )

        if state.driving or any(
            a.action_status in (ActionStatus.RUNNING, ActionStatus.INITIALIZING)
            for a in state.action_states
        ):
            return MissionStatusReport(
                mission_id=handle.mission_id, status=MissionStatus.IN_PROGRESS
            )

        return MissionStatusReport(mission_id=handle.mission_id, status=MissionStatus.DISPATCHED)

    def pause(self, handle: MissionHandle) -> None:
        self._publish_instant_action("startPause")

    def resume(self, handle: MissionHandle) -> None:
        self._publish_instant_action("stopPause")

    def abort(self, handle: MissionHandle) -> None:
        self._publish_instant_action("cancelOrder")

    def telemetry_stream(self) -> Iterator[TelemetryEvent]:
        # Live subscription-driven telemetry lands in step 8. Nothing to
        # replay here yet -- see adapters/vda5050_amr/README.md.
        return iter(())

    def _publish_instant_action(self, action_type: str) -> None:
        instant_actions = InstantActions(
            header=self._next_header(),
            actions=[
                Action(
                    action_type=action_type,
                    action_id=str(uuid.uuid4()),
                    blocking_type=ActionBlockingType.HARD,
                )
            ],
        )
        self._publish(self._topics.instant_actions, instant_actions)

    def _publish(self, topic: str, message: Order | InstantActions) -> None:
        payload = message.model_dump(mode="json", by_alias=True)
        self._client.publish(topic, json.dumps(payload), qos=1)
