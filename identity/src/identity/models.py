"""Data shapes for the minimal token issuer (CLAUDE.md section 4.7, see
ADR-004 for why this isn't Keycloak).
"""

from __future__ import annotations

from pydantic import BaseModel


class IssuedToken(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: float  # unix timestamp


class ClientIdentity(BaseModel):
    client_id: str
    scopes: list[str]
