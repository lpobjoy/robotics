# Edge deployment

CLAUDE.md section 4.9. How the adapter and MQTT pieces would sit
on-site with intermittent connectivity, store-and-forward, and what
happens when the link to the cloud drops. The connectivity-loss
*detection* half of this is actually built and tested (step 10); the
rest — store-and-forward, an edge/cloud broker split — is described,
not built, and said so plainly below.

## What's actually built: detecting a dropped link

`adapters/vda5050_amr/src/vda5050_amr/adapter.py`'s `Vda5050Adapter`
tracks the wall-clock time of the last MQTT message received, of *any*
kind, independent of that message's content. Past a configurable
`connectivity_timeout_s` (15s by default) with nothing heard, the
adapter reports the robot `OFFLINE` and any in-flight mission `FAILED`
with a `connectivity lost` detail — this is CLAUDE.md section 4.7's
"connectivity loss beyond a threshold" escalation trigger, and it's
exercised against a real MQTT broker with the link genuinely cut
(`adapters/vda5050_amr/tests/test_degraded_mode.py`): dispatch, drop
the robot side's connection, watch the adapter detect it, watch the
agent-equivalent escalation put the work order in `AwaitingHuman`,
watch a human resume or abort it, and watch the audit trail carry the
whole sequence.

The reasoning that shaped this, worth stating because it's the one
subtlety in an otherwise simple timeout: staleness has to be measured
by *elapsed time since the last message*, not by inspecting the
*content* of the last `connection` message received. If the MQTT link
itself drops, no further messages of any kind arrive — there's no
fresh "I'm offline" message to parse, because the thing that would
carry it is exactly what's gone.

## What a real edge site needs that this repo doesn't build

**Store-and-forward at the edge.** A real site would run its own local
MQTT broker (not the single shared Mosquitto this repo runs), with the
robot(s) and any local supervisory logic talking to it regardless of
whether the link to the cloud/central system is up. That local broker
bridges to the cloud broker (Mosquitto's own bridge config, or a
managed IoT broker's bridging feature) when connectivity allows, and
buffers when it doesn't — telemetry keeps accumulating locally,
inspection images keep getting captured, and none of it is lost, it's
just delayed. This repo's `telemetry/` ingestion service subscribes
directly to one broker and writes straight through to a time-series
store and the EAM; there's no local buffering layer in front of it,
because there's only one broker and it's never actually partitioned in
this repo's tests.

**A defined behavior for missions in flight when the link drops.**
Section 4.7's escalation trigger fires immediately in this repo —
15 seconds of silence, and the mission is `FAILED` and a human is
paged. A real site would want a middle state: the robot keeps
executing its last-known command locally (most AMR/quadruped stacks
already do this — losing the supervisory link doesn't necessarily mean
losing the local nav/locomotion loop) while the *supervisory* system
marks the mission as "unconfirmed" rather than immediately failed, and
only escalates to a human after a materially longer timeout, or after
the robot itself reports something has actually gone wrong once the
link is restored. This repo's binary
OFFLINE/FAILED-after-N-seconds model is the right shape for a demo
that needs to *show* the escalation path working end to end in a few
seconds, not the right timeout value for an actual site.

**Reconnection and reconciliation.** When the link comes back, a real
system needs to reconcile: what did the robot actually do while
disconnected, does the mission's recorded state match reality, and
does a human need to review anything before the mission is allowed to
resume automatically. This repo's `approve_escalation`/
`abort_escalation` (`mcp_server/tools.py`) are the human-in-the-loop
half of that decision, but they act on the router's last-known state,
not on anything freshly reconciled with the robot.

**Physical network segmentation**, covered in `security.md` — the OT/IT
boundary a real site needs is a deployment-topology concern that sits
alongside this document, not duplicated here.
