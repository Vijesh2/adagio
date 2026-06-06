from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

GROUPS = tuple("ABCDEFGHIJKL")
STAGES = (
    "group",
    "round_of_32",
    "round_of_16",
    "quarter_final",
    "semi_final",
    "third_place",
    "final",
)
STAGE_LABELS = {
    "group": "Group stage",
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "quarter_final": "Quarter-finals",
    "semi_final": "Semi-finals",
    "third_place": "Third-place match",
    "final": "Final",
}


@dataclass(frozen=True)
class MatchResult:
    group_code: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int


def result_sign(home_goals: int, away_goals: int) -> int:
    return (home_goals > away_goals) - (home_goals < away_goals)


def score_prediction(
    predicted_home: int | None,
    predicted_away: int | None,
    actual_home: int | None,
    actual_away: int | None,
    predicted_advancer: str | None = None,
    actual_advancer: str | None = None,
) -> int | None:
    if None in (predicted_home, predicted_away, actual_home, actual_away):
        return None
    if predicted_home == actual_home and predicted_away == actual_away:
        if actual_home == actual_away and actual_advancer:
            return 5 if predicted_advancer == actual_advancer else 3
        return 5
    predicted_result = result_sign(predicted_home, predicted_away)
    actual_result = result_sign(actual_home, actual_away)
    if predicted_result == 0 and actual_result == 0 and actual_advancer:
        return 3 if predicted_advancer == actual_advancer else 0
    if predicted_result != actual_result:
        return 0
    if predicted_home - predicted_away == actual_home - actual_away:
        return 3
    return 1


def group_table(results: list[MatchResult]) -> list[dict]:
    rows: dict[str, dict] = {}
    for result in results:
        for team in (result.home_team, result.away_team):
            rows.setdefault(
                team,
                {
                    "team": team,
                    "group_code": result.group_code,
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "goal_difference": 0,
                    "points": 0,
                    "tie_unresolved": False,
                },
            )
        home = rows[result.home_team]
        away = rows[result.away_team]
        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += result.home_goals
        home["goals_against"] += result.away_goals
        away["goals_for"] += result.away_goals
        away["goals_against"] += result.home_goals
        if result.home_goals > result.away_goals:
            home["won"] += 1
            away["lost"] += 1
            home["points"] += 3
        elif result.home_goals < result.away_goals:
            away["won"] += 1
            home["lost"] += 1
            away["points"] += 3
        else:
            home["drawn"] += 1
            away["drawn"] += 1
            home["points"] += 1
            away["points"] += 1
    for row in rows.values():
        row["goal_difference"] = row["goals_for"] - row["goals_against"]
    ordered = sorted(
        rows.values(),
        key=lambda r: (r["points"], r["goal_difference"], r["goals_for"], r["team"]),
        reverse=True,
    )
    rank_keys = defaultdict(list)
    for row in ordered:
        rank_keys[(row["points"], row["goal_difference"], row["goals_for"])].append(row)
    for tied in rank_keys.values():
        if len(tied) > 1:
            for row in tied:
                row["tie_unresolved"] = True
    return ordered


def all_group_tables(results: list[MatchResult]) -> dict[str, list[dict]]:
    grouped: dict[str, list[MatchResult]] = defaultdict(list)
    for result in results:
        grouped[result.group_code].append(result)
    return {group: group_table(group_results) for group, group_results in grouped.items()}


def best_thirds(tables: dict[str, list[dict]]) -> list[dict]:
    thirds = []
    for group, rows in tables.items():
        if len(rows) >= 3:
            row = dict(rows[2])
            row["source_group"] = group
            thirds.append(row)
    return sorted(
        thirds,
        key=lambda r: (r["points"], r["goal_difference"], r["goals_for"], r["team"]),
        reverse=True,
    )


def combination_key(groups: list[str] | tuple[str, ...]) -> str:
    return "".join(sorted(groups))


def validate_third_place_mapping(mapping: dict[str, dict[str, str]]) -> None:
    expected = {combination_key(c) for c in combinations(GROUPS, 8)}
    actual = set(mapping)
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        raise ValueError(f"third-place mapping mismatch: {len(missing)} missing, {len(extra)} extra")
    for key, slots in mapping.items():
        if set(slots) != {"1A", "1B", "1D", "1E", "1G", "1I", "1K", "1L"}:
            raise ValueError(f"bad destination slots for {key}")
