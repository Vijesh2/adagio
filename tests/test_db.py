from pathlib import Path

import db


def test_seed_integrity():
    fixtures = db.json.loads(Path("data/fixtures.json").read_text())
    mapping = db.json.loads(Path("data/third_place_mapping.json").read_text())
    assert len(fixtures["teams"]) == 48
    assert len(fixtures["fixtures"]) == 104
    assert len(mapping) == 495
    db.validate_third_place_mapping(mapping)


def test_database_path_prefers_railway_volume(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")
    assert db.database_path() == Path("/data/adagio.sqlite3")


def test_prediction_flow_and_locking(tmp_path):
    conn = db.connect(tmp_path / "test.sqlite3")
    db.init_db(conn)
    token = db.create_participant(conn, "Ada")
    participant = db.get_participant(conn, token)
    fixture = conn.execute("SELECT * FROM fixtures WHERE stage = 'group' ORDER BY display_order LIMIT 1").fetchone()
    db.upsert_prediction(conn, participant["id"], fixture["id"], 2, 1, None)
    db.set_actual_result(conn, fixture["id"], 2, 1, None)
    row = conn.execute("SELECT points FROM predictions WHERE participant_id = ?", (participant["id"],)).fetchone()
    assert row["points"] == 5
    db.set_stage_lock(conn, "group", True)
    try:
        db.upsert_prediction(conn, participant["id"], fixture["id"], 1, 0, None)
    except ValueError as exc:
        assert "locked" in str(exc)
    else:
        raise AssertionError("locked stage accepted prediction")
