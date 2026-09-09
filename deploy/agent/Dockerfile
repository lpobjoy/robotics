# Builds the mission agent's manual CLI trigger (agent/__main__.py --
# see its module docstring for why this is manual, not an automatic
# poller/webhook receiver). Meant to run as a Kubernetes Job per work
# order (deploy/k3d/agent-job.yaml), not a long-running Deployment.
FROM python:3.11-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY . .

RUN uv sync --frozen --no-dev --package agent

ENTRYPOINT ["uv", "run", "--no-dev", "--package", "agent", "python", "-m", "agent"]
