from __future__ import annotations

from fastapi.testclient import TestClient


def test_root_is_not_a_dead_end(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["odata_metadata"] == "/odata/v4/$metadata"
    assert body["rest_example"] == "/api/work-orders"


def test_list_locations(client: TestClient) -> None:
    response = client.get("/api/locations")
    assert response.status_code == 200
    assert len(response.json()) == 7


def test_list_assets(client: TestClient) -> None:
    response = client.get("/api/assets")
    assert response.status_code == 200
    assert len(response.json()) == 20


def test_get_asset_404(client: TestClient) -> None:
    response = client.get("/api/assets/99999")
    assert response.status_code == 404


def test_list_robots(client: TestClient) -> None:
    response = client.get("/api/robots")
    assert response.status_code == 200
    ecosystems = {robot["ecosystem"] for robot in response.json()}
    assert ecosystems == {"vda5050_amr", "unitree", "spot"}


def test_list_work_orders_filtered_by_status(client: TestClient) -> None:
    response = client.get("/api/work-orders", params={"status": "Draft"})
    assert response.status_code == 200
    assert all(wo["status"] == "Draft" for wo in response.json())
    assert len(response.json()) == 4


def test_create_work_order(client: TestClient) -> None:
    response = client.post(
        "/api/work-orders",
        json={"title": "Test WO", "asset_id": 1, "required_capabilities": ["inspect_visual"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "Draft"
    assert body["title"] == "Test WO"


def test_create_work_order_rejects_unknown_asset(client: TestClient) -> None:
    response = client.post(
        "/api/work-orders",
        json={"title": "x", "asset_id": 99999, "required_capabilities": ["patrol"]},
    )
    assert response.status_code == 400


def test_create_work_order_requires_at_least_one_capability(client: TestClient) -> None:
    response = client.post(
        "/api/work-orders", json={"title": "x", "asset_id": 1, "required_capabilities": []}
    )
    assert response.status_code == 422


def test_valid_status_transition(client: TestClient) -> None:
    created = client.post(
        "/api/work-orders",
        json={"title": "x", "asset_id": 1, "required_capabilities": ["patrol"]},
    ).json()

    response = client.patch(
        f"/api/work-orders/{created['id']}/status", json={"status": "Released"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Released"


def test_invalid_status_transition_is_rejected(client: TestClient) -> None:
    created = client.post(
        "/api/work-orders",
        json={"title": "x", "asset_id": 1, "required_capabilities": ["patrol"]},
    ).json()
    client.patch(f"/api/work-orders/{created['id']}/status", json={"status": "Released"})

    response = client.patch(
        f"/api/work-orders/{created['id']}/status", json={"status": "Draft"}
    )
    assert response.status_code == 409


def test_status_transition_on_missing_work_order(client: TestClient) -> None:
    response = client.patch("/api/work-orders/99999/status", json={"status": "Released"})
    assert response.status_code == 404


def test_attachment_roundtrip(client: TestClient) -> None:
    work_order_id = client.get("/api/work-orders").json()[0]["id"]

    upload = client.post(
        f"/api/work-orders/{work_order_id}/attachments",
        files={"file": ("photo.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert upload.status_code == 201
    attachment_id = upload.json()["id"]

    listing = client.get(f"/api/work-orders/{work_order_id}/attachments")
    assert len(listing.json()) == 1

    download = client.get(f"/api/attachments/{attachment_id}")
    assert download.status_code == 200
    assert download.content == b"fake-jpeg-bytes"
    assert download.headers["content-type"] == "image/jpeg"


def test_attachment_upload_to_missing_work_order(client: TestClient) -> None:
    response = client.post(
        "/api/work-orders/99999/attachments",
        files={"file": ("photo.jpg", b"x", "image/jpeg")},
    )
    assert response.status_code == 404


def test_download_missing_attachment(client: TestClient) -> None:
    response = client.get("/api/attachments/99999")
    assert response.status_code == 404


def test_create_and_list_webhooks(client: TestClient) -> None:
    response = client.post("/api/webhooks", json={"url": "http://example.invalid/hook"})
    assert response.status_code == 201
    assert response.json()["event_type"] == "work_order.released"

    listing = client.get("/api/webhooks")
    assert len(listing.json()) == 1
