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

## Follow-up: pushing past the original stopping point

After all 15 build-sequence steps landed, a later session returned to
close the "not yet verified" gap above, now with no step-budget
pressure forcing an early stop. Real progress, and a narrower, more
specific remaining gap:

Two more real bugs found and fixed, the same way the two above were --
by actually running it and reading what broke, not by reasoning about
what should work:

- `ros2_bridge/launch/bridge.launch.py` passed `headless: "true"` to
  the vendored `turtlebot4_gz.launch.py`, expecting it to route around
  the GUI-crash bug this ADR already fixed once via
  `headless_sim.launch.py`. It didn't: `turtlebot4_gz.launch.py` never
  declares or reads a `headless` argument at all, so it always calls
  the same broken `sim.launch.py` regardless -- confirmed directly by
  running it and getting the exact same `qt.qpa.xcb` crash again.
  Fixed by having `bridge.launch.py` include `headless_sim.launch.py`
  and `turtlebot4_spawn.launch.py` directly, bypassing
  `turtlebot4_gz.launch.py` entirely.
- Once a robot is actually spawned into the headless world,
  `--headless-rendering` alone isn't sufficient: Gazebo's *sensor*
  render thread (needed for the robot's camera) still opens a real
  GLX/X11 context to initialize, and aborts the same way the original
  GUI crash did -- confirmed directly, and only reproducible once a
  camera-equipped robot is actually present, which is why it wasn't
  seen during this ADR's original headless-boot-only check. Fixed with
  `xvfb-run` (a virtual, software-rendered X display) wrapping the
  whole launch -- see `deploy/vda5050_amr/Dockerfile`.

With both fixed: Nav2's **full lifecycle activates**
(`lifecycle_manager_navigation: Managed nodes are active`), and it
accepts and actively pursues a real `NavigateToPose` goal sent by
`vda5050_bridge/bridge_node.py` in response to a real VDA 5050 order
published over MQTT -- proving the bridge node itself works, end to
end, up to that point.

What's still not proven, and now a much more specific finding than
before: the robot actually *reaching* the commanded goal. The
`controller_server` gets stuck re-planning a fresh path roughly once a
second without visible net progress, alongside repeated `Control loop
missed its desired rate of 20.0000 Hz. Current loop rate is inf Hz.`
warnings. An "inf Hz" reading means the controller measured zero
elapsed time between loop iterations -- the signature of `/clock`
(simulation time) not advancing smoothly enough under this level of
x86_64 emulation for Nav2's real-time control-loop assumptions to hold.
This reads as a real-time-factor problem with the emulation itself,
not a configuration mistake in this package's launch files or
parameters -- and, unlike the previous two bugs, not one a launch-file
fix is likely to resolve. Closing it would most plausibly need either
faster hardware (a native x86_64 or arm64 host, avoiding emulation
entirely) or a deliberately slowed-down/relaxed Nav2 control-loop
configuration tolerant of an inconsistent simulation clock -- both
outside what this investigation's remaining time budget covered.

See `adapters/vda5050_amr/ros2_bridge/README.md`'s Status section for
the full, current, precise account of what's proven and what isn't.

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
