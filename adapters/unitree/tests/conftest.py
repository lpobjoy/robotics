"""unitree_sdk2py's ChannelFactory is a process-wide singleton --
ChannelFactoryInitialize only has an effect the first time it's called
in a process, silently no-oping on every call after that (confirmed by
reading unitree_sdk2py.core.channel.ChannelFactory.Init). The "sport"
RPC service name is likewise fixed by the SDK (SportClient always talks
to a service named "sport", not one scoped per robot instance), so only
one FakeSportService can safely exist per pytest session -- a second one
would leave two servers both listening for the same requests. That
fake service is session-scoped and shared by every test here; a fresh
SportClient (and adapter) is still created per test, the same way
vda5050_amr gets a fresh mqtt.Client per test even though its broker is
shared for the whole module.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fake_sport_service import FakeSportService
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.go2.sport.sport_client import SportClient


@pytest.fixture(scope="session", autouse=True)
def dds_domain() -> None:
    ChannelFactoryInitialize(0)


@pytest.fixture(scope="session")
def fake_sport_service(dds_domain: None) -> FakeSportService:
    service = FakeSportService()
    service.Init()
    service.Start(False)
    return service


@pytest.fixture
def sport_client(fake_sport_service: FakeSportService) -> SportClient:
    client = SportClient()
    client.SetTimeout(5.0)
    client.Init()
    return client


@pytest.fixture(autouse=True)
def _reset_fake_service(fake_sport_service: FakeSportService) -> Iterator[None]:
    fake_sport_service.stand_up_calls = 0
    fake_sport_service.move_calls = []
    fake_sport_service.stop_move_calls = 0
    yield
