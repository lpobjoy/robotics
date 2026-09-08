from __future__ import annotations

import pytest
from eam.models import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    WorkOrderStatus,
    is_transition_allowed,
)


@pytest.mark.parametrize(
    ("current", "target", "allowed"),
    [
        (WorkOrderStatus.DRAFT, WorkOrderStatus.RELEASED, True),
        (WorkOrderStatus.DRAFT, WorkOrderStatus.CANCELLED, True),
        (WorkOrderStatus.DRAFT, WorkOrderStatus.DISPATCHED, False),
        (WorkOrderStatus.DRAFT, WorkOrderStatus.COMPLETED, False),
        (WorkOrderStatus.RELEASED, WorkOrderStatus.DISPATCHED, True),
        (WorkOrderStatus.RELEASED, WorkOrderStatus.DRAFT, False),
        (WorkOrderStatus.DISPATCHED, WorkOrderStatus.IN_PROGRESS, True),
        (WorkOrderStatus.DISPATCHED, WorkOrderStatus.COMPLETED, False),
        (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.AWAITING_HUMAN, True),
        (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED, True),
        (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.FAILED, True),
        (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED, True),
        (WorkOrderStatus.AWAITING_HUMAN, WorkOrderStatus.IN_PROGRESS, True),
        (WorkOrderStatus.AWAITING_HUMAN, WorkOrderStatus.FAILED, True),
        (WorkOrderStatus.AWAITING_HUMAN, WorkOrderStatus.RELEASED, False),
        (WorkOrderStatus.COMPLETED, WorkOrderStatus.IN_PROGRESS, False),
        (WorkOrderStatus.FAILED, WorkOrderStatus.CANCELLED, False),
        (WorkOrderStatus.CANCELLED, WorkOrderStatus.DRAFT, False),
    ],
)
def test_transition_matrix(
    current: WorkOrderStatus, target: WorkOrderStatus, allowed: bool
) -> None:
    assert is_transition_allowed(current, target) is allowed


def test_terminal_statuses_allow_nothing() -> None:
    for status in TERMINAL_STATUSES:
        assert ALLOWED_TRANSITIONS[status] == frozenset()
