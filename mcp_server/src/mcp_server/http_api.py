"""A small REST API over MissionTools, for the console (CLAUDE.md
section 4.8). Separate from server.py's MCP tools -- a browser can't
speak MCP-over-stdio, and this is a different, HTTP-shaped surface for
the operator UI, not a second copy of the agent's tool surface. Wraps
the same MissionTools/Router/EAM either way.

The console reads most work order data straight from `eam`'s own REST
API (CLAUDE.md section 4.1) -- this app exists only for the pieces that
touch the router or the audit log, which `eam` knows nothing about:
live mission status, the audit trail, and escalation approve/abort.
"""

from __future__ import annotations

import os

from audit.models import AuditEvent
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from router.models import MissionStatusReport
from router.router import UnknownMissionError
from worldmodel.models import WorkOrder

from mcp_server.wiring import build_mission_tools


def create_app(
    eam_base_url: str,
    audit_db_path: str = ":memory:",
    *,
    console_origin: str | None = None,
) -> FastAPI:
    tools = build_mission_tools(eam_base_url, audit_db_path)
    origin = console_origin or os.environ.get("CONSOLE_ORIGIN", "http://localhost:5173")

    app = FastAPI(title="robot-router console API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/work-orders/{work_order_id}/mission-status")
    def get_mission_status(work_order_id: int) -> MissionStatusReport:
        mission_id = tools.router.get_mission_id_for_work_order(work_order_id)
        if mission_id is None:
            raise HTTPException(
                status_code=404, detail="no mission dispatched for this work order"
            )
        try:
            return tools.get_mission_status(mission_id)
        except UnknownMissionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/audit")
    def list_audit_events(work_order_id: int | None = None, limit: int = 200) -> list[AuditEvent]:
        if work_order_id is not None:
            return tools.list_audit_events_for_work_order(work_order_id)
        return tools.list_audit_events(limit)

    @app.post("/work-orders/{work_order_id}/approve")
    def approve_escalation(work_order_id: int) -> WorkOrder:
        return tools.approve_escalation(work_order_id)

    @app.post("/work-orders/{work_order_id}/abort")
    def abort_escalation(work_order_id: int) -> WorkOrder:
        return tools.abort_escalation(work_order_id)

    return app


if __name__ == "__main__":
    # `uv run python -m mcp_server.http_api`, not a bare module-level
    # `app = create_app(...)`: that would run at import time (including
    # a plain `import mcp_server.http_api` from a test), immediately
    # trying to reach EAM_BASE_URL before any test fixture has a real
    # EAM up yet.
    import uvicorn

    uvicorn.run(
        create_app(
            eam_base_url=os.environ.get("EAM_BASE_URL", "http://localhost:8000"),
            audit_db_path=os.environ.get("AUDIT_DB_PATH", "audit.db"),
        ),
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8001")),
    )
