# Step 2.1 — NBA Win Probability State Dataset

## Purpose and status

**Step 2.1 prepares data only; no model is fitted.** It converts real NBA CDN play-by-play into a reproducible fourth-quarter/overtime state table with a terminal game winner as its label. This deliberately uses **complete game PBP sources**, rather than the two-minute candidate table from Step 1.

Run:

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
python -m beyond_the_whistle.wp_dataset
```

Outputs:

- `data/win_probability/wp_q4_states_2021_2024.csv`
- `data/win_probability/wp_q4_manifest.json` (source URLs, archive SHA-256, splits and exclusions)

## Data cohort and chronological partitioning

Only **NBA regular-season games** from CDN-derived historical event archives are used at this stage:

| Split | NBA seasons |
|---|---|
| Training | 2021–22 and 2022–23 |
| Validation | 2023–24 |
| Held-out test | 2024–25 |

All Q4 and OT events are eligible to contribute a *post-action* state. We retain at most one state per game, period and **30-second remaining-clock bucket**, choosing the latest event in that bucket by the upstream action ordering. This avoids counting dozens of nearby substitution, foul and timeout events as if they were independent time points.

The **target** `home_win` is 1 if the home team's verified final score exceeds the away team's; otherwise 0. We only label games whose final action identifies a game/period end at 0 seconds. Games with an incomplete or tied final state are excluded. No final-buzzer state is used as a model input.

The input features are `period`, `seconds_remaining`, `home_score`, `away_score`, `home_margin`, and `seconds_into_period`. `game_id`, `season_start_year`, and `split` are **metadata**, not model features.

## Leakage prevention

1. The winner is computed using the last event **only after** selecting historical state features; the final winner never appears among predictor columns.
2. Every observation uses only period, clock and score **observed immediately after that action**, before the final buzzer.
3. Whole games stay in one chronological split; a game never contributes both training and test rows.
4. Terminal game-end status is required to label a result, so interrupted/incomplete games are not silently assigned a winner.
5. The manifest reports actual source game counts, missing/invalid rows and excluded games.

A critical next-step rule: **do not apply random row-level cross-validation**. Repeated state observations from the same game are dependent. Evaluate by game and by held-out season, with calibration plots, Brier score and log loss in Step 2.2.

## Research limitations

- The dataset is intentionally restricted to Q4 and overtime of **regular-season games**. Play-In/playoffs and early quarters can be added later with explicit domain and competition checks.
- Only visible clock and score features are currently used; possession, bonus, timeouts, player lineups and team priors are not inferred from ambiguous fields.
- One row every 30-second *occupied clock bucket* means the observed state sampling is not a uniformly spaced true clock grid. Bins with no play-by-play events are absent.
- Sampling post-action states avoids leaking future scores, but it changes the estimand relative to pre-whistle win probability. A future counterfactual study must align the model's state definition.
- Train/validation/test splits are **by year**, not randomly shuffled. Performance may shift across rule changes, roster distributions, and offense environments.
- The current dataset does not imply any referee error or its impact, and Step 2.1 should not be called a trained or calibrated win probability model.

## Next: Step 2.2

Fit a calibrated baseline win probability model using **training-only preprocessing**, select hyperparameters with the 2023–24 validation set, freeze the model specification, then report **held-out 2024–25** Brier score, log loss, and calibration curves. Sensitivity tests should separate late close games from blowouts and examine per-game weighting.
