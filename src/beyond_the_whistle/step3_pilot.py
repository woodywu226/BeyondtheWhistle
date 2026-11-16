"""Build the fixed NBA video pilot and summarize independently collected labels."""

import argparse
import csv
import hashlib
import io
import json
import math
import tarfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from beyond_the_whistle.build_archive_dataset import ARCHIVE_BASE, iso_clock_seconds

DATA = Path("data/validated")
OUTPUT = DATA / "step3"
WINDOWS = ("pre", "post")
LABELS = ("CC", "IC", "CNC", "INC", "normal_contact", "indeterminate")
WHISTLES = {"CC", "IC"}
SALT = "btw-step3-pilot-v1"
ARCHIVE = "cdnnba_2024.tar.xz"
RATERS = ("a", "b")
LABEL_FIELDS = ("incident_id", "label", "locatable", "review_seconds", "video_timestamp", "reason")


def ranked(value: str) -> str:
    return hashlib.sha256(f"{SALT}:{value}".encode()).hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, fields: tuple, rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def window(seconds: float) -> str:
    if not 0 <= seconds <= 240:
        raise ValueError("Clock outside the Q4 pilot")
    return "pre" if seconds > 120 else "post"


def read_archive(path: Path) -> dict:
    games = defaultdict(dict)
    with tarfile.open(path, mode="r:xz") as archive:
        for member in archive:
            if not member.isfile() or member.name != f"{ARCHIVE[:-7]}.csv":
                continue
            with io.TextIOWrapper(archive.extractfile(member), encoding="utf-8-sig") as stream:
                for row in csv.DictReader(stream):
                    gid = row["gameId"].zfill(10)
                    if not gid.startswith("002"):
                        continue
                    game = games[gid]
                    if "date" not in game and row["timeActual"]:
                        utc = datetime.fromisoformat(row["timeActual"].replace("Z", "+00:00"))
                        game["date"] = utc.astimezone(ZoneInfo("America/New_York")).date().isoformat()
                    if row["period"] == "4" and row["scoreHome"].isdigit() and (
                        row["scoreAway"].isdigit()
                    ):
                        sec = iso_clock_seconds(row["clock"])
                        game.setdefault("actions", []).append({
                            "clock": sec, "order": int(row["orderNumber"]),
                            "action_id": row["actionNumber"], "home": int(row["scoreHome"]),
                            "away": int(row["scoreAway"]), "type": row["actionType"].lower(),
                            "subtype": row["subType"].lower(), "team": row["teamTricode"],
                        })
                    if row["actionType"] in {"2pt", "3pt", "freethrow"} and (
                        row["shotResult"] == "Made" or row["actionType"] == "freethrow"
                    ) and row["scoreHome"].isdigit() and row["scoreAway"].isdigit():
                        pair = int(row["scoreHome"]), int(row["scoreAway"])
                        previous = game.get("score", (0, 0))
                        for index, side in enumerate(("home", "away")):
                            if pair[index] > previous[index] and pair[1-index] == previous[1-index]:
                                game[side] = row["teamTricode"]
                        game["score"] = pair
    if not games:
        raise ValueError("Regular-season action CSV missing from archive")
    return games


def select_games(games: dict, reports: set, excluded: set) -> list[dict]:
    strata = defaultdict(list)
    for gid, game in games.items():
        if gid in excluded or not all(game.get(k) for k in ("date", "home", "away", "actions")):
            continue
        actions = sorted(game["actions"], key=lambda a: a["order"])
        before = [a for a in actions if a["clock"] > 120]
        if not before or not any(
            a["type"] == "period" and a["subtype"] == "end" and a["clock"] == 0 for a in actions
        ):
            continue
        margin = abs(before[-1]["home"] - before[-1]["away"])
        # Common support at the boundary for games with and without an NBA report.
        if margin == 6:
            strata[gid in reports].append({
                "game_id": gid, "date_et": game["date"], "home_team": game["home"],
                "away_team": game["away"], "official_report_available": int(gid in reports),
                "abs_margin_entering_2m": margin, "actions": actions,
                "nba_game_url": f"https://www.nba.com/game/{gid}",
            })
    if min(len(strata[True]), len(strata[False])) < 5:
        raise ValueError("Insufficient common-support games in a report stratum")
    return sorted(
        [game for group in strata.values()
         for game in sorted(group, key=lambda g: ranked(g["game_id"]))[:5]],
        key=lambda g: g["game_id"],
    )


