"""Unit tests for frozen Step 2 inference contract."""
import numpy as np
import pytest

from beyond_the_whistle.wp_inference import GameState, infer
from beyond_the_whistle.wp_model import MODEL_FEATURES


class StubModel:
    def predict_proba(self, matrix):
        assert matrix.shape == (1, len(MODEL_FEATURES))
        return np.array([[0.25, 0.75]])


class StubCalibrator:
    def predict_proba(self, matrix):
        assert matrix.shape == (1, 1)
        return np.array([[0.2, 0.8]])


def bundle():
    return {
        "model": StubModel(), "calibrator": StubCalibrator(),
        "feature_names": MODEL_FEATURES, "selected_model": "hist_gradient_boosting",
    }


def test_exact_feature_schema_and_post_action_clock():
    state = GameState(period=4, seconds_remaining=95, home_score=103, away_score=101)
    matrix = state.features()
    assert matrix.shape == (1, 8)
    assert matrix[0, :6].tolist() == [4, 95, 103, 101, 2, 625]
    assert matrix[0, 6] == 204


def test_overtime_duration_and_inference_versions():
    state = GameState(period=5, seconds_remaining=230, home_score=110, away_score=110)
    assert state.features()[0, 5] == 70
    raw = infer(bundle(), state, probability_version="raw")
    platt = infer(bundle(), state, probability_version="platt")
    assert raw["home_win_probability"] == pytest.approx(0.75)
    assert platt["home_win_probability"] == pytest.approx(0.8)
    assert platt["away_win_probability"] == pytest.approx(0.2)
    assert platt["prediction_timing"] == "post_action"
    assert platt["causal_officiating_effect"] is False


@pytest.mark.parametrize("state", [
    GameState(3, 10, 100, 100),
    GameState(4, 0, 100, 100),
    GameState(4, 721, 100, 100),
    GameState(5, 301, 100, 100),
    GameState(4, float("nan"), 100, 100),
    GameState(4, float("inf"), 100, 100),
    GameState(4, 10, -1, 100),
    GameState(4, 10, 100, 301),
    GameState(4, 10, True, 100),
])
def test_reject_invalid_game_state(state):
    with pytest.raises(ValueError):
        state.features()


def test_guard_feature_schema_and_inference_version():
    state = GameState(4, 90, 100, 99)
    invalid = bundle()
    invalid["feature_names"] = ("wrong",)
    with pytest.raises(ValueError, match="schema"):
        infer(invalid, state)
    with pytest.raises(ValueError, match="probability_version"):
        infer(bundle(), state, probability_version="recalibrated")


def test_frozen_model_reference_reproducible():
    from pathlib import Path

    from beyond_the_whistle.wp_inference import load_trusted_bundle

    model = Path("models/win_probability/wp_baseline.joblib")
    if not model.is_file():
        pytest.skip("Committed real NBA model not available outside repository checkout")
    fitted = load_trusted_bundle(model)
    state = GameState(4, 60, 100, 100)
    a = infer(fitted, state)
    b = infer(fitted, state)
    assert a == b
    assert 0 < a["home_win_probability"] < 1
