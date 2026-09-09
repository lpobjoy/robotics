# Standards: VDA 5050 vs Open-RMF vs MassRobotics

CLAUDE.md section 4.10: written after actually building against VDA
5050 (`adapters/vda5050_amr/`, step 7), not secondhand. The VDA 5050
section below is from direct implementation experience — the topic
scheme, the message shapes, the parts of the spec this repo
deliberately didn't implement, and the one real bug that cost real
debugging time. Open-RMF and MassRobotics are described from reading
their specs and source, not from building against them; said plainly,
because it would be easy to blur that distinction and this document
shouldn't.

## VDA 5050 — built against it

VDA 5050 is a message-level protocol, not a framework: it defines a
topic naming scheme (`uagv/v2/<manufacturer>/<serialNumber>/<topic>`)
and JSON message shapes for six topics (`order`, `instantActions`,
`state`, `visualization`, `connection`, `factsheet`), and says nothing
about transport beyond "MQTT," nothing about how a fleet manager picks
which robot gets which order, and nothing about multi-vendor traffic
coexistence. That narrowness is exactly what made it tractable to build
a real, protocol-correct adapter (`adapters/vda5050_amr/src/vda5050_amr/`)
against a real broker in a few days: there's no framework to stand up,
just messages to serialize correctly and a state machine to drive from
what comes back.

What this repo actually implements, and what it deliberately doesn't
(`adapters/vda5050_amr/README.md`'s "Not covered" has the full list):
`Header`, `Order`/`Node`/`Edge`/`Action` (enough to send a sequence of
waypoints with one inspection action at the end), `InstantActions`,
`State`, `Visualization`, `Connection`. Not built: zone sets, multi-map
support, the full action-parameter-type system, or `factsheet` (a
robot's static capability advertisement — this repo gets that
information from the EAM's own robot records instead, since there's
only ever one of each robot in the seed data). None of what's skipped
is because it's hard; it's because this repo's one simulated site with
three named robots never needed it, and CLAUDE.md's own preference —
small working thing over large half-working thing — says not to build
it speculatively.

The one real bug worth recording because it's a good illustration of
how a protocol spec and a Python library's defaults can disagree in a
way that only shows up at the boundary: `Field(serialization_alias=...)`
only affects `model_dump(by_alias=True)` (Python → JSON, the direction
this repo's own outgoing messages needed), not `model_validate()` (JSON
→ Python, the direction incoming messages from the "robot" side of a
test needed). Every incoming camelCase VDA 5050 message failed
validation with "field required" until this was caught — fixed
globally with `alias=` (both directions) plus `populate_by_name=True`.
The lesson generalizes past this one spec: a protocol built around one
casing convention (camelCase, per VDA 5050's own JSON examples) meeting
a language ecosystem built around another (snake_case, idiomatic
Python) is a real seam, not a detail, and it bites exactly where you'd
expect — the deserialization path, which is easy to under-test if all
your hand-written tests only ever serialize outward.

Where VDA 5050 falls short for this repo's actual architecture: it has
**no concept of a fleet manager choosing between robots** — it assumes
a master control system (this repo's `router/`) already decided who
gets the order, and everything downstream of that decision is what the
spec covers. That's a reasonable division of labor, and it's exactly
where this repo's own layering (`router` decides, the adapter executes)
lines up with the spec's own boundary — but it means VDA 5050 alone
gives you zero help with the actual dispatch problem section 4.4 is
about. It's a wire protocol for the "L3" boundary in this repo's
architecture, not an answer to "which robot."

## Open-RMF — read, not built against

Open-RMF (Open Robotics' Robotics Middleware Framework) solves a
different, harder problem than VDA 5050: multiple *different vendors'*
fleets sharing the *same physical space* — traffic negotiation between
robots that don't speak to each other directly, lift/door coordination,
and a "fleet adapter" concept per vendor that is genuinely similar in
shape to this repo's `FleetAdapter` protocol. The similarity is not a
coincidence — it's the natural shape for this kind of integration
problem, and seeing that shape appear independently in this repo's own
design is a reasonable sanity check that the design is on the right
track. The real difference is scope and weight: Open-RMF is a full
ROS 2-native middleware deployment (its own scheduler, its own traffic
negotiation service, its own map format) built for the
multi-fleet-coexistence problem specifically, where VDA 5050 is a
narrow message contract that says nothing about coexistence at all —
if two VDA-5050-speaking AMRs from different vendors need to not
collide in a shared aisle, VDA 5050 itself has nothing to say about
that; it's the fleet manager's problem, same as dispatch is. Where
Open-RMF would actually earn its much larger footprint over this
repo's `router/` is exactly that multi-fleet traffic problem — this
demo has one router deciding among robots it fully controls, never
multiple independently-operated fleets sharing a site.

## MassRobotics AMR Interoperability Standard — read, not built against

Narrower again than VDA 5050: MassRobotics' standard is aimed
specifically at basic coexistence safety in a mixed-vendor warehouse —
robots broadcasting their position/velocity/status so *other* vendors'
AMRs and site infrastructure can avoid them, not full order execution.
It's the piece of the problem closest to "don't hit each other," where
VDA 5050 is closer to "here's your job, do it, tell me how it went."
The two aren't really competitors; a real multi-vendor site with tight
space could plausibly want both — MassRobotics-style broadcast for
safety/coexistence, VDA 5050 (or an equivalent order-execution
protocol) per vendor for actually assigning work. Neither replaces
what `router/` does in this repo (choosing which robot gets which
mission); both sit at a lower layer than that decision.

## Where each one would actually fit if this became a real product

VDA 5050 (or something shaped like it) stays the right choice for the
AMR order-execution boundary specifically — it's what this repo
already uses there. A second fleet class on the same site that isn't
speaking a vendor SDK directly (the way `adapters/unitree` and
`adapters/spot` do here) would be the natural candidate for it too.
Open-RMF becomes worth its weight the moment there's more than one
*independently operated* fleet sharing physical space — a scenario this
repo's single-router, single-operator model doesn't have and doesn't
claim to solve. MassRobotics' broadcast layer is cheap insurance
underneath either of those the moment robots from different vendors
share an aisle, a dock, or a lift — again, not a scenario this repo's
one simulated site actually creates.
