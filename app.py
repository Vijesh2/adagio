from __future__ import annotations

import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fasthtml.common import *
from starlette.responses import RedirectResponse

import db
from rules import STAGE_LABELS, STAGES
from ui import APP_STYLES, card, layout, page_header, table

APP_TITLE = "Adagio"
LONDON = ZoneInfo("Europe/London")

app, rt = fast_app(
    hdrs=[
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title(APP_TITLE),
        Style(APP_STYLES),
    ],
    title=APP_TITLE,
)
rt = app.route
db.init_db()


def conn():
    return db.connect()


def nav_admin(key: str | None = None):
    suffix = f"?key={key}" if key else ""
    return [
        A("Admin", href=f"/admin{suffix}", cls="secondary"),
        A("Participants", href=f"/admin/participants{suffix}", cls="secondary"),
        A("Results", href=f"/admin/results{suffix}", cls="secondary"),
        A("Locks", href=f"/admin/locks{suffix}", cls="secondary"),
    ]


def nav_participant(token: str):
    return [
        A("Dashboard", href=f"/p/{token}", cls="secondary"),
        A("Fixtures", href=f"/p/{token}/fixtures", cls="secondary"),
        A("Leaderboard", href=f"/p/{token}/leaderboard", cls="secondary"),
    ]


def admin_ok(key: str | None) -> bool:
    return bool(key) and key == os.getenv("ADMIN_PASSWORD", "admin")


def admin_gate(key: str | None):
    return layout(
        page_header("Admin", "Enter the admin password to manage the prediction game."),
        card(
            Form(
                Label("Password", Input(type="password", name="key", required=True)),
                Div(Button("Continue"), cls="actions"),
                method="get",
                action="/admin",
                cls="form-row",
            )
        ),
    )


def redirect(url: str):
    return RedirectResponse(url, status_code=303)


def parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def kickoff_label(iso_value: str) -> str:
    dt = datetime.fromisoformat(iso_value).astimezone(LONDON)
    return dt.strftime("%a %d %b, %H:%M %Z")


def score_text(home, away) -> str:
    if home is None or away is None:
        return "-"
    return f"{home}-{away}"


def stage_options(selected: str | None = None):
    return [Option(label, value=stage, selected=(stage == selected)) for stage, label in STAGE_LABELS.items()]


def participant_or_404(token: str):
    with conn() as c:
        participant = db.get_participant(c, token)
    if not participant:
        return None
    return participant


@rt("/")
def get():
    with conn() as c:
        fixtures = c.execute("SELECT COUNT(*) AS n FROM fixtures").fetchone()["n"]
        participants = c.execute("SELECT COUNT(*) AS n FROM participants WHERE active = 1").fetchone()["n"]
        first = c.execute("SELECT MIN(kickoff_utc) AS kickoff FROM fixtures").fetchone()["kickoff"]
    return layout(
        page_header("Adagio", "Private FIFA 2026 World Cup prediction game."),
        Div(
            card(Div(str(fixtures), cls="stat"), P("fixtures seeded", cls="muted")),
            card(Div(str(participants), cls="stat"), P("active participants", cls="muted")),
            card(Div(kickoff_label(first) if first else "-", cls="stat"), P("first kickoff", cls="muted")),
            cls="grid three",
        ),
        card(
            H2("How it works"),
            P("Admin creates private invite links. Participants predict each stage before the stage locks."),
            P("Scoring is 5 points exact score, 3 points correct result and goal difference, 1 point correct result."),
        ),
        nav=[A("Admin", href="/admin", cls="secondary")],
    )


