"""Fetch, preserve and audit a third-party NBA L2M CSV.

This is Step 0: preparation and descriptive QA only, not event-level validation.
No claims are made that downloaded records match NBA official reports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/atlhawksfanatic/L2M/"
    "master/1-tidy/L2M/L2M_stats_nba.csv"
)
VALID_GRADES = {"CC", "CNC", "IC", "INC"}
REQUIRED_FIELDS = {"season", "call_type"}
MAX_BYTES = 80_000_000


def download_csv(url: str = SOURCE_URL, timeout: int = 40) -> bytes:
    """Download a source CSV with an upper size limit; never silently use fake data."""
    request = urllib.request.Request(url, headers={"User-Agent": "BeyondTheWhistle/0.0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Input is larger than the allowed 80 MB")
    if not data.strip():
        raise ValueError("Downloaded CSV is empty")
    return data


def audit_csv(data: bytes) -> dict:
    """Inspect source schema and basic completeness without claiming ground-truth accuracy."""
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Source CSV is not UTF-8") from exc
    import io

    reader = csv.DictReader(io.StringIO(decoded))
    columns = reader.fieldnames or []
    if not columns or len(columns) != len(set(columns)):
        raise ValueError("Missing or duplicate CSV column names")
    missing = sorted(REQUIRED_FIELDS - set(columns))
    if missing:
        raise ValueError(f"Missing required source columns: {missing}")

    rows = list(reader)
    if not rows:
        raise ValueError("Source CSV contains no data rows")
    counts = Counter((row.get("call_type") or "").strip().upper() for row in rows)
    by_season = Counter((row.get("season") or "").strip() for row in rows)
    missing_values = {
        key: sum(not (row.get(key) or "").strip() for row in rows)
        for key in sorted(REQUIRED_FIELDS)
    }
    unknown_grades = {grade: n for grade, n in counts.items() if grade not in VALID_GRADES}
    return {
        "row_count": len(rows),
        "columns": columns,
        "column_count": len(columns),
        "grade_counts": dict(sorted(counts.items())),
        "unknown_grade_counts": unknown_grades,
        "season_counts": dict(sorted(by_season.items())),
        "missing_required_values": missing_values,
        "limitations": [
            "Third-party records are not independently checked against official L2M reports.",
            "CNC is a selection of notable non-calls, not all unwhistled actions.",
            "Official report eligibility and annotation conventions vary by era.",
            "No play-by-play matching, referee attribution, or causal estimation has been done.",
        ],
    }


def prepare(data: bytes, raw_path: Path, report_path: Path, source: str) -> dict:
    """Audit before writing; retain original bytes and provenance."""
    audit = audit_csv(data)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(data)
    report = {
        "source_url": source,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "raw_path": str(raw_path),
        "status": "downloaded_and_schema_audited_not_officially_validated",
        **audit,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and audit NBA L2M source CSV")
    parser.add_argument("--input", type=Path, help="Local CSV; otherwise download source URL")
    parser.add_argument("--raw", type=Path, default=Path("data/raw/l2m_source.csv"))
    parser.add_argument(
        "--report", type=Path, default=Path("data/processed/l2m_audit.json")
    )
    args = parser.parse_args()
    data = args.input.read_bytes() if args.input else download_csv()
    source = str(args.input) if args.input else SOURCE_URL
    report = prepare(data, args.raw, args.report, source)
    print(
        f"Prepared {report['row_count']} source rows; "
        f"SHA256={report['sha256']}; see {args.report}"
    )
    if report["unknown_grade_counts"]:
        print("WARNING: Unknown call_type values detected; inspect the QA report.")


if __name__ == "__main__":
    main()
