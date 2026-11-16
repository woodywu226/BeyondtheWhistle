"""Combine the score-clock and out-of-bounds scenario inventories."""

import argparse
import csv
import json
from decimal import Decimal
from pathlib import Path

EXTRA_FIELDS = (
    "estimate_status", "evidence_status", "observed_possession", "corrected_possession",
    "alternative_wp_min_pct", "alternative_wp_max_pct",
)


def write_coverage(score_clock: Path, possession: Path, output: Path) -> None:
    with score_clock.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        fields = list(reader.fieldnames or ()) + list(EXTRA_FIELDS)
        rows = list(reader)
    by_record = {row["l2m_record"]: row for row in rows}
    if len(by_record) != len(rows):
        raise ValueError("Duplicate score-clock case IDs")

    for row in rows:
        if row["observed_wp_pct"]:
            row["estimate_status"] = "estimated"
            row["evidence_status"] = "official_report_and_pbp"
            observed = Decimal(row["observed_wp_pct"])
            for bound in ("min", "max"):
                delta = Decimal(row[f"{bound}_delta_pp"])
                row[f"alternative_wp_{bound}_pct"] = f"{observed + delta:.6f}"
        else:
            row["estimate_status"] = "pending"
            row["probability_version"] = ""

    report = json.loads(possession.read_text(encoding="utf-8"))
    seen = set()
    for case in report["case_results"] + report["pending_cases"]:
        record = case["l2m_record"]
        row = by_record.get(record)
        if (
            row is None or row["game_id"] != case["game_id"]
            or row["estimate_status"] != "pending" or record in seen
        ):
            raise ValueError(f"Unexpected or overlapping out-of-bounds case {record}")
        seen.add(record)
        if "corrected_wp_pct" not in case:
            row["reason"] = case["reason"]
            continue
        row.update({
            "disposition": "scored_out_of_bounds_possession",
            "estimate_status": "estimated",
            "reason": case["evidence"],
            "evidence_status": case.get("evidence_status", "official_report_and_pbp_clock_anchor"),
            "probability_version": "out_of_bounds_possession_logistic",
            "affected_team": case["estimated_team"],
            "observed_wp_pct": f"{case['observed_wp_pct']:.6f}",
            "observed_possession": case["observed_possession"],
            "corrected_possession": case["corrected_possession"],
            "min_delta_pp": f"{case['delta_pp']:.6f}",
            "max_delta_pp": f"{case['delta_pp']:.6f}",
            "alternative_wp_min_pct": f"{case['corrected_wp_pct']:.6f}",
            "alternative_wp_max_pct": f"{case['corrected_wp_pct']:.6f}",
        })

    with output.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score-clock", required=True, type=Path)
    parser.add_argument("--possession", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    write_coverage(args.score_clock, args.possession, args.output)


if __name__ == "__main__":
    main()
