from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_tourist_sites() -> None:
    response = client.get("/api/tourist-sites")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 20
    assert any(item["city"] == "Yaoundé" for item in body["items"])


def test_get_tourist_site() -> None:
    response = client.get("/api/tourist-sites/site-010")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Mont Cameroun"
    assert body["latitude"] is None
    assert body["sources"]


def test_nearby_by_city() -> None:
    response = client.get("/api/tourist-sites/nearby", params={"city": "Kribi"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert all("Kribi" in item["city"] for item in body["items"])
