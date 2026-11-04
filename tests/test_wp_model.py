"""Regression checks on synthetic games; no synthetic examples reported as NBA metrics."""
import csv

import numpy as np
import pytest

from beyond_the_whistle.wp_model import (
    build,
    calibration_bins,
    feature_matrix,
    game_weights,
    read_states,
    selection_calibration_games,
    train_and_evaluate,
)


def examples() -> list[dict]:
    rows = []
    for season, split in (
        (2021, "train"), (2022, "train"),
        (2023, "validation"), (2024, "test"),
    ):
        for game in range(12):
            gid = f"{season:04d}{game:06d}"
            for seconds in (110, 60, 12):
                margin = game % 9 - 4
                rows.append({
                    "game_id": gid, "season_start_year": season, "split": split,
                    "period": 4, "seconds_remaining": seconds,
                    "home_score": 100 + max(margin, 0),
                    "away_score": 100 + max(-margin, 0),
                    "home_margin": margin, "seconds_into_period": 720 - seconds,
                    "home_win": int((game + season) % 3 != 0),
                })
    return rows


def test_validation_partition_disjoint_and_features_finite():
    rows = examples()
    selection, calibration = selection_calibration_games(
        [r for r in rows if r["split"] == "validation"]
    )
    assert {r["game_id"] for r in selection}.isdisjoint(
        {r["game_id"] for r in calibration}
    )
    assert feature_matrix(rows).shape == (len(rows), 8)
    assert np.isclose(game_weights(rows).sum(), 48)


def test_trains_model_and_calibrates_without_test_selection():
    report, bundle, bins, predictions = train_and_evaluate(examples())
    assert report["selected_model"] in {"logistic", "hist_gradient_boosting"}
    assert 0 <= report["test_metrics"]["calibrated"]["game_balanced_brier"] <= 1
    assert report["validation"]["game_overlap"] == 0
    assert sum(b["states"] for b in bins) == 36
    assert len(predictions) == 36
    assert 0 < bundle["calibrator"].predict_proba([[0]])[0, 1] < 1


def test_writes_report_calibration_predictions_and_fitted_model(tmp_path):
    rows = examples()
    source = tmp_path / "states.csv"
    with source.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = build(source, tmp_path / "output")
    assert report["status"] == "trained_calibrated_and_evaluated_out_of_time"
    for file in (
        "wp_baseline.joblib", "wp_test_predictions.csv",
        "wp_test_calibration.csv", "wp_model_report.json",
    ):
        assert (tmp_path / "output" / file).is_file()


def test_game_overlap_and_inconsistent_splits_rejected(tmp_path):
    rows = examples()
    rows[1]["split"] = "test"
    file = tmp_path / "bad.csv"
    with file.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):
        read_states(file)


def test_calibration_bins_account_for_every_row():
    rows = examples()[:12]
    probs = np.linspace(0.001, 0.999, len(rows))
    assert sum(b["states"] for b in calibration_bins(rows, probs)) == len(rows)
