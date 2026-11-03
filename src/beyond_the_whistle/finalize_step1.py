"""Step 1: independently check historical L2M against NBA official JSON and
supply the two otherwise missing 2025 Play-In game play-by-play feeds.

A verified official L2M *label* is not an independently video-reviewed ruling.
PBP candidates remain unverified until manual event-level adjudication.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from beyond_the_whistle.build_archive_dataset import ARCHIVE_BASE, ARCHIVES, read_archive
from beyond_the_whistle.build_real_dataset import (
    L2M_URL,
    MATCH_FIELDS,
    clean,
    download,
    normalize_id,
    parse_clock,
    parse_period,
    prepare,
    read_csv_bytes,
)

OFFICIAL_URL = "https://official.nba.com/l2m/json/{gid}.json"
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event}"
PLAY_IN = {
    "0052400121": {"espn": "401766459", "date": "2025-04-15", "home": "GSW", "away": "MEM"},
    "0052400201": {"espn": "401766462", "date": "2025-04-18", "home": "ATL", "away": "MIA"},
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
           "AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36",
           "Referer": "https://official.nba.com/", "Accept": "application/json"}


def fetch_json(url: str, attempts: int = 3) -> dict:
    error = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=HEADERS), timeout=20
            ) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise TypeError("Expected JSON object")
            return payload
        except (OSError, ValueError, TypeError) as exc:
            error = exc
            if attempt + 1 < attempts:
                time.sleep(0.75 * (attempt + 1))
    raise RuntimeError(f"Data fetch failed for {url}: {error}") from error


def normalize_grade(value: str) -> str:
    cleaned = str(value or "").strip().upper().rstrip("*")
    return {"NCC": "CNC", "NCI": "INC"}.get(cleaned, cleaned)


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or "")).strip()).casefold()


def canonical_l2m(record: dict, official: bool) -> tuple:
    """A multiset key: exact period and tenth-of-second clock, grade and ruling type."""
    period = record.get("PeriodName") if official else record.get("period")
    clock = record.get("PCTime") if official else record.get("time")
    kind = record.get("CallType") if official else record.get("call_type")
    grade = record.get("CallRatingName") if official else record.get("decision")
    return (
        parse_period(period), round(parse_clock(clock) * 10),
        normalize_label(kind), normalize_grade(grade),
    )


def compare_official(gid: str, records: list[dict], payload: dict) -> dict:
    """Independent official JSON cross-check, without treating a 403 as a negative label."""
    if not isinstance(payload.get("game"), list) or len(payload["game"]) != 1:
        raise ValueError("Official response missing one-row game metadata")
    if not isinstance(payload.get("l2m"), list):
        raise TypeError("Official response missing L2M list")
    game_id = normalize_id(payload["game"][0].get("GameId", ""))
    if game_id != gid:
        raise ValueError(f"Official game ID mismatch: {game_id} != {gid}")
    actual = Counter(canonical_l2m(x, True) for x in payload["l2m"])
    previous = Counter(canonical_l2m(x, False) for x in records)
    missing = actual - previous
    excess = previous - actual
    return {
        "game_id": gid,
        "official_count": sum(actual.values()),
        "community_count": sum(previous.values()),
        "matching_rows": sum((actual & previous).values()),
        "missing_from_community": sum(missing.values()),
        "extra_in_community": sum(excess.values()),
        "exact_multiset_match": not missing and not excess,
    }


def official_audit(l2m: list[dict], workers: int = 4) -> dict:
    by_game = defaultdict(list)
    for row in l2m:
        gid = normalize_id(row.get("gid", "") or row.get("GAME_ID", ""))
        if gid:
            by_game[gid].append(row)

    def fetch_and_compare(item: tuple[str, list[dict]]) -> dict:
        gid, rows = item
        try:
            return compare_official(gid, rows, fetch_json(OFFICIAL_URL.format(gid=gid)))
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            return {"game_id": gid, "error": str(exc)[:280]}

    verified = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_and_compare, item) for item in sorted(by_game.items())]
        for future in as_completed(futures):
            verified.append(future.result())
    verified.sort(key=lambda row: row["game_id"])
    ok = [r for r in verified if "error" not in r]
    disagreements = [r for r in ok if not r["exact_multiset_match"]]
    failures = [r for r in verified if "error" in r]
    return {
        "attempted_games": len(by_game),
        "official_reports_fetched": len(ok),
        "exactly_matching_games": sum(r["exact_multiset_match"] for r in ok),
        "official_rows_checked": sum(r["official_count"] for r in ok),
        "community_rows_checked": sum(r["community_count"] for r in ok),
        "exactly_matched_event_rows": sum(r["matching_rows"] for r in ok),
        "differences": disagreements,
        "fetch_or_parse_failures": failures,
        "game_level_results": verified,
        "label_interpretation": "Direct comparison with NBA official retrospective grading; "
                                "not independent video adjudication.",
    }


def read_espn_play_in(gid: str, payload: dict) -> tuple[list[dict], dict]:
    settings = PLAY_IN[gid]
    competitions = payload.get("header", {}).get("competitions", [])
    if not competitions:
        raise ValueError("ESPN summary lacks competition header")
    participants = competitions[0].get("competitors", [])
    home = next((p for p in participants if p.get("homeAway") == "home"), None)
    away = next((p for p in participants if p.get("homeAway") == "away"), None)
    if home is None or away is None:
        raise ValueError("ESPN home/away teams unavailable")
    aliases = {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "UTAH": "UTA"}
    h = aliases.get(home["team"]["abbreviation"], home["team"]["abbreviation"])
    a = aliases.get(away["team"]["abbreviation"], away["team"]["abbreviation"])
    if (h, a) != (settings["home"], settings["away"]):
        raise ValueError(f"ESPN team mismatch for {gid}: {(h, a)}")
    actions = payload.get("plays")
    if not isinstance(actions, list) or len(actions) < 100:
        raise ValueError(f"ESPN play-by-play unavailable for {gid}")
    events = []
    for event in actions:
        period = event.get("period", {}).get("number")
        clock = event.get("clock", {}).get("displayValue", "")
        try:
            seconds = parse_clock(clock)
            per = parse_period(str(period))
        except (ValueError, TypeError):
            continue
        if per < 4 or seconds > 121:
            continue
        label = str(event.get("type", {}).get("text") or "").lower()
        description = str(event.get("text") or "").lower()
        combined = label + " " + description
        if "foul" in combined:
            kind = "6"
        elif "turnover" in combined:
            kind = "5"
        elif "violation" in combined:
            kind = "7"
        else:
            kind = "other"
        events.append({
            "game_id": gid, "period": str(per), "clock": clock,
            "msg_type": kind,
            "event_num": str(event.get("sequenceNumber") or event.get("id") or ""),
            "game_date": settings["date"], "team_home": h, "team_away": a,
        })
    if not events:
        raise ValueError("No late-game actions in ESPN game")
    return events, {
        "game_id": gid, "espn_event_id": settings["espn"],
        "actions_available": len(actions), "retained_clutch_actions": len(events),
        "game_date": settings["date"], "home": h, "away": a,
    }


def build(output: Path, official_workers: int = 4) -> dict:
    source = download(L2M_URL)
    all_l2m = read_csv_bytes(
        source, {"season", "gid", "period", "time", "decision",
                 "call_type", "date", "home", "away"}
    )
    l2m = [r for r in all_l2m if clean(r.get("season", "")) == "2025"]
    pbp = []
    provenance = []
    for archive_name in ARCHIVES:
        url = ARCHIVE_BASE + archive_name
        archive = download(url, max_bytes=45_000_000)
        rows, qa = read_archive(archive)
        pbp.extend(rows)
        provenance.append({"url": url, "sha256": hashlib.sha256(archive).hexdigest(), **qa})
    playins = []
    for gid in PLAY_IN:
        rows, qa = read_espn_play_in(gid, fetch_json(ESPN_URL.format(event=PLAY_IN[gid]["espn"])))
        pbp.extend(rows)
        playins.append(qa)
    matches, audit = prepare(l2m, pbp)
    official = official_audit(l2m, workers=official_workers)
    audit.update({
        "source_data_scope": "2024-25 regular season, play-in, playoffs",
        "l2m_upstream": L2M_URL, "l2m_sha256": hashlib.sha256(source).hexdigest(),
        "pbp_archives": provenance, "play_in_espn_pbp": playins,
        "official_comparison_summary": {k: v for k, v in official.items()
                                        if k not in ("game_level_results", "differences", "fetch_or_parse_failures")},
        "official_exact_match_games": official["exactly_matching_games"],
        "official_comparison_mismatch_games": [
            r["game_id"] for r in official["differences"]
        ],
        "official_comparison_failed_games": [
            r["game_id"] for r in official["fetch_or_parse_failures"]
        ],
        "qualification": "Automatic official JSON label verification, not independent video review. "
                         "PBP unique candidates not definitive.",
    })
    output.mkdir(parents=True, exist_ok=True)
    with (output / "l2m_pbp_2025_candidates.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MATCH_FIELDS)
        writer.writeheader()
        writer.writerows(matches)
    (output / "l2m_pbp_2025_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "l2m_2025_official_comparison.json").write_text(
        json.dumps(official, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "l2m_rows": audit["l2m_rows"],
        "l2m_games": audit["l2m_distinct_games"],
        "metadata_consistent_games": audit["metadata_consistent_games"],
        "missing_pbp": audit["missing_pbp_game_ids"],
        "official_fetched": official["official_reports_fetched"],
        "official_exact_games": official["exactly_matching_games"],
        "official_mismatches": len(official["differences"]),
        "official_failures": len(official["fetch_or_parse_failures"]),
        "statuses": audit["status_counts"],
    }, indent=2))
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("data/validated"))
    parser.add_argument("--official-workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.official_workers <= 8:
        parser.error("--official-workers must be between 1 and 8")
    build(args.output_dir, args.official_workers)


if __name__ == "__main__":
    main()
