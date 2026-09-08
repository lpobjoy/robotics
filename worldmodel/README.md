# worldmodel

NetworkX graph built from EAM data, answering: for this work order, which
locations, which required capabilities, which robots qualify, what route.
See CLAUDE.md section 4.2 -- "this is the productisable asset in the
story."

Built at build-sequence step 3.

## What's here

- `models.py` -- the data shapes this module needs (`Location`,
  `LocationLink`, `Asset`, `Robot`, `WorkOrder`), defined independently of
  `eam`'s own models. This module is meant to work against anything that
  returns this shape over HTTP, not specifically the mock in this repo.
- `client.py` -- `EamClient`, a small `httpx`-based REST client. Plain
  REST, not OData -- this is an internal consumer, not the surface
  `eam/api_odata.py` exists to mimic.
- `graph.py` -- `build_graph(...)` turns EAM data into an `nx.DiGraph`:
  `Asset -LOCATED_AT-> Location`, `Location -REACHABLE_FROM-> Location`,
  `Robot -HAS_CAPABILITY-> Capability`, `WorkOrder -TARGETS-> Asset`,
  `WorkOrder -REQUIRES-> Capability`, plus `Robot -LOCATED_AT-> Location`
  for the robot's home base (not in section 4.2's list, but needed to
  answer "what route" at all). `build_graph_from_eam(client)` builds it
  straight from a live `EamClient`.
- `query.py` -- `qualify_robots_for_work_order(graph, work_order_id)`:
  the one function that answers the question this module exists for. A
  robot qualifies if it has *every* required capability (not just one)
  and a `location_links` path exists from its home location to the work
  order's target. Results are ranked by route distance, cheapest first.

## Not covered

- Availability (idle vs busy) is not checked here. That changes in real
  time during dispatch, so it belongs to the router's selection logic
  (CLAUDE.md section 4.4, step 4), not to a graph built once per lookup.
- The graph is rebuilt from scratch on every call to
  `build_graph_from_eam` -- no caching, no incremental updates, no
  subscription to EAM changes. Fine for this repo's scale; a real
  deployment would need one of those.
- Neo4j is an explicitly deferred swap (CLAUDE.md section 4.2) -- NetworkX
  in memory only.

## Running it

```bash
uv run pytest worldmodel
```

Most tests build small hand-written graphs directly (fast, no EAM
needed). A few build the real graph from `eam`'s actual seed data via
`EamClient` over `fastapi.testclient.TestClient` -- in-process, no socket
-- per CLAUDE.md section 6 step 3 ("Tests with the seed data").

There's no standalone way to "run" worldmodel on its own; it's a library
consumed by `router`/`agent` starting at step 4.
