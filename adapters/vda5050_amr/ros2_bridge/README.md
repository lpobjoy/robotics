# ros2_bridge

The ROS 2 half of `adapters/vda5050_amr/` (CLAUDE.md section 4.5): a real
ROS 2 (Jazzy) `ament_python` package that subscribes to VDA 5050
order/instantActions over MQTT and is meant to drive Nav2; the other
half (`../src/vda5050_amr/`) speaks only MQTT and has no ROS dependency
at all. See ADR-001 (Jazzy + Gazebo Harmonic) and ADR-005 (feasibility
investigation on this laptop).

## Status: real infrastructure built and partially verified, not fully proven end to end

Verified directly, on this machine, via `deploy/vda5050_amr/Dockerfile`
(`osrf/ros:jazzy-desktop`, x86_64 under emulation on Apple Silicon --
see ADR-005):

- The image builds and installs `ros-jazzy-turtlebot4-simulator`,
  `-gz-bringup`, and `-navigation` successfully.
- Gazebo Harmonic (`gz sim`, version 8.11.0) boots **headless** and
  loads the TurtleBot4 warehouse world -- confirmed via
  `/world/warehouse/*` topics being live. This took two real fixes,
  kept here rather than silently smoothed over:
  1. The vendored `turtlebot4_gz_bringup/launch/sim.launch.py` always
     launches Gazebo's Qt GUI client (`--gui-config`, no server-only
     option). In a container with no X display that crashes immediately
     (`qt.qpa.xcb: could not connect to display`, then abort). Fixed
     with a from-scratch `launch/headless_sim.launch.py` that passes
     `-s --headless-rendering` instead.
  2. That rewrite initially dropped `sim.launch.py`'s
     `GZ_SIM_RESOURCE_PATH` environment setup, so `gz sim` couldn't find
     `warehouse.sdf` ("Unable to find or download file"). Restored it.
- The TurtleBot4 robot spawns into that running headless world
  successfully via `turtlebot4_gz_bringup/launch/turtlebot4_spawn.launch.py`:
  camera/sensor bridges are created, `joint_state_broadcaster` and the
  diff-drive controller load and activate, no crashes.

**Not yet verified end to end**: Nav2 actually driving the spawned robot
to a goal pose in this headless setup, `vda5050_bridge/bridge_node.py`
(written, not run against a live Nav2 action server yet), and the
camera-grab-on-inspection step. Each of those is a plausible additional
integration point (Nav2 needs a valid map/localization source; the
bridge node's MQTT+rclpy threading needs to be proven against a real
action server, not just written) that would need further iteration under
slow x86_64 emulation to close out.

This means `adapters/vda5050_amr/` as a whole is **not yet honestly
`RUN_IN_SIM`** in the full sense CLAUDE.md section 4.5 asks for --
"first real robot in sim completes a work order" is not demonstrated.
It is real, substantially-verified infrastructure with a precisely
identified remaining gap, not `DESCRIBED_NOT_BUILT` either. Anyone
picking this up next knows exactly where it stops and why.

## What's here

- `package.xml`, `setup.py`, `setup.cfg`, `resource/` -- a standard ROS 2
  `ament_python` package, `vda5050_bridge`.
- `vda5050_bridge/bridge_node.py` -- the bridge node. Connects to MQTT,
  subscribes to `order`/`instantActions`, drives Nav2's `NavigateToPose`
  action per node in the order, grabs a camera frame at the final
  waypoint's inspection action, and publishes `state`/`connection` back.
  Pause/resume are a documented simplification (checked between
  waypoints, not a true Nav2 mid-navigation pause); cancel properly
  cancels the in-flight Nav2 goal. See the module docstring for the full
  detail.
- `launch/headless_sim.launch.py` -- the from-scratch headless
  replacement for the vendored `sim.launch.py`, needed for the reasons
  above.
- `launch/bridge.launch.py` -- brings up the TurtleBot4 sim + Nav2 +
  this bridge node together. Not yet run end to end (see Status).

## Why this can't run through `uv run pytest`

`rclpy`, `nav2_msgs`, `geometry_msgs`, `sensor_msgs`, and `cv_bridge` are
not pip-installable into this repo's uv workspace venv -- they only
exist inside a real ROS 2 environment. This package is built and (to the
extent above) tested inside `deploy/vda5050_amr/Dockerfile`, entirely
outside the uv workspace, using ROS 2's own `colcon`/`ament` tooling, not
`uv run pytest`. See ADR-005.

## Running it

```bash
docker build -f deploy/vda5050_amr/Dockerfile -t vda5050-amr-sim .
docker run --rm -it vda5050-amr-sim bash
# inside the container:
source /opt/ros/jazzy/setup.bash
ros2 launch /path/to/headless_sim.launch.py
# in a second shell into the same container:
ros2 launch turtlebot4_gz_bringup turtlebot4_spawn.launch.py rviz:=false
```

The bridge node itself (`colcon build` this package first, inside the
container) is run with `ros2 run vda5050_bridge bridge_node`.
