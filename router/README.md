# router

Fleet abstraction and dispatch. See CLAUDE.md section 4.4. Built at
build-sequence step 4.

## What's here

- `models.py` -- `Mission`, `MissionHandle`, `MissionStatusReport`,
  `TelemetryEvent`, and the `FleetAdapter` protocol. One documented
  extension beyond section 4.4's literal list: `capabilities()` returns a
  `RobotDescriptor` (capabilities + current availability + current
  location), not a bare capability list -- selection needs all three and
  `capabilities()` is the only query point the spec gives it.
- `router.py` -- `Router`: registers `FleetAdapter`s, and on `dispatch`
  selects the cheapest idle, capable, reachable one (capability match,
  then availability, then shortest-path distance via
  `worldmodel.query.shortest_distance`). Every dispatch, pause, resume,
  and abort writes an `audit.AuditEvent` -- including *why* a robot was
  chosen -- before the adapter is ever called.
- `fake_adapter.py` -- `FakeAdapter`, an in-memory `FleetAdapter` for
  testing. Not one of the labelled statuses in `adapters/`; it's router's
  own test double, reused in step 5 for audit/identity correlation
  testing.

## Not covered

- No persistence of missions or handles -- in-memory only, lost on
  restart. Long-running survive-a-restart supervision is the agent's job
  (CLAUDE.md section 4.3, step 6), not router's.
- No real adapters registered yet -- `adapters/` starts at step 7.

## Running it

```bash
uv run pytest router
```

The acceptance test from CLAUDE.md section 6 step 4 is
`test_released_work_order_becomes_a_dispatched_mission_on_the_fake` in
`tests/test_router.py`.
