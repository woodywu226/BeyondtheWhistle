# Incorrect-call win-probability scenarios

The first version uses the frozen [Step 2 baseline](step2_complete.md) to compare
a documented observed state with one or more rule-supported alternative states.
The target is an official **incorrect call (IC)**. Incorrect non-calls (INC)
require their own incident reconstruction.

## Case inventory

The 2024–25 candidate table contains 66 official IC records across 60 games.
Of these, 43 have one unverified clock-and-type candidate in play-by-play,
19 have no compatible candidate, and four have multiple candidates. These
counts describe matching coverage. Each real case requires independent video
verification and rule-based state reconstruction before scoring.

```bash
python -m pip install -e ".[dev,ml]"
python -m beyond_the_whistle.wp_incorrect_call
```

## Score a reconstructed case

Use post-resolution score and clock states for both paths at comparable points
in the sequence. Document when they differ and what happened to play
continuation, possession and free throws. Each alternative requires a written
assumption. Real cases also require the official `l2m_record`, matching
`game_id`, `video_reference`, `verification_notes` and `rule_reference`.
These references document the reviewer's work. The CLI checks that the record
and game exist in the IC table, while the reviewer is responsible for checking
the footage, ruling and states.

The following hypothetical example removes two made away free throws in a
corrected scenario. Save it as `case.json`.

```json
{
  "hypothetical": true,
  "affected_team": "home",
  "observed": {"period": 4, "seconds_remaining": 30, "home_score": 100, "away_score": 101},
  "alternatives": [
    {
      "assumption": "The away free throws are removed and play restarts with 30 seconds remaining.",
      "state": {"period": 4, "seconds_remaining": 30, "home_score": 100, "away_score": 99}
    }
  ]
}
```

```bash
python -m beyond_the_whistle.wp_incorrect_call --case case.json
```

The CLI reports corrected minus observed win probability in percentage points
for the affected team. With multiple branches it reports their min–max range.
This range reflects the supplied assumptions. It is neither a sampling
confidence interval nor an identified causal effect.

The baseline can score resolved score-clock states. If two branches differ only
in possession, bonus, or pending free throws, the current model assigns the same
probability to both. Use only resolved scenarios with defensible score-clock
inputs, and track missing context for a future model. Real-case effect estimates
remain pending video review and state reconstruction.
