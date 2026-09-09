"""
Append-only audit log correlating every decision and robot command to a
work order and mission, with actor identity on every row. See CLAUDE.md
section 4.7.

As of step 4: the AuditEvent shape and AuditSink protocol, plus an
in-memory sink. The persistent, append-only store lands in step 5.
"""
