# Win probability after an out-of-bounds ruling

This pilot compares the actual possession award with the possession
specified in the official Last Two Minute (L2M) correction. Each comparison
holds the score, period and game clock fixed. Win probability is reported
for the team that should have received the ball.

## Model and holdout

The training sample consists of Q4 and overtime out-of-bounds turnovers
in the regular-season NBA CDN play-by-play archives. The receiving team
is the opponent of the team charged with the turnover. Score and clock
come from the turnover row. A verified terminal score provides the
outcome label. Later actions serve only as an audit of the receiving team.
For the 2024–25 test set, the first identifiable subsequent offensive
action agreed in 1,325 of 1,325 auditable states, with 234 other states
outside that audit.

Two logistic models use identical splits and observations. The score-clock
model uses score margin, remaining time, their interaction and an overtime
indicator. The possession model adds the receiving side and its interaction
with time. The training set spans 2021–22 and 2022–23 (2,973 states from
1,704 games), with 2023–24 for validation and 2024–25 held out for testing.

| 2024–25 cohort | States / games | Brier, score-clock | Brier, possession | AUC, score-clock | AUC, possession |
| --- | ---: | ---: | ---: | ---: | ---: |
| All sampled restarts | 1,559 / 874 | 0.07984 | 0.07946 | 0.95964 | 0.96002 |
| At most two minutes and five points apart | 109 / 96 | 0.10977 | 0.11001 | 0.92256 | 0.92189 |

Possession slightly improved overall Brier and log loss in the test
sample. Both scores were slightly worse in the held-out clutch cohort.
This pilot provides exploratory scenario estimates with limited evidence of
probability accuracy in close late-game situations.

## Case review

The case inventory covers all 19 official IC records with an out-of-bounds
category. Fourteen have an official correction, an archived score-clock
anchor within one second and subsequent play-by-play that corroborates the
actual recipient. The notes record which actions were used for each check.
Two further scenarios use the official event clock and adjacent archive
actions that support the score and observed possession. Their evidence is
marked `official_report_and_pbp_bracket` because the archived feed does not
show the award at the exact clock. Both await independent video review.

| L2M record | State at official clock | Observed → corrected award | Estimated team | Observed WP | Alternative WP | Change |
| --- | --- | --- | --- | ---: | ---: | ---: |
| [1948](https://official.nba.com/l2m/json/0022400050.json) | Q4 0:36.5, 102–102 | PHI → CHA | CHA | 43.52% | 57.40% | +13.88 pp |
| [6525](https://official.nba.com/l2m/json/0022401163.json) | Q4 1:08.0, 107–107 | GSW → SAS | SAS | 43.38% | 53.45% | +10.07 pp |

Three out-of-bounds records remain pending. The corrected path for 1219
stays live, the observed restart for 6287 is a jump ball, and the available
feed for Play-In case 6727 lacks a direct restart anchor. Model evaluation
uses regular-season data.

The model was fitted on out-of-bounds turnovers. Some reviewed events are
deflections where the offense retained possession. Inbound location,
shot clock, timeouts, lineups and team strength are unavailable to this model.
Independent film review is pending. The probability contrasts describe
modeled scenarios with different possession awards. Their accuracy under
an alternative award has not been established.

- [Case evidence and pending reasons](../data/validated/ic_oob_possession_cases.json)
- [Model metrics and per-case probabilities](../data/validated/ic_oob_possession_results.json)
- [Score-clock scenarios for the original IC review](incorrect_call_win_probability.md)
- [Source archives](https://github.com/shufinskiy/nba_data/tree/main/datasets)

## Reproduce

Place `cdnnba_2021.tar.xz` through `cdnnba_2024.tar.xz` in a local
archive directory. The results JSON records each file's SHA-256.

```bash
python -m pip install -e ".[ml]" "scikit-learn==1.8.0"
python -m beyond_the_whistle.wp_possession \
  --archives /path/to/archives \
  --cases data/validated/ic_oob_possession_cases.json \
  --output /tmp/ic_oob_possession_results.json
```
