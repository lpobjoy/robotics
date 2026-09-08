from __future__ import annotations

from fastapi.testclient import TestClient


def test_metadata(client: TestClient) -> None:
    response = client.get("/odata/v4/$metadata")
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert '<EntitySet Name="WorkOrders"' in response.text


def test_collection_envelope(client: TestClient) -> None:
    response = client.get("/odata/v4/WorkOrders")
    assert response.status_code == 200
    body = response.json()
    assert body["@odata.context"].endswith("/odata/v4/$metadata#WorkOrders")
    assert len(body["value"]) == 5


def test_single_entity_by_key(client: TestClient) -> None:
    work_order_id = client.get("/odata/v4/WorkOrders").json()["value"][0]["id"]
    response = client.get(f"/odata/v4/WorkOrders({work_order_id})")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == work_order_id
    assert body["@odata.context"].endswith("/odata/v4/$metadata#WorkOrders/$entity")


def test_single_entity_not_found(client: TestClient) -> None:
    response = client.get("/odata/v4/WorkOrders(99999)")
    assert response.status_code == 404


def test_top_and_skip(client: TestClient) -> None:
    response = client.get("/odata/v4/Assets", params={"$top": 5, "$skip": 2})
    assert len(response.json()["value"]) == 5


def test_select(client: TestClient) -> None:
    response = client.get("/odata/v4/Assets", params={"$select": "id,name", "$top": 1})
    item = response.json()["value"][0]
    assert set(item.keys()) == {"id", "name"}


def test_filter_equality(client: TestClient) -> None:
    response = client.get("/odata/v4/Assets", params={"$filter": "asset_type eq pump"})
    body = response.json()
    assert len(body["value"]) > 0
    assert all(item["asset_type"] == "pump" for item in body["value"])


def test_filter_on_capability_list(client: TestClient) -> None:
    response = client.get(
        "/odata/v4/Robots", params={"$filter": "capabilities eq inspect_thermal"}
    )
    body = response.json()
    assert len(body["value"]) == 2
    assert all("inspect_thermal" in item["capabilities"] for item in body["value"])


def test_unsupported_filter_expression_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/odata/v4/Assets", params={"$filter": "asset_type contains pump"}
    )
    assert response.status_code == 400
