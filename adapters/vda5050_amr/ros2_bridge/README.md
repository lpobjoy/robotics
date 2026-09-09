# ros2_bridge

The ROS 2 half of `adapters/vda5050_amr/` (CLAUDE.md section 4.5): a real
ROS 2 (Jazzy) `ament_python` package that subscribes to VDA 5050
order/instantActions over MQTT and is meant to drive Nav2; the other
half (`../src/vda5050_amr/`) speaks only MQTT and has no ROS dependency
at all. See ADR-001 (Jazzy + Gazebo Harmonic) and ADR-005 (feasibility
investigation on this laptop).

## Status: real infrastructure built and substantially verified, goal-reaching not yet proven

Verified directly, on this machine, via `deploy/vda5050_amr/Dockerfile`
(`osrf/ros:jazzy-desktop`, x86_64 under emulation on Apple Silicon --
see ADR-005 and its follow-up section):

- The image builds and installs `ros-jazzy-turtlebot4-simulator`,
  `-gz-bringup`, and `-navigation` successfully.
- Gazebo Harmonic (`gz sim`, version 8.11.0) boots **headless** and
  loads the TurtleBot4 warehouse world -- confirmed via
  `/world/warehouse/*` topics being live.
- The TurtleBot4 robot spawns into that running headless world
  successfully: camera/sensor bridges are created, `joint_state_broadcaster`
  and the diff-drive controller load and activate, no crashes.
- `vda5050_bridge/bridge_node.py`, running for real (not just written):
  connects to a real MQTT broker, comes online, receives a real VDA 5050
  order, and drives it -- confirmed by publishing a real order over MQTT
  and watching the bridge node's own `state` messages update.
- Nav2's **full lifecycle activates** against this setup --
  `lifecycle_manager_navigation: Managed nodes are active` -- and it
  accepts and actively pursues a real `NavigateToPose` goal the bridge
  node sends it (`bt_navigator: Begin navigating from current location
  ... to ...`, `controller_server: Passing new path to controller`).

Getting there took four real fixes, kept here rather than silently
smoothed over:

1. The vendored `turtlebot4_gz_bringup/launch/sim.launch.py` always
   launches Gazebo's Qt GUI client (`--gui-config`, no server-only
   option). In a container with no X display that crashes immediately
   (`qt.qpa.xcb: could not connect to display`, then abort). Fixed with
   a from-scratch `launch/headless_sim.launch.py` that passes
   `-s --headless-rendering` instead.
2. That rewrite initially dropped `sim.launch.py`'s
   `GZ_SIM_RESOURCE_PATH` environment setup, so `gz sim` couldn't find
   `warehouse.sdf` ("Unable to find or download file"). Restored it.
3. `launch/bridge.launch.py` originally included the vendored
   `turtlebot4_gz.launch.py` with a `headless: "true"` launch argument,
   expecting that to route around fix #1. It didn't:
   `turtlebot4_gz.launch.py` never declares or reads a `headless`
   argument at all, so it always calls the same broken `sim.launch.py`
   from fix #1 regardless -- confirmed directly by running it and
   finding the exact `qt.qpa.xcb` crash again. Fixed by having
   `bridge.launch.py` include `headless_sim.launch.py` and
   `turtlebot4_spawn.launch.py` directly instead of going through
   `turtlebot4_gz.launch.py` at all.
4. Once a robot is actually spawned, `--headless-rendering` alone isn't
   enough: Gazebo's *sensor* render thread (needed for the robot's
   camera) still opens a real GLX/X11 context and aborts the same way
   fix #1 did (`Couldn't open X display` inside an `Ogre::RenderingAPIException`,
   this time from `gz-sim-sensors-system`, not the GUI client) the
   moment a camera-equipped robot loads -- confirmed directly: it never
   happened in the camera-less headless boot alone, only once
   `turtlebot4_spawn.launch.py` actually spawned the TurtleBot4. Fixed
   by running the whole launch under `xvfb-run` (a virtual, software-
   rendered X display) -- see `deploy/vda5050_amr/Dockerfile`.

