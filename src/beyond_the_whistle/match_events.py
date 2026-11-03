"""Conservative L2M-to-PBP temporal candidate matching.

Clock proximity is NOT definitive proof that a PBP action is the reviewed play.
Only uniqueness within time window is reported; review is still required.
INC/CNC may have no PBP action at all.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from beyond_the_whistle.ingest_pbp import parse_clock

OUTPUT_FIELDS = (
    "l2m_index", "game_id", "period", "l2m_clock_seconds", "decision",
    "call_type", "status", "candidate_count", "action_id", "time_delta_seconds",
    "action_type", "description"
)
ERROR_GRADES = {"IC", "INC"}
GRADES = {"CC", "CNC", "IC", "INC"}


def l2m_game_id(row: dict) -> str:
    for key in ("gid", "GAME_ID", "GameId"):
        value = str(row.get(key) or "").strip()
        if value.endswith(".0") and value[:-2].isdigit():
            value = value[:-2]
        if value.isdigit() and len(value) <= 10:
            return value.zfill(10)
    return ""


def match_events(l2m: list[dict], pbp: list[dict], tolerance: float = 2.0) -> list[dict]:
    if tolerance < 0:
        raise ValueError("Tolerance must be nonnegative")
    index = defaultdict(list)
    for action in pbp:
        index[(str(action["game_id"]), int(action["period"]))].append(action)
    matches = []
    for i, row in enumerate(l2m):
        gid = l2m_game_id(row)
        decision = (row.get("decision") or "").strip().upper()
        call_type = (row.get("call_type") or "").strip()
        output = {
            "l2m_index": i, "game_id": gid, "period": row.get("period", ""),
            "l2m_clock_seconds": "", "decision": decision,
            "call_type": call_type, "status": "", "candidate_count": 0,
            "action_id": "", "time_delta_seconds": "", "action_type": "",
            "description": "",
        }
        if decision not in GRADES:
            output["status"] = "ungraded_or_unknown_decision"
        elif not gid:
            output["status"] = "missing_game_id"
        else:
            try:
                period = int(float(row["period"]))
                seconds = parse_clock(row["time"])
                output["l2m_clock_seconds"] = seconds
                output["period"] = period
                # PBP can include administrative events near each whistle.
                candidates = [
                    a for a in index[(gid, period)]
                    if abs(float(a["clock_seconds"]) - seconds) <= tolerance
                    and (a.get("action_type") or "").lower() not in
                    {"period", "substitution", "timeout"}
                ]
                output["candidate_count"] = len(candidates)
                if decision in {"CNC", "INC"}:
                    output["status"] = "noncall_requires_video_review"
                elif not candidates:
                    output["status"] = "no_temporal_candidate"
                elif len(candidates) > 1:
                    output["status"] = "ambiguous_temporal_candidates"
                else:
                    action = candidates[0]
                    output["status"] = "unique_temporal_candidate_unverified"
                    output["action_id"] = str(action.get("action_id", ""))
                    output["action_type"] = str(action.get("action_type", ""))
                    output["description"] = str(action.get("description", ""))
                    output["time_delta_seconds"] = round(
                        abs(float(action["clock_seconds"]) - seconds), 3
                    )
            except (ValueError, KeyError, TypeError):
                output["status"] = "invalid_period_or_clock"
        matches.append(output)
    return matches


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--l2m", type=Path, default=Path("data/raw/l2m_source.csv"))
    parser.add_argument("--pbp", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/processed/l2m_pbp_candidates.csv"))
    parser.add_argument("--audit", type=Path, default=Path("data/processed/match_audit.json"))
    parser.add_argument("--tolerance", type=float, default=2.0)
    args = parser.parse_args()
    matches = match_events(read_csv(args.l2m), read_csv(args.pbp), args.tolerance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(matches)
    report = {
        "total_l2m_rows": len(matches),
        "statuses": dict(sorted(Counter(m["status"] for m in matches).items())),
        "matched_game_ids": sorted({m["game_id"] for m in matches if m["candidate_count"]}),
        "tolerance_seconds": args.tolerance,
        "warning": "Temporal candidates are NOT official L2M-to-PBP verification. "
                   "Non-calls generally require independent video review.",
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
