# mcp_server

MCP server wrapping the router and EAM as typed tools for the agent. See
CLAUDE.md section 4.3: "The agent must not call adapters directly" --
these tools are the only surface the agent gets; nothing here reaches
into `adapters/`.

Built at build-sequence step 6.

## What's here

- `tools.py` -- `MissionTools`: the actual tool implementations, kept as
  plain, directly-testable methods. Wraps an `EamGateway` (status
  mutations), a `graph_provider` callable (worldmodel, rebuilt fresh on
  every call so newly-released work orders are visible), and a `Router`.
- `eam_gateway.py` -- a small `httpx`-based client for the EAM mutations
  a mission's lifecycle needs (list/get work orders, PATCH status).
  Separate from `worldmodel.client.EamClient`, which is read-only.
- `wiring.py` -- `build_mission_tools(eam_base_url)`: wires a real
  `EamGateway` + world-model graph + `Router` together. No real adapters
  exist yet (`adapters/` starts at step 7) -- this registers a
  `FakeAdapter` per robot in the EAM's seed data, so the whole pipeline
  is exercisable end to end before a real robot exists.
- `server.py` / `__main__.py` -- the actual MCP server, built on the
  official MCP Python SDK (`mcp.server.mcpserver.MCPServer`), exposing
  `MissionTools`' methods as MCP tools over stdio. Reads `EAM_BASE_URL`
  from the environment.

Eleven tools: `list_released_work_orders`, `get_work_order`,
`qualify_robots`, `dispatch_mission`, `get_mission_status`,
`mark_in_progress`, `mark_completed`, `mark_failed`,
`escalate_to_human`, `abort_mission`, and `advance_fake_mission`
(demo/test only -- forces a FakeAdapter-backed mission to a terminal
status, standing in for what a real robot's own telemetry would
eventually report; raises against anything not FakeAdapter-backed).

## Not covered

- Only a stdio transport. HTTP/SSE (needed for a genuinely multi-process
  deployment, e.g. k3d in step 13) is a documented later swap, not built.
- No auth on the MCP layer itself -- machine identity (step 5) currently
  applies to adapter-to-router registration, not to the agent-to-MCP-server
  hop.

## Running it

Standalone (needs a running `eam`):

```bash
EAM_BASE_URL=http://localhost:8000 uv run python -m mcp_server
```

Tests:

```bash
uv run pytest mcp_server
```

`test_tools.py` exercises `MissionTools` directly (fast, in-process,
against `eam`'s real seed data) -- including both of CLAUDE.md section 6
step 6's acceptance scenarios: a released work order reaching Completed,
and the escalation path on a forced failure. `test_server_stdio.py` is a
separate, slower smoke test proving the server genuinely speaks MCP: it
spawns the real module as a subprocess over real stdio, against a real
(background-thread) `eam` instance, and checks the tool list over an
actual JSON-RPC round trip.
