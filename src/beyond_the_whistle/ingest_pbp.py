"""Download an NBA play-by-play V3 game and normalize its event records.

Remote access can be blocked/rate-limited. Fail explicitly; never produce fake games.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BeyondTheWhistle/0.1)",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}
FIELDS = ("game_id", "period", "clock_seconds", "action_id", "action_type",
          "sub_type", "description", "team_id", "home_score", "away_score")


def parse_clock(value: str) -> float:
    """Parse NBA ISO-8601 period-remaining clock or MM:SS[.ss]."""
    value = str(value).strip()
    match = re.fullmatch(r"PT(?:(\d+)M)?(\d+(?:\.\d+)?)S", value)
    if match:
        return int(match.group(1) or 0) * 60 + float(match.group(2))
    match = re.fullmatch(r"(\d+):(\d{2}(?:\.\d+)?)", value)
    if match and float(match.group(2)) < 60:
        return int(match.group(1)) * 60 + float(match.group(2))
    raise ValueError(f"Unrecognized period clock: {value!r}")


def read_actions(payload: dict) -> list[dict]:
    """Accept both the live game/actions layout and stats V3 resultSets layout."""
    game = payload.get("game")
    if isinstance(game, dict) and isinstance(game.get("actions"), list):
        return game["actions"]
    sets = payload.get("resultSets") or payload.get("resultSet")
    if isinstance(sets, dict):
        sets = [sets]
    if isinstance(sets, list):
        for ds in sets:
            if str(ds.get("name", "")).lower() == "playbyplay":
                return [dict(zip(ds["headers"], cells)) for cells in ds["rowSet"]]
    raise ValueError("Unsupported NBA PBP JSON structure; no actions found")


def normalize(payload: dict, expected_game_id: str) -> list[dict]:
    if not re.fullmatch(r"\d{10}", expected_game_id):
        raise ValueError("NBA game ID must be exactly 10 digits")
    actual = str((payload.get("game") or {}).get("gameId") or "")
    if actual and actual != expected_game_id:
        raise ValueError(f"Game ID mismatch: expected {expected_game_id}, received {actual}")
    out = []
    for event in read_actions(payload):
        event_game_id = str(event.get("gameId") or actual or expected_game_id)
        if event_game_id != expected_game_id:
            raise ValueError(f"Event game ID mismatch: {event_game_id}")
        out.append({
            "game_id": expected_game_id,
            "period": int(event["period"]),
            "clock_seconds": parse_clock(event["clock"]),
            "action_id": str(event.get("actionId") or event.get("actionNumber") or ""),
            "action_type": str(event.get("actionType") or ""),
            "sub_type": str(event.get("subType") or ""),
            "description": str(event.get("description") or ""),
            "team_id": str(event.get("teamId") or ""),
            "home_score": str(event.get("scoreHome") or ""),
            "away_score": str(event.get("scoreAway") or ""),
        })
    return out


def fetch_game(game_id: str, timeout: float = 30) -> dict:
    if not re.fullmatch(r"\d{10}", game_id):
        raise ValueError("Game ID must contain exactly ten digits")
    params = urllib.parse.urlencode(
        {"GameID": game_id, "StartPeriod": 0, "EndPeriod": 0}
    )
    req = urllib.request.Request(
        "https://stats.nba.com/stats/playbyplayv3?" + params, headers=HEADERS
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def write_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-id", required=True)
    parser.add_argument("--input-json", type=Path, help="Offline NBA PBP JSON")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8")) if args.input_json else fetch_game(args.game_id)
    rows = normalize(payload, args.game_id)
    if not rows:
        raise ValueError("No PBP actions returned for game")
    output = args.output or Path("data/processed/pbp") / f"{args.game_id}.csv"
    write_csv(rows, output)
    print(f"Normalized {len(rows)} play-by-play events -> {output}")


if __name__ == "__main__":
    main()
