"""The MCP server process. Run via stdio: `uv run python -m mcp_server`
(this is exactly what the agent's MCP client spawns). Wraps MissionTools
as MCP tools using the official MCP Python SDK.

Reads EAM_BASE_URL from the environment (default http://localhost:8000)
-- the EAM must already be running.
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer
from router.models import MissionType

from mcp_server.wiring import build_mission_tools

EAM_BASE_URL = os.environ.get("EAM_BASE_URL", "http://localhost:8000")

_tools = build_mission_tools(EAM_BASE_URL)

server = MCPServer(name="robot-router-mcp")


@server.tool()
def list_released_work_orders() -> list[dict[str, object]]:
    """List work orders currently in the Released state, ready to be planned and dispatched."""
    return [wo.model_dump(mode="json") for wo in _tools.list_released_work_orders()]


@server.tool()
def get_work_order(work_order_id: int) -> dict[str, object]:
    """Get one work order by id."""
    return _tools.get_work_order(work_order_id).model_dump(mode="json")


@server.tool()
def qualify_robots(work_order_id: int) -> dict[str, object]:
    """Given a work order, return which robots qualify (capability match
    and a reachable route) and their route distance, cheapest first."""
    result = _tools.qualify_robots(work_order_id)
    return {
        "work_order_id": result.work_order_id,
        "target_location_id": result.target_location_id,
        "required_capabilities": [c.value for c in result.required_capabilities],
        "qualified_robots": [
            {
                "robot_id": r.robot_id,
                "robot_name": r.robot_name,
                "route": list(r.route),
                "route_distance_m": r.route_distance_m,
            }
            for r in result.qualified_robots
        ],
    }


@server.tool()
def dispatch_mission(
    work_order_id: int,
    target_location_id: int,
    required_capabilities: list[str],
    requested_by: str,
) -> dict[str, object]:
    """Dispatch a mission for a released work order to the best
    qualified, idle, reachable robot. Transitions the work order to
    Dispatched. required_capabilities values must be one of
    inspect_visual, inspect_thermal, patrol."""
    handle = _tools.dispatch_mission(
        work_order_id,
        target_location_id,
        [MissionType(c) for c in required_capabilities],
        requested_by,
    )
    return handle.model_dump(mode="json")


@server.tool()
def get_mission_status(mission_id: str) -> dict[str, object]:
    """Poll a dispatched mission's current status. Keep polling until the
    status is a terminal one (completed, failed, aborted) before deciding
    what to do next."""
    return _tools.get_mission_status(mission_id).model_dump(mode="json")


@server.tool()
def mark_in_progress(work_order_id: int) -> dict[str, object]:
    """Mark a just-dispatched work order as InProgress."""
    return _tools.mark_in_progress(work_order_id).model_dump(mode="json")


@server.tool()
def mark_completed(work_order_id: int) -> dict[str, object]:
    """Mark a work order Completed once its mission has finished successfully."""
    return _tools.mark_completed(work_order_id).model_dump(mode="json")


@server.tool()
def mark_failed(work_order_id: int) -> dict[str, object]:
    """Mark a work order Failed. Prefer escalate_to_human for anything
    that needs a person to look at it -- this is for a clean, unambiguous
    failure only."""
    return _tools.mark_failed(work_order_id).model_dump(mode="json")


@server.tool()
def escalate_to_human(work_order_id: int, reason: str) -> dict[str, object]:
    """Escalate a work order to a human: transitions it to AwaitingHuman
    and stops -- it will not proceed until a human acts. Use this on any
    uncertainty or safety-relevant signal: a capability mismatch
    discovered mid-mission, a mission failure, connectivity loss, or
    anything you are not confident about."""
    return _tools.escalate_to_human(work_order_id, reason).model_dump(mode="json")


@server.tool()
def abort_mission(mission_id: str) -> None:
    """Abort a dispatched mission."""
    _tools.abort_mission(mission_id)


if __name__ == "__main__":
    server.run(transport="stdio")
