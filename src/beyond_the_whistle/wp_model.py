"""Train and independently evaluate calibrated Q4/OT NBA home-win baselines."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from beyond_the_whistle.wp_dataset import FEATURES

MODEL_FEATURES = (*FEATURES, "score_total", "margin_per_sqrt_minute")
SEASON_SPLITS = {2021: "train", 2022: "train", 2023: "validation", 2024: "test"}
SEED = 226


def read_states(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    required = {"game_id", "split", "season_start_year", "home_win", *FEATURES}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("State data empty or missing required columns")
    seen = {}
    for row in rows:
        gid = row["game_id"]
        split, season, outcome = row["split"], int(row["season_start_year"]), int(row["home_win"])
        if SEASON_SPLITS.get(season) != split or outcome not in (0, 1):
            raise ValueError("Invalid chronological split or outcome")
        entry = (split, season, outcome)
        if seen.setdefault(gid, entry) != entry:
            raise ValueError("A game crosses splits or has inconsistent outcome")
        if float(row["seconds_remaining"]) <= 0:
            raise ValueError("Final-buzzer state leakage")
        if int(row["home_score"]) - int(row["away_score"]) != int(row["home_margin"]):
            raise ValueError("Score margin mismatch")
    return rows


def feature_matrix(rows: list[dict]) -> np.ndarray:
    """Features are visible immediately after each play; no outcome/future score."""
    records = []
    for row in rows:
        base = [float(row[name]) for name in FEATURES]
        margin, seconds = float(row["home_margin"]), float(row["seconds_remaining"])
        records.append([
            *base, float(row["home_score"]) + float(row["away_score"]),
            margin / math.sqrt(max(seconds, 1.0) / 60.0),
        ])
    matrix = np.asarray(records, dtype=np.float64)
    if not np.isfinite(matrix).all():
        raise ValueError("Non-finite feature")
    return matrix


def game_weights(rows: list[dict]) -> np.ndarray:
    counts = Counter(row["game_id"] for row in rows)
    return np.asarray([1.0 / counts[row["game_id"]] for row in rows])


def selection_calibration_games(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Nonoverlapping earlier/later game-ID groups within the 2023-24 validation season."""
    ids = sorted({row["game_id"] for row in rows})
    if len(ids) < 10:
        raise ValueError("Too few validation games")
    first = set(ids[:int(0.6 * len(ids))])
    a = [row for row in rows if row["game_id"] in first]
    b = [row for row in rows if row["game_id"] not in first]
    return a, b


def clipped(values: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float), 1e-6, 1 - 1e-6)


def logit(values: np.ndarray) -> np.ndarray:
    probabilities = clipped(values)
    return np.log(probabilities / (1.0 - probabilities)).reshape(-1, 1)


def evaluate(rows: list[dict], values: np.ndarray) -> dict:
    target = np.asarray([int(row["home_win"]) for row in rows])
    pred = clipped(values)
    weights = game_weights(rows)
    if len(pred) != len(target):
        raise ValueError("Prediction count mismatch")
    result = {
        "states": len(rows),
        "games": len({row["game_id"] for row in rows}),
        "brier": float(brier_score_loss(target, pred)),
        "log_loss": float(log_loss(target, pred, labels=[0, 1])),
        "game_balanced_brier": float(brier_score_loss(target, pred, sample_weight=weights)),
        "game_balanced_log_loss": float(log_loss(target, pred, labels=[0, 1], sample_weight=weights)),
        "observed_home_win_rate": float(np.mean(target)),
        "mean_predicted_probability": float(np.mean(pred)),
    }
    result["auc"] = float(roc_auc_score(target, pred)) if len(set(target)) == 2 else None
    return result


def calibration_bins(rows: list[dict], values: np.ndarray) -> list[dict]:
    pred = clipped(values)
    target = np.asarray([int(row["home_win"]) for row in rows])
    result = []
    for idx in range(10):
        mask = (pred >= idx / 10) & (pred < (idx + 1) / 10)
        n = int(mask.sum())
        result.append({
            "bin": idx + 1, "lower": idx / 10, "upper": (idx + 1) / 10,
            "states": n,
            "mean_predicted": float(pred[mask].mean()) if n else None,
            "observed_home_win": float(target[mask].mean()) if n else None,
        })
    return result


