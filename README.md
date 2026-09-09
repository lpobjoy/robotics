# robot-router

A working demonstration of an agent-first integration between an enterprise
asset management (EAM) system and heterogeneous robot fleets: a work order
is released, an AI agent turns it into a physical mission, a router
dispatches it to whichever robot can do it, the robot executes it in
simulation, and results flow back with a full audit trail.

This is a portfolio project built by one person on a laptop over a few
weeks. It is **not** a product, **not** fleet-scale, and **not** run on real
hardware. See [`CLAUDE.md`](CLAUDE.md) for the full brief — what this is,
the non-negotiable honesty rules, the architecture, and the exact build
order this repo follows.

## Status

All 15 build-sequence steps (CLAUDE.md section 6) are done. `eam`,
`mcp_server`, `telemetry`, and `console` run together end to end via
`docker compose` or on a local k3d cluster; `agent` runs as a manual CLI
trigger against them. Each component directory has its own `README.md`
stating what it does and which step built it; `docs/decisions/` has an
ADR for every non-obvious choice along the way. The requirements table
below is the honest summary of what that adds up to against the actual
job spec.

## Layout

- `eam/` — mock business system (OData v4 + REST)
- `worldmodel/` — graph over assets, locations, robots, work orders
- `agent/` — mission planning agent (Pydantic AI)
- `router/` — fleet abstraction and dispatch
- `mcp_server/` — MCP tools over the router and EAM, for the agent
- `adapters/` — one package per robot ecosystem (`vda5050_amr`, `unitree`, `spot`)
- `telemetry/` — MQTT ingestion into a time-series store
- `audit/`, `identity/` — append-only audit log, machine identity
- `console/` — thin operator UI (TypeScript, Vite + React)
- `deploy/` — docker-compose and k3d (kustomize) manifests
- `docs/` — job spec, architecture, ADRs, security, edge deployment, standards

## Running it

