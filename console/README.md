# console

Thin TypeScript (Vite + React) operator UI: work orders, live mission
status, the audit trail, and the escalation queue with approve/abort
buttons. See CLAUDE.md section 4.8. Deliberately thin -- this is the
second language on the spec, not the product; no dashboards, charts, or
admin panels beyond what section 4.8 states.

Built at build-sequence step 9.

## What's here

- `src/api.ts` -- typed `fetch` wrappers for two backends:
  - `eam`'s own REST API (`VITE_EAM_URL`, default `http://localhost:8000`)
    for ordinary work order data.
  - `mcp_server`'s `http_api.py` (`VITE_HTTP_API_URL`, default
    `http://localhost:8001`) for the pieces `eam` knows nothing about:
    live mission status, the audit trail, and escalation approve/abort.
- `src/components/WorkOrdersTable.tsx` -- all work orders and their
  status, polling `eam` every few seconds.
- `src/components/EscalationQueue.tsx` -- work orders sitting in
  `AwaitingHuman`, with Approve/Abort buttons calling `http_api.py`.
- `src/components/MissionStatus.tsx` -- live status for a selected work
  order's dispatched mission (or "no mission dispatched yet").
- `src/components/AuditTrail.tsx` -- the recent audit log, from
  `http_api.py`.

## Not covered

- No websockets/live push -- plain polling (a few seconds), which is
  enough for a demo and keeps this thin.
- No routing, no state management library, no charts.
- No automated frontend test suite -- CLAUDE.md section 5 doesn't pin a
  JS test framework, and adding one wasn't asked for. Verified instead
  by actually running the full stack (`eam`, `mcp_server.http_api`, and
  this dev server) and driving it in a real browser: work orders load
  and poll from `eam`; selecting a row scopes mission status and the
  audit trail to it; transitioning a work order to `AwaitingHuman` makes
  it appear in the escalation queue; Approve and Abort each call the
  right endpoint and the queue updates accordingly.

## Running it

Needs `eam` running (default `http://localhost:8000`) and
`mcp_server`'s HTTP API running (`uv run python -m mcp_server.http_api`,
default `http://localhost:8001`):

```bash
npm install
npm run dev
```

Override the backend URLs with a `.env.local` file:

```
VITE_EAM_URL=http://localhost:8000
VITE_HTTP_API_URL=http://localhost:8001
```