def train_and_evaluate(rows: list[dict]) -> tuple[dict, dict, list[dict], list[dict]]:
    groups = {s: [r for r in rows if r["split"] == s]
              for s in ("train", "validation", "test")}
    if any(not group for group in groups.values()):
        raise ValueError("Training, validation and test must each be nonempty")
    train, validation, test = (groups[key] for key in ("train", "validation", "test"))
    selection, calibration = selection_calibration_games(validation)
    x_train = feature_matrix(train)
    y_train = np.asarray([int(row["home_win"]) for row in train])
    weights = game_weights(train)
    if len(set(y_train)) < 2:
        raise ValueError("Training requires both outcomes")
    logistic = make_pipeline(
        StandardScaler(), LogisticRegression(C=1.0, max_iter=1000, random_state=SEED)
    )
    logistic.fit(x_train, y_train, logisticregression__sample_weight=weights)
    boosted = HistGradientBoostingClassifier(
        max_iter=130, max_leaf_nodes=15, learning_rate=0.06,
        min_samples_leaf=75, l2_regularization=2.0, random_state=SEED,
    )
    boosted.fit(x_train, y_train, sample_weight=weights)
    models = {"logistic": logistic, "hist_gradient_boosting": boosted}
    candidates = [{
        "name": name,
        "selection_metrics": evaluate(
            selection, model.predict_proba(feature_matrix(selection))[:, 1]
        ),
    } for name, model in models.items()]
    candidates.sort(key=lambda c: (c["selection_metrics"]["game_balanced_brier"], c["name"]))
    name = candidates[0]["name"]
    model = models[name]
    p_cal = model.predict_proba(feature_matrix(calibration))[:, 1]
    y_cal = np.asarray([int(row["home_win"]) for row in calibration])
    calibrator = LogisticRegression(C=100.0, max_iter=1000, random_state=SEED)
    calibrator.fit(logit(p_cal), y_cal, sample_weight=game_weights(calibration))
    p_test_raw = model.predict_proba(feature_matrix(test))[:, 1]
    p_test = calibrator.predict_proba(logit(p_test_raw))[:, 1]
    home_rate = float(np.average(y_train, weights=weights))
    close_indices = [
        idx for idx, row in enumerate(test)
        if float(row["seconds_remaining"]) <= 120 and abs(int(row["home_margin"])) <= 5
    ]
    report = {
        "status": "trained_calibrated_and_evaluated_out_of_time",
        "selected_model": name,
        "model_candidates": candidates,
        "validation": {
            "model_selection_games": len({r["game_id"] for r in selection}),
            "calibration_games": len({r["game_id"] for r in calibration}),
            "game_overlap": 0,
            "selection": "First 60% of sorted 2023-24 game IDs",
            "calibration": "Remaining 40%; logistic sigmoid Platt scaling on raw-model log odds",
        },
        "training_seasons": [2021, 2022], "test_season": 2024,
        "features": list(MODEL_FEATURES),
        "test_metrics": {
            "constant_train_home_rate": evaluate(test, np.full(len(test), home_rate)),
            "uncalibrated": evaluate(test, p_test_raw),
            "calibrated": evaluate(test, p_test),
            "late_close_calibrated": evaluate(
                [test[idx] for idx in close_indices], p_test[close_indices]
            ) if close_indices else None,
        },
        "limitations": [
            "Snapshots from the same game are dependent; game-balanced Brier is primary",
            "Models predict post-play home win probability, not officiating causal effects",
            "Possession, lineups, timeouts and referee context not included",
            "Test season not used in model choice or calibration",
        ],
    }
    predictions = [{
        "game_id": row["game_id"], "period": row["period"],
        "seconds_remaining": row["seconds_remaining"],
        "home_margin": row["home_margin"], "home_win": row["home_win"],
        "predicted_home_win": round(float(prob), 8),
    } for row, prob in zip(test, p_test, strict=True)]
    return report, {
        "model": model, "calibrator": calibrator,
        "feature_names": MODEL_FEATURES, "selected_model": name,
    }, calibration_bins(test, p_test), predictions


def build(data_path: Path, output: Path) -> dict:
    rows = read_states(data_path)
    report, fitted, bins, predictions = train_and_evaluate(rows)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "wp_baseline.joblib"
    joblib.dump(fitted, path, compress=3)
    report["model_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    report["dataset_sha256"] = hashlib.sha256(data_path.read_bytes()).hexdigest()
    for filename, data in (("wp_test_predictions.csv", predictions),
                           ("wp_test_calibration.csv", bins)):
        with (output / filename).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    (output / "wp_model_report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "selected_model": report["selected_model"],
        "test_metrics": report["test_metrics"],
    }, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and test NBA Q4 WP baseline")
    parser.add_argument("--data", type=Path,
                        default=Path("data/win_probability/wp_q4_states_2021_2024.csv"))
    parser.add_argument("--output", type=Path, default=Path("models/win_probability"))
    args = parser.parse_args()
    build(args.data, args.output)


if __name__ == "__main__":
    main()
