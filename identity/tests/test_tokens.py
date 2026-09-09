from __future__ import annotations

import time

import pytest
from identity.tokens import InvalidTokenError, TokenIssuer


def test_issued_token_verifies_back_to_the_same_client() -> None:
    issuer = TokenIssuer("test-secret")
    issued = issuer.issue("adapter:vda5050_amr", ["dispatch"])

    identity = issuer.verify(issued.access_token)

    assert identity.client_id == "adapter:vda5050_amr"
    assert identity.scopes == ["dispatch"]


def test_token_signed_with_a_different_secret_is_rejected() -> None:
    issuer_a = TokenIssuer("secret-a")
    issuer_b = TokenIssuer("secret-b")
    issued = issuer_a.issue("adapter:spot", [])

    with pytest.raises(InvalidTokenError):
        issuer_b.verify(issued.access_token)


def test_malformed_token_is_rejected() -> None:
    issuer = TokenIssuer("test-secret")
    with pytest.raises(InvalidTokenError):
        issuer.verify("not-a-real-token")


def test_tampered_payload_is_rejected() -> None:
    issuer = TokenIssuer("test-secret")
    issued = issuer.issue("adapter:unitree", ["dispatch"])
    header, payload, signature = issued.access_token.split(".")

    tampered = f"{header}.{payload}extra.{signature}"

    with pytest.raises(InvalidTokenError):
        issuer.verify(tampered)


def test_expired_token_is_rejected() -> None:
    issuer = TokenIssuer("test-secret", ttl_seconds=0)
    issued = issuer.issue("adapter:spot", [])
    time.sleep(0.01)

    with pytest.raises(InvalidTokenError):
        issuer.verify(issued.access_token)
