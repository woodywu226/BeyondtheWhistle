# Step 2.2 — Calibrated NBA Win Probability Baseline

## Goal

Fit a reproducible, out-of-season NBA **post-action home-win probability** model, rather than inferring a referee's causal effect. The model reads [Step 2.1's verified Q4/OT states](../data/win_probability/wp_q4_states_2021_2024.csv).

**Outcome:** `home_win` is 1 for a verified home-team final victory; 0 otherwise. It is never an input.

## Pre-registered partition before looking at test results

| Use | NBA season | Purpose |
| --- | --- | --- |
| Fitting | 2021–22 + 2022–23 | Learn candidate models |
| Selection | Earlier 60% of 2023–24 sorted regular-season game IDs | Compare model candidates by game-balanced Brier |
| Calibration | Later 40% of 2023–24 game IDs | Fit one sigmoid/Platt calibration model |
| Final test | Entire 2024–25 held-out regular-season games | One-time unbiased out-of-time assessment |

**Game IDs—not individual rows—determine membership.** No states from a single game enter two partitions. The test season is excluded from preprocessing fit, candidate selection, and Platt calibration. Note that sorted NBA regular-season IDs provide a *roughly* chronological order, not independent randomization; the 2023–24 selection and calibration periods are temporally separated within the same season.

## Candidate models

1. **Logistic regression**, with training-only `StandardScaler`.
2. **Histogram Gradient Boosting** (`max_iter=130`, `max_leaf_nodes=15`, `learning_rate=0.06`, `min_samples_leaf=75` and `l2_regularization=2`).

Both use deterministic `random_state=226`. The model with the lower **game-balanced Brier score on the selection games** is chosen, with model name as a stable tie-breaker. We do not tune the test season.

Each model input is available at the historical *post-action state*: `period`, `seconds_remaining`, `home_score`, `away_score`, `home_margin`, `seconds_into_period`, current `score_total`, and `home_margin / sqrt(max(seconds_remaining, 1)/60)`. The latter is a time-pressure interaction engineered only from observed features. It is **not a causal model**.

No game ID, season label, `home_win`, final-score margin, post-state future events, L2M decision, player identity or referee identity is supplied as a predictor.

## Calibration and evaluation

For the chosen model, obtain **out-of-training-sample** raw probabilities from the held-out 2023–24 calibration games. Fit a logistic Platt scaler on the logit of those probabilities, with one game's total weight equal to another's. Evaluate this fitted pair on **2024–25**, without refitting.

Report:

- **Brier score:** mean squared probability error (lower is better).
- **Log loss:** cross-entropy of probability forecasts (lower is better).
- **ROC-AUC:** ranking discrimination; not calibration.
- **Game-balanced Brier and log loss:** each game, rather than each snapshot, contributes equally.
- **Reliability table:** counts, mean prediction and observed home win rate in ten 0.1-wide probability bins.
- **Late-close analysis:** time remaining <= 120 seconds and absolute home margin <= 5.
- A no-skill baseline using the **game-balanced training home-win frequency**, evaluated on the same untouched test season.

Metrics are descriptive model-performance statistics; no external referee harm or intervention effect is estimated.

## Reproduce

```bash
python -m pip install -e ".[dev,ml]"
pytest -q
ruff check .
python -m beyond_the_whistle.wp_model
```

Output directory: `models/win_probability/`.

- `wp_baseline.joblib`: fitted candidate model and Platt calibrator (load only when trusted).
- `wp_model_report.json`: selection protocol, candidate validation Brier, test metrics, SHA-256 hashes and caveats.
- `wp_test_predictions.csv`: out-of-time predictions for all held-out states.
- `wp_test_calibration.csv`: ten-bin calibration data for a reliability diagram.

The CI workflow checks final output coverage, valid probability ranges, held-out discrimination, and comparison against a fixed no-skill reference before committing the results.

## Important limits

- This is a **post-action** state win-probability model. For incorrect-call counterfactual studies, state transitions must be reconstructed at an appropriate **pre-ruling** reference time before comparing worlds.
- Repeated late-game states from the same game are correlated. Per-game equal weighting is used for fit/selection/calibration and separately reported for test. The state-level and game-balanced scores have different estimands.
- Score and clock only cannot properly account for possession, free throws pending, timeouts, bonuses, lineups, team strength, game location effects (beyond home), or other state information.
- Calibration on later 2023–24 data does not guarantee equal calibration in extremely late, close, or overtime states. Use the dedicated late-close subset.
- No bootstrap confidence interval, external multi-league validation or uncertainty-aware officiating counterfactual is claimed in Step 2.2.
- Loading `joblib` artifacts can execute code; load only the model committed by the trusted pipeline.

## Step 2.3 research directions

Validate calibration by **clock/margin strata**, examine model stability with team-level holdouts or rolling seasons, and add verified contemporaneous possession, timeout/bonus and foul context. Incorporate game-level uncertainty before the Step 3 counterfactual officiating-error model.
