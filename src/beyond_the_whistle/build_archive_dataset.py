"""Streaming adapter for full 2024-25 NBA CDN play-by-play archives.

Source archives are from shufinskiy/nba_data and remain in runner memory.
Only last-two-minute event keys are retained. No raw PBP is republished.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tarfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from beyond_the_whistle.build_real_dataset import (
    L2M_URL,
    MATCH_FIELDS,
    download,
    parse_period,
    prepare,
    read_csv_bytes,
)

ARCHIVE_BASE = "https://raw.githubusercontent.com/shufinskiy/nba_data/main/datasets/"
ARCHIVES = ("cdnnba_2024.tar.xz", "cdnnba_po_2024.tar.xz")


def iso_clock_seconds(value: str) -> float:
    """Parse the CDN's time remaining, e.g. PT01M52.00S."""
    import re

    m = re.fullmatch(r"PT(?:(\d+)M)?(\d+(?:\.\d+)?)S", str(value))
    if not m:
        raise ValueError("Unrecognized CDN clock: " + str(value))
    return int(m.group(1) or 0) * 60 + float(m.group(2))


def read_archive(data: bytes) -> tuple[list[dict], dict]:
    """Read a bounded .tar.xz archive and infer teams from confirmed score changes."""
    events = []
    meta = defaultdict(lambda: {"date": "", "home": "", "away": "",
                                "score_home": 0, "score_away": 0})
    count = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as archive:
        members = [m for m in archive.getmembers() if m.isfile() and m.name.endswith(".csv")]
        if len(members) != 1:
            raise ValueError("Expected exactly one CSV archive member")
        member = members[0]
        if member.size > 350_000_000:
            raise ValueError("Unexpectedly large decompressed CSV")
        source = archive.extractfile(member)
        if source is None:
            raise ValueError("Archive CSV missing")
        with io.TextIOWrapper(source, encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            required = {"gameId", "period", "clock", "timeActual", "teamTricode",
                        "actionType", "actionNumber", "scoreHome", "scoreAway"}
            if not required.issubset(set(rows.fieldnames or [])):
                raise ValueError("Unexpected CDN archive schema")
            for row in rows:
                count += 1
                gid = str(row["gameId"]).strip().zfill(10)
                if not gid.isdigit():
                    continue
                state = meta[gid]
                if not state["date"] and row["timeActual"]:
                    try:
                        when = datetime.fromisoformat(row["timeActual"].replace("Z", "+00:00"))
                        state["date"] = when.astimezone(ZoneInfo("America/New_York")).date().isoformat()
                    except ValueError:
                        pass
                tricode = row["teamTricode"].strip()
                try:
                    h, a = int(row["scoreHome"]), int(row["scoreAway"])
                    if h > state["score_home"] and a == state["score_away"] and tricode:
                        state["home"] = tricode
                    if a > state["score_away"] and h == state["score_home"] and tricode:
                        state["away"] = tricode
                    state["score_home"], state["score_away"] = h, a
                except ValueError:
                    pass
                try:
                    period = parse_period(row["period"])
                    seconds = iso_clock_seconds(row["clock"])
                except ValueError:
                    continue
                if period < 4 or seconds > 121:
                    continue
                typ = row["actionType"].lower().strip()
                msg_type = {"foul": "6", "turnover": "5", "violation": "7"}.get(typ, "other")
                events.append({
                    "game_id": gid, "period": str(period),
                    "clock": f"{int(seconds // 60):02d}:{seconds % 60:05.2f}",
                    "msg_type": msg_type,
                    "event_num": row["actionNumber"],
                })
    for e in events:
        state = meta[e["game_id"]]
        e.update({"game_date": state["date"],
                  "team_home": state["home"], "team_away": state["away"]})
    return events, {
        "games_in_archive": len(meta),
        "all_pbp_action_rows": count,
        "retained_clutch_actions": len(events),
        "games_with_inferred_teams": sum(bool(v["home"] and v["away"]) for v in meta.values()),
        "games_with_date": sum(bool(v["date"]) for v in meta.values()),
    }


def build(season: int, output: Path) -> dict:
    if season != 2025:
        raise ValueError("Current full archive adapter is scoped to season end year 2025")
    source_bytes = download(L2M_URL)
    l2m = read_csv_bytes(source_bytes, {"season", "gid", "period", "time", "decision",
                                         "call_type", "date", "home", "away"})
    combined = []
    provenance = []
    for name in ARCHIVES:
        url = ARCHIVE_BASE + name
        data = download(url, max_bytes=45_000_000)
        events, qa = read_archive(data)
        combined.extend(events)
        provenance.append({"url": url, "sha256": hashlib.sha256(data).hexdigest(), **qa})
    matches, audit = prepare(l2m, combined, season)
    audit.update({
        "source_data_scope": "2024-25 regular season and playoffs",
        "l2m_upstream": L2M_URL,
        "l2m_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "pbp_archives": provenance,
        "coverage_limitation": "This covers source-available records and checks metadata; "
                               "clock/type candidates still need manual event verification.",
    })
    output.mkdir(parents=True, exist_ok=True)
    with (output / "l2m_pbp_2025_candidates.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MATCH_FIELDS)
        writer.writeheader()
        writer.writerows(matches)
    (output / "l2m_pbp_2025_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--output-dir", type=Path, default=Path("data/validated"))
    args = parser.parse_args()
    build(args.season, args.output_dir)


if __name__ == "__main__":
    main()