@rt("/admin")
def get(key: str | None = None):
    if not admin_ok(key):
        return admin_gate(key)
    with conn() as c:
        stats = {
            "participants": c.execute("SELECT COUNT(*) AS n FROM participants WHERE active = 1").fetchone()["n"],
            "fixtures": c.execute("SELECT COUNT(*) AS n FROM fixtures").fetchone()["n"],
            "results": c.execute("SELECT COUNT(*) AS n FROM fixtures WHERE actual_home IS NOT NULL AND actual_away IS NOT NULL").fetchone()["n"],
        }
        locks = c.execute("SELECT * FROM stage_locks ORDER BY CASE stage " + " ".join([f"WHEN '{s}' THEN {i}" for i, s in enumerate(STAGES)]) + " END").fetchall()
    return layout(
        page_header("Admin", "Manage participants, locks, results, and generated knockout fixtures."),
        Div(
            card(Div(str(stats["participants"]), cls="stat"), P("active participants", cls="muted")),
            card(Div(str(stats["results"]), cls="stat"), P("results entered", cls="muted")),
            card(Div(str(stats["fixtures"]), cls="stat"), P("fixtures", cls="muted")),
            cls="grid three",
        ),
        card(
            H2("Stage locks"),
            table(["Stage", "Locked"], [[STAGE_LABELS[row["stage"]], "yes" if row["locked"] else "no"] for row in locks]),
        ),
        nav=nav_admin(key),
    )


@rt("/admin/participants")
def get(key: str | None = None):
    if not admin_ok(key):
        return admin_gate(key)
    base_url = os.getenv("APP_BASE_URL", "").rstrip("/")
    with conn() as c:
        participants = c.execute("SELECT * FROM participants ORDER BY active DESC, name").fetchall()
    rows = []
    for participant in participants:
        invite = f"{base_url}/p/{participant['token']}" if base_url else f"/p/{participant['token']}"
        rows.append(
            [
                participant["name"],
                participant["email"] or "",
                "active" if participant["active"] else "inactive",
                A(invite, href=invite),
            ]
        )
    return layout(
        page_header("Participants", "Create simple private links for the pool."),
        card(
            Form(
                Label("Name", Input(name="name", required=True)),
                Label("Email", Input(name="email", type="email")),
                Input(type="hidden", name="key", value=key),
                Button("Create"),
                method="post",
                action="/admin/participants",
                cls="form-row",
            )
        ),
        card(table(["Name", "Email", "Status", "Invite link"], rows)),
        nav=nav_admin(key),
    )


@rt("/admin/participants")
async def post(request):
    form = await request.form()
    key = form.get("key")
    if not admin_ok(key):
        return admin_gate(key)
    with conn() as c:
        db.create_participant(c, form.get("name", ""), form.get("email"))
    return redirect(f"/admin/participants?key={key}")


@rt("/admin/results")
def get(key: str | None = None, stage: str | None = None):
    if not admin_ok(key):
        return admin_gate(key)
    stage = stage or "group"
    with conn() as c:
        fixtures = db.fixtures_for_stage(c, stage)
    rows = []
    for fixture in fixtures:
        rows.append(
            Tr(
                Td(fixture["match_no"] or ""),
                Td(kickoff_label(fixture["kickoff_utc"])),
                Td(f"{fixture['home_team']} v {fixture['away_team']}"),
                Td(
                    Form(
                        Input(type="hidden", name="key", value=key),
                        Input(type="number", name="actual_home", value="" if fixture["actual_home"] is None else fixture["actual_home"], min="0", cls="score-input"),
                        Input(type="number", name="actual_away", value="" if fixture["actual_away"] is None else fixture["actual_away"], min="0", cls="score-input"),
                        Input(name="actual_advancer", value=fixture["actual_advancer"] or "", placeholder="Advancer"),
                        Button("Save"),
                        method="post",
                        action=f"/admin/results/{fixture['id']}",
                        cls="form-row",
                    )
                ),
            )
        )
    return layout(
        page_header("Results", "Enter actual scores and knockout advancers."),
        card(
            Form(
                Label("Stage", Select(*stage_options(stage), name="stage")),
                Input(type="hidden", name="key", value=key),
                Button("View"),
                method="get",
                action="/admin/results",
                cls="form-row",
            )
        ),
        Table(Thead(Tr(Th("No"), Th("Kickoff"), Th("Fixture"), Th("Result"))), Tbody(*rows)),
        nav=nav_admin(key),
    )


