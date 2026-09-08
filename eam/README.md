# eam

Mock EAM (asset/work-order) business system. See CLAUDE.md section 4.1.

Built at build-sequence step 2. FastAPI, plain `sqlite3` (no ORM), no
network calls other than best-effort webhook delivery.

## What's here

- `models.py` -- Pydantic models, the work order status enum, and the
  allowed-transition table (`Draft -> Released -> Dispatched -> InProgress
  -> AwaitingHuman -> Completed | Failed | Cancelled`).
- `db.py` -- SQLite persistence, one table per entity, no migrations
  (schema is `CREATE TABLE IF NOT EXISTS`, fine for a demo that always
  starts from seed data or a throwaway file).
- `webhooks.py` -- fires a `work_order.released` POST to every registered
  subscriber when a work order transitions into `Released`. Best-effort:
  a failed delivery is logged, not retried, and never blocks the
  transition that triggered it.
- `odata.py` / `api_odata.py` -- a deliberately partial OData v4 surface:
  `$metadata`, the collection/entity response envelope, and `$select`,
  `$filter` (equality only: `field eq value`), `$top`, `$skip`. No
  `$expand`, `$orderby`, `$count`, or write support. This is not a
  spec-compliant OData server -- it is enough of the dialect to look and
  behave like the target ERP suite's API for the entity sets this repo
  touches.
- `api_rest.py` -- plain REST for the same data, plus the endpoints OData
  doesn't cover: creating a work order, transitioning its status,
  uploading/downloading attachments, and managing webhook subscriptions.
- `seed.py` -- one small site (a pumping station), 7 locations, 20 assets,
  3 robots (one per adapter ecosystem), and 5 work orders (4 `Draft`, 1
  historical `Completed`).
- `app.py` -- FastAPI app factory (`create_app`) and the default
  entrypoint (`eam.app:app`) for uvicorn.

## Not covered

- No auth on any endpoint (machine identity lands in `identity/`, step 5).
- No pagination beyond `$top`/`$skip` on the REST endpoints (OData has it,
  REST doesn't -- REST is the convenience layer, OData is the one that
  has to look like the real thing).
- Webhook delivery has no retry, backoff, or dead-letter handling.

## Running it

```bash
uv run uvicorn eam.app:app --reload
```

Uses `eam.db` (SQLite file in the current directory) by default, or set
`EAM_DB_PATH` to point elsewhere. Seeds automatically on first run if the
database is empty.

```bash
uv run pytest eam
```

## Public demo deployment

Deployed to Railway (see `deploy/eam/Dockerfile`, `railway.json`, and
[ADR-003](../docs/decisions/adr-003-railway-demo-hosting.md)) for a public
link to use in interviews:

https://robo-sim-production.up.railway.app

This is separate from, not a replacement for, the docker-compose/k3d path
in CLAUDE.md section 9's definition of done. No persistent volume --
every deploy/restart starts from a fresh reseed.
