# ADR-002: Agent framework for the mission agent

## Status

Accepted

## Context

`agent/` (CLAUDE.md section 4.3) plans missions from released work orders,
calls tools exposed by `mcp_server/`, supervises execution, and must survive
its own restart mid-mission by resuming from persisted state. The two
realistic frameworks are:

- **Pydantic AI** — typed tools and outputs on top of Pydantic v2 models,
  a straightforward first-party MCP client.
- **LangGraph** — an explicit state-graph model with a built-in checkpointer
  designed for exactly this kind of pause/resume/long-running agent.

## Decision

Use **Pydantic AI**.

Reasoning:

- The `Mission` schema (section 4.4) and the EAM's work order model are
  already Pydantic v2 models; typed tool signatures over the same models
  keep the agent, the router, and the MCP tool layer speaking one type
  system end to end, with mypy able to check across the boundary.
- MCP client support is native, matching the section 4.3 requirement that
  the agent only reach the router and EAM through `mcp_server/`, never by
  calling adapters directly.
- Smaller surface area. In a live technical walkthrough, "here is the typed
  tool, here is the model call behind one interface" is easier to defend
  line by line than a state graph with its own execution model layered on
  top.

## Consequences

- Mid-mission resume-on-restart (section 4.3) has to be built by hand:
  persist mission state explicitly (e.g. to the same SQLite store the EAM
  uses, or a dedicated table) and reload it on startup, rather than getting
  a checkpointer for free. This is a known gap against what LangGraph would
  give out of the box.
- If that hand-rolled persistence turns out to be awkward or fragile once
  step 6 (CLAUDE.md section 6) is actually being built, switching to
  LangGraph for its checkpointer is the documented escape hatch — record
  that as a new ADR if it happens, don't swap silently.
- The model call itself (Anthropic Claude via the provider-native SDK) is
  kept behind one interface regardless of which agent framework wraps it,
  so this decision does not lock in a model vendor.
