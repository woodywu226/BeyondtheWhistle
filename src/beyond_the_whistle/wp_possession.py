"""Train and evaluate NBA win probability at out-of-bounds restarts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from itertools import pairwise
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from beyond_the_whistle.wp_dataset import SPLITS, action_state, extract_archive


def extract_rows(csv_bytes: bytes) -> tuple[list[dict], dict]:
    games = defaultdict(list)
    with io.StringIO(csv_bytes.decode("utf-8-sig")) as stream:
        for raw in csv.DictReader(stream):
            if (state := action_state(raw)) is not None:
                state.update(team=raw["teamId"], possession=raw["possession"])
                games[state["game_id"]].append(state)

    rows = []
    audit = defaultdict(int)
    for gid, actions in games.items():
        actions.sort(key=lambda row: row["order"])
        final = actions[-1]
        if (final["period"] < 4 or final["seconds_remaining"] != 0
                or final["action_type"] not in ("period", "game")
                or final["sub_type"] != "end" or final["home_margin"] == 0):
            audit["unverified_final_score_games"] += 1
            continue
        teams = {"home": set(), "away": set()}
        for previous, current in pairwise(actions):
            if current["action_type"] not in ("2pt", "3pt", "freethrow"):
                continue
            if not current["team"] or current["team"] == "0":
                continue
            for side, other in (("home", "away"), ("away", "home")):
                if (current[f"{side}_score"] > previous[f"{side}_score"]
                        and current[f"{other}_score"] == previous[f"{other}_score"]):
                    teams[side].add(current["team"])
        if any(len(ids) != 1 for ids in teams.values()) or teams["home"] == teams["away"]:
            audit["unverified_team_mapping_games"] += 1
            continue
        home, away = next(iter(teams["home"])), next(iter(teams["away"]))
        for index, state in enumerate(actions):
            if (state["period"] < 4 or state["seconds_remaining"] <= 0
                    or state["action_type"] != "turnover"
                    or state["sub_type"] != "out-of-bounds"
                    or state["team"] not in (home, away)):
                continue
            receiving = away if state["team"] == home else home
            for following_index in range(index + 1, len(actions)):
                following = actions[following_index]
                if (following["period"] != state["period"]
                        or following["action_type"] in ("foul", "jumpball", "period", "game")):
                    break
                if following["action_type"] in ("2pt", "3pt", "turnover"):
                    if following["team"] == following["possession"] in (home, away):
                        audit["next_offense_agrees" if following["team"] == receiving
                              else "next_offense_disagrees"] += 1
                    break
            rows.append({
                "game_id": gid, "period": state["period"],
                "seconds_remaining": state["seconds_remaining"],
                "home_margin": state["home_margin"], "home_possession": int(receiving == home),
                "home_win": int(final["home_margin"] > 0),
            })
    return rows, dict(audit)


def features(row: dict, use_possession: bool) -> list[float]:
    clock = row["seconds_remaining"]
    margin = row["home_margin"]
    clock_scale = math.sqrt(60 / max(1, clock))
    values = [margin / 10, margin * clock_scale / 10, math.log1p(clock) / 5,
              float(row["period"] > 4)]
    if use_possession:
        possession = 2 * row["home_possession"] - 1
        values.extend((possession, possession * clock_scale))
    return values


def evaluate(rows: list[dict], prediction: np.ndarray) -> dict:
    labels = [row["home_win"] for row in rows]
    return {
        "states": len(rows), "games": len({row["game_id"] for row in rows}),
        "brier": float(brier_score_loss(labels, prediction)),
        "log_loss": float(log_loss(labels, prediction, labels=[0, 1])),
        "auc": float(roc_auc_score(labels, prediction)),
    }


def predict(model: dict, row: dict) -> float:
    log_odds = model["intercept"] + np.dot(model["coefficients"], features(row, True))
    return float(np.exp(-np.logaddexp(0, -log_odds)))


def fit(archive_dir: Path) -> dict:
    splits = defaultdict(list)
    sources = []
    for year, split in SPLITS.items():
        path = archive_dir / f"cdnnba_{year}.tar.xz"
        archive = path.read_bytes()
        rows, audit = extract_rows(extract_archive(archive))
        splits[split].extend(rows)
        sources.append({"archive": path.name, "sha256": hashlib.sha256(archive).hexdigest(),
                        "states": len(rows), "next_offense_audit": audit})
    train = splits["train"]
    result = {"sources": sources, "training": {
        "states": len(train), "games": len({row["game_id"] for row in train}),
    }}
    for use_possession in (False, True):
        model = LogisticRegression(max_iter=1000).fit(
            [features(row, use_possession) for row in train], [row["home_win"] for row in train],
        )
        metrics = {}
        for split in ("validation", "test"):
            rows = splits[split]
            clutch = [row for row in rows
                      if row["seconds_remaining"] <= 120 and abs(row["home_margin"]) <= 5]
            metrics[split] = {}
            for name, cohort in (("all", rows), ("clutch", clutch)):
                pred = model.predict_proba([features(row, use_possession) for row in cohort])[:, 1]
                metrics[split][name] = evaluate(cohort, pred)
        key = "possession" if use_possession else "score_clock"
        result[key] = {
            "intercept": float(model.intercept_[0]), "coefficients": model.coef_[0].tolist(),
            "metrics": metrics,
        }
    return result


def score_cases(model: dict, cases: list[dict]) -> list[dict]:
    results = []
    for case in cases:
        sides = {case["home_team"], case["away_team"]}
        possessions = {case["observed_possession"], case["corrected_possession"]}
        if len(sides) != 2 or possessions != sides:
            raise ValueError("The observed and corrected possessions must be opposing teams")
        row = {
            "period": case["period"], "seconds_remaining": case["seconds_remaining"],
            "home_margin": case["home_score"] - case["away_score"],
        }
        actual = int(case["observed_possession"] == case["home_team"])
        before = predict(model, {**row, "home_possession": actual})
        after = predict(model, {**row, "home_possession": 1 - actual})
        if actual:
            before, after = 1 - before, 1 - after
        results.append({
            **case, "estimated_team": case["corrected_possession"],
            "observed_wp_pct": round(100 * before, 6),
            "corrected_wp_pct": round(100 * after, 6),
            "delta_pp": round(100 * (after - before), 6),
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = fit(args.archives)
    case_review = json.loads(args.cases.read_text(encoding="utf-8"))
    result["case_results"] = score_cases(result["possession"], case_review["scored"])
    result["pending_cases"] = case_review["pending"]
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
