from __future__ import annotations

import json
import os
import secrets
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from rules import MatchResult, STAGES, best_thirds, group_table, score_prediction, validate_third_place_mapping

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SEED_FIXTURES_PATH = DATA_DIR / "fixtures.json"
THIRD_PLACE_MAPPING_PATH = DATA_DIR / "third_place_mapping.json"


def database_path() -> Path:
    volume_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    default_path = Path(volume_path) / "adagio.sqlite3" if volume_path else DATA_DIR / "adagio.sqlite3"
    configured = os.getenv("DATABASE_URL", str(default_path))
    if configured.startswith("sqlite:///"):
        configured = configured.removeprefix("sqlite:///")
    return Path(configured)


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def init_db(conn: sqlite3.Connection | None = None) -> None:
    own_conn = conn is None
    conn = conn or connect()
    create_schema(conn)
    seed_static_data(conn)
    if own_conn:
        conn.close()


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS teams (
            name TEXT PRIMARY KEY,
            group_code TEXT,
            seed_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS fixtures (
            id TEXT PRIMARY KEY,
            match_no INTEGER,
            stage TEXT NOT NULL,
            group_code TEXT,
            kickoff_utc TEXT NOT NULL,
            venue TEXT,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_slot TEXT,
            away_slot TEXT,
            display_order INTEGER NOT NULL,
            actual_home INTEGER,
            actual_away INTEGER,
            actual_advancer TEXT,
            is_generated INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            token TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS predictions (
            participant_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
            fixture_id TEXT NOT NULL REFERENCES fixtures(id) ON DELETE CASCADE,
            predicted_home INTEGER,
            predicted_away INTEGER,
            predicted_advancer TEXT,
            points INTEGER,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (participant_id, fixture_id)
        );

        CREATE TABLE IF NOT EXISTS stage_locks (
            stage TEXT PRIMARY KEY,
            locked INTEGER NOT NULL DEFAULT 0,
            locked_at TEXT
        );

        CREATE TABLE IF NOT EXISTS group_standings (
            group_code TEXT NOT NULL,
            position INTEGER NOT NULL,
            team TEXT NOT NULL,
            played INTEGER NOT NULL,
            won INTEGER NOT NULL,
            drawn INTEGER NOT NULL,
            lost INTEGER NOT NULL,
            goals_for INTEGER NOT NULL,
            goals_against INTEGER NOT NULL,
            goal_difference INTEGER NOT NULL,
            points INTEGER NOT NULL,
            tie_unresolved INTEGER NOT NULL,
            PRIMARY KEY (group_code, position)
        );

        CREATE TABLE IF NOT EXISTS knockout_slots (
            slot TEXT PRIMARY KEY,
            team TEXT,
            source TEXT NOT NULL,
            needs_review INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS scoring_totals (
            participant_id INTEGER PRIMARY KEY REFERENCES participants(id) ON DELETE CASCADE,
            total_points INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    for stage in STAGES:
        conn.execute("INSERT OR IGNORE INTO stage_locks(stage, locked) VALUES (?, 0)", (stage,))
    conn.commit()


def seed_static_data(conn: sqlite3.Connection) -> None:
    if not SEED_FIXTURES_PATH.exists():
        return
    seed = json.loads(SEED_FIXTURES_PATH.read_text(encoding="utf-8"))
    if THIRD_PLACE_MAPPING_PATH.exists():
        validate_third_place_mapping(json.loads(THIRD_PLACE_MAPPING_PATH.read_text(encoding="utf-8")))
    for team in seed.get("teams", []):
        conn.execute(
            "INSERT OR IGNORE INTO teams(name, group_code, seed_order) VALUES (?, ?, ?)",
            (team["name"], team["group_code"], team["seed_order"]),
        )
    for fixture in seed.get("fixtures", []):
        conn.execute(
            """
            INSERT OR IGNORE INTO fixtures(
                id, match_no, stage, group_code, kickoff_utc, venue, home_team, away_team,
                home_slot, away_slot, display_order, is_generated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                fixture["id"],
                fixture.get("match_no"),
                fixture["stage"],
                fixture.get("group_code"),
                fixture["kickoff_utc"],
                fixture.get("venue"),
                fixture["home_team"],
                fixture["away_team"],
                fixture.get("home_slot"),
                fixture.get("away_slot"),
                fixture["display_order"],
            ),
        )
    conn.commit()


def get_participant(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM participants WHERE token = ? AND active = 1", (token,)).fetchone()


def create_participant(conn: sqlite3.Connection, name: str, email: str | None = None) -> str:
    token = secrets.token_urlsafe(18)
    conn.execute(
        "INSERT INTO participants(name, email, token, created_at) VALUES (?, ?, ?, ?)",
        (name.strip(), (email or "").strip() or None, token, utc_now_iso()),
    )
    conn.commit()
    return token


def fixture_rows(conn: sqlite3.Connection, sort: str = "date") -> list[sqlite3.Row]:
    order = "stage, group_code, display_order" if sort == "group" else "kickoff_utc, display_order"
    return list(conn.execute(f"SELECT * FROM fixtures ORDER BY {order}"))


def fixtures_for_stage(conn: sqlite3.Connection, stage: str) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM fixtures WHERE stage = ? ORDER BY display_order", (stage,)))


def stage_is_locked(conn: sqlite3.Connection, stage: str, now: datetime | None = None) -> bool:
    row = conn.execute("SELECT locked FROM stage_locks WHERE stage = ?", (stage,)).fetchone()
    if row and row["locked"]:
        return True
    first = conn.execute("SELECT MIN(kickoff_utc) AS first_kickoff FROM fixtures WHERE stage = ?", (stage,)).fetchone()
    if not first or not first["first_kickoff"]:
        return False
    now = now or datetime.now(UTC)
    kickoff = datetime.fromisoformat(first["first_kickoff"])
    return now >= kickoff


def set_stage_lock(conn: sqlite3.Connection, stage: str, locked: bool) -> None:
    conn.execute(
        "UPDATE stage_locks SET locked = ?, locked_at = ? WHERE stage = ?",
        (1 if locked else 0, utc_now_iso() if locked else None, stage),
    )
    conn.commit()


def upsert_prediction(
    conn: sqlite3.Connection,
    participant_id: int,
    fixture_id: str,
    predicted_home: int | None,
    predicted_away: int | None,
    predicted_advancer: str | None,
) -> None:
    fixture = conn.execute("SELECT * FROM fixtures WHERE id = ?", (fixture_id,)).fetchone()
    if not fixture:
        raise ValueError("fixture not found")
    if stage_is_locked(conn, fixture["stage"]):
        raise ValueError("stage is locked")
    conn.execute(
        """
        INSERT INTO predictions(participant_id, fixture_id, predicted_home, predicted_away, predicted_advancer, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(participant_id, fixture_id) DO UPDATE SET
            predicted_home = excluded.predicted_home,
            predicted_away = excluded.predicted_away,
            predicted_advancer = excluded.predicted_advancer,
            updated_at = excluded.updated_at
        """,
        (participant_id, fixture_id, predicted_home, predicted_away, predicted_advancer, utc_now_iso()),
    )
    conn.commit()
    recompute_scores(conn)


def set_actual_result(
    conn: sqlite3.Connection,
    fixture_id: str,
    actual_home: int | None,
    actual_away: int | None,
    actual_advancer: str | None,
) -> None:
    conn.execute(
        "UPDATE fixtures SET actual_home = ?, actual_away = ?, actual_advancer = ? WHERE id = ?",
        (actual_home, actual_away, actual_advancer, fixture_id),
    )
    conn.commit()
    refresh_group_standings(conn)
    recompute_scores(conn)


def recompute_scores(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT p.participant_id, p.fixture_id, p.predicted_home, p.predicted_away, p.predicted_advancer,
               f.actual_home, f.actual_away, f.actual_advancer
        FROM predictions p
        JOIN fixtures f ON f.id = p.fixture_id
        """
    ).fetchall()
    totals: dict[int, int] = {}
    for row in rows:
        points = score_prediction(
            row["predicted_home"],
            row["predicted_away"],
            row["actual_home"],
            row["actual_away"],
            row["predicted_advancer"],
            row["actual_advancer"],
        )
        conn.execute(
            "UPDATE predictions SET points = ? WHERE participant_id = ? AND fixture_id = ?",
            (points, row["participant_id"], row["fixture_id"]),
        )
        if points is not None:
            totals[row["participant_id"]] = totals.get(row["participant_id"], 0) + points
    conn.execute("DELETE FROM scoring_totals")
    for participant_id, total in totals.items():
        conn.execute(
            "INSERT INTO scoring_totals(participant_id, total_points) VALUES (?, ?)",
            (participant_id, total),
        )
    conn.commit()


def completed_group_results(conn: sqlite3.Connection) -> list[MatchResult]:
    rows = conn.execute(
        """
        SELECT group_code, home_team, away_team, actual_home, actual_away
        FROM fixtures
        WHERE stage = 'group' AND actual_home IS NOT NULL AND actual_away IS NOT NULL
        """
    ).fetchall()
    return [
        MatchResult(row["group_code"], row["home_team"], row["away_team"], row["actual_home"], row["actual_away"])
        for row in rows
    ]


def refresh_group_standings(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM group_standings")
    by_group: dict[str, list[MatchResult]] = {}
    for result in completed_group_results(conn):
        by_group.setdefault(result.group_code, []).append(result)
    for group, results in by_group.items():
        for position, row in enumerate(group_table(results), start=1):
            conn.execute(
                """
                INSERT INTO group_standings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group,
                    position,
                    row["team"],
                    row["played"],
                    row["won"],
                    row["drawn"],
                    row["lost"],
                    row["goals_for"],
                    row["goals_against"],
                    row["goal_difference"],
                    row["points"],
                    1 if row["tie_unresolved"] else 0,
                ),
            )
    conn.commit()


def leaderboard(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT participants.name, participants.token, COALESCE(scoring_totals.total_points, 0) AS total_points
            FROM participants
            LEFT JOIN scoring_totals ON scoring_totals.participant_id = participants.id
            WHERE participants.active = 1
            ORDER BY total_points DESC, participants.name
            """
        )
    )


def populate_knockout_slots(conn: sqlite3.Connection) -> None:
    refresh_group_standings(conn)
    tables: dict[str, list[dict]] = {}
    groups = conn.execute("SELECT DISTINCT group_code FROM teams ORDER BY group_code").fetchall()
    for group_row in groups:
        rows = conn.execute(
            "SELECT * FROM group_standings WHERE group_code = ? ORDER BY position",
            (group_row["group_code"],),
        ).fetchall()
        if len(rows) >= 4:
            tables[group_row["group_code"]] = [dict(row) for row in rows]
    conn.execute("DELETE FROM knockout_slots")
    for group, rows in tables.items():
        conn.execute("INSERT INTO knockout_slots(slot, team, source, needs_review) VALUES (?, ?, ?, ?)", (f"1{group}", rows[0]["team"], "group winner", rows[0]["tie_unresolved"]))
        conn.execute("INSERT INTO knockout_slots(slot, team, source, needs_review) VALUES (?, ?, ?, ?)", (f"2{group}", rows[1]["team"], "group runner-up", rows[1]["tie_unresolved"]))
    thirds = best_thirds(tables)[:8]
    third_groups = [row["source_group"] for row in thirds]
    mapping = json.loads(THIRD_PLACE_MAPPING_PATH.read_text(encoding="utf-8")) if THIRD_PLACE_MAPPING_PATH.exists() else {}
    slots = mapping.get("".join(sorted(third_groups)), {})
    third_lookup = {row["source_group"]: row for row in thirds}
    for slot, third_slot in slots.items():
        group = third_slot.removeprefix("3")
        row = third_lookup.get(group)
        if row:
            conn.execute(
                "INSERT OR REPLACE INTO knockout_slots(slot, team, source, needs_review) VALUES (?, ?, ?, ?)",
                (third_slot, row["team"], f"third place for {slot}", row["tie_unresolved"]),
            )
    conn.commit()


def generate_knockout_fixtures(conn: sqlite3.Connection, stage: str) -> int:
    if stage == "round_of_32":
        populate_knockout_slots(conn)
    count = 0
    rows = fixtures_for_stage(conn, stage)
    for fixture in rows:
        home = resolve_slot(conn, fixture["home_slot"] or fixture["home_team"])
        away = resolve_slot(conn, fixture["away_slot"] or fixture["away_team"])
        if home != fixture["home_team"] or away != fixture["away_team"]:
            conn.execute("UPDATE fixtures SET home_team = ?, away_team = ?, is_generated = 1 WHERE id = ?", (home, away, fixture["id"]))
            count += 1
    conn.commit()
    return count


def resolve_slot(conn: sqlite3.Connection, slot: str) -> str:
    if slot.startswith("Winner Match "):
        match_no = int(slot.removeprefix("Winner Match "))
        row = conn.execute("SELECT actual_advancer FROM fixtures WHERE match_no = ?", (match_no,)).fetchone()
        return row["actual_advancer"] if row and row["actual_advancer"] else slot
    if slot.startswith("Loser Match "):
        match_no = int(slot.removeprefix("Loser Match "))
        row = conn.execute("SELECT home_team, away_team, actual_advancer FROM fixtures WHERE match_no = ?", (match_no,)).fetchone()
        if row and row["actual_advancer"]:
            return row["away_team"] if row["actual_advancer"] == row["home_team"] else row["home_team"]
        return slot
    row = conn.execute("SELECT team FROM knockout_slots WHERE slot = ?", (slot,)).fetchone()
    return row["team"] if row and row["team"] else slot
