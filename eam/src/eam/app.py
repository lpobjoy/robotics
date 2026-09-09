"""FastAPI app factory and the default entrypoint for `uv run` / uvicorn.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eam.api_odata import router as odata_router
from eam.api_rest import router as rest_router
from eam.db import Database
from eam.seed import seed_if_empty

CONSOLE_ORIGIN = os.environ.get("CONSOLE_ORIGIN", "http://localhost:5173")


def create_app(db_path: str | Path = ":memory:", *, seed: bool = True) -> FastAPI:
    app = FastAPI(title="EAM (mock)", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[CONSOLE_ORIGIN],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )
    app.state.db = Database(db_path)
    if seed:
        seed_if_empty(app.state.db)
    app.include_router(rest_router)
    app.include_router(odata_router)

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "eam (mock)",
            "note": "Mock EAM business system -- see CLAUDE.md section 4.1. Not a real product.",
            "docs": "/docs",
            "rest_example": "/api/work-orders",
            "odata_metadata": "/odata/v4/$metadata",
            "odata_example": "/odata/v4/WorkOrders",
        }

    return app


app = create_app(db_path=os.environ.get("EAM_DB_PATH", "eam.db"))
