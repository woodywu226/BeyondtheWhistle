"""Frozen Step 2 win-probability inference for valid post-action NBA states.

This interface is NOT an officiating-error counterfactual simulator. Model
features do not encode possession, bonus, pending free throws or timeouts.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import joblib
import numpy as np

from beyond_the_whistle.wp_model import MODEL_FEATURES, logit


@dataclass(frozen=True)
class GameState:
    period: int
    seconds_remaining: float
    home_score: int
    away_score: int

    def validate(self) -> None:
        if isinstance(self.period, bool) or not isinstance(self.period, int):
            raise ValueError("period must be an integer")
        if self.period < 4 or self.period > 20:
            raise ValueError("Model only supports Q4 and overtime periods up to 20")
        if (isinstance(self.seconds_remaining, bool)
                or not isinstance(self.seconds_remaining, (int, float))
                or not math.isfinite(self.seconds_remaining)):
            raise ValueError("seconds_remaining must be a finite number")
        duration = 720 if self.period == 4 else 300
        if not 0 < self.seconds_remaining <= duration:
            raise ValueError("Clock must be strictly after start and before final buzzer")
        for name, value in (("home_score", self.home_score), ("away_score", self.away_score)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 300:
                raise ValueError(f"{name} must be a nonnegative integer ≤300")

    def features(self) -> np.ndarray:
        self.validate()
        duration = 720 if self.period == 4 else 300
        margin = self.home_score - self.away_score
        vector = [
            self.period, self.seconds_remaining, self.home_score,
            self.away_score, margin, duration - self.seconds_remaining,
            self.home_score + self.away_score,
            margin / math.sqrt(max(self.seconds_remaining, 1.0) / 60.0),
        ]
        if len(vector) != len(MODEL_FEATURES):
            raise RuntimeError("Feature layout has changed")
        return np.asarray([vector], dtype=np.float64)


def infer(bundle: dict, state: GameState, *, probability_version: str = "platt") -> dict:
    """Use the published frozen model; never fit calibrators on inference data."""
    if probability_version not in ("raw", "platt"):
        raise ValueError("probability_version must be raw or platt")
    if tuple(bundle.get("feature_names", ())) != tuple(MODEL_FEATURES):
        raise ValueError("Model feature schema incompatible with this code")
    matrix = state.features()
    raw = float(bundle["model"].predict_proba(matrix)[0, 1])
    if not math.isfinite(raw) or not 0 <= raw <= 1:
        raise ValueError("Model returned invalid probability")
    raw = float(np.clip(raw, 1e-6, 1 - 1e-6))
    probability = raw
    if probability_version == "platt":
        probability = float(bundle["calibrator"].predict_proba(logit(np.array([raw])))[0, 1])
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Calibrator returned invalid probability")
    return {
        "game_state": asdict(state),
        "home_win_probability": probability,
        "away_win_probability": 1 - probability,
        "probability_version": probability_version,
        "model": bundle.get("selected_model", "unknown"),
        "prediction_timing": "post_action",
        "causal_officiating_effect": False,
        "warning": (
            "Conditional predictive estimate only. Not an identified referee-error "
            "effect or a valid substitute for a verified pre-decision counterfactual."
        ),
    }


def load_trusted_bundle(path: Path) -> dict:
    """Only load joblib model artifacts from trusted sources (pickle can execute code)."""
    result = joblib.load(path)
    if not isinstance(result, dict) or not all(
        key in result for key in ("model", "calibrator", "feature_names")
    ):
        raise ValueError("Unexpected model bundle")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Predict post-action NBA Q4/OT win probability with frozen Step 2 model"
    )
    parser.add_argument("--period", type=int, required=True)
    parser.add_argument("--seconds-remaining", type=float, required=True)
    parser.add_argument("--home-score", type=int, required=True)
    parser.add_argument("--away-score", type=int, required=True)
    parser.add_argument("--probability-version", choices=("raw", "platt"), default="platt")
    parser.add_argument("--model", type=Path,
                        default=Path("models/win_probability/wp_baseline.joblib"))
    args = parser.parse_args()
    state = GameState(
        period=args.period, seconds_remaining=args.seconds_remaining,
        home_score=args.home_score, away_score=args.away_score,
    )
    state.validate()  # Fail before loading pickle from path for invalid inputs.
    print(json.dumps(infer(load_trusted_bundle(args.model), state,
                          probability_version=args.probability_version), indent=2))


if __name__ == "__main__":
    main()