def build(archive: Path, output: Path) -> None:
    audit = json.loads((DATA / "l2m_pbp_2025_audit.json").read_text())
    expected = next(x["sha256"] for x in audit["pbp_archives"]
                    if x["url"] == ARCHIVE_BASE + ARCHIVE)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != expected:
        raise ValueError(f"Archive fingerprint mismatch: {digest}")
    calibration = read_csv(DATA / "step1_review_queue_2025.csv")
    reports = {x["game_id"] for x in read_csv(DATA / "l2m_pbp_2025_candidates.csv")}
    games = select_games(read_archive(archive), reports, {row["game_id"] for row in calibration})
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Build requires an empty directory to protect completed labels")

    game_fields = (
        "game_id", "date_et", "away_team", "home_team", "official_report_available",
        "abs_margin_entering_2m", "nba_game_url",
    )
    write_csv(output / "games.csv", game_fields,
              ({key: game[key] for key in game_fields} for game in games))
    segments = []
    action_stats = Counter()
    seed_rows = []
    candidate_locators = []
    for game in games:
        gid = game["game_id"]
        for high in range(240, 0, -12):
            low = high - 12
            segments.append({
                "segment_id": f"{gid}-{high:03}", "game_id": gid, "date_et": game["date_et"],
                "away_team": game["away_team"], "home_team": game["home_team"],
                "period": 4, "clock_start_s": high, "clock_end_s": low,
            })
        for action in game["actions"]:
            kind = action["type"]
            clock = action["clock"]
            if clock > 240 or kind not in {"2pt", "3pt", "foul", "violation", "turnover"}:
                continue
            locator = {
                "game_id": gid, "period": 4, "clock_s": clock, "action_id": action["action_id"],
            }
            high = max(12, 12 * math.ceil(clock / 12))
            candidate_locators.append({**locator, "segment_id": f"{gid}-{high:03}"})
            if kind in {"foul", "violation", "turnover"}:
                action_stats[gid, window(clock), kind] += 1
                seed_rows.append({
                    **locator, "action_type": kind, "subtype": action["subtype"],
                    "team": action["team"],
                })
    write_csv(output / "video_segments.csv", tuple(segments[0]),
              sorted(segments, key=lambda s: ranked(s["segment_id"])))
    write_csv(output / "pbp_locator.csv", tuple(seed_rows[0]), seed_rows)
    write_csv(output / "candidate_locators.csv", tuple(candidate_locators[0]), candidate_locators)
    rows = [
        {"game_id": game["game_id"], "window": group,
         **{kind: action_stats[game["game_id"], group, kind]
            for kind in ("foul", "violation", "turnover")}}
        for game in games for group in WINDOWS
    ]
    write_csv(output / "pbp_counts.csv", tuple(rows[0]), rows)
    fields = ("segment_id", "status", "review_seconds", "possessions_started", "notes")
    for rater in RATERS:
        write_csv(output / f"segment_log_{rater}.csv", fields,
                  ({"segment_id": s["segment_id"]} for s in
                   sorted(segments, key=lambda s: ranked(f"{rater}:{s['segment_id']}"))))
    write_csv(output / "incidents.csv", (
        "incident_id", "segment_id", "clock_s", "neutral_locator", "observed_whistle",
        "possession_started_in_window",
    ), ())
    write_csv(output / "discovery_template.csv", (
        "segment_id", "clock_s", "neutral_locator", "video_timestamp", "possession_start_clock_s",
    ), ())
    calibration_rows = []
    answer_key = []
    neutral_fields = ("game_id", "period", "clock")
    for sequence, row in enumerate(sorted(calibration, key=lambda r: ranked(r["l2m_record"])), 1):
        cid = f"C{sequence:02}"
        calibration_rows.append({"incident_id": cid, **{key: row[key] for key in neutral_fields}})
        answer_key.append({
            "incident_id": cid, "l2m_record": row["l2m_record"], "official_grade": row["decision"],
        })
    write_csv(output / "calibration_locators.csv", ("incident_id", *neutral_fields), calibration_rows)
    write_csv(output / "calibration_key.csv", tuple(answer_key[0]), answer_key)
    for rater in RATERS:
        write_csv(output / f"labels_{rater}.csv", LABEL_FIELDS, ())
        write_csv(output / f"calibration_labels_{rater}.csv", LABEL_FIELDS,
                  ({"incident_id": row["incident_id"]} for row in
                   sorted(calibration_rows, key=lambda r: ranked(f"{rater}:{r['incident_id']}"))))
    write_csv(output / "adjudication.csv", ("incident_id", "label", "reason"), ())
    write_csv(output / "possession_adjudication.csv",
              ("segment_id", "possessions_started", "reason"), ())
    totals = {group: {kind: sum(r[kind] for r in rows if r["window"] == group)
                      for kind in ("foul", "violation", "turnover")} for group in WINDOWS}
    write_json(output / "baseline.json", {
        "archive": ARCHIVE_BASE + ARCHIVE, "archive_sha256": digest,
        "sampling_salt": SALT, "games": len(games),
        "review_segments": len(segments), "pbp_locator_rows": len(seed_rows),
        "unverified_candidate_locators": len(candidate_locators),
        "incident_target": [150, 250], "required_independent_reviewers": 2,
        "game_clock_minutes_per_window": 20, "pbp_action_rows": totals,
        "limitation": "PBP action rows are recording counts, not video-observed whistles or errors.",
    })


