# ROS 2 Jazzy + Gazebo Harmonic + TurtleBot4, for the ros2_bridge half of
# adapters/vda5050_amr/ (CLAUDE.md section 4.5, ADR-001). No arm64 build
# of osrf/ros:jazzy-desktop exists as of this writing -- this runs under
# x86_64 emulation on Apple Silicon. See ADR-005 for the feasibility
# investigation and what that means for CI.
FROM osrf/ros:jazzy-desktop

SHELL ["/bin/bash", "-c"]

RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        ros-jazzy-turtlebot4-simulator \
        ros-jazzy-turtlebot4-gz-bringup \
        ros-jazzy-turtlebot4-navigation \
        ros-jazzy-turtlebot4-desktop \
        python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages paho-mqtt>=2.0

WORKDIR /ros2_bridge_ws
