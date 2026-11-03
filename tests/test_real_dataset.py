"""Offline unit tests on representative shapes, not assertions of real NBA accuracy."""
from beyond_the_whistle.build_real_dataset import (
    category,
    normalize_id,
    parse_clock,
    parse_period,
    prepare,
)


def test_l2m_period_and_clock():
    assert parse_period("Q4") == 4
    assert parse_period("OT") == 5
    assert parse_period("OT2") == 6
    assert parse_clock("01:52.0") == 112.0
    assert normalize_id("2240061") == "0002240061"


def test_category():
    assert category("Foul: Shooting") == "foul"
    assert category("Violation: Traveling") == "violation_or_turnover"


def test_match_metadata_and_foul_type_with_realistic_schema():
    gid = "0022400061"
    l2m = [{"season": "2025", "gid": gid, "decision": "IC",
            "period": "Q4", "time": "01:52.0", "call_type": "Foul: Shooting",
            "date": "2024-10-22", "home": "BOS", "away": "NYK"}]
    pbp = [{"game_id": gid, "period": "4", "clock": "01:52",
            "msg_type": "6", "event_num": "123", "game_date": "2024-10-22",
            "team_home": "BOS", "team_away": "NYK"}]
    matches, audit = prepare(l2m, pbp)
    assert matches[0]["status"] == "unique_clock_type_candidate_unverified"
    assert matches[0]["pbp_event_num"] == "123"
    assert audit["metadata_consistent_games"] == 1


def test_noncall_never_fabricates_a_whistle():
    l2m = [{"season": "2025", "gid": "0022400061", "decision": "INC",
            "period": "Q4", "time": "01:52.0", "call_type": "Foul: Shooting",
            "date": "2024-10-22", "home": "BOS", "away": "NYK"}]
    pbp = [{"game_id": "0022400061", "period": "4", "clock": "01:52",
            "msg_type": "6", "event_num": "123", "game_date": "2024-10-22",
            "team_home": "BOS", "team_away": "NYK"}]
    matches, _ = prepare(l2m, pbp)
    assert matches[0]["status"] == "noncall_not_in_pbp"


def test_disagreement_prevents_event_match():
    l2m = [{"season": "2025", "gid": "0022400061", "decision": "CC",
            "period": "Q4", "time": "01:52.0", "call_type": "Foul",
            "date": "2024-10-23", "home": "BOS", "away": "NYK"}]
    pbp = [{"game_id": "0022400061", "period": "4", "clock": "01:52",
            "msg_type": "6", "event_num": "123", "game_date": "2024-10-22",
            "team_home": "BOS", "team_away": "NYK"}]
    matches, audit = prepare(l2m, pbp)
    assert matches[0]["status"] == "game_metadata_disagreement"
    assert audit["metadata_consistent_games"] == 0
