"""Score and merge the final 2024–25 incorrect-call review."""

import argparse
import csv
import json
from pathlib import Path

from beyond_the_whistle.wp_inference import GameState, infer, load_trusted_bundle
from beyond_the_whistle.wp_possession import predict

DATA = Path("data/validated")
BASE_MODEL = Path("models/win_probability/wp_baseline.joblib")
FIELDS = (
    "analysis_scope", "official_clip", "pbp_source", "pbp_actions", "reference_home_score",
    "reference_away_score", "reference_clock_seconds", "observed_state_note",
    "alternative_state_notes", "clip_check", "comparison_reference_wp_min_pct",
    "comparison_reference_wp_max_pct",
)


def score_case(case: dict, score_clock: dict, possession: dict) -> dict:
    home = case["home_team"]
    teams = {home, case["away_team"]}
    method = case["model"]
    if method not in {"score_clock", "possession_proxy"} or case["affected_team"] not in teams:
        raise ValueError(f"Invalid model or team for case {case['l2m_record']}")

    def probability(item: dict) -> float:
        score = GameState(
            item.get("period", case["period"]), item["seconds_remaining"],
            item["home_score"], item["away_score"],
        )
        score.validate()
        if method == "score_clock":
            p_home = infer(score_clock, score)["home_win_probability"]
        else:
            if item["possession"] not in teams:
                raise ValueError(f"Missing or invalid possession in case {case['l2m_record']}")
            p_home = predict(possession, {
                "period": score.period, "seconds_remaining": score.seconds_remaining,
                "home_margin": score.home_score - score.away_score,
                "home_possession": int(item["possession"] == home),
            })
        return 100 * (p_home if case["affected_team"] == home else 1 - p_home)

    observed = probability(case["observed"])
    alternatives = []
    for branch in case["alternatives"]:
        alternative = probability(branch)
        reference = probability(branch["observed_override"]) if "observed_override" in branch else observed
        alternatives.append({
            **branch, "reference_wp_pct": reference, "alternative_wp_pct": alternative,
            "delta_pp": alternative - reference,
        })
    if bool(alternatives) == (case["scope"] == "unidentifiable"):
        raise ValueError(f"Recorded scope and modeled alternatives disagree for {case['l2m_record']}")
    return {**case, "observed_wp_pct": observed, "alternatives": alternatives}


def write_review(baseline: Path, cases: list[dict], output: Path) -> None:
    with baseline.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        fields = list(reader.fieldnames or ()) + list(FIELDS)
        rows = list(reader)
    by_id = {case["l2m_record"]: case for case in cases}
    pending = [row for row in rows if row["estimate_status"] == "pending"]
    if len(by_id) != len(cases) or by_id.keys() != {row["l2m_record"] for row in pending}:
        raise ValueError("The follow-up must cover every open case exactly once")

    for row in rows:
        case = by_id.get(row["l2m_record"])
        if case is None:
            row["analysis_scope"] = (
                "rule_context_supported" if row["disposition"] == "scored_out_of_bounds_possession"
                else "scenario_range" if float(row["min_delta_pp"]) != float(row["max_delta_pp"])
                else "score_clock_component"
            )
            continue
        for key in ("game_id", "home_team", "away_team", "official_report"):
            if row[key] != case[key]:
                raise ValueError(f"Case metadata mismatch for {row['l2m_record']} ({key})")
        if int(row["period"]) != case["period"] or row["clock"] != case["official_clock"]:
            raise ValueError(f"Case clock mismatch for {row['l2m_record']}")
        branches = case["alternatives"]
        observed = case["observed"]
        row.update({
            "estimate_status": "estimated" if branches else "unidentifiable",
            "analysis_scope": case["scope"],
            "disposition": case["scope"],
            "evidence_status": (
                "official_report_pbp_and_clip_check" if case.get("clip_check")
                else "official_report_and_pbp"
            ),
            "clip_check": case.get("clip_check", ""),
            "probability_version": (
                "platt" if case["model"] == "score_clock" else "out_of_bounds_possession_proxy"
            ),
            "affected_team": case["affected_team"],
            "observed_wp_pct": f"{case['observed_wp_pct']:.6f}",
            "observed_possession": observed["possession"],
            "corrected_possession": "/".join(sorted({b["possession"] for b in branches})),
            "reference_home_score": observed["home_score"],
            "reference_away_score": observed["away_score"],
            "reference_clock_seconds": observed["seconds_remaining"],
            "observed_state_note": observed["assumption"],
            "alternative_state_notes": " | ".join(b["assumption"] for b in branches),
            "reason": case["interpretation"],
            "official_clip": case["official_clip"],
            "pbp_source": case["pbp_source"],
            "pbp_actions": " ".join(map(str, case["pbp_actions"])),
        })
        if branches:
            for key, low, high in (
                ("alternative_wp_pct", "alternative_wp_min_pct", "alternative_wp_max_pct"),
                ("reference_wp_pct", "comparison_reference_wp_min_pct",
                 "comparison_reference_wp_max_pct"),
                ("delta_pp", "min_delta_pp", "max_delta_pp"),
            ):
                values = [branch[key] for branch in branches]
                row[low], row[high] = f"{min(values):.6f}", f"{max(values):.6f}"

    with output.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()

    score_clock = load_trusted_bundle(BASE_MODEL)
    model = json.loads((DATA / "ic_oob_possession_results.json").read_text(encoding="utf-8"))
    cases = json.loads((DATA / "ic_followup_cases_2024_25.json").read_text(encoding="utf-8"))
    scored = [score_case(case, score_clock, model["possession"]) for case in cases]
    write_review(args.baseline, scored, args.output)
    args.details.write_text(json.dumps(scored, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
