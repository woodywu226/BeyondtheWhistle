"""Create a deterministic, *unadjudicated* review queue from real NBA event keys."""
from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

OUTPUT_FIELDS = (
    "l2m_record", "game_id", "period", "clock", "decision", "call_category",
    "pbp_event_num", "match_status", "official_report_url",
    "reviewer_id", "video_evidence_url", "same_event_verified",
    "reviewer_decision", "evidence_notes",
)
GRADES = ("CC", "IC", "CNC", "INC")


def sample_for_review(rows: list[dict], per_grade: int = 12, seed: int = 2026) -> list[dict]:
    if per_grade < 1:
        raise ValueError("per_grade must be positive")
    groups = defaultdict(list)
    for row in rows:
        if row.get("decision") in GRADES and row.get("game_id"):
            groups[row["decision"]].append(row)
    randomizer = random.Random(seed)
    sample = []
    for grade in GRADES:
        eligible = sorted(
            groups[grade],
            key=lambda r: (r["game_id"], int(r["l2m_record"])),
        )
        chosen = randomizer.sample(eligible, min(per_grade, len(eligible)))
        for row in chosen:
            gid = row["game_id"]
            sample.append({
                "l2m_record": row["l2m_record"],
                "game_id": gid,
                "period": row["period"],
                "clock": row["clock"],
                "decision": grade,
                "call_category": row["call_category"],
                "pbp_event_num": row["pbp_event_num"],
                "match_status": row["status"],
                "official_report_url": (
                    f"https://official.nba.com/l2m/L2MReport.html?gameId={gid}"
                ),
                "reviewer_id": "",
                "video_evidence_url": "",
                "same_event_verified": "",
                "reviewer_decision": "",
                "evidence_notes": "",
            })
    return sample


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", type=Path,
        default=Path("data/validated/l2m_pbp_2025_candidates.csv"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/validated/step1_review_queue_2025.csv"),
    )
    parser.add_argument("--per-grade", type=int, default=12)
    args = parser.parse_args()
    with args.input.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    sample = sample_for_review(rows, per_grade=args.per_grade)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(sample)
    print(f"Created {len(sample)} review assignments (not yet adjudicated): {args.output}")


if __name__ == "__main__":
    main()
