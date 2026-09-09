# Builds mcp_server's HTTP API (the surface the console talks to for
# mission status, the audit trail, and escalation approve/abort -- see
# mcp_server/http_api.py). CLAUDE.md section 4.9: one image per
# component. This is a separate entrypoint from the stdio MCP server the
# agent itself spawns as a subprocess (mcp_server/__main__.py) -- that
# one is never run standalone in a container; the agent starts it.
FROM python:3.11-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY . .

RUN uv sync --frozen --no-dev --package mcp_server

ENV PORT=8001
EXPOSE 8001

CMD ["uv", "run", "--no-dev", "--package", "mcp_server", "python", "-m", "mcp_server.http_api"]
