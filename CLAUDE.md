# robot-router — project brief

This file is the standing instruction set for the repo. Read it fully before doing anything. It describes what we are building, why, the rules we are building under, and the order we build in.

## 1. What this is

A working demonstration of an agent-first integration between an enterprise asset management (EAM) system and heterogeneous robot fleets. A work order is released in the business system, an AI agent turns it into a physical mission, a router dispatches that mission to whichever robot can do it, the robot executes it in simulation, telemetry and inspection results flow back, and the work order is updated. Every command and decision is audited. Humans are escalated to when the agent or the robot cannot proceed safely.

It is built by one person, Lewis Pobjoy, with AI assistance, over a few weeks, on a laptop. It is a portfolio piece for a VP Robotics Engineering role whose job description (see `docs/job-spec.md`) will be tested against this repo in a technical walkthrough, a design deep dive, and a live working session. It will also serve as a public example of Lewis's hands-on engineering for consulting work.

It is NOT a product, NOT fleet-scale, NOT run on real hardware. Say so wherever it matters.

## 2. The honesty rule (non-negotiable)

Everything in this repo must be defensible line by line in a live technical session.

- Never claim in code comments, README, docstrings, or commit messages that something works on hardware, at scale, or in production. It doesn't.
- Every robot adapter carries a clear status label: `RUN_IN_SIM`, `BUILT_AGAINST_SDK_TESTED_WITH_FAKE`, or `DESCRIBED_NOT_BUILT`.
- The README contains a requirements table (see section 8) mapping each line of the job spec to what in this repo demonstrates it and what it does not cover. Gaps are stated plainly. Do not soften them.
- Do not use any code, data, ontologies, scene graphs, or architecture documents from Lewis's employer (Shell), from Kognitwin, or from any Shell Physical AI / Robot Academy work. This is a clean-room build. If something looks like it came from there, stop and ask.
- Do not fake simulation output, stub a robot and call it real, or hardcode a "successful" result. A test double is fine when labelled as a test double.
- Prefer a small thing that works over a large thing that half works.

## 3. The architecture in one paragraph

Four layers. **L1 World model**: customer business data (assets, locations, work orders, robot capabilities) turned into a graph the agent and the robots share as context. **L2 Agent and router**: an agent plans, permission-checks, dispatches and supervises missions; a router treats robots as just another class of executor, alongside human technicians and software agents. **L3 Fleet abstraction**: one mission interface, one adapter per robot ecosystem, speaking each OEM's real SDK or an open interoperability standard. **L4 Platform**: containers, Kubernetes, CI, MQTT telemetry, machine identity, audit log. L4 concerns beyond that (edge infra, neuromorphic decisions from data) are described in docs, not built.

The punchline the demo has to land: humans become schedulers and maintainers of robot fleets; robots do the work; the business system never has to know which robot did it.

## 4. Components

### 4.1 `eam/` — mock business system
- FastAPI service exposing work orders, assets, locations and attachments.
- **OData v4** endpoints for the entity set (this is the dialect of the target ERP suite), plus plain REST for convenience.
- Webhook fired when a work order moves to `Released`.
- Work order states: `Draft → Released → Dispatched → InProgress → AwaitingHuman → Completed | Failed | Cancelled`.
- Seed data: one small industrial site (a pumping station or similar), ~20 assets with coordinates, ~5 work orders, 3 robots with capability descriptors.
- Persistence: SQLite is fine.

### 4.2 `worldmodel/` — graph
- Build a graph from the EAM data: `Asset -LOCATED_AT-> Location`, `Location -REACHABLE_FROM-> Location`, `Robot -HAS_CAPABILITY-> Capability`, `WorkOrder -TARGETS-> Asset`, `WorkOrder -REQUIRES-> Capability`.
- Start with NetworkX in memory, loaded from the EAM API. Neo4j is an optional later swap; do not start there.
- One module answers the question the agent needs: "for this work order, which locations, which required capabilities, which robots qualify, what route."
- This is the productisable asset in the story. Keep it clean and well-documented.

### 4.3 `agent/` — mission agent
- **Pydantic AI** (typed tools, straightforward MCP client support). LangGraph is an acceptable swap if a strong reason emerges; note it in `docs/decisions/`.
- Model: Anthropic Claude via the provider-native SDK. Keep the model call behind one interface so it can be swapped.
- Responsibilities: read released work order → resolve against world model → produce a mission plan (typed, validated) → check permissions → dispatch via router → supervise (poll status, react to events) → on completion write results back to the EAM → on any uncertainty or safety signal escalate to a human and wait.
- Long-running: the agent must survive its own restart mid-mission. Persist mission state; resume from it.
- Tools are exposed to the agent **via an MCP server** (`mcp_server/`) that wraps the router and the EAM. The agent must not call adapters directly.

