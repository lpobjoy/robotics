# audit

Append-only audit log correlating every decision and robot command to a
work order and mission, with actor identity on every row. See CLAUDE.md
section 4.7.

As of step 4: `models.py` (`AuditEvent`) and `sink.py` (the `AuditSink`
protocol plus `InMemoryAuditSink`) -- enough for router's "audit hooks"
requirement. `router.Router` writes through this on every dispatch,
pause, resume, and abort.

Not yet built (step 5): the persistent, append-only store and machine
identity on the fake adapter. That will implement the same `AuditSink`
protocol, so `router` and anything else writing through it won't need to
change.

## Running it

```bash
uv run pytest audit
```
