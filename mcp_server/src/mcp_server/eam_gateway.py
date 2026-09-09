"""HTTP gateway to the EAM's REST API for the mutations a mission's
lifecycle needs (status transitions). Separate from
worldmodel.client.EamClient, which is read-only and exists to build the
world-model graph.
"""

from __future__ import annotations

from typing import Any

import httpx
from worldmodel.models import WorkOrder

# See worldmodel.client._InjectedClient: TestClient isn't reliably an
# httpx.Client across this stack's versions, so the injected test double
# is typed Any rather than against a concrete (and possibly wrong) class.
_InjectedClient = Any


class EamGateway:
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

    def list_work_orders(self, status: str | None = None) -> list[WorkOrder]:
        params = {"status": status} if status else {}
        response = self._client.get("/api/work-orders", params=params)
        response.raise_for_status()
        return [WorkOrder.model_validate(item) for item in response.json()]

    def get_work_order(self, work_order_id: int) -> WorkOrder:
        response = self._client.get(f"/api/work-orders/{work_order_id}")
        response.raise_for_status()
        return WorkOrder.model_validate(response.json())

    def set_work_order_status(self, work_order_id: int, status: str) -> WorkOrder:
        response = self._client.patch(
            f"/api/work-orders/{work_order_id}/status", json={"status": status}
        )
        response.raise_for_status()
        return WorkOrder.model_validate(response.json())
