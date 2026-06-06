from itertools import combinations

from rules import GROUPS, MatchResult, best_thirds, combination_key, group_table, score_prediction, validate_third_place_mapping


def test_score_prediction_exact_margin_result_and_miss():
    assert score_prediction(2, 1, 2, 1) == 5
    assert score_prediction(3, 1, 2, 0) == 3
    assert score_prediction(2, 0, 1, 0) == 1
    assert score_prediction(0, 1, 1, 0) == 0


def test_score_prediction_tied_knockout_advancer():
    assert score_prediction(1, 1, 1, 1, "Brazil", "Brazil") == 5
    assert score_prediction(1, 1, 1, 1, "Spain", "Brazil") == 3
    assert score_prediction(2, 2, 1, 1, "Brazil", "Brazil") == 3
    assert score_prediction(2, 2, 1, 1, "Spain", "Brazil") == 0


def test_group_table_orders_and_marks_unresolved_ties():
    rows = group_table(
        [
            MatchResult("A", "A1", "A2", 2, 0),
            MatchResult("A", "A1", "A3", 0, 0),
            MatchResult("A", "A2", "A4", 3, 0),
        ]
    )
    assert rows[0]["team"] == "A1"
    assert rows[0]["points"] == 4
    assert rows[0]["goal_difference"] == 2


def test_group_table_marks_unresolved_ties():
    rows = group_table([MatchResult("A", "A3", "A4", 1, 1)])
    tied = [row for row in rows if row["tie_unresolved"]]
    assert {row["team"] for row in tied} == {"A3", "A4"}


def test_best_thirds_ranking():
    tables = {
        "A": [{"team": "A1"}, {"team": "A2"}, {"team": "A3", "points": 4, "goal_difference": 1, "goals_for": 5}],
        "B": [{"team": "B1"}, {"team": "B2"}, {"team": "B3", "points": 4, "goal_difference": 2, "goals_for": 3}],
    }
    assert best_thirds(tables)[0]["team"] == "B3"


def test_third_place_mapping_validation_shape():
    slots = {"1A": "3A", "1B": "3B", "1D": "3C", "1E": "3D", "1G": "3E", "1I": "3F", "1K": "3G", "1L": "3H"}
    mapping = {combination_key(groups): slots for groups in combinations(GROUPS, 8)}
    validate_third_place_mapping(mapping)
