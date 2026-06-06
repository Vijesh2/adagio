from fasthtml.common import *

APP_STYLES = """
:root {
    color-scheme: light;
    --bg: #f4f6f3;
    --surface: #ffffff;
    --surface-2: #eef2ed;
    --border: #cad4c8;
    --text: #172018;
    --muted: #5d685e;
    --accent: #0f766e;
    --accent-2: #b42318;
    --good: #047857;
    --warn: #b45309;
}

* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: Inter, "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
    background: var(--bg);
    color: var(--text);
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.page-shell {
    width: min(1180px, 100%);
    margin: 0 auto;
    padding: 1.25rem 1rem 3rem;
}

.topbar {
    align-items: center;
    display: flex;
    gap: .75rem;
    justify-content: space-between;
    margin-bottom: 1rem;
}

.nav {
    display: flex;
    flex-wrap: wrap;
    gap: .5rem;
}

.nav a, .button, button {
    align-items: center;
    background: var(--accent);
    border: 1px solid var(--accent);
    border-radius: 6px;
    color: white;
    display: inline-flex;
    font-weight: 700;
    min-height: 2.25rem;
    padding: .45rem .75rem;
    text-decoration: none;
}

.nav a.secondary, .button.secondary {
    background: var(--surface);
    color: var(--accent);
}

.page-header { margin: .75rem 0 1rem; }
.page-title { font-size: clamp(2rem, 4vw, 3.5rem); line-height: 1; margin: 0; }
.page-subtitle { color: var(--muted); margin: .5rem 0 0; max-width: 70ch; }

.grid { display: grid; gap: 1rem; }
.grid.two { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
.grid.three { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }

.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
}

.stat { font-size: 2rem; font-weight: 800; line-height: 1; }
.muted { color: var(--muted); }
.pill {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 999px;
    display: inline-block;
    font-size: .85rem;
    font-weight: 700;
    padding: .18rem .55rem;
}

table {
    background: var(--surface);
    border: 1px solid var(--border);
    border-collapse: collapse;
    border-radius: 8px;
    overflow: hidden;
    width: 100%;
}

th, td {
    border-bottom: 1px solid var(--border);
    padding: .55rem .6rem;
    text-align: left;
    vertical-align: middle;
}

th { background: var(--surface-2); font-size: .85rem; }
tr:last-child td { border-bottom: 0; }

input, select {
    border: 1px solid var(--border);
    border-radius: 6px;
    min-height: 2.2rem;
    padding: .35rem .5rem;
    width: 100%;
}

input[type="checkbox"] { min-height: auto; width: auto; }
.score-input { width: 4.5rem; }
input.compact-score {
    appearance: none;
    border-radius: 4px;
    box-sizing: border-box;
    display: block;
    font-size: .82rem;
    font-weight: 800;
    height: 1.35rem;
    line-height: normal;
    max-height: 1.35rem;
    min-height: 0;
    padding: 0 .1rem;
    position: relative;
    text-align: center;
    vertical-align: middle;
    width: 1.9rem;
}
.form-row { align-items: end; display: flex; flex-wrap: wrap; gap: .75rem; }
.form-row label { display: grid; gap: .25rem; font-size: .9rem; font-weight: 700; }
.create-participant-form { align-items: center; }
.create-participant-form label { width: 16rem; }
.actions { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .75rem; }
.danger { color: var(--accent-2); font-weight: 700; }
.ok { color: var(--good); font-weight: 700; }
.warn { color: var(--warn); font-weight: 700; }

.prediction-list {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
}

.prediction-row {
    align-items: center;
    border-bottom: 1px solid #dde5db;
    display: grid;
    gap: .3rem;
    grid-template-columns: minmax(10rem, 1fr) 2rem 1rem 2rem minmax(10rem, 1fr) minmax(9rem, auto);
    line-height: 1.1;
    min-height: 2rem;
    padding: .15rem .7rem;
}

.prediction-row:last-child { border-bottom: 0; }
.prediction-row:nth-child(even) { background: #fbfcfb; }
.prediction-row:hover { background: #eef6f1; }
.team-home, .team-away, .score-separator, .score-cell {
    align-items: center;
    display: flex;
    min-height: 1.7rem;
}
.team-home, .team-away {
    font-size: .95rem;
    font-weight: 800;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.team-home { justify-content: flex-end; text-align: right; }
.team-away { justify-content: flex-start; }
.score-separator {
    color: var(--muted);
    font-size: .8rem;
    font-weight: 800;
    justify-content: center;
    text-align: center;
}
.score-cell { justify-content: center; }
.score-cell input {
    box-sizing: border-box;
    height: 1.35rem;
    line-height: 1.35rem;
    padding: 0;
    text-align: center;
    transform: translateY(1px);
}
.match-meta { color: var(--muted); font-size: .82rem; text-align: right; white-space: nowrap; }
.group-label { color: var(--text); font-weight: 800; margin-right: .35rem; }

@media (max-width: 720px) {
    .topbar { align-items: stretch; flex-direction: column; }
    table { display: block; overflow-x: auto; }
    .prediction-row {
        grid-template-columns: minmax(6rem, 1fr) 2rem 1rem 2rem minmax(6rem, 1fr);
    }
    .match-meta {
        grid-column: 1 / -1;
        order: -1;
        text-align: left;
    }
    .compact-score { width: 1.85rem; }
}
"""


def layout(*children, nav=None):
    nav = nav or []
    return Main(
        Div(
            A("Adagio", href="/", cls="button secondary"),
            Nav(*nav, cls="nav"),
            cls="topbar",
        ),
        *children,
        cls="page-shell",
    )


def page_header(title: str, subtitle: str | None = None):
    children = [H1(title, cls="page-title")]
    if subtitle:
        children.append(P(subtitle, cls="page-subtitle"))
    return Header(*children, cls="page-header")


def card(*children):
    return Section(*children, cls="card")


def table(headers, rows):
    return Table(
        Thead(Tr(*[Th(h) for h in headers])),
        Tbody(*[Tr(*[Td(cell) for cell in row]) for row in rows]),
    )
