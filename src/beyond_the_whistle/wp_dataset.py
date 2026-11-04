"""Step 2.1: Generate time-split, leakage-aware NBA fourth-quarter states.

No model training. Every feature is observable at the chosen post-action state.
The outcome is read only from a verified final-period buzzer.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import tarfile
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ARCHIVE_BASE = "https://raw.githubusercontent.com/shufinskiy/nba_data/main/datasets/"
SPLITS = {2021: "train", 2022: "train", 2023: "validation", 2024: "test"}
COLUMNS = (
    "game_id", "season_start_year", "split", "period", "seconds_remaining",
    "home_score", "away_score", "home_margin", "seconds_into_period", "home_win",
)
FEATURES = ("period", "seconds_remaining", "home_score", "away_score",
            "home_margin", "seconds_into_period")


def clock_seconds(value: str) -> float:
    match = re.fullmatch(r"PT(?:(\d+)M)?(\d+(?:\.\d+)?)S", str(value))
    if not match:
        raise ValueError("Unrecognized NBA clock")
    return int(match.group(1) or 0) * 60 + float(match.group(2))


def number(value: str) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def action_state(row: dict) -> dict | None:
    gid = str(row.get("gameId", "")).strip()
    period = number(row.get("period"))
    home = number(row.get("scoreHome"))
    away = number(row.get("scoreAway"))
    order = number(row.get("orderNumber"))
    action = number(row.get("actionNumber"))
    if not gid.isdigit() or len(gid) > 10 or not all(
        x is not None for x in (period, home, away, order, action)
    ):
        return None
    if min(home, away) < 0 or period < 1:
        return None
    try:
        remaining = clock_seconds(row.get("clock", ""))
    except ValueError:
        return None
    duration = 720 if period <= 4 else 300
    if not 0 <= remaining <= duration:
        return None
    return {
        "game_id": gid.zfill(10), "period": period,
        "seconds_remaining": remaining,
        "home_score": home, "away_score": away, "home_margin": home - away,
        "seconds_into_period": duration - remaining,
        "order": (period, order, action),
        "action_type": str(row.get("actionType", "")).lower(),
        "sub_type": str(row.get("subType", "")).lower(),
    }


def extract_states(csv_content: bytes, season: int, bucket_seconds: int = 30) -> tuple[list[dict], dict]:
    if season not in SPLITS:
        raise ValueError("Unknown season")
    if bucket_seconds < 5 or 720 % bucket_seconds:
        raise ValueError("Invalid time bucket")
    games = defaultdict(lambda: {"last": None, "snapshots": {}})
    inputs = 0
    invalid = 0
    with io.StringIO(csv_content.decode("utf-8-sig")) as stream:
        reader = csv.DictReader(stream)
        required = {
            "gameId", "period", "clock", "actionType", "subType",
            "orderNumber", "actionNumber", "scoreHome", "scoreAway",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing NBA CDN fields: {sorted(missing)}")
        for raw in reader:
            inputs += 1
            state = action_state(raw)
            if state is None:
                invalid += 1
                continue
            game = games[state["game_id"]]
            if game["last"] is None or state["order"] > game["last"]["order"]:
                game["last"] = state
            if state["period"] < 4 or state["seconds_remaining"] <= 0:
                continue
            key = (state["period"], int(state["seconds_remaining"] // bucket_seconds))
            previous = game["snapshots"].get(key)
            if previous is None or state["order"] > previous["order"]:
                game["snapshots"][key] = state
    result = []
    last_event_examples = [
        {"game": gid, "period": g["last"]["period"],
         "remaining": g["last"]["seconds_remaining"],
         "action_type": g["last"]["action_type"], "sub_type": g["last"]["sub_type"]}
        for gid, g in list(sorted(games.items()))[:5] if g["last"]
    ]
    excluded = Counter()
    home_winners = 0
    included_games = 0
    for gid, game in sorted(games.items()):
        final = game["last"]
        if final is None or final["period"] < 4:
            excluded["missing_final_period"] += 1
            continue
        if (final["seconds_remaining"] > 0.01 or final["action_type"] != "period"
            or final["sub_type"] != "end"):
            excluded["unverified_final_buzzer"] += 1
            continue
        if final["home_score"] == final["away_score"]:
            excluded["tied_final_score"] += 1
            continue
        winner = int(final["home_score"] > final["away_score"])
        selected = sorted(game["snapshots"].values(), key=lambda s: s["order"])
        if not selected:
            excluded["no_eligible_states"] += 1
            continue
        included_games += 1
        home_winners += winner
        for state in selected:
            result.append({
                "game_id": gid, "season_start_year": season, "split": SPLITS[season],
                "period": state["period"], "seconds_remaining": state["seconds_remaining"],
                "home_score": state["home_score"], "away_score": state["away_score"],
                "home_margin": state["home_margin"],
                "seconds_into_period": state["seconds_into_period"], "home_win": winner,
            })
    result.sort(key=lambda r: (r["game_id"], r["period"], -r["seconds_remaining"]))
    return result, {
        "season_start_year": season, "split": SPLITS[season],
        "raw_actions": inputs, "invalid_actions": invalid,
        "games_observed": len(games), "games_in_dataset": included_games,
        "excluded_games": dict(sorted(excluded.items())),
        "terminal_examples": last_event_examples,
        "states_created": len(result), "home_winner_games": home_winners,
    }


def extract_archive(blob: bytes) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:xz") as archive:
        members = [m for m in archive.getmembers() if m.isfile() and m.name.endswith(".csv")]
        if len(members) != 1 or members[0].size > 350_000_000:
            raise ValueError("Unexpected archive members or size")
        stream = archive.extractfile(members[0])
        if stream is None:
            raise ValueError("Missing CSV in NBA archive")
        return stream.read()


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "BeyondTheWhistle/0.2"})
    with urllib.request.urlopen(request, timeout=100) as response:
        blob = response.read(45_000_001)
    if not blob or len(blob) > 45_000_000:
        raise ValueError("PBP archive is empty or oversized")
    return blob


def validate(rows: list[dict]) -> dict:
    games = {}
    groups = defaultdict(set)
    for row in rows:
        game_id, season = row["game_id"], row["season_start_year"]
        split, target = row["split"], row["home_win"]
        if split != SPLITS[season] or target not in (0, 1):
            raise ValueError("Invalid season split or target")
        if row["home_margin"] != row["home_score"] - row["away_score"]:
            raise ValueError("Incorrect score margin")
        if row["period"] < 4 or row["seconds_remaining"] <= 0:
            raise ValueError("Final-buzzer leakage detected")
        prior = games.setdefault(game_id, (season, split, target))
        if prior != (season, split, target):
            raise ValueError("Same game spans splits or inconsistent winner label")
        groups[split].add(game_id)
    if not rows or any(not groups[s] for s in ("train", "validation", "test")):
        raise ValueError("One or more chronological splits are empty")
    return {
        "rows": len(rows), "games": len(games), "features": list(FEATURES),
        "label": "home_win",
        "splits": {
            split: {"games": len(ids), "states": sum(r["split"] == split for r in rows)}
            for split, ids in sorted(groups.items())
        },
        "train_seasons": [2021, 2022], "validation_seasons": [2023],
        "test_seasons": [2024],
        "sampling_rule": "Latest post-action state per period and 30-second time-remaining bucket in Q4/OT",
        "leakage_guards": [
            "Final winner is label only; not a predictor",
            "No final-buzzer states; only observed post-action score and game clock",
            "Games are partitioned by chronologically separated season",
            "Missing terminal game-end actions are excluded instead of guessing winners",
            "Correlated observations from one game remain within one split",
        ],
        "limitations": [
            "Play-in and playoff games excluded; regular seasons only",
            "No possession inferred without reliable contemporaneous evidence",
            "Multiple states from the same game are statistically dependent",
            "Dataset generation does not train or validate a model",
        ],
    }


def build(output: Path) -> dict:
    rows = []
    sources = []
    for season in SPLITS:
        url = f"{ARCHIVE_BASE}cdnnba_{season}.tar.xz"
        compressed = download(url)
        events, details = extract_states(extract_archive(compressed), season)
        if details["games_in_dataset"] < 900:
            raise ValueError(f"Unexpectedly low game count for {season}: {details}")
        sources.append({"url": url, "sha256": hashlib.sha256(compressed).hexdigest(), **details})
        rows.extend(events)
    audit = validate(rows)
    audit["sources"] = sources
    audit["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    output.mkdir(parents=True, exist_ok=True)
    dataset = output / "wp_q4_states_2021_2024.csv"
    with dataset.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    audit["dataset_sha256"] = hashlib.sha256(dataset.read_bytes()).hexdigest()
    (output / "wp_q4_manifest.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": audit["rows"], "games": audit["games"], "splits": audit["splits"]}, indent=2))
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("data/win_probability"))
    args = parser.parse_args()
    build(args.output_dir)


if __name__ == "__main__":
    main()
