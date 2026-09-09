# agent

Pydantic AI mission agent: reads released work orders, plans missions,
dispatches via the router, supervises execution, and escalates to a
human on uncertainty. See CLAUDE.md section 4.3.

Built at build-sequence step 6.

## What's here

- `mission_agent.py` -- `MissionAgent`, and the two Pydantic AI agents it
  wraps:
  - **dispatch**: qualify robots for a released work order, dispatch the
    mission to the cheapest qualified one (or escalate if none qualify),
    mark the work order InProgress.
  - **supervise**: poll the mission until a terminal status, then mark
    the work order Completed, or escalate on failure/abort.

  Both agents share one MCP toolset (`mcp_toolset()`) -- one
  `python -m mcp_server` subprocess, kept alive across calls. This
  matters: without a shared, kept-alive subprocess, each agent.run()
  call would get its own fresh in-memory router, and the supervise step
  couldn't see a mission the dispatch step had just created. Verified
  empirically before relying on it (see the function's docstring).
- `state.py` -- `MissionStateStore`: plain-sqlite3 persistence of which
  work order is at which phase, with what mission_id, so a restarted
  agent resumes instead of re-dispatching. See its module docstring for
  exactly what this does and doesn't cover -- durable *agent* state, not
  durable *router* state (that needs mcp_server to run as its own
  long-lived process, not built yet).
- `model_config.py` -- keeps the model call behind one interface
  (CLAUDE.md section 4.3): `AGENT_MODEL` env var, defaulting to
  `anthropic:claude-sonnet-4-5`. Swapping providers means changing the
  string, not code.

The agent never imports `router`, `worldmodel`, or `eam` directly, and
never touches `adapters/` -- everything goes through the ten (well,
eleven -- one is demo/test-only) MCP tools in `mcp_server/`.

## Not covered

- Needs `ANTHROPIC_API_KEY` to actually call Claude. Without one, only
  the test suite runs (Pydantic AI's own `FunctionModel` test double
  stands in for the LLM -- see `tests/scripted_model.py`).
- Full process-crash survival needs `mcp_server` running as its own
  long-lived service that the agent reconnects to, not spawned fresh per
  agent run. Described in `state.py`'s docstring, not built -- real
  adapters and that deployment shape start at step 7+.
- No permission/approval-chain enforcement yet -- `Mission.approval_chain`
  exists on the schema (router, step 4) but nothing checks it before
  dispatch.

## Running it

Needs `ANTHROPIC_API_KEY` and a running `eam`:

```bash
ANTHROPIC_API_KEY=... EAM_BASE_URL=http://localhost:8000 uv run python -c "
import asyncio
from agent.mission_agent import build_mission_agent
from agent.state import MissionStateStore

async def main():
    agent = build_mission_agent(MissionStateStore('agent_state.db'))
    print(await agent.process_released_work_order(1))

asyncio.run(main())
"
```

Tests (no API key needed):

```bash
uv run pytest agent
```

`test_mission_agent.py` covers CLAUDE.md section 6 step 6's two
acceptance scenarios (dispatch to Completed; escalation on a forced
failure) plus the resume-after-restart mechanism, all against the real
MCP server (subprocess, real stdio), real router, real fake adapter, and
a real (background-thread) EAM -- only the model is scripted.
