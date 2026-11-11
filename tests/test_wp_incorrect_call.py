import pytest

from beyond_the_whistle.wp_incorrect_call import compare_scenarios


def test_corrected_minus_observed_uses_affected_team(monkeypatch):
    def predict(bundle, state, *, probability_version):
        return {"away_win_probability": 0.7 if state.home_score == 100 else 0.4}

    monkeypatch.setattr("beyond_the_whistle.wp_incorrect_call.infer", predict)
    observed = {"period": 4, "seconds_remaining": 30, "home_score": 102, "away_score": 101}
    case = {
        "hypothetical": True,
        "affected_team": "away",
        "observed": observed,
        "alternatives": [
            {"assumption": "Remove two converted free throws",
             "state": {**observed, "home_score": 100}},
        ],
    }
    result = compare_scenarios({}, case, {}, "platt")
    assert result["observed_win_probability"] == 0.4
    assert result["delta_range_percentage_points"] == pytest.approx([30, 30])
    assert result["official_record"] is None
    assert result["causal_officiating_effect"] is False


def test_real_case_requires_documented_verification():
    records = {"12": {"game_id": "0022400001"}}
    case = {"l2m_record": "12", "game_id": "0022400001"}
    with pytest.raises(ValueError, match="video_reference"):
        compare_scenarios({}, case, records, "raw")
    with pytest.raises(ValueError, match="official IC record"):
        compare_scenarios({}, {**case, "game_id": "wrong"}, records, "raw")
