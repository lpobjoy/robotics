# Security

CLAUDE.md section 4.7. What's actually built (machine identity), and
one paragraph on what isn't (OT network segmentation,
`DESCRIBED_NOT_BUILT`).

## Machine identity — built at step 5

Every adapter authenticates to the router as its own client, the same
shape as OIDC client-credentials: a `client_id`, a `client_secret`
(stored hashed, never in plaintext), and a signed token presented on
`register_adapter()`.

`identity/` is a **minimal stdlib token issuer**, not Keycloak, not
PyJWT — `hmac`/`hashlib`/`base64`/`json`, HS256-shaped tokens. ADR-004
records why: standing up a real Keycloak instance for a portfolio demo
would have added a whole extra service, a whole extra failure mode, and
a whole extra thing to explain in a live session, in exchange for
testing a token-verification code path this repo can exercise just as
genuinely with 80 lines of stdlib crypto. The token *shape* (issuer,
subject, expiry, HMAC signature) is the real, standard shape; the
*issuer* is a toy. Said explicitly, because it would be easy to glance
at "HS256 token" and assume more than that.

What's real about it:

- `identity/tokens.py`'s `TokenIssuer` signs and verifies tokens with a
  shared secret; a tampered token (changed payload, wrong signature,
  expired) is rejected — tested in `identity/tests/test_tokens.py`
  with an actually-tampered token, not just a round-trip.
- `identity/registry.py`'s `ClientRegistry` never stores a secret in
  plaintext — it stores a salted hash and verifies against it, the
  same pattern a real credential store uses.
- `router/router.py`'s `register_adapter()` — when constructed with an
  `IdentityService` — requires a valid token whose `client_id` matches
  the adapter's own `robot_id` before the adapter is added to the
  registry at all. Presenting no token, an invalid token, or a token
  for the wrong robot is all explicitly tested
  (`router/tests/test_router.py`) and all three cases are recorded to
  the audit log as `adapter.register.rejected` before raising.

What's not real about it, also said explicitly:

- No token rotation, no refresh flow, no revocation list.
- No transport security modeled at all — a real deployment would run
  this over TLS (mTLS, ideally, given CLAUDE.md section 4.7 names it as
  an alternative) or wrap the MQTT/DDS/gRPC transports in their own
  secured variants; this repo runs everything on loopback or a local
  Docker network, so there is nothing to secure it against.
- The identity check happens once, at `register_adapter()` time. A
  registered adapter's every subsequent `dispatch`/`status`/`pause`/
  `resume`/`abort` call is trusted for the life of that in-memory
  registration — there's no per-call re-authentication, because these
  are in-process Python method calls in this repo, not network hops to
  a physically separate robot. A real deployment, where the router and
  the adapter genuinely run on different machines, needs per-call
  authentication (or a session/lease that expires) — this is the same
  distinction `router/README.md`'s "Not covered" section already
  states about identity.
- `mcp_server/wiring.py` — the wiring actually used by the running demo
  — never passes an `IdentityService` to `Router` at all, so every
  `FakeAdapter` registers unauthenticated. The identity check is real
  and tested in isolation; it's not switched on in the end-to-end demo
  path, because doing so would mean generating and distributing tokens
  for adapters this repo never runs as separate processes with their
  own credentials to begin with.

## Network segmentation for OT — `DESCRIBED_NOT_BUILT`

A real site running this pattern would put every robot, every MQTT
broker, and every adapter on an OT (operational technology) network
segment separate from the IT network the EAM and the agent live on —
typically a purdue-model-style layered network with a DMZ or a
one-way/broker-mediated boundary between them, so a compromise on the
office network can't reach the robots directly and a compromised robot
can't reach the business system directly either. The MQTT broker (or a
protocol gateway in front of it) is usually the one thing that
straddles both sides, and it's the one thing worth hardening hardest:
authenticated, TLS-terminated MQTT with per-adapter credentials and
topic-level ACLs (a real robot should not be able to publish on
another robot's topic, let alone subscribe to the EAM's webhook feed),
rather than the anonymous, unauthenticated Mosquitto this repo runs for
convenience. None of that segmentation is modeled here — `deploy/`'s
docker-compose and k3d manifests put everything on one flat network,
which is honest for a laptop demo and would be a real finding in a
security review of an actual deployment.
