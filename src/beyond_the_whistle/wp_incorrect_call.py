"""Compare explicitly reconstructed post-resolution states for an incorrect call."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from beyond_the_whistle.wp_inference import GameState, infer, load_trusted_bundle

CANDIDATES = Path("data/validated/l2m_pbp_2025_candidates.csv")
MODEL = Path("models/win_probability/wp_baseline.joblib")


def load_incorrect_calls(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return {
            row["l2m_record"]: row for row in csv.DictReader(stream)
            if row["decision"] == "IC"
        }


def compare_scenarios(bundle: dict, case: dict, records: dict[str, dict], version: str) -> dict:
    record = None
    if case.get("hypothetical") is not True:
        record = records.get(str(case.get("l2m_record")))
        if record is None or case.get("game_id") != record["game_id"]:
            raise ValueError("A real case must identify an official IC record and its game")
        for field in ("video_reference", "verification_notes", "rule_reference"):
            if not str(case.get(field) or "").strip():
                raise ValueError(f"A real case requires {field}")
    if case.get("affected_team") not in ("home", "away"):
        raise ValueError("affected_team must be home or away")

    observed = GameState(**case["observed"])
    if record is not None and observed.period != int(record["period"]):
        raise ValueError("Observed state must be in the official record's period")

    def probability(state: GameState) -> float:
        result = infer(bundle, state, probability_version=version)
        return result[f"{case['affected_team']}_win_probability"]

    observed_wp = probability(observed)
    branches = []
    for item in case["alternatives"]:
        if not str(item.get("assumption") or "").strip():
            raise ValueError("Each alternative requires an explicit assumption")
        state = GameState(**item["state"])
        if state.period != observed.period:
            raise ValueError("Compare post-resolution states within the same period")
        wp = probability(state)
        branches.append({
            **item,
            "win_probability": wp,
            "delta_percentage_points": 100 * (wp - observed_wp),
        })
    if not branches:
        raise ValueError("Supply at least one alternative state")
    deltas = [item["delta_percentage_points"] for item in branches]
    return {
        "case": {key: value for key, value in case.items() if key != "alternatives"},
        "official_record": record,
        "probability_version": version,
        "observed_win_probability": observed_wp,
        "alternatives": branches,
        "delta_range_percentage_points": [min(deltas), max(deltas)],
        "causal_officiating_effect": False,
        "interpretation": (
            "Corrected minus observed, from the affected team's perspective. "
            "Range spans the supplied scenarios. The baseline scores resolved "
            "score-clock states and cannot distinguish possession or pending free throws."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--probability-version", choices=("raw", "platt"), default="platt")
    parser.add_argument("--case", type=Path, help="JSON file with observed and corrected states")
    args = parser.parse_args()
    records = load_incorrect_calls(args.candidates)
    if args.case is None:
        result = {
            "official_incorrect_calls": len(records),
            "games": len({row["game_id"] for row in records.values()}),
            "candidate_match_status": dict(Counter(row["status"] for row in records.values())),
        }
    else:
        case = json.loads(args.case.read_text(encoding="utf-8"))
        result = compare_scenarios(
            load_trusted_bundle(args.model), case, records, args.probability_version,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