**Not yet proven**: the robot actually *reaching* a commanded goal pose.
With Nav2's lifecycle active and a real goal accepted, the
`controller_server` gets stuck re-planning a fresh path roughly once a
second without visible net progress toward the goal (odometry after
~90 seconds pursuing a 1-metre goal: displaced by tenths of a metre in
directions inconsistent with simply not having arrived yet), alongside
repeated `Control loop missed its desired rate of 20.0000 Hz. Current
loop rate is inf Hz.` warnings -- an "inf Hz" reading is the signature
of the controller measuring zero elapsed time between loop iterations,
which points at `/clock` (simulation time) not advancing smoothly
enough under this level of x86_64 emulation for Nav2's real-time
control-loop assumptions to hold, rather than a configuration mistake
in this package. This is a materially more specific finding than
before (previously: Nav2 wasn't even reachable because Gazebo itself
kept crashing) but it is a genuine, not-yet-closed gap, and likely a
harder one -- it points at the simulation's effective real-time factor
under emulation, not at another missed launch-file argument.
`vda5050_bridge/bridge_node.py`'s camera-grab-on-inspection step is
consequently also still unverified, since it only runs once a mission
reaches its final waypoint.

This means `adapters/vda5050_amr/` as a whole is **still not yet
honestly `RUN_IN_SIM`** in the full sense CLAUDE.md section 4.5 asks
for -- "first real robot in sim completes a work order" is not
demonstrated. It is real, substantially-verified infrastructure with a
precisely identified remaining gap -- now much narrower than before --
not `DESCRIBED_NOT_BUILT` either. Anyone picking this up next knows
exactly where it stops and why.

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
- `launch/bridge.launch.py` -- brings up the TurtleBot4 sim (via
  `headless_sim.launch.py` and `turtlebot4_spawn.launch.py` directly,
  not the vendored `turtlebot4_gz.launch.py` -- see fix #3 above),
  SLAM, Nav2, and this bridge node together. Run for real (see Status);
  goal-reaching itself is not yet proven.
- `scripts/send_test_order.py` -- a one-off manual script, not part of
  the package and not run by any test: publishes a real VDA 5050 order
  over MQTT to a running bridge node and prints its `state` updates.
  What was actually used to drive the manual verification above.

## Why this can't run through `uv run pytest`

`rclpy`, `nav2_msgs`, `geometry_msgs`, `sensor_msgs`, and `cv_bridge` are
not pip-installable into this repo's uv workspace venv -- they only
exist inside a real ROS 2 environment. This package is built and (to the
extent above) tested inside `deploy/vda5050_amr/Dockerfile`, entirely
outside the uv workspace, using ROS 2's own `colcon`/`ament` tooling, not
`uv run pytest`. See ADR-005.

## Running it

Needs a real MQTT broker reachable from the container (a plain
`docker run eclipse-mosquitto:2` on the same Docker network works; see
`deploy/docker-compose.yml`'s `mosquitto` service for the config).

```bash
docker build -f deploy/vda5050_amr/Dockerfile -t vda5050-amr-sim .
docker run --rm -it --network <your-mosquitto-network> \
  -v "$(pwd)/adapters/vda5050_amr/ros2_bridge:/ros2_bridge_ws/src/vda5050_bridge" \
  vda5050-amr-sim bash
# inside the container:
source /opt/ros/jazzy/setup.bash
cd /ros2_bridge_ws && colcon build --symlink-install
source install/setup.bash
xvfb-run -a ros2 launch vda5050_bridge bridge.launch.py mqtt_host:=<mosquitto-hostname>
```

Then, from anywhere that can reach the same broker:

```bash
python3 adapters/vda5050_amr/ros2_bridge/scripts/send_test_order.py <mosquitto-host> 1883 1.0 0.0
```

`xvfb-run` is required (see fix #4 above) -- running `ros2 launch`
directly, without it, boots Gazebo and spawns the robot but then
crashes the instant the robot's camera sensor tries to initialize.
