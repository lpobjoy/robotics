# Builds telemetry's MQTT ingestion service (telemetry/service.py):
# subscribes to fleet/<robot_id>/{state,images,events} and writes to its
# own sqlite time-series store, attaching images to the EAM. CLAUDE.md
# section 4.9: one image per component.
FROM python:3.11-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY . .

RUN uv sync --frozen --no-dev --package telemetry

CMD ["uv", "run", "--no-dev", "--package", "telemetry", "python", "-m", "telemetry"]
