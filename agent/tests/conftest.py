"""Agent tests need a real MCP server subprocess (mcp_server spawns via
StdioTransport), which in turn needs a real, network-bound EAM -- there's
no in-process TestClient a subprocess can share. Same pattern as
mcp_server/tests/test_server_stdio.py.
"""

from __future__ import annotations

import socket
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


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
