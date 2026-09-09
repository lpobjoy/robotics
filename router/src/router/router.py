"""Fleet abstraction and dispatch (CLAUDE.md section 4.4).

Selection: capability match first, then availability, then a trivial
cost (shortest-path distance over worldmodel's location graph).
Deterministic and explainable -- every dispatch decision is recorded to
the audit sink with the reason, before the adapter is ever called.

Every state transition and every command to a robot goes through the
audit sink before it goes anywhere else: dispatch, pause, resume, and
abort all record an audit event first.
"""

from __future__ import annotations

import networkx as nx
from audit.models import AuditEvent
from audit.sink import AuditSink, InMemoryAuditSink
from worldmodel.query import shortest_distance

from router.models import (
    FleetAdapter,
    Mission,
    MissionHandle,
    MissionStatusReport,
    RobotAvailability,
    RobotDescriptor,
)


class NoQualifiedRobotError(RuntimeError):
    """No registered robot is capable, idle, and reachable for this mission."""


class UnknownMissionError(LookupError):
    """No dispatched mission with this id is being tracked."""


class Router:
    def __init__(self, graph: nx.DiGraph, audit_sink: AuditSink | None = None) -> None:
        self._graph = graph
        self._audit_sink: AuditSink = audit_sink if audit_sink is not None else InMemoryAuditSink()
        self._adapters_by_robot_id: dict[str, FleetAdapter] = {}
        self._handles_by_mission_id: dict[str, tuple[MissionHandle, FleetAdapter]] = {}

    def register_adapter(self, adapter: FleetAdapter) -> None:
        descriptor = adapter.capabilities()
        self._adapters_by_robot_id[descriptor.robot_id] = adapter

    def dispatch(self, mission: Mission) -> MissionHandle:
        ranked = self._rank_candidates(mission)
        if not ranked:
            self._audit_sink.record(
                AuditEvent(
                    actor="router",
                    action="mission.dispatch.no_candidate",
                    work_order_id=mission.work_order_id,
                    mission_id=mission.id,
                    detail={
                        "required_capabilities": [c.value for c in mission.required_capabilities],
                        "target_location_id": mission.primary_target_location_id,
                    },
                )
            )
            raise NoQualifiedRobotError(
                f"no idle, capable, reachable robot for mission {mission.id}"
            )

        chosen_adapter, chosen_descriptor, distance_m = ranked[0]

        self._audit_sink.record(
            AuditEvent(
                actor="router",
                action="mission.dispatch",
                work_order_id=mission.work_order_id,
                mission_id=mission.id,
                detail={
                    "robot_id": chosen_descriptor.robot_id,
                    "robot_name": chosen_descriptor.name,
                    "reason": "capability_match, idle, cheapest reachable distance",
                    "distance_m": distance_m,
                    "candidates_considered": len(ranked),
                },
            )
        )

        handle = chosen_adapter.dispatch(mission)
        self._handles_by_mission_id[mission.id] = (handle, chosen_adapter)
        return handle

    def status(self, mission_id: str) -> MissionStatusReport:
        handle, adapter = self._get(mission_id)
        return adapter.status(handle)

    def pause(self, mission_id: str) -> None:
        handle, adapter = self._get(mission_id)
        self._audit_sink.record(
            AuditEvent(actor="router", action="mission.pause", mission_id=mission_id)
        )
        adapter.pause(handle)

    def resume(self, mission_id: str) -> None:
        handle, adapter = self._get(mission_id)
        self._audit_sink.record(
            AuditEvent(actor="router", action="mission.resume", mission_id=mission_id)
        )
        adapter.resume(handle)

    def abort(self, mission_id: str) -> None:
        handle, adapter = self._get(mission_id)
        self._audit_sink.record(
            AuditEvent(actor="router", action="mission.abort", mission_id=mission_id)
        )
        adapter.abort(handle)

    def _get(self, mission_id: str) -> tuple[MissionHandle, FleetAdapter]:
        if mission_id not in self._handles_by_mission_id:
            raise UnknownMissionError(f"no dispatched mission with id {mission_id}")
        return self._handles_by_mission_id[mission_id]

    def _rank_candidates(
        self, mission: Mission
    ) -> list[tuple[FleetAdapter, RobotDescriptor, float]]:
        required = set(mission.required_capabilities)
        target = mission.primary_target_location_id

        ranked: list[tuple[FleetAdapter, RobotDescriptor, float]] = []
        for adapter in self._adapters_by_robot_id.values():
            descriptor = adapter.capabilities()
            if not required <= set(descriptor.supported_capabilities):
                continue
            if descriptor.availability != RobotAvailability.IDLE:
                continue
            distance = shortest_distance(self._graph, descriptor.location_id, target)
            if distance is None:
                continue
            ranked.append((adapter, descriptor, distance))

        ranked.sort(key=lambda candidate: candidate[2])
        return ranked
