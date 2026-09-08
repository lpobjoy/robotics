"""Webhook delivery: fired when a work order moves to Released
(CLAUDE.md section 4.1).
"""

from __future__ import annotations

import logging

import httpx

from eam.models import WebhookEventType, WebhookSubscription, WorkOrder

logger = logging.getLogger(__name__)


def notify_work_order_released(
    subscriptions: list[WebhookSubscription], work_order: WorkOrder
) -> None:
    """Best-effort delivery. A failed delivery is logged and otherwise
    ignored -- there is no retry queue here, this is a demo webhook, not a
    message bus. Callers must not let this raise into the request path.
    """
    if not subscriptions:
        return

    payload = {
        "event": WebhookEventType.WORK_ORDER_RELEASED.value,
        "work_order_id": work_order.id,
        "work_order": work_order.model_dump(mode="json"),
    }

    for subscription in subscriptions:
        try:
            httpx.post(subscription.url, json=payload, timeout=5.0)
        except httpx.HTTPError:
            logger.warning(
                "webhook delivery failed for subscription %s (%s)",
                subscription.id,
                subscription.url,
                exc_info=True,
            )
