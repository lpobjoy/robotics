"""Wires the client registry and token issuer into the client_credentials
grant flow (CLAUDE.md section 4.7).
"""

from __future__ import annotations

from identity.models import ClientIdentity, IssuedToken
from identity.registry import ClientRegistry
from identity.tokens import TokenIssuer


class AuthenticationError(RuntimeError):
    """Raised when a client presents the wrong client_id/secret pair."""


class IdentityService:
    def __init__(self, registry: ClientRegistry, issuer: TokenIssuer) -> None:
        self._registry = registry
        self._issuer = issuer

    def token_for_client_credentials(self, client_id: str, client_secret: str) -> IssuedToken:
        client = self._registry.authenticate(client_id, client_secret)
        if client is None:
            raise AuthenticationError(f"invalid credentials for client {client_id!r}")
        return self._issuer.issue(client.client_id, client.scopes)

    def verify(self, token: str) -> ClientIdentity:
        return self._issuer.verify(token)
