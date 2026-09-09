"""A minimal, stdlib-only HS256 JWT-shaped bearer token issuer and
verifier -- enough to prove the client-credentials machine-identity
concept CLAUDE.md section 4.7 asks for. Not a real OIDC provider: no
discovery document, no JWKS, no key rotation, no refresh tokens. See
ADR-004.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from identity.models import ClientIdentity, IssuedToken


class InvalidTokenError(ValueError):
    """Raised when a presented token is malformed, unsigned by us, or expired."""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


class TokenIssuer:
    """One shared HMAC signing secret for the whole demo. A real
    deployment would use per-environment secrets and asymmetric keys;
    this is a minimal token issuer, not a production identity provider.
    """

    def __init__(self, signing_secret: str, *, ttl_seconds: int = 3600) -> None:
        self._signing_secret = signing_secret.encode("utf-8")
        self._ttl_seconds = ttl_seconds

    def issue(self, client_id: str, scopes: list[str]) -> IssuedToken:
        now = time.time()
        expires_at = now + self._ttl_seconds
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": client_id,
            "scope": " ".join(scopes),
            "iat": int(now),
            "exp": int(expires_at),
        }
        signing_input = (
            f"{_b64url_encode(json.dumps(header).encode())}."
            f"{_b64url_encode(json.dumps(payload).encode())}"
        )
        signature = hmac.new(self._signing_secret, signing_input.encode(), hashlib.sha256).digest()
        token = f"{signing_input}.{_b64url_encode(signature)}"
        return IssuedToken(access_token=token, expires_at=expires_at)

    def verify(self, token: str) -> ClientIdentity:
        parts = token.split(".")
        if len(parts) != 3:
            raise InvalidTokenError("malformed token")
        header_b64, payload_b64, signature_b64 = parts

        signing_input = f"{header_b64}.{payload_b64}"
        expected_signature = hmac.new(
            self._signing_secret, signing_input.encode(), hashlib.sha256
        ).digest()
        try:
            actual_signature = _b64url_decode(signature_b64)
        except Exception as exc:
            raise InvalidTokenError("malformed signature") from exc
        if not hmac.compare_digest(actual_signature, expected_signature):
            raise InvalidTokenError("bad signature")

        try:
            payload = json.loads(_b64url_decode(payload_b64))
        except Exception as exc:
            raise InvalidTokenError("malformed payload") from exc

        if payload.get("exp", 0) < time.time():
            raise InvalidTokenError("token expired")

        scope = payload.get("scope", "")
        return ClientIdentity(client_id=payload["sub"], scopes=scope.split() if scope else [])