### 4.4 `router/` — fleet abstraction and dispatch
- A single `Mission` schema (Pydantic): id, work_order_id, type (`inspect_visual`, `inspect_thermal`, `patrol`), target locations, required capabilities, constraints, requested_by, approval chain.
- A `FleetAdapter` protocol: `capabilities()`, `dispatch(mission) -> handle`, `status(handle)`, `pause`, `resume`, `abort`, `telemetry_stream()`.
- Selection: capability match first, then availability, then a trivial cost (distance). Deterministic and explainable; log why a robot was chosen.
- Every state transition and every command to a robot goes through `audit/` before it goes anywhere else.

### 4.5 `adapters/` — one per ecosystem

**`adapters/vda5050_amr/` — status: `RUN_IN_SIM`**
- A ROS 2 (Humble or Jazzy, pick one and pin it) mobile robot in **Gazebo** using **Nav2**. TurtleBot 3 sim is fine to start. Isaac Sim is an optional later swap for visuals; Gazebo first because it is lighter and can run headless in CI.
- A VDA 5050 bridge node: subscribes to `order` and `instantActions` on MQTT, drives Nav2 actions, publishes `state`, `visualization`, `connection` topics per the spec.
- The adapter speaks **only VDA 5050 over MQTT** to the robot. It must not reach into ROS directly. That separation is the point.
- Camera "inspection" = grab an image from the simulated camera at the target pose and attach it to the mission result.

**`adapters/unitree/` — status: split, label each half**
- Half A (`BUILT_AGAINST_SDK_TESTED_WITH_FAKE`): adapter written against `unitree_sdk2_python`'s high-level API (`SportClient` and its DDS topics), which is what a real Go2 deployment would call. Tested against a fake of the onboard sport service. The high-level service does not run in Unitree's simulator; state this in the module docstring and the README.
- Half B (`RUN_IN_SIM`): Go2 in `unitree_mujoco` walking under Unitree's published locomotion policy from `unitree_rl_gym` (sim2sim MuJoCo deployment). The adapter sends velocity/goal commands on the same low-level DDS topics and reads `SportModeState` back. Prove a mission can be visibly executed.
- Keep this adapter in **its own container**. `unitree_sdk2py` pins CycloneDDS 0.10.2 and clashes with ROS 2's build; never install both in one image.

**`adapters/spot/` — status: `BUILT_AGAINST_SDK_TESTED_WITH_FAKE`**
- Adapter against `bosdyn-client` (public on PyPI): mission API, GraphNav navigation to waypoint, data acquisition for the camera payload. No public simulator exists; test against a fake. Label it.

### 4.6 `telemetry/`
- MQTT broker (Mosquitto) in compose.
- Robot state, position, battery, and inspection images published on a stable topic scheme (`fleet/<robot_id>/state`, `.../images`, `.../events`).
- Ingestion service writes state to a time-series store (TimescaleDB or just SQLite with a time index for now — do not over-build) and attaches images to the work order in the EAM.
- OPC UA is `DESCRIBED_NOT_BUILT`. One paragraph in docs on where it would sit.

### 4.7 `audit/` and `identity/`
- Append-only audit log: who/what requested, what was decided, what was sent to which robot, what came back, timestamps, correlation to work order and mission. Every row has an actor identity.
- Machine identity: each adapter authenticates to the router and the EAM as its own OIDC client (client-credentials) or mTLS cert. Use a local Keycloak or a minimal token issuer; do not build auth from scratch.
- Human-in-the-loop: `AwaitingHuman` is a real state; the mission does not proceed until a human acts in the console. Escalation triggers: low agent confidence, capability mismatch discovered mid-mission, connectivity loss beyond a threshold, any adapter error flagged as safety-relevant.
- Network segmentation for OT is `DESCRIBED_NOT_BUILT` in `docs/security.md`.

### 4.8 `console/` — operator UI
- Small **TypeScript** app (Vite + React). Shows work orders, live mission status, telemetry, the audit trail, and the escalation queue with approve/abort buttons. Deliberately thin. This is the second language on the spec; it is not the product.

### 4.9 `deploy/`
- `docker-compose.yml` for local dev (everything runnable with one command).
- Kubernetes manifests (kustomize) for **k3d**. Separate images per component. Unitree and ROS 2 adapters never share an image.
- `docs/edge-deployment.md`: how the adapter and MQTT pieces would sit on-site with intermittent connectivity, store-and-forward, and what happens when the link to the cloud drops.

