import importlib
import sys

from starlette.testclient import TestClient


def test_home_and_admin_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "app.sqlite3"))
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    app_module = importlib.reload(sys.modules["app"]) if "app" in sys.modules else importlib.import_module("app")
    client = TestClient(app_module.app)
    home = client.get("/")
    assert home.status_code == 200
    assert "Adagio" in home.text
    admin = client.get("/admin?key=secret")
    assert admin.status_code == 200
    assert "participants" in admin.text.lower()


def test_participant_route_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "participant.sqlite3"))
    app_module = importlib.reload(sys.modules["app"]) if "app" in sys.modules else importlib.import_module("app")
    with app_module.conn() as c:
        token = app_module.db.create_participant(c, "Grace")
    client = TestClient(app_module.app)
    response = client.get(f"/p/{token}")
    assert response.status_code == 200
    assert "Grace" in response.text
