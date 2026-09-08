# Job spec

Verbatim job description this repo is built against (CLAUDE.md section 1).
Used to build the README requirements table (CLAUDE.md section 8) at
build-sequence step 15.

---

## The role

You will define and build the robotics integration architecture for the IFS suite and grow the engineering team that delivers it. This is a software role. You will not design actuators, motion control, or perception stacks, and hardware experience is not required. What is required is deep, current working knowledge of the software surfaces of the major robot OEM platforms: their SDKs, APIs, fleet managers, autonomy stacks, data models, and their real limitations.

You will also be the engineering counterpart to our robotics ecosystem: OEMs, robotics foundation model companies, startup networks, and standards bodies. When an OEM partner puts their platform engineers in a room, you are the person on our side of the table.

It is a player-coach role in a unit that ships. You will build the first integrations yourself, prove them with real customers and live demos, then scale the capability through the team you hire.

## What you will do

* Own the agent-first integration architecture between the IFS suite and robotics OEM platforms, from reference design to production
* Build the abstraction layer that lets IFS agents and applications treat heterogeneous robot fleets as dispatchable, auditable executors of work
* Deliver working integrations hands-on: work order dispatch to robots, mission and task orchestration, telemetry and inspection data flowing into asset and service records
* Evaluate OEM platforms on engineering merit and steer where IFS invests integration effort; kill weak options early
* Represent IFS in technical engagements with robot OEMs, robotics foundation model providers, and interoperability bodies
* Hire and lead a robotics integration engineering team and set its technical bar
* Ship demonstrable outcomes on real customer scenarios and flagship events, on hard dates
* Brief executives and customers on the robotics roadmap in commercial terms

## Qualifications

### What we are looking for

* 15+ years in software engineering, with several years architecting integration or platform layers used in production at enterprise scale
* Demonstrable working knowledge of at least 2 major robot OEM ecosystems at the SDK and API level: you have built against them, not read about them
* Still keyboard-credible: you prototype, review PRs, and debug integrations. We will verify this in the interview process
* Applied AI capability: production experience with agentic systems, tool use and function calling, and orchestration of long-running autonomous tasks
* Fluency in the operational reality of robots in industrial settings: connectivity, safety interlocks, teleoperation and human-in-the-loop handover, degraded modes, and what actually breaks in deployment
* Experience leading engineering teams and dealing with external partner engineering organisations
* Clear written and spoken communication at executive level; comfortable presenting live demos

### Technical depth expected

We hire for depth per area, not a keyword count. The named platforms and tools are examples; strong equivalents are fine. Expect to be tested on the areas below.

* OEM platforms and SDKs: hands-on integration experience with platforms such as Boston Dynamics (Spot SDK), Agility Robotics, Unitree, ANYbotics, or comparable quadruped, humanoid, AMR, or drone ecosystems; understanding of their mission APIs, fleet managers, autonomy behaviours, and payload and data interfaces
* Robotics middleware and interoperability: ROS 2 (topics, services, actions, DDS) at integration level; fleet interoperability standards such as VDA 5050, the MassRobotics Interoperability Standard, and Open-RMF; where these standards genuinely work and where they fall short
* Agent-first integration: designing AI agents that plan, dispatch, and supervise robot missions; MCP servers and tool interfaces over robot APIs; orchestration frameworks such as LangGraph, Pydantic AI, or provider-native SDKs; permissioning, human-in-the-loop escalation, and audit trails for autonomous physical action
* Robotics foundation models: working awareness of VLA and omni models for robots (for example SkildAI, Physical Intelligence, Nvidia GR00T) and what they change about the integration surface over the next 2 to 3 years
* Industrial data and telemetry: MQTT, OPC UA, and event-driven ingestion of robot telemetry, inspection imagery, and sensor data into enterprise systems; time-series handling at fleet scale
* Simulation and validation: using simulation environments (Isaac Sim, Gazebo, or OEM-native simulators) to validate integrations and demos without waiting on hardware availability
* Enterprise integration: API design and consumption at scale, including REST, OData, GraphQL, and webhook/event patterns into ERP, EAM, and FSM systems; mapping robot missions onto work orders, assets, and service processes
* Languages and platform: expert-level Python and TypeScript; able to read C++ where OEM SDKs demand it; production Kubernetes and containerisation, CI/CD, and edge deployment patterns for on-site connectivity
* Security and safety posture: identity and authorisation for machine actors, network segmentation for OT environments, and the audit and traceability expectations that come with software commanding physical machines

### What sets candidates apart

* Prior work connecting robots or autonomous systems to business systems (ERP, EAM, WMS, MES) rather than to other robots
* Exposure to asset-intensive or field service domains: utilities, manufacturing, aviation, energy, logistics
* Experience in an OEM or fleet management vendor engineering organisation, seen from the inside
* Standards body or interoperability consortium participation
* 0-to-1 experience standing up a new engineering capability inside a larger organisation

## How we assess

A walkthrough of integrations you have personally architected and shipped against real robot platforms, a technical deep dive on your agent-first design approach and how you handle autonomy, safety handover, and auditability, and a working session on a live integration problem. References will be asked specifically about hands-on contribution and OEM engagement, not leadership style.

## Practicalities

* Location and working model: Virtual/Hybrid – location dependent
* Compensation: Upon discussion
* International travel to OEM partners, customers, and flagship events (Europe and US, some Asia)
