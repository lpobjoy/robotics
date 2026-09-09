# adapters/spot

CLAUDE.md section 4.5. Status: **`BUILT_AGAINST_SDK_TESTED_WITH_FAKE`**,
built at build-sequence step 12. No public Spot simulator exists, so
unlike `adapters/vda5050_amr` there is no `RUN_IN_SIM` half to build
here at all -- this is the whole adapter.

## What's here

- `src/spot/adapter.py` -- `SpotAdapter`, implementing router's
  `FleetAdapter` protocol against the real `bosdyn-client` SDK's
  `GraphNavClient`: `dispatch` calls a real `navigate_to()` RPC to a
  mapped waypoint; `status` polls a real `navigation_feedback()` RPC and
  maps GraphNav's status enum onto `MissionStatus`; `resume` re-issues
  `navigate_to()`. `pause` and `abort` don't have a clean GraphNav RPC
  to call (see "Not covered" below) -- `abort` is handled locally
  (marks the mission `ABORTED`, frees the robot), `pause` is a
  documented no-op.

## Tested against a real gRPC server, the same way the SDK vendor does

`tests/fake_graph_nav_service.py` is a real gRPC servicer subclassing
the generated `GraphNavServiceServicer`, run on a real (in-process,
loopback) `grpc.server`. This mirrors Boston Dynamics' own
`bosdyn-client` unit tests almost exactly -- see `test_graph_nav_client.py`
in their `spot-sdk` repo, which fakes the same service the same way, for
the same reason: there's no public Spot simulator to run integration
tests against instead.

## Said plainly (CLAUDE.md's honesty rule)

`bosdyn-client`'s real robot connection flow -- `create_robot()`,
`authenticate()`, time-sync, lease acquisition, directory service
lookup -- is not exercised here. There's no real robot or Boston
Dynamics cloud account to authenticate against in this repo, and
building a fake for all of that just to reach `GraphNavClient` would
test `bosdyn-client`'s own plumbing, not this adapter's logic.
`tests/conftest.py` instead constructs a bare `GraphNavClient()` and
assigns its `.channel` and `._timesync_endpoint` directly -- exactly
what `bosdyn-client`'s own unit tests do, for the same reason.

Two capabilities CLAUDE.md section 4.5 names for this adapter are
consequently **not** exercised by anything here: the lease-based
"mission API" (robot command execution, e-stop, lease administration)
and data acquisition for the camera payload. Neither has a
`FleetAdapter` protocol method to hang off of -- `adapters/vda5050_amr`
has the same gap, since its own camera capture lives in `ros2_bridge/`,
not `adapter.py`. Both are real, documented `bosdyn-client` capabilities
this repo could wire up later; this adapter doesn't currently call
them.

## Not covered

- `pause()`/`abort()` have no matching GraphNav RPC in this adapter's
  scope -- GraphNav's `navigate_to` doesn't expose a "pause in place"
  command the way VDA 5050's `instantActions` does. A real
  implementation would need a separate `RobotCommandClient` (Spot's
  `stop()` command) that this adapter doesn't hold. `pause()` is
  therefore an honest no-op, not a faked success; `abort()` only
  updates this adapter's own local state (marks the mission `ABORTED`
  and frees the robot for another dispatch) without commanding the
  robot to actually stop.
- No `OFFLINE` availability state, unlike `adapters/vda5050_amr` and
  `adapters/unitree`: GraphNav's request/response RPCs don't have a
  continuous telemetry stream this adapter subscribes to, so there's no
  "haven't heard from it in N seconds" signal to derive one from the
  way the other two adapters do.
- `telemetry_stream()` returns nothing yet, same seam as the other
  adapters.
- The lease-based mission API and camera data acquisition, as above.

## Running it

```bash
uv run pytest adapters/spot
```

No Docker, no native build -- `bosdyn-client` and its dependencies
(including `grpcio`) have ordinary prebuilt wheels.
