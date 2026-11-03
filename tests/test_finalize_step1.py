"""Deterministic Step 1 tests for independent, source-aware validation."""
import pytest

from beyond_the_whistle.finalize_step1 import (
    canonical_l2m,
    compare_official,
    normalize_grade,
    normalize_label,
    read_espn_play_in,
)


def test_official_canonical_uses_tenths_and_period():
    community = {"period": "Q4", "time": "01:52.0",
                 "call_type": "Foul: Shooting", "decision": "CNC"}
    official = {"PeriodName": "Q4", "PCTime": "01:52.0",
                "CallType": "Foul: Shooting", "CallRatingName": "NCC"}
    assert canonical_l2m(community, False) == canonical_l2m(official, True)
    assert normalize_grade("NCI*") == "INC"
    assert normalize_label("  Foul:  Shooting ") == "foul: shooting"


def test_official_multiset_detects_missing_and_changed_grade():
    community = [
        {"period": "Q4", "time": "01:52.0",
         "call_type": "Foul: Shooting", "decision": "CC"},
        {"period": "Q4", "time": "01:52.0",
         "call_type": "Foul: Shooting", "decision": "CC"},
    ]
    official = {"game": [{"GameId": "0052400121"}], "l2m": [
        {"PeriodName": "Q4", "PCTime": "01:52.0",
         "CallType": "Foul: Shooting", "CallRatingName": "CC"},
        {"PeriodName": "Q4", "PCTime": "01:52.0",
         "CallType": "Foul: Shooting", "CallRatingName": "IC"},
    ]}
    result = compare_official("0052400121", community, official)
    assert not result["exact_multiset_match"]
    assert result["matching_rows"] == 1
    assert result["missing_from_community"] == 1
    assert result["extra_in_community"] == 1


def test_official_gameid_must_match():
    with pytest.raises(ValueError, match="mismatch"):
        compare_official("0052400121", [], {"game": [{"GameId": "0052400201"}], "l2m": []})


def test_playin_espn_feed_is_source_checked():
    payload = {
        "header": {"competitions": [{"competitors": [
            {"homeAway": "home", "team": {"abbreviation": "GSW"}},
            {"homeAway": "away", "team": {"abbreviation": "MEM"}},
        ]}]},
        "plays": [{"period": {"number": 4}, "clock": {"displayValue": "1:40"},
                   "sequenceNumber": str(i),
                   "text": "Personal Foul by Curry", "type": {"text": "Foul"}}
                  for i in range(120)],
    }
    rows, metadata = read_espn_play_in("0052400121", payload)
    assert len(rows) == 120
    assert rows[0]["msg_type"] == "6"
    assert rows[0]["game_date"] == "2025-04-15"
    assert metadata["actions_available"] == 120


def test_espn_mismatched_home_away_is_rejected():
    payload = {
        "header": {"competitions": [{"competitors": [
            {"homeAway": "home", "team": {"abbreviation": "MEM"}},
            {"homeAway": "away", "team": {"abbreviation": "GSW"}},
        ]}]},
        "plays": [{"period": {"number": 4}, "clock": {"displayValue": "1:40"}}
                  for _ in range(120)],
    }
    with pytest.raises(ValueError, match="team mismatch"):
        read_espn_play_in("0052400121", payload)