### 4.10 `docs/`
- `job-spec.md` — the JD, verbatim.
- `architecture.md` — the four layers, with a diagram (Mermaid).
- `decisions/` — short ADRs for every non-obvious choice.
- `security.md`, `edge-deployment.md`, `foundation-models.md` (what VLA/omni models change about the integration surface over 2–3 years — written, not built), `standards.md` (VDA 5050 vs Open-RMF vs MassRobotics: where each works, where it falls short, from actually using one of them).

## 5. Tech stack (pinned)

- Python 3.11, `uv` for envs, `ruff`, `pytest`, `mypy --strict` on `router/`, `agent/`, `worldmodel/`.
- FastAPI, Pydantic v2, Pydantic AI, paho-mqtt, NetworkX, httpx.
- ROS 2 (pick Humble or Jazzy in the first ADR), Nav2, Gazebo, `rclpy`.
- `unitree_sdk2_python`, `unitree_mujoco`, `unitree_rl_gym`, MuJoCo.
- `bosdyn-client`.
- TypeScript, Vite, React for the console.
- Docker, docker-compose, k3d, kustomize.
- GitHub Actions: lint, type-check, unit tests, and a headless Gazebo integration test of one full work order on every push to `main`.

## 6. Build sequence

Work strictly in this order. Each step ends with something that runs, a test, and a commit. Do not start step N+1 until step N is green.

1. **Repo skeleton** — layout above, `uv` workspace, compose with Mosquitto, CI running lint + empty tests. ADR-001: ROS 2 distro. ADR-002: agent framework.
2. **EAM mock** — OData + REST, seed data, webhook. Tests.
3. **World model** — graph from EAM, the "qualify robots for this work order" query. Tests with the seed data.
4. **Router core** — `Mission`, `FleetAdapter` protocol, selection, audit hooks, an in-memory `FakeAdapter`. Tests: a released work order becomes a dispatched mission on the fake.
5. **Audit + identity** — append-only log, machine identity on the fake adapter, correlation ids end to end.
6. **MCP server + agent** — tools over router and EAM; agent takes a released work order to `Completed` on the fake adapter. Escalation path tested with a forced failure.
7. **VDA 5050 AMR adapter** — Gazebo + Nav2 + bridge node. First real robot in sim completes a work order. Camera image attached. Headless CI test.
8. **Telemetry** — MQTT ingestion, time-series, images to EAM.
9. **Console** — TypeScript UI over the APIs. Escalation approve/abort works.
10. **Degraded mode** — cut MQTT mid-mission; mission pauses; agent escalates; human resumes or aborts; audit shows it all.
11. **Unitree adapter** — Half A against the SDK with a fake; Half B in unitree_mujoco with the published policy. Own container.
12. **Spot adapter** — against `bosdyn-client` with a fake.
13. **k3d deployment** — everything on a local cluster.
14. **Docs** — architecture, ADRs, security, edge, standards, foundation models.
15. **README requirements table** and a 3-minute recording script.

## 7. Working conventions for Claude Code

- Small commits with plain-English messages describing what changed and why. Never squash away a wrong turn; it is evidence of real work.
- Ask before adding a dependency not in section 5.
- Ask before expanding scope. If a feature is not in section 4, it is out.
- Do not write dashboards, admin panels, or charts beyond what section 4.8 states.
- Plain English in all docs and comments. No marketing language. No "seamless", "robust", "cutting-edge", "leverage".
- When something cannot be made to work in sim (e.g. an OEM service only exists on hardware), do not work around it by faking success. Document the seam and label the adapter status accordingly.
- Tests are not optional. An adapter without a test against its fake is not done.
- Keep every service runnable on its own with `uv run` and inside compose.

## 8. README requirements table — required format

| Job spec requirement | Demonstrated by | Status | Not covered |
|---|---|---|---|

Statuses: `Built and run in sim`, `Built against SDK, tested with fake`, `Described, not built`, `No direct experience`. Every line of the "What you will do" and "Technical depth expected" sections of `docs/job-spec.md` gets a row. Rows marked `No direct experience` are written as plainly as the others.

## 9. Definition of done

A person with Docker and a GPU-less laptop can clone the repo, run one command, open the console, release a work order, watch the Gazebo AMR complete it, see the image attached to the work order, read the audit trail, and reproduce the degraded-mode escalation. The Unitree and Spot adapters pass their tests. CI is green. The README table is complete and true.
