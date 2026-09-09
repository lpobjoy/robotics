"""A real (in-process) gRPC server + channel per test, the same pattern
bosdyn-client's own unit tests use (see test_graph_nav_client.py
upstream) -- unlike unitree_sdk2py's DDS, gRPC has no process-wide
singleton getting in the way, so each test gets a fully fresh server.
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Iterator

import grpc
import pytest
from bosdyn.api import time_sync_pb2
from bosdyn.api.graph_nav import graph_nav_service_pb2_grpc
from bosdyn.client.graph_nav import GraphNavClient
from bosdyn.client.time_sync import TimeSyncEndpoint
from fake_graph_nav_service import FakeGraphNavService


@pytest.fixture
def fake_graph_nav_service() -> FakeGraphNavService:
    return FakeGraphNavService()


@pytest.fixture
def graph_nav_client(fake_graph_nav_service: FakeGraphNavService) -> Iterator[GraphNavClient]:
    client = GraphNavClient()

    # bosdyn-client requires a timesync endpoint before navigate_to will
    # even build a request -- constructed the same minimal way
    # bosdyn-client's own tests do, with no real timesync RPC exchange
    # (there's no robot to exchange it with).
    timesync = TimeSyncEndpoint(None)
    timesync._locked_previous_response = time_sync_pb2.TimeSyncUpdateResponse()
    timesync.response.state.status = time_sync_pb2.TimeSyncState.STATUS_OK
    client._timesync_endpoint = timesync

    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=1))
    graph_nav_service_pb2_grpc.add_GraphNavServiceServicer_to_server(fake_graph_nav_service, server)
    port = server.add_insecure_port("127.0.0.1:0")
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    client.channel = channel
    server.start()

    yield client

    server.stop(None)
