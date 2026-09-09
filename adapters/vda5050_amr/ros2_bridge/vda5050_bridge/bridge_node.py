"""ROS 2 bridge node: subscribes to VDA 5050 order/instantActions over
MQTT and drives Nav2's NavigateToPose action; publishes VDA 5050
state/connection back over MQTT. This is the ROS 2 half of
adapters/vda5050_amr/ (CLAUDE.md section 4.5) -- the other half
(src/vda5050_amr/, a separate Python package with no ROS dependency at
all) speaks only MQTT to this node's robot. This node is the only thing
in the adapter that talks to both MQTT and ROS.

Camera "inspection" (section 4.5): grabs one frame from the robot's
camera topic at the final waypoint and saves it to disk; the saved path
is carried in the action's resultDescription. There is no EAM/telemetry
image upload wired up to this yet -- that is step 8's job.

Known limitation, stated plainly rather than silently glossed over:
pause/resume are a simplified approximation. VDA 5050's startPause stops
the robot between waypoints (checked before each _navigate_to call), not
mid-navigation via Nav2's own pause mechanism -- that would need holding
and re-issuing a Nav2 goal preemption, which is real additional work
this demo doesn't need to prove the core dispatch-to-completion loop.
cancelOrder does properly cancel an in-flight Nav2 goal.
"""

from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.action.client import ClientGoalHandle
from rclpy.node import Node
from rclpy.task import Future
from sensor_msgs.msg import Image

MANUFACTURER = "robot-router-demo"


def _topic(serial_number: str, name: str) -> str:
    return f"uagv/v2/{MANUFACTURER}/{serial_number}/{name}"


def _wait_for_future(future: Future) -> Any:
    while not future.done():
        time.sleep(0.05)
    return future.result()


