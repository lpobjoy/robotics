"""The actual tool implementations, kept as plain, directly-testable
methods -- the MCP transport wrapper lives in server.py. CLAUDE.md
section 4.3: "Tools are exposed to the agent via an MCP server that
wraps the router and the EAM. The agent must not call adapters
directly." These tools are the only surface the agent gets; nothing here
reaches into adapters/.
"""

from __future__ import annotations

from collections.abc import Callable

import networkx as nx
from eam.models import WorkOrderStatus
from router.models import Mission, MissionHandle, MissionStatusReport, MissionType
from router.router import Router
from worldmodel.models import WorkOrder
from worldmodel.query import WorkOrderQualification, qualify_robots_for_work_order

from mcp_server.eam_gateway import EamGateway


class MissionTools:
    """graph_provider is a callable, not a fixed graph, because the
    world model can (and, once step 8's telemetry lands, will) change
    between calls -- robot status and asset data aren't static."""

    def __init__(
        self,
        eam: EamGateway,
        graph_provider: Callable[[], nx.DiGraph],
        router: Router,
    ) -> None:
        self._eam = eam
        self._graph_provider = graph_provider
        self._router = router

    @property
    def router(self) -> Router:
        """Exposed for tests and operational introspection (e.g. reaching
        a specific FakeAdapter to force a status change) -- not an MCP
        tool itself."""
        return self._router

    def list_released_work_orders(self) -> list[WorkOrder]:
        return self._eam.list_work_orders(status=WorkOrderStatus.RELEASED.value)

    def get_work_order(self, work_order_id: int) -> WorkOrder:
        return self._eam.get_work_order(work_order_id)

    def qualify_robots(self, work_order_id: int) -> WorkOrderQualification:
        return qualify_robots_for_work_order(self._graph_provider(), work_order_id)

    def dispatch_mission(
        self,
        work_order_id: int,
        target_location_id: int,
        required_capabilities: list[MissionType],
        requested_by: str,
    ) -> MissionHandle:
        mission = Mission(
            work_order_id=work_order_id,
            type=required_capabilities[0],
            target_locations=[target_location_id],
            required_capabilities=required_capabilities,
            requested_by=requested_by,
        )
        handle = self._router.dispatch(mission)
        self._eam.set_work_order_status(work_order_id, WorkOrderStatus.DISPATCHED.value)
        return handle

    def get_mission_status(self, mission_id: str) -> MissionStatusReport:
        return self._router.status(mission_id)

    def mark_in_progress(self, work_order_id: int) -> WorkOrder:
        return self._eam.set_work_order_status(work_order_id, WorkOrderStatus.IN_PROGRESS.value)

    def mark_completed(self, work_order_id: int) -> WorkOrder:
        return self._eam.set_work_order_status(work_order_id, WorkOrderStatus.COMPLETED.value)

    def mark_failed(self, work_order_id: int) -> WorkOrder:
        return self._eam.set_work_order_status(work_order_id, WorkOrderStatus.FAILED.value)

    def escalate_to_human(self, work_order_id: int, reason: str) -> WorkOrder:
        """CLAUDE.md section 4.7: AwaitingHuman is a real state; the
        mission does not proceed until a human acts. reason is carried
        only in the tool's return value here -- audit.AuditEvent (via
        router) is where a durable record belongs; the EAM's work order
        row has no free-text field for it, and adding one is out of the
        section 4.1 scope already built.
        """
        return self._eam.set_work_order_status(work_order_id, WorkOrderStatus.AWAITING_HUMAN.value)

    def abort_mission(self, mission_id: str) -> None:
        self._router.abort(mission_id)
