"""adapters/spot/ (CLAUDE.md section 4.5): status
BUILT_AGAINST_SDK_TESTED_WITH_FAKE -- no public Spot simulator exists,
so unlike adapters/vda5050_amr there is no RUN_IN_SIM half to build
here at all.

SpotAdapter implements router's FleetAdapter protocol against the real
`bosdyn-client` SDK's GraphNavClient -- the same class and the same
gRPC service ("graph-nav-service") a real Spot deployment uses for
"navigate to a mapped waypoint", which is the CLAUDE.md section 4.5
capability ("GraphNav navigation to waypoint") that maps directly onto
FleetAdapter's dispatch/status contract. Tested against a real gRPC
server running `MockGraphNavServicer` (tests/fake_graph_nav_service.py),
built the same way Boston Dynamics' own `bosdyn-client` unit tests fake
GraphNav -- see their test_graph_nav_client.py upstream -- rather than
mocking the Python client objects.

Said plainly: bosdyn-client's real robot connection flow (`create_robot`,
authenticate, time-sync, lease acquisition, directory lookup) is not
exercised here -- there is no real robot or Boston Dynamics cloud to
authenticate against, and building a fake for all of that just to reach
GraphNavClient would test bosdyn-client's own plumbing, not this
adapter's logic. Bypassing straight to a channel + timesync stub is
exactly what bosdyn-client's own unit tests do for the same reason.
Two capabilities CLAUDE.md names for this adapter are consequently
*not* exercised by FleetAdapter at all: the lease-based "mission API"
(robot command execution/e-stop/lease administration) and data
acquisition for the camera payload -- neither has a FleetAdapter
protocol method to hang off of; VDA 5050's adapter has the same gap
(its own camera capture lives in ros2_bridge/, not adapter.py). Both are
real, documented `bosdyn-client` capabilities this repo could wire up
later, not ones this adapter currently calls.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from bosdyn.api.graph_nav import graph_nav_pb2
from bosdyn.client.graph_nav import GraphNavClient
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

# location id -> GraphNav waypoint id (an opaque string GraphNav assigns
# when a site is mapped) -- the equivalent of vda5050_amr's
# LocationLookup, just returning a waypoint id instead of (x, y).
WaypointLookup = Callable[[int], str]

_TERMINAL_FAILURE_STATUSES = {
    graph_nav_pb2.NavigationFeedbackResponse.STATUS_NO_ROUTE,
    graph_nav_pb2.NavigationFeedbackResponse.STATUS_NO_LOCALIZATION,
    graph_nav_pb2.NavigationFeedbackResponse.STATUS_LOST,
    graph_nav_pb2.NavigationFeedbackResponse.STATUS_STUCK,
    graph_nav_pb2.NavigationFeedbackResponse.STATUS_COMMAND_TIMED_OUT,
    graph_nav_pb2.NavigationFeedbackResponse.STATUS_ROBOT_IMPAIRED,
    graph_nav_pb2.NavigationFeedbackResponse.STATUS_CONSTRAINT_FAULT,
    graph_nav_pb2.NavigationFeedbackResponse.STATUS_COMMAND_OVERRIDDEN,
    graph_nav_pb2.NavigationFeedbackResponse.STATUS_NOT_LOCALIZED_TO_ROUTE,
    graph_nav_pb2.NavigationFeedbackResponse.STATUS_LEASE_ERROR,
    graph_nav_pb2.NavigationFeedbackResponse.STATUS_AREA_CALLBACK_ERROR,
}


class SpotAdapter:
    """One instance represents one Spot. `waypoint_lookup` resolves a
    world-model location id to a GraphNav waypoint id, same reasoning as
    the other adapters: that mapping lives in the world model, not here.
    """

    def __init__(
        self,
        robot_id: str,
        name: str,
        supported_capabilities: list[MissionType],
        home_location_id: int,
        waypoint_lookup: WaypointLookup,
        graph_nav_client: GraphNavClient,
        cmd_duration_s: float = 10.0,
    ) -> None:
        self._robot_id = robot_id
        self._name = name
        self._supported_capabilities = supported_capabilities
        self._current_location_id = home_location_id
        self._waypoint_lookup = waypoint_lookup
        self._cmd_duration_s = cmd_duration_s

        # graph_nav_client is expected to already have its .channel (and,
        # for real use, its lease/timesync endpoint) set up by the
        # caller -- the same division of labour as the other adapters'
        # already-connected transport objects.
        self._graph_nav = graph_nav_client

        self._active_handle: MissionHandle | None = None
        self._active_command_id: int | None = None
        self._active_target_location_id: int | None = None
        self._busy = False
        self._terminal_status: MissionStatus | None = None
        self._terminal_detail = ""

    # --- FleetAdapter protocol ---

    def capabilities(self) -> RobotDescriptor:
        return RobotDescriptor(
            robot_id=self._robot_id,
            name=self._name,
            ecosystem="spot",
            supported_capabilities=self._supported_capabilities,
            availability=RobotAvailability.BUSY if self._busy else RobotAvailability.IDLE,
            location_id=self._current_location_id,
        )

    def dispatch(self, mission: Mission) -> MissionHandle:
        target_location_id = mission.primary_target_location_id
        destination_waypoint_id = self._waypoint_lookup(target_location_id)

        command_id = self._graph_nav.navigate_to(destination_waypoint_id, self._cmd_duration_s)

        handle = MissionHandle(mission_id=mission.id, robot_id=self._robot_id, ecosystem="spot")
        self._active_handle = handle
        self._active_command_id = command_id
        self._active_target_location_id = target_location_id
        self._busy = True
        self._terminal_status = None
        self._terminal_detail = ""
        return handle

    def status(self, handle: MissionHandle) -> MissionStatusReport:
        if self._active_handle is None or self._active_handle.mission_id != handle.mission_id:
            return MissionStatusReport(
                mission_id=handle.mission_id, status=MissionStatus.DISPATCHED
            )

        if self._terminal_status is not None:
            return MissionStatusReport(
                mission_id=handle.mission_id,
                status=self._terminal_status,
                detail=self._terminal_detail,
            )

        feedback = self._graph_nav.navigation_feedback(self._active_command_id or 0)

        if feedback.status == graph_nav_pb2.NavigationFeedbackResponse.STATUS_REACHED_GOAL:
            assert self._active_target_location_id is not None
            self._current_location_id = self._active_target_location_id
            self._terminal_status = MissionStatus.COMPLETED
            self._busy = False
            return MissionStatusReport(mission_id=handle.mission_id, status=MissionStatus.COMPLETED)

        if feedback.status in _TERMINAL_FAILURE_STATUSES:
            self._terminal_detail = (
                f"graph nav reported status="
                f"{graph_nav_pb2.NavigationFeedbackResponse.Status.Name(feedback.status)}"
            )
            self._terminal_status = MissionStatus.FAILED
            self._busy = False
            return MissionStatusReport(
                mission_id=handle.mission_id,
                status=MissionStatus.FAILED,
                detail=self._terminal_detail,
            )

        return MissionStatusReport(mission_id=handle.mission_id, status=MissionStatus.IN_PROGRESS)

    def pause(self, handle: MissionHandle) -> None:
        # GraphNav's navigate_to has no separate "pause" RPC of its own --
        # simply not re-issuing navigate_to leaves the robot holding its
        # current command, which the real SDK's own StopMove-equivalent
        # is robot_command.RobotCommandClient.robot_command's stop(), a
        # different client this adapter doesn't hold. Left as a gap here,
        # not faked: see the README's "Not covered" section.
        pass

    def resume(self, handle: MissionHandle) -> None:
        if self._active_target_location_id is None or self._terminal_status is not None:
            return
        destination_waypoint_id = self._waypoint_lookup(self._active_target_location_id)
        self._active_command_id = self._graph_nav.navigate_to(
            destination_waypoint_id, self._cmd_duration_s
        )

    def abort(self, handle: MissionHandle) -> None:
        self._terminal_status = MissionStatus.ABORTED
        self._busy = False

    def telemetry_stream(self) -> Iterator[TelemetryEvent]:
        # Same seam as the other adapters: live telemetry ingestion is
        # step 8's job (telemetry/), not this adapter's.
        return iter(())
