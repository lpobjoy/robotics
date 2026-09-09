"""Manual CLI trigger: `uv run python -m agent <work_order_id>`.

Said plainly: this is the whole "wiring" that exists for running the
agent outside a test. There is no polling loop or webhook receiver that
picks up a released work order automatically -- eam/webhooks.py can
notify a subscriber URL when a work order is released, but nothing in
this repo subscribes to it. A real deployment would need one of those;
neither is built here. For this demo, releasing a work order in the
console and then running this command against its id is the reproduction
step (see deploy/k3d/README.md and the root README's "Running it").

Reads EAM_BASE_URL, AGENT_MODEL (see model_config.py), and
MISSION_STATE_DB_PATH (default "agent_state.db") from the environment.
Needs ANTHROPIC_API_KEY set to actually call Claude.
"""

from __future__ import annotations

import asyncio
import os
import sys

from agent.mission_agent import EscalatedError, build_mission_agent
from agent.state import MissionStateStore


async def _main(work_order_id: int) -> None:
    state_store = MissionStateStore(os.environ.get("MISSION_STATE_DB_PATH", "agent_state.db"))
    mission_agent = build_mission_agent(
        state_store, eam_base_url=os.environ.get("EAM_BASE_URL")
    )
    try:
        result = await mission_agent.process_released_work_order(work_order_id)
        print(result)
    except EscalatedError as exc:
        print(exc)
    finally:
        state_store.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m agent <work_order_id>", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(_main(int(sys.argv[1])))
