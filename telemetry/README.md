# telemetry

MQTT ingestion of robot state/images into a time-series store, with
images attached back to the EAM work order. See CLAUDE.md section 4.6.

Built at build-sequence step 8.

## What's here

- `models.py` -- `RobotStateEvent`, `ImageEvent`, `FleetEvent`: the
  canonical fleet telemetry shape, deliberately separate from any
  adapter's own native protocol (e.g. VDA 5050's `state`/`visualization`
  topics). This is the normalized view the rest of the fleet reads.
- `topics.py` -- the canonical topic scheme:
  `fleet/<robot_id>/state`, `.../images`, `.../events`.
- `store.py` -- `TelemetryStore`: a time-series table for robot state and
  fleet events, plain `sqlite3` indexed on `(robot_id, timestamp)`.
  TimescaleDB is the documented production-shaped swap (CLAUDE.md section
  4.6); not needed at this demo's scale ("do not over-build").
- `eam_attachments.py` -- `EamAttachmentGateway`: uploads an inspection
  image to the EAM as a work order attachment (`eam`'s existing
  `POST /api/work-orders/{id}/attachments`).
- `ingestion.py` -- `IngestionService`: subscribes to the three fleet
  topics, writes state/events to `TelemetryStore`, and uploads images
  via `EamAttachmentGateway`. A malformed message on any topic is logged
  and dropped, not allowed to crash the service.
- `service.py` / `__main__.py` -- the standalone entrypoint
  (`uv run python -m telemetry`), reading `MQTT_HOST`, `MQTT_PORT`,
  `EAM_BASE_URL`, `TELEMETRY_DB_PATH` from the environment.

## Not covered

- No adapter currently publishes onto this canonical topic scheme.
  `adapters/vda5050_amr/` speaks its own native VDA 5050 topics
  (`uagv/v2/...`) to the router; wiring an adapter to *also* publish
  normalized telemetry here is a natural follow-up, not yet done.
- Image payloads are base64-encoded JSON, not MQTT5 binary + user
  properties -- simpler to implement and test, adequate at this scale.
- OPC UA is `DESCRIBED_NOT_BUILT` (CLAUDE.md section 4.6) -- see
  `docs/security.md` / `docs/standards.md` (step 14) for where it would
  sit.

## Running the tests

Needs Docker (spins up a real, ephemeral Mosquitto broker, same as
`adapters/vda5050_amr`):

```bash
uv run pytest telemetry
```

These tests hit a real broker with a real subscribing client and a
separate real publishing client -- and were intermittently flaky both
locally and in CI, always a different test, always a `_wait_until`
timeout. Root cause: `paho-mqtt`'s `subscribe()` returns once the
SUBSCRIBE packet is queued, not once the broker has registered the
filter, and `IngestionService.__init__` subscribes right before the
test's publisher client sends its first message -- with no guaranteed
ordering between the two, a fast publish could beat the broker's own
processing of the subscription and be delivered to nobody. Fixed in
`ingestion.py` (`_subscribe_and_wait`, same fix as
`adapters/vda5050_amr`): block on the SUBACK via `on_subscribe` before
`IngestionService.__init__` returns.
