import hashlib
import json

import pytest

from beyond_the_whistle.prepare_l2m import audit_csv, prepare


SAMPLE = b"season,call_type,decision,period,time,GameId\n2025,Foul,CC,4,1:00,001\n2025,Foul,INC,4,1:02,001\n2024,Travel,CNC,4,0:30,002\n"


def test_audit_counts_and_seasons():
    result = audit_csv(SAMPLE)
    assert result["row_count"] == 3
    assert result["grade_counts"] == {"CC": 1, "CNC": 1, "INC": 1}
    assert result["season_counts"] == {"2024": 1, "2025": 2}
    assert result["unknown_grade_counts"] == {}


def test_rejects_missing_required_columns():
    with pytest.raises(ValueError, match="Missing required"):
        audit_csv(b"season,GameId\n2025,001\n")


def test_rejects_empty_file():
    with pytest.raises(ValueError, match="Missing or duplicate"):
        audit_csv(b"")


def test_flags_unexpected_grade():
    result = audit_csv(b"season,call_type,decision,period,time\n2025,Foul,UNKNOWN,4,1:02\n")
    assert result["unknown_grade_counts"] == {"UNKNOWN": 1}


def test_prepare_preserves_original_and_provenance(tmp_path):
    raw = tmp_path / "raw" / "l2m.csv"
    report_path = tmp_path / "processed" / "audit.json"
    result = prepare(SAMPLE, raw, report_path, "local-test")
    assert raw.read_bytes() == SAMPLE
    assert result["sha256"] == hashlib.sha256(SAMPLE).hexdigest()
    saved = json.loads(report_path.read_text())
    assert saved["status"] == "downloaded_and_schema_audited_not_officially_validated"
