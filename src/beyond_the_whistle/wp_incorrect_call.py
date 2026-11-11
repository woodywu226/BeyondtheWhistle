"""Compare explicitly reconstructed post-resolution states for an incorrect call."""
from __future__ import annotations

import argparse
import csv
import json
import sys
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
    evidence_status = "hypothetical"
    if case.get("hypothetical") is not True:
        record = records.get(str(case.get("l2m_record")))
        if record is None or case.get("game_id") != record["game_id"]:
            raise ValueError("A real case must identify an official IC record and its game")
        evidence_status = case.get("evidence_status", "reviewer_documented")
        if evidence_status not in ("reviewer_documented", "official_report_and_pbp"):
            raise ValueError("Unsupported evidence_status for a real case")
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
        "evidence_status": evidence_status,
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


def score_review(bundle: dict, review: dict, records: dict[str, dict], version: str) -> list[dict]:
    """Return one auditable row per official IC, including cases without estimates."""
    entries = review["records"]
    ids = [entry["l2m_record"] for entry in entries]
    if len(ids) != len(set(ids)) or set(ids) != records.keys():
        raise ValueError("Review must contain each official IC record exactly once")

    rows = []
    for entry in entries:
        rid = entry["l2m_record"]
        record = records[rid]
        if entry["game_id"] != record["game_id"]:
            raise ValueError(f"Review game mismatch for record {rid}")
        row = {
            "l2m_record": rid,
            "game_id": record["game_id"],
            "period": record["period"],
            "clock": record["clock"],
            "home_team": entry["home_team"],
            "away_team": entry["away_team"],
            "official_call_type": entry["official_call_type"],
            "pbp_match_status": record["status"],
            "pbp_candidate_action": record["pbp_event_num"],
            "official_report": entry["official_report"],
            "video_review": entry["video_review"],
            "disposition": entry["disposition"],
            "reason": entry.get("reason", ""),
            "probability_version": version,
            "affected_team": "",
            "observed_wp_pct": "",
            "min_delta_pp": "",
            "max_delta_pp": "",
        }
        if "case" in entry:
            case = entry["case"]
            if case.get("hypothetical") is True or str(case["l2m_record"]) != rid:
                raise ValueError(f"Review case must use its corresponding official record {rid}")
            result = compare_scenarios(bundle, case, records, version)
            low, high = result["delta_range_percentage_points"]
            row.update(
                affected_team=row[f"{case['affected_team']}_team"],
                observed_wp_pct=round(100 * result["observed_win_probability"], 6),
                min_delta_pp=round(low, 6),
                max_delta_pp=round(high, 6),
            )
        elif not row["reason"]:
            raise ValueError(f"Unscored record {rid} requires a reason")
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--probability-version", choices=("raw", "platt"), default="platt")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--case", type=Path, help="JSON file with observed and corrected states")
    mode.add_argument("--review", type=Path, help="Full IC review JSON. Writes a coverage CSV")
    args = parser.parse_args()
    records = load_incorrect_calls(args.candidates)
    if args.review is not None:
        review = json.loads(args.review.read_text(encoding="utf-8"))
        rows = score_review(
            load_trusted_bundle(args.model), review, records, args.probability_version,
        )
        writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return
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
