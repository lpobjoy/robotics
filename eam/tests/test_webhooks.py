from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import httpx
from eam.models import MissionCapability, WebhookSubscription, WorkOrder, WorkOrderStatus
from eam.webhooks import notify_work_order_released
from fastapi.testclient import TestClient


def _work_order(status: WorkOrderStatus = WorkOrderStatus.RELEASED) -> WorkOrder:
    now = datetime.now(UTC)
    return WorkOrder(
        id=1,
        title="Test",
        asset_id=1,
        required_capabilities=[MissionCapability.PATROL],
        status=status,
        created_at=now,
        updated_at=now,
    )


def test_notify_posts_to_every_subscription() -> None:
    subscriptions = [
        WebhookSubscription(id=1, url="http://a.invalid/hook", created_at=datetime.now(UTC)),
        WebhookSubscription(id=2, url="http://b.invalid/hook", created_at=datetime.now(UTC)),
    ]
    with patch("eam.webhooks.httpx.post") as mock_post:
        notify_work_order_released(subscriptions, _work_order())

    assert mock_post.call_count == 2
    called_urls = {call.args[0] for call in mock_post.call_args_list}
    assert called_urls == {"http://a.invalid/hook", "http://b.invalid/hook"}


def test_notify_is_a_noop_with_no_subscriptions() -> None:
    with patch("eam.webhooks.httpx.post") as mock_post:
        notify_work_order_released([], _work_order())
    mock_post.assert_not_called()


def test_notify_swallows_delivery_failures() -> None:
    subscriptions = [
        WebhookSubscription(id=1, url="http://a.invalid/hook", created_at=datetime.now(UTC))
    ]
    with patch("eam.webhooks.httpx.post", side_effect=httpx.ConnectError("boom")):
        notify_work_order_released(subscriptions, _work_order())  # must not raise


def test_webhook_fires_when_work_order_is_released(client: TestClient) -> None:
    calls: list[Any] = []
    with patch("eam.api_rest.notify_work_order_released", lambda *args: calls.append(args)):
        client.post("/api/webhooks", json={"url": "http://example.invalid/hook"})
        work_order_id = client.get("/api/work-orders", params={"status": "Draft"}).json()[0]["id"]
        response = client.patch(
            f"/api/work-orders/{work_order_id}/status", json={"status": "Released"}
        )

    assert response.status_code == 200
    assert len(calls) == 1
    subscriptions, work_order = calls[0]
    assert len(subscriptions) == 1
    assert work_order.status == WorkOrderStatus.RELEASED


def test_webhook_does_not_fire_for_other_transitions(client: TestClient) -> None:
    calls: list[Any] = []
    with patch("eam.api_rest.notify_work_order_released", lambda *args: calls.append(args)):
        work_order_id = client.get("/api/work-orders", params={"status": "Draft"}).json()[0]["id"]
        client.patch(f"/api/work-orders/{work_order_id}/status", json={"status": "Cancelled"})

    assert calls == []
