# identity

Machine identity for adapters: a minimal, client-credentials token
issuer. See CLAUDE.md section 4.7 and
[ADR-004](../docs/decisions/adr-004-machine-identity.md) for why this
isn't Keycloak.

Built at build-sequence step 5.

## What's here

- `tokens.py` -- `TokenIssuer`: stdlib-only HS256 JWT-shaped bearer
  tokens (`issue`/`verify`). No new dependency -- `hmac`, `hashlib`,
  `base64`, `json` are enough for this scope.
- `registry.py` -- `ClientRegistry`: client_id -> hashed secret + scopes.
  Secrets are hashed at rest and compared with `hmac.compare_digest`.
- `service.py` -- `IdentityService`: wires the two into the
  client_credentials grant (`token_for_client_credentials`) and token
  verification (`verify`).

`router.Router` uses this: if constructed with an `IdentityService`, an
adapter must present a valid token whose `client_id` matches its own
`robot_id` to register.

## Not covered

- No OIDC discovery document, no JWKS, no key rotation, no refresh
  tokens -- one shared HMAC secret for the whole demo.
- No network service: this is a library used in-process. A real
  deployment would run it (or Keycloak) as its own service with adapters
  calling a `/token` endpoint over the network; that seam is described in
  ADR-004, not built.

## Running it

```bash
uv run pytest identity
```
