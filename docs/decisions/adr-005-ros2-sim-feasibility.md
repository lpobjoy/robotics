# ADR-005: Running ROS 2 Jazzy + Gazebo Harmonic + TurtleBot4 on this laptop

## Status

Accepted

## Context

This repo is built on macOS (Apple Silicon, arm64), no GPU passthrough.
CLAUDE.md section 5 pins ROS 2 (Humble or Jazzy) and Gazebo; ADR-001
already picked Jazzy + Gazebo Harmonic, with TurtleBot4 as the named
fallback if TurtleBot3 support on Harmonic proved rough.

Before writing the VDA 5050 bridge node against a stack that might not
actually run here, this was checked directly:

- `osrf/ros:jazzy-desktop` has **no arm64 build**. It only runs via
  x86_64 emulation (Docker Desktop's Rosetta/QEMU) on Apple Silicon.
- Under that emulation, basic `ros2` CLI commands complete in a few
  seconds -- slow relative to native, not unusable.
- `ros-jazzy-turtlebot4-simulator`, `ros-jazzy-turtlebot4-gz-bringup`,
  and `ros-jazzy-turtlebot4-navigation` are all real, installable
  packages for Jazzy. `gz sim --version` reports Gazebo Sim (Harmonic)
  8.11.0 after installing them -- the simulator itself is present and
  runs.
- Package installation (`apt-get install`) for the TurtleBot4 + Gazebo +
  Nav2 stack completes in a few minutes under emulation, which is a real
  but tolerable cost for a Docker image build.

## Decision

Build `adapters/vda5050_amr/ros2_bridge/` as a real ROS 2 ament_python
package against this stack (Jazzy, Gazebo Harmonic, TurtleBot4, Nav2),
running in `deploy/vda5050_amr/Dockerfile` (based on
`osrf/ros:jazzy-desktop`, x86_64, run under emulation on this laptop).

Tested directly, in that container, on this laptop:

- Gazebo Harmonic boots **headless** and loads the TurtleBot4 warehouse
  world (confirmed via live `/world/warehouse/*` topics). This needed
  two real fixes: the vendored `sim.launch.py` hardcodes a GUI client
  with no server-only option, which crashes on a container with no X
  display (`qt.qpa.xcb: could not connect to display`); and a
  from-scratch headless launch file initially dropped the
  `GZ_SIM_RESOURCE_PATH` environment setup the world file needed to be
  found at all. Both are fixed in
  `adapters/vda5050_amr/ros2_bridge/launch/headless_sim.launch.py`.
- The TurtleBot4 robot spawns into that running world successfully:
  camera/sensor bridges create, the joint-state and diff-drive
  controllers load and activate, no crashes.
- Not yet verified: Nav2 actually driving the robot to a goal pose here,
  and the VDA 5050 bridge node (written, not run against a live action
  server yet) actually dispatching a mission through it. See
  `adapters/vda5050_amr/ros2_bridge/README.md` for the precise,
  up-to-date status -- this ADR records the feasibility finding
  (yes, with two identified fixes), not a claim that the full loop has
  been proven end to end.

## Consequences

- CI (`docs/standards.md`/`.github/workflows/ci.yml`) will need a
  separate job for this, not part of the main `uv run pytest` matrix:
  `rclpy` and the ROS 2 message packages this bridge node imports
  (`nav2_msgs`, `geometry_msgs`, `sensor_msgs`, `cv_bridge`) are not
  pip-installable into this repo's uv workspace venv -- they only exist
  inside a ROS 2 environment. The bridge node's logic is consequently
  untestable via `uv run pytest`; it can only be exercised inside the
  container described above.
- If a real GPU/Linux machine becomes available later, the same
  Dockerfile should run natively (no emulation) and this ADR's
  performance caveat goes away -- nothing about the adapter code itself
  is emulation-specific.
