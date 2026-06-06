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


def test_group_prediction_form_hides_advancer(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "group-form.sqlite3"))
    app_module = importlib.reload(sys.modules["app"]) if "app" in sys.modules else importlib.import_module("app")
    with app_module.conn() as c:
        token = app_module.db.create_participant(c, "Marta")
    client = TestClient(app_module.app)
    response = client.get(f"/p/{token}/predict/group")
    assert response.status_code == 200
    assert "Advancer" not in response.text
    assert "prediction-row" in response.text
    assert "Sort by date" in response.text
    assert "Sort by group" in response.text
    assert 'type="text"' in response.text
    assert 'pattern="[0-9]*"' in response.text


def test_group_prediction_form_sorts_by_group(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "group-sort.sqlite3"))
    app_module = importlib.reload(sys.modules["app"]) if "app" in sys.modules else importlib.import_module("app")
    with app_module.conn() as c:
        token = app_module.db.create_participant(c, "Alex")
    client = TestClient(app_module.app)
    response = client.get(f"/p/{token}/predict/group?sort=group")
    assert response.status_code == 200
    assert "Group A" in response.text


def test_prediction_submit_rejects_invalid_score(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "invalid-score.sqlite3"))
    app_module = importlib.reload(sys.modules["app"]) if "app" in sys.modules else importlib.import_module("app")
    with app_module.conn() as c:
        token = app_module.db.create_participant(c, "Sam")
        fixture = c.execute("SELECT id FROM fixtures WHERE stage = 'group' ORDER BY display_order LIMIT 1").fetchone()
    client = TestClient(app_module.app)
    response = client.post(
        f"/p/{token}/predict/group",
        data={f"home_{fixture['id']}": "-1", f"away_{fixture['id']}": "two"},
    )
    assert response.status_code == 200
    assert "Invalid score" in response.text
