import pytest

from beyond_the_whistle.wp_possession import score_cases


def test_score_uses_corrected_team_perspective():
    case = {
        "home_team": "NYK", "away_team": "CLE", "home_score": 100, "away_score": 106,
        "period": 4, "seconds_remaining": 12.1, "observed_possession": "NYK",
        "corrected_possession": "CLE",
    }
    model = {"intercept": 0, "coefficients": [0, 0, 0, 0, 1, 0]}
    [result] = score_cases(model, [case])
    assert result["estimated_team"] == "CLE"
    assert result["observed_wp_pct"] == pytest.approx(26.894142)
    assert result["corrected_wp_pct"] == pytest.approx(73.105858)
    with pytest.raises(ValueError, match="opposing"):
        score_cases(model, [{**case, "corrected_possession": "NYK"}])
