"""Configuración y health check de la aplicación (CF1-01)."""

from fastapi.testclient import TestClient

from cuentafaro.api import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["base_currency"] == "CLP"
    assert payload["timezone"] == "America/Santiago"


def test_unknown_route_returns_404() -> None:
    client = TestClient(create_app())
    assert client.get("/no-existe").status_code == 404
