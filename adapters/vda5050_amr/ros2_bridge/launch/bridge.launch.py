"""Launches the VDA 5050 bridge node alongside the TurtleBot4 Gazebo
simulation, SLAM, and Nav2. See ros2_bridge/README.md for how to run
this and what its current status is.

Composes headless_sim.launch.py (this package's own headless Gazebo
boot, ADR-005) with turtlebot4_gz_bringup's own turtlebot4_spawn.launch.py
directly, rather than going through the vendored turtlebot4_gz.launch.py:
that file always includes the vendored sim.launch.py for Gazebo (the one
that hardcodes a GUI client and crashes with no X display -- the same
bug headless_sim.launch.py exists to route around) and does not forward
a `headless` argument to it at all. An earlier version of this file
passed `headless: "true"` to turtlebot4_gz.launch.py expecting it to
have an effect; it didn't -- confirmed directly by running this launch
file and finding Gazebo dead (`qt.qpa.xcb: could not connect to
display`, the exact ADR-005 crash) while `nav2`/`slam` had (confusingly)
still taken effect, because ROS 2 launch's `LaunchConfiguration`s are
looked up by name across the whole launch tree regardless of which
file declares them, not lexically scoped to files that explicitly
forward them.
"""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    mqtt_host = LaunchConfiguration("mqtt_host")
    serial_number = LaunchConfiguration("serial_number")

    pkg_vda5050_bridge = get_package_share_directory("vda5050_bridge")
    pkg_turtlebot4_gz_bringup = get_package_share_directory("turtlebot4_gz_bringup")

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([pkg_vda5050_bridge, "launch", "headless_sim.launch.py"])
        ),
        launch_arguments=[("world", "warehouse")],
    )

    robot_spawn = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [pkg_turtlebot4_gz_bringup, "launch", "turtlebot4_spawn.launch.py"]
            )
        ),
        launch_arguments=[("nav2", "true"), ("slam", "true")],
    )

    bridge_node = Node(
        package="vda5050_bridge",
        executable="bridge_node",
        parameters=[{"mqtt_host": mqtt_host, "serial_number": serial_number}],
        output="screen",
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("mqtt_host", default_value="localhost"),
            DeclareLaunchArgument("serial_number", default_value="amr-01"),
            gazebo,
            robot_spawn,
            bridge_node,
        ]
    )
