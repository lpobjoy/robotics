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

Step 1 of 15 (repo skeleton) — see CLAUDE.md section 6. Nothing here runs
end to end yet. Each component directory has its own `README.md` stating
what it will do and which step builds it.

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
- `deploy/` — docker-compose and (later) k3d manifests
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

Right now that starts only the Mosquitto broker — components are added to
compose as each build-sequence step lands them.

## Requirements table

Not started yet. This section will map every line of the target job spec
(`docs/job-spec.md`, not yet added) to what this repo demonstrates, in the
format fixed in CLAUDE.md section 8. Due at build-sequence step 15.
