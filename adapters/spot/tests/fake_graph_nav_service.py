"""A real gRPC servicer standing in for Spot's onboard GraphNav service,
built the same way Boston Dynamics' own bosdyn-client unit tests fake it
(see their test_graph_nav_client.py): subclass the generated
GraphNavServiceServicer and implement just the RPCs this adapter calls.
A clearly labelled test double, not a claim that this is what
adapters/spot/ IS -- there's no public Spot simulator to run against
instead.
"""

from __future__ import annotations

from bosdyn.api import header_pb2
from bosdyn.api.graph_nav import graph_nav_pb2, graph_nav_service_pb2_grpc


class FakeGraphNavService(graph_nav_service_pb2_grpc.GraphNavServiceServicer):
    def __init__(self) -> None:
        self.navigate_to_calls: list[str] = []
        self.next_command_id = 1
        self.feedback_status = graph_nav_pb2.NavigationFeedbackResponse.STATUS_FOLLOWING_ROUTE

    def NavigateTo(self, request, context):  # noqa: N802 (matches the generated servicer's API)
        self.navigate_to_calls.append(request.destination_waypoint_id)
        command_id = self.next_command_id
        self.next_command_id += 1
        response = graph_nav_pb2.NavigateToResponse(
            status=graph_nav_pb2.NavigateToResponse.STATUS_OK, command_id=command_id
        )
        response.header.error.code = header_pb2.CommonError.CODE_OK
        return response

    def NavigationFeedback(self, request, context):  # noqa: N802
        response = graph_nav_pb2.NavigationFeedbackResponse(status=self.feedback_status)
        response.header.error.code = header_pb2.CommonError.CODE_OK
        return response
