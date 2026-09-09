# ADR-004: Minimal token issuer instead of Keycloak for machine identity

## Status

Accepted

## Context

CLAUDE.md section 4.7 requires each adapter to authenticate to the
router and the EAM as its own OIDC client (client-credentials grant),
and explicitly allows two options: "Use a local Keycloak or a minimal
token issuer; do not build auth from scratch."

Keycloak is a full, JVM-based identity provider: realms, client
registration, an admin console, a real OIDC discovery document and JWKS
endpoint. Standing it up in `deploy/docker-compose.yml` for this repo's
scale (3 robots, one router process) is a lot of infrastructure for what
the demo needs to prove -- that a machine actor holds credentials, gets a
short-lived bearer token via client-credentials, and that token is
verified before the actor can act.

## Decision

Build a minimal token issuer (`identity/`) instead:

- `TokenIssuer` mints and verifies HS256 JWT-shaped bearer tokens
  (header.payload.signature, base64url, HMAC-SHA256) using only the
  standard library -- no new dependency.
- `ClientRegistry` holds client_id -> hashed secret + scopes. Secrets are
  hashed at rest (SHA-256); comparison uses `hmac.compare_digest`.
- `IdentityService` wires the two together: `token_for_client_credentials`
  implements the client_credentials grant; `verify` checks a presented
  token.

This is a client-credentials token issuer, not an OIDC provider: no
discovery document, no JWKS, no key rotation, no refresh tokens, one
shared signing secret for the whole demo. That is the deliberate scope
of "a minimal token issuer" as named in the brief, not an attempt to
half-build Keycloak.

## Consequences

- If this needs to look more like a real OIDC deployment later (for the
  interview's technical depth conversation, say), Keycloac is the
  documented swap -- this ADR is the place to record that decision if it
  happens, not a silent upgrade.
- `router.Router` treats identity as optional: constructed without an
  `IdentityService`, it behaves exactly as it did in step 4 (no auth
  enforced, existing tests unchanged). Constructed with one, adapter
  registration requires a valid token whose `client_id` matches the
  adapter's own `robot_id` -- proving the concept at the one real
  integration boundary that exists yet (adapter registration), since
  `FleetAdapter` calls in this repo are still in-process method calls,
  not network hops. A real deployment would put this check on every
  adapter-to-router network call; that seam is described here, not
  silently pretended away.
