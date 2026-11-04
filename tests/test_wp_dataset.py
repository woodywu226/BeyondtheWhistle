"""Synthetic regressions only. Real-season QA is separately run in Actions."""
import csv
import io
import tarfile

import pytest

from beyond_the_whistle.wp_dataset import (
    SPLITS,
    extract_archive,
    extract_states,
    validate,
)

FIELDS = [
    "gameId", "period", "clock", "actionType", "subType",
    "orderNumber", "actionNumber", "scoreHome", "scoreAway",
]


def fixture_csv(home_win: bool = True) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(FIELDS)
    writer.writerows([
        ["0022400001", 4, "PT2M12.00S", "shot", "made", 10, 10, 99, 97],
        ["0022400001", 4, "PT1M47.00S", "shot", "made", 20, 20, 101, 97],
        ["0022400001", 4, "PT1M31.00S", "foul", "personal", 30, 30, 101, 97],
        [
            "0022400001", 4, "PT00M00.00S", "period", "end", 40, 40,
            103 if home_win else 101, 100 if home_win else 104,
        ],
    ])
    return buf.getvalue().encode()


def test_post_action_scores_and_buckets():
    states, audit = extract_states(fixture_csv(), 2021)
    assert audit["games_in_dataset"] == 1
    assert audit["states_created"] == 2
    assert [s["seconds_remaining"] for s in states] == [132.0, 91.0]
    assert [s["home_margin"] for s in states] == [2, 4]
    assert all(s["home_win"] == 1 for s in states)


def test_future_outcome_does_not_modify_historical_features():
    a, _ = extract_states(fixture_csv(True), 2024)
    b, _ = extract_states(fixture_csv(False), 2024)
    assert [(r["home_margin"], r["seconds_remaining"]) for r in a] == [
        (r["home_margin"], r["seconds_remaining"]) for r in b
    ]
    assert all(r["home_win"] == 0 for r in b)


def test_no_verified_final_buzzer_means_no_labels():
    text = fixture_csv().decode().replace(",period,end,40,40,", ",shot,made,40,40,")
    states, audit = extract_states(text.encode(), 2021)
    assert not states
    assert audit["excluded_games"]["unverified_final_buzzer"] == 1


def test_one_snapshot_per_clock_bucket():
    rows, _ = extract_states(fixture_csv(), 2022, bucket_seconds=60)
    assert len(rows) == 2
    assert rows[-1]["home_score"] == 101


def test_chronological_split_and_game_separation():
    rows = []
    for season in SPLITS:
        batch, _ = extract_states(fixture_csv(), season)
        for row in batch:
            row["game_id"] = str(season)
        rows.extend(batch)
    audit = validate(rows)
    assert audit["games"] == 4
    assert audit["splits"]["train"]["games"] == 2
    assert audit["splits"]["test"]["games"] == 1


def test_same_game_leaking_across_splits_is_rejected():
    rows = []
    for season in SPLITS:
        batch, _ = extract_states(fixture_csv(), season)
        rows.extend(batch)
    with pytest.raises(ValueError, match="Same game"):
        validate(rows)


def test_single_member_archive():
    data = fixture_csv()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:xz") as archive:
        info = tarfile.TarInfo("cdnnba_2024.csv")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    assert extract_archive(buf.getvalue()) == data


def test_input_schema_validation():
    with pytest.raises(ValueError, match="Missing NBA CDN fields"):
        extract_states(b"gameId,period\n1,4\n", 2024)
