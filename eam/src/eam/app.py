"""FastAPI app factory and the default entrypoint for `uv run` / uvicorn.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from eam.api_odata import router as odata_router
from eam.api_rest import router as rest_router
from eam.db import Database
from eam.seed import seed_if_empty


def create_app(db_path: str | Path = ":memory:", *, seed: bool = True) -> FastAPI:
    app = FastAPI(title="EAM (mock)", version="0.1.0")
    app.state.db = Database(db_path)
    if seed:
        seed_if_empty(app.state.db)
    app.include_router(rest_router)
    app.include_router(odata_router)
    return app


app = create_app(db_path=os.environ.get("EAM_DB_PATH", "eam.db"))
