# Step 2.4 — Frozen Inference and Step 2 Completion Protocol

**Scope: Step 2 is a reproducible, validated *post-action* NBA win-probability baseline, not a certified last-two-minute causal officiating model.** The initial project protocol separates baseline predictive modeling (Step 2) from counterfactual incident assessment (Step 3).

## Completed deliverables

| Milestone | Artifact | Validated outcome |
| --- | --- | --- |
| 2.1 — Chronologically split state dataset | `wp_dataset.py`, NBA snapshots and manifest | 125,812 post-action states across 4,907 games; 2021–22 and 2022–23 training, 2023–24 validation, 2024–25 test |
| 2.2 — Frozen model and out-of-time evaluation | `wp_model.py`, `wp_baseline.joblib`, model report | HistGradientBoosting selected on earlier holdout; 2024–25 AUC 0.950403, state Brier 0.090405 with Platt calibration; uncalibrated state Brier 0.089779 |
| 2.3 — Reliability and uncertainty | `wp_robustness.py`, stratum JSON and CSV artifacts | Paired, 1,000-replicate whole-game cluster bootstrap; 2024–25 sample 1,229 games. Platt-vs-raw Brier difference +0.000466 game-balanced (95% interval [−0.000748, +0.001623]) |
| 2.4 — Frozen inference interface and handoff | `wp_inference.py`, tests, this document | Public, deterministic CLI; exact feature-order enforcement, Q4/OT clock validation, explicit raw/Platt choice, warning against causal interpretation |

## Example inference

```bash
python -m pip install -e ".[dev,ml]"
python -m beyond_the_whistle.wp_inference \
  --period 4 --seconds-remaining 60 --home-score 105 --away-score 103
# Optional: --probability-version raw
```

Output is JSON containing `home_win_probability`, complementary `away_win_probability`, the probability version, the input game state, `prediction_timing=post_action`, and `causal_officiating_effect=false`. **The sample inputs are hypothetical**: do not quote the resulting probability as a measured NBA game or official incident.

The published default uses the **already-frozen Platt calibrator** for reproducibility with Step 2.2, not because it beat raw predictions. Both versions remain visible. Test-season findings must never be used to select a new calibrator without another temporally independent evaluation.

The inference API accepts only period 4 or overtime, an in-period strictly positive clock, and nonnegative integer scores. Internally it reconstructs the exact eight training features: `period`, `seconds_remaining`, `home_score`, `away_score`, `home_margin`, `seconds_into_period`, `score_total`, `margin_per_sqrt_minute`. It **does not** accept a list of arbitrary, unvetted model features.

### Reproducibility and safety

- Source and model hashes are checked by the Step 2.3 robustness audit against the frozen Step 2.2 metrics JSON; that audit reproduces overall game-balanced Brier to tolerance.
- Run all tests and code lint: `pytest -q` and `ruff check .`.
- The committed `joblib` model is deserialized by Python pickle mechanics, which **can execute code**. Load only the trusted repository artifact; do not load unsolicited user-provided files.
- The training dataset has multiple highly dependent samples per game. Inference returns conditional predictions, **not** independent observations or an interval for a particular game's result.
- Game-balanced scores represent a per-participating-game average, not equal weighting of individual whistles.

## Key interpretation

The frozen model **discriminates NBA game outcomes well in general**, but the overall 0.95 ROC-AUC is not 95% accuracy and cannot certify performance under narrow officiating counterfactual states. In 0–2-point-margin game states, the Platt game-balanced Brier was approximately 0.218, compared with 0.0856 overall. Model input limitations include the absence of **possession, pending free throws, team strength, timeouts, lineups, foul/bonus context**. These are potentially central to close-game outcomes.

## Explicit acceptance criteria and boundaries

**Step 2 may be marked complete as a *baseline research infrastructure component* once:**

1. Data split and label leakage guards pass tests.
2. Model and calibrated/unadjusted out-of-time results are saved and independently reproduced.
3. Clutch subgroup reliability and game-cluster confidence intervals are documented without test-set retraining.
4. A frozen post-action inference interface reproduces stable predictions and does not mislabel them as causal results.
5. CI verifies every deliverable on the `main` branch.

**Step 2 does not claim:**

- Match accuracy between any individual incorrect non-call and a play-by-play action.
- Independent video adjudication of official L2M grades.
- A referee-specific error rate or comparative officiating bias.
- A pre-whistle, possession-aware counterfactual win probability.
- The causally identified number of games won/lost due to officials, or the effectiveness of an intervention.

## Step 3 handoff: go/no-go gate

Before simulating officiating scenarios:

1. Establish verified incident IDs, video/source timestamps and reviewer agreement.
2. Reconstruct pre-decision states including possession and free-throw/bonus context, and verify they are consistently aligned with official L2M periods/clocks.
3. Pre-register scenario actions and stochastic branches (e.g., free-throw attempts and conditional possession), and show sensitivity to these choices.
4. Assess calibration on relevant **pre-decision** state cohorts via chronological holdout. Rebuild and revalidate if those inputs differ from the Step 2 model schema.
5. Report uncertainty at game and event level; clearly separate model-based scenarios from identified causal claims.

**Research conclusion:** Step 2 is complete *as a frozen, auditable predictive baseline*. It is **not** adequate on its own to declare an officiating-induced change in win probability.
