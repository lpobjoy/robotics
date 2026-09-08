from __future__ import annotations

import pytest
from eam.app import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    app = create_app(db_path=":memory:", seed=True)
    return TestClient(app)


@pytest.fixture
def unseeded_client() -> TestClient:
    app = create_app(db_path=":memory:", seed=False)
    return TestClient(app)
