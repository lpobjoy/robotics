"""Proves the MCP server actually speaks MCP: real stdio subprocess,
real JSON-RPC round trip. Separate from test_tools.py, which tests
MissionTools directly and never touches the MCP transport.

Needs a real, network-bound EAM (the subprocess can't share this
process's in-memory TestClient), so this spins up a real uvicorn server
in a background thread for the test's lifetime.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn
from eam.app import create_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def running_eam() -> Iterator[str]:
    port = _free_port()
    app = create_app(db_path=":memory:", seed=True)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            httpx.get(f"{base_url}/api/locations", timeout=0.2)
            break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        raise RuntimeError("eam did not start in time")

    yield base_url

    server.should_exit = True
    thread.join(timeout=5.0)


@pytest.mark.anyio
async def test_mcp_server_lists_the_expected_tools_over_real_stdio(running_eam: str) -> None:
    from pydantic_ai.mcp import FastMCPClient, StdioTransport

    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "mcp_server"],
        env={"EAM_BASE_URL": running_eam},
    )
    client = FastMCPClient(transport=transport)

    async with client:
        tools = await client.list_tools()

    tool_names = {tool.name for tool in tools}
    assert tool_names == {
        "list_released_work_orders",
        "get_work_order",
        "qualify_robots",
        "dispatch_mission",
        "get_mission_status",
        "mark_in_progress",
        "mark_completed",
        "mark_failed",
        "escalate_to_human",
        "abort_mission",
        "advance_fake_mission",
    }


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
