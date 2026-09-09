# ADR-006: Keeping the Unitree adapter out of the main uv workspace

## Status

Accepted

## Context

CLAUDE.md section 4.5 pins `unitree_sdk2_python` for the Unitree adapter's
Half A (`BUILT_AGAINST_SDK_TESTED_WITH_FAKE`), and says outright: "Keep
this adapter in its own container. `unitree_sdk2py` pins CycloneDDS
0.10.2 and clashes with ROS 2's build; never install both in one image."

`unitree_sdk2py` itself is pip-installable (from its GitHub repo -- it
isn't on PyPI), but its `cyclonedds==0.10.2` pin is not: there's no
prebuilt wheel for this platform, so `pip`/`uv` tries to build it from
source, which fails immediately with "Could not locate cyclonedds" --
the Python bindings need the CycloneDDS *C library* already built and
pointed to via `CYCLONEDDS_HOME` first. That was confirmed directly:
building CycloneDDS 0.10.x from source with `cmake` (a few minutes) and
setting `CYCLONEDDS_HOME` makes the wheel build succeed, and a real
DDS pub/sub round trip over loopback (domain 0, no physical network
interface) works on this laptop.

The question this ADR answers isn't "does it work" -- it does -- it's
"where does it belong." `adapters/unitree` is currently a member of the
root uv workspace, which means one shared lockfile and one shared
`.venv` for every package in the repo. Adding `unitree_sdk2py` and
`cyclonedds` there would mean:

- Every contributor and every CI job running `uv sync`/`uv run` for
  *any* reason -- linting `router`, testing `eam`, anything -- now needs
  a working C toolchain and a pre-built CycloneDDS on their machine,
  whether or not they touch the Unitree adapter.
- The exact clash CLAUDE.md warns about (CycloneDDS vs. ROS 2's own DDS
  stack) becomes a live risk the moment anyone tries to add ROS 2
  Python packages to the same shared venv later, instead of a
  contained, already-isolated one.

This is the same shape of problem `adapters/vda5050_amr/ros2_bridge/`
already solved for `rclpy`: that package is a real ROS 2 ament_python
package, deliberately kept *outside* the uv workspace (see ADR-005),
tested only inside its own Docker container, because `rclpy` isn't
pip-installable into a normal venv at all. `unitree_sdk2py` differs in
one detail -- it *is* pip-installable, given the native library -- but
the practical conclusion is the same: it doesn't belong in the shared
environment.

## Decision

`adapters/unitree` is removed from `[tool.uv.workspace] members` in the
root `pyproject.toml` and becomes its own standalone `uv` project: its
own `pyproject.toml`, its own lockfile, its own `.venv`, created with
`cd adapters/unitree && uv sync`. Root's `uv run pytest` explicitly
ignores it (`--ignore=adapters/unitree`); its tests run with
`cd adapters/unitree && uv run pytest` instead. See
`adapters/unitree/README.md` for the one-time CycloneDDS build step this
requires locally, and `.github/workflows/ci.yml` for the same steps run
in CI as their own job.

This is one step lighter than `ros2_bridge`'s isolation: Half A's tests
*are* runnable outside a container (there's no `rclpy`-style hard wall),
just not inside the shared workspace venv. Docker is still where the
adapter is deployed (`deploy/unitree/Dockerfile`, once step 13 lands
it) -- this ADR is about local dev and CI tooling, not the deployment
target.

## Consequences

- `uv sync --all-packages --all-groups` at the repo root no longer
  touches the Unitree adapter at all -- it has nothing to do with
  whether that adapter's own tests pass.
- A new CI job builds CycloneDDS from source and runs
  `adapters/unitree`'s own test suite separately from the main
  lint/type-check/test job.
- If Half B (`unitree_mujoco` sim2sim) turns out to need a similarly
  heavy, separate environment -- likely, given MuJoCo and
  `unitree_rl_gym` are both sizeable -- it gets the same treatment
  rather than being forced into this same standalone project by
  default; that's a decision for when Half B is actually built.