Requires [`uv`](https://docs.astral.sh/uv/) and Docker.

```bash
uv sync --all-packages --all-groups
uv run pytest --ignore=adapters/unitree
```

`adapters/unitree` is its own standalone `uv` project, not a member of this
workspace: its SDK dependency (`unitree_sdk2py`) needs a native CycloneDDS
build that the rest of the repo has no reason to carry, and CLAUDE.md
section 4.5 flags CycloneDDS as something that must never share an
environment with the ROS 2 adapter's own DDS stack. See
`adapters/unitree/README.md` for how to set it up and run its tests on
their own.

```bash
docker compose -f deploy/docker-compose.yml up
```

Starts Mosquitto, `eam` (`:8000`), `mcp_server`'s HTTP API (`:8001`),
`telemetry`, and the console (`:5173`). Release a work order in the
console, then process it with the agent (needs `ANTHROPIC_API_KEY`):

```bash
ANTHROPIC_API_KEY=... docker compose -f deploy/docker-compose.yml run --rm agent <work_order_id>
```

See `deploy/docker-compose.yml`'s own comments for exactly what's
*not* included (the ROS 2 + Gazebo half of `adapters/vda5050_amr`,
`adapters/unitree`/`adapters/spot` which have no server component of
their own, and why the agent is a manual step rather than automatic).
`deploy/k3d/README.md` has the same stack running on a local k3d
cluster instead.

## Requirements table

Every line of `docs/job-spec.md`'s "What you will do" and "Technical
depth expected" sections (CLAUDE.md section 8's format). The "Job spec
requirement" column paraphrases; `docs/job-spec.md` has the verbatim
text. One row can only carry one status, so where a single bullet
bundles something built with something not, the strongest true claim
is the status and the gap is named in "Not covered" — never softened
away.

### What you will do

| Job spec requirement | Demonstrated by | Status | Not covered |
|---|---|---|---|
| Own the agent-first integration architecture, reference design to production | The whole repo; `docs/architecture.md`'s four layers | Built and run in sim | Production deployment, real scale, real IFS suite (`eam/` is a mock) |
| Build the abstraction layer treating heterogeneous fleets as dispatchable, auditable executors | `router/` (`FleetAdapter` protocol, capability/availability/distance selection), `audit/` (append-only, audits before every command) | Built and run in sim | More than three ecosystems; production traffic volume |
| Deliver working integrations hands-on: dispatch, mission/task orchestration, telemetry into asset/service records | `agent/` + `mcp_server/` (dispatch, supervise), `telemetry/` (MQTT ingestion → EAM attachments) | Built and run in sim | Real OEM hardware; a real ERP/EAM/FSM system on the receiving end |
| Evaluate OEM platforms on engineering merit; kill weak options early | ADR-005 (ROS 2/Gazebo feasibility investigation, stopped short of full Nav2 on purpose, given the time budget); the three adapters' differing status labels are themselves a merit call per ecosystem | Built and run in sim | A formal multi-vendor bake-off; no real commercial/licensing evaluation |
| Represent IFS in technical engagements with OEMs, foundation model providers, standards bodies | — | No direct experience | Nothing in this repo involves an external partner organization |
| Hire and lead a robotics integration engineering team | — | No direct experience | Built solo |
| Ship demonstrable outcomes on real customer scenarios and flagship events, on hard dates | This repo itself: built and shipped end to end for this application, in commits, on a defined build sequence | Built and run in sim | No real customer scenario; the only "hard date" was self-imposed |
| Brief executives and customers on the robotics roadmap in commercial terms | The 3-minute recording script below frames this repo for a non-engineering audience | Described, not built | No commercial/roadmap framing exercised against a real stakeholder |

### Technical depth expected

| Job spec requirement | Demonstrated by | Status | Not covered |
|---|---|---|---|
| OEM platforms/SDKs: Boston Dynamics, Agility, Unitree, ANYbotics or comparable; mission APIs, fleet managers, autonomy, payload/data interfaces | `adapters/spot` (real `bosdyn-client`, `GraphNavClient`), `adapters/unitree` (real `unitree_sdk2py`, DDS RPC to a real `SportClient`) | Built against SDK, tested with fake | Agility Robotics, ANYbotics, or any OEM SDK — no direct exposure; no real hardware for Spot or Unitree; no public simulator exists for either, so "tested with fake" is the ceiling, not a shortcut (see each adapter's README) |
| Robotics middleware/interoperability: ROS 2 (topics/services/actions/DDS) at integration level; VDA 5050, MassRobotics, Open-RMF — where they work and fall short | `adapters/vda5050_amr/ros2_bridge` (real ROS 2 Jazzy node, Gazebo Harmonic, TurtleBot4); `docs/standards.md` written from that experience | Built and run in sim | Nav2 actually driving to a goal through the bridge node, not yet verified end to end (ADR-005); Open-RMF and MassRobotics are read and analyzed, not built against |
| Agent-first integration: agents that plan/dispatch/supervise; MCP servers and tool interfaces; orchestration frameworks; permissioning, human-in-the-loop escalation, audit trails | `agent/` (Pydantic AI, two-phase dispatch/supervise, resume-after-restart); `mcp_server/` (official MCP SDK, 11 tools); `identity/` (permissioning); escalation + human resume/abort proven under a real dropped MQTT link (`adapters/vda5050_amr/tests/test_degraded_mode.py`) | Built and run in sim | LangGraph specifically not used (Pydantic AI chosen instead — ADR-002); no live Anthropic API key in this environment, so the model call itself is verified structurally (real request reaches Anthropic, real 401 on a dummy key) rather than with a live response |
| Robotics foundation models: VLA/omni model awareness (e.g. SkildAI, Physical Intelligence, Nvidia GR00T) and what changes over 2-3 years | `docs/foundation-models.md` | Described, not built | No VLA/omni model integrated, prototyped, or run anywhere in this repo |
| Industrial data/telemetry: MQTT, OPC UA, event-driven ingestion, time-series at fleet scale | `telemetry/` (real MQTT ingestion, sqlite time-series store, image attachment to the EAM) | Built and run in sim | OPC UA (`DESCRIBED_NOT_BUILT`, CLAUDE.md section 4.6); fleet-scale data volume — this repo runs three robots, not a fleet |
| Simulation and validation: Isaac Sim, Gazebo, or OEM-native simulators, to validate without waiting on hardware | `adapters/vda5050_amr/ros2_bridge` (Gazebo Harmonic + TurtleBot4, headless-boot proven — ADR-005) | Built and run in sim | Isaac Sim not used (Gazebo chosen — ADR-001); `unitree_mujoco` (Unitree's own simulator, Half B) not started; full Nav2 loop not yet verified |
| Enterprise integration: REST/OData/GraphQL/webhooks into ERP/EAM/FSM; mapping missions onto work orders, assets, service processes | `eam/` (OData v4 + REST + webhook), `worldmodel/` (the actual work-order → asset → capability → robot mapping) | Built and run in sim | GraphQL not implemented (OData + REST only); a real ERP/EAM/FSM (SAP, Maximo, IFS itself) — `eam/` is a clean-room mock |
| Languages/platform: expert Python and TypeScript; read C++ where SDKs demand it; production Kubernetes, CI/CD, edge deployment | Python throughout; `console/` (TypeScript); `deploy/k3d/` (a real k3d cluster stood up and verified — five Deployments Ready, port-forwarded, smoke-tested); `.github/workflows/ci.yml` | Built and run in sim | No C++ — both SDKs used here (`unitree_sdk2py`, `bosdyn-client`) are Python-native, so no C++ reading was actually required; "production" Kubernetes means a real multi-node, production-traffic cluster, which this one-node local demo cluster is not |
| Security/safety posture: identity and authorization for machine actors; OT network segmentation; audit and traceability | `identity/` (client-credentials-shaped tokens, tested against a tampered token); `router/`'s `register_adapter` identity check; `audit/` (literally append-only); `docs/security.md` | Built and run in sim | OT network segmentation (`DESCRIBED_NOT_BUILT`, `docs/security.md`); no TLS/mTLS anywhere in this repo — everything runs on loopback or a local Docker network |

## Recording script (3 minutes)

A walkthrough script for a live or recorded demo, timed to CLAUDE.md
section 9's definition of done.

**0:00–0:20 — What this is.** "This is `robot-router`: a demo of an
agent-first integration between a business system and a heterogeneous
robot fleet. A work order gets released, an AI agent turns it into a
mission, a router picks whichever robot can do it, the robot executes
in simulation, and everything — every decision, every command — gets
audited. Built solo, on a laptop, over a few weeks. Not a product, not
run on real hardware, and I'll say so again anywhere it matters."

**0:20–1:10 — The happy path, live.** Open the console. Point at the
work order list ("this is a mock EAM — OData and REST, the same
dialect a real ERP suite exposes"). Release "Visual inspect Pump P-101
for leaks." Run the agent CLI against it. While it runs: "the agent
resolves this against a world-model graph — which robots have the
right capability, which is idle, which is closest — dispatches to the
cheapest match, and supervises it to completion." Switch to the audit
trail: "every one of those decisions is right here, append-only,
before the robot was ever called."

**1:10–2:00 — The part that actually proves something.** "Here's a
real robot adapter — VDA 5050 over MQTT, a real broker, a real ROS 2 +
Gazebo simulation underneath." (Show the sim boot, or the recorded
clip if live boot is too slow for the format.) "And here's the
degraded-mode scenario: I cut the MQTT link mid-mission —" (kill the
connection) "— the adapter detects it within its timeout, the mission
gets marked failed, the agent escalates, and it sits here waiting for
a human." Approve or abort it in the console. "That loop, cut link to
human decision, is fully tested against a real broker, not mocked."

**2:00–2:40 — What's honestly not there.** "Two of the three adapters
— Unitree and Spot — are built against the real vendor SDKs and tested
against a real fake of the onboard service, because neither vendor
ships a simulator this laptop can run their high-level API against.
Said plainly in each adapter's README, not glossed over. Same for
Nav2: it boots, it doesn't yet drive to a goal end to end. The
requirements table above has the complete, honest list — no keyword
without a receipt."

**2:40–3:00 — Close.** "The point isn't that this is production
software — it isn't. It's that every piece of it, from the MCP tool
calls to the audit log to the degraded-mode escalation, is something I
built and can defend line by line, right now, in this room."
