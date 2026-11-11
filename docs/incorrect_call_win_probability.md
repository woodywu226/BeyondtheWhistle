# Incorrect-call win-probability scenarios

The first version uses the frozen [Step 2 baseline](step2_complete.md) to compare
a documented observed state with one or more rule-supported alternative states.
The target is an official **incorrect call (IC)**. Incorrect non-calls (INC)
require their own incident reconstruction.

## Case inventory

The 2024–25 candidate table contains 66 official IC records across 60 games.
Of these, 43 have one unverified clock-and-type candidate in play-by-play,
19 have no compatible candidate, and four have multiple candidates. These
counts describe matching coverage. The two worked cases below use official
report and play-by-play evidence. Independent video review is pending.

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
The CLI checks the record and game against the IC table. Use
`evidence_status: "official_report_and_pbp"` for a provisional analysis
grounded in those sources. The report's clip identifier may serve as the
video reference in that case. The CLI reports the evidence status with
the probabilities.

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
inputs, and track missing context for a future model.

## First two real-game cases

Both event links agree on the game, period, clock and player named for
the called foul. The corrected score and clock remain scenario assumptions.
The examples were selected because they have an exact-clock foul match and
illustrate two different ruling corrections. They do not estimate an
average effect across the 66 official IC records.

| Official IC | Affected team | Observed state | Corrected score scenarios at the same clock | Platt ΔWP (percentage points) |
| --- | --- | --- | --- | --- |
| [330](../data/validated/ic_cases/330.json) | Washington (away) | WAS 118–114, Q4 41.9 s, after both Atlanta free throws | No foul and 0 or 2 Atlanta points on the drive | +2.01 or 0.00 |
| [4039](../data/validated/ic_cases/4039.json) | Orlando (away) | ORL 94–99, Q4 50.6 s, with no free throws awarded | Continuation on an assumed unsuccessful two-point attempt and 0, 1 or 2 made Orlando free throws | 0.00, +3.78 or +12.67 |

The fixed clock isolates score differences. Possession, rebounds and
elapsed time on a continued play remain outside these estimates.
Under raw probabilities the respective deltas are +3.48 or 0.00
and 0.00, +3.97 or +12.30 percentage points.

```bash
python -m beyond_the_whistle.wp_incorrect_call --case data/validated/ic_cases/330.json
python -m beyond_the_whistle.wp_incorrect_call --case data/validated/ic_cases/4039.json
```

Sources: [NBA L2M JSON for WAS–ATL](https://official.nba.com/l2m/json/0022400103.json),
[NBA L2M JSON for ORL–GSW](https://official.nba.com/l2m/json/0022400708.json),
[NBA Rule 12](https://official.nba.com/rule-no-12-fouls-and-penalties/),
and [2024–25 NBA CDN play-by-play archive](https://github.com/shufinskiy/nba_data/blob/main/datasets/cdnnba_2024.tar.xz)
(SHA-256 `35a82e6b29821adb22b8474dea8c51e08847d8e00690d1d5ffde7d000e0087d1`).
