"""The mission agent (CLAUDE.md section 4.3): reads a released work
order, resolves it against the world model, produces a mission plan,
dispatches via the router, supervises execution, writes results back to
the EAM on completion, and escalates to a human on any uncertainty or
safety signal.

All of this happens through MCP tools (mcp_server/) -- this module never
imports router, worldmodel, or eam directly, and never touches
adapters/.

Two agent.run() calls per work order, not one:
  1. "dispatch": qualify robots, dispatch the mission (or escalate if
     none qualify), mark the work order InProgress.
  2. "supervise": poll the mission until a terminal status, then mark
     the work order Completed, or escalate on failure/abort.
Splitting them gives a real, testable resume point: if the process
restarts between the two calls, MissionState already has the dispatched
mission_id, so processing resumes at "supervise" instead of dispatching
a second, duplicate mission. See state.py's module docstring for what
this resume mechanism does and doesn't cover.
"""

from __future__ import annotations

import os
import sys

from pydantic_ai import Agent

# FastMCPClient/StdioTransport are pydantic_ai's intended MCP client
# integration point but aren't in pydantic_ai.mcp's __all__ (they're
# re-exported from the third-party `fastmcp` package). Importing them
# through fastmcp's own internal modules directly would be even less
# stable across versions than this.
from pydantic_ai.mcp import FastMCPClient, MCPToolset, StdioTransport  # type: ignore[attr-defined]
from pydantic_ai.models import Model

from agent.model_config import configured_model_name
from agent.state import MissionPhase, MissionState, MissionStateStore, now

DISPATCH_SYSTEM_PROMPT = """
You are the dispatch step of a mission agent for a robot fleet
integration demo. You are given one released work order id. Using only
the tools available to you:

1. Call qualify_robots for the work order.
2. If qualified_robots is empty, call escalate_to_human with a clear
   reason, then reply with exactly: ESCALATED <reason>
3. Otherwise, call dispatch_mission for the cheapest (first) qualified
   robot, using the work order's target_location_id and
   required_capabilities from the qualify_robots result, and
   requested_by="mission-agent".
4. Call mark_in_progress for the work order.
5. Reply with exactly: DISPATCHED <mission_id>

Do not call any other tools. Do not explain yourself further than the
one final line above.
"""

SUPERVISE_SYSTEM_PROMPT = """
You are the supervision step of a mission agent for a robot fleet
integration demo. You are given a work order id and a mission id that
has already been dispatched. Using only the tools available to you:

1. Call get_mission_status for the mission id.
2. If the status is not a terminal one (completed, failed, aborted),
   call get_mission_status again. Keep polling until you see a terminal
   status.
3. If the terminal status is completed, call mark_completed for the
   work order, then reply with exactly: COMPLETED
4. If the terminal status is failed or aborted, call escalate_to_human
   for the work order with a reason describing what happened, then
   reply with exactly: ESCALATED <reason>. Never call mark_completed
   for a failed or aborted mission.

Do not call any other tools. Do not explain yourself further than the
one final line above.
"""


def mcp_toolset(eam_base_url: str | None = None) -> MCPToolset:
    """One toolset, one subprocess, shared by both agents below.

    keep_alive matters here (True is pydantic_ai's own default, made
    explicit): without it, each agent.run() call would spawn -- and tear
    down -- its own fresh `python -m mcp_server` process, each with its
    own fresh in-memory Router, and the supervise agent's
    get_mission_status call would find no record of a mission the
    dispatch agent had just created in a different process. Verified
    empirically before relying on it: two separate Agent instances
    sharing one keep_alive toolset do see the same router state across
    separate .run() calls.

    eam_base_url overrides EAM_BASE_URL for the spawned subprocess
    (tests point this at a real, per-test EAM instance rather than
    relying on inherited environment).
    """
    env = dict(os.environ)
    if eam_base_url is not None:
        env["EAM_BASE_URL"] = eam_base_url
    transport = StdioTransport(
        command=sys.executable, args=["-m", "mcp_server"], env=env, keep_alive=True
    )
    return MCPToolset(FastMCPClient(transport=transport))


def build_dispatch_agent(toolset: MCPToolset, model: str | Model | None = None) -> Agent:
    return Agent(
        model or configured_model_name(), toolsets=[toolset], system_prompt=DISPATCH_SYSTEM_PROMPT
    )


def build_supervise_agent(toolset: MCPToolset, model: str | Model | None = None) -> Agent:
    return Agent(
        model or configured_model_name(),
        toolsets=[toolset],
        system_prompt=SUPERVISE_SYSTEM_PROMPT,
    )


class EscalatedError(RuntimeError):
    """Raised (not swallowed) so callers know a work order is now sitting
    in AwaitingHuman, not silently dropped. CLAUDE.md section 4.7:
    AwaitingHuman is a real state; the mission does not proceed until a
    human acts."""


class MissionAgent:
    def __init__(
        self, dispatch_agent: Agent, supervise_agent: Agent, state_store: MissionStateStore
    ) -> None:
        self._dispatch_agent = dispatch_agent
        self._supervise_agent = supervise_agent
        self._state_store = state_store

    async def process_released_work_order(self, work_order_id: int) -> str:
        state = self._state_store.get(work_order_id)

        if state is not None and state.phase == MissionPhase.DONE:
            return f"work order {work_order_id} already processed"

        if state is None or state.mission_id is None:
            mission_id = await self._run_dispatch(work_order_id)
        else:
            mission_id = state.mission_id

        return await self._run_supervise(work_order_id, mission_id)

    async def _run_dispatch(self, work_order_id: int) -> str:
        result = await self._dispatch_agent.run(f"Process released work order {work_order_id}.")
        outcome = str(result.output)

        if outcome.startswith("ESCALATED"):
            self._state_store.save(
                MissionState(
                    work_order_id=work_order_id,
                    mission_id=None,
                    phase=MissionPhase.AWAITING_HUMAN,
                    updated_at=now(),
                )
            )
            raise EscalatedError(outcome)

        mission_id = outcome.removeprefix("DISPATCHED").strip()
        self._state_store.save(
            MissionState(
                work_order_id=work_order_id,
                mission_id=mission_id,
                phase=MissionPhase.DISPATCHED,
                updated_at=now(),
            )
        )
        return mission_id

    async def _run_supervise(self, work_order_id: int, mission_id: str) -> str:
        result = await self._supervise_agent.run(
            f"Supervise mission {mission_id} for work order {work_order_id}."
        )
        outcome = str(result.output)

        if outcome.startswith("ESCALATED"):
            self._state_store.save(
                MissionState(
                    work_order_id=work_order_id,
                    mission_id=mission_id,
                    phase=MissionPhase.AWAITING_HUMAN,
                    updated_at=now(),
                )
            )
            raise EscalatedError(outcome)

        self._state_store.save(
            MissionState(
                work_order_id=work_order_id,
                mission_id=mission_id,
                phase=MissionPhase.DONE,
                updated_at=now(),
            )
        )
        return outcome


def build_mission_agent(
    state_store: MissionStateStore,
    model: str | Model | None = None,
    *,
    eam_base_url: str | None = None,
) -> MissionAgent:
    toolset = mcp_toolset(eam_base_url)
    return MissionAgent(
        dispatch_agent=build_dispatch_agent(toolset, model),
        supervise_agent=build_supervise_agent(toolset, model),
        state_store=state_store,
    )
