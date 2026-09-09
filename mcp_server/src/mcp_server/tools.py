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
from audit.models import AuditEvent
from audit.sqlite_sink import SqliteAuditSink
from eam.models import WorkOrderStatus
from router.fake_adapter import FakeAdapter
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
        audit_sink: SqliteAuditSink,
    ) -> None:
        self._eam = eam
        self._graph_provider = graph_provider
        self._router = router
        self._audit_sink = audit_sink

    @property
    def router(self) -> Router:
        """Exposed for tests and operational introspection (e.g. reaching
        a specific FakeAdapter to force a status change) -- not an MCP
        tool itself."""
        return self._router

    @property
    def audit(self) -> SqliteAuditSink:
        """Exposed for the console's audit trail (http_api.py) -- not an
        MCP tool itself."""
        return self._audit_sink

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

    def approve_escalation(self, work_order_id: int) -> WorkOrder:
        """The console's escalation-queue "approve" button (CLAUDE.md
        section 4.8): a human decided the mission can continue. Resumes
        it via the router (if one is still tracked -- a mission that
        already failed/aborted has nothing to resume) and returns the
        work order to InProgress."""
        mission_id = self._router.get_mission_id_for_work_order(work_order_id)
        if mission_id is not None:
            self._router.resume(mission_id)
        return self._eam.set_work_order_status(work_order_id, WorkOrderStatus.IN_PROGRESS.value)

    def abort_escalation(self, work_order_id: int) -> WorkOrder:
        """The console's escalation-queue "abort" button: a human decided
        the mission should stop. Aborts it via the router and cancels the
        work order."""
        mission_id = self._router.get_mission_id_for_work_order(work_order_id)
        if mission_id is not None:
            self._router.abort(mission_id)
        return self._eam.set_work_order_status(work_order_id, WorkOrderStatus.CANCELLED.value)

    def list_audit_events(self, limit: int = 200) -> list[AuditEvent]:
        return self._audit_sink.list_events()[-limit:]

    def list_audit_events_for_work_order(self, work_order_id: int) -> list[AuditEvent]:
        return self._audit_sink.list_events_for_work_order(work_order_id)

    def advance_fake_mission(self, robot_id: str, mission_id: str, status: str) -> None:
        """Demo/test only: force a FakeAdapter-backed mission straight to
        a terminal status, standing in for what a real robot's own
        telemetry would eventually report on its own. Every robot is
        FakeAdapter-backed until step 7+ lands real adapters -- this is
        how the full dispatch-to-completion (and dispatch-to-failure)
        lifecycle is demonstrable end to end before a real robot exists.
        Raises if robot_id isn't backed by a FakeAdapter: this must never
        be reachable against a real adapter.
        """
        adapter = self._router.get_adapter(robot_id)
        if not isinstance(adapter, FakeAdapter):
            raise TypeError(
                f"advance_fake_mission only works against a FakeAdapter; "
                f"robot {robot_id!r} is not one"
            )
        handle = MissionHandle(
            mission_id=mission_id, robot_id=robot_id, ecosystem=adapter.capabilities().ecosystem
        )
        if status == "completed":
            adapter.complete(handle)
        elif status == "aborted":
            adapter.abort(handle)
        else:
            raise ValueError(f"unsupported status {status!r} -- use 'completed' or 'aborted'")
