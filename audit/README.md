# audit

Append-only audit log correlating every decision and robot command to a
work order and mission, with actor identity on every row. See CLAUDE.md
section 4.7.

Built at build-sequence step 5.

## What's here

- `models.py` -- `AuditEvent`: actor, action, timestamps, and
  correlation ids (`work_order_id`, `mission_id`).
- `sink.py` -- the `AuditSink` protocol, plus `InMemoryAuditSink` (used
  by tests, and as `router.Router`'s default when no sink is given).
- `sqlite_sink.py` -- `SqliteAuditSink`: the real, persistent,
  append-only store (plain `sqlite3`, same rationale as `eam/db.py`).
  Append-only in the literal sense -- there is no update or delete
  method, and nothing in this codebase runs `UPDATE`/`DELETE` against the
  `audit_events` table. `list_events_for_mission` and
  `list_events_for_work_order` are how a whole mission's or work order's
  history is recovered as one ordered thread.

`router.Router` writes through whichever sink it's given on every
dispatch, pause, resume, abort, and (with identity configured) adapter
registration and rejection.

## Not covered

- No log shipping, retention policy, or tamper-evidence (hash chaining,
  signing) beyond SQLite's own durability.

## Running it

```bash
uv run pytest audit
```
