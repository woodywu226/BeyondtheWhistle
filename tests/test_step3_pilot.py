import shutil
from collections import Counter

import pytest

from beyond_the_whistle.step3_pilot import OUTPUT, agreement, summarize, window


def test_boundary_and_empty_pilot():
    assert window(120.01) == "pre"
    assert window(120) == window(0) == "post"
    with pytest.raises(ValueError):
        window(-1)
    result = summarize(OUTPUT)
    assert result["status"] == "awaiting_independent_review"
    for name in ("pre", "post"):
        assert result["windows"][name]["counts"]["segments_scheduled"] == 100
        assert result["windows"][name]["whistles_per_100_possessions"] is None
    assert result["windows"]["overall"]["cohens_kappa"] is None


def test_agreement_uses_original_label_pairs(tmp_path):
    pairs = Counter({("CC", "CC"): 1, ("INC", "CC"): 1})
    assert agreement(pairs)["raw_agreement"] == 0.5
    assert agreement(pairs)["cohens_kappa"] == 0
    assert agreement(Counter({("CC", "CC"): 2}))["cohens_kappa"] is None

    directory = tmp_path / "pilot"
    shutil.copytree(OUTPUT, directory)
    fields = "incident_id,label,locatable,review_seconds,video_timestamp,reason\n"
    (directory / "labels_a.csv").write_text(fields + "UNKNOWN,CC,yes,10,0:30,\n")
    with pytest.raises(ValueError, match="unexpected incident"):
        summarize(directory)
