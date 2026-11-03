import pytest

from beyond_the_whistle.ingest_pbp import normalize, parse_clock
from beyond_the_whistle.match_events import l2m_game_id, match_events


def test_clock_formats():
    assert parse_clock("PT1M02.50S") == 62.5
    assert parse_clock("01:02.5") == 62.5
    with pytest.raises(ValueError):
        parse_clock("bad")


def test_normalize_live_v3_payload():
    payload = {"game": {"gameId": "0022400001", "actions": [
        {"period": 4, "clock": "PT1M02.50S", "actionId": 25,
         "actionType": "foul", "description": "Personal foul", "teamId": 1,
         "scoreHome": "99", "scoreAway": "98"}
    ]}}
    result = normalize(payload, "0022400001")
    assert result[0]["clock_seconds"] == 62.5
    assert result[0]["game_id"] == "0022400001"
    with pytest.raises(ValueError, match="mismatch"):
        normalize(payload, "0022400002")


def test_normalize_stats_resultsets():
    payload = {"resultSets": [{"name": "PlayByPlay",
        "headers": ["gameId", "period", "clock", "actionNumber", "actionType"],
        "rowSet": [["0022400001", 4, "PT1M00S", 3, "foul"]]}]}
    assert normalize(payload, "0022400001")[0]["action_id"] == "3"


def test_temporal_candidate_is_not_verified():
    pbp = [{"game_id": "0022400001", "period": 4, "clock_seconds": 62.0,
            "action_id": "9", "action_type": "foul", "description": "Foul"}]
    l2m = [{"gid": "0022400001", "period": "4", "time": "1:02",
            "decision": "IC", "call_type": "Foul: Personal"}]
    result = match_events(l2m, pbp)
    assert result[0]["status"] == "unique_temporal_candidate_unverified"
    assert result[0]["action_id"] == "9"


def test_noncall_never_automatically_verified():
    pbp = [{"game_id": "0022400001", "period": 4, "clock_seconds": 62,
            "action_id": "9", "action_type": "foul", "description": "Foul"}]
    l2m = [{"gid": "0022400001", "period": "4", "time": "1:02",
            "decision": "INC", "call_type": "Foul"}]
    assert match_events(l2m, pbp)[0]["status"] == "noncall_requires_video_review"


def test_ambiguity_retained():
    pbp = [{"game_id": "0022400001", "period": 4, "clock_seconds": 62,
            "action_id": str(i), "action_type": "foul"} for i in range(2)]
    row = {"GAME_ID": "0022400001", "period": "4",
           "time": "1:02", "decision": "CC"}
    result = match_events([row], pbp)
    assert result[0]["status"] == "ambiguous_temporal_candidates"
    assert result[0]["candidate_count"] == 2


def test_game_id_preserves_zeroes():
    assert l2m_game_id({"gid": "22400001"}) == "0022400001"
