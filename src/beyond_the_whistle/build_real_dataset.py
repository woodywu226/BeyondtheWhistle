"""Build an auditable 2024-25 cross-source L2M/PBP matching dataset.

Data sources are independent GitHub-hosted community archives of NBA records.
Only limited factual match keys and aggregate audit metrics are committed.
The full upstream CSV files remain local to the runner.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

L2M_URL = "https://raw.githubusercontent.com/atlhawksfanatic/L2M/master/1-tidy/L2M/L2M_stats_nba.csv"
PBP_URL = "https://raw.githubusercontent.com/ramirobentes/nba_pbp_data/main/pbp-final-2025/data.csv"
VALID_DECISIONS = {"CC", "IC", "CNC", "INC"}
MATCH_FIELDS = [
    "l2m_record", "game_id", "period", "clock", "decision", "call_category",
    "pbp_event_num", "pbp_clock", "pbp_msg_type", "clock_gap_seconds",
    "candidate_count", "status",
]
MISSING = {"", "NA", "N/A", "NULL", "NONE"}
FOUL_TYPE = "6"
VIOLATION_TYPES = {"5", "7"}


def download(url: str, max_bytes: int = 90_000_000) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "BeyondTheWhistle/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        content = resp.read(max_bytes + 1)
    if not content or len(content) > max_bytes:
        raise ValueError("Empty or oversized download: " + url)
    return content


def parse_clock(text: str) -> float:
    text = str(text).strip()
    match = re.fullmatch(r"(\d{1,2}):(\d{2}(?:\.\d+)?)", text)
    if not match or float(match.group(2)) >= 60:
        raise ValueError("Bad clock: " + text)
    return int(match.group(1)) * 60 + float(match.group(2))


def parse_period(text: str) -> int:
    s = str(text).strip().upper()
    if s.startswith("Q") and s[1:].isdigit():
        return int(s[1:])
    if s.startswith("OT") and (s[2:].isdigit() or s == "OT"):
        return 4 + int(s[2:] or 1)
    if s.isdigit():
        return int(s)
    raise ValueError("Bad period: " + s)


def normalize_id(value: str) -> str:
    text = str(value).strip()
    return text.zfill(10) if text.isdigit() and len(text) <= 10 else ""


def clean(value: str) -> str:
    s = str(value or "").strip()
    return "" if s.upper() in MISSING else s


def category(text: str) -> str:
    value = text.lower().strip()
    if value.startswith("foul"):
        return "foul"
    if any(x in value for x in ("violation", "turnover", "travel", "out of bounds", "out-of-bounds",
                                 "double dribble", "goaltend", "basket interference")):
        return "violation_or_turnover"
    return "other"


def read_csv_bytes(data: bytes, required: set[str]) -> list[dict]:
    with io.StringIO(data.decode("utf-8-sig")) as f:
        reader = csv.DictReader(f)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError("Missing columns: " + str(missing))
        return list(reader)


def prepare(l2m_rows: list[dict], pbp_rows: list[dict], season: int = 2025) -> tuple[list[dict], dict]:
    l2m = [r for r in l2m_rows if clean(r.get("season", "")) == str(season)]
    pbp = [r for r in pbp_rows if clean(r.get("game_id", ""))]
    if not l2m or not pbp:
        raise ValueError("No records for season or PBP input is empty")

    pbp_by_game = defaultdict(list)
    pbp_meta = defaultdict(lambda: {"dates": set(), "homes": set(), "aways": set()})
    for row in pbp:
        gid = normalize_id(row.get("game_id", ""))
        if not gid:
            continue
        try:
            per, secs = parse_period(row["period"]), parse_clock(row["clock"])
        except (ValueError, KeyError):
            continue
        item = {
            "gid": gid, "period": per, "seconds": secs,
            "event_num": clean(row.get("event_num", "")),
            "msg_type": clean(row.get("msg_type", "")),
            "clock": clean(row.get("clock", "")),
        }
        pbp_by_game[(gid, per)].append(item)
        meta = pbp_meta[gid]
        meta["dates"].add(clean(row.get("game_date", "")))
        meta["homes"].add(clean(row.get("team_home", "")))
        meta["aways"].add(clean(row.get("team_away", "")))

    results = []
    game_checks = {}
    duplicate_keys = Counter()
    for i, row in enumerate(l2m):
        gid = normalize_id(clean(row.get("gid", "")) or clean(row.get("GAME_ID", "")))
        grade = clean(row.get("decision", "")).upper()
        group = category(clean(row.get("call_type", "")))
        record = {
            "l2m_record": i + 1, "game_id": gid, "period": "", "clock": clean(row.get("time", "")),
            "decision": grade, "call_category": group, "pbp_event_num": "",
            "pbp_clock": "", "pbp_msg_type": "", "clock_gap_seconds": "",
            "candidate_count": 0, "status": "",
        }
        if gid and gid not in game_checks:
            meta = pbp_meta.get(gid)
            match = bool(meta)
            date = clean(row.get("date", ""))
            home = clean(row.get("home", ""))
            away = clean(row.get("away", ""))
            game_checks[gid] = {
                "pbp_present": match,
                "date_agrees": match and date in meta["dates"],
                "home_agrees": match and home in meta["homes"],
                "away_agrees": match and away in meta["aways"],
            }
        if grade not in VALID_DECISIONS:
            record["status"] = "ungraded"
        elif not gid:
            record["status"] = "invalid_game_id"
        elif not pbp_meta.get(gid):
            record["status"] = "missing_pbp_game"
        else:
            try:
                period, secs = parse_period(row["period"]), parse_clock(row["time"])
                record["period"] = period
            except (KeyError, ValueError):
                record["status"] = "invalid_clock_or_period"
                results.append(record)
                continue
            # No official whistle exists for CNC/INC; do not force PBP matching.
            if grade in {"CNC", "INC"}:
                record["status"] = "noncall_not_in_pbp"
            elif not all(game_checks[gid].values()):
                record["status"] = "game_metadata_disagreement"
            else:
                events = [
                    p for p in pbp_by_game[(gid, period)]
                    if abs(p["seconds"] - secs) <= 1.0
                ]
                # Require corresponding event category for an eligible candidate.
                if group == "foul":
                    events = [p for p in events if p["msg_type"] == FOUL_TYPE]
                elif group == "violation_or_turnover":
                    events = [p for p in events if p["msg_type"] in VIOLATION_TYPES]
                else:
                    events = []
                record["candidate_count"] = len(events)
                if len(events) == 1:
                    e = events[0]
                    record.update({
                        "pbp_event_num": e["event_num"], "pbp_clock": e["clock"],
                        "pbp_msg_type": e["msg_type"],
                        "clock_gap_seconds": round(abs(e["seconds"] - secs), 3),
                        "status": "unique_clock_type_candidate_unverified",
                    })
                elif len(events) > 1:
                    record["status"] = "multiple_clock_type_candidates"
                else:
                    record["status"] = "no_clock_type_candidate"
        key = (gid, str(record["period"]), record["clock"], grade, group)
        duplicate_keys[key] += 1
        results.append(record)

    statuses = Counter(r["status"] for r in results)
    grades = Counter(r["decision"] or "BLANK" for r in results)
    game_count = len(game_checks)
    valid_games = sum(all(fields.values()) for fields in game_checks.values())
    checks = {k: sum(v[k] for v in game_checks.values()) for k in
              ("pbp_present", "date_agrees", "home_agrees", "away_agrees")}
    audit = {
        "season_end_year": season,
        "l2m_rows": len(l2m),
        "l2m_distinct_games": game_count,
        "pbp_distinct_games_in_source": len(pbp_meta),
        "metadata_consistent_games": valid_games,
        "game_metadata_coverage_pct": round(100 * valid_games / game_count, 2) if game_count else 0,
        "missing_pbp_game_ids": sorted(g for g, result in game_checks.items() if not result["pbp_present"]),
        "metadata_validation_counts": checks,
        "l2m_grade_counts": dict(sorted(grades.items())),
        "status_counts": dict(sorted(statuses.items())),
        "unique_clock_and_type_candidates": statuses["unique_clock_type_candidate_unverified"],
        "ambiguous_candidates": statuses["multiple_clock_type_candidates"],
        "repeated_l2m_record_keys": sum(n-1 for n in duplicate_keys.values() if n > 1),
        "interpretation": [
            "Metadata agreement checks game/date/home/away, not event-level correctness.",
            "Unique time and event-type candidate is NOT verified same play.",
            "CNC and INC noncalls have no obligatory PBP whistle event.",
            "L2M is selectively eligible and does not represent all close games.",
            "This is not a referee accuracy estimate or causal effect estimate.",
        ],
    }
    return results, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--l2m-file", type=Path)
    parser.add_argument("--pbp-file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/validated"))
    args = parser.parse_args()
    l2m_data = args.l2m_file.read_bytes() if args.l2m_file else download(L2M_URL)
    pbp_data = args.pbp_file.read_bytes() if args.pbp_file else download(PBP_URL)
    l2m_rows = read_csv_bytes(l2m_data, {"season", "gid", "period", "time", "decision",
                                           "call_type", "date", "home", "away"})
    pbp_rows = read_csv_bytes(pbp_data, {"game_id", "period", "clock", "msg_type",
                                           "game_date", "team_home", "team_away", "event_num"})
    matches, audit = prepare(l2m_rows, pbp_rows, args.season)
    audit.update({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "l2m_upstream": L2M_URL if not args.l2m_file else str(args.l2m_file),
        "pbp_upstream": PBP_URL if not args.pbp_file else str(args.pbp_file),
        "l2m_sha256": hashlib.sha256(l2m_data).hexdigest(),
        "pbp_sha256": hashlib.sha256(pbp_data).hexdigest(),
    })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / f"l2m_pbp_{args.season}_candidates.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MATCH_FIELDS)
        writer.writeheader()
        writer.writerows(matches)
    audit_path = args.output_dir / f"l2m_pbp_{args.season}_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))
    print("WROTE", csv_path, audit_path)


if __name__ == "__main__":
    main()
