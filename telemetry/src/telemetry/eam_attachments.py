"""Uploads an inspection image to the EAM as a work order attachment
(CLAUDE.md section 4.6). Wraps the same endpoint eam/api_rest.py exposes
(`POST /api/work-orders/{id}/attachments`); a separate small client
rather than reusing worldmodel.client.EamClient or
mcp_server.eam_gateway.EamGateway, both of which serve different
purposes (read-only graph building; work order status mutation).
"""

from __future__ import annotations

from typing import Any

import httpx

_InjectedClient = Any


class EamAttachmentGateway:
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

    def upload_image(
        self, work_order_id: int, filename: str, content_type: str, data: bytes
    ) -> dict[str, Any]:
        response = self._client.post(
            f"/api/work-orders/{work_order_id}/attachments",
            files={"file": (filename, data, content_type)},
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result
