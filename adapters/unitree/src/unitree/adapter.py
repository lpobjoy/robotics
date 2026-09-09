"""Half A of adapters/unitree/ (CLAUDE.md section 4.5): status
BUILT_AGAINST_SDK_TESTED_WITH_FAKE.

UnitreeAdapter implements router's FleetAdapter protocol against
unitree_sdk2py's real high-level API: the same SportClient class, the
same DDS RPC service ("sport"), and the same SportModeState telemetry a
real Go2 deployment would use. There is no vendor simulator this half
runs against -- Unitree's own simulator (unitree_mujoco, Half B) only
speaks the *low-level* joint/DDS interface, not this high-level sport
service -- so this is tested against a fake of the onboard sport
service instead (tests/fake_sport_service.py), a real DDS RPC responder
standing in for the robot the same way vda5050_amr's FakeRobot stands in
for a real bridge over real MQTT.

Said plainly, per CLAUDE.md's honesty rule: the high-level SportClient
API is velocity/gait control (Move(vx, vy, vyaw), StandUp, StopMove,
...), not "navigate to this waypoint" -- there is no path planner or
localization behind it in this SDK. What's proven here is genuine DDS
RPC protocol correctness (the adapter issues real requests a real robot
would receive and act on) and status reporting driven by genuine
SportModeState telemetry fields (position, error_code) -- not real
autonomous navigation to a location. A real deployment would need this
adapter to sit behind an actual navigation stack issuing the Move()
calls; that isn't built or claimed here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

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
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.go2.sport.sport_client import SportClient
from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_

LocationLookup = Callable[[int], tuple[float, float]]

# The documented Go2 high-level state topic. Both sides of every test
# agree on this string (adapter and fake service alike), so an exact
# real-robot match matters less than internal consistency -- but this is
# the name Unitree's own examples use for it, kept the same on purpose.
SPORT_STATE_TOPIC = "rt/sportmodestate"


class UnitreeAdapter:
    """One instance represents one Go2. `location_lookup` resolves a
    location id to (x, y), same reasoning as vda5050_amr's adapter: the
    coordinates live in the world model, not here.
    """

    def __init__(
        self,
        robot_id: str,
        name: str,
        supported_capabilities: list[MissionType],
        home_location_id: int,
        location_lookup: LocationLookup,
        sport_client: SportClient,
        arrival_tolerance_m: float = 0.5,
    ) -> None:
        self._robot_id = robot_id
        self._name = name
        self._supported_capabilities = supported_capabilities
        self._current_location_id = home_location_id
        self._location_lookup = location_lookup
        self._arrival_tolerance_m = arrival_tolerance_m

        # sport_client is expected to already be constructed and Init()'d
        # by the caller (its own timeout, its own API registration) --
        # the same division of labour as vda5050_amr's adapter, which
        # takes an already-connected mqtt.Client rather than connecting
        # one itself.
        self._sport = sport_client

        self._latest_state: SportModeState_ | None = None
        self._state_subscriber = ChannelSubscriber(SPORT_STATE_TOPIC, SportModeState_)
        self._state_subscriber.Init(handler=self._on_state)

        # No FleetAdapter concept of "which mission is active" exists on
        # the wire -- the sport service just executes velocity commands,
        # it doesn't track a mission id. Tracked locally so status() and
        # capabilities() know what's in flight, the same role
        # vda5050_amr's adapter gets for free from the order_id on
        # incoming `state` messages. _active_handle/_active_target_location_id
        # are kept even after a mission reaches a terminal status, so a
        # repeat status() call for the same handle keeps answering the
        # same terminal status instead of falling back to DISPATCHED;
        # _terminal_status/_terminal_detail cache exactly what that
        # answer is, and _busy is the separate flag that actually drives
        # availability -- it *does* clear once a mission goes terminal,
        # otherwise this robot would look BUSY forever and the router
        # would never dispatch to it again.
        self._active_handle: MissionHandle | None = None
        self._active_target_location_id: int | None = None
        self._busy = False
        self._terminal_status: MissionStatus | None = None
        self._terminal_detail = ""
        # SportModeState also carries no order/mission id to compare
        # against (unlike VDA 5050's state.order_id), so there's no way
        # to tell a telemetry sample from *before* dispatch apart from
        # one from *after* by content alone. Counted instead: status()
        # only trusts position/error_code once at least one sample has
        # arrived since the mission was dispatched.
        self._state_count = 0
        self._dispatch_state_count: int | None = None

    def _on_state(self, state: SportModeState_) -> None:
        self._latest_state = state
        self._state_count += 1

    # --- FleetAdapter protocol ---

    def capabilities(self) -> RobotDescriptor:
        return RobotDescriptor(
            robot_id=self._robot_id,
            name=self._name,
            ecosystem="unitree",
            supported_capabilities=self._supported_capabilities,
            availability=self._availability(),
            location_id=self._current_location_id,
        )

    def _availability(self) -> RobotAvailability:
        if self._latest_state is None:
            return RobotAvailability.OFFLINE
        if self._busy:
            return RobotAvailability.BUSY
        return RobotAvailability.IDLE

    def dispatch(self, mission: Mission) -> MissionHandle:
        target_location_id = mission.primary_target_location_id

        self._sport.StandUp()
        vx, vy = _heading_towards(
            self._current_location_id, target_location_id, self._location_lookup
        )
        self._sport.Move(vx, vy, 0.0)

        handle = MissionHandle(mission_id=mission.id, robot_id=self._robot_id, ecosystem="unitree")
        self._active_handle = handle
        self._active_target_location_id = target_location_id
        self._dispatch_state_count = self._state_count
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

        state = self._latest_state
        if state is None or self._state_count <= (self._dispatch_state_count or 0):
            return MissionStatusReport(
                mission_id=handle.mission_id, status=MissionStatus.DISPATCHED
            )

        if state.error_code != 0:
            self._terminal_detail = f"sport service reported error_code={state.error_code}"
            self._terminal_status = MissionStatus.FAILED
            self._busy = False
            return MissionStatusReport(
                mission_id=handle.mission_id,
                status=MissionStatus.FAILED,
                detail=self._terminal_detail,
            )

        assert self._active_target_location_id is not None
        target_x, target_y = self._location_lookup(self._active_target_location_id)
        distance = (
            (state.position[0] - target_x) ** 2 + (state.position[1] - target_y) ** 2
        ) ** 0.5

        if distance <= self._arrival_tolerance_m:
            self._current_location_id = self._active_target_location_id
            self._terminal_status = MissionStatus.COMPLETED
            self._busy = False
            return MissionStatusReport(mission_id=handle.mission_id, status=MissionStatus.COMPLETED)

        return MissionStatusReport(mission_id=handle.mission_id, status=MissionStatus.IN_PROGRESS)

    def pause(self, handle: MissionHandle) -> None:
        self._sport.StopMove()

    def resume(self, handle: MissionHandle) -> None:
        if self._active_target_location_id is None or self._terminal_status is not None:
            return
        vx, vy = _heading_towards(
            self._current_location_id, self._active_target_location_id, self._location_lookup
        )
        self._sport.Move(vx, vy, 0.0)

    def abort(self, handle: MissionHandle) -> None:
        self._sport.StopMove()
        self._terminal_status = MissionStatus.ABORTED
        self._busy = False

    def telemetry_stream(self) -> Iterator[TelemetryEvent]:
        # Same seam as vda5050_amr's adapter: live telemetry ingestion is
        # step 8's job (telemetry/), not this adapter's.
        return iter(())

    def close(self) -> None:
        """Not part of FleetAdapter -- needed because unitree_sdk2py's
        DDS state topic uses reliable QoS: a stale reader left registered
        after this adapter is done with it can make a *later* adapter
        instance's publisher block on write() waiting for an ack that
        will never come. Tests close each adapter they create; a
        long-lived production instance would simply never call this."""
        self._state_subscriber.Close()


def _heading_towards(
    from_location_id: int, to_location_id: int, location_lookup: LocationLookup
) -> tuple[float, float]:
    """A crude, open-loop heading command -- there is no closed-loop
    course correction here (no localization feedback drives a fresh
    Move() call), which is exactly the gap the module docstring is
    upfront about: this SDK gives velocity control, not navigation."""
    from_x, from_y = location_lookup(from_location_id)
    to_x, to_y = location_lookup(to_location_id)
    dx, dy = to_x - from_x, to_y - from_y
    magnitude = max((dx**2 + dy**2) ** 0.5, 1e-6)
    speed = 0.3
    return (dx / magnitude * speed, dy / magnitude * speed)
