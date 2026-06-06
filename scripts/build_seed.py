from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GUARDIAN_URL = "https://www.theguardian.com/football/world-cup-2026/overview"
WIKI_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage"
LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

ROUND_OF_32_NUMBERS = [74, 77, 73, 75, 83, 84, 81, 82, 76, 78, 79, 80, 86, 88, 85, 87]
ROUND_OF_16_NUMBERS = list(range(89, 97))
QUARTER_FINAL_NUMBERS = list(range(97, 101))
SEMI_FINAL_NUMBERS = [101, 102]
THIRD_PLACE_NUMBER = [103]
FINAL_NUMBER = [104]


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": "AdagioPredictionSeed/0.1 (fixture seed builder)"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def kickoff_iso(date_text: str, time_text: str) -> str:
    raw = f"{clean(date_text)} 2026 {clean(time_text).replace(' BST', '')}"
    local = datetime.strptime(raw, "%a %d %B %Y %H:%M").replace(tzinfo=LONDON)
    return local.astimezone(UTC).replace(microsecond=0).isoformat()


def parse_group_data(soup: BeautifulSoup) -> tuple[list[dict], list[dict]]:
    teams = []
    fixtures = []
    display_order = 1
    for group_li in soup.select("li.football-group"):
        caption = group_li.select_one("caption .football-matches__heading")
        if not caption:
            continue
        group_label = clean(caption.get_text())
        if not group_label.startswith("Group "):
            continue
        group_code = group_label.removeprefix("Group ").strip()
        for order, team_el in enumerate(group_li.select("span.team-name a.team-name__long"), start=1):
            teams.append({"name": clean(team_el.get_text()), "group_code": group_code, "seed_order": order})
        for table in group_li.select("table.football-matches"):
            date_el = table.select_one(".football-matches__date")
            if not date_el:
                continue
            date_text = clean(date_el.get_text())
            for row in table.select("tr.football-match"):
                names = [clean(el.get_text()) for el in row.select(".football-team__name")]
                time_el = row.select_one(".football-match__status")
                if len(names) != 2 or not time_el:
                    continue
                source_id = row.get("id", f"group-{display_order}").removeprefix("football-match-")
                fixtures.append(
                    {
                        "id": f"g-{source_id}",
                        "match_no": display_order,
                        "stage": "group",
                        "group_code": group_code,
                        "kickoff_utc": kickoff_iso(date_text, time_el.get_text()),
                        "venue": None,
                        "home_team": names[0],
                        "away_team": names[1],
                        "home_slot": names[0],
                        "away_slot": names[1],
                        "display_order": display_order,
                    }
                )
                display_order += 1
    return teams, fixtures


def stage_key(label: str) -> str:
    return {
        "Round of 32": "round_of_32",
        "Round of 16": "round_of_16",
        "Quarter Final": "quarter_final",
        "Semi-Final": "semi_final",
        "3rd/4th Play-Offs": "third_place",
        "Final": "final",
    }[label]


def match_numbers_for(stage: str) -> list[int]:
    return {
        "round_of_32": ROUND_OF_32_NUMBERS,
        "round_of_16": ROUND_OF_16_NUMBERS,
        "quarter_final": QUARTER_FINAL_NUMBERS,
        "semi_final": SEMI_FINAL_NUMBERS,
        "third_place": THIRD_PLACE_NUMBER,
        "final": FINAL_NUMBER,
    }[stage]


def slot_name(name: str) -> str:
    match = re.fullmatch(r"(Winner|Runner-up) ([A-L])", name)
    if match:
        prefix = "1" if match.group(1) == "Winner" else "2"
        return f"{prefix}{match.group(2)}"
    match = re.fullmatch(r"Group ([A-L](?: / [A-L])*) Third Place", name)
    if match:
        return name
    return name


def parse_knockout_fixtures(soup: BeautifulSoup, start_order: int) -> list[dict]:
    fixtures = []
    counters: dict[str, int] = {}
    chart = soup.select_one(".football-knockout-chart")
    if not chart:
        return fixtures
    for round_el in chart.select(".football-round"):
        name_el = round_el.select_one(".football-round__name")
        if not name_el:
            continue
        stage = stage_key(clean(name_el.get_text()))
        numbers = match_numbers_for(stage)
        for match_el in round_el.select(".football-match"):
            names = [clean(el.get_text()) for el in match_el.select(".football-match__team-name")]
            date_el = match_el.select_one(".football-match__date")
            time_el = match_el.select_one(".football-match__kickoff")
            if len(names) != 2 or not date_el or not time_el:
                continue
            date_text = clean(date_el.get_text()).replace(clean(time_el.get_text()), "").strip()
            index = counters.get(stage, 0)
            counters[stage] = index + 1
            source_id = match_el.get("id", f"{stage}-{index + 1}").removeprefix("football-match-")
            match_no = numbers[index]
            fixtures.append(
                {
                    "id": f"k-{source_id}",
                    "match_no": match_no,
                    "stage": stage,
                    "group_code": None,
                    "kickoff_utc": kickoff_iso(date_text, time_el.get_text()),
                    "venue": None,
                    "home_team": names[0],
                    "away_team": names[1],
                    "home_slot": slot_name(names[0]),
                    "away_slot": slot_name(names[1]),
                    "display_order": start_order + len(fixtures),
                }
            )
    return fixtures


def parse_third_place_mapping(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    table = soup.find("table")
    if not table:
        raise RuntimeError("Wikipedia mapping table not found")
    mapping = {}
    headers = [clean(cell.get_text()) for cell in table.select("tr")[0].find_all(["th", "td"])]
    slots = [header for header in headers if re.fullmatch(r"1[A-L]\s*vs", header)]
    slots = [slot.replace(" vs", "").replace("vs", "") for slot in slots]
    for row in table.select("tr")[1:]:
        cells = [clean(cell.get_text()) for cell in row.find_all(["th", "td"])]
        if len(cells) < 10:
            continue
        destinations = cells[-len(slots) :]
        groups = "".join(cell for cell in cells[1 : -len(slots)] if re.fullmatch(r"[A-L]", cell))
        if len(groups) == 8 and len(destinations) == 8:
            mapping[groups] = dict(zip(slots, destinations))
    return mapping


def main() -> int:
    guardian = BeautifulSoup(fetch(GUARDIAN_URL), "html.parser")
    wiki = BeautifulSoup(fetch(WIKI_URL), "html.parser")
    teams, group_fixtures = parse_group_data(guardian)
    fixtures = group_fixtures + parse_knockout_fixtures(guardian, len(group_fixtures) + 1)
    mapping = parse_third_place_mapping(wiki)
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "fixtures.json").write_text(
        json.dumps(
            {
                "source": GUARDIAN_URL,
                "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "teams": teams,
                "fixtures": fixtures,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (DATA_DIR / "third_place_mapping.json").write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(teams)} teams, {len(fixtures)} fixtures, {len(mapping)} third-place combinations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
