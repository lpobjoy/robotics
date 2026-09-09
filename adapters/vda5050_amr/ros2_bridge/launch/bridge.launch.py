"""Launches the VDA 5050 bridge node alongside the TurtleBot4 Gazebo
simulation and Nav2. See ros2_bridge/README.md for how to run this and
what its current status is.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    mqtt_host = LaunchConfiguration("mqtt_host")
    serial_number = LaunchConfiguration("serial_number")

    turtlebot4_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                "/opt/ros/jazzy/share/turtlebot4_gz_bringup/launch/turtlebot4_gz.launch.py",
            ]
        ),
        launch_arguments={"headless": "true", "nav2": "true", "slam": "true"}.items(),
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
            turtlebot4_sim,
            bridge_node,
        ]
    )
