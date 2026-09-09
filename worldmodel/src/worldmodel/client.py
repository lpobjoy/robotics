"""HTTP client for the EAM's REST API (CLAUDE.md section 4.2: "loaded from
the EAM API"). Talks plain REST, not OData -- this is an internal
consumer, not the dialect-matching surface eam/api_odata.py exists for.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from worldmodel.models import Asset, Location, LocationLink, Robot, WorkOrder

ModelT = TypeVar("ModelT", bound=BaseModel)

# fastapi.testclient.TestClient isn't an httpx.Client in every version of
# this stack -- some builds wrap a separate httpx2.Client instead, and its
# methods' exact keyword-only signatures differ enough that no Protocol
# both is sound and matches real httpx.Client too. `client` is typed Any:
# it only ever holds an httpx.Client (default, real usage) or a test
# double (TestClient) that duck-types get()/close() the same way.
_InjectedClient = Any


class EamClient:
    def __init__(
        self, base_url: str = "http://localhost:8000", *, client: _InjectedClient | None = None
    ) -> None:
        self._client: _InjectedClient = (
            client if client is not None else httpx.Client(base_url=base_url)
        )
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> EamClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def list_locations(self) -> list[Location]:
        return self._get_list("/api/locations", Location)

    def list_location_links(self) -> list[LocationLink]:
        return self._get_list("/api/location-links", LocationLink)

    def list_assets(self) -> list[Asset]:
        return self._get_list("/api/assets", Asset)

    def list_robots(self) -> list[Robot]:
        return self._get_list("/api/robots", Robot)

    def list_work_orders(self) -> list[WorkOrder]:
        return self._get_list("/api/work-orders", WorkOrder)

    def get_work_order(self, work_order_id: int) -> WorkOrder:
        response = self._client.get(f"/api/work-orders/{work_order_id}")
        response.raise_for_status()
        return WorkOrder.model_validate(response.json())

    def _get_list(self, path: str, model: type[ModelT]) -> list[ModelT]:
        response = self._client.get(path)
        response.raise_for_status()
        return [model.model_validate(item) for item in response.json()]
