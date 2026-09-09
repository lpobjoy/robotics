# adapters/vda5050_amr

CLAUDE.md section 4.5. Status: **split, label each half** (same pattern
CLAUDE.md already uses for `adapters/unitree/`) --

- **The `FleetAdapter`/MQTT half (`src/`): `BUILT_AGAINST_SDK_TESTED_WITH_FAKE`.**
  "SDK" here means the VDA 5050 v2.x message spec, not a vendor library --
  there is no vendor SDK for an open protocol. Built and tested against a
  real MQTT broker (Mosquitto, via Docker) and a fake robot
  (`tests/fake_robot.py`) standing in for the real ROS 2 bridge + Gazebo
  robot.
- **The ROS 2 + Gazebo + Nav2 half: real infrastructure built and
  partially verified, not yet the full `RUN_IN_SIM` loop.** Headless
  Gazebo Harmonic boots and the TurtleBot4 robot spawns into it,
  confirmed directly on this laptop; Nav2 driving the robot and the
  bridge node completing a mission through it are not yet verified end
  to end. See `ros2_bridge/README.md` for exactly what's proven and
  what's left, and ADR-005 for the feasibility investigation (this
  environment has no arm64 ROS 2 image and runs the stack under x86_64
  emulation).

## Why split this way

Section 4.5 is explicit: "The adapter speaks only VDA 5050 over MQTT to
the robot. It must not reach into ROS directly. That separation is the
point." That's a real architectural boundary, not just a testing
convenience -- `src/vda5050_amr/` has no ROS imports at all, and never
will. It only ever talks MQTT.

## What's here

- `messages.py` -- Pydantic models for a pragmatically-scoped subset of
  VDA 5050 v2.x: `Header`, `Order`/`Node`/`Edge`/`Action` (enough to send
  a sequence of waypoints with an inspection action at the end),
  `InstantActions`, `State`, `Visualization`, `Connection`. Not the full
  spec (no zone sets, no multi-map, no full action-parameter-type
  system) -- see the module docstring for exactly what's excluded and
  why it isn't needed here.
- `topics.py` -- VDA 5050's topic naming convention:
  `uagv/v2/<manufacturer>/<serialNumber>/<order|instantActions|state|visualization|connection>`.
- `adapter.py` -- `Vda5050Adapter`, implementing router's `FleetAdapter`
  protocol entirely in terms of MQTT publish/subscribe: `dispatch`
  publishes a real `Order`; `pause`/`resume`/`abort` publish
  `InstantActions` (`startPause`/`stopPause`/`cancelOrder`); `status` and
  `capabilities` are derived from the latest `state`/`connection`
  messages received. Since step 10: the adapter also tracks when the
  last message of *any* kind arrived, independent of that message's
  content -- if the MQTT link itself drops, no further messages arrive
  at all, so staleness has to be measured by elapsed time, not inferred
  from a `connection` payload that will never come. Past
  `connectivity_timeout_s` (default 15s, configurable per adapter
  instance) with nothing heard, `capabilities()` reports the robot
  `OFFLINE` and `status()` reports any in-flight mission `FAILED` with a
  `connectivity lost` detail message -- CLAUDE.md section 4.7's
  "connectivity loss beyond a threshold" escalation trigger.

## Degraded mode (CLAUDE.md section 6, step 10)

`tests/test_degraded_mode.py` proves the full scenario end to end: cut
the MQTT link mid-mission, the mission fails via the connectivity-loss
detection above, that failure is escalated to a human through the same
`MissionTools` surface the agent uses, and a human then resumes or
aborts it -- with the audit trail correlating every step back to the
work order. Unlike `tests/test_adapter.py`, this test wires up a real
EAM, a real `Router`, and the real `Vda5050Adapter` together (not just
the adapter against `FakeRobot` in isolation), so the failure that
triggers escalation is a genuine dropped connection, not a status forced
by hand.

## Not covered

- `telemetry_stream()` returns nothing yet -- live telemetry ingestion is
  step 8's job.
- No zone sets, multi-map support, or the full VDA 5050 action-parameter
  type system.
- Position tracking is coarse: the adapter reports the mission's target
  location once dispatched, not a continuously updated position derived
  from `visualization` messages. Real position tracking is part of
  step 8's telemetry work.

## Running the tests

Needs Docker (spins up a real, ephemeral Mosquitto broker):

```bash
uv run pytest adapters/vda5050_amr
```

These are real MQTT round trips over a real broker, not mocked. This
surfaced as intermittent `_wait_until` timeouts, a different test each
time, both locally and in CI on GitHub-hosted runners. It was a real
race, not just slow hardware: `paho-mqtt`'s `subscribe()` returns as
soon as the SUBSCRIBE packet is queued on the wire, not once the broker
has actually registered the filter. Every fixture here has one client
subscribe and a second, independent client publish right after --
there's no guarantee the broker processes the SUBSCRIBE before the
PUBLISH lands, and when it doesn't, the message is simply never
delivered (no error, no retry, just a wait that times out). Fixed by
`_subscribe_and_wait` (`src/vda5050_amr/adapter.py`, duplicated for
tests in `tests/fake_robot.py`), which blocks on the SUBACK via
`on_subscribe` before the constructor -- or the test -- proceeds. Worth
keeping an eye on for CI-only slowness beyond that (container pull time,
noisy-neighbor scheduling), but the subscribe race was the actual bug.
