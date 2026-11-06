"""Deterministic synthetic regression tests for frozen model robustness audit."""
import numpy as np
import pytest

from beyond_the_whistle.wp_robustness import (
    game_cluster_intervals,
    reliability,
    run_audit,
    subset_masks,
)


def rows(n_games=40):
    result = []
    for game in range(n_games):
        for sec in (12, 55, 90, 200, 450):
            margin = (game % 13) - 6
            result.append({
                "game_id": f"00224{game:05d}", "split": "test",
                "period": 4, "seconds_remaining": sec,
                "home_margin": margin, "home_win": int(game % 2 == 0),
            })
    return result


def test_subset_masks_and_game_clustering():
    sample = rows()
    masks = subset_masks(sample)
    assert masks["all_q4_and_ot"].sum() == len(sample)
    assert masks["clock_0_30"].sum() == 40
    assert masks["clock_30_60"].sum() == 40
    assert masks["clock_60_120"].sum() == 40
    assert masks["clock_120_300"].sum() == 40
    assert masks["clock_over_300"].sum() == 40
    assert masks["l2m_close_margin_5"].sum() > 0


def test_paired_cluster_interval_when_calibration_is_exactly_unchanged():
    sample = rows()
    p = np.linspace(0.05, 0.95, len(sample))
    intervals = game_cluster_intervals(sample, p, p, repetitions=120, seed=11)
    assert intervals["games"] == 40
    for key in ("delta_brier_cal_minus_raw", "delta_log_loss_cal_minus_raw"):
        assert intervals["metrics"][key] == {
            "point": 0.0, "ci95_lower": 0.0, "ci95_upper": 0.0,
        }
    again = game_cluster_intervals(sample, p, p, repetitions=120, seed=11)
    assert intervals == again


def test_bootstrap_uses_whole_games_not_rows():
    sample = [
        {"game_id": "A", "home_win": 1},
        {"game_id": "A", "home_win": 1},
        {"game_id": "A", "home_win": 1},
        {"game_id": "B", "home_win": 0},
        {"game_id": "C", "home_win": 0},
    ]
    raw = np.full(5, 0.5)
    cal = np.array([1, 1, 1, 0, 0], dtype=float)
    result = game_cluster_intervals(sample, raw, cal, repetitions=100, seed=44)
    assert result["games"] == 3
    assert result["metrics"]["raw_brier"]["point"] == pytest.approx(0.25)
    assert result["metrics"]["calibrated_brier"]["point"] < 1e-9


def test_strata_and_reliability_conserve_state_counts():
    sample = rows()
    raw = np.array([0.8 if r["home_win"] else 0.2 for r in sample])
    calibrated = np.clip(raw + 0.03, 0, 1)
    report, summary, bins = run_audit(sample, raw, calibrated, repetitions=30)
    assert report["all_q4_and_ot"]["games"] == 40
    assert report["all_q4_and_ot"]["cluster_bootstrap"]["games"] == 40
    assert report["overtime"]["insufficient_data"]
    assert len(summary) >= 10
    assert sum(x["states"] for x in bins
               if x["stratum"] == "all_q4_and_ot" and x["model"] == "raw") == len(sample)
    stats, bin_rows = reliability(sample, raw, "all", "raw")
    assert sum(r["states"] for r in bin_rows) == len(sample)
    assert 0 <= stats["ece_10_bin_game_balanced"] <= 1


def test_test_season_guard():
    sample = rows(3)
    sample[0]["split"] = "train"
    with pytest.raises(ValueError, match="test-season"):
        run_audit(sample, np.full(15, 0.5), np.full(15, 0.5), repetitions=20)


def test_mismatched_prediction_length():
    sample = rows(3)
    with pytest.raises(ValueError, match="length"):
        run_audit(sample, np.full(14, 0.5), np.full(15, 0.5), repetitions=20)
