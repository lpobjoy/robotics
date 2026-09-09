"""Stands in for the Go2's onboard sport service: a real DDS RPC
responder built on unitree_sdk2py's own Server class (the same base
class the real robot's service would extend), answering the same
"sport" service requests a real SportClient sends, and publishing real
SportModeState telemetry on the same topic the adapter subscribes to.
This lets UnitreeAdapter's own protocol logic be tested against real DDS
messages without needing a physical Go2 -- a clearly labelled test
double, not a claim that this is what adapters/unitree/ IS.
"""

from __future__ import annotations

import json

from unitree.adapter import SPORT_STATE_TOPIC
from unitree_sdk2py.core.channel import ChannelPublisher
from unitree_sdk2py.go2.sport.sport_api import (
    SPORT_API_ID_MOVE,
    SPORT_API_ID_STANDUP,
    SPORT_API_ID_STOPMOVE,
    SPORT_API_VERSION,
    SPORT_SERVICE_NAME,
)
from unitree_sdk2py.idl.default import unitree_go_msg_dds__SportModeState_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_
from unitree_sdk2py.rpc.server import Server


class FakeSportService(Server):
    """A single instance is shared for a whole test module (see
    conftest.py): unitree_sdk2py's ChannelFactory is a process-wide
    singleton (ChannelFactoryInitialize can only meaningfully run once),
    so a second competing Server registered against the same "sport"
    service in the same process would leave two handlers listening on
    the same request topic. Tests drive this one shared fake's behaviour
    by calling its methods directly (publish_state, error_code) rather
    than by constructing a fresh instance per test.
    """

    def __init__(self) -> None:
        super().__init__(SPORT_SERVICE_NAME)
        self.stand_up_calls = 0
        self.move_calls: list[tuple[float, float, float]] = []
        self.stop_move_calls = 0
        self._state_publisher = ChannelPublisher(SPORT_STATE_TOPIC, SportModeState_)
        self._state_publisher.Init()

    def Init(self) -> None:  # noqa: N802 (matches unitree_sdk2py's own PascalCase API)
        self._SetApiVersion(SPORT_API_VERSION)
        self._RegistHandler(SPORT_API_ID_STANDUP, self._stand_up, False)
        self._RegistHandler(SPORT_API_ID_MOVE, self._move, False)
        self._RegistHandler(SPORT_API_ID_STOPMOVE, self._stop_move, False)

    def _stand_up(self, parameter: str) -> tuple[int, str]:
        self.stand_up_calls += 1
        return 0, ""

    def _move(self, parameter: str) -> tuple[int, str]:
        p = json.loads(parameter)
        self.move_calls.append((p["x"], p["y"], p["z"]))
        return 0, ""

    def _stop_move(self, parameter: str) -> tuple[int, str]:
        self.stop_move_calls += 1
        return 0, ""

    def publish_state(
        self, position: tuple[float, float, float], error_code: int = 0
    ) -> None:
        """What a real Go2 broadcasts continuously on rt/sportmodestate.
        Tests use this to move the fake robot's reported position, the
        same role FakeRobot.report_driving plays for vda5050_amr."""
        state = unitree_go_msg_dds__SportModeState_()
        state.position = list(position)
        state.error_code = error_code
        self._state_publisher.Write(state)
