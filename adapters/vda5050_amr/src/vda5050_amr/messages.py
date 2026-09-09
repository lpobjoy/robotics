"""VDA 5050 message models -- a pragmatically-scoped subset of the
spec (v2.x), not an exhaustive implementation. Included: the header
fields every message carries, Order/Node/Edge/Action (enough to send a
sequence of navigation waypoints with an inspection action at the end),
InstantActions, State (enough to report mission progress, battery, and
errors), Visualization (position/velocity), and Connection.

Not included: zone sets, node/edge maps beyond a single map, safety
state, and the full action-parameter-type system. Those aren't needed to
express "go to these locations and do this inspection," which is all
this repo's missions ever ask for.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field


class Header(BaseModel):
    header_id: int = Field(alias="headerId")
    timestamp: str
    version: str
    manufacturer: str
    serial_number: str = Field(alias="serialNumber")

    model_config = {"populate_by_name": True}


class ActionBlockingType(enum.StrEnum):
    NONE = "NONE"
    SOFT = "SOFT"
    HARD = "HARD"


class ActionParameter(BaseModel):
    key: str
    value: str | int | float | bool


class Action(BaseModel):
    action_type: str = Field(alias="actionType")
    action_id: str = Field(alias="actionId")
    blocking_type: ActionBlockingType = Field(alias="blockingType")
    action_description: str = Field(default="", alias="actionDescription")
    action_parameters: list[ActionParameter] = Field(
        default_factory=list, alias="actionParameters"
    )

    model_config = {"populate_by_name": True}


class NodePosition(BaseModel):
    x: float
    y: float
    theta: float = 0.0
    map_id: str = Field(default="site", alias="mapId")

    model_config = {"populate_by_name": True}


class Node(BaseModel):
    node_id: str = Field(alias="nodeId")
    sequence_id: int = Field(alias="sequenceId")
    released: bool = True
    node_position: NodePosition = Field(alias="nodePosition")
    actions: list[Action] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class Edge(BaseModel):
    edge_id: str = Field(alias="edgeId")
    sequence_id: int = Field(alias="sequenceId")
    released: bool = True
    start_node_id: str = Field(alias="startNodeId")
    end_node_id: str = Field(alias="endNodeId")
    actions: list[Action] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class Order(BaseModel):
    header: Header
    order_id: str = Field(alias="orderId")
    order_update_id: int = Field(default=0, alias="orderUpdateId")
    nodes: list[Node]
    edges: list[Edge]

    model_config = {"populate_by_name": True}


class InstantActions(BaseModel):
    header: Header
    actions: list[Action]

    model_config = {"populate_by_name": True}


class ActionStatus(enum.StrEnum):
    WAITING = "WAITING"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"


class ActionState(BaseModel):
    action_id: str = Field(alias="actionId")
    action_type: str = Field(alias="actionType")
    action_status: ActionStatus = Field(alias="actionStatus")
    result_description: str = Field(default="", alias="resultDescription")

    model_config = {"populate_by_name": True}


class BatteryState(BaseModel):
    battery_charge: float = Field(alias="batteryCharge")
    charging: bool = False

    model_config = {"populate_by_name": True}


class ErrorLevel(enum.StrEnum):
    WARNING = "WARNING"
    FATAL = "FATAL"


class Error(BaseModel):
    error_type: str = Field(alias="errorType")
    error_level: ErrorLevel = Field(alias="errorLevel")
    error_description: str = Field(default="", alias="errorDescription")

    model_config = {"populate_by_name": True}


class OperatingMode(enum.StrEnum):
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    SERVICE = "SERVICE"


class State(BaseModel):
    header: Header
    order_id: str = Field(default="", alias="orderId")
    last_node_id: str = Field(default="", alias="lastNodeId")
    driving: bool = False
    operating_mode: OperatingMode = Field(
        default=OperatingMode.AUTOMATIC, alias="operatingMode"
    )
    action_states: list[ActionState] = Field(default_factory=list, alias="actionStates")
    battery_state: BatteryState = Field(alias="batteryState")
    errors: list[Error] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class AgvPosition(BaseModel):
    x: float
    y: float
    theta: float = 0.0
    map_id: str = Field(default="site", alias="mapId")
    position_initialized: bool = Field(default=True, alias="positionInitialized")

    model_config = {"populate_by_name": True}


class Velocity(BaseModel):
    vx: float = 0.0
    vy: float = 0.0
    omega: float = 0.0


class Visualization(BaseModel):
    header: Header
    agv_position: AgvPosition = Field(alias="agvPosition")
    velocity: Velocity = Field(default_factory=Velocity)

    model_config = {"populate_by_name": True}


class ConnectionState(enum.StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    CONNECTIONBROKEN = "CONNECTIONBROKEN"


class Connection(BaseModel):
    header: Header
    connection_state: ConnectionState = Field(alias="connectionState")

    model_config = {"populate_by_name": True}
