"""Static client registry: one credential pair per machine actor (each
robot adapter, for now). Secrets are hashed at rest and never logged or
returned in plaintext after registration.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RegisteredClient:
    client_id: str
    secret_hash: str
    scopes: list[str]


class ClientRegistry:
    def __init__(self) -> None:
        self._clients: dict[str, RegisteredClient] = {}

    def register(self, client_id: str, secret: str, scopes: list[str]) -> None:
        self._clients[client_id] = RegisteredClient(client_id, _hash_secret(secret), scopes)

    def authenticate(self, client_id: str, secret: str) -> RegisteredClient | None:
        client = self._clients.get(client_id)
        if client is None:
            return None
        if not hmac.compare_digest(client.secret_hash, _hash_secret(secret)):
            return None
        return client
