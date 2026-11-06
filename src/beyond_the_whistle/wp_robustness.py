"""Step 2.3: audit temporal/clutch calibration without refitting on the held-out season.

All metrics, plots/tables and bootstrap intervals refer to the already-frozen
Step 2.2 model. Test-set diagnostics are NOT a model-selection protocol.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np

from beyond_the_whistle.wp_model import (
    clipped,
    evaluate,
    feature_matrix,
    game_weights,
    logit,
    read_states,
)

RNG_SEED = 226
BOOTSTRAPS = 1000
PROBABILITY_BINS = 10


def subset_masks(rows: list[dict]) -> dict[str, np.ndarray]:
    seconds = np.array([float(row["seconds_remaining"]) for row in rows])
    margins = np.abs(np.array([float(row["home_margin"]) for row in rows]))
    periods = np.array([int(row["period"]) for row in rows])
    return {
        "all_q4_and_ot": np.ones(len(rows), dtype=bool),
        "q4_only": periods == 4,
        "overtime": periods > 4,
        "clock_0_30": seconds <= 30,
        "clock_30_60": (seconds > 30) & (seconds <= 60),
        "clock_60_120": (seconds > 60) & (seconds <= 120),
        "clock_120_300": (seconds > 120) & (seconds <= 300),
        "clock_over_300": seconds > 300,
        "margin_0_2": margins <= 2,
        "margin_3_5": (margins > 2) & (margins <= 5),
        "margin_6_10": (margins > 5) & (margins <= 10),
        "margin_over_10": margins > 10,
        "l2m_close_margin_5": (seconds <= 120) & (margins <= 5),
        "last_30s_margin_3": (seconds <= 30) & (margins <= 3),
        "l2m_margin_over_5": (seconds <= 120) & (margins > 5),
    }


def reliability(rows: list[dict], probabilities: np.ndarray, group: str,
                version: str) -> tuple[dict, list[dict]]:
    """Return 10-bin state- and within-stratum game-balanced ECE."""
    pred = clipped(probabilities)
    outcomes = np.array([int(r["home_win"]) for r in rows])
    weights = game_weights(rows)
    edges = np.minimum((pred * PROBABILITY_BINS).astype(int), PROBABILITY_BINS - 1)
    table = []
    state_ece = 0.0
    game_ece = 0.0
    for k in range(PROBABILITY_BINS):
        mask = edges == k
        n = int(mask.sum())
        weight = float(weights[mask].sum())
        if n:
            forecast = float(pred[mask].mean())
            frequency = float(outcomes[mask].mean())
            weighted_forecast = float(np.average(pred[mask], weights=weights[mask]))
            weighted_frequency = float(np.average(outcomes[mask], weights=weights[mask]))
            state_ece += n / len(rows) * abs(forecast - frequency)
            game_ece += weight / weights.sum() * abs(weighted_forecast - weighted_frequency)
        else:
            forecast = frequency = weighted_forecast = weighted_frequency = None
        table.append({
            "stratum": group, "model": version, "bin": k + 1,
            "probability_lower": k / PROBABILITY_BINS,
            "probability_upper": (k + 1) / PROBABILITY_BINS,
            "states": n, "game_balance_weight": round(weight, 9),
            "mean_probability": forecast, "observed_rate": frequency,
            "game_weighted_probability": weighted_forecast,
            "game_weighted_observed_rate": weighted_frequency,
        })
    return {
        "ece_10_bin_state": state_ece,
        "ece_10_bin_game_balanced": game_ece,
    }, table


def game_cluster_intervals(rows: list[dict], raw: np.ndarray,
                           calibrated: np.ndarray, repetitions: int = BOOTSTRAPS,
                           seed: int = RNG_SEED) -> dict:
    """Paired percentile bootstrap, resampling entire games, not individual states.

    Each sampled game contributes its average state loss once. No model refitting,
    no random row-level resampling and no test-set parameter selection.
    """
    if repetitions < 20:
        raise ValueError("At least 20 bootstrap replicates required")
    ids = [r["game_id"] for r in rows]
    games = sorted(set(ids))
    if len(games) < 3:
        raise ValueError("At least three independent game clusters required")
    game_codes = {game_id: idx for idx, game_id in enumerate(games)}
    codes = np.array([game_codes[g] for g in ids], dtype=int)
    n = len(games)
    counts = np.bincount(codes, minlength=n)
    y = np.array([int(r["home_win"]) for r in rows], dtype=float)
    raw_p, cal_p = clipped(raw), clipped(calibrated)
    if not (len(raw_p) == len(cal_p) == len(y)):
        raise ValueError("Outcomes and predictions must align")
    brier_raw = np.bincount(
        codes, weights=(raw_p - y) ** 2, minlength=n
    ) / counts
    brier_cal = np.bincount(
        codes, weights=(cal_p - y) ** 2, minlength=n
    ) / counts
    log_raw = -(y * np.log(raw_p) + (1 - y) * np.log(1 - raw_p))
    log_cal = -(y * np.log(cal_p) + (1 - y) * np.log(1 - cal_p))
    log_raw_game = np.bincount(codes, weights=log_raw, minlength=n) / counts
    log_cal_game = np.bincount(codes, weights=log_cal, minlength=n) / counts
    rng = np.random.default_rng(seed)
    replicates = rng.integers(0, n, size=(repetitions, n))
    results = {}
    for name, values in (
        ("raw_brier", brier_raw),
        ("calibrated_brier", brier_cal),
        ("delta_brier_cal_minus_raw", brier_cal - brier_raw),
        ("raw_log_loss", log_raw_game),
        ("calibrated_log_loss", log_cal_game),
        ("delta_log_loss_cal_minus_raw", log_cal_game - log_raw_game),
    ):
        samples = values[replicates].mean(axis=1)
        lo, hi = np.quantile(samples, [0.025, 0.975])
        results[name] = {
            "point": float(values.mean()), "ci95_lower": float(lo),
            "ci95_upper": float(hi),
        }
    return {
        "method": "Paired percentile game-cluster bootstrap; per-game mean losses",
        "games": n, "replicates": repetitions, "random_seed": seed,
        "metrics": results,
        "interpretation": "Intervals are conditional on the held-out cohort and fixed model.",
    }


def run_audit(rows: list[dict], raw: np.ndarray, calibrated: np.ndarray,
              repetitions: int = BOOTSTRAPS) -> tuple[dict, list[dict], list[dict]]:
    if not rows or any(r["split"] != "test" for r in rows):
        raise ValueError("Only untouched test-season states are permitted")
    if len(raw) != len(rows) or len(calibrated) != len(rows):
        raise ValueError("Mismatched prediction length")
    if not np.isfinite(raw).all() or not np.isfinite(calibrated).all():
        raise ValueError("Non-finite probabilities")
    masks = subset_masks(rows)
    result = {}
    binned_rows = []
    table_rows = []
    for group, mask in masks.items():
        selected = [r for r, include in zip(rows, mask, strict=True) if include]
        if not selected:
            result[group] = {"states": 0, "games": 0, "insufficient_data": True}
            continue
        original = clipped(raw[mask])
        changed = clipped(calibrated[mask])
        raw_reliability, rtable = reliability(selected, original, group, "raw")
        cal_reliability, ctable = reliability(selected, changed, group, "platt")
        binned_rows.extend(rtable)
        binned_rows.extend(ctable)
        raw_metrics = evaluate(selected, original)
        cal_metrics = evaluate(selected, changed)
        n_games = len({row["game_id"] for row in selected})
        report = {
            "states": len(selected),
            "games": n_games,
            "raw": {**raw_metrics, **raw_reliability},
            "platt": {**cal_metrics, **cal_reliability},
            "delta_platt_minus_raw": {
                "brier": cal_metrics["brier"] - raw_metrics["brier"],
                "game_balanced_brier": (
                    cal_metrics["game_balanced_brier"] - raw_metrics["game_balanced_brier"]
                ),
                "log_loss": cal_metrics["log_loss"] - raw_metrics["log_loss"],
            },
            "cluster_bootstrap": (
                game_cluster_intervals(
                    selected, original, changed, repetitions=repetitions, seed=RNG_SEED
                )
                if n_games >= 30 else None
            ),
        }
        result[group] = report
        table_rows.append({
            "stratum": group, "states": len(selected), "games": n_games,
            "raw_game_brier": raw_metrics["game_balanced_brier"],
            "platt_game_brier": cal_metrics["game_balanced_brier"],
            "raw_ece": raw_reliability["ece_10_bin_game_balanced"],
            "platt_ece": cal_reliability["ece_10_bin_game_balanced"],
            "delta_brier_platt_minus_raw": (
                cal_metrics["game_balanced_brier"] - raw_metrics["game_balanced_brier"]
            ),
        })
    return result, table_rows, binned_rows


def write_csv(path: Path, entries: list[dict]) -> None:
    if not entries:
        raise ValueError("Cannot write empty report")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(entries[0]))
        writer.writeheader()
        writer.writerows(entries)


def build(dataset: Path, model_path: Path, model_report: Path, output: Path,
          repetitions: int = BOOTSTRAPS) -> dict:
    """Load frozen model, verify file fingerprints and diagnose held-out data."""
    original = json.loads(model_report.read_text(encoding="utf-8"))
    if hashlib.sha256(dataset.read_bytes()).hexdigest() != original["dataset_sha256"]:
        raise ValueError("Dataset differs from frozen Step 2.2 training/evaluation")
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != original["model_sha256"]:
        raise ValueError("Model differs from frozen Step 2.2 artifact")
    # Only load artifacts from trusted repository CI; pickle/joblib is not safe for untrusted files.
    model_bundle = joblib.load(model_path)
    rows = [r for r in read_states(dataset) if r["split"] == "test"]
    features = feature_matrix(rows)
    raw = model_bundle["model"].predict_proba(features)[:, 1]
    calibrated = model_bundle["calibrator"].predict_proba(logit(raw))[:, 1]
    findings, summary, bins = run_audit(rows, raw, calibrated, repetitions=repetitions)
    full = findings["all_q4_and_ot"]
    prior_raw = original["test_metrics"]["uncalibrated"]["game_balanced_brier"]
    prior_platt = original["test_metrics"]["calibrated"]["game_balanced_brier"]
    if not (
        abs(full["raw"]["game_balanced_brier"] - prior_raw) < 1e-10
        and abs(full["platt"]["game_balanced_brier"] - prior_platt) < 1e-10
    ):
        raise ValueError("Frozen Step 2.2 test metrics not reproduced")
    report = {
        "status": "complete_diagnostic_only_no_retraining",
        "scope": "Frozen Step 2.2 model / 2024-25 out-of-time Q4/OT test games",
        "frozen_dataset_sha256": original["dataset_sha256"],
        "frozen_model_sha256": original["model_sha256"],
        "bootstrap_games_as_clusters": True,
        "bootstrap_replicates": repetitions,
        "seed": RNG_SEED,
        "strata": findings,
        "warnings": [
            "This is post-hoc test-season diagnostic analysis; do not tune on these findings.",
            "Ten-bin ECE is resolution-dependent and may hide within-bin miscalibration.",
            "Cluster bootstrap conditions on observed test games, without retraining the model.",
            "Game-balanced strata reweight participating games equally within each subset.",
            "Post-action win probabilities are not counterfactual officiating effects.",
            "Tiny subgroups and high-confidence bins may have unstable estimates.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "wp_robustness_report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    write_csv(output / "wp_strata_summary.csv", summary)
    write_csv(output / "wp_strata_reliability.csv", bins)
    print(json.dumps({
        "overall": {k: full[k] for k in ("states", "games", "delta_platt_minus_raw")},
        "clutch": {
            k: findings["l2m_close_margin_5"][k]
            for k in ("states", "games", "delta_platt_minus_raw")
        },
    }, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit frozen 2024-25 NBA win-probability model")
    parser.add_argument("--dataset", type=Path,
                        default=Path("data/win_probability/wp_q4_states_2021_2024.csv"))
    parser.add_argument("--model", type=Path,
                        default=Path("models/win_probability/wp_baseline.joblib"))
    parser.add_argument("--report", type=Path,
                        default=Path("models/win_probability/wp_model_report.json"))
    parser.add_argument("--output", type=Path, default=Path("models/win_probability"))
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAPS)
    args = parser.parse_args()
    build(args.dataset, args.model, args.report, args.output, repetitions=args.bootstrap)


if __name__ == "__main__":
    main()
