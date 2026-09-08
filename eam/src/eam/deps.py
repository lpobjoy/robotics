"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from eam.db import Database


def get_db(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


DbDep = Annotated[Database, Depends(get_db)]
