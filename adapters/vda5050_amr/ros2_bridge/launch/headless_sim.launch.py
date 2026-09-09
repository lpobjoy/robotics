"""A headless variant of turtlebot4_gz_bringup's sim.launch.py.

The vendored sim.launch.py hardcodes `--gui-config` on the `gz sim`
invocation with no server-only option, so it always launches Gazebo's Qt
GUI client -- which crashes immediately in a container with no X
display (confirmed directly: `qt.qpa.xcb: could not connect to display`,
then abort). This launch file is the same thing minus the GUI: `gz_args`
gets `-s` (server only) instead of `--gui-config`, and there is no
clock/GUI bridge for a GUI that was never started.
"""

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node

ARGUMENTS = [
    DeclareLaunchArgument("world", default_value="warehouse", description="Simulation World"),
]


def generate_launch_description() -> LaunchDescription:
    pkg_ros_gz_sim = get_package_share_directory("ros_gz_sim")
    pkg_turtlebot4_gz_bringup = get_package_share_directory("turtlebot4_gz_bringup")
    pkg_turtlebot4_description = get_package_share_directory("turtlebot4_description")
    pkg_irobot_create_description = get_package_share_directory("irobot_create_description")
    pkg_irobot_create_gz_bringup = get_package_share_directory("irobot_create_gz_bringup")
    gz_sim_launch = PathJoinSubstitution([pkg_ros_gz_sim, "launch", "gz_sim.launch.py"])

    # Same resource path sim.launch.py sets up -- dropped when this file
    # was written as a from-scratch headless variant of it, and gz sim
    # couldn't find warehouse.sdf without it (confirmed directly: "Unable
    # to find or download file").
    gz_resource_path = SetEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=":".join(
            [
                os.path.join(pkg_turtlebot4_gz_bringup, "worlds"),
                os.path.join(pkg_irobot_create_gz_bringup, "worlds"),
                str(Path(pkg_turtlebot4_description).parent.resolve()),
                str(Path(pkg_irobot_create_description).parent.resolve()),
            ]
        ),
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([gz_sim_launch]),
        launch_arguments=[
            (
                "gz_args",
                [LaunchConfiguration("world"), ".sdf", " -r", " -s", " --headless-rendering"],
            ),
        ],
    )

    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="clock_bridge",
        output="screen",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
    )

    ld = LaunchDescription(ARGUMENTS)
    ld.add_action(gz_resource_path)
    ld.add_action(gazebo)
    ld.add_action(clock_bridge)
    return ld
