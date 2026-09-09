from __future__ import annotations

import pytest
from identity.registry import ClientRegistry
from identity.service import AuthenticationError, IdentityService
from identity.tokens import TokenIssuer


@pytest.fixture
def service() -> IdentityService:
    registry = ClientRegistry()
    registry.register("adapter:vda5050_amr", "correct-secret", ["dispatch"])
    return IdentityService(registry, TokenIssuer("test-secret"))


def test_client_credentials_grant_issues_a_verifiable_token(service: IdentityService) -> None:
    issued = service.token_for_client_credentials("adapter:vda5050_amr", "correct-secret")

    identity = service.verify(issued.access_token)

    assert identity.client_id == "adapter:vda5050_amr"
    assert identity.scopes == ["dispatch"]


def test_wrong_secret_is_rejected(service: IdentityService) -> None:
    with pytest.raises(AuthenticationError):
        service.token_for_client_credentials("adapter:vda5050_amr", "wrong-secret")


def test_unknown_client_is_rejected(service: IdentityService) -> None:
    with pytest.raises(AuthenticationError):
        service.token_for_client_credentials("adapter:does-not-exist", "anything")


def test_secrets_are_never_stored_in_plaintext() -> None:
    registry = ClientRegistry()
    registry.register("adapter:spot", "super-secret-value", [])

    client = registry.authenticate("adapter:spot", "super-secret-value")
    assert client is not None
    assert "super-secret-value" not in client.secret_hash