class Vda5050BridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("vda5050_bridge")

        self.declare_parameter("serial_number", "amr-01")
        self.declare_parameter("mqtt_host", "localhost")
        self.declare_parameter("mqtt_port", 1883)
        self.declare_parameter("camera_topic", "/oakd/rgb/preview/image_raw")
        self.declare_parameter("image_save_dir", "/tmp/vda5050_bridge_images")

        self._serial_number = str(self.get_parameter("serial_number").value)
        self._camera_topic = str(self.get_parameter("camera_topic").value)
        self._image_save_dir = Path(str(self.get_parameter("image_save_dir").value))
        self._image_save_dir.mkdir(parents=True, exist_ok=True)

        self._nav_client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self._latest_image: Image | None = None
        self._current_goal_handle: ClientGoalHandle | None = None
        self.create_subscription(Image, self._camera_topic, self._on_image, 1)

        self._header_id = 0
        self._current_order_id = ""
        self._current_actions: dict[str, dict[str, str]] = {}
        self._driving = False
        self._paused = False
        self._cancelled = False

        self._mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._mqtt.on_message = self._on_mqtt_message
        self._mqtt.connect(
            str(self.get_parameter("mqtt_host").value),
            int(self.get_parameter("mqtt_port").value),
        )
        self._mqtt.subscribe(_topic(self._serial_number, "order"))
        self._mqtt.subscribe(_topic(self._serial_number, "instantActions"))
        self._mqtt.loop_start()

        self._publish_connection("ONLINE")
        self.create_timer(1.0, self._publish_state)

        self.get_logger().info(f"vda5050_bridge online for {self._serial_number}")

    # --- camera ---

    def _on_image(self, msg: Image) -> None:
        self._latest_image = msg

    def _save_current_image(self, action_id: str) -> str:
        if self._latest_image is None:
            return ""
        # Imported lazily: cv_bridge/cv2 are ROS-image-only concerns, kept
        # out of the module's top-level imports so the rest of this file
        # stays readable independent of them.
        import cv2
        from cv_bridge import CvBridge

        cv_image = CvBridge().imgmsg_to_cv2(self._latest_image, desired_encoding="bgr8")
        path = self._image_save_dir / f"{action_id}.jpg"
        cv2.imwrite(str(path), cv_image)
        return str(path)

    # --- MQTT in ---

    def _on_mqtt_message(self, client: mqtt.Client, userdata: object, message: Any) -> None:
        payload = json.loads(message.payload.decode("utf-8"))
        if message.topic.endswith("/order"):
            self._handle_order(payload)
        elif message.topic.endswith("/instantActions"):
            self._handle_instant_actions(payload)

    def _handle_order(self, payload: dict[str, Any]) -> None:
        self._current_order_id = payload["orderId"]
        self._current_actions = {}
        self._cancelled = False
        nodes = payload["nodes"]
        for node in nodes:
            for action in node.get("actions", []):
                self._current_actions[action["actionId"]] = {
                    "type": action["actionType"],
                    "status": "WAITING",
                }
        # Driving blocks on Nav2 goal completion, so it runs off the
        # executor thread; the executor (rclpy.spin) keeps handling MQTT
        # callbacks and Nav2 action responses concurrently.
        threading.Thread(target=self._drive_order, args=(nodes,), daemon=True).start()

    def _drive_order(self, nodes: list[dict[str, Any]]) -> None:
        self._driving = True
        for node in nodes:
            if self._cancelled:
                break
            while self._paused and not self._cancelled:
                time.sleep(0.2)
            position = node["nodePosition"]
            self._navigate_to(position["x"], position["y"], position.get("theta", 0.0))
            if self._cancelled:
                break
            for action in node.get("actions", []):
                self._current_actions[action["actionId"]]["status"] = "RUNNING"
                self._publish_state()
                time.sleep(1.0)  # simulated inspection dwell
                image_path = self._save_current_image(action["actionId"])
                self._current_actions[action["actionId"]]["status"] = "FINISHED"
                self._current_actions[action["actionId"]]["result"] = image_path
        self._driving = False
        self._publish_state()

    def _navigate_to(self, x: float, y: float, theta: float) -> None:
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = "map"
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.orientation.z = math.sin(theta / 2.0)
        goal.pose.pose.orientation.w = math.cos(theta / 2.0)

        self._nav_client.wait_for_server()
        goal_handle = _wait_for_future(self._nav_client.send_goal_async(goal))
        if not goal_handle.accepted:
            self.get_logger().warning("Nav2 rejected the goal")
            return
        self._current_goal_handle = goal_handle
        _wait_for_future(goal_handle.get_result_async())
        self._current_goal_handle = None

    def _handle_instant_actions(self, payload: dict[str, Any]) -> None:
        for action in payload["actions"]:
            action_type = action["actionType"]
            if action_type == "startPause":
                self._paused = True
            elif action_type == "stopPause":
                self._paused = False
            elif action_type == "cancelOrder":
                self._cancelled = True
                self._paused = False
                if self._current_goal_handle is not None:
                    self._current_goal_handle.cancel_goal_async()

    # --- MQTT out ---

    def _next_header(self) -> dict[str, Any]:
        self._header_id += 1
        return {
            "headerId": self._header_id,
            "timestamp": str(time.time()),
            "version": "2.0",
            "manufacturer": MANUFACTURER,
            "serialNumber": self._serial_number,
        }

    def _publish_connection(self, state: str) -> None:
        payload = {**self._next_header(), "connectionState": state}
        self._mqtt.publish(
            _topic(self._serial_number, "connection"), json.dumps(payload), qos=1, retain=True
        )

    def _publish_state(self) -> None:
        action_states = [
            {
                "actionId": action_id,
                "actionType": info["type"],
                "actionStatus": info["status"],
                "resultDescription": info.get("result", ""),
            }
            for action_id, info in self._current_actions.items()
        ]
        payload = {
            **self._next_header(),
            "orderId": self._current_order_id,
            "driving": self._driving,
            "actionStates": action_states,
            "batteryState": {"batteryCharge": 80.0, "charging": False},
            "errors": [],
        }
        self._mqtt.publish(_topic(self._serial_number, "state"), json.dumps(payload), qos=1)


def main() -> None:
    rclpy.init()
    node = Vda5050BridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
