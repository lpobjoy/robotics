# Foundation models

CLAUDE.md section 4.10: what VLA (vision-language-action) and
"omni" multimodal models change about the integration surface over the
next 2-3 years. Written from having just built the integration surface
this would change — not built, no VLA model runs anywhere in this
repo.

## The part of this architecture a VLA model doesn't touch

`eam/`, `worldmodel/`, `router/`, `audit/`, `identity/` — the business
system, the graph, the dispatch/selection logic, the audit trail,
machine identity — are all about *which robot does the work and who's
accountable for the decision*. A foundation model that can turn "walk
to the pump and check for leaks" directly into joint torques doesn't
change any of that. If anything it raises the stakes on it: the better
the model is at silently doing something plausible-but-wrong, the more
this layer's job (constrain what's dispatched, log every decision,
require a human sign-off on uncertainty) matters, not less. This
repo's honesty rule — never claim an adapter does more than it proves —
gets harder to hold to, not easier, once the thing on the other end of
the adapter is a model with no interpretable failure mode.

## The part that does change: what a "Mission" is

This repo's `Mission` schema (`router/models.py`) is deliberately
rigid: a `type` from a closed enum (`inspect_visual`, `inspect_thermal`,
`patrol`), a list of target locations, a list of required capabilities.
That rigidity is what makes `qualify_robots_for_work_order`
(`worldmodel/query.py`) a simple, explainable, testable graph query —
capability match, then availability, then distance. It's also exactly
the kind of interface a capable-enough VLA/omni model starts to make
optional. A model that can take "the pump on the east wall looks like
it might be leaking, go check" as input — free text, maybe a reference
photo, no enum required — and turn that into a sequence of actions on
whichever embodiment it's deployed on doesn't need `required_capabilities`
pre-declared by a human filling out a work order template; it can
reason about what capability the task needs at dispatch time.

The integration-surface consequence: `worldmodel`'s job shifts from
"answer a structured qualify-robots query" to "supply grounding context
to a model that's doing the qualifying reasoning itself" — the graph
stays valuable (a model still benefits enormously from being told what
locations, assets, and robots exist and how they're connected, rather
than inferring a site's topology from scratch), but the *query* against
it stops being a fixed function and starts being closer to a
retrieval step feeding a prompt. The `Mission` schema this repo uses as
the router's contract would need a genuinely unstructured field (free
text goal, reference image, whatever the model needs) that a human
work order almost never provides today.

## The part that changes further out: where the model runs

Everything in this repo assumes the "brain" — the agent — runs off the
robot, talking to it through an adapter over a network protocol
(MQTT, DDS, gRPC). A capable-enough on-device VLA model collapses part
of that: the robot's own onboard compute does perception-to-action
directly, and what's left for a system like this one to do is closer
to *fleet-level* coordination — which robot goes where, in what order,
with what priority — rather than *task-level* instruction. `router/`'s
job (capability match, availability, distance, audit-before-dispatch)
is actually the part of this architecture best positioned for that
future: it was already written to treat "how the robot executes the
mission" as none of its business, on purpose (that's the whole point of
the `FleetAdapter` protocol boundary). What would need to change is the
*content* of what gets dispatched — from "go to these coordinates and
run this named action" to something closer to "here's the goal and the
context, you figure out the plan" — and what `status()` means, since
"in progress" stops being inferable from simple telemetry fields like
`driving` or `position` and starts requiring the model (or a
supervisor watching it) to self-report confidence and progress in a
way this repo's `MissionStatusReport` (a closed status enum plus a
free-text detail string) would need to grow real structure for.

## Where this repo's own gaps would bite hardest

Two things built in this repo would need to change first if a VLA
model were dropped into it:

- **`Mission.required_capabilities`** would need to become optional or
  advisory rather than required — the whole qualify-then-dispatch flow
  in `worldmodel/query.py` and `router/router.py` assumes it's known
  up front.
- **Escalation triggers** (CLAUDE.md section 4.7: low confidence,
  capability mismatch discovered mid-mission, connectivity loss,
  safety-relevant adapter errors) would need a genuine "the model isn't
  sure" signal to key off, not just protocol-level failures — this
  repo's escalation paths (`adapter.py`'s connectivity-loss detection,
  `mcp_server/tools.py`'s `escalate_to_human`) are all triggered by
  concrete, structured failures today, precisely because there's no
  model in the loop whose own uncertainty could be the trigger instead.
