"""An in-memory FleetAdapter for testing the router without any real
robot or simulator (CLAUDE.md section 6, step 4). Not one of the labelled
adapters/ statuses (RUN_IN_SIM etc.) -- it isn't a real adapter, it's
router's own test double, and step 5 reuses it for audit/identity
correlation testing.
"""

from __future__ import annotations

from collections.abc import Iterator

from router.models import (
    Mission,
    MissionHandle,
    MissionStatus,
    MissionStatusReport,
    MissionType,
    RobotAvailability,
    RobotDescriptor,
    TelemetryEvent,
)


class FakeAdapter:
    """Satisfies the FleetAdapter protocol structurally (no inheritance
    needed -- Protocol is structural)."""

    def __init__(
        self,
        robot_id: str,
        name: str,
        ecosystem: str,
        supported_capabilities: list[MissionType],
        location_id: int,
    ) -> None:
        self._descriptor = RobotDescriptor(
            robot_id=robot_id,
            name=name,
            ecosystem=ecosystem,
            supported_capabilities=supported_capabilities,
            availability=RobotAvailability.IDLE,
            location_id=location_id,
        )
        self._mission_status: dict[str, MissionStatus] = {}

    def capabilities(self) -> RobotDescriptor:
        return self._descriptor

    def dispatch(self, mission: Mission) -> MissionHandle:
        self._mission_status[mission.id] = MissionStatus.DISPATCHED
        self._descriptor = self._descriptor.model_copy(
            update={"availability": RobotAvailability.BUSY}
        )
        return MissionHandle(
            mission_id=mission.id,
            robot_id=self._descriptor.robot_id,
            ecosystem=self._descriptor.ecosystem,
        )

    def status(self, handle: MissionHandle) -> MissionStatusReport:
        status = self._mission_status.get(handle.mission_id)
        if status is None:
            raise KeyError(f"unknown mission handle {handle.mission_id}")
        return MissionStatusReport(mission_id=handle.mission_id, status=status)

    def pause(self, handle: MissionHandle) -> None:
        self._mission_status[handle.mission_id] = MissionStatus.PAUSED

    def resume(self, handle: MissionHandle) -> None:
        self._mission_status[handle.mission_id] = MissionStatus.IN_PROGRESS

    def abort(self, handle: MissionHandle) -> None:
        self._mission_status[handle.mission_id] = MissionStatus.ABORTED
        self._descriptor = self._descriptor.model_copy(
            update={"availability": RobotAvailability.IDLE}
        )

    def complete(self, handle: MissionHandle) -> None:
        """Test/demo helper, not part of FleetAdapter. A real adapter
        reports its own completion; this fake has to be told."""
        self._mission_status[handle.mission_id] = MissionStatus.COMPLETED
        self._descriptor = self._descriptor.model_copy(
            update={"availability": RobotAvailability.IDLE}
        )

    def telemetry_stream(self) -> Iterator[TelemetryEvent]:
        return iter(())