@rt("/admin/results/{fixture_id}")
async def post(fixture_id: str, request):
    form = await request.form()
    key = form.get("key")
    if not admin_ok(key):
        return admin_gate(key)
    with conn() as c:
        fixture = c.execute("SELECT stage FROM fixtures WHERE id = ?", (fixture_id,)).fetchone()
        db.set_actual_result(
            c,
            fixture_id,
            parse_int(form.get("actual_home")),
            parse_int(form.get("actual_away")),
            (form.get("actual_advancer") or "").strip() or None,
        )
    return redirect(f"/admin/results?key={key}&stage={fixture['stage'] if fixture else 'group'}")


@rt("/admin/locks")
def get(key: str | None = None):
    if not admin_ok(key):
        return admin_gate(key)
    with conn() as c:
        locks = c.execute("SELECT * FROM stage_locks").fetchall()
    rows = []
    for lock in locks:
        rows.append(
            [
                STAGE_LABELS[lock["stage"]],
                "locked" if lock["locked"] else "open until kickoff",
                Form(
                    Input(type="hidden", name="key", value=key),
                    Input(type="hidden", name="stage", value=lock["stage"]),
                    Input(type="hidden", name="locked", value="0" if lock["locked"] else "1"),
                    Button("Unlock" if lock["locked"] else "Lock"),
                    method="post",
                    action="/admin/locks",
                ),
            ]
        )
    return layout(page_header("Locks"), card(table(["Stage", "State", "Action"], rows)), nav=nav_admin(key))


@rt("/admin/locks")
async def post(request):
    form = await request.form()
    key = form.get("key")
    if not admin_ok(key):
        return admin_gate(key)
    with conn() as c:
        db.set_stage_lock(c, form.get("stage"), form.get("locked") == "1")
    return redirect(f"/admin/locks?key={key}")


@rt("/admin/generate-knockout/{stage}")
def post(stage: str, key: str | None = None):
    if not admin_ok(key):
        return admin_gate(key)
    with conn() as c:
        db.generate_knockout_fixtures(c, stage)
    return redirect(f"/admin/results?key={key}&stage={stage}")


@rt("/p/{token}")
def get(token: str):
    participant = participant_or_404(token)
    if not participant:
        return layout(page_header("Invite not found"))
    with conn() as c:
        board = db.leaderboard(c)
        locks = c.execute("SELECT * FROM stage_locks").fetchall()
    stage_cards = []
    for stage in STAGES:
        locked = next((row for row in locks if row["stage"] == stage), None)
        state = "locked" if locked and locked["locked"] else "open until kickoff"
        stage_cards.append(card(H3(STAGE_LABELS[stage]), P(state, cls="muted"), A("Predict", href=f"/p/{token}/predict/{stage}", cls="button secondary")))
    return layout(
        page_header(f"Hi {participant['name']}", "Predictions lock by stage. Your own predictions remain visible after saving."),
        Div(*stage_cards, cls="grid three"),
        card(H2("Leaderboard"), table(["Participant", "Points"], [[row["name"], row["total_points"]] for row in board])),
        nav=nav_participant(token),
    )


