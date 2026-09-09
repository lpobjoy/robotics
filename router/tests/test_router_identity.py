"""Machine identity on adapter registration (CLAUDE.md section 4.7,
ADR-004). Separate from test_router.py's pure selection/audit tests,
which deliberately don't configure identity -- Router without an
IdentityService behaves exactly as it did in step 4.
"""

from __future__ import annotations

import pytest
from audit.sink import InMemoryAuditSink
from identity.registry import ClientRegistry
from identity.service import IdentityService
from identity.tokens import TokenIssuer
from router.fake_adapter import FakeAdapter
from router.models import MissionType
from router.router import AdapterAuthenticationError, Router
from worldmodel.graph import build_graph
from worldmodel.models import Location


@pytest.fixture
def identity() -> IdentityService:
    registry = ClientRegistry()
    registry.register("amr-01", "amr-01-secret", ["dispatch"])
    registry.register("spot-01", "spot-01-secret", ["dispatch"])
    return IdentityService(registry, TokenIssuer("router-test-secret"))


def _graph() -> object:
    return build_graph([Location(id=1, name="Pump House", x=0.0, y=0.0)], [], [], [], [])


def _fake(robot_id: str) -> FakeAdapter:
    return FakeAdapter(robot_id, robot_id, "vda5050_amr", [MissionType.INSPECT_VISUAL], 1)


def test_adapter_with_a_valid_token_registers_and_is_audited(identity: IdentityService) -> None:
    audit = InMemoryAuditSink()
    router = Router(_graph(), audit_sink=audit, identity=identity)
    token = identity.token_for_client_credentials("amr-01", "amr-01-secret").access_token

    router.register_adapter(_fake("amr-01"), token=token)

    assert any(e.action == "adapter.register" for e in audit.events)


def test_adapter_with_no_token_is_rejected(identity: IdentityService) -> None:
    audit = InMemoryAuditSink()
    router = Router(_graph(), audit_sink=audit, identity=identity)

    with pytest.raises(AdapterAuthenticationError):
        router.register_adapter(_fake("amr-01"))

    assert any(e.action == "adapter.register.rejected" for e in audit.events)


def test_adapter_with_an_invalid_token_is_rejected(identity: IdentityService) -> None:
    router = Router(_graph(), identity=identity)

    with pytest.raises(AdapterAuthenticationError):
        router.register_adapter(_fake("amr-01"), token="not-a-real-token")


def test_adapter_cannot_register_as_a_different_robot(identity: IdentityService) -> None:
    """spot-01's own valid token must not authenticate amr-01 -- each
    adapter is its own client, not a shared credential."""
    router = Router(_graph(), identity=identity)
    spot_token = identity.token_for_client_credentials("spot-01", "spot-01-secret").access_token

    with pytest.raises(AdapterAuthenticationError):
        router.register_adapter(_fake("amr-01"), token=spot_token)


def test_router_without_identity_configured_ignores_tokens_entirely() -> None:
    """Step 4 behaviour is preserved for callers that don't opt into
    identity enforcement."""
    router = Router(_graph())
    router.register_adapter(_fake("amr-01"))  # no token, no identity service -- must not raise
