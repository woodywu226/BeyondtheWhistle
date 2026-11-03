from beyond_the_whistle.review_queue import sample_for_review


def test_review_queue_is_stratified_and_unadjudicated():
    rows = []
    for grade in ("CC", "IC", "CNC", "INC"):
        for i in range(5):
            rows.append({
                "l2m_record": str(len(rows) + 1),
                "game_id": f"0022400{i:03d}",
                "period": "4", "clock": "01:10", "decision": grade,
                "call_category": "foul", "status": "unverified",
                "pbp_event_num": "",
            })
    sample = sample_for_review(rows, per_grade=2, seed=2026)
    assert len(sample) == 8
    assert {grade: sum(r["decision"] == grade for r in sample)
            for grade in ("CC", "IC", "CNC", "INC")} == {
                "CC": 2, "IC": 2, "CNC": 2, "INC": 2
            }
    assert all(not r["same_event_verified"] for r in sample)
    assert all(not r["reviewer_decision"] for r in sample)
    assert sample == sample_for_review(rows, per_grade=2, seed=2026)
