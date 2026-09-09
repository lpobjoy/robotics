# adapters/unitree

CLAUDE.md section 4.5. Status: **split, label each half** --

- **Half A (`src/`): `BUILT_AGAINST_SDK_TESTED_WITH_FAKE`.** Built at
  build-sequence step 11. Real `unitree_sdk2py` (the actual Python SDK a
  Go2 deployment uses), real CycloneDDS, tested against a fake of the
  onboard sport service (`tests/fake_sport_service.py`) standing in for
  a real robot.
- **Half B (`unitree_mujoco` sim2sim locomotion): not built yet.**

This is its own standalone `uv` project, not a member of the root
workspace -- see ADR-006 for why (short version: `unitree_sdk2py`'s
`cyclonedds==0.10.2` pin needs a native library built from source, and
CLAUDE.md itself flags CycloneDDS as something that must never share an
environment with the ROS 2 adapter's own DDS stack).

## What's here

- `src/unitree/adapter.py` -- `UnitreeAdapter`, implementing router's
  `FleetAdapter` protocol entirely against the real high-level SDK:
  `dispatch` calls real `StandUp()`/`Move()` RPCs; `pause`/`resume`/
  `abort` call real `StopMove()`/`Move()`/`StopMove()`; `status` and
  `capabilities` are derived from real `SportModeState` telemetry
  (`position`, `error_code`) received over a real DDS subscription.

## Said plainly (CLAUDE.md's honesty rule)

The high-level `SportClient` API this SDK exposes is velocity/gait
control -- `Move(vx, vy, vyaw)`, `StandUp`, `StopMove`, and so on -- not
"navigate to this waypoint." There is no path planner or localization
behind it in this SDK; Unitree's own simulator (`unitree_mujoco`, Half
B) only speaks a *different*, lower-level joint/DDS interface, so there
is no vendor simulator this half could run real navigation against even
if one were built here.

What this half actually proves, tested against a real DDS RPC responder
over loopback (not mocked at the Python object level -- a real
`unitree_sdk2py.rpc.server.Server` subclass, the same base class a real
robot's own service would extend):

- The adapter issues genuine `StandUp`/`Move`/`StopMove` DDS requests a
  real robot would receive and act on, using the real request/response
  protocol (`tests/test_unitree_adapter.py`'s
  `test_dispatch_issues_real_standup_and_move_requests` and the
  pause/resume/abort tests).
- `status()` correctly derives `IN_PROGRESS`/`COMPLETED`/`FAILED` from
  genuine `SportModeState` telemetry fields (`position`, `error_code`),
  not a hardcoded result.

What it does not prove: that `dispatch()`'s single open-loop `Move()`
call actually gets a real robot from A to B. `_heading_towards()` in
`adapter.py` computes one bearing towards the target and never corrects
course from telemetry -- there is no control loop here, because there
is nothing in this SDK to close it with. A real deployment would need
this adapter to sit behind an actual navigation stack (a planner reading
localization and re-issuing `Move()` calls); that isn't built or claimed
here.

## Running it

Needs a native CycloneDDS 0.10.x build first -- there's no prebuilt
wheel for `cyclonedds==0.10.2` on most platforms, and `unitree_sdk2py`'s
Python bindings need `CYCLONEDDS_HOME` pointed at one:

```bash
cd adapters/unitree
git clone --depth 1 -b releases/0.10.x https://github.com/eclipse-cyclonedds/cyclonedds .cyclonedds-src
cmake -S .cyclonedds-src -B .cyclonedds-src/build -DCMAKE_INSTALL_PREFIX=../.cyclonedds-install -DBUILD_EXAMPLES=OFF -DENABLE_SSL=OFF -DENABLE_SECURITY=OFF
cmake --build .cyclonedds-src/build --target install -j 4

export CYCLONEDDS_HOME="$PWD/.cyclonedds-install"
uv sync
uv run pytest
```

`.cyclonedds-src/` and `.cyclonedds-install/` are gitignored -- they're
a local build artifact, not vendored source. `CYCLONEDDS_HOME` needs to
be set for every `uv sync`/`uv run` in this directory, not just the
first one.

## Not covered

- Half B (`unitree_mujoco` sim2sim locomotion under the published
  `unitree_rl_gym` policy) -- not built yet.
- No real navigation, as above -- open-loop velocity commands only.
- `telemetry_stream()` returns nothing yet, same seam as
  `adapters/vda5050_amr` -- step 8's ingestion pipeline doesn't have a
  Unitree source wired up.
- Not part of `deploy/docker-compose.yml` or the root `uv run pytest`
  run yet; a `deploy/unitree/Dockerfile` giving this its own container
  (CLAUDE.md section 4.5) is step 13's job.
