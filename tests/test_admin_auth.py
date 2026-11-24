from fastapi.testclient import TestClient

from app.main import app


def test_health_is_public_without_admin_credentials(monkeypatch):
    monkeypatch.delenv("TORRES_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("TORRES_ADMIN_PASSWORD", raising=False)

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200


def test_admin_docs_returns_503_when_credentials_are_not_configured(monkeypatch):
    monkeypatch.delenv("TORRES_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("TORRES_ADMIN_PASSWORD", raising=False)

    client = TestClient(app)
    response = client.get("/docs")

    assert response.status_code == 503


def test_admin_docs_rejects_missing_credentials(monkeypatch):
    monkeypatch.setenv("TORRES_ADMIN_USERNAME", "admin-test")
    monkeypatch.setenv("TORRES_ADMIN_PASSWORD", "password-test")

    client = TestClient(app)
    response = client.get("/docs")

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_admin_docs_rejects_wrong_credentials(monkeypatch):
    monkeypatch.setenv("TORRES_ADMIN_USERNAME", "admin-test")
    monkeypatch.setenv("TORRES_ADMIN_PASSWORD", "password-test")

    client = TestClient(app)
    response = client.get("/docs", auth=("admin-test", "wrong-password"))

    assert response.status_code == 401


def test_admin_docs_accepts_valid_credentials(monkeypatch):
    monkeypatch.setenv("TORRES_ADMIN_USERNAME", "admin-test")
    monkeypatch.setenv("TORRES_ADMIN_PASSWORD", "password-test")

    client = TestClient(app)
    response = client.get("/docs", auth=("admin-test", "password-test"))

    assert response.status_code == 200
