"""The MCP server process. Run via stdio: `uv run python -m mcp_server`
(this is exactly what the agent's MCP client spawns). Wraps MissionTools
as MCP tools using the official MCP Python SDK.

Reads EAM_BASE_URL and AUDIT_DB_PATH from the environment (defaults
http://localhost:8000 and ":memory:" -- the EAM must already be
running).

Said plainly: this process's Router (mission dispatch state, registered
FakeAdapters) is entirely separate, in-memory, and process-local -- it
is NOT the same Router instance http_api.py's mcp_server serves to the
console. In deploy/docker-compose.yml, the agent spawns this as its own
subprocess per invocation while the console talks to a long-running
http_api.py process; a mission the agent dispatches through this
process will not appear as in-progress in the console's live mission
status view, because that view is reading a different Router.
Pointing both at the same AUDIT_DB_PATH (deploy/docker-compose.yml does
this) keeps the audit trail itself consistent between them, which is
the one piece of state SqliteAuditSink actually persists to a shared
file; mission status is not something either process persists.
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer
from router.models import MissionType

from mcp_server.wiring import build_mission_tools

EAM_BASE_URL = os.environ.get("EAM_BASE_URL", "http://localhost:8000")
AUDIT_DB_PATH = os.environ.get("AUDIT_DB_PATH", ":memory:")

_tools = build_mission_tools(EAM_BASE_URL, AUDIT_DB_PATH)

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


@server.tool()
def advance_fake_mission(robot_id: str, mission_id: str, status: str) -> None:
    """Demo/test only: force a mission straight to a terminal status
    (completed or aborted). Only works while the robot is backed by a
    FakeAdapter (true for every robot until a real adapter is registered
    for it) -- raises otherwise. A real robot reports its own status
    through get_mission_status; this exists only because a fake one
    can't."""
    _tools.advance_fake_mission(robot_id, mission_id, status)


if __name__ == "__main__":
    server.run(transport="stdio")
