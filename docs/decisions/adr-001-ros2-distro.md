# ADR-001: ROS 2 distro and simulator for the VDA 5050 AMR adapter

## Status

Accepted

## Context

`adapters/vda5050_amr/` (CLAUDE.md section 4.5) needs a ROS 2 distro and a
simulator, pinned up front so every later step (Nav2 config, the VDA 5050
bridge node, the headless CI test) targets one target instead of drifting.

The realistic choices are:

- **ROS 2 Humble Hawksbill** (Ubuntu 22.04, supported to May 2027) with
  **Gazebo Classic** (the historically dominant pairing; most existing
  TurtleBot3 tutorials assume this combination).
- **ROS 2 Jazzy Jalisco** (Ubuntu 24.04, supported to May 2029) with
  **Gazebo Harmonic** (the actively developed "new Gazebo", an LTS release
  supported to 2028).

Gazebo Classic was end-of-lifed by Open Robotics in January 2025 and is not
receiving further feature work. Building a new project against it in 2026
would mean starting on a simulator whose upstream is already frozen.

## Decision

Use **ROS 2 Jazzy Jalisco with Gazebo Harmonic**.

Reasoning:

- Longer support runway (to 2029) matters less for a few-week demo than the
  fact that Gazebo Harmonic is the simulator still receiving fixes; Classic
  is a dead end to build fresh code against.
- Nav2 and the TurtleBot family both have active Jazzy/Harmonic support.

## Consequences

- TurtleBot3's own simulation packages have historically targeted Gazebo
  Classic; the tutorials and launch files are more mature there than on
  Harmonic. If TurtleBot3-on-Harmonic proves too rough in practice, the
  fallback is **TurtleBot4**, which targets Jazzy/Harmonic natively — this
  would be a documented, deliberate swap, not a silent one, and would be
  recorded as a follow-up ADR if it happens.
- All ROS 2 tooling, base images, and CI steps for this adapter are pinned
  to Jazzy. The Unitree adapter (ADR is not needed there — it does not use
  ROS 2 at all, and is explicitly kept out of any ROS 2 container per
  CLAUDE.md section 4.5) is unaffected.
