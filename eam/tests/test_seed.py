from __future__ import annotations

from eam.app import create_app
from eam.models import WorkOrderStatus
from eam.seed import seed_if_empty


def test_seed_counts() -> None:
    app = create_app(db_path=":memory:", seed=True)
    db = app.state.db
    assert len(db.list_locations()) == 7
    assert len(db.list_assets()) == 20
    assert len(db.list_robots()) == 3
    assert len(db.list_work_orders()) == 5


def test_seed_has_a_draft_and_a_completed_work_order() -> None:
    app = create_app(db_path=":memory:", seed=True)
    statuses = {wo.status for wo in app.state.db.list_work_orders()}
    assert WorkOrderStatus.DRAFT in statuses
    assert WorkOrderStatus.COMPLETED in statuses


def test_seed_is_idempotent() -> None:
    app = create_app(db_path=":memory:", seed=True)
    seed_if_empty(app.state.db)
    assert len(app.state.db.list_assets()) == 20
    assert len(app.state.db.list_work_orders()) == 5


def test_unseeded_app_starts_empty() -> None:
    app = create_app(db_path=":memory:", seed=False)
    assert app.state.db.list_locations() == []


def test_asset_and_robot_capabilities_use_the_same_vocabulary() -> None:
    """The whole point of seeding both from the same MissionCapability enum
    is that a released work order's required_capabilities can be matched
    against a robot's capabilities directly (worldmodel, step 3)."""
    app = create_app(db_path=":memory:", seed=True)
    db = app.state.db

    robot_capabilities = {c for robot in db.list_robots() for c in robot.capabilities}
    required_capabilities = {c for wo in db.list_work_orders() for c in wo.required_capabilities}

    assert required_capabilities <= robot_capabilities