@rt("/p/{token}/fixtures")
def get(token: str, sort: str | None = "date"):
    participant = participant_or_404(token)
    if not participant:
        return layout(page_header("Invite not found"))
    sort = sort if sort in {"date", "group"} else "date"
    with conn() as c:
        rows = c.execute(
            """
            SELECT f.*, p.predicted_home, p.predicted_away, p.predicted_advancer, p.points
            FROM fixtures f
            LEFT JOIN predictions p ON p.fixture_id = f.id AND p.participant_id = ?
            ORDER BY
                CASE WHEN ? = 'group' THEN f.stage ELSE f.kickoff_utc END,
                CASE WHEN ? = 'group' THEN COALESCE(f.group_code, '') ELSE '' END,
                f.display_order
            """,
            (participant["id"], sort, sort),
        ).fetchall()
    table_rows = [
        [
            STAGE_LABELS[row["stage"]],
            row["group_code"] or "",
            kickoff_label(row["kickoff_utc"]),
            f"{row['home_team']} v {row['away_team']}",
            score_text(row["predicted_home"], row["predicted_away"]),
            score_text(row["actual_home"], row["actual_away"]),
            "" if row["points"] is None else row["points"],
        ]
        for row in rows
    ]
    return layout(
        page_header("Fixtures"),
        card(Div(A("Sort by date", href=f"/p/{token}/fixtures?sort=date", cls="button secondary"), A("Sort by group", href=f"/p/{token}/fixtures?sort=group", cls="button secondary"), cls="actions")),
        table(["Stage", "Group", "Kickoff", "Fixture", "Prediction", "Actual", "Pts"], table_rows),
        nav=nav_participant(token),
    )


@rt("/p/{token}/leaderboard")
def get(token: str):
    if not participant_or_404(token):
        return layout(page_header("Invite not found"))
    with conn() as c:
        board = db.leaderboard(c)
    return layout(
        page_header("Leaderboard"),
        card(table(["Participant", "Points"], [[row["name"], row["total_points"]] for row in board])),
        nav=nav_participant(token),
    )


@rt("/p/{token}/predict/{stage}")
def get(token: str, stage: str):
    participant = participant_or_404(token)
    if not participant:
        return layout(page_header("Invite not found"))
    if stage not in STAGES:
        return layout(page_header("Unknown stage"), nav=nav_participant(token))
    with conn() as c:
        locked = db.stage_is_locked(c, stage)
        fixtures = c.execute(
            """
            SELECT f.*, p.predicted_home, p.predicted_away, p.predicted_advancer
            FROM fixtures f
            LEFT JOIN predictions p ON p.fixture_id = f.id AND p.participant_id = ?
            WHERE f.stage = ?
            ORDER BY f.display_order
            """,
            (participant["id"], stage),
        ).fetchall()
    controls = []
    for fixture in fixtures:
        tied_help = "Advancer is only needed for tied knockout predictions."
        controls.append(
            card(
                H3(f"{fixture['home_team']} v {fixture['away_team']}"),
                P(kickoff_label(fixture["kickoff_utc"]), cls="muted"),
                Div(
                    Label(fixture["home_team"], Input(type="number", name=f"home_{fixture['id']}", min="0", value="" if fixture["predicted_home"] is None else fixture["predicted_home"], disabled=locked, cls="score-input")),
                    Label(fixture["away_team"], Input(type="number", name=f"away_{fixture['id']}", min="0", value="" if fixture["predicted_away"] is None else fixture["predicted_away"], disabled=locked, cls="score-input")),
                    Label("Advancer", Input(name=f"adv_{fixture['id']}", value=fixture["predicted_advancer"] or "", placeholder=tied_help, disabled=locked)),
                    cls="form-row",
                ),
            )
        )
    return layout(
        page_header(STAGE_LABELS[stage], "This stage is locked." if locked else "Enter scores before the stage locks."),
        Form(*controls, Button("Save predictions", disabled=locked), method="post", action=f"/p/{token}/predict/{stage}"),
        nav=nav_participant(token),
    )


@rt("/p/{token}/predict/{stage}")
async def post(token: str, stage: str, request):
    participant = participant_or_404(token)
    if not participant:
        return layout(page_header("Invite not found"))
    form = await request.form()
    with conn() as c:
        fixtures = db.fixtures_for_stage(c, stage)
        for fixture in fixtures:
            db.upsert_prediction(
                c,
                participant["id"],
                fixture["id"],
                parse_int(form.get(f"home_{fixture['id']}")),
                parse_int(form.get(f"away_{fixture['id']}")),
                (form.get(f"adv_{fixture['id']}") or "").strip() or None,
            )
    return redirect(f"/p/{token}/fixtures")


if __name__ == "__main__":
    serve(host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "5001")))