def index(rows: list[dict], key: str) -> dict:
    records = {row[key]: row for row in rows}
    if len(records) != len(rows) or "" in records:
        raise ValueError(f"Missing or duplicate {key}")
    return records


def duration(text: str) -> float:
    result = float(text)
    if not math.isfinite(result) or result < 0:
        raise ValueError("Review duration must be a finite nonnegative number")
    return result


def rate(count: int, denominator: int) -> float | None:
    return count / denominator if denominator else None


def agreement(pairs: Counter) -> dict:
    n = sum(pairs.values())
    observed = rate(sum(pairs[label, label] for label in LABELS), n)
    expected = None if not n else sum(
        sum(pairs[label, other] for other in LABELS)
        * sum(pairs[other, label] for other in LABELS)
        for label in LABELS
    ) / n**2
    return {
        "paired_independent_labels": n, "raw_agreement": observed,
        "cohens_kappa": None if expected in (None, 1) else (observed - expected) / (1-expected),
        "label_confusion": {a: {b: pairs[a, b] for b in LABELS} for a in LABELS},
    }


def summarize(directory: Path) -> dict:
    games = index(read_csv(directory / "games.csv"), "game_id")
    segments = index(read_csv(directory / "video_segments.csv"), "segment_id")
    incidents = index(read_csv(directory / "incidents.csv"), "incident_id")
    logs = [index(read_csv(directory / f"segment_log_{r}.csv"), "segment_id") for r in RATERS]
    ratings = [index(read_csv(directory / f"labels_{r}.csv"), "incident_id") for r in RATERS]
    adjudications = index(read_csv(directory / "adjudication.csv"), "incident_id")
    possession_decisions = index(read_csv(directory / "possession_adjudication.csv"), "segment_id")
    if possession_decisions.keys() - segments.keys():
        raise ValueError("Unexpected segment ID in possession adjudication")
    if any(log.keys() != segments.keys() for log in logs) or any(
        source.keys() - incidents.keys() for source in (*ratings, adjudications)
    ):
        raise ValueError("Unexpected or missing segment IDs, or unexpected incident IDs")
    if any(
        row["status"] not in {"", "complete", "unavailable"} for log in logs for row in log.values()
    ):
        raise ValueError("Invalid segment status")

    totals = {group: Counter() for group in WINDOWS}
    per_game = defaultdict(Counter)
    pair_counts = {group: Counter() for group in (*WINDOWS, "overall")}
    for sid, segment in segments.items():
        group = window(float(segment["clock_start_s"]))
        group_counts = totals[group]
        game_counts = per_game[segment["game_id"], group]
        group_counts["segments_scheduled"] += 1
        game_counts["segments_scheduled"] += 1
        left, right = (log[sid] for log in logs)
        for name, row in zip(RATERS, (left, right)):
            if row["status"] == "complete":
                group_counts[f"segments_complete_{name}"] += 1
                group_counts[f"screening_seconds_{name}"] += duration(row["review_seconds"])
                if int(row["possessions_started"]) < 0:
                    raise ValueError("Negative possession count")
        if left["status"] == right["status"] == "complete":
            group_counts["segments_complete_both"] += 1
            game_counts["segments_complete_both"] += 1
            decision = possession_decisions.get(sid)
            if decision:
                count = int(decision["possessions_started"])
                if count < 0 or not decision["reason"]:
                    raise ValueError(f"Invalid reconciled possession count for {sid}")
            elif int(left["possessions_started"]) == int(right["possessions_started"]):
                count = int(left["possessions_started"])
            else:
                group_counts["segments_possession_count_disagrees"] += 1
                game_counts["segments_possession_count_disagrees"] += 1
                continue
            group_counts["possessions_resolved"] += count
            game_counts["possessions_resolved"] += count
        elif sid in possession_decisions:
            raise ValueError(f"Cannot adjudicate possessions before two reviews for {sid}")

    for iid, incident in incidents.items():
        sid = incident["segment_id"]
        segment = segments[sid]
        clock = float(incident["clock_s"])
        group = window(clock)
        low, high = float(segment["clock_end_s"]), float(segment["clock_start_s"])
        if not (low < clock <= high or low == clock == 0) or not incident["neutral_locator"]:
            raise ValueError(f"Invalid incident locator for {iid}")
        if incident["possession_started_in_window"] not in {"yes", "no", "uncertain"}:
            raise ValueError(f"Invalid possession eligibility for {iid}")
        whistle = incident["observed_whistle"]
        if whistle not in {"yes", "no", "uncertain"}:
            raise ValueError(f"Invalid whistle observation for {iid}")
        counts = totals[group]
        counts["incidents_registered"] += 1
        left, right = (source.get(iid) for source in ratings)
        for name, row in zip(RATERS, (left, right)):
            if row is None:
                continue
            if row["label"] not in LABELS or row["locatable"] not in {"yes", "no"}:
                raise ValueError(f"Invalid label or locatability for {iid}")
            if row["locatable"] == "no" and (
                row["label"] != "indeterminate" or not row["reason"]
            ):
                raise ValueError(f"Nonlocatable incident needs an indeterminate reason for {iid}")
            if row["locatable"] == "yes" and not row["video_timestamp"]:
                raise ValueError(f"Missing video timestamp for {iid}")
            counts[f"rating_attempts_{name}"] += 1
            counts[f"located_{name}"] += row["locatable"] == "yes"
            counts[f"rating_seconds_{name}"] += duration(row["review_seconds"])
        if left is None or right is None:
            counts["incidents_without_two_labels"] += 1
            per_game[segment["game_id"], group]["incidents_without_two_labels"] += 1
            if iid in adjudications:
                raise ValueError(f"Cannot adjudicate before two independent labels for {iid}")
            continue

        key = (left["label"], right["label"])
        pair_counts[group][key] += 1
        pair_counts["overall"][key] += 1
        decision = adjudications.get(iid)
        if decision:
            if decision["label"] not in LABELS or not decision["reason"]:
                raise ValueError(f"Invalid adjudication for {iid}")
            label = decision["label"]
        elif left["label"] == right["label"]:
            label = left["label"]
        else:
            counts["disagreements_unresolved"] += 1
            per_game[segment["game_id"], group]["disagreements_unresolved"] += 1
            continue
        if label != "indeterminate" and whistle != (
            "yes" if label in WHISTLES else "no"
        ):
            raise ValueError(f"Final label and observed whistle disagree for {iid}")
        if not all(log[sid]["status"] == "complete" for log in logs):
            counts["resolved_incidents_outside_joint_screening"] += 1
            continue
        game_counts = per_game[segment["game_id"], group]
        counts[label] += 1
        game_counts[label] += 1
        if whistle == "yes" and incident["possession_started_in_window"] == "yes":
            counts["eligible_whistles"] += 1
            game_counts["eligible_whistles"] += 1
        if whistle == "uncertain" or (
            whistle == "yes" and incident["possession_started_in_window"] == "uncertain"
        ):
            counts["whistles_possession_eligibility_unknown"] += 1
            game_counts["whistles_possession_eligibility_unknown"] += 1

    def metrics(counts: Counter) -> dict:
        cc, ic, cnc, inc = (counts[label] for label in LABELS[:4])
        has_unresolved = (
            counts["incidents_without_two_labels"] or counts["disagreements_unresolved"]
        )
        return {
            "counts": dict(counts),
            "whistles_per_100_possessions": (
                None if not counts["segments_complete_both"] or has_unresolved
                or counts["segments_possession_count_disagrees"]
                or counts["whistles_possession_eligibility_unknown"]
                else rate(100 * counts["eligible_whistles"], counts["possessions_resolved"])
            ),
            "incorrect_fraction_among_whistles": None if has_unresolved else rate(ic, cc + ic),
            "incorrect_fraction_among_rule_assessed_noncalls": (
                None if has_unresolved else rate(inc, cnc + inc)
            ),
            "incorrect_fraction_among_rule_assessed_incidents": (
                None if has_unresolved else rate(ic + inc, cc + ic + cnc + inc)
            ),
            "locatable_a": rate(counts["located_a"], counts["rating_attempts_a"]),
            "locatable_b": rate(counts["located_b"], counts["rating_attempts_b"]),
            "indeterminate_fraction_of_resolved": rate(
                counts["indeterminate"], sum(counts[label] for label in LABELS)
            ),
        }

    result = {group: metrics(totals[group]) for group in WINDOWS}
    for group, pairs in pair_counts.items():
        result.setdefault(group, {}).update(agreement(pairs))

    calibration_ids = index(read_csv(directory / "calibration_locators.csv"), "incident_id")
    calibration = [
        index(read_csv(directory / f"calibration_labels_{r}.csv"), "incident_id")
        for r in RATERS
    ]
    if any(source.keys() != calibration_ids.keys() for source in calibration):
        raise ValueError("Calibration rating sheets must retain every calibration incident ID")
    calibration_pairs = Counter()
    for iid in calibration_ids:
        left, right = (source[iid]["label"] for source in calibration)
        if (left and left not in LABELS) or (right and right not in LABELS):
            raise ValueError(f"Invalid calibration label for {iid}")
        if left and right:
            calibration_pairs[left, right] += 1

    paired_games = {
        gid: {group: metrics(per_game[gid, group]) for group in WINDOWS}
        for gid in games
    }
    paired_changes = {}
    for metric in ("whistles_per_100_possessions", "incorrect_fraction_among_whistles",
                   "incorrect_fraction_among_rule_assessed_noncalls"):
        differences = []
        for item in paired_games.values():
            pre, post = (item[group] for group in WINDOWS)
            if all(
                w["counts"].get("segments_complete_both") == w["counts"]["segments_scheduled"]
                and w[metric] is not None for w in (pre, post)
            ):
                differences.append(post[metric] - pre[metric])
        paired_changes[metric] = {
            "games": len(differences),
            "mean_post_minus_pre": rate(sum(differences), len(differences)),
        }

    complete = bool(incidents) and all(
        counts["segments_complete_both"] == counts["segments_scheduled"]
        and not counts["segments_possession_count_disagrees"]
        and not counts["incidents_without_two_labels"]
        and not counts["disagreements_unresolved"]
        and not counts["whistles_possession_eligibility_unknown"]
        for counts in totals.values()
    )
    started = bool(incidents) or any(row["status"] for log in logs for row in log.values())
    return {
        "status": ("complete" if complete else "in_progress" if started
                   else "awaiting_independent_review"),
        "windows": result,
        "calibration_independent_agreement": agreement(calibration_pairs),
        "paired_games": paired_games,
        "within_game_changes": paired_changes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build")
    builder.add_argument("--archive", required=True, type=Path)
    builder.add_argument("--output", default=OUTPUT, type=Path)
    summary = commands.add_parser("summarize")
    summary.add_argument("--input", default=OUTPUT, type=Path)
    summary.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "build":
        build(args.archive, args.output)
    else:
        write_json(args.output, summarize(args.input))


if __name__ == "__main__":
    main()
