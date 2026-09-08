# Builds just the eam service, but from the full workspace context --
# uv needs the root pyproject.toml/uv.lock and every workspace member's
# pyproject.toml to resolve the lockfile, even though only eam's own code
# ends up running. See CLAUDE.md section 4.9: one image per component.
FROM python:3.11-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY . .

RUN uv sync --frozen --no-dev --package eam

# Railway assigns $PORT at runtime; fall back to 8000 for local `docker run`.
# EAM_DB_PATH defaults to a container-local file -- there is no persistent
# volume here, so a redeploy starts from a fresh, reseeded database. That is
# a feature for a demo, not a bug: see eam/seed.py.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uv run --no-dev --package eam uvicorn eam.app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
